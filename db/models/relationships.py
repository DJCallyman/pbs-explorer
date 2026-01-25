from __future__ import annotations

from sqlalchemy import Column, Integer, String

from db.base import Base


class ItemATCRelationship(Base):
    __tablename__ = "item_atc_relationship"

    li_item_id = Column(String(100), primary_key=True)
    atc_code = Column(String(20), primary_key=True)
    schedule_code = Column(String(20), primary_key=True)
    atc_priority_pct = Column(Integer)


class ItemRestrictionRelationship(Base):
    __tablename__ = "item_restriction_relationship"

    pbs_code = Column(String(20), primary_key=True)
    res_code = Column(String(100), primary_key=True)
    schedule_code = Column(String(20), primary_key=True)
    benefit_type_code = Column(String(1))
    restriction_indicator = Column(String(1))
    res_position = Column(Integer)


class ItemOrganisationRelationship(Base):
    __tablename__ = "item_organisation_relationship"

    li_item_id = Column(String(100), primary_key=True)
    organisation_id = Column(Integer, primary_key=True)
    schedule_code = Column(String(20), primary_key=True)


class RestrictionPrescribingTextRelationship(Base):
    __tablename__ = "restriction_prescribing_text_relationship"

    res_code = Column(String(100), primary_key=True)
    prescribing_text_id = Column(Integer, primary_key=True)
    schedule_code = Column(String(20), primary_key=True)
    pt_position = Column(Integer)


class ItemPrescribingTextRelationship(Base):
    __tablename__ = "item_prescribing_text_relationship"

    pbs_code = Column(String(20), primary_key=True)
    prescribing_txt_id = Column(Integer, primary_key=True)
    schedule_code = Column(String(20), primary_key=True)
    pt_position = Column(Integer)
