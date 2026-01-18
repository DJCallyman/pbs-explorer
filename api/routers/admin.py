from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter

from services.sync.status_store import status_store

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/sync/status")
def sync_status() -> dict:
    status = status_store.get()
    if status is None:
        return {"status": "idle"}
    return {
        "status": "in_progress" if status.in_progress else "idle",
        "current_endpoint": status.current_endpoint,
        "last_run_at": status.last_run_at.isoformat() if status.last_run_at else None,
        "last_success_at": status.last_success_at.isoformat() if status.last_success_at else None,
        "last_error": status.last_error,
        "records_processed": status.records_processed,
    }


@router.post("/sync/trigger")
def sync_trigger() -> dict:
    return {"status": "accepted", "requested_at": datetime.utcnow().isoformat()}


@router.post("/sync/latest")
def sync_latest() -> dict:
    return {"status": "accepted", "requested_at": datetime.utcnow().isoformat()}


@router.post("/cache/clear")
def cache_clear() -> dict:
    return {"status": "accepted"}


@router.get("/config")
def config_get() -> dict:
    return {"status": "not_implemented"}


@router.put("/config")
def config_update() -> dict:
    return {"status": "not_implemented"}
