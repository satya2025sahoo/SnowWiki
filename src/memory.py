"""
src/memory.py
=============
MemoryManager — hybrid LLM memory for SnowWiki.

Combines:
  - Persistent JSON storage per branch (./data/chat_history/<branch>.json)
  - 6-turn sliding context window (last 3 user-assistant exchanges)
  - Periodic memory compaction every 10 messages via llama-3.1-8b-instant
"""

from __future__ import annotations

import json
import os

import groq

from src.config import CHAT_HISTORY_DIR, GROQ_API_KEY, GROQ_CLASSIFIER_MODEL


class MemoryManager:
    """
    Production-grade hybrid LLM memory manager.

    Public API
    ----------
    load_memory(branch)         → dict
    save_memory(branch, data)
    add_message(branch, msg)
    get_condensed_context(branch) → dict
    check_and_summarize_history(branch) → bool
    clear_active_session(branch)  → clears in-memory turn list only
    """

    def __init__(self, history_dir: str = CHAT_HISTORY_DIR) -> None:
        self.history_dir = history_dir
        os.makedirs(self.history_dir, exist_ok=True)

    # ── File path helpers ──────────────────────────────────────────────────────

    def _safe_name(self, branch_name: str) -> str:
        """Sanitise branch name so it is safe as a file-system path component."""
        return "".join(c if c.isalnum() or c in (" ", "_", "-") else "_" for c in branch_name)

    def get_history_filepath(self, branch_name: str) -> str:
        return os.path.join(self.history_dir, f"{self._safe_name(branch_name)}.json")

    # ── Persistence ────────────────────────────────────────────────────────────

    def load_memory(self, branch_name: str) -> dict:
        """Load persistent chat memory for a branch, or return a blank state."""
        filepath = self.get_history_filepath(branch_name)
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "messages" in data:
                        return data
            except Exception as exc:
                print(f"[memory] Load error for '{branch_name}': {exc}")

        return {
            "branch_name":           branch_name,
            "running_summary":       "",
            "last_summarized_index": 0,
            "messages":              [],
        }

    def save_memory(self, branch_name: str, memory_data: dict) -> None:
        """Persist memory data dict to the branch JSON file."""
        filepath = self.get_history_filepath(branch_name)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(memory_data, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            print(f"[memory] Save error for '{branch_name}': {exc}")

    def add_message(self, branch_name: str, message: dict) -> None:
        """Append a user or assistant message to persistent branch memory."""
        memory_data = self.load_memory(branch_name)
        memory_data["messages"].append(message)
        self.save_memory(branch_name, memory_data)

    # ── Context Window ─────────────────────────────────────────────────────────

    def get_condensed_context(self, branch_name: str) -> dict:
        """
        Return running_summary + last 6 messages (3 exchange pairs) as a
        compact context dict for injection into LLM prompts.
        """
        memory_data     = self.load_memory(branch_name)
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

    def check_and_summarize_history(self, branch_name: str) -> bool:
        """
        Compact older conversation turns into a Running Memory Summary every
        10 newly accumulated messages.  Uses llama-3.1-8b-instant (fast/cheap).

        Returns True if compaction was performed.
        """
        memory_data = self.load_memory(branch_name)
        messages    = memory_data.get("messages", [])
        last_idx    = memory_data.get("last_summarized_index", 0)

        unsummarized_count = len(messages) - last_idx
        if unsummarized_count < 10:
            return False

        # Leave the most recent 6 turns in the sliding window
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
            client   = groq.Groq(api_key=GROQ_API_KEY)
            response = client.chat.completions.create(
                model=GROQ_CLASSIFIER_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=256,
                temperature=0.3,
            )
            new_summary = response.choices[0].message.content.strip()

            memory_data["running_summary"]       = new_summary
            memory_data["last_summarized_index"] = cutoff
            self.save_memory(branch_name, memory_data)
            return True

        except Exception as exc:
            print(f"[memory] Compaction error for '{branch_name}': {exc}")
            return False

    # ── New Chat helper ────────────────────────────────────────────────────────

    def get_all_messages(self, branch_name: str) -> list[dict]:
        """Return full persistent message list for a branch."""
        return self.load_memory(branch_name).get("messages", [])
