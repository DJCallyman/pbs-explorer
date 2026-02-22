from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class RestrictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    res_code: str
    schedule_code: Optional[str] = None
    restriction_number: Optional[int] = None
    authority_method: Optional[str] = None

