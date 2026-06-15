"""Turn an uploaded file (PDF/PNG/JPG) into a list of page images.

If a PDF already carries a digital text layer, we surface it so the pipeline can
skip OCR for that page (faster and more accurate than OCR-ing born-digital PDFs).
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image, UnidentifiedImageError

from .errors import TooManyPagesError, UnsupportedDocumentError

DEFAULT_DPI = 200


@dataclass
class Page:
    index: int  # 0-based page number
    image: Image.Image
    text_layer: str = ""  # digital text extracted from a PDF, if any


@dataclass
class Document:
    source_name: str
    pages: list[Page] = field(default_factory=list)


def _pixmap_to_pil(pix: "fitz.Pixmap") -> Image.Image:
    mode = "RGBA" if pix.alpha else "RGB"
    return Image.frombytes(mode, (pix.width, pix.height), pix.samples).convert("RGB")


def load_document(
    data: bytes,
    source_name: str,
    *,
    dpi: int = DEFAULT_DPI,
    max_pages: int | None = None,
) -> Document:
    """Load raw bytes into a Document of page images.

    Detects PDF vs image by content/extension. Raises UnsupportedDocumentError
    for anything we can't open, and TooManyPagesError if a PDF exceeds max_pages.
    """
    if not data:
        raise UnsupportedDocumentError("Empty document")

    suffix = Path(source_name).suffix.lower()
    is_pdf = suffix == ".pdf" or data[:5] == b"%PDF-"

    if is_pdf:
        return _load_pdf(data, source_name, dpi=dpi, max_pages=max_pages)
    return _load_image(data, source_name)


def _load_pdf(data: bytes, source_name: str, *, dpi: int, max_pages: int | None) -> Document:
    doc = Document(source_name=source_name)
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    try:
        pdf = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 - PyMuPDF raises a variety of types
        raise UnsupportedDocumentError(f"Could not open PDF: {exc}") from exc
    with pdf:
        if max_pages is not None and pdf.page_count > max_pages:
            raise TooManyPagesError(
                f"Document has {pdf.page_count} pages; limit is {max_pages}"
            )
        for i, page in enumerate(pdf):
            pix = page.get_pixmap(matrix=matrix)
            doc.pages.append(
                Page(index=i, image=_pixmap_to_pil(pix), text_layer=page.get_text("text") or "")
            )
    return doc


def _load_image(data: bytes, source_name: str) -> Document:
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
    except UnidentifiedImageError as exc:
        raise UnsupportedDocumentError(
            f"Unsupported file type for {source_name!r}; expected PDF/PNG/JPG"
        ) from exc
    return Document(source_name=source_name, pages=[Page(index=0, image=img)])


def load_path(path: str | Path, **kwargs) -> Document:
    p = Path(path)
    return load_document(p.read_bytes(), p.name, **kwargs)
