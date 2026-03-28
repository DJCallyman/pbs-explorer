from __future__ import annotations

from sqlalchemy import Column, Date, Index, String, Text, TIMESTAMP

from db.base import Base


class MedicineStatusEntry(Base):
    __tablename__ = "medicine_status_entry"
    __table_args__ = (
        Index("ix_medicine_status_drug_name_normalized", "drug_name_normalized"),
        Index("ix_medicine_status_meeting_date", "meeting_date"),
    )

    medicine_status_id = Column(String(50), primary_key=True)
    document_url = Column(String(500), nullable=False)
    drug_name = Column(String(500), nullable=False)
    drug_name_normalized = Column(String(500), nullable=False)
    brand_names = Column(Text)
    sponsor = Column(String(500))
    purpose = Column(Text)
    meeting_date = Column(Date)
    meeting_date_label = Column(String(100))
    listing_outcome_status = Column(String(200))
    pbac_meeting_date = Column(Date)
    pbac_outcome_published_text = Column(String(200))
    pbac_outcome_published_url = Column(String(500))
    public_summary_title = Column(String(500))
    public_summary_url = Column(String(500))
    status = Column(String(100))
    page_last_updated = Column(Date)
    last_synced_at = Column(TIMESTAMP)
