import os
import re
from src.config import TRANSCRIPTS_DIR
from src.llm_wrapper import get_chat_client
from src.config import GROQ_RESPONSE_MODEL

def parse_timestamp_lines(raw_text: str) -> list[tuple[int, str, str]]:
    """
    Extracts (timestamp_seconds, timestamp_str, text_content) from `[MM:SS] text` lines.
    """
    pattern = re.compile(r"^\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(.*)$")
    lines = raw_text.splitlines()
    
    parsed = []
    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue
        match = pattern.match(line_str)
        if match:
            ts_str = match.group(1)
            text_part = match.group(2)
            
            # parse to seconds
            parts = ts_str.split(":")
            secs = 0
            try:
                if len(parts) == 2:
                    secs = int(parts[0]) * 60 + int(parts[1])
                elif len(parts) == 3:
                    secs = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            except ValueError:
                pass
                
            parsed.append((secs, ts_str, text_part))
        else:
            # If line doesn't match timestamp, assume 0s or append to previous if we wanted to
            # But the prompt says Whisper always emits lines in this format
            pass
            
    return parsed

def slice_transcript_windows(parsed_lines: list[tuple[int, str, str]], window_duration=300, stride=240) -> list[dict]:
    """
    Slices transcript into overlapping 5-minute chunks (300s window, 240s stride).
    """
    if not parsed_lines:
        return []
        
    chunks = []
    max_time = parsed_lines[-1][0]
    start_time = 0
    
    while start_time <= max_time:
        end_time = start_time + window_duration
        
        chunk_lines = []
        for secs, ts_str, text in parsed_lines:
            if start_time <= secs <= end_time:
                chunk_lines.append(f"[{ts_str}] {text}")
                
        if chunk_lines:
            chunks.append({
                "start": start_time,
                "end": end_time,
                "content": "\n".join(chunk_lines)
            })
            
        start_time += stride
        
    return chunks

def generate_rolling_markdown(transcript_text: str, filename: str, branch_name: str) -> tuple[str, str]:
    """
    Manages the Rolling 2-Page Context Window and generates structured markdown.
    Returns (markdown_text, saved_markdown_path).
    """
    if not transcript_text.strip():
        return "", ""
        
    parsed = parse_timestamp_lines(transcript_text)
    
    # If parsing failed, fallback
    if not parsed:
        chunks = [{"start": 0, "end": 300, "content": transcript_text[:10000]}] # rough fallback
    else:
        chunks = slice_transcript_windows(parsed, window_duration=300, stride=240)
        
    client = get_chat_client()
    
    active_page_content = ""
    all_pages = []
    current_page_num = 1
    
    for i, chunk in enumerate(chunks):
        page_num = (i // 2) + 1
        
        if page_num > current_page_num:
            # We shifted to a new page, save the old page and start fresh
            all_pages.append(active_page_content)
            active_page_content = ""
            current_page_num = page_num
            
        prompt = (
            "You are a technical documentation assistant. Your task is to process a segment of a raw video/audio transcript "
            "and format it into structured Markdown notes.\n\n"
            f"--- Active Page Content ---\n"
            f"{active_page_content if active_page_content else '(New page - no content yet)'}\n"
            f"---------------------------\n\n"
            f"--- New Transcript Snippet ({chunk['start']}s to {chunk['end']}s) ---\n"
            f"{chunk['content']}\n"
            f"---------------------------\n\n"
            "INSTRUCTIONS:\n"
            "Review the active Markdown page content. Determine if the new transcript continues under the last active `## Heading` or introduces a new topic.\n"
            "If it continues, append points under the existing heading. If a new topic starts, close the previous section and create a new `## Heading`. "
            "When creating a new heading, you MUST include the start timestamp of the new topic inside the heading in the format: `## [MM:SS] Topic Name` or `## [HH:MM:SS] Topic Name`.\n"
            "Output ONLY the updated full clean Markdown for the current active page, with the new content seamlessly integrated. "
            "Use bullet points, bold key terms, and keep it strictly technical and structured. Do not output anything outside the markdown content."
        )
        
        try:
            response = client.chat.completions.create(
                model=GROQ_RESPONSE_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2048,
                temperature=0.2,
            )
            # The model should return the newly updated active page content
            new_content = response.choices[0].message.content.strip()
            # Remove markdown code blocks if the model wrapped it
            if new_content.startswith("```markdown"):
                new_content = new_content[11:]
            if new_content.startswith("```"):
                new_content = new_content[3:]
            if new_content.endswith("```"):
                new_content = new_content[:-3]
                
            active_page_content = new_content.strip()
        except Exception as e:
            print(f"[markdown_generator] Error calling LLM: {e}")
            # simple append fallback
            active_page_content += f"\n\n## Transcript Snippet\n{chunk['content']}"
            
    if active_page_content:
        all_pages.append(active_page_content)
        
    final_markdown = "\n\n".join(all_pages)
    
    # Save the markdown file
    branch_dir = os.path.join(TRANSCRIPTS_DIR, branch_name)
    os.makedirs(branch_dir, exist_ok=True)
    out_name = f"{os.path.splitext(filename)[0]}.md"
    out_path = os.path.join(branch_dir, out_name)
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(final_markdown)
        
    return final_markdown, out_path
