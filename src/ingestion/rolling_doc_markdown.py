import os
import json
import tempfile
import pymupdf as fitz
from src.llm_wrapper import get_chat_client
from src.config import GROQ_RESPONSE_MODEL

def _atomic_write(filepath: str, content: str):
    tmp_path = filepath + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp_path, filepath)

def _run_llm_for_page(client, active_heading_stack: str, prev_page_markdown: str, current_page_raw: str, page_num: int, global_toc: list, current_rolling_summary: str) -> tuple[str, str, str, list]:
    toc_string = "\n".join(global_toc[-20:]) if global_toc else "None (Start of document)"
    
    # CALL 1: MARKDOWN GENERATION
    md_prompt = (
        "You are an expert technical editor converting raw document pages into seamless hierarchical Markdown.\n"
        "Your task is to take the raw text of the current page and convert it into clean, well-structured Markdown, "
        "ensuring it continues seamlessly from the previous page.\n\n"
        "--- CONTEXT FROM PREVIOUS PAGES ---\n"
        f"Active Heading Hierarchy (Immediate context): {active_heading_stack if active_heading_stack else 'None'}\n"
        f"Recent Table of Contents (Broader context): \n{toc_string}\n\n"
        f"Document Rolling Summary (Overall knowledge so far): \n{current_rolling_summary}\n\n"
        "End of Previous Page Content (PREVIOUS PAGE CONTEXT):\n"
        f"{prev_page_markdown if prev_page_markdown else '(No previous content)'}\n"
        "----------------------------------\n\n"
        "--- RAW CURRENT PAGE CONTENT ---\n"
        f"{current_page_raw}\n"
        "--------------------------------\n\n"
        "INSTRUCTIONS:\n"
        "1. Format the current page content strictly in standard Markdown. Use `#`, `##`, `###` for headings, and `*` for ALL bullet points (never `-`).\n"
        "2. DO NOT use `*` for headings or `#` for bullet points. Adhere strictly to standard Markdown syntax.\n"
        "3. Merge smoothly with the previous page.\n"
        "   * DO NOT repeat any sentence, heading, or table row already present in PREVIOUS PAGE CONTEXT.\n"
        "   * If the previous page ended mid-table, do NOT re-emit the table header. Continue outputting ONLY the new rows.\n"
        "4. DO NOT blindly force new topics under the Active Heading. Break out if a major new chapter appears.\n"
        "5. PRESERVE ALL IMAGES AND VISUAL ANALYSIS: If the raw content contains image tags (e.g. ![IMG_xxxx](images/...) or Visual Analysis blocks), keep them intact at their proper conceptual location.\n"
        "6. Output ONLY the clean Markdown. Do not include introductory or concluding text. Do not wrap in ```markdown blocks.\n"
    )

    clean_markdown = current_page_raw
    new_active_stack = active_heading_stack
    new_toc = global_toc.copy()
    
    try:
        response1 = client.chat.completions.create(
            model=GROQ_RESPONSE_MODEL,
            messages=[{"role": "user", "content": md_prompt}],
            max_tokens=4096,
            temperature=0.1,
        )
        content1 = response1.choices[0].message.content.strip()
        
        # Clean up code blocks if LLM still includes them
        if content1.startswith("```markdown"):
            content1 = content1[11:]
        if content1.startswith("```"):
            content1 = content1[3:]
        if content1.endswith("```"):
            content1 = content1[:-3]
        clean_markdown = content1.strip()
        
        # Extract active heading
        import re
        headings = re.findall(r'^(#{1,6})\s+(.*)$', clean_markdown, flags=re.MULTILINE)
        if headings:
            last_heading = headings[-1]
            new_active_stack = f"{last_heading[0]} {last_heading[1]}"
            for h in headings:
                if len(h[0]) <= 3:
                    if not new_toc or f"{h[0]} {h[1]}" != new_toc[-1]:
                        new_toc.append(f"{h[0]} {h[1]}")
            if len(new_toc) > 20:
                new_toc = new_toc[-20:]
                
    except Exception as e:
        print(f"[rolling_doc_markdown] LLM Error (Markdown) on page {page_num}: {e}")

    # CALL 2: SUMMARY GENERATION
    summary_prompt = (
        "You are an expert technical summarizer.\n"
        "Your task is to update a rolling summary based on newly processed Markdown content.\n\n"
        "--- CURRENT ROLLING SUMMARY ---\n"
        f"{current_rolling_summary}\n\n"
        "--- NEWLY PROCESSED CONTENT ---\n"
        f"{clean_markdown}\n\n"
        "INSTRUCTIONS:\n"
        "1. Update the Current Rolling Summary to incorporate topics from the newly processed content.\n"
        "2. Maximum 15 top-level bullets total, up to 3 sub-bullets each.\n"
        "3. Merge new details into existing bullets instead of endlessly appending. Synthesize and compress earlier points.\n"
        "4. Output ONLY the updated Markdown bullet points. Do not include introductory text.\n"
    )
    
    new_rolling_summary = current_rolling_summary
    try:
        response2 = client.chat.completions.create(
            model=GROQ_RESPONSE_MODEL,
            messages=[{"role": "user", "content": summary_prompt}],
            max_tokens=2048,
            temperature=0.1,
        )
        new_rolling_summary = response2.choices[0].message.content.strip()
    except Exception as e:
        print(f"[rolling_doc_markdown] LLM Error (Summary) on page {page_num}: {e}")

    return clean_markdown, new_active_stack, new_rolling_summary, new_toc

