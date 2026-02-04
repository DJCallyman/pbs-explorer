from __future__ import annotations

from sqlalchemy import Column, String, TIMESTAMP, Integer

from db.base import Base


class SyncState(Base):
    __tablename__ = "sync_state"

    endpoint = Column(String(100), primary_key=True)
    last_synced_schedule_code = Column(String(20))
    last_synced_at = Column(TIMESTAMP)
    records_synced = Column(Integer, default=0)
    records_fetched = Column(Integer, default=0)
    sync_type = Column(String(20))  # 'full' or 'incremental'
