from __future__ import annotations

from sqlalchemy import Column, String, TIMESTAMP, PrimaryKeyConstraint

from db.base import Base


class AMTItem(Base):
    __tablename__ = "amt_item"
    __table_args__ = (
        PrimaryKeyConstraint('pbs_concept_id', 'schedule_code', 'li_item_id'),
    )

    pbs_concept_id = Column(String(50), nullable=False)
    schedule_code = Column(String(20), nullable=False)
    li_item_id = Column(String(100), nullable=False)
    concept_type_code = Column(String(20))
    amt_code = Column(String(50))
    preferred_term = Column(String(500))
    exempt_ind = Column(String(1))
    non_amt_code = Column(String(50))
    pbs_preferred_term = Column(String(500))
    created_at = Column(TIMESTAMP)
