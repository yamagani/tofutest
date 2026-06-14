"""JobService behavior with the in-memory store (inline worker, deterministic)."""

from __future__ import annotations

import json
from pathlib import Path

from insurance_extractor.config import Settings
from insurance_extractor.jobs import JobService
from insurance_extractor.storage import JobStatus, MemoryStore

from .sample_doc import make_png_bytes

SCHEMA = json.loads(
    (Path(__file__).parent.parent / "examples" / "proof_of_insurance.schema.json").read_text()
)


def _service() -> JobService:
    settings = Settings(store_backend="memory", worker_inline=True, default_strategy="rule")
    return JobService(MemoryStore(), settings)


def test_submit_then_succeeds():
    svc = _service()
    job = svc.submit(make_png_bytes(), "cert.png", SCHEMA)
    fetched = svc.get(job.job_id)
    assert fetched.status is JobStatus.SUCCEEDED
    assert fetched.result["data"]["policy_number"] == "NWM-4820-7731"
    assert fetched.result["validation"]["valid"] is True


def test_unknown_job_is_none():
    assert _service().get("does-not-exist") is None


def test_failed_job_records_error():
    svc = _service()
    job = svc.submit(b"not a real document", "note.txt", SCHEMA)
    fetched = svc.get(job.job_id)
    assert fetched.status is JobStatus.FAILED
    assert "unsupported_document" in fetched.error


def test_public_dict_hides_internal_fields():
    svc = _service()
    job = svc.submit(make_png_bytes(), "cert.png", SCHEMA)
    pub = svc.get(job.job_id).public_dict()
    assert "schema" not in pub and "document_key" not in pub
    assert pub["status"] == "SUCCEEDED" and "result" in pub
