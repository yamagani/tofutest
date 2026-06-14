"""Mapper strategies and the factory that builds them.

Strategies:
  rule  - deterministic label-proximity matching (offline, no model)
  llm   - local Ollama model only
  auto  - rules first; if required fields remain empty and Ollama is reachable,
          fill the gaps with the LLM (falls back silently if Ollama is down)
"""

from __future__ import annotations

from ..config import Settings
from ..observability import get_logger
from ..ocr import OcrResult
from ..types import FieldResult
from .base import Mapper
from .llm import LlmMapper
from .rule import RuleMapper

log = get_logger(__name__)

__all__ = ["Mapper", "RuleMapper", "LlmMapper", "AutoMapper", "build_mapper"]


class AutoMapper:
    """Rule mapper, with the LLM filling any missing *required* fields."""

    name = "auto"

    def __init__(self, rule: RuleMapper, llm: LlmMapper):
        self._rule = rule
        self._llm = llm

    def map(self, schema: dict, ocr_results: list[OcrResult]) -> dict[str, FieldResult]:
        fields = self._rule.map(schema, ocr_results)

        missing = [
            r for r in schema.get("required", [])
            if fields.get(r) is None or fields[r].value is None
        ]
        if not missing:
            return fields

        if not self._llm.is_available():
            log.info("auto: rules left fields unfilled but Ollama unavailable; skipping LLM",
                     extra={"extra": {"missing": missing}})
            return fields

        try:
            llm_fields = self._llm.map(schema, ocr_results)
        except Exception as exc:  # noqa: BLE001 - never let the LLM path break extraction
            log.warning("auto: LLM mapping failed; keeping rule results",
                        extra={"extra": {"error": str(exc)}})
            return fields

        for name, fr in llm_fields.items():
            if (fields.get(name) is None or fields[name].value is None) and fr.value is not None:
                fields[name] = fr
        return fields


def build_mapper(strategy: str, settings: Settings) -> Mapper:
    if strategy == "rule":
        return RuleMapper()
    if strategy == "llm":
        return LlmMapper(settings)
    if strategy == "auto":
        return AutoMapper(RuleMapper(), LlmMapper(settings))
    raise ValueError(f"Unknown strategy {strategy!r}; expected rule|llm|auto")
