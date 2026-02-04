from __future__ import annotations

from sqlalchemy import Column, String, TIMESTAMP

from db.base import Base


class Prescriber(Base):
    __tablename__ = "prescriber"

    pbs_code = Column(String(50), primary_key=True)
    prescriber_code = Column(String(10), primary_key=True)
    schedule_code = Column(String(20), primary_key=True)
    prescriber_type = Column(String(100))
    created_at = Column(TIMESTAMP)
