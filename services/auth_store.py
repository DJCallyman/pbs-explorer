from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from db.base import Base
from db.models import WebUser
from db.session import get_session, init_engine


USERS_PATH = Path(__file__).resolve().parent.parent / "data" / "auth" / "users.json"
PBKDF2_ITERATIONS = 390_000


@dataclass
class AuthUser:
    username: str
    role: str
    source: str


def _ensure_tables() -> None:
    init_engine()
    assert get_session is not None
    from db.session import _engine  # type: ignore

    Base.metadata.create_all(bind=_engine, tables=[WebUser.__table__])


def _load_json_seed() -> dict:
    if not USERS_PATH.exists():
        return {"users": []}
    with USERS_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _rename_legacy_file() -> None:
    if USERS_PATH.exists():
        USERS_PATH.rename(USERS_PATH.with_suffix(".json.migrated"))


def _migrate_legacy_json_if_needed() -> None:
    _ensure_tables()
    with get_session() as session:
        existing = session.execute(select(WebUser.username).limit(1)).first()
        if existing is not None:
            return
        payload = _load_json_seed()
        users = payload.get("users", [])
        if not users:
            return
        for record in users:
            if not isinstance(record, dict):
                continue
            username = str(record.get("username", "")).strip()
            if not username:
                continue
            session.merge(
                WebUser(
                    username=username,
                    role=str(record.get("role", "user") or "user"),
                    password_hash=str(record.get("password_hash", "")),
                    created_at=_parse_dt(str(record.get("created_at", ""))),
                    updated_at=_parse_dt(str(record.get("updated_at", ""))),
                )
            )
        session.commit()
    _rename_legacy_file()


def _hash_password(password: str, salt: bytes | None = None) -> str:
    actual_salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), actual_salt, PBKDF2_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS,
        base64.b64encode(actual_salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations_raw, salt_b64, digest_b64 = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected = base64.b64decode(digest_b64.encode("ascii"))
    except Exception:
        return False

    computed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(computed, expected)


def _parse_dt(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def list_users() -> list[dict]:
    _migrate_legacy_json_if_needed()
    with get_session() as session:
        rows = session.execute(select(WebUser).order_by(WebUser.username.asc())).scalars().all()
        return [
            {
                "username": row.username,
                "role": row.role,
                "created_at": row.created_at.isoformat() if row.created_at else "",
                "updated_at": row.updated_at.isoformat() if row.updated_at else "",
            }
            for row in rows
        ]


def has_users() -> bool:
    _migrate_legacy_json_if_needed()
    with get_session() as session:
        return session.execute(select(WebUser.username).limit(1)).first() is not None


def create_user(username: str, password: str, role: str = "user") -> None:
    _migrate_legacy_json_if_needed()
    username = username.strip()
    if not username:
        raise ValueError("Username is required")
    if role not in {"admin", "user"}:
        raise ValueError("Role must be admin or user")
    if len(password) < 10:
        raise ValueError("Password must be at least 10 characters")

    with get_session() as session:
        existing = session.execute(
            select(WebUser).where(WebUser.username.ilike(username))
        ).scalar_one_or_none()
        if existing:
            raise ValueError("User already exists")
        now = _utcnow()
        session.add(
            WebUser(
                username=username,
                role=role,
                password_hash=_hash_password(password),
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()


def update_user_password(username: str, password: str) -> None:
    _migrate_legacy_json_if_needed()
    if len(password) < 10:
        raise ValueError("Password must be at least 10 characters")

    with get_session() as session:
        user = session.execute(
            select(WebUser).where(WebUser.username.ilike(username.strip()))
        ).scalar_one_or_none()
        if not user:
            raise ValueError("User not found")
        user.password_hash = _hash_password(password)
        user.updated_at = _utcnow()
        session.commit()


def delete_user(username: str) -> None:
    _migrate_legacy_json_if_needed()
    with get_session() as session:
        user = session.execute(
            select(WebUser).where(WebUser.username.ilike(username.strip()))
        ).scalar_one_or_none()
        if not user:
            raise ValueError("User not found")
        session.delete(user)
        session.commit()


def verify_managed_user(username: str, password: str) -> AuthUser | None:
    _migrate_legacy_json_if_needed()
    with get_session() as session:
        user = session.execute(
            select(WebUser).where(WebUser.username.ilike(username.strip()))
        ).scalar_one_or_none()
        if not user:
            return None
        if _verify_password(password, str(user.password_hash or "")):
            return AuthUser(username=user.username, role=user.role, source="managed")
        return None


def verify_any_user(
    username: str,
    password: str,
    admin_username: str,
    admin_password: str,
) -> AuthUser | None:
    normalized_username = username.strip()
    if (
        admin_username
        and admin_password
        and normalized_username == admin_username
        and hmac.compare_digest(password, admin_password)
    ):
        return AuthUser(username=admin_username, role="admin", source="bootstrap")
    return verify_managed_user(username, password)
