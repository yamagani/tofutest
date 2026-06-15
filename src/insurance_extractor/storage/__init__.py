"""Job storage backends and their factory."""

from __future__ import annotations

from ..config import Settings
from .base import Job, JobStatus, JobStore
from .memory import MemoryStore

__all__ = ["Job", "JobStatus", "JobStore", "MemoryStore", "build_store"]


def build_store(settings: Settings) -> JobStore:
    if settings.store_backend == "memory":
        return MemoryStore()
    if settings.store_backend == "dynamo":
        from .dynamo import DynamoStore  # imported lazily so boto3 isn't required for memory

        return DynamoStore(settings)
    raise ValueError(f"Unknown store backend {settings.store_backend!r}")
