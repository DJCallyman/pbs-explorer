from __future__ import annotations

import logging

from config import get_settings


def setup_logging() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.logging.level, format=settings.logging.format)
