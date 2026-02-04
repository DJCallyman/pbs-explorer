from __future__ import annotations

from sqlalchemy import Column, Numeric, String, TIMESTAMP

from db.base import Base


class StandardFormulaPreparation(Base):
    __tablename__ = "standard_formula_preparation"

    schedule_code = Column(String(20), primary_key=True)
    pbs_code = Column(String(50), primary_key=True)
    sfp_drug_name = Column(String(500))
    sfp_reference = Column(String(500))
    container_fee = Column(Numeric(10, 4))
    dispensing_fee_max_quantity = Column(Numeric(10, 4))
    safety_net_price = Column(Numeric(10, 4))
    maximum_patient_charge = Column(Numeric(10, 4))
    maximum_quantity_unit = Column(String(50))
    maximum_quantity = Column(String(50))
    created_at = Column(TIMESTAMP)
