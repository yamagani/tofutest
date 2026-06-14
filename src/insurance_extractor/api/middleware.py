"""Request middleware and exception handlers."""

from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..errors import ExtractionError
from ..observability import Timer, get_logger, request_id_var

log = get_logger("insurance_extractor.api")


def register(app: FastAPI) -> None:
    @app.middleware("http")
    async def _observe(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        token = request_id_var.set(request_id)
        try:
            with Timer() as t:
                response = await call_next(request)
            log.info(
                "request",
                extra={"extra": {
                    "method": request.method, "path": request.url.path,
                    "status": response.status_code, "duration_ms": t.ms,
                }},
            )
            response.headers["x-request-id"] = request_id
            return response
        finally:
            request_id_var.reset(token)

    @app.exception_handler(ExtractionError)
    async def _handle_extraction_error(request: Request, exc: ExtractionError):
        log.warning("extraction error",
                    extra={"extra": {"code": exc.code, "detail": exc.message}})
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.code, "detail": exc.message, "request_id": request_id_var.get()},
        )
