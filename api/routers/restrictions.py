from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas.restrictions import RestrictionOut
from db.models import Restriction

router = APIRouter(prefix="/api/v1/restrictions", tags=["restrictions"])


@router.get("")
def list_restrictions(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> dict:
    """List PBS restrictions with pagination."""
    query = select(Restriction)
    total_records = db.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
    offset = (page - 1) * limit
    results = db.execute(query.offset(offset).limit(limit)).scalars().all()
    return {
        "data": [
            {
                "res_code": row.res_code,
                "restriction_number": row.restriction_number,
                "authority_method": row.authority_method,
                "treatment_phase": row.treatment_phase,
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


@router.get("/{res_code}", response_model=RestrictionOut)
def get_restriction(res_code: str, db: Session = Depends(get_db)) -> RestrictionOut:
    """Get a single restriction by its ``res_code``.

    Returns 404 if no restriction with the given code exists.
    """
    row = db.execute(select(Restriction).where(Restriction.res_code == res_code)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Restriction '{res_code}' not found")
    return RestrictionOut.model_validate(row)
