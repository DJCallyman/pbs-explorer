from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

from config import get_settings


class JSONFormatter(logging.Formatter):
    """Emit one JSON object per log line — suitable for log aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, default=str)


def setup_logging() -> None:
    settings = get_settings()

    root_logger = logging.getLogger()
    root_logger.setLevel(settings.logging.level)

    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(settings.logging.level)
        if settings.logging.json_output:
            handler.setFormatter(JSONFormatter())
        else:
            handler.setFormatter(logging.Formatter(settings.logging.format))
        root_logger.addHandler(handler)

    logging.getLogger("sync").setLevel(logging.INFO)

    # Reduce noise from HTTP libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
