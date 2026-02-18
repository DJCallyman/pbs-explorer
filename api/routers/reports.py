from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from api.deps import get_db
from db.models import Item, ATCCode, SummaryOfChange

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/items-by-program")
def items_by_program(db: Session = Depends(get_db)) -> dict:
    """Get count of items grouped by program code."""
    result = db.execute(
        select(Item.program_code, func.count(Item.li_item_id).label("count"))
        .group_by(Item.program_code)
        .order_by(func.count(Item.li_item_id).desc())
    ).all()
    
    data = [
        {"program_code": row.program_code, "count": row.count}
        for row in result
    ]
    return {"data": data}


@router.get("/items-by-benefit-type")
def items_by_benefit_type(db: Session = Depends(get_db)) -> dict:
    """Get count of items grouped by benefit type code."""
    result = db.execute(
        select(Item.benefit_type_code, func.count(Item.li_item_id).label("count"))
        .where(Item.benefit_type_code.isnot(None))
        .group_by(Item.benefit_type_code)
        .order_by(func.count(Item.li_item_id).desc())
    ).all()
    
    data = [
        {"benefit_type_code": row.benefit_type_code, "count": row.count}
        for row in result
    ]
    return {"data": data}


@router.get("/items-by-atc-level")
def items_by_atc_level(db: Session = Depends(get_db)) -> dict:
    """Get count of ATC codes grouped by level."""
    result = db.execute(
        select(ATCCode.atc_level, func.count(ATCCode.atc_code).label("count"))
        .where(ATCCode.atc_level.isnot(None))
        .group_by(ATCCode.atc_level)
        .order_by(ATCCode.atc_level)
    ).all()
    
    data = [
        {"atc_level": row.atc_level, "count": row.count}
        for row in result
    ]
    return {"data": data}


@router.get("/price-changes")
def price_changes(db: Session = Depends(get_db)) -> dict:
    """Get items with recent price changes based on schedule changes."""
    # For now, return items sorted by most recently updated
    # This is a placeholder until we have better price change tracking
    result = db.execute(
        select(
            Item.li_item_id,
            Item.drug_name,
            Item.brand_name,
            Item.determined_price,
            Item.updated_at
        )
        .where(Item.updated_at.isnot(None))
        .order_by(Item.updated_at.desc())
        .limit(100)
    ).all()
    
    data = [
        {
            "li_item_id": row.li_item_id,
            "drug_name": row.drug_name,
            "brand_name": row.brand_name,
            "current_price": float(row.determined_price) if row.determined_price else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
        for row in result
    ]
    return {"data": data}


@router.get("/restriction-changes")
def restriction_changes(db: Session = Depends(get_db)) -> dict:
    """Get restriction changes from summary of changes."""
    # Get recent restriction-related changes
    result = db.execute(
        select(
            SummaryOfChange.changed_table,
            SummaryOfChange.table_keys,
            SummaryOfChange.change_type,
            SummaryOfChange.changed_endpoint,
            SummaryOfChange.source_schedule_code,
            SummaryOfChange.schedule_code
        )
        .where(
            SummaryOfChange.changed_endpoint.like('%restriction%')
        )
        .order_by(SummaryOfChange.schedule_code.desc())
        .limit(100)
    ).all()
    
    data = [
        {
            "changed_table": row.changed_table,
            "table_keys": row.table_keys,
            "change_type": row.change_type,
            "changed_endpoint": row.changed_endpoint,
            "from_schedule": row.source_schedule_code,
            "to_schedule": row.schedule_code,
        }
        for row in result
    ]
    return {"data": data}
