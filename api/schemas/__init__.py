"""Pydantic schemas."""

from __future__ import annotations

from typing import Generic, List, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class PaginationMeta(BaseModel):
    total_records: int
    page: int
    limit: int
    total_pages: int


class PaginatedResponse(BaseModel, Generic[T]):
    data: List[T]
    _meta: PaginationMeta

    model_config = ConfigDict(populate_by_name=True)
