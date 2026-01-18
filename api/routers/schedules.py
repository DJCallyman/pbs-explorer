from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_db
from db.models import Schedule

router = APIRouter(prefix="/api/v1/schedules", tags=["schedules"])


@router.get("")
def list_schedules(db: Session = Depends(get_db)) -> list[dict]:
    results = db.execute(select(Schedule)).scalars().all()
    return [
        {
            "schedule_code": row.schedule_code,
            "effective_date": row.effective_date,
            "effective_month": row.effective_month,
            "effective_year": row.effective_year,
        }
        for row in results
    ]


@router.get("/{schedule_code}")
def get_schedule(schedule_code: str, db: Session = Depends(get_db)) -> dict | None:
    row = db.execute(select(Schedule).where(Schedule.schedule_code == schedule_code)).scalar_one_or_none()
    if row is None:
        return None
    return {
        "schedule_code": row.schedule_code,
        "effective_date": row.effective_date,
        "effective_month": row.effective_month,
        "effective_year": row.effective_year,
        "publication_status": row.publication_status,
    }
