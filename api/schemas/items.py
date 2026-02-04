from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel


class ItemOut(BaseModel):
    li_item_id: str
    schedule_code: Optional[str] = None
    drug_name: Optional[str] = None
    brand_name: Optional[str] = None
    pbs_code: Optional[str] = None
    program_code: Optional[str] = None
    benefit_type_code: Optional[str] = None
    determined_price: Optional[float] = None
    first_listed_date: Optional[date] = None

    class Config:
        orm_mode = True
