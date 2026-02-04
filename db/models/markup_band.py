from __future__ import annotations

from sqlalchemy import Column, Numeric, String, TIMESTAMP, PrimaryKeyConstraint

from db.base import Base


class MarkupBand(Base):
    __tablename__ = "markup_band"
    __table_args__ = (
        PrimaryKeyConstraint('schedule_code', 'program_code', 'dispensing_rule_mnem', 'markup_band_code', 'limit'),
    )

    schedule_code = Column(String(20), nullable=False)
    program_code = Column(String(10), nullable=False)
    dispensing_rule_mnem = Column(String(100), nullable=False)
    markup_band_code = Column(String(50), nullable=False)
    limit = Column(Numeric(15, 4), nullable=False)
    variable = Column(Numeric(12, 2))
    offset = Column(Numeric(12, 2))
    fixed = Column(Numeric(15, 4))
    created_at = Column(TIMESTAMP)
