"""
src/chains.py
=============
LangChain prompt templates and chain builders for SnowWiki.

Chains:
  - intent_classification_chain()  -> classifies GREETING | SERVICENOW | OUT_OF_SCOPE
  - rag_answer_chain()             -> RAG answer generation with memory & retrieved context
"""

from langchain_core.prompts import PromptTemplate
from langchain.chains import LLMChain  # langchain (classic) still ships LLMChain
from .llm_wrapper import get_llm
from .servicenow_domain import get_classifier_domain_prompt

# ── Intent Classification Prompt ───────────────────────────────────────────────
INTENT_SYSTEM_PROMPT = PromptTemplate(
    input_variables=["domain_prompt", "query"],
    template=(
        "You are an intent classifier for a ServiceNow assistant.\n"
        "{domain_prompt}\n"
        "Classify the following user query *exactly* as JSON:\n"
        "{\"intent\": \"GREETING|SERVICENOW|OUT_OF_SCOPE\", \"confidence\": <0.0-1.0>}\n"
        "User query: {query}"
    ),
)

# ── RAG Answer Prompt ──────────────────────────────────────────────────────────
RAG_ANSWER_PROMPT = PromptTemplate(
    input_variables=[
        "master_summary",
        "running_summary",
        "recent_turns",
        "retrieved_chunks",
        "question",
    ],
    template=(
        "You are SnowWiki, an expert ServiceNow assistant.\n"
        "Use ONLY the INTERNAL KNOWLEDGE BASE below. If the context is insufficient, respond with the token "
        "<<INSUFFICIENT>>.\n"
        "=== MASTER SUMMARY ===\n{master_summary}\n"
        "=== CONVERSATION MEMORY ===\n{running_summary}\n"
        "=== RECENT EXCHANGES ===\n{recent_turns}\n"
        "=== RETRIEVED CHUNKS ===\n{retrieved_chunks}\n"
        "=== USER QUESTION ===\n{question}"
    ),
)

# ── Chain Factories ────────────────────────────────────────────────────────────

def intent_classification_chain() -> LLMChain:
    """Return an LLMChain for intent classification using the small (classifier) LLM."""
    llm = get_llm(kind="classifier")
    return LLMChain(llm=llm, prompt=INTENT_SYSTEM_PROMPT)


def rag_answer_chain() -> LLMChain:
    """Return an LLMChain for RAG-grounded answer generation using the large (response) LLM."""
    llm = get_llm(kind="response")
    return LLMChain(llm=llm, prompt=RAG_ANSWER_PROMPT)
