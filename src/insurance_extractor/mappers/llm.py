"""Local LLM mapper via Ollama (optional path).

Sends OCR text + the JSON Schema to a locally running Ollama model and asks for
a JSON object. Nothing leaves the machine. Raises MapperUnavailableError if
Ollama is not reachable so callers can fall back to rules.
"""

from __future__ import annotations

import json

import requests

from ..config import Settings
from ..errors import MapperUnavailableError
from ..observability import get_logger
from ..ocr import OcrResult
from ..types import FieldResult, Provenance

log = get_logger(__name__)

_SYSTEM = (
    "You extract structured data from insurance documents. "
    "You are given OCR text and a JSON Schema. Return ONLY a JSON object that "
    "matches the schema's properties. Use ONLY values present in the text. "
    "If a field is not present, set it to null. Never invent values. "
    "Return dates exactly as written in the document."
)


class LlmMapper:
    name = "llm"

    def __init__(self, settings: Settings):
        self._url = settings.ollama_url
        self._model = settings.ollama_model
        self._timeout = settings.ollama_timeout_s

    def is_available(self) -> bool:
        try:
            base = self._url.rsplit("/api/", 1)[0]
            requests.get(base + "/api/tags", timeout=2)
            return True
        except requests.RequestException:
            return False

    def map(self, schema: dict, ocr_results: list[OcrResult]) -> dict[str, FieldResult]:
        text = "\n".join(f"[p{r.page_index}] {r.text}" for r in ocr_results)
        prompt = (
            f"JSON Schema:\n{json.dumps(schema, indent=2)}\n\n"
            f"OCR text:\n{text}\n\nReturn the JSON object now."
        )
        payload = {
            "model": self._model,
            "format": "json",
            "stream": False,
            "options": {"temperature": 0},
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": prompt},
            ],
        }
        try:
            resp = requests.post(self._url, json=payload, timeout=self._timeout)
            resp.raise_for_status()
            content = resp.json()["message"]["content"]
            data = json.loads(content)
        except (requests.RequestException, KeyError, ValueError) as exc:
            raise MapperUnavailableError(f"Ollama request failed: {exc}") from exc

        return _attach_provenance(schema, data, ocr_results)


def _attach_provenance(schema: dict, data: dict, ocr_results: list[OcrResult]) -> dict[str, FieldResult]:
    flat_lines = [(r.page_index, ln) for r in ocr_results for ln in r.lines]
    out: dict[str, FieldResult] = {}
    for field_name in schema.get("properties", {}):
        value = data.get(field_name)
        if value is None:
            out[field_name] = FieldResult(None, 0.0, None)
            continue
        prov, conf = None, 0.6  # base confidence for an LLM-produced value
        for page, ln in flat_lines:
            if str(value).lower() in ln.text.lower():
                prov = Provenance(page, ln.text, ln.bbox)
                conf = max(conf, ln.confidence)
                break
        out[field_name] = FieldResult(value, round(conf, 3), prov)
    return out
