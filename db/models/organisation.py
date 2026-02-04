from __future__ import annotations

from sqlalchemy import Column, Integer, String, TIMESTAMP

from db.base import Base


class Organisation(Base):
    __tablename__ = "organisation"

    organisation_id = Column(Integer, primary_key=True)
    name = Column(String(500))
    abn = Column(String(20))
    street_address = Column(String(500))
    city = Column(String(200))
    state = Column(String(100))
    postcode = Column(String(20))
    telephone_number = Column(String(50))
    facsimile_number = Column(String(50))
    created_at = Column(TIMESTAMP)
