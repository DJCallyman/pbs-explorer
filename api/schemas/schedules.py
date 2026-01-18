from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel


class ScheduleOut(BaseModel):
    schedule_code: str
    effective_date: Optional[date] = None
    effective_month: Optional[str] = None
    effective_year: Optional[int] = None
    publication_status: Optional[str] = None

    class Config:
        orm_mode = True
