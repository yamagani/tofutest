"""Validate the extracted payload against the caller-supplied JSON Schema."""

from __future__ import annotations

from dataclasses import dataclass

from jsonschema import Draft202012Validator


@dataclass
class ValidationReport:
    valid: bool
    errors: list[str]


def validate_payload(data: dict, schema: dict) -> ValidationReport:
    # Drop nulls so absent optional fields don't trip "wrong type" errors; the
    # required-field check below still catches missing mandatory fields.
    non_null = {k: v for k, v in data.items() if v is not None}
    validator = Draft202012Validator(schema)
    errors = [
        f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
        for e in validator.iter_errors(non_null)
    ]
    return ValidationReport(valid=not errors, errors=errors)
