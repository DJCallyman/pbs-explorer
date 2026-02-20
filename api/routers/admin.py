from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.deps import get_db
from services.sync.status_store import status_store
from services.sync.orchestrator import SyncOrchestrator
from services.sync.incremental import IncrementalSync
from services.sync.plan import SYNC_PLAN

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class SyncEndpointsRequest(BaseModel):
    endpoints: List[str]


@router.get("/sync/endpoints")
def list_endpoints() -> dict:
    """List all available sync endpoints."""
    return {
        "endpoints": list(SYNC_PLAN.keys()),
        "count": len(SYNC_PLAN),
    }


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
async def sync_full(db: Session = Depends(get_db)) -> dict:
    """Trigger a full sync of all endpoints."""
    existing_status = status_store.get()
    if existing_status and existing_status.in_progress:
        raise HTTPException(status_code=409, detail="Sync already in progress")

    async def run_sync():
        orchestrator = SyncOrchestrator(db)
        try:
            await orchestrator.sync_all_full()
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
        "requested_at": datetime.utcnow().isoformat(),
        "message": "Full sync started in background. Check status endpoint for progress.",
    }


@router.post("/sync/endpoints")
async def sync_endpoints(request: SyncEndpointsRequest, db: Session = Depends(get_db)) -> dict:
    """Trigger a sync of specific endpoints only."""
    existing_status = status_store.get()
    if existing_status and existing_status.in_progress:
        raise HTTPException(status_code=409, detail="Sync already in progress")

    # Validate endpoints
    invalid_endpoints = [e for e in request.endpoints if e not in SYNC_PLAN]
    if invalid_endpoints:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid endpoints: {invalid_endpoints}. Valid endpoints: {list(SYNC_PLAN.keys())}",
        )

    async def run_sync():
        orchestrator = SyncOrchestrator(db)
        try:
            await orchestrator.sync_endpoints(request.endpoints)
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
        "requested_at": datetime.utcnow().isoformat(),
        "message": f"Sync of {len(request.endpoints)} endpoint(s) started in background. Check status endpoint for progress.",
    }


@router.post("/sync/incremental")
async def sync_incremental(db: Session = Depends(get_db)) -> dict:
    """Trigger an incremental sync using summary-of-changes."""
    existing_status = status_store.get()
    if existing_status and existing_status.in_progress:
        raise HTTPException(status_code=409, detail="Sync already in progress")

    async def run_sync():
        orchestrator = SyncOrchestrator(db)
        try:
            await orchestrator.sync_all_incremental()
        except Exception as e:
            task_status = status_store.get()
            if task_status:
                task_status.last_error = str(e)
                task_status.in_progress = False

    asyncio.create_task(run_sync())

    return {
        "status": "accepted",
        "type": "incremental",
        "requested_at": datetime.utcnow().isoformat(),
        "message": "Incremental sync started in background. Check status endpoint for progress.",
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


@router.get("/settings/medicare-end-date")
def get_medicare_end_date(db: Session = Depends(get_db)) -> dict:
    from db.models.app_setting import AppSetting
    row = db.execute(
        __import__("sqlalchemy").select(AppSetting.value)
        .where(AppSetting.key == "medicare_stats_end_date")
    ).scalar()
    return {"end_date": row or "202511"}


@router.put("/settings/medicare-end-date")
def update_medicare_end_date(body: UpdateSettingRequest, db: Session = Depends(get_db)) -> dict:
    import re
    from datetime import datetime, timezone
    from db.models.app_setting import AppSetting

    value = body.value.strip()
    if not re.match(r"^\d{6}$", value):
        raise HTTPException(status_code=400, detail="Value must be in YYYYMM format, e.g. 202511")

    existing = db.execute(
        __import__("sqlalchemy").select(AppSetting)
        .where(AppSetting.key == "medicare_stats_end_date")
    ).scalar_one_or_none()

    if existing:
        existing.value = value
        existing.updated_at = datetime.now(timezone.utc)
    else:
        db.add(AppSetting(key="medicare_stats_end_date", value=value, updated_at=datetime.now(timezone.utc)))
    db.commit()
    return {"end_date": value}
