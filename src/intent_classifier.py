"""
src/intent_classifier.py
========================
Stage 1 — Intent Classifier for the SnowWiki Smart Routing pipeline.

Classifies each user query into:
    GREETING | CONVERSATIONAL | SERVICENOW | OUT_OF_SCOPE

For SERVICENOW queries, also classifies the RAG sub-intent:
    global_summary | detailed_fact

Supports two backends:
1. Jev-Style Discriminative Classifier (CLASSIFIER_BACKEND="jev"):
   Fast (~5ms), open-source zero-shot similarity encoder using local embeddings.
   Zero hallucination, deterministic, zero JSON syntax errors.
2. LLM Mode (CLASSIFIER_BACKEND="llm"):
   Generative classifier via Ollama (qwen3:0.6b / qwen2.5:0.5b) or Groq.

Public API
----------
classify_intent(query: str) -> dict
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from src.config import GROQ_CLASSIFIER_MODEL, CLASSIFIER_BACKEND
from src.servicenow_domain import get_classifier_domain_prompt
from src.llm_wrapper import get_chat_client

logger = logging.getLogger(__name__)


# ── Jev-Style Discriminative Classifier (Open-Source Fast Encoder) ────────────

_DISCRIMINATIVE_MODEL = None
_ANCHOR_EMBEDDINGS = None

_INTENT_ANCHORS = {
    "GREETING": [
        "hello hi hey good morning good evening greetings pleasantries thanks thank you goodbye bye",
        "how are you how do you do nice to meet you",
    ],
    "CONVERSATIONAL": [
        "what was my last question repeat that explain what you said earlier what did you mean by that",
        "summarize our chat history what have we discussed so far recap our conversation",
    ],
    "SERVICENOW": [
        "ServiceNow platform configuration ITSM ITOM CSM HRSD CMDB CSDM tables scripting workflow",
        "Asset Management Configuration Item CI Deploy node Lifecycle diagram Discovery mid server",
        "Service catalog business rule client script script include incident change problem SLA",
    ],
    "OUT_OF_SCOPE": [
        "what is the weather today recipe for chocolate cake sports score football news",
        "write a poem about flowers who won the election travel flight booking general trivia",
    ],
}

_GLOBAL_SUMMARY_KEYWORDS = {
    "summarize", "summary", "overview", "high-level", "broadly",
    "general topics", "what does this session cover", "big picture",
    "table of contents", "outline"
}


def _get_discriminative_encoder():
    """Lazily load and cache the sentence-transformers encoder for discriminative routing."""
    global _DISCRIMINATIVE_MODEL, _ANCHOR_EMBEDDINGS
    if _DISCRIMINATIVE_MODEL is not None:
        return _DISCRIMINATIVE_MODEL, _ANCHOR_EMBEDDINGS

    try:
        import torch
        from sentence_transformers import SentenceTransformer, util
        from src.config import EMBEDDING_MODEL_NAME

        _DISCRIMINATIVE_MODEL = SentenceTransformer(EMBEDDING_MODEL_NAME)
        # Compute mean embeddings for each intent anchor
        _ANCHOR_EMBEDDINGS = {}
        for intent, texts in _INTENT_ANCHORS.items():
            embs = _DISCRIMINATIVE_MODEL.encode(texts, convert_to_tensor=True)
            _ANCHOR_EMBEDDINGS[intent] = torch.mean(embs, dim=0, keepdim=True)

        return _DISCRIMINATIVE_MODEL, _ANCHOR_EMBEDDINGS
    except Exception as exc:
        logger.warning("Could not initialize discriminative classifier: %s", exc)
        return None, None


def _classify_discriminative_jev(query: str) -> Optional[dict]:
    """
    Open-source Jev-style discriminative classification.
    Calculates cosine similarity against intent anchor embeddings.
    Runs in ~5ms with zero chance of JSON parse failures.
    """
    model, anchor_embs = _get_discriminative_encoder()
    if model is None or anchor_embs is None:
        return None

    try:
        import torch
        from sentence_transformers import util

        q_clean = query.strip()
        if not q_clean:
            return {
                "intent": "GREETING",
                "rag_sub_intent": "detailed_fact",
                "confidence": 1.0,
                "raw_output": "Discriminative-Jev: empty input -> GREETING",
                "system_prompt": "Jev-Discriminative-Encoder",
            }

        q_emb = model.encode(q_clean, convert_to_tensor=True)

        scores = {}
        for intent, a_emb in anchor_embs.items():
            sim = util.cos_sim(q_emb, a_emb).item()
            scores[intent] = sim

        # Direct classification
        best_intent = max(scores, key=scores.get)
        confidence = round(max(0.0, min(1.0, scores[best_intent])), 3)

        # ServiceNow sub-intent heuristic
        rag_sub = "detailed_fact"
        if best_intent == "SERVICENOW":
            q_lower = q_clean.lower()
            if any(k in q_lower for k in _GLOBAL_SUMMARY_KEYWORDS):
                rag_sub = "global_summary"

        return {
            "intent": best_intent,
            "rag_sub_intent": rag_sub,
            "confidence": confidence,
            "raw_output": f"Discriminative-Jev scores: {scores}",
            "system_prompt": "Jev-Discriminative-Anchor-Similarity",
        }
    except Exception as exc:
        logger.warning("Discriminative classification failed, falling back: %s", exc)
        return None


# ── LLM Generative System Prompt ──────────────────────────────────────────────

_INTENT_SYSTEM = f"""You are an intent classifier for a ServiceNow enterprise knowledge assistant.

