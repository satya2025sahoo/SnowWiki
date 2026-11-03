# Junk Image Filtering — Final Rules

Goal: for every extracted image, decide **content** (send onward) or **junk**
(icon / logo / separator / blank — flag and skip) before it ever costs a VLM call.

## Pipeline order

```
extract image
   -> size + shape checks        (free)
   -> blank/color-variance check (free)
   -> corpus-repeat check        (needs one pre-pass over all images)
   -> [survived] OCR             (cheap, local)
   -> decorative-icon recheck    (uses OCR + color signal together)
   -> [survived] route to VLM: ocr_primary / ocr_plus_vlm / vlm_only
```

Nothing is ever deleted. Every image gets `junk: bool` + `reason` (or `route`
if kept), so a wrong call is one config change away from reversible — pull the
first ~100 drops and read them by eye before trusting the thresholds on the
full corpus.

## Final rule set

| # | Rule | Catches | Threshold |
|---|---|---|---|
| 1 | Too small | icons, bullets, spacers | width or height < 100px |
| 2 | Thin + extreme aspect ratio | separator lines, rules | ratio > 8:1 **and** short side < 60px |
| 3 | Blank / near-solid | empty boxes, plain backgrounds | ≤3 dominant colors covering >90% of pixels |
| 4 | Repeats across many documents | logos, letterheads, watermarks | same perceptual hash in ≥5 different docs |
| 5 | Decorative icon (post-OCR) | small icons that snuck past #1 | no OCR text **and** ≤4 colors **and** longest side < 200px |

Rules 1–4 run before OCR (cheapest first, and #4 needs a corpus-wide
pre-pass). Rule 5 needs the OCR result, so it runs after.

## Reference implementation

Dependencies (all local, no cloud calls):
```
pip install pillow ImageHash pytesseract
# + the tesseract-ocr binary on the system (e.g. apt install tesseract-ocr)
```

```python
from __future__ import annotations
import hashlib
from dataclasses import dataclass
from typing import Optional

import imagehash
import pytesseract
from PIL import Image

# ---- tunables --------------------------------------------------------
MIN_SIDE_PX           = 100
THIN_ASPECT_RATIO     = 8.0
THIN_MAX_SIDE_PX      = 60
BLANK_MAX_COLORS      = 3
BLANK_DOMINANT_PCT    = 0.90
REPEAT_DOC_THRESHOLD  = 5
DECORATIVE_MAX_SIDE   = 200
OCR_PRIMARY_CHARS     = 200


@dataclass
class ImageVerdict:
    junk: bool
    reason: Optional[str] = None
    route: Optional[str] = None       # "ocr_primary" | "ocr_plus_vlm" | "vlm_only"
    ocr_text: str = ""
    sha256: str = ""
    phash: str = ""


def _sha256(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _color_signal(img: Image.Image) -> tuple[int, float]:
    """(distinct dominant colors, % of pixels in the single most common one)"""
    colors = img.quantize(colors=32).getcolors() or []
    if not colors:
        return 999, 0.0
    total = img.width * img.height
    return len(colors), max(c for c, _ in colors) / total


def classify_image(path: str, doc_phash_counts: dict[str, int]) -> ImageVerdict:
    img = Image.open(path).convert("RGB")
    w, h = img.size
    sha = _sha256(path)
    phash = str(imagehash.phash(img))

    # Rule 1 — too small
    if w < MIN_SIDE_PX or h < MIN_SIDE_PX:
        return ImageVerdict(True, "too_small", sha256=sha, phash=phash)

    # Rule 2 — thin separator line
    ratio = max(w / h, h / w)
    if ratio > THIN_ASPECT_RATIO and min(w, h) < THIN_MAX_SIDE_PX:
        return ImageVerdict(True, "separator_line", sha256=sha, phash=phash)

    n_colors, dominant_pct = _color_signal(img)

    # Rule 3 — blank / near-solid
    if n_colors <= BLANK_MAX_COLORS and dominant_pct > BLANK_DOMINANT_PCT:
        return ImageVerdict(True, "blank_or_solid", sha256=sha, phash=phash)

    # Rule 4 — repeats across many documents (logo / letterhead / watermark)
    if doc_phash_counts.get(phash, 0) >= REPEAT_DOC_THRESHOLD:
        return ImageVerdict(True, "repeated_across_docs", sha256=sha, phash=phash)

    # --- passed the free checks: OCR runs once, locally ---
    ocr_text = pytesseract.image_to_string(img).strip()

    # Rule 5 — decorative icon that snuck past rule 1
    if not ocr_text and n_colors <= 4 and max(w, h) < DECORATIVE_MAX_SIDE:
        return ImageVerdict(True, "decorative_icon", sha256=sha, phash=phash)

    # --- kept: decide the VLM route ---
    if len(ocr_text) > OCR_PRIMARY_CHARS:
        route = "ocr_primary"      # table / screenshot — OCR carries the content
    elif ocr_text:
        route = "ocr_plus_vlm"     # labeled diagram — VLM prompt includes the OCR text
    else:
        route = "vlm_only"         # photo or unlabeled diagram

    return ImageVerdict(False, None, route, ocr_text, sha, phash)
```

## Corpus-repeat pre-pass

Run once per ingestion batch, before `classify_image()`, so rule 4 has
something to check against:

```python
def build_phash_doc_counts(image_paths_by_doc: dict[str, list[str]]) -> dict[str, int]:
    """How many distinct documents each perceptual hash appears in."""
    counts: dict[str, int] = {}
    for doc_id, paths in image_paths_by_doc.items():
        seen_in_this_doc = {
            str(imagehash.phash(Image.open(p).convert("RGB"))) for p in paths
        }
        for ph in seen_in_this_doc:
            counts[ph] = counts.get(ph, 0) + 1
    return counts
```

## Caching

Use SQLite, not `assets.json` — a JSON file will corrupt under parallel ingestion.

```sql
CREATE TABLE image_assets (
    sha256         TEXT NOT NULL,
    context_hash   TEXT NOT NULL,   -- hash of the heading + paragraph shown to the VLM
    model_version  TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    junk           INTEGER NOT NULL,
    reason         TEXT,
    route          TEXT,
    ocr_text       TEXT,
    description    TEXT,            -- VLM output; NULL for junk or ocr_primary
    doc_id         TEXT NOT NULL,
    image_id       TEXT NOT NULL,   -- short ID the LLM cites, e.g. IMG_7f3a
    PRIMARY KEY (sha256, context_hash, model_version, prompt_version)
);
```

`sha256` alone only cache-hits identical files — good for exact re-uploads.
`phash` (rule 4's field) is what catches a resized or re-saved copy of the
same logo. Keying the description cache on `context_hash + model_version +
prompt_version` means changing the prompt or the model correctly invalidates
old captions instead of silently reusing stale ones.

## Where this plugs into your pipeline

- **`pipeline.py`**, right after image extraction: call
  `build_phash_doc_counts()` once per batch, then `classify_image()` per image.
- Only `route in {"vlm_only", "ocr_plus_vlm"}` goes to **`enricher.py`**'s VLM
  call (pass `ocr_text` into the prompt for `ocr_plus_vlm`). `ocr_primary`
  skips the full VLM description and gets at most one short summary line.
- `junk=True` images never reach `enricher.py` or the embedding step — store
  the verdict in metadata and move on.

## Before turning it on

Pull ~100 already-extracted images, run `classify_image()` over them, and
read the `reason` field by eye. That's enough to catch a threshold that's too
aggressive (dropping real diagrams) or too loose (still letting icons
through) before it runs on the full corpus.
