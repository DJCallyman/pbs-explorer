from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_db, verify_admin
from config import get_settings
from db.session import get_session
from services.background_jobs import (
    PBS_SCHEDULE_LAST_CHECKED_AT_KEY,
    PBS_SCHEDULE_LAST_CHECK_STATUS_KEY,
    PBS_SCHEDULE_LATEST_API_KEY,
    PBS_SCHEDULE_LATEST_EFFECTIVE_DATE_KEY,
    run_medicine_status_refresh_once,
    run_medicare_latest_month_check_once,
    run_pbs_endpoint_sync_once,
    run_pbs_full_sync_once,
    run_pbs_incremental_sync_once,
    run_pbs_schedule_check_once,
)
from services.psd.manifest import summarize_manifest
from services.psd.runtime import get_or_create_status, run_psd_job
from services.psd.search_index import SEARCH_INDEX_PATH, search_index
from services.scheduler import app_scheduler
from services.sync.status_store import status_store
from services.sync.orchestrator import SyncOrchestrator
from services.sync.incremental import IncrementalSync
from services.sync.plan import SYNC_PLAN
from db.models.app_setting import AppSetting
from db.models import Schedule
from services.auth_store import create_user, delete_user, list_users, update_user_password
from services.session_store import count_active_sessions_by_username, list_active_sessions, revoke_sessions_for_user

router = APIRouter(prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(verify_admin)])

def _sync_in_progress() -> bool:
    existing_status = status_store.get()
    return bool((existing_status and existing_status.in_progress) or app_scheduler.is_running())


def _ensure_psd_enabled() -> None:
    if not get_settings().server.enable_psd:
        raise HTTPException(status_code=404, detail="PSD Search is not enabled in this deployment")


class SyncEndpointsRequest(BaseModel):
    endpoints: List[str]


class PSDDownloadRequest(BaseModel):
    max_documents: int | None = 25


class PSDSampleDownloadRequest(BaseModel):
    sample_per_source: int = 3


@router.get("/sync/endpoints")
def list_endpoints() -> dict:
    """List all available sync endpoints."""
    return {
        "endpoints": list(SYNC_PLAN.keys()),
        "count": len(SYNC_PLAN),
    }


@router.get("/psd/status")
def psd_status() -> dict:
    _ensure_psd_enabled()
    status = get_or_create_status()
    return {
        "in_progress": status.in_progress,
        "mode": status.mode,
        "last_run_at": status.last_run_at.isoformat() if status.last_run_at else None,
        "last_success_at": status.last_success_at.isoformat() if status.last_success_at else None,
        "last_error": status.last_error,
        "current_step": status.current_step,
        "current_url": status.current_url,
        "pages_fetched": status.pages_fetched,
        "pages_skipped": status.pages_skipped,
        "pages_missing": status.pages_missing,
        "documents_downloaded": status.documents_downloaded,
        "documents_skipped": status.documents_skipped,
        "documents_discovered": status.documents_discovered,
        "documents_missing": status.documents_missing,
        "output_dir": status.output_dir,
        "manifest_path": status.manifest_path,
        "last_result": status.last_result,
        "manifest": summarize_manifest("data/pbs_documents/manifest.json"),
    }


@router.post("/psd/discover")
async def psd_discover() -> dict:
    _ensure_psd_enabled()
    status = get_or_create_status()
    if status.in_progress:
        raise HTTPException(status_code=409, detail="PSD discovery already in progress")

    async def run_job():
        await run_psd_job(mode="discover")

    asyncio.create_task(run_job())

    return {
        "status": "accepted",
        "type": "documents-discover",
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "message": "PSD & DUSC scan started in background.",
    }


@router.post("/psd/download")
async def psd_download(request: PSDDownloadRequest) -> dict:
    _ensure_psd_enabled()
    status = get_or_create_status()
    if status.in_progress:
        raise HTTPException(status_code=409, detail="Another PSD job is already in progress")

    async def run_job():
        await run_psd_job(mode="download", max_documents=request.max_documents)

    asyncio.create_task(run_job())

    return {
        "status": "accepted",
        "type": "documents-download",
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "message": "PSD & DUSC download job started in background.",
        "max_documents": request.max_documents,
    }


