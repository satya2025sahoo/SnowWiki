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
        "End of Previous Page Content (PREVIOUS PAGE CONTEXT):\n"
        f"{prev_page_markdown if prev_page_markdown else '(No previous content)'}\n"
        "----------------------------------\n\n"
        "--- RAW CURRENT PAGE CONTENT ---\n"
        f"{current_page_raw}\n"
        "--------------------------------\n\n"
        "INSTRUCTIONS:\n"
        "1. Format the current page content strictly in Markdown. Merge smoothly with the previous page.\n"
        "   - DO NOT repeat any sentence, heading, or table row already present in PREVIOUS PAGE CONTEXT.\n"
        "   - If the previous page ended mid-table, do NOT re-emit the table header. Continue outputting ONLY the new rows.\n"
        "2. DO NOT blindly force new topics under the Active Heading. Break out if a major new chapter appears.\n"
        "3. Output ONLY the clean Markdown. Do not include introductory or concluding text. Do not wrap in ```markdown blocks.\n"
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

def process_pdf_rolling_markdown(pdf_path: str, output_md_path: str, max_pages: int = None):
    """
    Extracts text from a PDF page-by-page and uses an LLM to generate seamless Markdown and a rolling summary.
    """
    client = get_chat_client()
    doc = fitz.open(pdf_path)
    
    active_heading_stack = ""
    prev_page_markdown = ""
    rolling_summary = "None (Start of document)"
    global_toc = []
    all_clean_md = []
    
    total_pages = len(doc)
    if max_pages and max_pages < total_pages:
        total_pages = max_pages

    temp_buffer_path = os.path.join(tempfile.gettempdir(), f"temp_prev_page_{os.path.basename(pdf_path)}.md")
    if os.path.exists(temp_buffer_path):
        os.remove(temp_buffer_path)

    for i in range(total_pages):
        page = doc[i]
        raw_text = page.get_text()
        
        if not raw_text.strip():
            continue
            
        print(f"Processing PDF page {i+1}/{total_pages}...")
        
        if os.path.exists(temp_buffer_path):
            with open(temp_buffer_path, "r", encoding="utf-8") as f:
                prev_page_markdown = f.read()
        else:
            prev_page_markdown = ""
            
        clean_md, active_heading_stack, rolling_summary, global_toc = _run_llm_for_page(
            client=client,
            active_heading_stack=active_heading_stack,
            prev_page_markdown=prev_page_markdown,
            current_page_raw=raw_text,
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
    doc.close()


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
