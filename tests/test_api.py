"""API tests via FastAPI TestClient (rule strategy — fully offline)."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from insurance_extractor.api import create_app

from .sample_doc import make_png_bytes

SCHEMA = json.loads(
    (Path(__file__).parent.parent / "examples" / "proof_of_insurance.schema.json").read_text()
)


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert r.headers.get("x-request-id")  # middleware stamps a request id


def test_extract_json_happy_path(client):
    body = {
        "filename": "cert.png",
        "content_base64": base64.b64encode(make_png_bytes()).decode(),
        "schema": SCHEMA,
        "options": {"strategy": "rule"},
    }
    r = client.post("/extract-json", json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["validation"]["valid"]
    assert out["data"]["policy_number"] == "NWM-4820-7731"
    assert out["engine"] == "rule"


def test_extract_multipart(client):
    r = client.post(
        "/extract",
        files={"file": ("cert.png", make_png_bytes(), "image/png")},
        data={"schema": json.dumps(SCHEMA), "options": json.dumps({"strategy": "rule"})},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["insured_name"].upper().startswith("ACME")


def test_bad_base64_returns_422(client):
    body = {"content_base64": "!!!not base64!!!", "schema": SCHEMA}
    r = client.post("/extract-json", json=body)
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_schema"


def test_unsupported_document_returns_415(client):
    body = {
        "filename": "note.txt",
        "content_base64": base64.b64encode(b"just some text, not an image").decode(),
        "schema": SCHEMA,
    }
    r = client.post("/extract-json", json=body)
    assert r.status_code == 415
    assert r.json()["error"] == "unsupported_document"
