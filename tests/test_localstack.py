"""Integration test against LocalStack (DynamoDB + S3).

Auto-skips unless LocalStack is reachable at IE_AWS_ENDPOINT_URL (default
http://localhost:4566). Run it with:

    docker compose up -d localstack
    IE_AWS_ENDPOINT_URL=http://localhost:4566 AWS_ACCESS_KEY_ID=test \
      AWS_SECRET_ACCESS_KEY=test pytest tests/test_localstack.py -v
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from insurance_extractor.config import Settings
from insurance_extractor.jobs import JobService
from insurance_extractor.storage import JobStatus, build_store

from .sample_doc import make_png_bytes

ENDPOINT = os.environ.get("IE_AWS_ENDPOINT_URL", "http://localhost:4566")
SCHEMA = json.loads(
    (Path(__file__).parent.parent / "examples" / "proof_of_insurance.schema.json").read_text()
)


def _localstack_up() -> bool:
    try:
        import requests

        return requests.get(f"{ENDPOINT}/_localstack/health", timeout=2).ok
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _localstack_up(), reason="LocalStack not running")


def _settings() -> Settings:
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
    return Settings(
        store_backend="dynamo",
        worker_inline=True,
        default_strategy="rule",
        aws_endpoint_url=ENDPOINT,
        aws_region="us-east-1",
        ddb_table="insurance_jobs_test",
        s3_bucket="insurance-documents-test",
        auto_create_resources=True,
    )


def test_dynamo_s3_round_trip():
    settings = _settings()
    store = build_store(settings)
    store.ensure()
    svc = JobService(store, settings)

    job = svc.submit(make_png_bytes(), "cert.png", SCHEMA)
    fetched = svc.get(job.job_id)

    assert fetched.status is JobStatus.SUCCEEDED
    assert fetched.result["data"]["policy_number"] == "NWM-4820-7731"
    # document persisted to S3 and re-readable
    assert store.get_document(fetched.document_key)[:4] == b"\x89PNG"
