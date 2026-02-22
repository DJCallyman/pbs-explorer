from __future__ import annotations

import secrets
from typing import Generator

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from config import get_settings
from db.session import get_session

_api_key_header = APIKeyHeader(name="X-Admin-API-Key", auto_error=False)


def get_db() -> Generator[Session, None, None]:
    with get_session() as session:
        yield session


def verify_admin(api_key: str | None = Security(_api_key_header)) -> str:
    """Verify the admin API key from the ``X-Admin-API-Key`` header.

    Raises:
        HTTPException 401: If the key is missing.
        HTTPException 403: If the key does not match the configured value.
    """
    settings = get_settings()
    configured_key = settings.server.admin_api_key
    if not configured_key:
        # No key configured — admin endpoints are disabled for safety
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin API key not configured. Set PBS_EXPLORER_ADMIN_API_KEY.",
        )
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Admin-API-Key header",
        )
    if not secrets.compare_digest(api_key, configured_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin API key",
        )
    return api_key
