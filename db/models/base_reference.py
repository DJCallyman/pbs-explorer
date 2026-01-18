from __future__ import annotations

from sqlalchemy import Column, String, TIMESTAMP, Text

from db.base import Base


class BaseReference(Base):
    __tablename__ = "base_reference"

    id = Column(String(200), primary_key=True)
    endpoint = Column(String(100), nullable=False)
    schedule_code = Column(String(20), nullable=True)
    data = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP)
