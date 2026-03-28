from __future__ import annotations

from sqlalchemy import Column, Index, Integer, String, TIMESTAMP

from db.base import Base


class Indication(Base):
    __tablename__ = "indication"
    __table_args__ = (
        Index("ix_indication_condition", "condition"),
        Index("ix_indication_severity", "severity"),
    )

    indication_prescribing_txt_id = Column(Integer, primary_key=True)
    condition = Column(String(500))
    episodicity = Column(String(100))
    severity = Column(String(100))
    schedule_code = Column(String(20), primary_key=True)
    created_at = Column(TIMESTAMP)
