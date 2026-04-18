from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from ignition.core.paths import log_dir

_configured = False


def _log_file_for_today() -> Path:
    stamp = datetime.now(UTC).strftime("%Y-%m-%d")
    return log_dir() / f"ignition-{stamp}.jsonl"


def configure_logging() -> None:
    global _configured
    if _configured:
        return

    handler = logging.FileHandler(_log_file_for_today(), encoding="utf-8")
    handler.setLevel(logging.INFO)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str | None = None) -> Any:
    configure_logging()
    return structlog.get_logger(name) if name else structlog.get_logger()
