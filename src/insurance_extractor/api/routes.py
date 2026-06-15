"""HTTP routes.

Two flavors of extraction:
  - synchronous: POST /extract, /extract-json  -> result in the response
  - asynchronous: POST /jobs, /jobs-json -> {job_id}; GET /jobs/{id} -> result
    (use the async flow when ingestion may be slow; it never blocks the caller)
"""

from __future__ import annotations

import base64
import binascii
import json

from fastapi import APIRouter, File, Form, UploadFile, status

from ..errors import JobNotFoundError, SchemaError
from ..jobs import get_job_service
from ..pipeline import extract_document
from .schemas import ExtractJsonRequest, SubmitJobRequest, SubmitJobResponse

router = APIRouter()


def _decode_b64(content: str) -> bytes:
    try:
        return base64.b64decode(content, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SchemaError(f"Invalid base64 content: {exc}") from exc


@router.get("/health", tags=["ops"])
def health() -> dict:
    return {"status": "ok"}


@router.post("/extract-json", tags=["extract (sync)"])
def extract_json(req: ExtractJsonRequest) -> dict:
    """Preferred endpoint behind API Gateway (base64 body, no multipart)."""
    data = _decode_b64(req.content_base64)
    return extract_document(
        data, req.filename, req.schema_, strategy=req.options.get("strategy")
    ).to_dict()


@router.post("/extract", tags=["extract (sync)"])
async def extract(
    file: UploadFile = File(..., description="PDF/PNG/JPG document"),
    schema: str = Form(..., description="JSON Schema as a string"),
    options: str = Form("{}", description="Optional JSON: {strategy}"),
) -> dict:
    """Multipart upload variant."""
    schema_obj = _parse_json(schema, "schema")
    opts = _parse_json(options or "{}", "options")
    data = await file.read()
    return extract_document(
        data, file.filename or "upload", schema_obj, strategy=opts.get("strategy")
    ).to_dict()


def _parse_json(raw: str, what: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SchemaError(f"Invalid {what} JSON: {exc}") from exc


# --- async job API ---------------------------------------------------------

@router.post(
    "/jobs", tags=["jobs (async)"], status_code=status.HTTP_202_ACCEPTED,
    response_model=SubmitJobResponse,
)
async def submit_job(
    file: UploadFile = File(..., description="PDF/PNG/JPG document"),
    schema: str = Form(..., description="JSON Schema as a string"),
    options: str = Form("{}", description="Optional JSON: {strategy}"),
) -> SubmitJobResponse:
    """Upload a document for asynchronous extraction. Returns a job_id to poll."""
    schema_obj = _parse_json(schema, "schema")
    opts = _parse_json(options or "{}", "options")
    data = await file.read()
    job = get_job_service().submit(
        data, file.filename or "upload", schema_obj, strategy=opts.get("strategy")
    )
    return SubmitJobResponse(job_id=job.job_id, status=job.status.value, created_at=job.created_at)


@router.post(
    "/jobs-json", tags=["jobs (async)"], status_code=status.HTTP_202_ACCEPTED,
    response_model=SubmitJobResponse,
)
def submit_job_json(req: SubmitJobRequest) -> SubmitJobResponse:
    """Base64 variant of POST /jobs (no multipart)."""
    data = _decode_b64(req.content_base64)
    job = get_job_service().submit(
        data, req.filename, req.schema_, strategy=req.options.get("strategy")
    )
    return SubmitJobResponse(job_id=job.job_id, status=job.status.value, created_at=job.created_at)


@router.get("/jobs/{job_id}", tags=["jobs (async)"])
def get_job(job_id: str) -> dict:
    """Fetch a job's status and (once SUCCEEDED) its extraction result."""
    job = get_job_service().get(job_id)
    if job is None:
        raise JobNotFoundError(f"Job {job_id} not found")
    return job.public_dict()
