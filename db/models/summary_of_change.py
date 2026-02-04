from __future__ import annotations

from sqlalchemy import Column, Integer, String, TIMESTAMP, Text, PrimaryKeyConstraint

from db.base import Base


class SummaryOfChange(Base):
    __tablename__ = "summary_of_change"
    __table_args__ = (
        PrimaryKeyConstraint('schedule_code', 'source_schedule_code', 'changed_table', 'table_keys'),
    )

    schedule_code = Column(String(20), nullable=False)
    source_schedule_code = Column(String(20), nullable=False)
    changed_table = Column(String(50), nullable=False)
    table_keys = Column(Text, nullable=False)
    target_effective_date = Column(String(20))
    source_effective_date = Column(String(20))
    target_revision_number = Column(Integer)
    source_revision_number = Column(Integer)
    target_publication_status = Column(String(20))
    source_publication_status = Column(String(20))
    changed_endpoint = Column(String(100))
    change_type = Column(String(10))  # UPDATE, INSERT, DELETE
    sql_statement = Column(Text)
    change_detail = Column(Text)
    previous_detail = Column(Text)
    deleted_ind = Column(String(1))
    new_ind = Column(String(1))
    modified_ind = Column(String(1))
    created_at = Column(TIMESTAMP)
