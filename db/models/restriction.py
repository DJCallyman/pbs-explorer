from __future__ import annotations

from sqlalchemy import Column, Date, Integer, String, TIMESTAMP

from db.base import Base


class Restriction(Base):
    __tablename__ = "restriction"

    res_code = Column(String(100), primary_key=True)
    schedule_code = Column(String(20), primary_key=True)
    restriction_number = Column(Integer)
    treatment_of_code = Column(Integer)
    authority_method = Column(String(50))
    treatment_phase = Column(String(100))
    note_indicator = Column(String(1))
    caution_indicator = Column(String(1))
    complex_authority_rqrd_ind = Column(String(1))
    assessment_type_code = Column(String(50))
    criteria_relationship = Column(String(10))
    variation_rule_applied = Column(String(1))
    first_listing_date = Column(Date)
    written_authority_required = Column(String(1))
    created_at = Column(TIMESTAMP)
    updated_at = Column(TIMESTAMP)
