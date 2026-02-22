from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas.organisations import OrganisationOut
from db.models import Organisation

router = APIRouter(prefix="/api/v1/organisations", tags=["organisations"])


@router.get("")
def list_organisations(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> dict:
    """List pharmaceutical organisations with pagination."""
    query = select(Organisation)
    total_records = db.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
    offset = (page - 1) * limit
    results = db.execute(query.offset(offset).limit(limit)).scalars().all()
    return {
        "data": [
            {
                "organisation_id": row.organisation_id,
                "name": row.name,
                "abn": row.abn,
                "city": row.city,
                "state": row.state,
                "postcode": row.postcode,
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


@router.get("/{organisation_id}", response_model=OrganisationOut)
def get_organisation(organisation_id: int, db: Session = Depends(get_db)) -> OrganisationOut:
    """Get a single organisation by its ID.

    Returns 404 if no organisation with the given ID exists.
    """
    row = (
        db.execute(select(Organisation).where(Organisation.organisation_id == organisation_id))
        .scalar_one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"Organisation '{organisation_id}' not found")
    return OrganisationOut.model_validate(row)
