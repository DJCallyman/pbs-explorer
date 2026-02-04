from __future__ import annotations

from sqlalchemy import Column, Integer, String, TIMESTAMP

from db.base import Base


class PrescribingText(Base):
    __tablename__ = "prescribing_text"

    prescribing_txt_id = Column(Integer, primary_key=True)
    prescribing_txt = Column(String)
    prescribing_type = Column(String(100))
    complex_authority_rqrd_ind = Column(String(1))
    assessment_type_code = Column(String(50))
    apply_to_increase_mq_flag = Column(String(1))
    apply_to_increase_nr_flag = Column(String(1))
    created_at = Column(TIMESTAMP)
