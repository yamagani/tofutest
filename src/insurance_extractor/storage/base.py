"""Job model and the JobStore protocol.

A JobStore persists job metadata/results and the original document bytes. Two
implementations exist: an in-memory store (tests, zero-AWS) and a DynamoDB+S3
store (LocalStack locally, real AWS in prod).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional, Protocol


class JobStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


@dataclass
class Job:
    job_id: str
    status: JobStatus
    filename: str
    strategy: str
    created_at: str
    updated_at: str
    schema: dict[str, Any] = field(default_factory=dict)
    document_key: Optional[str] = None  # S3 object key for the original document
    result: Optional[dict[str, Any]] = None  # extraction output once SUCCEEDED
    error: Optional[str] = None  # message when FAILED

    def public_dict(self) -> dict[str, Any]:
        """The shape returned by GET /jobs/{id} (omits internal/raw fields)."""
        d = asdict(self)
        d["status"] = self.status.value
        d.pop("schema", None)
        d.pop("document_key", None)
        if self.status != JobStatus.SUCCEEDED:
            d.pop("result", None)
        if self.status != JobStatus.FAILED:
            d.pop("error", None)
        return d


class JobStore(Protocol):
    def ensure(self) -> None:
        """Create backing resources if missing (no-op when already present)."""
        ...

    def put_document(self, job_id: str, data: bytes) -> str:
        """Persist the original document; return its storage key."""
        ...

    def get_document(self, key: str) -> bytes:
        ...

    def create_job(self, job: Job) -> None:
        ...

    def update_job(self, job_id: str, **fields: Any) -> None:
        """Patch fields on a job (status/result/error/updated_at)."""
        ...

    def get_job(self, job_id: str) -> Optional[Job]:
        ...
