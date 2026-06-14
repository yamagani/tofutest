"""Centralized, environment-driven configuration.

All tunables live here and are overridable via ``IE_*`` environment variables
(or a local ``.env`` file). This keeps the rest of the code free of magic
numbers and makes the same image behave correctly in local, Docker, and Lambda
environments just by changing env vars.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

Strategy = Literal["rule", "llm", "auto"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="IE_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- OCR ---
    ocr_lang: str = "eng"
    pdf_dpi: int = 200  # below ~150 DPI OCR accuracy drops sharply
    tesseract_cmd: str | None = None  # explicit path to the tesseract binary, if needed

    # --- Mapping ---
    default_strategy: Strategy = "rule"
    ollama_url: str = "http://localhost:11434/api/chat"
    ollama_model: str = "qwen2.5:3b"
    ollama_timeout_s: int = 120

    # --- Input guards ---
    max_upload_mb: int = 15
    max_pages: int = 10

    # --- App / observability ---
    api_title: str = "Insurance Document Extractor"
    log_level: str = "INFO"
    json_logs: bool = True

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Process-wide settings singleton (cached so env is read once)."""
    return Settings()