@router.post("/psd/sample-download")
async def psd_sample_download(request: PSDSampleDownloadRequest) -> dict:
    _ensure_psd_enabled()
    status = get_or_create_status()
    if status.in_progress:
        raise HTTPException(status_code=409, detail="Another PSD job is already in progress")

    async def run_job():
        await run_psd_job(mode="sample", sample_per_source=request.sample_per_source)

    asyncio.create_task(run_job())

    return {
        "status": "accepted",
        "type": "documents-sample-download",
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "message": "Sample PSD & DUSC download started in background.",
        "sample_per_source": request.sample_per_source,
    }


@router.get("/psd/search")
def psd_search(q: str) -> dict:
    _ensure_psd_enabled()
    if not SEARCH_INDEX_PATH.exists():
        raise HTTPException(status_code=404, detail="Search index not built yet")
    return search_index(q)


@router.get("/sync/status")
def sync_status(db: Session = Depends(get_db)) -> dict:
    orchestrator = SyncOrchestrator(db)
    return orchestrator.get_sync_status()


@router.get("/sync/history")
def sync_history(db: Session = Depends(get_db)) -> dict:
    orchestrator = SyncOrchestrator(db)
    return {"history": orchestrator.get_sync_history()}


@router.get("/sync/schedules")
async def sync_schedules(db: Session = Depends(get_db)) -> dict:
    """Get available schedules from API and current database state."""
    from sqlalchemy import select, func, desc
    from db.models import Schedule, SyncState

    orchestrator = SyncOrchestrator(db)
    incremental = IncrementalSync(db)

    try:
        latest_api = await incremental.get_latest_schedule_code()
    except Exception as e:
        return {
            "error": "Could not connect to PBS API",
            "detail": str(e),
            "latest_api_schedule": None,
            "last_fully_synced_schedule": None,
            "schedules": [],
            "needs_sync": True,
        }

    result = db.execute(
        select(func.min(SyncState.last_synced_schedule_code))
    )
    last_fully_synced = result.scalar()

    result = db.execute(select(func.count(SyncState.endpoint)))
    sync_state_count = result.scalar()

    result = db.execute(select(Schedule).order_by(desc(Schedule.effective_date)))
    schedules = []
    for row in result.scalars():
        schedules.append({
            "schedule_code": row.schedule_code,
            "effective_date": row.effective_date.isoformat() if row.effective_date else None,
            "revision_number": row.revision_number,
        })

    needs_sync = False
    changed_endpoints = []

    if not latest_api:
        needs_sync = False
    elif sync_state_count == 0:
        needs_sync = True
    elif last_fully_synced is None:
        needs_sync = True
    elif latest_api != last_fully_synced:
        try:
            changes = await incremental.get_changes(
                source_schedule_code=last_fully_synced,
                target_schedule_code=latest_api,
            )
            if changes:
                needs_sync = True
                changed_endpoints = list(set(c.get("changed_endpoint") for c in changes if c.get("changed_endpoint")))
        except Exception as e:
            needs_sync = True

    return {
        "latest_api_schedule": latest_api,
        "last_fully_synced_schedule": last_fully_synced,
        "schedules": schedules,
        "needs_sync": needs_sync,
        "changed_endpoints": changed_endpoints,
    }


@router.post("/sync/full")
async def sync_full() -> dict:
    """Trigger a full sync of all endpoints."""
    if _sync_in_progress():
        raise HTTPException(status_code=409, detail="Sync already in progress")

    async def run_sync():
        try:
            await run_pbs_full_sync_once()
        except Exception as e:
            # Get the status again in case it changed
            task_status = status_store.get()
            if task_status:
                task_status.last_error = str(e)
                task_status.in_progress = False

    asyncio.create_task(run_sync())

    return {
        "status": "accepted",
        "type": "full",
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "message": "Full PBS sync started in background.",
    }


