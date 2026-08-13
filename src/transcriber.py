"""
src/transcriber.py
==================
Speech-to-text processing and document summarization.

Audio transcription uses Groq's Whisper endpoint (whisper-large-v3).
All text summarization uses Groq chat completions via llama-3.1-8b-instant.

Video files (.mp4, .mkv) require ffmpeg on PATH for audio extraction.
If ffmpeg is absent, video files are processed as text-only (no transcript).
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
)


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


# ── Audio Extraction Helper ────────────────────────────────────────────────────

def _extract_audio_from_video(video_path: str) -> str | None:
    """
    Use ffmpeg (must be on PATH) to extract a mono 16 kHz MP3 from a video file.
    Returns path to the temporary audio file, or None if ffmpeg is not available.
    """
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None  # ffmpeg not available

    # Write to a named temp file that the caller owns
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp.close()

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-ar", "16000",
        "-ac", "1",
        "-b:a", "64k",
        tmp.name,
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        os.unlink(tmp.name)
        return None
    return tmp.name


# ── Transcription ──────────────────────────────────────────────────────────────

def transcribe_media_groq(
    media_path: str,
    branch_name: str,
    filename: str,
) -> tuple[str, str]:
    """
    Transcribe an audio (.mp3) or video (.mp4 / .mkv) file using
    Groq Whisper (whisper-large-v3).

    For video files, ffmpeg is used to extract audio first.
    If ffmpeg is absent the transcript will be empty/placeholder.

    Returns:
        (transcript_text, saved_transcript_path)
    """
    client = _get_groq_client()
    ext = os.path.splitext(media_path)[1].lower()

    audio_path = media_path
    temp_audio  = None   # track temp file for cleanup

    try:
        # For video files, extract audio track first
        if ext in {".mp4", ".mkv"}:
            extracted = _extract_audio_from_video(media_path)
            if extracted:
                audio_path = extracted
                temp_audio = extracted
            else:
                # Graceful degradation: no ffmpeg
                transcript_text = (
                    f"[Audio extraction skipped — ffmpeg not found on PATH. "
                    f"Install ffmpeg to enable video transcription for '{filename}'.]"
                )
                _save_transcript(transcript_text, branch_name, filename)
                return transcript_text, ""

        # Groq Whisper has a 25 MB limit — check size
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
                model="whisper-large-v3",
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
        # Clean up extracted audio temp file
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
