from __future__ import annotations

from sqlalchemy import Column, String, TIMESTAMP

from db.base import Base


class AppSetting(Base):
    __tablename__ = "app_setting"

    key = Column(String(100), primary_key=True)
    value = Column(String(500))
    updated_at = Column(TIMESTAMP)
