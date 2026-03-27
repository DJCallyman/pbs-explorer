from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

from db.base import Base
from db.models import SavedReport
from db.session import get_session, init_engine


def manifest_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "saved_reports" / "manifest.json"


def _ensure_tables() -> None:
    init_engine()
    from db.session import _engine  # type: ignore

    Base.metadata.create_all(bind=_engine, tables=[SavedReport.__table__])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _load_json_seed() -> dict[str, Any]:
    path = manifest_path()
    if not path.exists():
        return {"reports": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _rename_legacy_file() -> None:
    path = manifest_path()
    if path.exists():
        path.rename(path.with_suffix(".json.migrated"))


def _normalise_report(report: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(report)
    owner = str(normalized.get("owner") or "").strip()
    shared_with = normalized.get("shared_with") or []
    if not isinstance(shared_with, list):
        shared_with = []
    normalized["owner"] = owner
    normalized["shared_with"] = sorted(
        {
            str(username).strip()
            for username in shared_with
            if str(username).strip()
        },
        key=str.lower,
    )
    return normalized


def _report_row_to_dict(row: SavedReport) -> dict[str, Any]:
    payload = json.loads(row.report_json or "{}")
    payload = _normalise_report(payload if isinstance(payload, dict) else {})
    payload["slug"] = row.slug
    if row.owner:
        payload["owner"] = row.owner
    if row.name:
        payload["name"] = row.name
    if row.description is not None:
        payload["description"] = row.description
    return payload


def _upsert_row(session, report: dict[str, Any], slug_override: str | None = None) -> None:
    report = _normalise_report(dict(report))
    slug = str(slug_override or report.get("slug") or "").strip()
    if not slug:
        raise ValueError("Saved report slug is required")
    row = session.execute(select(SavedReport).where(SavedReport.slug == slug)).scalar_one_or_none()
    now = _utcnow()
    payload_json = json.dumps(report, indent=2, sort_keys=True)
    if row is None:
        row = SavedReport(
            slug=slug,
            owner=str(report.get("owner") or "").strip() or None,
            name=str(report.get("name") or slug),
            description=str(report.get("description") or ""),
            report_json=payload_json,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
    else:
        row.owner = str(report.get("owner") or "").strip() or None
        row.name = str(report.get("name") or slug)
        row.description = str(report.get("description") or "")
        row.report_json = payload_json
        row.updated_at = now


def _migrate_legacy_json_if_needed() -> None:
    _ensure_tables()
    with get_session() as session:
        existing = session.execute(select(SavedReport.slug).limit(1)).first()
        if existing is not None:
            return
        manifest = _load_json_seed()
        reports = manifest.get("reports", [])
        if not reports:
            return
        for report in reports:
            if isinstance(report, dict):
                _upsert_row(session, report)
        session.commit()
    _rename_legacy_file()


def list_reports() -> list[dict[str, Any]]:
    _migrate_legacy_json_if_needed()
    with get_session() as session:
        rows = session.execute(select(SavedReport).order_by(SavedReport.name.asc(), SavedReport.slug.asc())).scalars().all()
        return [_report_row_to_dict(row) for row in rows]


def get_report(slug: str) -> dict[str, Any] | None:
    _migrate_legacy_json_if_needed()
    with get_session() as session:
        row = session.execute(select(SavedReport).where(SavedReport.slug == slug)).scalar_one_or_none()
        return _report_row_to_dict(row) if row else None


def can_view_report(report: dict[str, Any], username: str, role: str) -> bool:
    normalized = _normalise_report(report)
    if role == "admin":
        return True
    owner = str(normalized.get("owner") or "").strip()
    if not owner:
        return True
    if username == owner:
        return True
    return username in set(normalized.get("shared_with") or [])


def can_manage_report(report: dict[str, Any], username: str, role: str) -> bool:
    normalized = _normalise_report(report)
    if role == "admin":
        return True
    owner = str(normalized.get("owner") or "").strip()
    if not owner:
        return False
    return username == owner


def _ensure_report_csv_access_token(report: dict[str, Any]) -> tuple[dict[str, Any], str]:
    token = str(report.get("csv_access_token") or "").strip()
    if token:
        return report, token
    updated = dict(report)
    updated["csv_access_token"] = secrets.token_urlsafe(24)
    return updated, updated["csv_access_token"]


def ensure_csv_access_token(slug: str) -> str:
    _migrate_legacy_json_if_needed()
    with get_session() as session:
        row = session.execute(select(SavedReport).where(SavedReport.slug == slug)).scalar_one_or_none()
        if row is None:
            raise ValueError("Saved report not found")
        report = _report_row_to_dict(row)
        updated, token = _ensure_report_csv_access_token(report)
        if updated != report:
            _upsert_row(session, updated, slug_override=slug)
            session.commit()
        return token


def validate_csv_access_token(slug: str, token: str) -> bool:
    report = get_report(slug)
    if not report:
        return False
    stored = str(report.get("csv_access_token") or "").strip()
    return bool(stored and token and secrets.compare_digest(stored, token))


def rotate_csv_access_token(slug: str) -> str:
    _migrate_legacy_json_if_needed()
    with get_session() as session:
        row = session.execute(select(SavedReport).where(SavedReport.slug == slug)).scalar_one_or_none()
        if row is None:
            raise ValueError("Saved report not found")
        report = _report_row_to_dict(row)
        report["csv_access_token"] = secrets.token_urlsafe(24)
        _upsert_row(session, report, slug_override=slug)
        session.commit()
        return str(report["csv_access_token"])


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return cleaned.strip("-")


def ensure_unique_slug(base_slug: str) -> str:
    slug = base_slug.strip()
    if not slug:
        raise ValueError("Saved report slug is required")
    existing = {str(report.get("slug") or "").strip() for report in list_reports()}
    if slug not in existing:
        return slug

    suffix = 2
    while f"{slug}-{suffix}" in existing:
        suffix += 1
    return f"{slug}-{suffix}"


def create_report(report: dict[str, Any]) -> None:
    _migrate_legacy_json_if_needed()
    report = _normalise_report(dict(report))
    slug = str(report.get("slug") or "").strip()
    if not slug:
        raise ValueError("Saved report slug is required")
    with get_session() as session:
        existing = session.execute(select(SavedReport).where(SavedReport.slug == slug)).scalar_one_or_none()
        if existing:
            raise ValueError("A saved report with that slug already exists")
        report, _ = _ensure_report_csv_access_token(report)
        _upsert_row(session, report, slug_override=slug)
        session.commit()


def update_report(slug: str, report: dict[str, Any]) -> None:
    _migrate_legacy_json_if_needed()
    slug = str(slug or "").strip()
    if not slug:
        raise ValueError("Saved report slug is required")
    with get_session() as session:
        existing = session.execute(select(SavedReport).where(SavedReport.slug == slug)).scalar_one_or_none()
        if existing is None:
            raise ValueError("Saved report not found")
        updated = _normalise_report(dict(report))
        updated["slug"] = slug
        updated["csv_access_token"] = str(
            existing and _report_row_to_dict(existing).get("csv_access_token")
            or updated.get("csv_access_token")
            or secrets.token_urlsafe(24)
        )
        _upsert_row(session, updated, slug_override=slug)
        session.commit()


def delete_report(slug: str) -> None:
    _migrate_legacy_json_if_needed()
    slug = str(slug or "").strip()
    if not slug:
        raise ValueError("Saved report slug is required")
    with get_session() as session:
        row = session.execute(select(SavedReport).where(SavedReport.slug == slug)).scalar_one_or_none()
        if row is None:
            raise ValueError("Saved report not found")
        session.delete(row)
        session.commit()
