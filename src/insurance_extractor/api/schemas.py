"""Pydantic request/response models for the API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ExtractJsonRequest(BaseModel):
    filename: str = Field("upload.pdf", description="Original filename (used to detect PDF vs image)")
    content_base64: str = Field(..., description="Base64-encoded document bytes")
    schema_: dict[str, Any] = Field(..., alias="schema", description="JSON Schema object")
    options: dict[str, Any] = Field(default_factory=dict, description="{strategy}")

    model_config = {"populate_by_name": True}


class ErrorResponse(BaseModel):
    error: str = Field(..., description="Machine-readable error code")
    detail: str = Field(..., description="Human-readable message")
    request_id: str | None = None
