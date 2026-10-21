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

    # SEC EDGAR full-text search (`vitiligo discover watch`). SEC requires a
    # declared contact, e.g. "Jane Doe jane@example.org"; unset skips SEC.
    sec_user_agent: str | None = Field(default=None, alias="SEC_USER_AGENT")

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
    trusted_proxy_hops: int = Field(
        default=0,
        alias="VITILIGO_TRUSTED_PROXY_HOPS",
        description=(
            "Reverse proxies in front of the app. 0 keys rate limits by the TCP peer; "
            "N reads the N-th X-Forwarded-For entry from the right."
        ),
    )
    llm_requests_per_minute: int = Field(
        default=0,
        alias="VITILIGO_LLM_REQUESTS_PER_MINUTE",
        description="Ask/Hypothesize calls per minute across ALL clients (0 disables).",
    )
    llm_daily_token_budget: int = Field(
        default=0,
        alias="VITILIGO_LLM_DAILY_TOKEN_BUDGET",
        description="Ask/Hypothesize input+output tokens per rolling 24 h, all clients (0 disables).",
    )
    state_db_path: Path | None = Field(
        default=None,
        alias="VITILIGO_STATE_DB_PATH",
        description="SQLite file for runtime state (LLM budget); default: next to the corpus DB.",
    )
    ledger_path: Path | None = Field(
        default=None,
        alias="VITILIGO_LEDGER_PATH",
        description="Discovery-loop ledger (SQLite); default: next to the corpus DB.",
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
        """Bind host; default to all interfaces when PORT is set (container hosts)."""
        if os.environ.get("PORT") and self.web_host == "127.0.0.1":
            return "0.0.0.0"
        return self.web_host

    @property
    def effective_web_port(self) -> int:
        """Listen port; Render and similar hosts inject PORT."""
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
    def resolved_state_db_path(self) -> Path:
        """Runtime-state SQLite file; kept separate so writes never touch the corpus DB."""
        if self.state_db_path is None:
            return self.resolved_db_path.parent / "vitiligo-state.db"
        path = self.state_db_path
        return path if path.is_absolute() else PROJECT_ROOT / path

    @property
    def resolved_ledger_path(self) -> Path:
        """Discovery ledger file; separate from the corpus so it survives rebuilds."""
        if self.ledger_path is None:
            return self.resolved_db_path.parent / "discovery-ledger.db"
        path = self.ledger_path
        return path if path.is_absolute() else PROJECT_ROOT / path

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
