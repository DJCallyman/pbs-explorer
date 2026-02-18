from __future__ import annotations

import logging
import sys

from config import get_settings


def setup_logging() -> None:
    settings = get_settings()
    
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.logging.level)
    
    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(settings.logging.level)
        handler.setFormatter(logging.Formatter(settings.logging.format))
        root_logger.addHandler(handler)
    
    logging.getLogger("sync").setLevel(logging.INFO)
    
    # Reduce noise from HTTP libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
