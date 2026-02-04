from __future__ import annotations

from sqlalchemy import Column, String, TIMESTAMP

from db.base import Base


class DispensingRule(Base):
    __tablename__ = "dispensing_rule"

    schedule_code = Column(String(20), primary_key=True)
    dispensing_rule_mnem = Column(String(100), primary_key=True)
    dispensing_rule_reference = Column(String(100), primary_key=True)
    dispensing_rule_title = Column(String(200))
    community_pharmacy_indicator = Column(String(10))
    created_at = Column(TIMESTAMP)
