from __future__ import annotations

from sqlalchemy import Column, Numeric, String, TIMESTAMP, PrimaryKeyConstraint

from db.base import Base


class ItemPricingEvent(Base):
    __tablename__ = "item_pricing_event"
    __table_args__ = (
        PrimaryKeyConstraint('schedule_code', 'li_item_id', 'event_type_code'),
    )

    schedule_code = Column(String(20), nullable=False)
    li_item_id = Column(String(100), nullable=False)
    event_type_code = Column(String(50), nullable=False)
    percentage_applied = Column(Numeric(10, 4))
    created_at = Column(TIMESTAMP)
