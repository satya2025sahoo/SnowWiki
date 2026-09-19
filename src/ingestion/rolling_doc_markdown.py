import os
import re
import pymupdf as fitz
from src.llm_wrapper import get_chat_client
from src.config import GROQ_RESPONSE_MODEL

def _run_llm_for_page(client, active_heading_stack: str, tail_context: str, current_page_raw: str, page_num: int, global_toc: list) -> tuple[str, str, str, list]:
    """
    Runs the LLM to format the current page's markdown and updates state.
    Returns (cleaned_markdown, updated_active_heading_stack, updated_tail_context, updated_global_toc)
    """
    toc_string = "\n".join(global_toc[-15:]) if global_toc else "None (Start of document)"
    
    prompt = (
        "You are an expert technical editor converting raw document pages into seamless hierarchical Markdown.\n"
        "Your task is to take the raw text of the current page and convert it into clean, well-structured Markdown, "
        "ensuring it continues seamlessly from the previous page.\n\n"
        "--- CONTEXT FROM PREVIOUS PAGES ---\n"
        f"Active Heading Hierarchy (Immediate context): {active_heading_stack if active_heading_stack else 'None'}\n"
        f"Recent Table of Contents (Broader context): \n{toc_string}\n\n"
        f"End of Previous Page Content (Tail):\n{tail_context if tail_context else '(No previous content)'}\n"
        "----------------------------------\n\n"
        "--- RAW CURRENT PAGE CONTENT ---\n"
        f"{current_page_raw}\n"
        "--------------------------------\n\n"
        "INSTRUCTIONS:\n"
        "1. Format the current page content strictly in Markdown.\n"
        "2. Merge smoothly with the previous page. If the previous page ended mid-sentence, mid-list, or mid-table, complete it here without adding artificial line breaks or repeating headings.\n"
        "3. Review the 'Recent Table of Contents' to understand the broader structure. \n"
        "4. DO NOT blindly force new topics under the Active Heading. If the raw text clearly introduces a major new chapter, topic, or section, you MUST break out of the current hierarchy and create a new Top-Level (`#`) or Secondary (`##`) heading.\n"
        "5. Output ONLY the clean Markdown for this page. Do not include introductory or concluding text, and do not wrap in ```markdown blocks.\n"
    )

    try:
        response = client.chat.completions.create(
            model=GROQ_RESPONSE_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
            temperature=0.2,
        )
        content = response.choices[0].message.content.strip()
        
        # Clean up code blocks if LLM still includes them
        if content.startswith("```markdown"):
            content = content[11:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
            
        content = content.strip()
        
        # Heuristically update the active heading stack and TOC
        headings = re.findall(r'^(#{1,6})\s+(.*)$', content, flags=re.MULTILINE)
        new_active_stack = active_heading_stack
        new_toc = global_toc.copy()
        
        if headings:
            last_heading = headings[-1]
            new_active_stack = f"{last_heading[0]} {last_heading[1]}"
            for h in headings:
                # Add only major headings to the TOC to keep context clean
                if len(h[0]) <= 3:
                    new_toc.append(f"{h[0]} {h[1]}")
            
        # Update tail context (last ~250 words)
        words = content.split()
        new_tail = " ".join(words[-250:]) if len(words) > 250 else content
        
        return content, new_active_stack, new_tail, new_toc

    except Exception as e:
        print(f"[rolling_doc_markdown] LLM Error on page {page_num}: {e}")
        # Fallback: just return the raw text
        return current_page_raw, active_heading_stack, tail_context, global_toc


def process_pdf_rolling_markdown(pdf_path: str, output_md_path: str, max_pages: int = None):
    """
    Extracts text from a PDF page-by-page and uses an LLM to generate seamless Markdown.
    """
    client = get_chat_client()
    doc = fitz.open(pdf_path)
    
    active_heading_stack = ""
    tail_context = ""
    global_toc = []
    
    total_pages = len(doc)
    if max_pages and max_pages < total_pages:
        total_pages = max_pages

    with open(output_md_path, "w", encoding="utf-8") as out_f:
        for i in range(total_pages):
            page = doc[i]
            raw_text = page.get_text()
            
            if not raw_text.strip():
                continue
                
            print(f"Processing PDF page {i+1}/{total_pages}...")
            
            clean_md, active_heading_stack, tail_context, global_toc = _run_llm_for_page(
                client=client,
                active_heading_stack=active_heading_stack,
                tail_context=tail_context,
                current_page_raw=raw_text,
                page_num=i+1,
                global_toc=global_toc
            )
            
            out_f.write(clean_md + "\n\n")

    doc.close()


def process_docx_rolling_markdown(docx_path: str, output_md_path: str, max_blocks: int = None):
    """
    Extracts text from a DOCX file in chunks (paragraphs) and uses an LLM to generate seamless Markdown.
    Since DOCX doesn't have explicit pages, we group text into ~500-word blocks.
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
    tail_context = ""
    global_toc = []
    
    with open(output_md_path, "w", encoding="utf-8") as out_f:
        for i, block_text in enumerate(blocks):
            print(f"Processing DOCX block {i+1}/{len(blocks)}...")
            
            clean_md, active_heading_stack, tail_context, global_toc = _run_llm_for_page(
                client=client,
                active_heading_stack=active_heading_stack,
                tail_context=tail_context,
                current_page_raw=block_text,
                page_num=i+1,
                global_toc=global_toc
            )
            
            out_f.write(clean_md + "\n\n")