@router.post("/sync/endpoints")
async def sync_endpoints(request: SyncEndpointsRequest) -> dict:
    """Trigger a sync of specific endpoints only."""
    if _sync_in_progress():
        raise HTTPException(status_code=409, detail="Sync already in progress")

    # Validate endpoints
    invalid_endpoints = [e for e in request.endpoints if e not in SYNC_PLAN]
    if invalid_endpoints:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid endpoints: {invalid_endpoints}. Valid endpoints: {list(SYNC_PLAN.keys())}",
        )

    async def run_sync():
        try:
            await run_pbs_endpoint_sync_once(request.endpoints)
        except Exception as e:
            task_status = status_store.get()
            if task_status:
                task_status.last_error = str(e)
                task_status.in_progress = False

    asyncio.create_task(run_sync())

    return {
        "status": "accepted",
        "type": "endpoints",
        "endpoints": request.endpoints,
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "message": f"Sync of {len(request.endpoints)} endpoint(s) started in background.",
    }


@router.post("/sync/incremental")
async def sync_incremental() -> dict:
    """Trigger an incremental sync using summary-of-changes."""
    if _sync_in_progress():
        raise HTTPException(status_code=409, detail="Sync already in progress")

    async def run_sync():
        try:
            await run_pbs_incremental_sync_once()
        except Exception as e:
            task_status = status_store.get()
            if task_status:
                task_status.last_error = str(e)
                task_status.in_progress = False

    asyncio.create_task(run_sync())

    return {
        "status": "accepted",
        "type": "incremental",
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "message": "Incremental PBS sync started in background.",
    }


@router.post("/sync/medicine-status")
async def sync_medicine_status() -> dict:
    """Trigger a Medicines Status / PBAC metadata refresh only."""
    if _sync_in_progress():
        raise HTTPException(status_code=409, detail="Sync already in progress")

    async def run_sync():
        try:
            await run_medicine_status_refresh_once()
        except Exception as e:
            task_status = status_store.get()
            if task_status:
                task_status.last_error = str(e)
                task_status.in_progress = False
                task_status.current_endpoint = None

    asyncio.create_task(run_sync())

    return {
        "status": "accepted",
        "type": "medicine-status",
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "message": "Medicines Status / PBAC metadata refresh started in background.",
    }


@router.get("/sync/estimate")
async def sync_estimate(db: Session = Depends(get_db)) -> dict:
    """Get estimate of what an incremental sync would process."""
    incremental = IncrementalSync(db)

    try:
        latest_api = await incremental.get_latest_schedule_code()
    except Exception as e:
        return {
            "type": "error",
            "error": "Could not connect to PBS API",
            "detail": str(e),
            "message": "Check your API subscription key configuration.",
        }

    current_db = await incremental.get_current_db_schedule()

    if not latest_api:
        return {
            "type": "error",
            "error": "No schedule data returned",
            "message": "The API returned no schedule data.",
        }

    if not current_db:
        return {
            "type": "full_required",
            "message": "No data in database. A full sync is required.",
            "estimated_time": "5-10 minutes",
            "estimated_records": "2-3 million",
        }

    if latest_api == current_db:
        return {
            "type": "not_needed",
            "message": f"Database is already at the latest schedule ({latest_api}).",
            "current_schedule": current_db,
            "latest_schedule": latest_api,
        }

    try:
        changes_response = await incremental.client.get(
            "/summary-of-changes",
            params={
                "filter": f"source_schedule_code eq {current_db}",
                "limit": 1,
            },
        )

        from services.sync.parser import parse_json
        changes, meta = parse_json(changes_response.text)
        total_changes = meta.get("_meta", {}).get("total_records", "unknown")
    except Exception:
        total_changes = "unknown"

    return {
        "type": "incremental",
        "message": f"Schedule {current_db} -> {latest_api}",
        "source_schedule": current_db,
        "target_schedule": latest_api,
        "estimated_changes": total_changes,
        "estimated_time": "1-5 minutes" if total_changes and total_changes != "unknown" else "seconds",
    }


@router.get("/scheduler/status")
def scheduler_status() -> dict:
    return app_scheduler.get_status()


@router.post("/cache/clear")
def cache_clear() -> dict:
    return {"status": "accepted"}


@router.get("/config")
def config_get() -> dict:
    return {"status": "not_implemented"}


