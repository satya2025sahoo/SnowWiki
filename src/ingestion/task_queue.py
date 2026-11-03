"""
src/ingestion/task_queue.py
===========================
Enterprise asynchronous ingestion task manager for SnowWiki.
Decouples heavy multi-modal file ingestion (VLM, Whisper, Marker, chunking)
from the Streamlit UI thread using a persistent SQLite job queue and a
background worker daemon.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import sqlite3
import threading
import time
import traceback
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from src.config import DATA_DIR
from src.ingestion.core import get_file_dir

logger = logging.getLogger(__name__)

JOBS_DB_PATH = os.path.join(DATA_DIR, "ingestion_jobs.db")

# Thread-safe in-memory queue for task dispatching
_TASK_QUEUE: queue.Queue[str] = queue.Queue()
_WORKER_THREAD: Optional[threading.Thread] = None
_WORKER_LOCK = threading.Lock()


class SavedFileDescriptor:
    """Lightweight duck-typed replacement for Streamlit's UploadedFile.

    Downstream pipeline functions expect an object with `.name` and `.getbuffer()`.
    """

    def __init__(self, name: str, path: str):
        self.name = name
        self.path = path

    def getbuffer(self) -> bytes:
        if os.path.exists(self.path):
            with open(self.path, "rb") as f:
                return f.read()
        return b""


def _get_db_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(JOBS_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(JOBS_DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_jobs_db() -> None:
    """Initialize SQLite database for tracking ingestion tasks."""
    with _get_db_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ingestion_jobs (
                job_id TEXT PRIMARY KEY,
                branch_name TEXT NOT NULL,
                files_json TEXT NOT NULL,
                status TEXT NOT NULL,
                progress_pct INTEGER DEFAULT 0,
                current_file TEXT DEFAULT '',
                stage_message TEXT DEFAULT '',
                error_message TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT DEFAULT ''
            );
            """
        )
        # Handle jobs left in RUNNING state from previous process restarts
        conn.execute(
            """
            UPDATE ingestion_jobs
            SET status = 'FAILED',
                error_message = 'Interrupted by server restart',
                updated_at = datetime('now')
            WHERE status IN ('RUNNING', 'PROCESSING');
            """
        )
        conn.commit()


def _update_job_status(
    job_id: str,
    status: Optional[str] = None,
    progress_pct: Optional[int] = None,
    current_file: Optional[str] = None,
    stage_message: Optional[str] = None,
    error_message: Optional[str] = None,
    completed: bool = False,
) -> None:
    now_iso = datetime.utcnow().isoformat()
    fields = ["updated_at = ?"]
    params: list[Any] = [now_iso]

    if status is not None:
        fields.append("status = ?")
        params.append(status)
    if progress_pct is not None:
        fields.append("progress_pct = ?")
        params.append(int(progress_pct))
    if current_file is not None:
        fields.append("current_file = ?")
        params.append(current_file)
    if stage_message is not None:
        fields.append("stage_message = ?")
        params.append(stage_message)
    if error_message is not None:
        fields.append("error_message = ?")
        params.append(error_message)
    if completed:
        fields.append("completed_at = ?")
        params.append(now_iso)

    params.append(job_id)
    query = f"UPDATE ingestion_jobs SET {', '.join(fields)} WHERE job_id = ?"

    try:
        with _get_db_conn() as conn:
            conn.execute(query, params)
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to update job {job_id} in SQLite: {e}")


