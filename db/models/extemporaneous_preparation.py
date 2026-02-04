from __future__ import annotations

from sqlalchemy import Column, String, TIMESTAMP

from db.base import Base


class ExtemporaneousPreparation(Base):
    __tablename__ = "extemporaneous_preparation"

    schedule_code = Column(String(20), primary_key=True)
    preparation = Column(String(500), primary_key=True)
    pbs_code = Column(String(50), primary_key=True)
    maximum_quantity = Column(String(50))
    maximum_quantity_unit = Column(String(50))
    created_at = Column(TIMESTAMP)
