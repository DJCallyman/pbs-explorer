from __future__ import annotations

from sqlalchemy import Column, Integer, String, TIMESTAMP

from db.base import Base


class Indication(Base):
    __tablename__ = "indication"

    indication_prescribing_txt_id = Column(Integer, primary_key=True)
    condition = Column(String(500))
    episodicity = Column(String(100))
    severity = Column(String(100))
    schedule_code = Column(String(20))
    created_at = Column(TIMESTAMP)
