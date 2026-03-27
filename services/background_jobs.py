from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select

from db.models import Schedule
from db.models.app_setting import AppSetting
from db.session import get_session
from services.medicine_status.sync import MedicineStatusSync
from services.sync.incremental import IncrementalSync
from services.sync.orchestrator import SyncOrchestrator
from services.sync.status import SyncStatus
from services.sync.status_store import status_store
from web.helpers import refresh_latest_medicare_data

PBS_SCHEDULE_LAST_CHECKED_AT_KEY = "pbs_schedule_last_checked_at"
PBS_SCHEDULE_LAST_CHECK_STATUS_KEY = "pbs_schedule_last_check_status"
PBS_SCHEDULE_LATEST_API_KEY = "pbs_schedule_latest_api"
PBS_SCHEDULE_LATEST_EFFECTIVE_DATE_KEY = "pbs_schedule_latest_effective_date"


def _get_setting_value(db, key: str) -> str | None:
    return db.execute(select(AppSetting.value).where(AppSetting.key == key)).scalar()


def _set_setting_value(db, key: str, value: str) -> None:
    existing = db.execute(select(AppSetting).where(AppSetting.key == key)).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if existing:
        existing.value = value
        existing.updated_at = now
    else:
        db.add(AppSetting(key=key, value=value, updated_at=now))


def _ensure_status(current_endpoint: str) -> SyncStatus:
    status = status_store.get()
    if status is None:
        status = SyncStatus()
        status_store.set(status)
    status.last_run_at = datetime.now(timezone.utc)
    status.last_error = None
    status.in_progress = True
    status.current_endpoint = current_endpoint
    if current_endpoint != "Refreshing Medicines Status / PBAC metadata":
        status.records_processed = 0
    return status


def _finalize_status_error(exc: Exception) -> None:
    status = status_store.get()
    if status:
        status.last_error = str(exc)
        status.in_progress = False
        status.current_endpoint = None


async def run_medicare_latest_month_check_once() -> dict[str, str]:
    return await refresh_latest_medicare_data()


async def run_medicine_status_refresh_once() -> dict:
    task_status = _ensure_status("Refreshing Medicines Status / PBAC metadata")
    try:
        with get_session() as background_db:
            sync = MedicineStatusSync(background_db)
            try:
                result = await sync.run()
            finally:
                await sync.aclose()
        task_status.current_endpoint = None
        task_status.in_progress = False
        task_status.last_success_at = datetime.now(timezone.utc)
        task_status.records_processed = sum(
            int(result.get(key, 0) or 0) for key in ("created", "updated", "unchanged", "entries_upserted")
        )
        return result
    except Exception as exc:
        _finalize_status_error(exc)
        raise


async def run_pbs_schedule_check_once() -> dict:
    with get_session() as db:
        incremental = IncrementalSync(db)
        checked_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        current_db_schedule = await incremental.get_current_db_schedule()
        current_db_effective_date = (
            db.execute(select(Schedule.effective_date).where(Schedule.schedule_code == current_db_schedule)).scalar()
            if current_db_schedule
            else None
        )
        try:
            latest_api_schedule = await incremental.get_latest_schedule_code()
            latest_api_effective_date = (
                await incremental._get_schedule_effective_date(latest_api_schedule) if latest_api_schedule else ""
            )
        except Exception as exc:
            _set_setting_value(db, PBS_SCHEDULE_LAST_CHECKED_AT_KEY, checked_at)
            _set_setting_value(db, PBS_SCHEDULE_LAST_CHECK_STATUS_KEY, f"Check failed: {exc}")
            db.commit()
            cached_schedule = _get_setting_value(db, PBS_SCHEDULE_LATEST_API_KEY) or current_db_schedule or "Unknown"
            cached_effective_date = _get_setting_value(db, PBS_SCHEDULE_LATEST_EFFECTIVE_DATE_KEY) or (
                current_db_effective_date.isoformat() if current_db_effective_date else ""
            )
            return {
                "latest_api_schedule": cached_schedule,
                "latest_api_effective_date": cached_effective_date,
                "current_db_schedule": current_db_schedule or "Unknown",
                "current_db_effective_date": current_db_effective_date.isoformat() if current_db_effective_date else "",
                "last_checked_at": checked_at,
                "last_check_status": f"Check failed: {exc}",
                "new_schedule_available": False,
                "message": "Could not check the latest PBS schedule.",
            }
        finally:
            await incremental.aclose()

        latest_api_schedule = latest_api_schedule or ""
        latest_api_effective_date = latest_api_effective_date or ""
        _set_setting_value(db, PBS_SCHEDULE_LAST_CHECKED_AT_KEY, checked_at)
        _set_setting_value(db, PBS_SCHEDULE_LATEST_API_KEY, latest_api_schedule)
        _set_setting_value(db, PBS_SCHEDULE_LATEST_EFFECTIVE_DATE_KEY, latest_api_effective_date)

        if latest_api_schedule and current_db_schedule and latest_api_schedule != current_db_schedule:
            status = (
                "New PBS schedule available: "
                f"{latest_api_effective_date or 'Unknown'} "
                f"(current database: {current_db_effective_date.isoformat() if current_db_effective_date else ''})."
            )
            new_available = True
        elif latest_api_schedule and current_db_schedule:
            status = (
                "Database is already on the latest PBS schedule: "
                f"{current_db_effective_date.isoformat() if current_db_effective_date else ''}."
            )
            new_available = False
        elif latest_api_schedule:
            status = f"Latest PBS schedule available: {latest_api_effective_date or 'Unknown'}."
            new_available = False
        else:
            status = "Could not determine the latest PBS schedule."
            new_available = False

        _set_setting_value(db, PBS_SCHEDULE_LAST_CHECK_STATUS_KEY, status)
        db.commit()
        return {
            "latest_api_schedule": latest_api_schedule or "Unknown",
            "latest_api_effective_date": latest_api_effective_date,
            "current_db_schedule": current_db_schedule or "Unknown",
            "current_db_effective_date": current_db_effective_date.isoformat() if current_db_effective_date else "",
            "last_checked_at": checked_at,
            "last_check_status": status,
            "new_schedule_available": new_available,
            "message": status,
        }


async def run_pbs_incremental_sync_once() -> dict:
    _ensure_status("Incremental PBS Sync")
    orchestrator = None
    try:
        with get_session() as background_db:
            orchestrator = SyncOrchestrator(background_db)
            result = await orchestrator.sync_all_incremental()
        return result
    except Exception as exc:
        _finalize_status_error(exc)
        raise
    finally:
        if orchestrator is not None:
            await orchestrator.aclose()


async def run_pbs_full_sync_once() -> dict:
    _ensure_status("Full PBS Sync")
    orchestrator = None
    try:
        with get_session() as background_db:
            orchestrator = SyncOrchestrator(background_db)
            result = await orchestrator.sync_all_full()
        return result
    except Exception as exc:
        _finalize_status_error(exc)
        raise
    finally:
        if orchestrator is not None:
            await orchestrator.aclose()


async def run_pbs_endpoint_sync_once(endpoints: Iterable[str]) -> dict:
    endpoint_list = list(endpoints)
    _ensure_status(f"Syncing {len(endpoint_list)} PBS endpoint(s)")
    orchestrator = None
    try:
        with get_session() as background_db:
            orchestrator = SyncOrchestrator(background_db)
            result = await orchestrator.sync_endpoints(endpoint_list)
        return result
    except Exception as exc:
        _finalize_status_error(exc)
        raise
    finally:
        if orchestrator is not None:
            await orchestrator.aclose()
