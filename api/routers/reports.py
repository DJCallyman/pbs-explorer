from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/items-by-program")
def items_by_program() -> dict:
    return {"data": []}


@router.get("/items-by-benefit-type")
def items_by_benefit_type() -> dict:
    return {"data": []}


@router.get("/items-by-atc-level")
def items_by_atc_level() -> dict:
    return {"data": []}


@router.get("/price-changes")
def price_changes() -> dict:
    return {"data": []}


@router.get("/restriction-changes")
def restriction_changes() -> dict:
    return {"data": []}
