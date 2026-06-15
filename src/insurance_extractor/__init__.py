"""Offline proof-of-insurance document extraction.

Pipeline: ingest -> preprocess -> OCR -> map-to-schema -> coerce -> validate.
All steps run locally; no cloud services are required.
"""

from .config import Settings, get_settings
from .pipeline import ExtractionResult, extract_document, extract_path

__all__ = ["extract_document", "extract_path", "ExtractionResult", "Settings", "get_settings"]
__version__ = "0.1.0"
