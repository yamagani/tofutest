"""End-to-end test: synthetic certificate image -> schema-validated JSON.

Uses the rule mapper only (no LLM) so the test is fully offline and deterministic.
"""

from __future__ import annotations

import json
from pathlib import Path

from insurance_extractor import extract_document

from .sample_doc import make_png_bytes

SCHEMA = json.loads(
    (Path(__file__).parent.parent / "examples" / "proof_of_insurance.schema.json").read_text()
)


def _run():
    return extract_document(make_png_bytes(), "sample.png", SCHEMA, strategy="rule")


def test_required_fields_present_and_valid():
    result = _run()
    assert result.validation["valid"], result.validation["errors"]
    for req in SCHEMA["required"]:
        assert result.data.get(req), f"missing required field {req}"


def test_values_extracted_correctly():
    data = _run().data
    assert "ACME LOGISTICS" in data["insured_name"].upper()
    assert data["policy_number"] == "NWM-4820-7731"
    assert data["effective_date"] == "2026-03-01"  # coerced to ISO
    assert data["expiration_date"] == "2027-03-01"


def test_number_and_vin_coercion():
    data = _run().data
    assert data["liability_limit"] == 1000000.0
    assert data["vin"] == "1HGCM82633A004352"


def test_provenance_and_confidence_present():
    result = _run()
    assert result.confidence["policy_number"] > 0
    assert result.provenance["policy_number"] is not None
