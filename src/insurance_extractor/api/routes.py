"""HTTP routes. Thin handlers that delegate to the pipeline."""

from __future__ import annotations

import base64
import binascii
import json

from fastapi import APIRouter, File, Form, UploadFile

from ..config import get_settings
from ..errors import SchemaError
from ..pipeline import extract_document
from .schemas import ExtractJsonRequest

router = APIRouter()


@router.get("/health", tags=["ops"])
def health() -> dict:
    return {"status": "ok"}


@router.post("/extract-json", tags=["extract"])
def extract_json(req: ExtractJsonRequest) -> dict:
    """Preferred endpoint behind API Gateway (base64 body, no multipart)."""
    try:
        data = base64.b64decode(req.content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SchemaError(f"Invalid base64 content: {exc}") from exc

    return extract_document(
        data, req.filename, req.schema_, strategy=req.options.get("strategy")
    ).to_dict()


@router.post("/extract", tags=["extract"])
async def extract(
    file: UploadFile = File(..., description="PDF/PNG/JPG document"),
    schema: str = Form(..., description="JSON Schema as a string"),
    options: str = Form("{}", description="Optional JSON: {strategy}"),
) -> dict:
    """Multipart upload variant."""
    try:
        schema_obj = json.loads(schema)
    except json.JSONDecodeError as exc:
        raise SchemaError(f"Invalid schema JSON: {exc}") from exc
    try:
        opts = json.loads(options or "{}")
    except json.JSONDecodeError as exc:
        raise SchemaError(f"Invalid options JSON: {exc}") from exc

    data = await file.read()
    return extract_document(
        data, file.filename or "upload", schema_obj, strategy=opts.get("strategy")
    ).to_dict()
