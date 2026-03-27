from __future__ import annotations

from sqlalchemy import Column, String, Text, TIMESTAMP

from db.base import Base


class SavedReport(Base):
    __tablename__ = "saved_report"

    slug = Column(String(200), primary_key=True)
    owner = Column(String(100))
    name = Column(String(255))
    description = Column(Text)
    report_json = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP)
    updated_at = Column(TIMESTAMP)
