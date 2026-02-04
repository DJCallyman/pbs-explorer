from __future__ import annotations

from sqlalchemy import Column, Integer, String, TIMESTAMP

from db.base import Base


class ATCCode(Base):
    __tablename__ = "atc_code"

    atc_code = Column(String(20), primary_key=True)
    atc_description = Column(String(500))
    atc_level = Column(Integer)
    atc_parent_code = Column(String(20))
    schedule_code = Column(String(20))
    created_at = Column(TIMESTAMP)
