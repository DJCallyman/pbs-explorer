from __future__ import annotations

from sqlalchemy import Column, Numeric, String, TIMESTAMP

from db.base import Base


class Copayment(Base):
    __tablename__ = "copayment"

    schedule_code = Column(String(20), primary_key=True)
    general = Column(Numeric(10, 2))
    concessional = Column(Numeric(10, 2))
    safety_net_general = Column(Numeric(10, 2))
    safety_net_concessional = Column(Numeric(10, 2))
    safety_net_card_issue = Column(Numeric(10, 2))
    increased_discount_limit = Column(Numeric(10, 2))
    safety_net_ctg_contribution = Column(Numeric(10, 2))
    created_at = Column(TIMESTAMP)
