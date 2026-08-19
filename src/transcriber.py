"""
src/transcriber.py
==================
Speech-to-text processing and document summarization.

Audio transcription uses Groq's Whisper endpoint (GROQ_WHISPER_MODEL).
  - .mp3 files → sent directly to Groq Whisper.
  - .mp4 files → audio track extracted to a temp .mp3 via ffmpeg, then
                  the .mp3 is sent to Groq Whisper (smaller, faster upload).

All text summarization uses Groq chat completions.
"""

from __future__ import annotations

import os
import json
import subprocess
import tempfile

import groq

from src.config import (
    TRANSCRIPTS_DIR,
    PROJECT_STATES_DIR,
    GROQ_API_KEY,
    GROQ_CLASSIFIER_MODEL,
    GROQ_RESPONSE_MODEL,
    GROQ_WHISPER_MODEL,
)

from src.api_utils import with_retry


# ── Internal Groq client helper ────────────────────────────────────────────────

def _get_groq_client() -> groq.Groq:
    """Return a configured Groq client using the env-loaded API key."""
    return groq.Groq(api_key=GROQ_API_KEY)


# ── Branch State Helpers ───────────────────────────────────────────────────────

def get_branch_transcript_dir(branch_name: str) -> str:
    """Ensure per-branch transcript directory exists and return its path."""
    branch_dir = os.path.join(TRANSCRIPTS_DIR, branch_name)
    os.makedirs(branch_dir, exist_ok=True)
    return branch_dir


def get_branch_state_filepath(branch_name: str) -> str:
    """Absolute path to a branch's project-state JSON file."""
    return os.path.join(PROJECT_STATES_DIR, f"{branch_name}.json")


def load_branch_state(branch_name: str) -> dict:
    """Load existing branch state JSON or initialise a blank one."""
    state_path = get_branch_state_filepath(branch_name)
    if os.path.exists(state_path):
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"branch_name": branch_name, "master_summary": "", "files": {}}


def save_branch_state(branch_name: str, state: dict) -> None:
    """Persist branch state dictionary to its JSON file."""
    state_path = get_branch_state_filepath(branch_name)
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


# ── MP4 → MP3 Conversion Helper ─────────────────────────────────────────────────

def _convert_mp4_to_mp3(video_path: str) -> str | None:
    """
    Extract a mono 16 kHz MP3 from an .mp4 file using ffmpeg.
    Returns the path to the temporary .mp3 file, or None if ffmpeg
    is unavailable or extraction fails.
    The caller is responsible for deleting the temp file.
    """
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None  # ffmpeg not on PATH

    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp.close()

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-ar", "16000",   # 16 kHz — optimal for Whisper
        "-ac", "1",       # mono
        "-b:a", "64k",    # 64 kbps keeps file small
        tmp.name,
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        os.unlink(tmp.name)
        return None
    return tmp.name


