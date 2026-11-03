"""
src/servicenow_domain.py
========================
Domain knowledge definitions, terminology, and out-of-scope taxonomy for ServiceNow.
Used to enforce strict, robust intent classification and prevent AI hallucinations.
"""

from __future__ import annotations

# ── ServiceNow Domain Keywords & Concepts ─────────────────────────────────────

SERVICENOW_MODULES = [
    "ITSM", "ITOM", "CSM", "HRSD", "SPM", "HAM", "SAM", "APM", "FSM", "SecOps",
    "Service Catalog", "CMDB", "Knowledge Management", "Portal", "Service Portal",
]

SERVICENOW_TECHNICAL_TERMS = [
    "GlideRecord", "GlideSystem", "g_form", "g_user", "g_scratchpad",
    "Business Rule", "Script Include", "Client Script", "UI Policy", "UI Action",
    "Flow Designer", "Workflow", "IntegrationHub", "Transform Map", "Import Set",
    "Update Set", "Sys_id", "ACL", "Access Control", "MID Server", "Discovery",
    "Service Mapping", "Event Management", "Incident", "Change Request", "Problem",
    "Requested Item", "RITM", "Catalog Task", "sc_req_item", "sys_user", "sys_choice",
]

# ── Explicit Out-of-Scope Taxonomy ────────────────────────────────────────────

OUT_OF_SCOPE_CATEGORIES = {
    "General AI & Machine Learning": [
        "recursive language model", "language model", "LLM architecture", "PyTorch",
        "TensorFlow", "convolutional neural network", "transformer model", "BERT",
        "GPT-4", "fine-tuning", "vector embedding model", "reinforcement learning",
    ],
    "General Software Engineering & DevOps": [
        "React", "Vue", "Angular", "Docker", "Kubernetes", "C++", "Java Spring Boot",
        "Django", "Flask", "PostgreSQL query tuning", "Linux kernel", "git rebase",
    ],
    "General Computing & Cloud (Non-ServiceNow)": [
        "AWS S3 bucket policy", "Azure Blob storage", "GCP Compute Engine",
    ],
    "Non-Technical Topics": [
        "cooking recipes", "sports scores", "politics", "financial stock advice",
        "movie reviews", "weather forecast",
    ],
}


def get_classifier_domain_prompt() -> str:
    """
    Format the domain knowledge rules into a concise prompt segment
    for the intent classifier LLM.
    """
    out_scope_examples = []
    for cat, examples in OUT_OF_SCOPE_CATEGORIES.items():
        out_scope_examples.append(f"  - {cat}: {', '.join(examples[:4])}")

    return (
        f"SERVICENOW DOMAIN INCLUDES:\n"
        f"Modules: {', '.join(SERVICENOW_MODULES[:8])}\n"
        f"Technical terms: {', '.join(SERVICENOW_TECHNICAL_TERMS[:10])}, etc.\n\n"
        f"EXPLICIT OUT_OF_SCOPE CATEGORIES (Must classify as OUT_OF_SCOPE):\n"
        + "\n".join(out_scope_examples)
    )

def get_ingested_topics(branch_state: dict) -> list[str]:
    """
    Extracts the unique ServiceNow topics from the branch state files.
    """
    files_dict = branch_state.get("files", {})
    matched_modules = set()
    
    for fname, finfo in files_dict.items():
        f_summary = finfo.get("summary", "").lower()
        for module in SERVICENOW_MODULES:
            if module.lower() in f_summary:
                matched_modules.add(module)
                
    if not matched_modules:
        return ["ServiceNow topics from your uploaded sessions"]
        
    return list(matched_modules)
