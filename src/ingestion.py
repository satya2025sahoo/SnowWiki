import os
import re
import json
import chromadb
from sentence_transformers import SentenceTransformer
from pypdf import PdfReader
from docx import Document

from src.config import (
    CHROMA_DB_DIR, UPLOADS_DIR, EMBEDDING_MODEL_NAME, 
    COLLECTION_NAME
)
from src.transcriber import (
    transcribe_media_gemini, generate_file_summary, 
    load_branch_state, save_branch_state, update_master_branch_summary
)

# Global embedding model instance cache
_EMBEDDER = None

def get_embedder():
    global _EMBEDDER
    if _EMBEDDER is None:
        _EMBEDDER = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _EMBEDDER

def get_chroma_collection():
    client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )
    return collection

def get_branch_upload_dir(branch_name: str) -> str:
    branch_dir = os.path.join(UPLOADS_DIR, branch_name)
    os.makedirs(branch_dir, exist_ok=True)
    return branch_dir

def extract_document_text(file_path: str, file_ext: str) -> str:
    """Extract raw text from PDF, DOCX, or TXT file."""
    ext = file_ext.lower()
    text = ""
    
    if ext == ".pdf":
        reader = PdfReader(file_path)
        pages_text = []
        for i, page in enumerate(reader.pages):
            p_text = page.extract_text()
            if p_text:
                pages_text.append(p_text)
        text = "\n\n".join(pages_text)
        
    elif ext == ".docx":
        doc = Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n\n".join(paragraphs)
        
    elif ext == ".txt":
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
            
    return text

def parse_timestamp_str(timestamp_str: str) -> int:
    """Convert 'MM:SS' or 'HH:MM:SS' string into total seconds."""
    parts = timestamp_str.split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except ValueError:
        pass
    return 0

def parse_transcript_chunks(transcript_text: str, filename: str, branch_name: str, media_path: str):
    """
    Parse timestamped transcript text into structured chunk objects.
    Looks for lines starting with [MM:SS].
    """
    pattern = re.compile(r"^\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(.*)$")
    lines = transcript_text.splitlines()
    
    chunks = []
    current_time_str = "00:00"
    current_seconds = 0
    current_text_buf = []

    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue
            
        match = pattern.match(line_str)
        if match:
            # If we have buffered text from previous block, save chunk
            if current_text_buf:
                buf_text = " ".join(current_text_buf).strip()
                if buf_text:
                    chunks.append({
                        "text": f"[{current_time_str}] {buf_text}",
                        "timestamp": current_time_str,
                        "timestamp_seconds": current_seconds,
                        "branch": branch_name,
                        "source_file": filename,
                        "media_path": media_path,
                        "type": "media"
                    })
                current_text_buf = []

            current_time_str = match.group(1)
            current_seconds = parse_timestamp_str(current_time_str)
            text_part = match.group(2)
            if text_part:
                current_text_buf.append(text_part)
        else:
            current_text_buf.append(line_str)

    # Add last remaining chunk
    if current_text_buf:
        buf_text = " ".join(current_text_buf).strip()
        if buf_text:
            chunks.append({
                "text": f"[{current_time_str}] {buf_text}",
                "timestamp": current_time_str,
                "timestamp_seconds": current_seconds,
                "branch": branch_name,
                "source_file": filename,
                "media_path": media_path,
                "type": "media"
            })

    # If no timestamps matched pattern, fallback to paragraph chunking
    if not chunks and transcript_text.strip():
        paragraphs = [p.strip() for p in transcript_text.split("\n\n") if p.strip()]
        for idx, p in enumerate(paragraphs):
            chunks.append({
                "text": p,
                "timestamp": "00:00",
                "timestamp_seconds": 0,
                "branch": branch_name,
                "source_file": filename,
                "media_path": media_path,
                "type": "media"
            })

    return chunks

