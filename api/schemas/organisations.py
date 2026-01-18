from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class OrganisationOut(BaseModel):
    organisation_id: int
    name: Optional[str] = None
    abn: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postcode: Optional[str] = None

    class Config:
        orm_mode = True
