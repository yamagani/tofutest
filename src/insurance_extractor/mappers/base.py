"""Mapper protocol: turn OCR results into per-field extraction results."""

from __future__ import annotations

from typing import Protocol

from ..ocr import OcrResult
from ..types import FieldResult


class Mapper(Protocol):
    name: str

    def map(self, schema: dict, ocr_results: list[OcrResult]) -> dict[str, FieldResult]:
        """Return one FieldResult per property declared in the schema."""
        ...
