from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_db
from db.models import Item

router = APIRouter(prefix="/api/v1/items", tags=["items"])


@router.get("")
def list_items(
    drug_name: Optional[str] = None,
    brand_name: Optional[str] = None,
    program_code: Optional[str] = None,
    benefit_type_code: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> dict:
    query = select(Item)
    if drug_name:
        query = query.where(Item.drug_name.ilike(f"%{drug_name}%"))
    if brand_name:
        query = query.where(Item.brand_name.ilike(f"%{brand_name}%"))
    if program_code:
        query = query.where(Item.program_code == program_code)
    if benefit_type_code:
        query = query.where(Item.benefit_type_code == benefit_type_code)

    total = db.execute(query).scalars().all()
    total_records = len(total)
    offset = (page - 1) * limit
    results = db.execute(query.offset(offset).limit(limit)).scalars().all()

    return {
        "data": [
            {
                "li_item_id": row.li_item_id,
                "drug_name": row.drug_name,
                "brand_name": row.brand_name,
                "pbs_code": row.pbs_code,
                "program_code": row.program_code,
                "benefit_type_code": row.benefit_type_code,
                "determined_price": row.determined_price,
                "first_listed_date": row.first_listed_date,
            }
            for row in results
        ],
        "_meta": {
            "total_records": total_records,
            "page": page,
            "limit": limit,
            "total_pages": (total_records + limit - 1) // limit,
        },
    }


@router.get("/{li_item_id}")
def get_item(li_item_id: str, db: Session = Depends(get_db)) -> dict | None:
    row = db.execute(select(Item).where(Item.li_item_id == li_item_id)).scalar_one_or_none()
    if row is None:
        return None
    return {
        "li_item_id": row.li_item_id,
        "drug_name": row.drug_name,
        "brand_name": row.brand_name,
        "pbs_code": row.pbs_code,
        "program_code": row.program_code,
        "benefit_type_code": row.benefit_type_code,
        "determined_price": row.determined_price,
        "first_listed_date": row.first_listed_date,
    }
