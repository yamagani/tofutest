"""FastAPI application factory.

`create_app()` builds and configures the app; `app` is a module-level instance
used by uvicorn (`insurance_extractor.api:app`) and the Lambda handler.
"""

from __future__ import annotations

from fastapi import FastAPI

from ..config import Settings, get_settings
from ..observability import setup_logging
from . import middleware, routes


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(level=settings.log_level, json_logs=settings.json_logs)

    app = FastAPI(title=settings.api_title, version="0.1.0")
    middleware.register(app)
    app.include_router(routes.router)
    return app


app = create_app()
