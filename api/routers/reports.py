from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.deps import get_db
from services.reports import (
    items_by_atc_level,
    items_by_benefit_type,
    items_by_program,
    price_changes,
    restriction_changes,
)

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/items-by-program")
def report_items_by_program(db: Session = Depends(get_db)) -> dict:
    """Get count of items grouped by program code."""
    return {"data": items_by_program(db)}


@router.get("/items-by-benefit-type")
def report_items_by_benefit_type(db: Session = Depends(get_db)) -> dict:
    """Get count of items grouped by benefit type code."""
    return {"data": items_by_benefit_type(db)}


@router.get("/items-by-atc-level")
def report_items_by_atc_level(db: Session = Depends(get_db)) -> dict:
    """Get count of ATC codes grouped by level."""
    return {"data": items_by_atc_level(db)}


@router.get("/price-changes")
def report_price_changes(db: Session = Depends(get_db)) -> dict:
    """Get items with recent price changes based on schedule changes."""
    return {"data": price_changes(db)}


@router.get("/restriction-changes")
def report_restriction_changes(db: Session = Depends(get_db)) -> dict:
    """Get restriction changes from summary of changes."""
    return {"data": restriction_changes(db)}
