"""
src/ingestion/pdf_utils/structure.py
====================================
Structural metadata extraction for PDF to Markdown v2.
Handles TOC extraction and font-size clustering for heading hierarchy.
"""
from typing import Dict, Any, List

def extract_toc(pdf_path: str) -> List[Dict[str, Any]]:
    """Extract TOC using pymupdf."""
    try:
        import fitz
    except ImportError:
        return []
    
    toc = []
    try:
        doc = fitz.open(pdf_path)
        toc = doc.get_toc()
    except Exception:
        pass
    
    # toc format is [level, title, page, ...]
    result = []
    for item in toc:
        if len(item) >= 3:
            result.append({
                "level": item[0],
                "title": item[1],
                "page": item[2]
            })
    return result

def cluster_font_sizes(blocks: List[Any]) -> Dict[float, int]:
    """
    Cluster font sizes to identify heading levels.
    Returns mapping of avg_size to heading level (1-6) or 0 (body text).
    """
    sizes = sorted(list(set([b.avg_size for b in blocks if b.avg_size > 0])), reverse=True)
    if not sizes:
        return {}
    
    # Simple heuristic: largest 3 distinct sizes are H1, H2, H3
    mapping = {}
    level = 1
    for s in sizes:
        if level <= 3:
            mapping[s] = level
            level += 1
        else:
            mapping[s] = 0
            
    return mapping