def process_pdf_rolling_markdown(
    pdf_path: str,
    output_md_path: str,
    image_dir: str | None = None,
    branch_name: str = "default",
    max_pages: int | None = None,
    status_callback: callable | None = None,
):
    """
    Unified entry point for PDF to Markdown conversion.
    Delegates to the dedicated rolling_pdf_markdown pipeline.
    """
    from src.ingestion.rolling_pdf_markdown import process_pdf_rolling_markdown as _impl
    return _impl(
        pdf_path=pdf_path,
        output_md_path=output_md_path,
        image_dir=image_dir,
        branch_name=branch_name,
        max_pages=max_pages,
        status_callback=status_callback,
    )


def process_docx_rolling_markdown(docx_path: str, output_md_path: str, max_blocks: int = None):
    """
    Extracts text from a DOCX file in chunks (paragraphs) and uses an LLM to generate seamless Markdown and a rolling summary.
    """
    try:
        from docx import Document
    except ImportError:
        print("python-docx is not installed. Cannot process DOCX.")
        return
        
    client = get_chat_client()
    doc = Document(docx_path)
    
    blocks = []
    current_block = []
    current_word_count = 0
    
    for p in doc.paragraphs:
        text = p.text.strip()
        if text:
            current_block.append(text)
            current_word_count += len(text.split())
            
        if current_word_count >= 500:
            blocks.append("\n".join(current_block))
            current_block = []
            current_word_count = 0
            
    if current_block:
        blocks.append("\n".join(current_block))
        
    if max_blocks and max_blocks < len(blocks):
        blocks = blocks[:max_blocks]
        
    active_heading_stack = ""
    prev_page_markdown = ""
    rolling_summary = "None (Start of document)"
    global_toc = []
    all_clean_md = []
    
    temp_buffer_path = os.path.join(tempfile.gettempdir(), f"temp_prev_page_{os.path.basename(docx_path)}.md")
    if os.path.exists(temp_buffer_path):
        os.remove(temp_buffer_path)
        
    for i, block_text in enumerate(blocks):
        print(f"Processing DOCX block {i+1}/{len(blocks)}...")
        
        if os.path.exists(temp_buffer_path):
            with open(temp_buffer_path, "r", encoding="utf-8") as f:
                prev_page_markdown = f.read()
        else:
            prev_page_markdown = ""
            
        clean_md, active_heading_stack, rolling_summary, global_toc = _run_llm_for_page(
            client=client,
            active_heading_stack=active_heading_stack,
            prev_page_markdown=prev_page_markdown,
            current_page_raw=block_text,
            page_num=i+1,
            global_toc=global_toc,
            current_rolling_summary=rolling_summary
        )
        
        _atomic_write(temp_buffer_path, clean_md)
        all_clean_md.append(clean_md)
        
        print(f"  -> Active Heading: {active_heading_stack}")
        bullet_count = rolling_summary.count("- ") + rolling_summary.count("* ")
        print(f"  -> Summary Bullets: {bullet_count}")
        
    summary_md_path = output_md_path.replace(".md", "_summary.md")
    with open(summary_md_path, "w", encoding="utf-8") as sum_f:
        sum_f.write("# Document Summary & Topic Overview\n\n")
        sum_f.write(rolling_summary)
        
    with open(output_md_path, "w", encoding="utf-8") as out_f:
        out_f.write("\n\n".join(all_clean_md))

    if os.path.exists(temp_buffer_path):
        os.remove(temp_buffer_path)


