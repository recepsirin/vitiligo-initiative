"""Configuration for the Vitiligo Initiative engine.

All settings are loaded from environment variables (optionally via a `.env`
file). See `.env.example` for the full set of supported variables.
"""

from __future__ import annotations

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
    return _settings
