from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Awaitable, Callable
from zoneinfo import ZoneInfo

from services.background_jobs import (
    run_medicare_latest_month_check_once,
    run_medicine_status_refresh_once,
    run_pbs_incremental_sync_once,
    run_pbs_schedule_check_once,
)
from services.sync.status_store import status_store

logger = logging.getLogger(__name__)
SYDNEY_TZ = ZoneInfo("Australia/Sydney")


@dataclass
class ScheduledJobState:
    name: str
    label: str
    summary: str
    next_run_at: datetime | None = None
    last_started_at: datetime | None = None
    last_finished_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    last_result: str | None = None
    is_running: bool = False


@dataclass
class ScheduledJobDefinition:
    name: str
    label: str
    summary: str
    priority: int
    next_run: Callable[[datetime, ScheduledJobState], datetime]
    runner: Callable[[], Awaitable[dict | None]]


def _next_time_of_day(now: datetime, hours: tuple[int, ...], minute: int = 0) -> datetime:
    for hour in hours:
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate > now:
            return candidate
    tomorrow = now + timedelta(days=1)
    return tomorrow.replace(hour=hours[0], minute=minute, second=0, microsecond=0)


def _next_medicare_check(now: datetime, _state: ScheduledJobState) -> datetime:
    return _next_time_of_day(now, (9, 12, 15))


def _next_pbs_schedule_check(now: datetime, _state: ScheduledJobState) -> datetime:
    candidates: list[datetime] = []
    today_slots = [(6, 10)]
    if now.day == 1:
        today_slots.extend([(9, 10), (12, 10)])
    for hour, minute in today_slots:
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate > now:
            candidates.append(candidate)
    if candidates:
        return min(candidates)

    tomorrow = now + timedelta(days=1)
    return tomorrow.replace(hour=6, minute=10, second=0, microsecond=0)


def _first_business_day(year: int, month: int) -> datetime:
    candidate = datetime(year, month, 1, 4, 30, tzinfo=SYDNEY_TZ)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate


def _next_first_business_day(now: datetime, _state: ScheduledJobState) -> datetime:
    current = _first_business_day(now.year, now.month)
    if current > now:
        return current
    if now.month == 12:
        return _first_business_day(now.year + 1, 1)
    return _first_business_day(now.year, now.month + 1)


def _next_sunday_fallback(now: datetime, _state: ScheduledJobState) -> datetime:
    days_until_sunday = (6 - now.weekday()) % 7
    candidate = (now + timedelta(days=days_until_sunday)).replace(hour=4, minute=30, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=7)
    return candidate


