from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_db
from db.models import ATCCode

router = APIRouter(prefix="/api/v1/atc-codes", tags=["atc_codes"])


@router.get("")
def list_atc_codes(db: Session = Depends(get_db)) -> list[dict]:
    results = db.execute(select(ATCCode)).scalars().all()
    return [{"atc_code": row.atc_code, "atc_description": row.atc_description, "atc_level": row.atc_level} for row in results]


@router.get("/{atc_code}")
def get_atc_code(atc_code: str, db: Session = Depends(get_db)) -> dict | None:
    row = db.execute(select(ATCCode).where(ATCCode.atc_code == atc_code)).scalar_one_or_none()
    if row is None:
        return None
    return {
        "atc_code": row.atc_code,
        "atc_description": row.atc_description,
        "atc_level": row.atc_level,
        "atc_parent_code": row.atc_parent_code,
    }
