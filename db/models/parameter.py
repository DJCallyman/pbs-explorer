from __future__ import annotations

from sqlalchemy import Column, String, TIMESTAMP

from db.base import Base


class Parameter(Base):
    __tablename__ = "parameter"

    schedule_code = Column(String(20), primary_key=True)
    parameter_prescribing_txt_id = Column(String(50), primary_key=True)
    assessment_type = Column(String(20))
    parameter_type = Column(String(50))
    created_at = Column(TIMESTAMP)
