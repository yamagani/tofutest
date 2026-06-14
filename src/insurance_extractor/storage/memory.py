"""In-memory JobStore for tests and zero-dependency local runs.

Thread-safe (the worker mutates jobs from a background thread) and returns
copies so callers never see a job mutated mid-read.
"""

from __future__ import annotations

import copy
import threading
from typing import Any, Optional

from ..errors import JobNotFoundError
from .base import Job, JobStore


class MemoryStore(JobStore):
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._docs: dict[str, bytes] = {}
        self._lock = threading.Lock()

    def ensure(self) -> None:  # nothing to create
        return None

    def put_document(self, job_id: str, data: bytes) -> str:
        key = f"documents/{job_id}"
        with self._lock:
            self._docs[key] = data
        return key

    def get_document(self, key: str) -> bytes:
        with self._lock:
            return self._docs[key]

    def create_job(self, job: Job) -> None:
        with self._lock:
            self._jobs[job.job_id] = copy.deepcopy(job)

    def update_job(self, job_id: str, **fields: Any) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFoundError(f"Job {job_id} not found")
            for k, v in fields.items():
                setattr(job, k, v)

    def get_job(self, job_id: str) -> Optional[Job]:
        with self._lock:
            job = self._jobs.get(job_id)
            return copy.deepcopy(job) if job else None