@router.put("/config")
def config_update() -> dict:
    return {"status": "not_implemented"}


class UpdateSettingRequest(BaseModel):
    value: str


class ManagedUserCreateRequest(BaseModel):
    username: str
    password: str
    role: str = "user"


class ManagedUserPasswordRequest(BaseModel):
    password: str


def _format_admin_date(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    if len(raw) >= 16 and raw[4] == "-" and raw[7] == "-" and raw[10] == " " and raw[13] == ":":
        try:
            date_part = datetime.strptime(raw[:10], "%Y-%m-%d").strftime("%d-%b-%Y")
            time_part = datetime.strptime(raw[11:16], "%H:%M").strftime("%I:%M %p")
            suffix = raw[16:].strip()
            return f"{date_part} {time_part}{(' ' + suffix) if suffix else ''}"
        except ValueError:
            pass
    for fmt in (
        "%Y-%m-%d %H:%M %Z",
        "%Y-%m-%d %H:%M UTC",
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            if "H:%M" in fmt or "T%H:%M:%S" in fmt:
                return datetime.strptime(raw, fmt).strftime("%d-%b-%Y %I:%M %p")
            return datetime.strptime(raw, fmt).strftime("%d-%b-%Y")
        except ValueError:
            continue
    return raw


def _format_admin_month(value: str | None) -> str:
    raw = (value or "").strip()
    if len(raw) == 6 and raw.isdigit():
        try:
            return datetime.strptime(raw, "%Y%m").strftime("%b %Y")
        except ValueError:
            return raw
    return raw or "Unknown"


def _format_admin_effective_date(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return "Unknown"
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d").strftime("%d-%b-%Y")
    except ValueError:
        return raw


def _get_setting_value(db: Session, key: str) -> str | None:
    return db.execute(select(AppSetting.value).where(AppSetting.key == key)).scalar()


def _set_setting_value(db: Session, key: str, value: str) -> None:
    existing = db.execute(select(AppSetting).where(AppSetting.key == key)).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if existing:
        existing.value = value
        existing.updated_at = now
    else:
        db.add(AppSetting(key=key, value=value, updated_at=now))


@router.get("/settings/medicare-end-date")
def get_medicare_end_date(db: Session = Depends(get_db)) -> dict:
    row = db.execute(
        select(AppSetting.value)
        .where(AppSetting.key == "medicare_stats_end_date")
    ).scalar()
    return {"end_date": row or "202511"}


@router.get("/settings/medicare-status")
def get_medicare_status(db: Session = Depends(get_db)) -> dict:
    values = {
        key: value
        for key, value in db.execute(
            select(AppSetting.key, AppSetting.value).where(
                AppSetting.key.in_(
                    [
                        "medicare_stats_end_date",
                        "medicare_stats_last_checked_at",
                        "medicare_stats_last_check_status",
                    ]
                )
            )
        ).all()
    }
    end_date = values.get("medicare_stats_end_date") or "202511"
    return {
        "end_date": end_date,
        "end_date_label": _format_admin_month(end_date),
        "last_checked_at": _format_admin_date(values.get("medicare_stats_last_checked_at")),
        "last_check_status": values.get("medicare_stats_last_check_status") or "Not checked yet",
    }


@router.get("/settings/pbs-schedule-status")
async def get_pbs_schedule_status(db: Session = Depends(get_db)) -> dict:
    incremental = IncrementalSync(db)
    current_db_schedule = await incremental.get_current_db_schedule()
    latest_api_schedule = _get_setting_value(db, PBS_SCHEDULE_LATEST_API_KEY)
    latest_api_effective_date = _get_setting_value(db, PBS_SCHEDULE_LATEST_EFFECTIVE_DATE_KEY)
    last_checked_at = _get_setting_value(db, PBS_SCHEDULE_LAST_CHECKED_AT_KEY)
    last_check_status = _get_setting_value(db, PBS_SCHEDULE_LAST_CHECK_STATUS_KEY) or "Not checked yet"
    current_db_effective_date = db.execute(
        select(Schedule.effective_date).where(Schedule.schedule_code == current_db_schedule)
    ).scalar() if current_db_schedule else None

    if not latest_api_schedule and current_db_schedule:
        latest_api_schedule = current_db_schedule
    if not latest_api_effective_date and current_db_effective_date:
        latest_api_effective_date = current_db_effective_date.isoformat()

    new_schedule_available = bool(
        latest_api_schedule and current_db_schedule and latest_api_schedule != current_db_schedule
    )

    return {
        "latest_api_schedule": latest_api_schedule or "Unknown",
        "latest_api_schedule_label": _format_admin_effective_date(latest_api_effective_date),
        "current_db_schedule": current_db_schedule or "Unknown",
        "current_db_schedule_label": _format_admin_effective_date(current_db_effective_date.isoformat() if current_db_effective_date else ""),
        "last_checked_at": _format_admin_date(last_checked_at),
        "last_check_status": last_check_status,
        "new_schedule_available": new_schedule_available,
    }


@router.post("/settings/pbs-schedule-check")
async def check_pbs_schedule_status(db: Session = Depends(get_db)) -> dict:
    result = await run_pbs_schedule_check_once()
    return {
        "latest_api_schedule": result.get("latest_api_schedule") or "Unknown",
        "latest_api_schedule_label": _format_admin_effective_date(result.get("latest_api_effective_date")),
        "current_db_schedule": result.get("current_db_schedule") or "Unknown",
        "current_db_schedule_label": _format_admin_effective_date(result.get("current_db_effective_date")),
        "last_checked_at": _format_admin_date(result.get("last_checked_at")),
        "last_check_status": result.get("last_check_status") or "Unknown",
        "new_schedule_available": bool(result.get("new_schedule_available")),
        "message": result.get("message") or "PBS schedule checked.",
    }


@router.post("/settings/medicare-check-latest")
async def check_latest_medicare() -> dict:
    status = await run_medicare_latest_month_check_once()
    return {
        "end_date": status.get("end_date"),
        "end_date_label": status.get("end_date_label"),
        "last_checked_at": status.get("last_checked_at"),
        "last_check_status": status.get("last_check_status"),
        "message": f"Latest Medicare data checked: {status.get('end_date_label') or status.get('end_date') or 'Unknown'}",
    }


@router.put("/settings/medicare-end-date")
def update_medicare_end_date(body: UpdateSettingRequest, db: Session = Depends(get_db)) -> dict:
    import re

    value = body.value.strip()
    if not re.match(r"^\d{6}$", value):
        raise HTTPException(status_code=400, detail="Value must be in YYYYMM format, e.g. 202511")

    existing = db.execute(
        select(AppSetting)
        .where(AppSetting.key == "medicare_stats_end_date")
    ).scalar_one_or_none()

    if existing:
        existing.value = value
        existing.updated_at = datetime.now(timezone.utc)
    else:
        db.add(AppSetting(key="medicare_stats_end_date", value=value, updated_at=datetime.now(timezone.utc)))
    db.commit()
    return {"end_date": value}


@router.get("/users")
def get_managed_users() -> dict:
    counts = count_active_sessions_by_username()
    users = list_users()
    for user in users:
        user["active_sessions"] = counts.get(user["username"], 0)
    return {"users": users}


@router.post("/users")
def create_managed_user(body: ManagedUserCreateRequest) -> dict:
    create_user(body.username, body.password, body.role)
    return {"message": f"User {body.username} created."}


@router.put("/users/{username}/password")
def reset_managed_user_password(username: str, body: ManagedUserPasswordRequest) -> dict:
    update_user_password(username, body.password)
    return {"message": f"Password updated for {username}."}


@router.delete("/users/{username}")
def delete_managed_user(username: str) -> dict:
    delete_user(username)
    revoke_sessions_for_user(username)
    return {"message": f"User {username} deleted."}


@router.get("/sessions")
def get_active_web_sessions() -> dict:
    return {"sessions": list_active_sessions()}


@router.post("/sessions/revoke-user/{username}")
def revoke_user_sessions(username: str) -> dict:
    count = revoke_sessions_for_user(username)
    return {"message": f"Signed out {count} active session(s) for {username}.", "revoked_count": count}
