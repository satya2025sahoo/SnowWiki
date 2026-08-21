"""
tests/test_llm_logger.py
========================
Unit tests for the structured LLM logger and context transparency functions.
"""

import json
import os
import pytest

from src.config import LOGS_DIR
from src.llm_logger import (
    log_llm_interaction,
    print_terminal_context_transparency,
    HUMAN_LOG_FILE,
    JSONL_LOG_FILE,
)


def test_log_llm_interaction(tmp_path):
    trace_sample = {
        "query": "How do I configure CMDB identification rules?",
        "branch": "main",
        "stage_used": "Path D — Parent-Child RAG",
        "route": "local_rag",
        "classifier": {
            "model": "groq/compound-mini",
            "intent": "SERVICENOW",
            "rag_sub_intent": "detailed_fact",
            "confidence": 0.95,
            "raw_output": '{"intent": "SERVICENOW", "rag_sub_intent": "detailed_fact", "confidence": 0.95}',
        },
        "memory": {
            "running_summary": "Discussed CMDB classes earlier.",
            "recent_turns_text": "User: What is CMDB?\nAssistant: Configuration Management Database.",
        },
        "rag": {
            "mode": "Parent-Child RAG (Path D)",
            "similarity": 0.88,
            "child_chunks": [
                {
                    "similarity_score": 0.88,
                    "source": "cmdb_guide.md",
                    "page_or_timestamp": "[02:30]",
                    "chunk_text": "Identification and Reconciliation Engine (IRE) rules require unique identifiers.",
                }
            ],
            "parent_sections": [
                {
                    "parent_id": "parent_12345",
                    "topic_title": "CMDB Identification & Reconciliation",
                    "source": "cmdb_guide.md",
                    "content": "Full section detailing IRE rule setup and class constraints in ServiceNow.",
                }
            ],
        },
        "generation": {
            "model": "openai/gpt-oss-20b",
            "messages": [
                {"role": "system", "content": "You are SnowWiki..."},
                {"role": "user", "content": "=== INTERNAL KNOWLEDGE BASE CONTEXT ===\n..."},
            ],
            "draft_output": "To configure CMDB identification rules, navigate to CI Class Manager...",
        },
        "answer": "To configure CMDB identification rules, navigate to CI Class Manager...",
    }

    log_llm_interaction(trace_sample)

    assert os.path.exists(HUMAN_LOG_FILE)
    assert os.path.exists(JSONL_LOG_FILE)

    with open(HUMAN_LOG_FILE, "r", encoding="utf-8") as f:
        human_content = f.read()
        assert "CMDB identification rules" in human_content
        assert "Parent-Child RAG" in human_content
        assert "Identification and Reconciliation Engine" in human_content
        assert "parent_12345" in human_content

    with open(JSONL_LOG_FILE, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
        assert len(lines) >= 1
        last_entry = json.loads(lines[-1])
        assert last_entry["query"] == "How do I configure CMDB identification rules?"
        assert last_entry["rag"]["similarity"] == 0.88


def test_print_terminal_context_transparency(capsys):
    retrieved_chunks = [
        {
            "similarity_score": 0.85,
            "source": "test_file.md",
            "page_or_timestamp": "[01:15]",
            "chunk_text": "Sample child chunk content.",
        }
    ]
    context_str = "--- Topic: Test Parent Section ---\nSample expanded parent text."

    print_terminal_context_transparency(
        query="Test query",
        similarity=0.85,
        legacy_index=False,
        retrieved_chunks=retrieved_chunks,
        context_str=context_str,
    )

    captured = capsys.readouterr()
    assert "WHAT THE LLM IS SEEING" in captured.out
    assert "Test query" in captured.out
    assert "Sample child chunk content." in captured.out
    assert "Sample expanded parent text." in captured.out
