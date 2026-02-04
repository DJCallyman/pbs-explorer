from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class RestrictionOut(BaseModel):
    res_code: str
    schedule_code: Optional[str] = None
    restriction_number: Optional[int] = None
    authority_method: Optional[str] = None

    class Config:
        orm_mode = True
