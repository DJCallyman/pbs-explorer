from __future__ import annotations

from sqlalchemy import Column, Date, Integer, Numeric, String, TIMESTAMP

from db.base import Base


class Container(Base):
    __tablename__ = "container"

    container_code = Column(String(20), primary_key=True)
    schedule_code = Column(String(20), primary_key=True)
    container_name = Column(String(500))
    mark_up = Column(Numeric(10, 4))
    agreed_purchasing_unit = Column(String(50))
    average_exact_unit_price = Column(Numeric(15, 8))
    average_rounded_unit_price = Column(Numeric(15, 8))
    container_type = Column(String(100))
    container_quantity = Column(String(50))
    container_unit_of_measure = Column(String(50))
    created_at = Column(TIMESTAMP)
