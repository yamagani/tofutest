"""Config and input-guard behavior."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from insurance_extractor import extract_document, get_settings
from insurance_extractor.errors import DocumentTooLargeError, TooManyPagesError
from insurance_extractor.mappers import build_mapper

from .sample_doc import make_png_bytes

SCHEMA = json.loads(
    (Path(__file__).parent.parent / "examples" / "proof_of_insurance.schema.json").read_text()
)


def test_env_override(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("IE_MAX_UPLOAD_MB", "1")
    monkeypatch.setenv("IE_DEFAULT_STRATEGY", "llm")
    s = get_settings()
    assert s.max_upload_mb == 1 and s.default_strategy == "llm"
    get_settings.cache_clear()


def test_build_mapper_unknown_strategy():
    with pytest.raises(ValueError):
        build_mapper("nonsense", get_settings())


def test_document_too_large():
    tiny = get_settings().model_copy(update={"max_upload_mb": 0})
    with pytest.raises(DocumentTooLargeError):
        extract_document(make_png_bytes(), "cert.png", SCHEMA, strategy="rule", settings=tiny)


def test_too_many_pages(tmp_path):
    import fitz

    pdf = fitz.open()
    for _ in range(3):
        pdf.new_page()
    data = pdf.tobytes()
    pdf.close()
    limited = get_settings().model_copy(update={"max_pages": 2})
    with pytest.raises(TooManyPagesError):
        extract_document(data, "multi.pdf", SCHEMA, strategy="rule", settings=limited)
