from __future__ import annotations

from sqlalchemy import Column, Integer, Numeric, String, TIMESTAMP

from db.base import Base


class Copayment(Base):
    __tablename__ = "copayment"

    id = Column(Integer, primary_key=True)
    schedule_code = Column(String(20))
    general = Column(Numeric(10, 2))
    concessional = Column(Numeric(10, 2))
    safety_net_general = Column(Numeric(10, 2))
    safety_net_concessional = Column(Numeric(10, 2))
    safety_net_card_issue = Column(Numeric(10, 2))
    increased_discount_limit = Column(Numeric(10, 2))
    safety_net_ctg_contribution = Column(Numeric(10, 2))
    created_at = Column(TIMESTAMP)
