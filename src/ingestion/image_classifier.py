from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import imagehash
import pytesseract
from PIL import Image

logger = logging.getLogger(__name__)

# ---- tunables --------------------------------------------------------
MIN_SIDE_PX           = 100
THIN_ASPECT_RATIO     = 8.0
THIN_MAX_SIDE_PX      = 60
BLANK_MAX_COLORS      = 3
BLANK_DOMINANT_PCT    = 0.90
REPEAT_DOC_THRESHOLD  = 5
DECORATIVE_MAX_SIDE   = 200
OCR_PRIMARY_CHARS     = 200

# ---- Data Structures -------------------------------------------------

@dataclass
class ImageVerdict:
    junk: bool
    reason: Optional[str] = None
    route: Optional[str] = None       # "ocr_primary" | "ocr_plus_vlm" | "vlm_only"
    ocr_text: str = ""
    sha256: str = ""
    phash: str = ""
    image_id: str = ""                # Short ID like IMG_7f3a


# ---- Helper Functions ------------------------------------------------

def _sha256(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _color_signal(img: Image.Image) -> tuple[int, float]:
    """(distinct dominant colors, % of pixels in the single most common one)"""
    colors = img.quantize(colors=32).getcolors() or []
    if not colors:
        return 999, 0.0
    total = img.width * img.height
    return len(colors), max(c for c, _ in colors) / total


def build_phash_doc_counts(image_paths_by_doc: dict[str, list[str]]) -> dict[str, int]:
    """How many distinct documents each perceptual hash appears in."""
    counts: dict[str, int] = {}
    for doc_id, paths in image_paths_by_doc.items():
        seen_in_this_doc = set()
        for p in paths:
            try:
                img = Image.open(p).convert("RGB")
                seen_in_this_doc.add(str(imagehash.phash(img)))
            except Exception as e:
                logger.warning(f"Failed to process image {p} for phash: {e}")
        for ph in seen_in_this_doc:
            counts[ph] = counts.get(ph, 0) + 1
    return counts


def classify_image(path: str, doc_phash_counts: dict[str, int]) -> ImageVerdict:
    try:
        img = Image.open(path).convert("RGB")
    except Exception as e:
        logger.error(f"Failed to open image {path} for classification: {e}")
        return ImageVerdict(True, "load_error")

    w, h = img.size
    sha = _sha256(path)
    phash = str(imagehash.phash(img))
    
    # Generate short image_id from sha256
    image_id = f"IMG_{sha[:4]}"

    # Rule 1 — too small
    if w < MIN_SIDE_PX or h < MIN_SIDE_PX:
        return ImageVerdict(True, "too_small", sha256=sha, phash=phash, image_id=image_id)

    # Rule 2 — thin separator line
    ratio = max(w / float(h), h / float(w))
    if ratio > THIN_ASPECT_RATIO and min(w, h) < THIN_MAX_SIDE_PX:
        return ImageVerdict(True, "separator_line", sha256=sha, phash=phash, image_id=image_id)

    n_colors, dominant_pct = _color_signal(img)

    # Rule 3 — blank / near-solid
    if n_colors <= BLANK_MAX_COLORS and dominant_pct > BLANK_DOMINANT_PCT:
        return ImageVerdict(True, "blank_or_solid", sha256=sha, phash=phash, image_id=image_id)

    # Rule 4 — repeats across many documents (logo / letterhead / watermark)
    if doc_phash_counts.get(phash, 0) >= REPEAT_DOC_THRESHOLD:
        return ImageVerdict(True, "repeated_across_docs", sha256=sha, phash=phash, image_id=image_id)

    # --- passed the free checks: OCR runs once, locally ---
    try:
        ocr_text = pytesseract.image_to_string(img).strip()
    except Exception as e:
        logger.warning(f"OCR failed for {path}: {e}")
        ocr_text = ""

    # Rule 5 — decorative icon that snuck past rule 1
    if not ocr_text and n_colors <= 4 and max(w, h) < DECORATIVE_MAX_SIDE:
        return ImageVerdict(True, "decorative_icon", sha256=sha, phash=phash, image_id=image_id)

    # --- kept: decide the VLM route ---
    if len(ocr_text) > OCR_PRIMARY_CHARS:
        route = "ocr_primary"      # table / screenshot — OCR carries the content
    elif ocr_text:
        route = "ocr_plus_vlm"     # labeled diagram — VLM prompt includes the OCR text
    else:
        route = "vlm_only"         # photo or unlabeled diagram

    return ImageVerdict(False, None, route, ocr_text, sha, phash, image_id)


# ---- SQLite Asset Cache ----------------------------------------------

def get_db_path() -> str:
    from src.ingestion.core import get_data_dir
    return os.path.join(get_data_dir(), "image_assets.db")

def init_db(db_path: str = None) -> None:
    if db_path is None:
        db_path = get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS image_assets (
            sha256         TEXT NOT NULL,
            context_hash   TEXT NOT NULL,
            model_version  TEXT NOT NULL,
            prompt_version TEXT NOT NULL,
            junk           INTEGER NOT NULL,
            reason         TEXT,
            route          TEXT,
            ocr_text       TEXT,
            description    TEXT,
            doc_id         TEXT NOT NULL,
            branch         TEXT NOT NULL,
            image_id       TEXT NOT NULL,
            rel_path       TEXT NOT NULL,
            abs_path       TEXT NOT NULL,
            page           INTEGER,
            parent_id      TEXT,
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (sha256, context_hash, model_version, prompt_version)
        );
        CREATE INDEX IF NOT EXISTS idx_image_assets_lookup ON image_assets (doc_id, image_id);
        CREATE INDEX IF NOT EXISTS idx_image_assets_sha ON image_assets (sha256);
    ''')
    conn.commit()
    conn.close()


def get_cached_asset(sha256: str, context_hash: str, model_version: str, prompt_version: str, db_path: str = None) -> Optional[dict]:
    if db_path is None:
        db_path = get_db_path()
    if not os.path.exists(db_path):
        return None
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM image_assets 
        WHERE sha256 = ? AND context_hash = ? AND model_version = ? AND prompt_version = ?
    ''', (sha256, context_hash, model_version, prompt_version))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None


def upsert_asset(asset: dict, db_path: str = None) -> None:
    if db_path is None:
        db_path = get_db_path()
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO image_assets (
            sha256, context_hash, model_version, prompt_version,
            junk, reason, route, ocr_text, description,
            doc_id, branch, image_id, rel_path, abs_path, page, parent_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(sha256, context_hash, model_version, prompt_version) DO UPDATE SET
            junk=excluded.junk,
            reason=excluded.reason,
            route=excluded.route,
            ocr_text=excluded.ocr_text,
            description=excluded.description,
            doc_id=excluded.doc_id,
            branch=excluded.branch,
            image_id=excluded.image_id,
            rel_path=excluded.rel_path,
            abs_path=excluded.abs_path,
            page=excluded.page,
            parent_id=excluded.parent_id
    ''', (
        asset.get("sha256"),
        asset.get("context_hash", ""),
        asset.get("model_version", ""),
        asset.get("prompt_version", ""),
        1 if asset.get("junk") else 0,
        asset.get("reason"),
        asset.get("route"),
        asset.get("ocr_text"),
        asset.get("description"),
        asset.get("doc_id"),
        asset.get("branch"),
        asset.get("image_id"),
        asset.get("rel_path"),
        asset.get("abs_path"),
        asset.get("page"),
        asset.get("parent_id")
    ))
    
    conn.commit()
    conn.close()
