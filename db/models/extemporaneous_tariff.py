from __future__ import annotations

from sqlalchemy import Column, Numeric, String, TIMESTAMP

from db.base import Base


class ExtemporaneousTariff(Base):
    __tablename__ = "extemporaneous_tariff"

    pbs_code = Column(String(50), primary_key=True)
    schedule_code = Column(String(20), primary_key=True)
    drug_name = Column(String(500))
    agreed_purchasing_unit = Column(String(50))
    markup = Column(Numeric(10, 4))
    rounded_rec_one_tenth_gram = Column(Numeric(15, 4))
    rounded_rec_one_gram = Column(Numeric(15, 4))
    rounded_rec_ten_gram = Column(Numeric(15, 4))
    rounded_rec_hundred_gram = Column(Numeric(15, 4))
    exact_rec_one_tenth_gram = Column(Numeric(15, 4))
    exact_rec_one_gram = Column(Numeric(15, 4))
    exact_rec_ten_gram = Column(Numeric(15, 4))
    exact_rec_hundred_gram = Column(Numeric(15, 4))
    created_at = Column(TIMESTAMP)
