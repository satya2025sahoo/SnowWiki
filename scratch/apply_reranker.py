import os

src_file = os.path.join(os.path.dirname(__file__), "..", "src", "route_handlers.py")
with open(src_file, "r", encoding="utf-8") as f:
    code = f.read()

# Normalize CRLF in memory if needed
code = code.replace("\r\n", "\n")

target = """    # ── ChromaDB lookup ──────────────────────────────────────────────────────
    try:
        results = collection.query(
            query_embeddings=query_vector,
            n_results=5,
            where={"branch": active_branch},
        )
    except Exception:
        results = None

    top_chunk        = None
    top_metadata     = None
    similarity       = 0.0
    retrieved_chunks: list[dict] = []
    legacy_index     = False
    parent_sections  = []

    if results and results.get("documents") and results["documents"][0]:
        distances  = results["distances"][0]
        similarity = max(0.0, 1.0 - distances[0])

        if similarity >= SIMILARITY_THRESHOLD:"""

replacement = """    # ── Hybrid Search (Dense + BM25) + Cross-Encoder Reranker ───────────────
    top_rerank_score = None
    try:
        from src.hybrid_search import hybrid_search
        from src.reranker import rerank_candidates
        from src.config import RERANK_CANDIDATE_POOL_SIZE, RERANK_SCORE_THRESHOLD, RERANK_TOP_N

        hybrid_res = hybrid_search(
            query=search_query,
            active_branch=active_branch,
            top_k=RERANK_CANDIDATE_POOL_SIZE,
            dense_weight=0.6,
            sparse_weight=0.4,
        )
        candidates = hybrid_res.get("fused_results", [])
        top_reranked, top_rerank_score = rerank_candidates(
            query=search_query,
            candidates=candidates,
            top_n=RERANK_TOP_N,
        )

        results = {
            "ids": [[c["id"] for c in top_reranked]],
            "documents": [[c["document"] for c in top_reranked]],
            "metadatas": [[c["metadata"] for c in top_reranked]],
            "distances": [[max(0.0, 1.0 - c["rerank_score"]) for c in top_reranked]],
            "raw_dense_hits": hybrid_res.get("raw_dense_hits", []),
            "raw_bm25_hits": hybrid_res.get("raw_bm25_hits", []),
            "top_rerank_score": top_rerank_score,
        }
    except Exception as exc:
        print(f"[route_handlers] Reranker / Hybrid search failed, falling back to pure dense: {exc}")
        try:
            results = collection.query(
                query_embeddings=query_vector,
                n_results=5,
                where={"branch": active_branch},
            )
            top_rerank_score = None
        except Exception:
            results = None
            top_rerank_score = None

    top_chunk        = None
    top_metadata     = None
    similarity       = 0.0
    retrieved_chunks: list[dict] = []
    legacy_index     = False
    parent_sections  = []

    if results and results.get("documents") and results["documents"][0]:
        distances  = results["distances"][0]
        similarity = max(0.0, 1.0 - distances[0])

        gate_threshold = RERANK_SCORE_THRESHOLD if top_rerank_score is not None else SIMILARITY_THRESHOLD
        if similarity >= gate_threshold:"""

# Update trace
trace_target = """                    "stage2_retrieval": {
                        "method":              "Parent-Child Vector Search" if not legacy_index else "Legacy Vector Search",
                        "similarity_score":    round(similarity, 3),
                        "child_chunks_found":  len(retrieved_chunks),
                        "parent_ids_fetched":  list(dict.fromkeys(c.get("parent_id", "") for c in retrieved_chunks if c.get("parent_id"))),
                        "context_sent_to_llm": context_str[:1200] + " ... [truncated]" if len(context_str) > 1200 else context_str,
                    },"""

trace_replacement = """                    "stage2_retrieval": {
                        "method":              "Hybrid Search (Dense + BM25) + Cross-Encoder Reranker" if not legacy_index else "Legacy Reranker Search",
                        "similarity_score":    round(similarity, 3),
                        "rerank_score":        round(top_rerank_score, 4) if top_rerank_score is not None else round(similarity, 3),
                        "child_chunks_found":  len(retrieved_chunks),
                        "dense_matches":       len(results.get("raw_dense_hits", [])) if results else 0,
                        "bm25_matches":        len(results.get("raw_bm25_hits", [])) if results else 0,
                        "parent_ids_fetched":  list(dict.fromkeys(c.get("parent_id", "") for c in retrieved_chunks if c.get("parent_id"))),
                        "context_sent_to_llm": context_str[:1200] + " ... [truncated]" if len(context_str) > 1200 else context_str,
                    },"""

if target in code:
    code = code.replace(target, replacement, 1)
    if trace_target in code:
        code = code.replace(trace_target, trace_replacement, 1)
    with open(src_file, "w", encoding="utf-8") as f:
        f.write(code)
    print("SUCCESS: route_handlers.py updated successfully")
else:
    print("ERROR: Target block not found in route_handlers.py")
