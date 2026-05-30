"""Structured logging for the engine, using rich for human-readable output."""

from __future__ import annotations

import logging

from rich.logging import RichHandler

from vitiligo.config import get_settings

_CONFIGURED = False


def configure_logging(level: str | None = None) -> None:
    """Configure root logging with rich formatting. Safe to call multiple times."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    resolved_level = (level or get_settings().log_level).upper()

    logging.basicConfig(
        level=resolved_level,
        format="%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            RichHandler(
                rich_tracebacks=True,
                show_time=True,
                show_path=False,
                markup=False,
            )
        ],
    )

    # Quiet noisy third-party loggers by default.
    for noisy in ("httpx", "httpcore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger."""
    configure_logging()
    return logging.getLogger(name)
