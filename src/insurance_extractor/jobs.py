"""Async job orchestration.

submit() persists the document and a PENDING job, then hands processing to a
background thread pool (so slow ingestion never blocks the request). The worker
runs the extraction pipeline and writes the result back to the store. Clients
poll get() by job_id for the outcome.

For prod this runs in a long-running container (ECS/App Runner) where background
threads survive past the response — unlike Lambda, which freezes after replying.
"""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Optional

from .config import Settings, get_settings
from .errors import ExtractionError
from .observability import get_logger, request_id_var
from .pipeline import extract_document
from .storage import Job, JobStatus, JobStore, build_store

log = get_logger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobService:
    def __init__(self, store: JobStore, settings: Settings):
        self._store = store
        self._settings = settings
        self._inline = settings.worker_inline
        self._executor = (
            None if self._inline else ThreadPoolExecutor(max_workers=settings.worker_concurrency)
        )

    def submit(
        self, data: bytes, filename: str, schema: dict, strategy: Optional[str] = None
    ) -> Job:
        job_id = uuid.uuid4().hex
        key = self._store.put_document(job_id, data)
        now = _now()
        job = Job(
            job_id=job_id,
            status=JobStatus.PENDING,
            filename=filename,
            strategy=strategy or self._settings.default_strategy,
            created_at=now,
            updated_at=now,
            schema=schema,
            document_key=key,
        )
        self._store.create_job(job)
        log.info("job submitted", extra={"extra": {"job_id": job_id, "filename": filename}})

        if self._inline:
            self._process(job_id)
        else:
            rid = request_id_var.get()
            self._executor.submit(self._process, job_id, rid)
        return self._store.get_job(job_id)

    def get(self, job_id: str) -> Optional[Job]:
        return self._store.get_job(job_id)

    def _process(self, job_id: str, request_id: str | None = None) -> None:
        if request_id:  # carry the submitting request's id into worker logs
            request_id_var.set(request_id)
        job = self._store.get_job(job_id)
        if job is None:
            log.warning("worker: job vanished", extra={"extra": {"job_id": job_id}})
            return

        self._store.update_job(job_id, status=JobStatus.PROCESSING, updated_at=_now())
        try:
            data = self._store.get_document(job.document_key)
            result = extract_document(
                data, job.filename, job.schema, strategy=job.strategy, settings=self._settings
            ).to_dict()
            self._store.update_job(
                job_id, status=JobStatus.SUCCEEDED, result=result, updated_at=_now()
            )
            log.info("job succeeded", extra={"extra": {"job_id": job_id}})
        except ExtractionError as exc:
            self._fail(job_id, f"{exc.code}: {exc.message}")
        except Exception as exc:  # noqa: BLE001 - worker must never crash silently
            log.exception("job crashed", extra={"extra": {"job_id": job_id}})
            self._fail(job_id, f"internal_error: {exc}")

    def _fail(self, job_id: str, message: str) -> None:
        self._store.update_job(
            job_id, status=JobStatus.FAILED, error=message, updated_at=_now()
        )
        log.warning("job failed", extra={"extra": {"job_id": job_id, "error": message}})


@lru_cache
def get_job_service() -> JobService:
    """Process-wide JobService singleton; bootstraps storage on first use."""
    settings = get_settings()
    store = build_store(settings)
    store.ensure()
    return JobService(store, settings)
