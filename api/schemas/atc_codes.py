from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class ATCCodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    atc_code: str
    atc_description: Optional[str] = None
    atc_level: Optional[int] = None
    atc_parent_code: Optional[str] = None

