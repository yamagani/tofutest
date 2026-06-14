"""Label-proximity rule mapper (no LLM required).

Given a JSON Schema and OCR lines, find each field's value by locating its label
on the page and reading the adjacent value. This is the deterministic fast-path;
it handles standardized forms well and works fully offline with zero models.
"""

from __future__ import annotations

import re

from ..ocr import Line, OcrResult
from ..types import FieldResult, Provenance

# Built-in label synonyms for common proof-of-insurance fields. Keys are matched
# as substrings of the schema field name (snake_case).
_SYNONYMS: dict[str, list[str]] = {
    "insured": ["insured", "name of insured", "policyholder", "named insured"],
    "carrier": ["carrier", "insurer", "insurance company", "company", "underwriter"],
    "policy": ["policy number", "policy no", "policy #", "policy"],
    "effective": ["effective date", "effective", "policy effective", "from"],
    "expiration": ["expiration date", "expiration", "expires", "expiry", "to"],
    "coverage": ["coverage", "coverage type", "type of insurance", "type of coverage"],
    "liability": ["liability limit", "each occurrence", "limit", "liability"],
    "vin": ["vin", "vehicle identification number", "vehicle id"],
    "premium": ["premium", "total premium"],
    "agent": ["agent", "producer", "broker"],
}

_DATE_RE = re.compile(
    r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}"
    r"|[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{4})\b"
)
_MONEY_RE = re.compile(r"\$?\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?\b")
_VIN_RE = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")


class RuleMapper:
    name = "rule"

    def map(self, schema: dict, ocr_results: list[OcrResult]) -> dict[str, FieldResult]:
        props: dict = schema.get("properties", {})
        all_lines: list[tuple[int, Line]] = [
            (res.page_index, ln) for res in ocr_results for ln in res.lines
        ]

        out = {name: _map_one(name, prop, all_lines) for name, prop in props.items()}

        # VIN is distinctive enough to find by pattern alone if the label search failed.
        for name, prop in props.items():
            if out[name].value is None and "vin" in name.lower():
                for page, ln in all_lines:
                    m = _VIN_RE.search(ln.text)
                    if m:
                        out[name] = FieldResult(
                            m.group(0), ln.confidence, Provenance(page, ln.text, ln.bbox)
                        )
                        break
        return out


def _labels_for(field_name: str, prop: dict) -> list[str]:
    """Candidate labels: synonyms, the humanized name, and description words."""
    labels: list[str] = []
    lname = field_name.lower()
    for key, syns in _SYNONYMS.items():
        if key in lname:
            labels.extend(syns)
    labels.append(field_name.replace("_", " "))
    desc = (prop.get("description") or "").lower()
    if desc:
        labels.append(desc)
    # Longest labels first so "policy number" wins over "policy".
    return sorted(set(labels), key=len, reverse=True)


def _value_after_label(line_text: str, label: str) -> str | None:
    """Return the text following the label on the same line, if present."""
    m = re.search(re.escape(label) + r"\s*[:\-#]?\s*(.+)", line_text, re.IGNORECASE)
    if m:
        return m.group(1).strip() or None
    return None


def _typed_extract(prop: dict, text: str) -> str | None:
    """Pull a value out of free text according to the field's JSON type."""
    ptype = prop.get("type")
    fmt = prop.get("format")
    if fmt == "date" or (ptype == "string" and _DATE_RE.search(text)):
        m = _DATE_RE.search(text)
        if m:
            return m.group(0)
    if ptype in ("number", "integer"):
        m = _MONEY_RE.search(text)
        if m:
            return m.group(0)
    return None


def _map_one(field_name: str, prop: dict, all_lines: list[tuple[int, Line]]) -> FieldResult:
    for label in _labels_for(field_name, prop):
        for i, (page, ln) in enumerate(all_lines):
            if label.lower() not in ln.text.lower():
                continue
            # 1) value on the same line, after the label
            same = _value_after_label(ln.text, label)
            if same:
                typed = _typed_extract(prop, same) or same
                return FieldResult(typed, ln.confidence, Provenance(page, ln.text, ln.bbox))
            # 2) value on the next line (label-above layout)
            if i + 1 < len(all_lines):
                nxt_page, nxt = all_lines[i + 1]
                typed = _typed_extract(prop, nxt.text) or nxt.text.strip()
                if typed:
                    return FieldResult(
                        typed, nxt.confidence, Provenance(nxt_page, nxt.text, nxt.bbox)
                    )
    return FieldResult(None, 0.0, None)
