from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from db.base import Base
from db.models import WebSession
from db.session import get_session as get_db_session, init_engine


SESSIONS_PATH = Path(__file__).resolve().parent.parent / "data" / "auth" / "sessions.json"
SESSION_TTL_DAYS = 30
MAX_ACTIVE_SESSIONS_PER_USER = 5


@dataclass
class AuthSession:
    session_id: str
    username: str
    role: str
    source: str
    created_at: str
    last_seen_at: str
    expires_at: str


def _ensure_tables() -> None:
    init_engine()
    from db.session import _engine  # type: ignore

    Base.metadata.create_all(bind=_engine, tables=[WebSession.__table__])


def _load_json_seed() -> dict:
    if not SESSIONS_PATH.exists():
        return {"sessions": []}
    with SESSIONS_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _rename_legacy_file() -> None:
    if SESSIONS_PATH.exists():
        SESSIONS_PATH.rename(SESSIONS_PATH.with_suffix(".json.migrated"))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_iso(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _to_auth_session(row: WebSession) -> AuthSession:
    return AuthSession(
        session_id=row.session_id,
        username=row.username,
        role=row.role,
        source=row.source,
        created_at=row.created_at.isoformat() if row.created_at else "",
        last_seen_at=row.last_seen_at.isoformat() if row.last_seen_at else "",
        expires_at=row.expires_at.isoformat() if row.expires_at else "",
    )


def _migrate_legacy_json_if_needed() -> None:
    _ensure_tables()
    with get_db_session() as session:
        existing = session.execute(select(WebSession.session_id).limit(1)).first()
        if existing is not None:
            return
        payload = _load_json_seed()
        rows = payload.get("sessions", [])
        if not rows:
            return
        for record in rows:
            if not isinstance(record, dict):
                continue
            session.merge(
                WebSession(
                    session_id=str(record.get("session_id", "")),
                    username=str(record.get("username", "")),
                    role=str(record.get("role", "user")),
                    source=str(record.get("source", "managed")),
                    created_at=_parse_iso(str(record.get("created_at", ""))),
                    last_seen_at=_parse_iso(str(record.get("last_seen_at", ""))),
                    expires_at=_parse_iso(str(record.get("expires_at", ""))),
                    revoked_at=_parse_iso(str(record.get("revoked_at", ""))),
                )
            )
        session.commit()
    _rename_legacy_file()


def _active_row(row: WebSession) -> bool:
    return bool(not row.revoked_at and row.expires_at and row.expires_at > _utcnow())


def create_session(username: str, role: str, source: str) -> AuthSession:
    _migrate_legacy_json_if_needed()
    now = _utcnow()
    expires_at = now + timedelta(days=SESSION_TTL_DAYS)
    row = WebSession(
        session_id=secrets.token_urlsafe(32),
        username=username,
        role=role,
        source=source,
        created_at=now,
        last_seen_at=now,
        expires_at=expires_at,
        revoked_at=None,
    )
    with get_db_session() as session:
        session.add(row)
        session.commit()
        return _to_auth_session(row)


def get_session(session_id: str, touch: bool = True) -> AuthSession | None:
    _migrate_legacy_json_if_needed()
    with get_db_session() as session:
        row = session.execute(
            select(WebSession).where(WebSession.session_id == session_id)
        ).scalar_one_or_none()
        if not row:
            return None
        if row.expires_at and row.expires_at <= _utcnow() and not row.revoked_at:
            row.revoked_at = _utcnow()
            session.commit()
            return None
        if not _active_row(row):
            return None
        if touch:
            row.last_seen_at = _utcnow()
            session.commit()
        return _to_auth_session(row)


def revoke_session(session_id: str) -> bool:
    _migrate_legacy_json_if_needed()
    with get_db_session() as session:
        row = session.execute(
            select(WebSession).where(WebSession.session_id == session_id)
        ).scalar_one_or_none()
        if not row or row.revoked_at:
            return False
        row.revoked_at = _utcnow()
        session.commit()
        return True


def revoke_sessions_for_user(username: str) -> int:
    _migrate_legacy_json_if_needed()
    with get_db_session() as session:
        rows = session.execute(
            select(WebSession).where(WebSession.username.ilike(username.strip()))
        ).scalars().all()
        now = _utcnow()
        count = 0
        for row in rows:
            if _active_row(row):
                row.revoked_at = now
                count += 1
        if count:
            session.commit()
        return count


def list_active_sessions() -> list[dict]:
    _migrate_legacy_json_if_needed()
    with get_db_session() as session:
        rows = session.execute(select(WebSession).order_by(WebSession.username.asc())).scalars().all()
        now = _utcnow()
        sessions = []
        changed = False
        grouped_active_rows: dict[str, list[WebSession]] = {}
        for row in rows:
            if row.expires_at and row.expires_at <= now and not row.revoked_at:
                row.revoked_at = now
                changed = True
                continue
            if not _active_row(row):
                continue
            grouped_active_rows.setdefault(row.username, []).append(row)

        for username, active_rows in grouped_active_rows.items():
            active_rows.sort(
                key=lambda active_row: (
                    active_row.last_seen_at or datetime.min,
                    active_row.created_at or datetime.min,
                ),
                reverse=True,
            )
            for stale_row in active_rows[MAX_ACTIVE_SESSIONS_PER_USER:]:
                stale_row.revoked_at = now
                changed = True
            for row in active_rows[:MAX_ACTIVE_SESSIONS_PER_USER]:
                sessions.append(
                    {
                        "session_id": row.session_id,
                        "username": row.username,
                        "role": row.role,
                        "source": row.source,
                        "created_at": row.created_at.isoformat() if row.created_at else "",
                        "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else "",
                        "expires_at": row.expires_at.isoformat() if row.expires_at else "",
                    }
                )

        if changed:
            session.commit()
        return sessions


def count_active_sessions_by_username() -> dict[str, int]:
    counts: dict[str, int] = {}
    for session in list_active_sessions():
        key = session["username"]
        counts[key] = counts.get(key, 0) + 1
    return counts
