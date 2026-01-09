"""Centralized logging configuration for LegalRAG."""

from __future__ import annotations

import json
import logging
import logging.config
from pathlib import Path
from typing import Any, Dict

LOG_DIR = Path("logs")
ERROR_LOG = LOG_DIR / "errors.log"
APP_LOG = LOG_DIR / "app.log"


class JsonFormatter(logging.Formatter):
    """Simple JSON formatter for structured logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "time": self.formatTime(record, self.datefmt),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def ensure_log_dir() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def configure_logging(level: str = "INFO") -> None:
    ensure_log_dir()

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": JsonFormatter,
                },
                "console": {
                    "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "console",
                    "level": level,
                },
                "app_file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "formatter": "json",
                    "filename": str(APP_LOG),
                    "maxBytes": 100 * 1024 * 1024,
                    "backupCount": 10,
                    "encoding": "utf-8",
                    "level": level,
                },
                "error_file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "formatter": "json",
                    "filename": str(ERROR_LOG),
                    "maxBytes": 100 * 1024 * 1024,
                    "backupCount": 10,
                    "encoding": "utf-8",
                    "level": "ERROR",
                },
            },
            "root": {
                "handlers": ["console", "app_file", "error_file"],
                "level": level,
            },
        }
    )

