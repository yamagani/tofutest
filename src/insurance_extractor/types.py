"""Shared data types used across mappers and the pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class Provenance:
    page: int
    text: str  # the OCR line the value was drawn from
    bbox: Optional[tuple[int, int, int, int]] = None


@dataclass
class FieldResult:
    value: Any  # raw value as found (pre-coercion); None if not found
    confidence: float  # 0..1
    provenance: Optional[Provenance] = None
