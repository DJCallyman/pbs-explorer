from __future__ import annotations

from sqlalchemy import Column, Date, Integer, String, TIMESTAMP

from db.base import Base


class Schedule(Base):
    __tablename__ = "schedule"

    schedule_code = Column(String(20), primary_key=True)
    effective_date = Column(Date)
    effective_month = Column(String(20))
    effective_year = Column(Integer)
    start_tsp = Column(TIMESTAMP)
    revision_number = Column(Integer)
    publication_status = Column(String(20))
    last_synced_at = Column(TIMESTAMP)
