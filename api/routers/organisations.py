from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_db
from db.models import Organisation

router = APIRouter(prefix="/api/v1/organisations", tags=["organisations"])


@router.get("")
def list_organisations(db: Session = Depends(get_db)) -> list[dict]:
    results = db.execute(select(Organisation)).scalars().all()
    return [
        {
            "organisation_id": row.organisation_id,
            "name": row.name,
            "abn": row.abn,
            "city": row.city,
            "state": row.state,
            "postcode": row.postcode,
        }
        for row in results
    ]


@router.get("/{organisation_id}")
def get_organisation(organisation_id: int, db: Session = Depends(get_db)) -> dict | None:
    row = (
        db.execute(select(Organisation).where(Organisation.organisation_id == organisation_id))
        .scalar_one_or_none()
    )
    if row is None:
        return None
    return {
        "organisation_id": row.organisation_id,
        "name": row.name,
        "abn": row.abn,
        "street_address": row.street_address,
        "city": row.city,
        "state": row.state,
        "postcode": row.postcode,
        "telephone_number": row.telephone_number,
        "facsimile_number": row.facsimile_number,
    }
