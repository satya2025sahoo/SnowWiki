import os
import sys
import time
import traceback

import torch
print("CUDA available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("Using device:", torch.cuda.get_device_name())

# Must be set BEFORE any marker/surya imports
os.environ["SURYA_INFERENCE_BACKEND"] = "llamacpp"
os.environ["TORCH_DEVICE"] = "cuda"                          # GPU for Marker torch models
os.environ["LLAMA_CPP_NGL"] = "99"                          # Offload all layers to GPU
os.environ["LLAMA_CPP_BINARY"] = r"D:\SnowWiki\tools\llama-cpp\llama-server.exe"
os.environ["SURYA_GGUF_LOCAL_MODEL_PATH"] = r"D:\SnowWiki\models\surya-2.gguf"
os.environ["SURYA_GGUF_LOCAL_MMPROJ_PATH"] = r"D:\SnowWiki\models\surya-2-mmproj.gguf"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered

# Add src to path so we can import markdown_cleanup
sys.path.insert(0, r"D:\SnowWiki\src")
from ingestion.pdf_utils.markdown_cleanup import clean_marker_markdown

pdf_path = r"D:\SnowWiki\CIS-DF 13.pdf"
output_path = r"D:\SnowWiki\output CIS-DF 13.md"

# Windows multiprocessing requires all spawning to happen inside this guard
if __name__ == "__main__":
    try:
        print("Loading models (GPU mode, local GGUF)...")
        c = PdfConverter(
            artifact_dict=create_model_dict(),
            config={"pdftext_workers": 1}
        )
        print("Running conversion...")
        rendered = c(pdf_path)
        text, metadata, images = text_from_rendered(rendered)

        print("Cleaning up markdown...")
        cleaned = clean_marker_markdown(text)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(cleaned)

        print(f"SUCCESS — extracted {len(text)} chars, {len(images)} images")
        print(f"Cleaned markdown saved to {output_path}")
        print("\n--- Preview (first 800 chars) ---\n")
        print(cleaned[:800])
    except Exception as e:
        traceback.print_exc()
    finally:
        # Give Surya's spawned worker a moment to exit cleanly before the script ends,
        # so a stray interrupt during cleanup doesn't print a scary-looking (harmless) traceback.
        time.sleep(1)