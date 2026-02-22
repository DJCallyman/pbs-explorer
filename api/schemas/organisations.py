from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class OrganisationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    organisation_id: int
    name: Optional[str] = None
    abn: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postcode: Optional[str] = None

