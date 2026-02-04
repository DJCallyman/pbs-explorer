from __future__ import annotations

from sqlalchemy import Column, Integer, Numeric, String, PrimaryKeyConstraint

from db.base import Base


class ItemAtcRelationship(Base):
    __tablename__ = "item_atc_relationships"
    __table_args__ = (
        PrimaryKeyConstraint('atc_code', 'pbs_code', 'schedule_code'),
    )

    atc_code = Column(String(20), nullable=False)
    pbs_code = Column(String(20), nullable=False)
    schedule_code = Column(String(20), nullable=False)
    atc_priority_pct = Column(String(10))


class ItemRestrictionRelationship(Base):
    __tablename__ = "item_restriction_relationships"
    __table_args__ = (
        PrimaryKeyConstraint('res_code', 'pbs_code', 'schedule_code'),
    )

    res_code = Column(String(100), nullable=False)
    pbs_code = Column(String(20), nullable=False)
    schedule_code = Column(String(20), nullable=False)
    benefit_type_code = Column(String(1))
    restriction_indicator = Column(String(1))
    res_position = Column(Integer)


class ItemOrganisationRelationship(Base):
    __tablename__ = "item_organisation_relationships"
    __table_args__ = (
        PrimaryKeyConstraint('pbs_code', 'organisation_id', 'schedule_code'),
    )

    pbs_code = Column(String(20), nullable=False)
    organisation_id = Column(String(20), nullable=False)
    schedule_code = Column(String(20), nullable=False)


class RestrictionPrescribingTextRelationship(Base):
    __tablename__ = "restriction_prescribing_text_relationships"
    __table_args__ = (
        PrimaryKeyConstraint('res_code', 'prescribing_text_id', 'schedule_code'),
    )

    res_code = Column(String(100), nullable=False)
    prescribing_text_id = Column(Integer, nullable=False)
    schedule_code = Column(String(20), nullable=False)
    pt_position = Column(Integer)


class ItemPrescribingTextRelationship(Base):
    __tablename__ = "item_prescribing_text_relationships"
    __table_args__ = (
        PrimaryKeyConstraint('pbs_code', 'prescribing_txt_id', 'schedule_code'),
    )

    pbs_code = Column(String(20), nullable=False)
    prescribing_txt_id = Column(String(50), nullable=False)
    schedule_code = Column(String(20), nullable=False)
    pt_position = Column(Integer)


class ItemDispensingRuleRelationship(Base):
    __tablename__ = "item_dispensing_rule_relationships"
    __table_args__ = (
        PrimaryKeyConstraint('li_item_id', 'dispensing_rule_reference', 'schedule_code'),
    )

    schedule_code = Column(String(20), nullable=False)
    li_item_id = Column(String(100), nullable=False)
    dispensing_rule_mnem = Column(String(100))
    dispensing_rule_reference = Column(String(100), nullable=False)
    brand_premium = Column(Numeric(10, 2))
    dispense_fee_type_code = Column(String(10))
    dangerous_drug_fee_code = Column(String(10))
    therapeutic_group_premium = Column(Numeric(10, 2))
    cmnwlth_price_to_pharmacist = Column(Numeric(12, 2))
    man_price_to_pharmacist = Column(Numeric(12, 2))
    man_dispnsd_price_max_qty = Column(Numeric(12, 2))
    max_record_val_for_safety_net = Column(Numeric(12, 2))
    cmnwlth_dsp_price_max_qty = Column(Numeric(12, 2))
    tgm_price_phrmcst = Column(Numeric(12, 2))
    tgm_disp_price_max_qty = Column(Numeric(12, 2))
    special_patient_contribution = Column(Numeric(10, 2))
    fee_dispensing = Column(Numeric(10, 2))
    fee_dispensing_ex = Column(Numeric(10, 2))
    fee_dispensing_dd = Column(Numeric(10, 2))
    fee_water = Column(Numeric(10, 2))
    fee_container_injectable = Column(Numeric(10, 2))
    fee_container_other = Column(Numeric(10, 2))
    fee_safety_net_recording = Column(Numeric(10, 2))
    fee_safety_net_recording_ex = Column(Numeric(10, 2))
    fee_extra = Column(Numeric(10, 2))
    fee_chemo_flat_wholesale = Column(Numeric(10, 2))
    fee_chemo_prep = Column(Numeric(10, 2))
    fee_diluent = Column(Numeric(10, 2))
    submitted_pharmacists_pack_price = Column(Numeric(12, 2))
    max_general_patient_charge = Column(Numeric(10, 2))
    mn_price_dispenser = Column(Numeric(12, 2))
    mn_price_wholesale_markup_limit = Column(Numeric(12, 2))
    mn_price_wholesale_markup_code = Column(String(10))
    mn_price_wholesale_markup = Column(Numeric(10, 4))
    mn_pharmacy_price = Column(Numeric(12, 2))
    mn_pharmacy_markup_limit = Column(Numeric(12, 2))
    mn_pharmacy_markup_code = Column(String(10))
    mn_pharmacy_markup = Column(Numeric(10, 4))


class CriteriaParameterRelationship(Base):
    __tablename__ = "criteria_parameter_relationships"
    __table_args__ = (
        PrimaryKeyConstraint('criteria_prescribing_txt_id', 'parameter_prescribing_txt_id', 'schedule_code'),
    )

    schedule_code = Column(String(20), nullable=False)
    criteria_prescribing_txt_id = Column(String(50), nullable=False)
    parameter_prescribing_txt_id = Column(String(50), nullable=False)
    pt_position = Column(Integer)


class ContainerOrganisationRelationship(Base):
    __tablename__ = "container_organisation_relationships"
    __table_args__ = (
        PrimaryKeyConstraint('container_code', 'organisation_id', 'schedule_code'),
    )

    container_code = Column(String(20), nullable=False)
    organisation_id = Column(String(20), nullable=False)
    schedule_code = Column(String(20), nullable=False)


class ExtPrepSfpRelationship(Base):
    __tablename__ = "extemporaneous_prep_sfp_relationships"
    __table_args__ = (
        PrimaryKeyConstraint('sfp_pbs_code', 'ex_prep_pbs_code', 'schedule_code'),
    )

    schedule_code = Column(String(20), nullable=False)
    sfp_pbs_code = Column(String(50), nullable=False)
    ex_prep_pbs_code = Column(String(50), nullable=False)


class ProgramDispensingRule(Base):
    __tablename__ = "program_dispensing_rules"
    __table_args__ = (
        PrimaryKeyConstraint('program_code', 'dispensing_rule_mnem', 'schedule_code'),
    )

    program_code = Column(String(10), nullable=False)
    dispensing_rule_mnem = Column(String(100), nullable=False)
    default_indicator = Column(String(1))
    schedule_code = Column(String(20), nullable=False)
