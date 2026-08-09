import os
from google.genai import types
from src.config import LLM_MODEL_NAME, SIMILARITY_THRESHOLD
from src.ingestion import get_embedder, get_chroma_collection
from src.transcriber import load_branch_state

def search_summaries_hierarchy(query_text: str, active_branch: str):
    """
    Stage 1 & Stage 2 Search:
    Inspect master summary and per-file summaries for semantic relevance.
    Returns summary context hints.
    """
    state = load_branch_state(active_branch)
    master_summary = state.get("master_summary", "")
    files_dict = state.get("files", {})
    
    matching_files = []
    query_lower = query_text.lower()
    
    for fname, finfo in files_dict.items():
        f_summary = finfo.get("summary", "")
        # Basic keyword/semantic check across summaries
        if any(w in f_summary.lower() for w in query_lower.split() if len(w) > 3):
            matching_files.append({
                "filename": fname,
                "summary": f_summary,
                "type": finfo.get("type", "file")
            })
            
    return {
        "master_summary": master_summary,
        "matching_file_summaries": matching_files
    }

def query_snow_wiki(client, query_text: str, active_branch: str):
    """
    Main Hierarchical Query Pipeline:
    1. Search Master & File Summaries context.
    2. Execute ChromaDB vector search for granular chunks.
    3. Calculate cosine similarity = 1 - distance.
    4. If similarity >= 0.65 -> Generate internal RAG answer with video timestamp seek info.
    5. If similarity < 0.65 -> Perform Gemini Google Search Grounding targeting docs.servicenow.com.
    """
    embedder = get_embedder()
    collection = get_chroma_collection()

    # Stage 1 & 2: Summary checks
    summary_hints = search_summaries_hierarchy(query_text, active_branch)

    # Stage 3: Vector search in ChromaDB
    query_vector = embedder.encode([query_text]).tolist()

    try:
        results = collection.query(
            query_embeddings=query_vector,
            n_results=5,
            where={"branch": active_branch}
        )
    except Exception as e:
        results = None

    top_chunk = None
    top_metadata = None
    top_similarity = 0.0

    if results and results.get("documents") and results["documents"][0]:
        distances = results["distances"][0]
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]

        # In cosine space, distance is 1 - similarity -> similarity = 1 - distance
        top_distance = distances[0]
        top_similarity = max(0.0, 1.0 - top_distance)

        if top_similarity >= SIMILARITY_THRESHOLD:
            top_chunk = documents[0]
            top_metadata = metadatas[0]

    # STAGE 3 MATCH: Internal Knowledge Base RAG
    if top_similarity >= SIMILARITY_THRESHOLD and top_chunk and top_metadata:
        # Retrieve context from top matches
        context_blocks = []
        for doc, meta in zip(results["documents"][0][:3], results["metadatas"][0][:3]):
            context_blocks.append(
                f"[Source: {meta.get('source_file')} | Timestamp: {meta.get('timestamp', 'N/A')}]\n{doc}"
            )
        context_str = "\n\n".join(context_blocks)

        prompt = (
            f"You are the SNOW Wiki AI assistant, an expert in ServiceNow.\n"
            f"Answer the user's technical question based STRICTLY on the following internal training session context.\n"
            f"Provide a clear, step-by-step, actionable answer.\n\n"
            f"CONTEXT:\n{context_str}\n\n"
            f"QUESTION: {query_text}"
        )

        response = client.models.generate_content(
            model=LLM_MODEL_NAME,
            contents=prompt
        )

        answer_text = response.text or "Answer generation returned empty response."

        return {
            "found": True,
            "source_type": "internal",
            "answer": answer_text,
            "top_chunk": top_chunk,
            "source_file": top_metadata.get("source_file"),
            "timestamp": top_metadata.get("timestamp"),
            "timestamp_seconds": top_metadata.get("timestamp_seconds", 0),
            "media_path": top_metadata.get("media_path", ""),
            "similarity": top_similarity,
            "stage_used": "Stage 3 (Granular Vector Search)",
            "summary_hints": summary_hints
        }

    # STAGE 4 FALLBACK: Google Search Grounding for Live ServiceNow Documentation
    fallback_prompt = (
        f"You are an expert ServiceNow Technical Architect. The user's query was not found in internal training videos.\n"
        f"Search official ServiceNow documentation site:docs.servicenow.com or site:github.com/servicenow to answer the user's question accurately.\n"
        f"Include relevant configuration steps, tables, or APIs.\n\n"
        f"QUESTION: {query_text}"
    )

    grounding_config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())]
    )

    try:
        grounded_response = client.models.generate_content(
            model=LLM_MODEL_NAME,
            contents=fallback_prompt,
            config=grounding_config
        )
        answer_text = grounded_response.text or "Search grounding returned empty response."

        # Extract search grounding sources if present
        sources = []
        try:
            cand = grounded_response.candidates[0]
            if hasattr(cand, "grounding_metadata") and cand.grounding_metadata:
                gm = cand.grounding_metadata
                if hasattr(gm, "grounding_chunks") and gm.grounding_chunks:
                    for chunk in gm.grounding_chunks:
                        if hasattr(chunk, "web") and chunk.web:
                            sources.append({
                                "title": getattr(chunk.web, "title", "ServiceNow Docs"),
                                "url": getattr(chunk.web, "uri", "https://docs.servicenow.com")
                            })
        except Exception:
            pass

    except Exception as e:
        answer_text = f"Search grounding error: {str(e)}"
        sources = []

    return {
        "found": False,
        "source_type": "web_grounding",
        "answer": answer_text,
        "grounding_sources": sources,
        "similarity": top_similarity,
        "stage_used": "Stage 4 (Live ServiceNow Google Search Grounding)",
        "summary_hints": summary_hints
    }