class AppScheduler:
    def __init__(self) -> None:
        self._stop_event: asyncio.Event | None = None
        self._task: asyncio.Task | None = None
        self._jobs: dict[str, ScheduledJobDefinition] = {
            "medicine_status_monthly_refresh": ScheduledJobDefinition(
                name="medicine_status_monthly_refresh",
                label="Medicines Status monthly refresh",
                summary="First business day of the month at 4:30 AM Sydney time.",
                priority=2,
                next_run=_next_first_business_day,
                runner=run_medicine_status_refresh_once,
            ),
            "medicine_status_stale_fallback": ScheduledJobDefinition(
                name="medicine_status_stale_fallback",
                label="Medicines Status stale fallback",
                summary="Sunday 4:30 AM Sydney time when Medicines Status is older than 35 days.",
                priority=3,
                next_run=_next_sunday_fallback,
                runner=self._run_medicine_status_fallback,
            ),
            "medicare_latest_month_check": ScheduledJobDefinition(
                name="medicare_latest_month_check",
                label="Medicare latest-month check",
                summary="Daily at 9:00 AM, 12:00 PM, and 3:00 PM Sydney time.",
                priority=3,
                next_run=_next_medicare_check,
                runner=run_medicare_latest_month_check_once,
            ),
            "pbs_schedule_check": ScheduledJobDefinition(
                name="pbs_schedule_check",
                label="PBS schedule check",
                summary="Daily at 6:10 AM, plus 9:10 AM and 12:10 PM on the first day of each month.",
                priority=4,
                next_run=_next_pbs_schedule_check,
                runner=run_pbs_schedule_check_once,
            ),
        }
        self._states = {
            name: ScheduledJobState(name=name, label=job.label, summary=job.summary)
            for name, job in self._jobs.items()
        }
        self._states["pbs_incremental_sync"] = ScheduledJobState(
            name="pbs_incremental_sync",
            label="Automatic PBS incremental sync",
            summary="Runs immediately after an automatic schedule check detects a new PBS schedule.",
        )

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        now = datetime.now(SYDNEY_TZ)
        for name, job in self._jobs.items():
            state = self._states[name]
            state.next_run_at = job.next_run(now, state)
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def is_running(self) -> bool:
        return any(state.is_running for state in self._states.values())

    def get_status(self) -> dict:
        jobs = []
        for state in self._states.values():
            jobs.append(
                {
                    "name": state.name,
                    "label": state.label,
                    "summary": state.summary,
                    "next_run_at": state.next_run_at.isoformat() if state.next_run_at else None,
                    "last_started_at": state.last_started_at.isoformat() if state.last_started_at else None,
                    "last_finished_at": state.last_finished_at.isoformat() if state.last_finished_at else None,
                    "last_success_at": state.last_success_at.isoformat() if state.last_success_at else None,
                    "last_error": state.last_error,
                    "last_result": state.last_result,
                    "is_running": state.is_running,
                }
            )
        jobs.sort(key=lambda item: (item["next_run_at"] is None, item["next_run_at"] or "", item["name"]))
        return {"jobs": jobs}

    async def _run_loop(self) -> None:
        assert self._stop_event is not None
        while not self._stop_event.is_set():
            now = datetime.now(SYDNEY_TZ)
            due_jobs = [
                (self._jobs[name], self._states[name])
                for name in self._jobs
                if self._states[name].next_run_at and self._states[name].next_run_at <= now
            ]
            if due_jobs:
                due_jobs.sort(key=lambda item: (item[0].priority, item[1].next_run_at or now))
                job, state = due_jobs[0]
                if self._sync_in_progress():
                    state.last_result = "Deferred because another sync or refresh was already running."
                    state.next_run_at = now + timedelta(minutes=15)
                    await asyncio.sleep(1)
                    continue
                await self._execute_job(job, state)
                continue

            next_times = [state.next_run_at for state in self._states.values() if state.next_run_at]
            if not next_times:
                await asyncio.sleep(60)
                continue
            next_run_at = min(next_times)
            delay = max((next_run_at - now).total_seconds(), 1.0)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
            except asyncio.TimeoutError:
                continue

    def _sync_in_progress(self) -> bool:
        status = status_store.get()
        return bool(status and status.in_progress)

    async def _execute_job(self, job: ScheduledJobDefinition, state: ScheduledJobState) -> None:
        state.is_running = True
        state.last_started_at = datetime.now(SYDNEY_TZ)
        state.last_error = None
        try:
            result = await job.runner()
            state.last_success_at = datetime.now(SYDNEY_TZ)
            state.last_result = self._summarize_result(job.name, result)
            if job.name == "pbs_schedule_check" and isinstance(result, dict) and result.get("new_schedule_available"):
                await self._execute_ad_hoc_incremental_sync()
        except Exception as exc:
            logger.exception("Scheduled job failed: %s", job.name)
            state.last_error = str(exc)
            state.last_result = None
        finally:
            state.is_running = False
            state.last_finished_at = datetime.now(SYDNEY_TZ)
            state.next_run_at = job.next_run(datetime.now(SYDNEY_TZ), state)

    async def _execute_ad_hoc_incremental_sync(self) -> None:
        state = self._states["pbs_incremental_sync"]
        state.is_running = True
        state.last_started_at = datetime.now(SYDNEY_TZ)
        state.last_error = None
        try:
            result = await run_pbs_incremental_sync_once()
            state.last_success_at = datetime.now(SYDNEY_TZ)
            synced = sum(int(row.get("synced", 0) or 0) for row in result.values()) if isinstance(result, dict) else 0
            state.last_result = f"Automatic incremental sync complete ({synced:,} records synced)."
        except Exception as exc:
            logger.exception("Automatic PBS incremental sync failed")
            state.last_error = str(exc)
            state.last_result = None
        finally:
            state.is_running = False
            state.last_finished_at = datetime.now(SYDNEY_TZ)
            state.next_run_at = None

    async def _run_medicine_status_fallback(self) -> dict | None:
        state = self._states["medicine_status_monthly_refresh"]
        if state.last_success_at and datetime.now(SYDNEY_TZ) - state.last_success_at < timedelta(days=35):
            return {"skipped": True, "reason": "Medicines Status refresh is still current."}
        return await run_medicine_status_refresh_once()

    def _summarize_result(self, job_name: str, result: dict | None) -> str:
        if not isinstance(result, dict):
            return "Completed."
        if job_name == "medicare_latest_month_check":
            label = result.get("end_date_label") or result.get("end_date") or "Unknown"
            return f"Latest Medicare month checked: {label}."
        if job_name.startswith("medicine_status"):
            if result.get("skipped"):
                return str(result.get("reason") or "Skipped.")
            fetched = int(result.get("detail_pages_fetched", 0) or 0)
            skipped = int(result.get("detail_pages_skipped", 0) or 0)
            return f"Medicines Status refreshed ({fetched} detail pages fetched, {skipped} skipped)."
        if job_name == "pbs_schedule_check":
            return str(result.get("message") or result.get("last_check_status") or "PBS schedule checked.")
        return "Completed."


app_scheduler = AppScheduler()
