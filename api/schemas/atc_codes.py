from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ATCCodeOut(BaseModel):
    atc_code: str
    atc_description: Optional[str] = None
    atc_level: Optional[int] = None
    atc_parent_code: Optional[str] = None

    class Config:
        orm_mode = True