@with_retry(max_retries=5)
def transcribe_media_groq(
    media_path: str,
    branch_name: str,
    filename: str,
) -> tuple[str, str]:
    """
    Transcribe an audio/video file using Groq Whisper (GROQ_WHISPER_MODEL).

    Supported formats:
      .mp3 — sent directly to Groq Whisper.
      .mp4 — audio track extracted to a temp .mp3 via ffmpeg first,
               then the .mp3 is sent to Groq Whisper (smaller, faster upload).

    Transcript cache: if a valid .txt transcript already exists in
    data/transcripts/<branch>/, it is returned immediately — no API call made.

    Returns:
        (transcript_text, saved_transcript_path)
    """
    # ── Transcript cache check ─────────────────────────────────────────────────
    cached_path = os.path.join(
        get_branch_transcript_dir(branch_name),
        f"{os.path.splitext(filename)[0]}.txt",
    )
    if os.path.exists(cached_path):
        try:
            with open(cached_path, "r", encoding="utf-8") as f:
                cached_text = f.read()
            if cached_text.strip() and not cached_text.startswith("[Audio extraction skipped"):
                print(f"[transcriber] Cache hit — skipping Whisper for '{filename}'")
                return cached_text, cached_path
        except Exception as exc:
            print(f"[transcriber] Cache read failed for '{filename}': {exc} — re-transcribing.")

    # ── No cache — call Groq Whisper ───────────────────────────────────────────
    client = _get_groq_client()
    ext = os.path.splitext(media_path)[1].lower()

    # For .mp4 files, extract audio track first to reduce file size
    audio_path  = media_path
    temp_audio  = None
    if ext == ".mp4":
        converted = _convert_mp4_to_mp3(media_path)
        if converted:
            print(f"[transcriber] MP4 → MP3 conversion complete for '{filename}'")
            audio_path = converted
            temp_audio = converted
        else:
            transcript_text = (
                f"[MP4 audio extraction failed for '{filename}'. "
                f"ffmpeg may not be on PATH. Install ffmpeg or convert to .mp3 manually.]"
            )
            _save_transcript(transcript_text, branch_name, filename)
            return transcript_text, ""

    try:
        # Groq Whisper has a 25 MB limit — check size after conversion
        file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        if file_size_mb > 24.5:
            transcript_text = (
                f"[File '{filename}' exceeds the 25 MB Whisper limit ({file_size_mb:.1f} MB). "
                f"Please split into smaller segments and re-upload.]"
            )
            _save_transcript(transcript_text, branch_name, filename)
            return transcript_text, ""

        with open(audio_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model=GROQ_WHISPER_MODEL,
                file=audio_file,
                response_format="verbose_json",  # includes segment timestamps
            )

        # Build timestamped transcript from Whisper segments
        lines: list[str] = []
        if hasattr(transcription, "segments") and transcription.segments:
            for seg in transcription.segments:
                start_sec = int(seg.get("start", 0)) if isinstance(seg, dict) else int(getattr(seg, "start", 0))
                minutes, seconds = divmod(start_sec, 60)
                ts = f"{minutes:02d}:{seconds:02d}"
                text = seg.get("text", "").strip() if isinstance(seg, dict) else getattr(seg, "text", "").strip()
                if text:
                    lines.append(f"[{ts}] {text}")
        else:
            # Fallback: plain text without timestamps
            plain = getattr(transcription, "text", "") or ""
            lines = [plain]

        transcript_text = "\n".join(lines)

    finally:
        # Always clean up the temp MP3 extracted from the video
        if temp_audio and os.path.exists(temp_audio):
            try:
                os.unlink(temp_audio)
            except OSError:
                pass

    saved_path = _save_transcript(transcript_text, branch_name, filename)
    return transcript_text, saved_path


def _save_transcript(text: str, branch_name: str, filename: str) -> str:
    """Save transcript text to ./data/transcripts/<branch>/<filename>.txt."""
    branch_dir = get_branch_transcript_dir(branch_name)
    out_name   = f"{os.path.splitext(filename)[0]}.txt"
    out_path   = os.path.join(branch_dir, out_name)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    return out_path


# ── Summarization ──────────────────────────────────────────────────────────────

@with_retry(max_retries=5)
def generate_file_summary(text_content: str, filename: str, file_type: str) -> str:
    """
    Generate a concise bullet-point executive summary for a document or
    transcript using the fast Groq classifier model.
    """
    if not text_content or not text_content.strip():
        return "No text content available for summary."

    # Truncate to ~6 000 chars to stay within context budget of 8b model
    snippet = text_content[:6000]

    prompt = (
        f"Generate a concise executive summary (3–5 key bullet points) of the following "
        f"technical content from file '{filename}' (Type: {file_type}).\n"
        f"Emphasise ServiceNow concepts, steps, configuration details, and key technical takeaways.\n\n"
        f"CONTENT:\n{snippet}"
    )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model=GROQ_CLASSIFIER_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        return f"Summary generation error: {exc}"


@with_retry(max_retries=5)
def update_master_branch_summary(branch_name: str) -> str:
    """
    Synthesise all per-file summaries into an overarching Master Branch Summary
    using the 70B response model for higher quality output.
    """
    state      = load_branch_state(branch_name)
    files_dict = state.get("files", {})

    if not files_dict:
        state["master_summary"] = "No files uploaded in this session yet."
        save_branch_state(branch_name, state)
        return state["master_summary"]

    combined: list[str] = []
    for fname, info in files_dict.items():
        summary = info.get("summary", "No summary")
        combined.append(f"### File: {fname} ({info.get('type', 'file')})\n{summary}")

    all_summaries_text = "\n\n".join(combined)

    prompt = (
        f"You are a technical knowledge manager for a ServiceNow training platform.\n"
        f"Below are individual file summaries from the training branch '{branch_name}'.\n"
        f"Synthesise them into a high-level Master Branch Summary covering:\n"
        f"  - Primary learning objectives\n"
        f"  - Key ServiceNow architecture topics\n"
        f"  - Covered workflows and configurations\n\n"
        f"{all_summaries_text}"
    )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model=GROQ_RESPONSE_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.3,
        )
        master_summary = response.choices[0].message.content.strip()
    except Exception as exc:
        master_summary = f"Master summary synthesis error: {exc}"

    state["master_summary"] = master_summary
    save_branch_state(branch_name, state)
    return master_summary
