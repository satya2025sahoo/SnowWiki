import os
import traceback

# Must be set before any marker/surya imports
os.environ["SURYA_INFERENCE_BACKEND"] = "transformers"
os.environ["TORCH_DEVICE"] = "cpu"

from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered

pdf_path = r"d:\SnowWiki\data\uploads\CSM Training\CIS-DF.pdf\CIS-DF.pdf"
try:
    print("Loading models...")
    c = PdfConverter(artifact_dict=create_model_dict())
    print("Running conversion...")
    rendered = c(pdf_path)
    text, metadata, images = text_from_rendered(rendered)
    print(f"SUCCESS — extracted {len(text)} chars, {len(images)} images")
    print(text[:500])
except Exception as e:
    traceback.print_exc()
