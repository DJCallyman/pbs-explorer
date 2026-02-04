from __future__ import annotations

from sqlalchemy import Column, String, TIMESTAMP, Text

from db.base import Base


class Program(Base):
    __tablename__ = "program"

    program_code = Column(String(10), primary_key=True)
    schedule_code = Column(String(20), primary_key=True)
    program_title = Column(String(400))
    created_at = Column(TIMESTAMP)
