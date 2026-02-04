from __future__ import annotations

import logging

from config import get_settings


def setup_logging() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.logging.level, format=settings.logging.format)
    
    # Reduce noise from HTTP libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
