"""Async job API via TestClient (memory store, inline worker)."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from insurance_extractor import get_settings
from insurance_extractor.api import create_app
from insurance_extractor.jobs import get_job_service

from .sample_doc import make_png_bytes

SCHEMA = json.loads(
    (Path(__file__).parent.parent / "examples" / "proof_of_insurance.schema.json").read_text()
)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("IE_STORE_BACKEND", "memory")
    monkeypatch.setenv("IE_WORKER_INLINE", "true")
    monkeypatch.setenv("IE_DEFAULT_STRATEGY", "rule")
    get_settings.cache_clear()
    get_job_service.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()
    get_job_service.cache_clear()


def test_submit_and_poll(client):
    body = {
        "filename": "cert.png",
        "content_base64": base64.b64encode(make_png_bytes()).decode(),
        "schema": SCHEMA,
        "options": {"strategy": "rule"},
    }
    sub = client.post("/jobs-json", json=body)
    assert sub.status_code == 202, sub.text
    job_id = sub.json()["job_id"]

    got = client.get(f"/jobs/{job_id}")
    assert got.status_code == 200, got.text
    out = got.json()
    assert out["status"] == "SUCCEEDED"
    assert out["result"]["data"]["policy_number"] == "NWM-4820-7731"


def test_submit_multipart(client):
    r = client.post(
        "/jobs",
        files={"file": ("cert.png", make_png_bytes(), "image/png")},
        data={"schema": json.dumps(SCHEMA), "options": json.dumps({"strategy": "rule"})},
    )
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]
    assert client.get(f"/jobs/{job_id}").json()["status"] == "SUCCEEDED"


def test_unknown_job_404(client):
    r = client.get("/jobs/nope")
    assert r.status_code == 404
    assert r.json()["error"] == "job_not_found"
