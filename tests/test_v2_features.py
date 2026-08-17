"""
tests/test_v2_features.py
=========================
Unit tests for SnowWiki v2 enhancements:
1. Session-scoped MemoryManager and legacy file migration
2. Dynamic topic extraction in servicenow_domain
3. Conversational routing and Polish LLM in retriever
"""

import os
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch

from src.memory import MemoryManager
from src.servicenow_domain import get_ingested_topics, SERVICENOW_MODULES
from src.retriever import _handle_conversational, _polish_answer


class TestSnowWikiV2(unittest.TestCase):

    def test_session_creation_and_message_addition(self):
        temp_dir = tempfile.mkdtemp()
        try:
            mem = MemoryManager(sessions_dir=temp_dir)
            branch = "Test Branch"
            
            # Create session
            sess_id = mem.create_session(branch, title="Initial Title")
            self.assertTrue(sess_id.startswith("sess_"))
            
            sessions = mem.list_sessions(branch)
            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0]["id"], sess_id)
            
            # Add user message -> auto updates title
            mem.add_message(branch, sess_id, {"role": "user", "content": "How do I configure CSM Case Management in ServiceNow?"})
            
            # Check title update in session and index
            session_data = mem.load_session(branch, sess_id)
            self.assertEqual(len(session_data["messages"]), 1)
            self.assertIn("CSM Case Management", session_data["title"])
            
            updated_sessions = mem.list_sessions(branch)
            self.assertIn("CSM Case Management", updated_sessions[0]["title"])
            
            # Context window
            context = mem.get_condensed_context(branch, sess_id)
            self.assertIn("CSM Case Management", context["recent_turns_text"])
            
        finally:
            shutil.rmtree(temp_dir)

    def test_legacy_migration(self):
        temp_dir = tempfile.mkdtemp()
        try:
            branch = "Legacy Branch"
            safe_branch = "Legacy Branch"
            legacy_file = os.path.join(temp_dir, f"{safe_branch}.json")
            
            # Write old format flat file
            old_data = {
                "branch_name": branch,
                "running_summary": "Legacy summary notes",
                "last_summarized_index": 2,
                "messages": [
                    {"role": "user", "content": "Hello legacy"},
                    {"role": "assistant", "content": "Hi there"}
                ]
            }
            with open(legacy_file, "w", encoding="utf-8") as f:
                json.dump(old_data, f)
                
            # Init MemoryManager and trigger migration
            mem = MemoryManager(sessions_dir=temp_dir)
            sessions = mem.list_sessions(branch)
            
            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0]["title"], "Migrated Legacy Chat")
            
            loaded = mem.load_session(branch, sessions[0]["id"])
            self.assertEqual(len(loaded["messages"]), 2)
            self.assertEqual(loaded["running_summary"], "Legacy summary notes")
            
            # Verify old file was renamed
            self.assertFalse(os.path.exists(legacy_file))
            archived_file = os.path.join(temp_dir, f"{safe_branch}_legacy.json")
            self.assertTrue(os.path.exists(archived_file))
        finally:
            shutil.rmtree(temp_dir)

    def test_get_ingested_topics(self):
        # Empty files
        state_empty = {"files": {}}
        self.assertEqual(get_ingested_topics(state_empty), ["ServiceNow topics from your uploaded sessions"])
        
        # Matching files
        state_with_files = {
            "files": {
                "csm_guide.pdf": {"summary": "This document covers ServiceNow CSM (Customer Service Management) setup and cases."},
                "itom_overview.docx": {"summary": "Explains ITOM discovery and service mapping workflows."}
            }
        }
        topics = get_ingested_topics(state_with_files)
        self.assertIn("CSM", topics)
        self.assertIn("ITOM", topics)

    def test_conversational_handler_no_history(self):
        res = _handle_conversational("What was my previous question?", "CSM Training", None)
        self.assertEqual(res["intent"], "CONVERSATIONAL")
        self.assertFalse(res["found"])
        self.assertIn("We don't have any conversation history", res["answer"])

    def test_conversational_handler_with_history(self):
        class FakeMessage:
            content = "Your previous question was about CSM."
        class FakeChoice:
            message = FakeMessage()
        class FakeResponse:
            choices = [FakeChoice()]
        class FakeCompletions:
            def create(self, **kwargs):
                return FakeResponse()
        class FakeClient:
            chat = type("Chat", (), {"completions": FakeCompletions()})()
            completions = FakeCompletions()

        with patch("src.retriever._groq", return_value=FakeClient()):
            memory_ctx = {
                "recent_turns_text": "User: What is CSM?\nAssistant: Customer Service Management.",
                "running_summary": ""
            }
            res = _handle_conversational("What was my previous question?", "CSM Training", memory_ctx)
            self.assertEqual(res["intent"], "CONVERSATIONAL")
            self.assertTrue(res["found"])
            self.assertIn("Your previous question", res["answer"])

    def test_polish_answer_sentinel_passthrough(self):
        res = _polish_answer("test", "INSUFFICIENT_CONTEXT", None)
        self.assertEqual(res, "__NO_ANSWER__")

        res2 = _polish_answer("test", "NOT_FOUND in search results", None)
        self.assertEqual(res2, "__NO_ANSWER__")


if __name__ == "__main__":
    unittest.main()
