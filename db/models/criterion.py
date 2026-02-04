from __future__ import annotations

from sqlalchemy import Column, String, TIMESTAMP

from db.base import Base


class Criterion(Base):
    __tablename__ = "criterion"

    schedule_code = Column(String(20), primary_key=True)
    criteria_prescribing_txt_id = Column(String(50), primary_key=True)
    criteria_type = Column(String(100))
    parameter_relationship = Column(String(10))
    created_at = Column(TIMESTAMP)
