"""Coerce raw extracted strings into the types the JSON Schema expects.

The mappers return values roughly as written on the page; here we normalize
dates to ISO (YYYY-MM-DD) and money/number strings to floats. We never trust a
model to format these correctly.
"""

from __future__ import annotations

import re
from typing import Any

import dateparser


def coerce_value(value: Any, prop: dict) -> Any:
    if value is None:
        return None
    ptype = prop.get("type")
    fmt = prop.get("format")

    if fmt == "date" or (ptype == "string" and _looks_like_date(value)):
        iso = _to_iso_date(value)
        if iso:
            return iso

    if ptype in ("number", "integer"):
        num = _to_number(value)
        if num is not None:
            return int(num) if ptype == "integer" else num

    if ptype == "string":
        return str(value).strip()

    return value


def _looks_like_date(value: Any) -> bool:
    return bool(re.search(r"\d{1,2}[/-]\d{1,2}|\d{4}|[A-Za-z]{3,9}\s+\d", str(value)))


def _to_iso_date(value: Any) -> str | None:
    dt = dateparser.parse(str(value), settings={"DATE_ORDER": "MDY"})
    return dt.date().isoformat() if dt else None


def _to_number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"[^\d.]", "", str(value))
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def coerce_all(values: dict[str, Any], schema: dict) -> dict[str, Any]:
    props = schema.get("properties", {})
    return {k: coerce_value(v, props.get(k, {})) for k, v in values.items()}
