import os
import json
import time
from src.config import TRANSCRIPTS_DIR, PROJECT_STATES_DIR, LLM_MODEL_NAME

def get_branch_transcript_dir(branch_name: str) -> str:
    """Ensure directory exists for branch transcripts."""
    branch_dir = os.path.join(TRANSCRIPTS_DIR, branch_name)
    os.makedirs(branch_dir, exist_ok=True)
    return branch_dir

def get_branch_state_filepath(branch_name: str) -> str:
    """Get absolute path to branch project state JSON file."""
    return os.path.join(PROJECT_STATES_DIR, f"{branch_name}.json")

def load_branch_state(branch_name: str) -> dict:
    """Load existing branch state JSON or initialize new one."""
    state_path = get_branch_state_filepath(branch_name)
    if os.path.exists(state_path):
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "branch_name": branch_name,
        "master_summary": "",
        "files": {}
    }

def save_branch_state(branch_name: str, state: dict):
    """Save branch state dictionary to JSON file."""
    state_path = get_branch_state_filepath(branch_name)
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def transcribe_media_gemini(client, media_path: str, branch_name: str, filename: str) -> str:
    """
    Upload media to Gemini Files API, generate timestamped speech-to-text,
    save text transcript locally to ./data/transcripts/<branch>/<filename>.txt,
    and delete uploaded file from Gemini storage.
    """
    file_ref = None
    try:
        # 1. Upload to Gemini Files API
        file_ref = client.files.upload(file=media_path)
        
        # Wait for file processing if needed
        while hasattr(file_ref, "state") and file_ref.state.name == "PROCESSING":
            time.sleep(2)
            file_ref = client.files.get(name=file_ref.name)
            
        if hasattr(file_ref, "state") and file_ref.state.name == "FAILED":
            raise RuntimeError(f"Gemini API file processing failed for {filename}")

        # 2. Prompt Gemini for timestamped transcript
        prompt = (
            "You are an expert audio/video speech-to-text transcription engine for technical ServiceNow sessions.\n"
            "Transcribe the spoken content verbatim with accurate timestamps.\n"
            "Format EVERY line as: [MM:SS] Text content spoken here.\n"
            "Do not skip sections. Do not include conversation preamble or markdown quotes.\n"
            "Example format:\n"
            "[00:00] Welcome to the session.\n"
            "[00:15] Today we discuss ITOM pattern configuration."
        )

        response = client.models.generate_content(
            model=LLM_MODEL_NAME,
            contents=[file_ref, prompt]
        )
        
        transcript_text = response.text or ""
        
        # 3. Save transcript text locally
        branch_dir = get_branch_transcript_dir(branch_name)
        out_txt_name = f"{os.path.splitext(filename)[0]}.txt"
        out_path = os.path.join(branch_dir, out_txt_name)
        
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(transcript_text)

        return transcript_text, out_path

    finally:
        # 4. Clean up uploaded file from Gemini storage
        if file_ref and hasattr(file_ref, "name"):
            try:
                client.files.delete(name=file_ref.name)
            except Exception as e:
                print(f"Warning: Failed to delete Gemini file {file_ref.name}: {e}")

def generate_file_summary(client, text_content: str, filename: str, file_type: str) -> str:
    """Generate a concise executive summary for an uploaded document or transcript."""
    if not text_content or not text_content.strip():
        return "No text content available for summary."
        
    prompt = (
        f"Generate a concise executive summary (3-5 key bullet points) of the following technical content from "
        f"file '{filename}' (Type: {file_type}). Emphasize ServiceNow concepts, steps, and key technical takeaways.\n\n"
        f"CONTENT:\n{text_content[:8000]}"
    )
    
    try:
        response = client.models.generate_content(
            model=LLM_MODEL_NAME,
            contents=prompt
        )
        return response.text.strip() if response.text else "Summary unavailable."
    except Exception as e:
        return f"Summary generation error: {str(e)}"

def update_master_branch_summary(client, branch_name: str) -> str:
    """Synthesize all per-file summaries into an overarching Master Branch Summary."""
    state = load_branch_state(branch_name)
    files_dict = state.get("files", {})
    
    if not files_dict:
        state["master_summary"] = "No files uploaded in this session yet."
        save_branch_state(branch_name, state)
        return state["master_summary"]
        
    combined_summaries = []
    for fname, info in files_dict.items():
        summary = info.get("summary", "No summary")
        combined_summaries.append(f"### File: {fname} ({info.get('type', 'file')})\n{summary}")
        
    all_summaries_text = "\n\n".join(combined_summaries)
    
    prompt = (
        f"You are a technical knowledge manager. Below are individual summaries of files in the ServiceNow training branch '{branch_name}'.\n"
        f"Synthesize them into a high-level Master Branch Summary outlining the primary objectives, key architecture topics, and covered workflows.\n\n"
        f"{all_summaries_text}"
    )
    
    try:
        response = client.models.generate_content(
            model=LLM_MODEL_NAME,
            contents=prompt
        )
        master_summary = response.text.strip() if response.text else "Master summary generated."
    except Exception as e:
        master_summary = f"Master summary synthesis error: {str(e)}"
        
    state["master_summary"] = master_summary
    save_branch_state(branch_name, state)
    return master_summary
