from __future__ import annotations

from sqlalchemy import Column, Numeric, String, TIMESTAMP

from db.base import Base


class ExtemporaneousIngredient(Base):
    __tablename__ = "extemporaneous_ingredient"

    pbs_code = Column(String(50), primary_key=True)
    schedule_code = Column(String(20), primary_key=True)
    agreed_purchasing_unit = Column(String(50))
    exact_tenth_gram_per_ml_price = Column(Numeric(15, 4))
    exact_one_gram_per_ml_price = Column(Numeric(15, 4))
    exact_ten_gram_per_ml_price = Column(Numeric(15, 4))
    exact_hundred_gram_per_ml_price = Column(Numeric(15, 4))
    rounded_tenth_gram_per_ml_price = Column(Numeric(15, 4))
    rounded_one_gram_per_ml_price = Column(Numeric(15, 4))
    rounded_ten_gram_per_ml_price = Column(Numeric(15, 4))
    rounded_hundred_gram_per_ml_price = Column(Numeric(15, 4))
    created_at = Column(TIMESTAMP)
