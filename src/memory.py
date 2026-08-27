"""
src/memory.py
=============
MemoryManager — session-aware hybrid LLM memory for SnowWiki v2.

Combines:
  - Persistent JSON storage per branch/session
  - Automatic migration from legacy flat files
  - 6-turn sliding context window (last 3 user-assistant exchanges)
  - Periodic memory compaction every 10 messages via llama-3.1-8b-instant
"""

from __future__ import annotations

import json
import os
import uuid
import datetime

from src.config import SESSIONS_DIR
from src.llm_wrapper import get_chat_client

class MemoryManager:
    """
    Production-grade hybrid LLM memory manager (Session-scoped).

    Public API
    ----------
    create_session(branch_name, title) -> session_id
    list_sessions(branch_name) -> list[dict]
    load_session(branch_name, session_id) -> dict
    save_session(branch_name, session_id, data)
    add_message(branch_name, session_id, msg)
    get_condensed_context(branch_name, session_id) -> dict
    check_and_summarize_history(branch_name, session_id) -> bool
    """

    def __init__(self, sessions_dir: str = SESSIONS_DIR) -> None:
        self.sessions_dir = sessions_dir
        os.makedirs(self.sessions_dir, exist_ok=True)

    # ── File path helpers ──────────────────────────────────────────────────────

    def _safe_name(self, branch_name: str) -> str:
        """Sanitise branch name so it is safe as a file-system path component."""
        return "".join(c if c.isalnum() or c in (" ", "_", "-") else "_" for c in branch_name)

    def get_branch_dir(self, branch_name: str) -> str:
        branch_dir = os.path.join(self.sessions_dir, self._safe_name(branch_name))
        os.makedirs(branch_dir, exist_ok=True)
        return branch_dir

    def get_index_filepath(self, branch_name: str) -> str:
        return os.path.join(self.get_branch_dir(branch_name), "index.json")

    def get_session_filepath(self, branch_name: str, session_id: str) -> str:
        return os.path.join(self.get_branch_dir(branch_name), f"{session_id}.json")

    # ── Migration ──────────────────────────────────────────────────────────────

    def _migrate_legacy_if_needed(self, branch_name: str) -> None:
        """Auto-migrate old flat data/chat_history/<branch>.json into session format."""
        legacy_file = os.path.join(self.sessions_dir, f"{self._safe_name(branch_name)}.json")
        if not os.path.exists(legacy_file):
            return

        print(f"[memory] Found legacy memory file for branch '{branch_name}'. Migrating...")
        try:
            with open(legacy_file, "r", encoding="utf-8") as f:
                legacy_data = json.load(f)

            if isinstance(legacy_data, dict) and "messages" in legacy_data:
                # Create a default session to hold this data
                session_id = f"sess_legacy_{uuid.uuid4().hex[:8]}"
                
                new_session_data = {
                    "id": session_id,
                    "branch_name": branch_name,
                    "title": "Migrated Legacy Chat",
                    "running_summary": legacy_data.get("running_summary", ""),
                    "last_summarized_index": legacy_data.get("last_summarized_index", 0),
                    "messages": legacy_data.get("messages", []),
                    "created_at": datetime.datetime.now().isoformat()
                }

                # Save session file
                self.save_session(branch_name, session_id, new_session_data)
                
                # Update index
                index_data = self.list_sessions(branch_name, migrate=False)
                index_data.append({
                    "id": session_id,
                    "title": new_session_data["title"],
                    "created_at": new_session_data["created_at"],
                    "preview": "Legacy history migrated"
                })
                with open(self.get_index_filepath(branch_name), "w", encoding="utf-8") as f:
                    json.dump(index_data, f, indent=2)

            # Rename legacy file to avoid migrating again
            archived_file = os.path.join(self.sessions_dir, f"{self._safe_name(branch_name)}_legacy.json")
            os.rename(legacy_file, archived_file)
            print(f"[memory] Migration complete. Legacy file archived to {archived_file}")

        except Exception as exc:
            print(f"[memory] Migration error for '{branch_name}': {exc}")

    # ── Sessions API ───────────────────────────────────────────────────────────

    def create_session(self, branch_name: str, title: str = "New Chat") -> str:
        self._migrate_legacy_if_needed(branch_name)
        session_id = f"sess_{datetime.datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}"
        created_at = datetime.datetime.now().isoformat()

        session_data = {
            "id": session_id,
            "branch_name": branch_name,
            "title": title,
            "running_summary": "",
            "last_summarized_index": 0,
            "messages": [],
            "created_at": created_at
        }
        self.save_session(branch_name, session_id, session_data)

        # Update index
        index_data = self.list_sessions(branch_name)
        index_data.append({
            "id": session_id,
            "title": title,
            "created_at": created_at,
            "preview": "New conversation started"
        })
        with open(self.get_index_filepath(branch_name), "w", encoding="utf-8") as f:
            json.dump(index_data, f, indent=2)

        return session_id

    def list_sessions(self, branch_name: str, migrate: bool = True) -> list[dict]:
        if migrate:
            self._migrate_legacy_if_needed(branch_name)
        index_path = self.get_index_filepath(branch_name)
        if os.path.exists(index_path):
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as exc:
                print(f"[memory] Load index error for '{branch_name}': {exc}")
        return []

    def load_session(self, branch_name: str, session_id: str) -> dict:
        self._migrate_legacy_if_needed(branch_name)
        filepath = self.get_session_filepath(branch_name, session_id)
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "messages" in data:
                        return data
            except Exception as exc:
                print(f"[memory] Load session error for '{session_id}': {exc}")

        return {
            "id": session_id,
            "branch_name": branch_name,
            "title": "New Chat",
            "running_summary": "",
            "last_summarized_index": 0,
            "messages": [],
            "created_at": datetime.datetime.now().isoformat()
        }

    def save_session(self, branch_name: str, session_id: str, memory_data: dict) -> None:
        filepath = self.get_session_filepath(branch_name, session_id)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(memory_data, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            print(f"[memory] Save session error for '{session_id}': {exc}")

    def add_message(self, branch_name: str, session_id: str, message: dict) -> None:
        memory_data = self.load_session(branch_name, session_id)
        
        # If it's the first user message, update title and preview
        if not memory_data["messages"] and message.get("role") == "user":
            content = message.get("content", "").strip()
            new_title = content[:50] + ("..." if len(content) > 50 else "")
            memory_data["title"] = new_title
            
            # Update index
            index_data = self.list_sessions(branch_name)
            for s in index_data:
                if s["id"] == session_id:
                    s["title"] = new_title
                    s["preview"] = content[:100]
                    break
            with open(self.get_index_filepath(branch_name), "w", encoding="utf-8") as f:
                json.dump(index_data, f, indent=2)

        memory_data["messages"].append(message)
        self.save_session(branch_name, session_id, memory_data)

    # ── Context Window ─────────────────────────────────────────────────────────

    def get_condensed_context(self, branch_name: str, session_id: str) -> dict:
        memory_data     = self.load_session(branch_name, session_id)
        running_summary = memory_data.get("running_summary", "")
        all_messages    = memory_data.get("messages", [])

        recent_messages = all_messages[-6:] if len(all_messages) > 6 else all_messages

        formatted: list[str] = []
        for msg in recent_messages:
            role    = "User" if msg.get("role") == "user" else "Assistant"
            content = msg.get("content", "").strip()
            formatted.append(f"{role}: {content}")

        return {
            "running_summary":   running_summary,
            "recent_messages":   recent_messages,
            "recent_turns_text": "\n".join(formatted),
        }

    # ── Memory Compaction ──────────────────────────────────────────────────────

    def check_and_summarize_history(self, branch_name: str, session_id: str) -> bool:
        memory_data = self.load_session(branch_name, session_id)
        messages    = memory_data.get("messages", [])
        last_idx    = memory_data.get("last_summarized_index", 0)

        unsummarized_count = len(messages) - last_idx
        if unsummarized_count < 10:
            return False

        cutoff = len(messages) - 6
        if cutoff <= last_idx:
            return False

        turns_to_condense = messages[last_idx:cutoff]
        if not turns_to_condense:
            return False

        condense_lines: list[str] = []
        for msg in turns_to_condense:
            role    = "User" if msg.get("role") == "user" else "Assistant"
            content = msg.get("content", "").strip()
            condense_lines.append(f"{role}: {content}")

        turns_block      = "\n".join(condense_lines)
        existing_summary = memory_data.get("running_summary", "")

        prompt = (
            "You are a conversation memory compactor for a ServiceNow AI assistant.\n"
            "Condense the conversation turns below into EXACTLY 3 concise bullet points "
            "covering core technical facts, questions asked, and ServiceNow topics discussed.\n"
            "If an existing summary is provided, merge it into your output.\n\n"
            f"EXISTING SUMMARY:\n{existing_summary or 'None'}\n\n"
            f"CONVERSATION TURNS TO CONDENSE:\n{turns_block}"
        )

        try:
            from src.config import GROQ_CLASSIFIER_MODEL
            client   = get_chat_client()
            response = client.chat.completions.create(
                model=GROQ_CLASSIFIER_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=256,
                temperature=0.3,
            )
            new_summary = response.choices[0].message.content.strip()

            memory_data["running_summary"]       = new_summary
            memory_data["last_summarized_index"] = cutoff
            self.save_session(branch_name, session_id, memory_data)
            return True

        except Exception as exc:
            print(f"[memory] Compaction error for '{session_id}': {exc}")
            return False

    def get_all_messages(self, branch_name: str, session_id: str) -> list[dict]:
        return self.load_session(branch_name, session_id).get("messages", [])
