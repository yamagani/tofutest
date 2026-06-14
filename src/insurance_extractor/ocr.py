"""OCR layer: page image -> text lines with bounding boxes and confidence.

The engine is behind a small Protocol so an alternative backend (PaddleOCR,
docTR, a cloud OCR) can be dropped in without touching the pipeline. The default
is Tesseract, which runs well on CPU and ships easily.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pytesseract
from PIL import Image

from .config import Settings
from .errors import OcrError
from .preprocess import preprocess


@dataclass
class Line:
    text: str
    bbox: tuple[int, int, int, int]  # (x0, y0, x1, y1) in image pixels
    confidence: float  # 0..1


@dataclass
class OcrResult:
    page_index: int
    lines: list[Line]

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)


class OcrEngine(Protocol):
    name: str

    def run(self, img: Image.Image, page_index: int = 0, *, do_preprocess: bool = True) -> OcrResult:
        ...


class TesseractEngine:
    name = "tesseract"

    def __init__(self, settings: Settings):
        self._lang = settings.ocr_lang
        if settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    def run(self, img: Image.Image, page_index: int = 0, *, do_preprocess: bool = True) -> OcrResult:
        if do_preprocess:
            img = preprocess(img)
        try:
            data = pytesseract.image_to_data(
                img, lang=self._lang, output_type=pytesseract.Output.DICT
            )
        except pytesseract.TesseractError as exc:  # pragma: no cover - env dependent
            raise OcrError(f"Tesseract failed: {exc}") from exc
        except pytesseract.TesseractNotFoundError as exc:  # pragma: no cover
            raise OcrError(
                "Tesseract binary not found. Install it (e.g. `brew install tesseract`) "
                "or set IE_TESSERACT_CMD."
            ) from exc
        return OcrResult(page_index=page_index, lines=_group_lines(data))


def get_ocr_engine(settings: Settings) -> OcrEngine:
    """Factory for the configured OCR engine (only Tesseract today)."""
    return TesseractEngine(settings)


def _group_lines(data: dict) -> list[Line]:
    """Group Tesseract words sharing (block, paragraph, line) into one Line."""
    groups: dict[tuple, list[int]] = {}
    for i, word in enumerate(data["text"]):
        if not word.strip():
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        groups.setdefault(key, []).append(i)

    lines: list[Line] = []
    for idxs in groups.values():
        words = [data["text"][i] for i in idxs]
        confs = [float(data["conf"][i]) for i in idxs if float(data["conf"][i]) >= 0]
        x0 = min(data["left"][i] for i in idxs)
        y0 = min(data["top"][i] for i in idxs)
        x1 = max(data["left"][i] + data["width"][i] for i in idxs)
        y1 = max(data["top"][i] + data["height"][i] for i in idxs)
        conf = (sum(confs) / len(confs) / 100.0) if confs else 0.0
        lines.append(Line(text=" ".join(words), bbox=(x0, y0, x1, y1), confidence=round(conf, 3)))

    # Reading order: top-to-bottom, then left-to-right.
    lines.sort(key=lambda ln: (ln.bbox[1], ln.bbox[0]))
    return lines
