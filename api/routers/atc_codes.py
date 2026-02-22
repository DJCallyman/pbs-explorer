from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas.atc_codes import ATCCodeOut
from db.models import ATCCode

router = APIRouter(prefix="/api/v1/atc-codes", tags=["atc_codes"])


@router.get("")
def list_atc_codes(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> dict:
    """List ATC (Anatomical Therapeutic Chemical) classification codes with pagination."""
    query = select(ATCCode)
    total_records = db.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
    offset = (page - 1) * limit
    results = db.execute(query.offset(offset).limit(limit)).scalars().all()
    return {
        "data": [
            {"atc_code": row.atc_code, "atc_description": row.atc_description, "atc_level": row.atc_level}
            for row in results
        ],
        "_meta": {
            "total_records": total_records,
            "page": page,
            "limit": limit,
            "total_pages": (total_records + limit - 1) // limit if total_records else 0,
        },
    }


@router.get("/{atc_code}", response_model=ATCCodeOut)
def get_atc_code(atc_code: str, db: Session = Depends(get_db)) -> ATCCodeOut:
    """Get a single ATC code by its identifier.

    Returns 404 if no ATC code with the given identifier exists.
    """
    row = db.execute(select(ATCCode).where(ATCCode.atc_code == atc_code)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"ATC code '{atc_code}' not found")
    return ATCCodeOut.model_validate(row)