def process_markdown_rolling_markdown(md_path: str, output_md_path: str, chunk_size: int = 2000):
    """
    2000-character sliding-window Markdown rewriter with rolling summary.

    Per-iteration logic
    -------------------
    Iteration 1  (chars 0 – chunk_size):
        Call 1 : RAW[1]                              → clean MD[1]
        Call 2 : RAW[1]                              → SUMMARY[1]

    Iteration N  (chars (N-1)*chunk – N*chunk):
        Call 1 : RAW[N]  + MD[N-1]   + SUMMARY[N-1] → clean MD[N]
        Call 2 : SUMMARY[N-1] + MD[N]               → compressed SUMMARY[N]

    The summary is *rewritten* each time (never just appended) so it stays
    concise while incorporating every chunk seen so far.

    Outputs
    -------
    output_md_path                           – Full cleaned / rewritten Markdown.
    output_md_path.replace('.md','_summary.md') – Final compressed rolling summary.
    """
    with open(md_path, "r", encoding="utf-8") as f:
        raw_md = f.read()

    # ── Slice into non-overlapping 2000-char chunks ───────────────────────────
    chunks = [raw_md[i: i + chunk_size] for i in range(0, len(raw_md), chunk_size)]
    if not chunks:
        print("[process_markdown_rolling_markdown] File is empty — nothing to process.")
        return

    client      = get_chat_client()
    prev_clean  = ""          # MD[N-1]  — empty on first iteration
    rolling_summary = ""      # SUMMARY[N-1] — empty on first iteration
    all_clean_md: list = []

    total = len(chunks)
    for i, raw_chunk in enumerate(chunks):
        iteration = i + 1
        print(f"[rolling_md] Chunk {iteration}/{total}  ({len(raw_chunk)} chars)...")

        is_first = (i == 0)

        # ════════════════════════════════════════════════════════════════════
        # CALL 1 — Generate clean Markdown for this chunk
        # ════════════════════════════════════════════════════════════════════
        if is_first:
            md_prompt = (
                "You are an expert technical editor converting raw Markdown into clean, "
                "well-structured hierarchical Markdown.\n\n"
                "--- RAW CONTENT (Chunk 1) ---\n"
                f"{raw_chunk}\n"
                "-----------------------------\n\n"
                "INSTRUCTIONS:\n"
                "1. Convert the raw content into clean, standard Markdown.\n"
                "   * Use `#`, `##`, `###` for headings.\n"
                "   * Use `*` for ALL bullet points — NEVER `-`.\n"
                "   * Nest sub-points as `  *` (2-space indent) under their parent.\n"
                "2. Structure as parent-child hierarchy: concept as heading, details as `*` sub-bullets.\n"
                "3. Preserve ALL information — do not drop anything.\n"
                "4. Output ONLY the clean Markdown. Do not wrap in ```markdown blocks.\n"
            )
        else:
            md_prompt = (
                "You are an expert technical editor converting raw Markdown into clean, "
                "well-structured hierarchical Markdown.\n\n"
                "--- ROLLING SUMMARY (knowledge so far) ---\n"
                f"{rolling_summary}\n"
                "------------------------------------------\n\n"
                "--- PREVIOUS CHUNK (clean Markdown, for continuity) ---\n"
                f"{prev_clean}\n"
                "-------------------------------------------------------\n\n"
                f"--- CURRENT RAW CONTENT (Chunk {iteration}) ---\n"
                f"{raw_chunk}\n"
                "------------------------------------------------\n\n"
                "INSTRUCTIONS:\n"
                "1. Convert ONLY the CURRENT RAW CONTENT into clean Markdown.\n"
                "   * Use `#`, `##`, `###` for headings.\n"
                "   * Use `*` for ALL bullet points — NEVER `-`.\n"
                "   * Nest sub-points as `  *` (2-space indent) under their parent.\n"
                "2. Use the PREVIOUS CHUNK and ROLLING SUMMARY as context to:\n"
                "   * Continue mid-sentence / mid-list items smoothly.\n"
                "   * Place content under the correct parent heading.\n"
                "   * Avoid repeating anything already in the PREVIOUS CHUNK.\n"
                "3. Structure as parent-child hierarchy: concept as heading, details as `*` sub-bullets.\n"
                "4. Preserve ALL information from the current chunk — do not drop anything.\n"
                "5. Output ONLY the clean Markdown for this chunk. Do not wrap in ```markdown blocks.\n"
            )

        clean_md = raw_chunk  # fallback: raw text if LLM fails
        try:
            resp1 = client.chat.completions.create(
                model=GROQ_RESPONSE_MODEL,
                messages=[{"role": "user", "content": md_prompt}],
                max_tokens=4096,
                temperature=0.1,
            )
            c1 = resp1.choices[0].message.content.strip()
            # Strip accidental code fences
            if c1.startswith("```markdown"):
                c1 = c1[11:]
            if c1.startswith("```"):
                c1 = c1[3:]
            if c1.endswith("```"):
                c1 = c1[:-3]
            clean_md = c1.strip()
        except Exception as e:
            print(f"[rolling_md] LLM Error (Call 1) chunk {iteration}: {e}")

        # ════════════════════════════════════════════════════════════════════
        # CALL 2 — Generate / rewrite rolling summary
        # ════════════════════════════════════════════════════════════════════
        if is_first:
            summary_prompt = (
                "You are an expert technical summarizer.\n\n"
                "--- NEWLY PROCESSED CONTENT (Chunk 1) ---\n"
                f"{clean_md}\n"
                "------------------------------------------\n\n"
                "INSTRUCTIONS:\n"
                "1. Write a concise summary of the content above.\n"
                "2. Use at most 10 top-level `*` bullets, up to 3 sub-bullets each (also `*`, never `-`).\n"
                "3. Output ONLY the Markdown bullet points. No intro text.\n"
            )
        else:
            summary_prompt = (
                "You are an expert technical summarizer.\n\n"
                "--- CURRENT ROLLING SUMMARY (covers all previous chunks) ---\n"
                f"{rolling_summary}\n"
                "-------------------------------------------------------------\n\n"
                f"--- NEWLY PROCESSED CONTENT (Chunk {iteration}) ---\n"
                f"{clean_md}\n"
                "----------------------------------------------------\n\n"
                "INSTRUCTIONS:\n"
                "1. Rewrite the CURRENT ROLLING SUMMARY to incorporate key information "
                "from the NEWLY PROCESSED CONTENT.\n"
                "2. Do NOT just append — merge, compress, and synthesise. "
                "The result must still feel like one coherent summary.\n"
                "3. Use at most 15 top-level `*` bullets, up to 3 sub-bullets each (also `*`, never `-`).\n"
                "4. Output ONLY the updated Markdown bullet points. No intro text.\n"
            )

        try:
            resp2 = client.chat.completions.create(
                model=GROQ_RESPONSE_MODEL,
                messages=[{"role": "user", "content": summary_prompt}],
                max_tokens=2048,
                temperature=0.1,
            )
            rolling_summary = resp2.choices[0].message.content.strip()
        except Exception as e:
            print(f"[rolling_md] LLM Error (Call 2) chunk {iteration}: {e}")

        # ── Carry forward for next iteration ─────────────────────────────────
        prev_clean = clean_md
        all_clean_md.append(clean_md)

        bullets = rolling_summary.count("* ")
        print(f"  -> Clean MD length : {len(clean_md)} chars")
        print(f"  -> Summary bullets : {bullets}")

    # ── Write outputs ─────────────────────────────────────────────────────────
    summary_md_path = output_md_path.replace(".md", "_summary.md")
    with open(summary_md_path, "w", encoding="utf-8") as f:
        f.write("# Document Summary & Topic Overview\n\n")
        f.write(rolling_summary)

    _atomic_write(output_md_path, "\n\n".join(all_clean_md))
    print(f"[rolling_md] Done.    Output  : {output_md_path}")
    print(f"[rolling_md] Done.    Summary : {summary_md_path}")