def chunk_document_text(doc_text: str, filename: str, branch_name: str):
    """Chunk raw document text by paragraphs with overlap if needed."""
    paragraphs = [p.strip() for p in doc_text.split("\n\n") if p.strip()]
    chunks = []
    
    buf = ""
    for p in paragraphs:
        if len(buf) + len(p) < 800:
            buf = f"{buf}\n\n{p}".strip()
        else:
            if buf:
                chunks.append({
                    "text": buf,
                    "timestamp": "N/A",
                    "timestamp_seconds": 0,
                    "branch": branch_name,
                    "source_file": filename,
                    "media_path": "",
                    "type": "document"
                })
            buf = p

    if buf:
        chunks.append({
            "text": buf,
            "timestamp": "N/A",
            "timestamp_seconds": 0,
            "branch": branch_name,
            "source_file": filename,
            "media_path": "",
            "type": "document"
        })

    return chunks

def process_and_ingest_files(client, branch_name: str, file_objects: list, status_callback=None):
    """
    Main Ingestion Entry Point:
    1. Sort media files chronologically.
    2. Save files locally to ./data/uploads/<branch>/.
    3. For Media (.mp4, .mkv, .mp3): Gemini STT -> save transcript -> per-file summary -> chunk -> ChromaDB.
    4. For Docs (.pdf, .docx, .txt): Extract text -> per-file summary -> chunk -> ChromaDB.
    5. Update branch state JSON and Master Branch Summary.
    """
    # Categorize files
    media_files = []
    doc_files = []
    
    media_extensions = {".mp4", ".mkv", ".mp3"}
    doc_extensions = {".pdf", ".docx", ".txt"}

    for f in file_objects:
        ext = os.path.splitext(f.name)[1].lower()
        if ext in media_extensions:
            media_files.append(f)
        elif ext in doc_extensions:
            doc_files.append(f)

    # Sort media files chronologically by filename
    media_files.sort(key=lambda x: x.name)

    all_files_ordered = media_files + doc_files
    upload_dir = get_branch_upload_dir(branch_name)
    embedder = get_embedder()
    collection = get_chroma_collection()
    state = load_branch_state(branch_name)

    total_files = len(all_files_ordered)
    
    for idx, f_obj in enumerate(all_files_ordered):
        filename = f_obj.name
        ext = os.path.splitext(filename)[1].lower()
        save_path = os.path.join(upload_dir, filename)

        if status_callback:
            status_callback(f"Processing ({idx+1}/{total_files}): {filename}...")

        # Save uploaded file bytes to local storage
        with open(save_path, "wb") as out_f:
            out_f.write(f_obj.getbuffer())

        file_text = ""
        chunks = []
        is_media = ext in media_extensions

        if is_media:
            # Gemini STT pipeline
            if status_callback:
                status_callback(f"Transcribing media via Gemini API: {filename}...")
            file_text, _ = transcribe_media_gemini(client, save_path, branch_name, filename)
            chunks = parse_transcript_chunks(file_text, filename, branch_name, save_path)
        else:
            # Document text extraction pipeline
            if status_callback:
                status_callback(f"Extracting document text: {filename}...")
            file_text = extract_document_text(save_path, ext)
            chunks = chunk_document_text(file_text, filename, branch_name)

        # Generate per-file summary
        if status_callback:
            status_callback(f"Generating summary for: {filename}...")
        file_summary = generate_file_summary(client, file_text, filename, "Media" if is_media else "Document")

        # Save to state dict
        state["files"][filename] = {
            "summary": file_summary,
            "type": "media" if is_media else "document",
            "path": save_path
        }
        save_branch_state(branch_name, state)

        # Vector Indexing in ChromaDB
        if chunks:
            if status_callback:
                status_callback(f"Indexing {len(chunks)} chunks into ChromaDB: {filename}...")
                
            documents = [c["text"] for c in chunks]
            embeddings = embedder.encode(documents).tolist()
            
            ids = [f"{branch_name}_{filename}_{i}" for i in range(len(chunks))]
            metadatas = [
                {
                    "branch": c["branch"],
                    "source_file": c["source_file"],
                    "timestamp": c["timestamp"],
                    "timestamp_seconds": c["timestamp_seconds"],
                    "media_path": c["media_path"],
                    "type": c["type"]
                }
                for c in chunks
            ]

            collection.add(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas
            )

    # Synthesize Master Branch Summary
    if status_callback:
        status_callback("Synthesizing Master Branch Summary...")
    update_master_branch_summary(client, branch_name)

    if status_callback:
        status_callback(f"Successfully processed all {total_files} file(s)!")
