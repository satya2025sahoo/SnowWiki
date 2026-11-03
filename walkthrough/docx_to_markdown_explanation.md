# DOCX to Markdown Conversion Pipeline

This document explains the complete lifecycle of how SnowWiki ingests a Microsoft Word (`.docx`) file and perfectly translates it into clean, semantic Markdown with inline image descriptions.

---

## 1. The Entry Point: `pipeline.py`

When a user uploads a `.docx` file, the ingestion engine (`process_and_ingest_files`) detects the extension and routes it to our specialized Word processor.

```python
# src/ingestion/pipeline.py (Snippet)

elif ext == ".docx":
    from src.ingestion.docx_utils import convert_docx_to_markdown
    
    # 1. Convert the DOCX bytes into semantic Markdown
    file_text = convert_docx_to_markdown(save_path, branch_name)
    
    # 2. Save the final Markdown to the branch's upload directory
    branch_dir = get_branch_upload_dir(branch_name)
    out_name = f"{os.path.splitext(filename)[0]}.md"
    markdown_path = os.path.join(branch_dir, out_name)
    
    with open(markdown_path, "w", encoding="utf-8") as f:
        f.write(file_text)
```

---

## 2. Mammoth Conversion & Inline Images: `docx_utils.py`

The heavy lifting is done in `src/ingestion/docx_utils.py`. We use **Mammoth**, a library specifically designed to convert Word documents into HTML/Markdown by focusing on semantic structure (headings, lists, tables) rather than exact visual formatting.

### 2a. The Inline Image Interceptor
When Mammoth parses the document from top to bottom, it occasionally hits an embedded image. We intercept this process using a custom `convert_image` handler.

```python
# src/ingestion/docx_utils.py -> convert_docx_to_markdown() (Snippet)

image_describer = ImageDescriberAgent()

def convert_image(image):
    # 1. Save the image to the local disk
    ext = ".png"
    if image.content_type == "image/jpeg": ext = ".jpg"
    filename = f"{prefix}_inline_{uuid.uuid4().hex[:6]}{ext}"
    out_path = os.path.join(image_dir, filename)
    
    with image.open() as image_bytes:
        with open(out_path, "wb") as f:
            f.write(image_bytes.read())
            
    # 2. Call the LLM to generate an OCR text extraction and description
    desc = image_describer.describe_from_path(out_path)
        
    # 3. Return a markdown dict to Mammoth to place it EXACTLY where it appears in the text
    return {"src": out_path, "alt": f"Image - Description: {desc}"}
```

> [!TIP]
> **Why do it this way?** By intercepting Mammoth directly, the image is guaranteed to appear **inline** exactly where the author placed it, rather than being blindly dumped at the bottom of the document.

### 2b. The Mammoth `style_map`
We enforce strict style mapping so that Word's proprietary styles translate into clean Markdown tags.

```python
style_map = (
    "p[style-name='Heading 1'] => h1:fresh\n"
    "p[style-name='Heading 2'] => h2:fresh\n"
    "p[style-name='Title'] => h1:fresh\n"
    "p[style-name='Code'] => pre:fresh\n"
)
result = mammoth.convert_to_markdown(
    docx_file, 
    style_map=style_map,
    convert_image=mammoth.images.img_element(convert_image)
)
raw_md = result.value
```

---

## 3. The Normalization Pass

Word documents are notorious for containing terrible user-generated formatting (e.g., using bold text instead of actual headings, or writing sentences inside a "Heading 2" block).

After Mammoth gives us the `raw_md`, we pass it through `_normalize_docx_markdown()` to fix these visual bugs.

```python
# src/ingestion/docx_utils.py -> _normalize_docx_markdown() (Snippets)
```

### Unpacking Inline Images
Mammoth outputs images as `![Image - Description: ...](path)`. We reformat this into a much cleaner multi-line block so the LLM chunker captures the description easily.

```python
image_match = re.match(r"^!\[Image - Description: (.*?)\]\((.*?)\)$", line_clean)
if image_match:
    desc = image_match.group(1)
    path = image_match.group(2)
    out_lines.append(f"![Image]({path})")
    out_lines.append("")
    out_lines.append(f"*Description: {desc}*")
```

### Demoting "Fake" Headings (Word Style Abuse)
If an author accidentally applied the "Heading 2" style to a normal bullet point or sentence (which usually ends in a period), we demote it back to a standard bullet point to prevent it from ruining the Markdown document hierarchy.

```python
fake_heading_match = re.match(r"^(#{1,6})\s+(.*)$", line_clean)
if fake_heading_match:
    h_content = fake_heading_match.group(2)
    # True headings don't end in a period. If it does, it's a sentence.
    if h_content.endswith(".") and len(h_content.split()) > 4:
        out_lines.append(f"- {h_content}")
```

### Removing Phantom Parent Bullets
Mammoth sometimes emits an empty `-` bullet when parsing nested lists. We look ahead to the next line, and if it's an indented bullet, we safely delete the empty parent.

```python
if line_clean in ["-", "*", "+"]:
    if i + 1 < len(lines):
        next_line = lines[i + 1]
        if next_line.startswith("\t- ") or next_line.startswith("    - "):
            continue # Skip emitting this empty bullet
```

---

## 4. OCR & Vision API (`image_describer.py`)

When an image is passed to `describe_from_path()`, it is base64 encoded and sent to a Vision LLM (e.g., Qwen-Flash or Gemini) with a strict `SYSTEM_PROMPT`.

```python
# src/ingestion/image_describer.py (Snippet)

SYSTEM_PROMPT = """
You are an expert AI vision assistant. Your task is to analyze the provided image...
3. EXTRACTING ALL TEXT: If the image contains any readable text, labels, code snippets, or handwriting, you MUST transcribe it verbatim and include it in your description.
"""
```

Because free-tier APIs often throw `429 Too Many Requests` when hit with multiple images simultaneously, the `image_describer.py` includes a robust **Exponential Backoff** loop (waiting 5s, 10s, 20s, up to 80s) to guarantee the image eventually processes successfully without crashing the pipeline.
