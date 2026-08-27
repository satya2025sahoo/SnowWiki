"""
src/intent_classifier.py
========================
Stage 1 — Intent Classifier for the SnowWiki Smart Routing pipeline.

Classifies each user query into:
    GREETING | CONVERSATIONAL | SERVICENOW | OUT_OF_SCOPE

For SERVICENOW queries, also classifies the RAG sub-intent:
    global_summary | detailed_fact

Public API
----------
classify_intent(query: str) -> dict
"""

from __future__ import annotations

import json
import re

from src.config import GROQ_CLASSIFIER_MODEL
from src.servicenow_domain import get_classifier_domain_prompt
from src.llm_wrapper import get_chat_client


# ── Intent System Prompt ───────────────────────────────────────────────────────

_INTENT_SYSTEM = f"""You are an intent classifier for a ServiceNow enterprise knowledge assistant.

{get_classifier_domain_prompt()}

Classify the user message into EXACTLY one of these intents:
  - GREETING       : greetings, chit-chat, thanks, farewells, or pleasantries
  - CONVERSATIONAL : questions about the conversation itself — "what was my last question?", "can you explain that again?", "I didn't understand your reply", "repeat that", "what did you mean by X?", "what have we discussed so far?"
  - SERVICENOW     : any question or request related to ServiceNow platform, modules, configuration, workflows, scripting, ITSM, ITOM, CSM, HRSD, etc.
  - OUT_OF_SCOPE   : anything not related to ServiceNow or greetings.

For SERVICENOW intent, also classify rag_sub_intent:
  - global_summary : broad/overview queries — "Summarize the video", "List all features of X", "What topics are covered?", "Give me an overview of...", "What does this session cover?", "What can you tell me about..."
  - detailed_fact  : narrow/specific queries — "How do I set class constraints?", "What is the property name for X?", "Show me the script for Y", "Explain step 3 of the workflow", "What is the configuration for Z?"

Respond with ONLY valid JSON — no markdown, no explanation:
{{"intent": "<GREETING|CONVERSATIONAL|SERVICENOW|OUT_OF_SCOPE>", "rag_sub_intent": "<global_summary|detailed_fact>", "confidence": <0.0-1.0>}}

Note: rag_sub_intent is only meaningful when intent == SERVICENOW; for all other intents set it to "detailed_fact"."""


# ── Public API ─────────────────────────────────────────────────────────────────

def classify_intent(query: str) -> dict:
    """
    Call llama-3.1-8b-instant to classify the user's intent.

    Returns:
        {
            "intent": "GREETING|CONVERSATIONAL|SERVICENOW|OUT_OF_SCOPE",
            "rag_sub_intent": "global_summary|detailed_fact",
            "confidence": float,
            "raw_output": str,          # raw JSON string from LLM (for trace)
            "system_prompt": str,       # classifier system prompt (for trace)
        }
    """
    try:
        client   = get_chat_client()
        response = client.chat.completions.create(
            model=GROQ_CLASSIFIER_MODEL,
            messages=[
                {"role": "system", "content": _INTENT_SYSTEM},
                {"role": "user",   "content": query},
            ],
            max_tokens=80,
            temperature=0.0,
        )
        raw = response.choices[0].message.content.strip()

        # Strip markdown code fences if the model wraps anyway
        raw_clean = re.sub(r"```(?:json)?|```", "", raw).strip()
        data = json.loads(raw_clean)

        intent      = str(data.get("intent", "SERVICENOW")).upper()
        rag_sub     = str(data.get("rag_sub_intent", "detailed_fact")).lower()
        confidence  = float(data.get("confidence", 0.9))

        if intent not in {"GREETING", "CONVERSATIONAL", "SERVICENOW", "OUT_OF_SCOPE"}:
            intent = "SERVICENOW"
        if rag_sub not in {"global_summary", "detailed_fact"}:
            rag_sub = "detailed_fact"

        return {
            "intent":        intent,
            "rag_sub_intent": rag_sub,
            "confidence":    confidence,
            "raw_output":    raw,
            "system_prompt": _INTENT_SYSTEM,
        }

    except Exception as exc:
        print(f"[intent_classifier] Classification error: {exc}")
        return {
            "intent":        "SERVICENOW",
            "rag_sub_intent": "detailed_fact",
            "confidence":    0.5,
            "raw_output":    f"ERROR: {exc}",
            "system_prompt": _INTENT_SYSTEM,
        }
