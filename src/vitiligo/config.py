"""Configuration for the Vitiligo Initiative engine.

All settings are loaded from environment variables (optionally via a `.env`
file). See `.env.example` for the full set of supported variables.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # NCBI E-utilities (PubMed). API key is optional but recommended.
    ncbi_api_key: str | None = Field(default=None, alias="NCBI_API_KEY")
    ncbi_tool: str = Field(default="vitiligo-initiative", alias="NCBI_TOOL")
    ncbi_email: str | None = Field(default=None, alias="NCBI_EMAIL")

    # Storage
    db_path: Path = Field(default=Path("data/vitiligo.db"), alias="VITILIGO_DB_PATH")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # LLM (reasoning layer)
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-4-5", alias="ANTHROPIC_MODEL")

    # Web UI / deployment
    web_host: str = Field(default="127.0.0.1", alias="VITILIGO_WEB_HOST")
    web_port: int = Field(default=8765, alias="VITILIGO_WEB_PORT")
    rate_limit_post_per_minute: int = Field(
        default=30,
        alias="VITILIGO_RATE_LIMIT_POST_PER_MINUTE",
        description="Max POST /api/* requests per IP per minute (0 disables).",
    )
    prewarm_embeddings: bool = Field(
        default=True,
        alias="VITILIGO_PREWARM_EMBEDDINGS",
        description="Load the embedding model at startup (recommended for production).",
    )
    fastembed_cache_path: Path | None = Field(
        default=None,
        alias="FASTEMBED_CACHE_PATH",
        description="Optional cache directory for fastembed ONNX models.",
    )

    @property
    def effective_web_host(self) -> str:
        """Bind host; default to all interfaces when PORT is set (Fly/Render)."""
        if os.environ.get("PORT") and self.web_host == "127.0.0.1":
            return "0.0.0.0"
        return self.web_host

    @property
    def effective_web_port(self) -> int:
        """Listen port; Fly.io and Render inject PORT."""
        if port := os.environ.get("PORT"):
            return int(port)
        return self.web_port

    def apply_runtime_env(self) -> None:
        """Apply deployment-related environment overrides."""
        if self.fastembed_cache_path is not None:
            cache = self.fastembed_cache_path
            if not cache.is_absolute():
                cache = PROJECT_ROOT / cache
            cache.mkdir(parents=True, exist_ok=True)
            os.environ.setdefault("FASTEMBED_CACHE_PATH", str(cache))

    @property
    def resolved_db_path(self) -> Path:
        """Return absolute path to the SQLite database, ensuring parent exists."""
        path = self.db_path
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def db_url(self) -> str:
        """SQLAlchemy URL for the SQLite database."""
        return f"sqlite:///{self.resolved_db_path}"


_settings: Settings | None = None


def get_settings() -> Settings:
    """Lazily build a singleton Settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.apply_runtime_env()
    return _settings