def _worker_loop() -> None:
    """Continuous background loop consuming ingestion jobs from the queue."""
    logger.info("Ingestion background worker thread started.")
    from src.ingestion.pipeline import process_and_ingest_files

    while True:
        try:
            job_id = _TASK_QUEUE.get()
            if job_id is None:
                break  # Shutdown sentinel

            job = get_job_status(job_id)
            if not job or job["status"] == "CANCELLED":
                _TASK_QUEUE.task_done()
                continue

            branch_name = job["branch_name"]
            files_meta = json.loads(job["files_json"])
            total_files = len(files_meta)

            _update_job_status(
                job_id,
                status="RUNNING",
                progress_pct=5,
                stage_message=f"Starting ingestion for {total_files} file(s)…",
            )

            file_descriptors = [
                SavedFileDescriptor(item["name"], item["path"])
                for item in files_meta
            ]

            def _progress_callback(msg: str) -> None:
                # Calculate progress heuristics from pipeline messages
                current_file = ""
                progress = 10
                if "(" in msg and "/" in msg and ")" in msg:
                    try:
                        part = msg.split("(")[1].split(")")[0]
                        cur_idx, tot = [int(x) for x in part.split("/")]
                        file_ratio = (cur_idx - 1) / max(tot, 1)
                        progress = int(10 + file_ratio * 80)
                    except Exception:
                        pass
                if ":" in msg:
                    current_file = msg.split(":")[-1].replace("…", "").strip()

                _update_job_status(
                    job_id,
                    current_file=current_file if current_file else None,
                    stage_message=msg,
                    progress_pct=progress,
                )

            logger.info(f"Processing ingestion job {job_id} for branch '{branch_name}'")
            process_and_ingest_files(
                branch_name=branch_name,
                file_objects=file_descriptors,
                status_callback=_progress_callback,
            )

            _update_job_status(
                job_id,
                status="COMPLETED",
                progress_pct=100,
                stage_message="✅ Ingestion & Indexing Complete!",
                completed=True,
            )
            logger.info(f"Ingestion job {job_id} completed successfully.")

        except Exception as exc:
            err_trace = traceback.format_exc()
            logger.error(f"Ingestion job {job_id} failed: {exc}\n{err_trace}")
            _update_job_status(
                job_id,
                status="FAILED",
                stage_message=f"Error: {exc}",
                error_message=err_trace,
                completed=True,
            )
        finally:
            _TASK_QUEUE.task_done()


def _ensure_worker_running() -> None:
    global _WORKER_THREAD
    with _WORKER_LOCK:
        if _WORKER_THREAD is None or not _WORKER_THREAD.is_alive():
            init_jobs_db()
            _WORKER_THREAD = threading.Thread(
                target=_worker_loop,
                name="IngestionBackgroundWorker",
                daemon=True,
            )
            _WORKER_THREAD.start()


def enqueue_ingestion_job(branch_name: str, uploaded_files: list) -> str:
    """Persist uploaded file bytes to disk immediately and enqueue ingestion job.

    This runs in milliseconds and returns a unique `job_id` so the UI never hangs.
    """
    _ensure_worker_running()

    job_id = f"job_{uuid.uuid4().hex[:8]}"
    saved_files = []

    for f in uploaded_files:
        filename = getattr(f, "name", "document")
        file_dir = get_file_dir(branch_name, filename)
        save_path = os.path.join(file_dir, filename)

        # Write uploaded bytes immediately to disk
        buffer = f.getbuffer() if hasattr(f, "getbuffer") else f.read()
        with open(save_path, "wb") as out_f:
            out_f.write(buffer)

        saved_files.append({"name": filename, "path": save_path})

    files_json = json.dumps(saved_files)
    now_iso = datetime.utcnow().isoformat()

    with _get_db_conn() as conn:
        conn.execute(
            """
            INSERT INTO ingestion_jobs (
                job_id, branch_name, files_json, status,
                progress_pct, stage_message, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                job_id,
                branch_name,
                files_json,
                "QUEUED",
                0,
                f"Queued {len(saved_files)} file(s) for background processing",
                now_iso,
                now_iso,
            ),
        )
        conn.commit()

    _TASK_QUEUE.put(job_id)
    logger.info(f"Enqueued ingestion job {job_id} for branch '{branch_name}'")
    return job_id


def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """Fetch status dict for a specific job."""
    with _get_db_conn() as conn:
        cursor = conn.execute(
            "SELECT * FROM ingestion_jobs WHERE job_id = ?",
            (job_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_active_jobs(branch_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return all QUEUED or RUNNING jobs, optionally filtered by branch."""
    query = "SELECT * FROM ingestion_jobs WHERE status IN ('QUEUED', 'RUNNING') "
    params: list[Any] = []
    if branch_name:
        query += "AND branch_name = ? "
        params.append(branch_name)
    query += "ORDER BY created_at ASC"

    with _get_db_conn() as conn:
        cursor = conn.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]


def get_recent_jobs(branch_name: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
    """Return recent jobs for UI status reporting."""
    query = "SELECT * FROM ingestion_jobs "
    params: list[Any] = []
    if branch_name:
        query += "WHERE branch_name = ? "
        params.append(branch_name)
    query += "ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)

    with _get_db_conn() as conn:
        cursor = conn.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]


# Start background worker when module is imported
_ensure_worker_running()
