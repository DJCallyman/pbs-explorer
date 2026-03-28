from __future__ import annotations

from sqlalchemy import Column, Numeric, String, TIMESTAMP

from db.base import Base


class Fee(Base):
    __tablename__ = "fee"

    schedule_code = Column(String(20), primary_key=True)
    program_code = Column(String(10), primary_key=True)
    dispensing_fee_ready_prepared = Column(Numeric(10, 2))
    dispensing_fee_dangerous_drug = Column(Numeric(10, 2))
    dispensing_fee_extra = Column(Numeric(10, 2))
    dispensing_fee_extemporaneous = Column(Numeric(10, 2))
    safety_net_recording_fee_ep = Column(Numeric(10, 2))
    safety_net_recording_fee_rp = Column(Numeric(10, 2))
    dispensing_fee_water_added = Column(Numeric(10, 2))
    container_fee_injectable = Column(Numeric(10, 2))
    container_fee_other = Column(Numeric(10, 2))
    gnrl_copay_discount_general = Column(Numeric(10, 2))
    gnrl_copay_discount_hospital = Column(Numeric(10, 2))
    con_copay_discount_general = Column(Numeric(10, 2))
    con_copay_discount_hospital = Column(Numeric(10, 2))
    efc_diluent_fee = Column(Numeric(10, 2))
    efc_preparation_fee = Column(Numeric(10, 2))
    efc_distribution_fee = Column(Numeric(10, 2))
    acss_imdq60_payment = Column(Numeric(10, 2))
    acss_payment = Column(Numeric(10, 2))
    created_at = Column(TIMESTAMP)
