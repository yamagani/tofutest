"""Typed exception hierarchy.

Each error carries an HTTP status so the API layer can translate any
ExtractionError into a consistent JSON error response without a big if/else.
"""

from __future__ import annotations


class ExtractionError(Exception):
    """Base class for all expected (client- or content-related) failures."""

    status_code: int = 400
    code: str = "extraction_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class UnsupportedDocumentError(ExtractionError):
    status_code = 415
    code = "unsupported_document"


class DocumentTooLargeError(ExtractionError):
    status_code = 413
    code = "document_too_large"


class TooManyPagesError(ExtractionError):
    status_code = 422
    code = "too_many_pages"


class SchemaError(ExtractionError):
    status_code = 422
    code = "invalid_schema"


class OcrError(ExtractionError):
    status_code = 500
    code = "ocr_failed"


class MapperUnavailableError(ExtractionError):
    """Raised when a requested mapper backend (e.g. Ollama) is not reachable."""

    status_code = 503
    code = "mapper_unavailable"


class JobNotFoundError(ExtractionError):
    status_code = 404
    code = "job_not_found"


class StorageError(ExtractionError):
    status_code = 502
    code = "storage_error"
