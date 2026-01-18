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

    li_item_id = Column(String(100), primary_key=True)
    res_code = Column(String(100), primary_key=True)
    schedule_code = Column(String(20), primary_key=True)
    res_position = Column(Integer)


class ItemOrganisationRelationship(Base):
    __tablename__ = "item_organisation_relationship"

    li_item_id = Column(String(100), primary_key=True)
    organisation_id = Column(Integer, primary_key=True)
    schedule_code = Column(String(20), primary_key=True)
