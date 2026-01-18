from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_db
from db.models import Restriction

router = APIRouter(prefix="/api/v1/restrictions", tags=["restrictions"])


@router.get("")
def list_restrictions(db: Session = Depends(get_db)) -> list[dict]:
    results = db.execute(select(Restriction)).scalars().all()
    return [
        {
            "res_code": row.res_code,
            "restriction_number": row.restriction_number,
            "authority_method": row.authority_method,
            "treatment_phase": row.treatment_phase,
        }
        for row in results
    ]


@router.get("/{res_code}")
def get_restriction(res_code: str, db: Session = Depends(get_db)) -> dict | None:
    row = db.execute(select(Restriction).where(Restriction.res_code == res_code)).scalar_one_or_none()
    if row is None:
        return None
    return {
        "res_code": row.res_code,
        "restriction_number": row.restriction_number,
        "authority_method": row.authority_method,
        "treatment_phase": row.treatment_phase,
        "criteria_relationship": row.criteria_relationship,
    }
