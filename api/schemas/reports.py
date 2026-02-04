from __future__ import annotations

from typing import List

from pydantic import BaseModel


class ReportRow(BaseModel):
    label: str
    value: int


class ReportOut(BaseModel):
    data: List[ReportRow]