{get_classifier_domain_prompt()}

Classify the user message into EXACTLY one of these intents:
  - GREETING       : greetings, chit-chat, thanks, farewells, or pleasantries
  - CONVERSATIONAL : questions about the conversation itself — "what was my last question?", "can you explain that again?", "I didn't understand your reply", "repeat that", "what did you mean by X?", "what have we discussed so far?"
  - SERVICENOW     : any question or request related to ServiceNow platform, modules, configuration, workflows, scripting, ITSM, ITOM, CSM, HRSD, etc.
  - OUT_OF_SCOPE   : anything not related to ServiceNow or greetings.

For SERVICENOW intent, also classify rag_sub_intent:
  - global_summary : ONLY broad panoramic queries — "Summarize the video", "What general topics are covered?", "Give me a high-level overview of...", "What does this session cover broadly?"
  - detailed_fact  : narrow/specific fact-finding queries — "What are the types of X?", "List the features of Y", "How do I set class constraints?", "What is the property name for X?", "Explain step 3 of the workflow"

Respond with ONLY valid JSON — no markdown, no explanation:
{{"intent": "<GREETING|CONVERSATIONAL|SERVICENOW|OUT_OF_SCOPE>", "rag_sub_intent": "<global_summary|detailed_fact>", "confidence": <0.0-1.0>}}

Note: rag_sub_intent is only meaningful when intent == SERVICENOW; for all other intents set it to "detailed_fact"."""


# ── Public API ─────────────────────────────────────────────────────────────────

def classify_intent(query: str) -> dict:
    """
    Classify the user query into GREETING | CONVERSATIONAL | SERVICENOW | OUT_OF_SCOPE.
    
    If CLASSIFIER_BACKEND is 'jev' or 'discriminative', uses the fast local
    open-source discriminative encoder. Otherwise, queries the configured LLM.
    """
    # 1. Fast Jev-Style Discriminative Path
    if CLASSIFIER_BACKEND in ("jev", "discriminative"):
        disc_result = _classify_discriminative_jev(query)
        if disc_result is not None:
            return disc_result

    # 2. LLM Path (Ollama qwen3:0.6b or Groq)
    try:
        client = get_chat_client()
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

        # Robust JSON extraction: strip thinking tokens and code fences
        raw_clean = re.sub(r"<think>[\s\S]*?</think>", "", raw).strip()
        raw_clean = re.sub(r"```(?:json)?|```", "", raw_clean).strip()

        match = re.search(r"\{[\s\S]*?\}", raw_clean)
        if match:
            data = json.loads(match.group(0))
        else:
            data = json.loads(raw_clean)

        intent = str(data.get("intent", "SERVICENOW")).upper()
        rag_sub = str(data.get("rag_sub_intent", "detailed_fact")).lower()
        confidence = float(data.get("confidence", 0.9))

        if intent not in {"GREETING", "CONVERSATIONAL", "SERVICENOW", "OUT_OF_SCOPE"}:
            intent = "SERVICENOW"
        if rag_sub not in {"global_summary", "detailed_fact"}:
            rag_sub = "detailed_fact"

        return {
            "intent": intent,
            "rag_sub_intent": rag_sub,
            "confidence": confidence,
            "raw_output": raw,
            "system_prompt": _INTENT_SYSTEM,
        }

    except Exception as exc:
        logger.warning("[intent_classifier] LLM classification error: %s", exc)
        return {
            "intent": "SERVICENOW",
            "rag_sub_intent": "detailed_fact",
            "confidence": 0.5,
            "raw_output": f"ERROR: {exc}",
            "system_prompt": _INTENT_SYSTEM,
        }
