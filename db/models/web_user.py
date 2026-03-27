from __future__ import annotations

from sqlalchemy import Column, String, TIMESTAMP

from db.base import Base


class WebUser(Base):
    __tablename__ = "web_user"

    username = Column(String(100), primary_key=True)
    role = Column(String(20), nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP)
    updated_at = Column(TIMESTAMP)
