"""Orchestrates the full extraction: ingest -> OCR -> map -> coerce -> validate.

This module is the single public entry point used by the API and the CLI. The
choice of OCR engine and mapper strategy is driven entirely by Settings, so the
same code path runs identically across local, Docker, and Lambda.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from .config import Settings, get_settings
from .coerce import coerce_all
from .errors import DocumentTooLargeError
from .ingest import load_document, load_path
from .mappers import build_mapper
from .observability import Timer, get_logger
from .ocr import Line, OcrResult, get_ocr_engine
from .types import FieldResult
from .validate import validate_payload

log = get_logger(__name__)


@dataclass
class ExtractionResult:
    data: dict[str, Any]
    confidence: dict[str, float]
    provenance: dict[str, Any]
    validation: dict[str, Any]
    engine: str
    ocr_text: str = field(default="", repr=False)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("ocr_text", None)
        return d


def extract_document(
    data: bytes,
    source_name: str,
    schema: dict,
    *,
    strategy: Optional[str] = None,
    settings: Optional[Settings] = None,
) -> ExtractionResult:
    settings = settings or get_settings()
    strategy = strategy or settings.default_strategy

    if len(data) > settings.max_upload_bytes:
        raise DocumentTooLargeError(
            f"Document is {len(data) // 1024} KB; limit is {settings.max_upload_mb} MB"
        )

    doc = load_document(data, source_name, dpi=settings.pdf_dpi, max_pages=settings.max_pages)
    ocr_results = _ocr_pages(doc, settings)

    mapper = build_mapper(strategy, settings)
    with Timer() as t:
        fields: dict[str, FieldResult] = mapper.map(schema, ocr_results)

    raw = {k: fr.value for k, fr in fields.items()}
    coerced = coerce_all(raw, schema)
    report = validate_payload(coerced, schema)

    log.info(
        "extraction complete",
        extra={"extra": {
            "source": source_name, "strategy": mapper.name, "pages": len(doc.pages),
            "valid": report.valid, "map_ms": t.ms,
        }},
    )

    return ExtractionResult(
        data=coerced,
        confidence={k: fr.confidence for k, fr in fields.items()},
        provenance={
            k: (asdict(fr.provenance) if fr.provenance else None) for k, fr in fields.items()
        },
        validation={"valid": report.valid, "errors": report.errors},
        engine=mapper.name,
        ocr_text="\n\n".join(r.text for r in ocr_results),
    )


def _ocr_pages(doc, settings: Settings) -> list[OcrResult]:
    """OCR each page, reusing a PDF's digital text layer where present."""
    engine = get_ocr_engine(settings)
    results: list[OcrResult] = []
    for page in doc.pages:
        if page.text_layer.strip():
            lines = [
                Line(t, (0, 0, 0, 0), 0.99)
                for t in page.text_layer.splitlines()
                if t.strip()
            ]
            results.append(OcrResult(page_index=page.index, lines=lines))
        else:
            results.append(engine.run(page.image, page.index))
    return results


def extract_path(path: str | Path, schema: dict, **kwargs) -> ExtractionResult:
    settings = kwargs.get("settings") or get_settings()
    doc = load_path(path, dpi=settings.pdf_dpi, max_pages=settings.max_pages)
    return extract_document(Path(path).read_bytes(), doc.source_name, schema, **kwargs)
