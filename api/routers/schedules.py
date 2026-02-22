from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas.schedules import ScheduleOut
from db.models import Schedule

router = APIRouter(prefix="/api/v1/schedules", tags=["schedules"])


@router.get("")
def list_schedules(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> dict:
    """List PBS schedules with pagination."""
    query = select(Schedule)
    total_records = db.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
    offset = (page - 1) * limit
    results = db.execute(query.offset(offset).limit(limit)).scalars().all()
    return {
        "data": [
            {
                "schedule_code": row.schedule_code,
                "effective_date": row.effective_date,
                "effective_month": row.effective_month,
                "effective_year": row.effective_year,
            }
            for row in results
        ],
        "_meta": {
            "total_records": total_records,
            "page": page,
            "limit": limit,
            "total_pages": (total_records + limit - 1) // limit if total_records else 0,
        },
    }


@router.get("/{schedule_code}", response_model=ScheduleOut)
def get_schedule(schedule_code: str, db: Session = Depends(get_db)) -> ScheduleOut:
    """Get a single schedule by its ``schedule_code``.

    Returns 404 if no schedule with the given code exists.
    """
    row = db.execute(select(Schedule).where(Schedule.schedule_code == schedule_code)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Schedule '{schedule_code}' not found")
    return ScheduleOut.model_validate(row)
