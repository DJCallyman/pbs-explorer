from __future__ import annotations

from sqlalchemy import Column, String, TIMESTAMP

from db.base import Base


class WebSession(Base):
    __tablename__ = "web_session"

    session_id = Column(String(255), primary_key=True)
    username = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False)
    source = Column(String(20), nullable=False)
    created_at = Column(TIMESTAMP)
    last_seen_at = Column(TIMESTAMP)
    expires_at = Column(TIMESTAMP)
    revoked_at = Column(TIMESTAMP)
