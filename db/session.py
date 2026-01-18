from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config import get_settings


_engine = None
_SessionLocal = None


def _build_sqlalchemy_url() -> str:
    settings = get_settings()
    db = settings.database
    if db.type == "sqlite":
        return f"sqlite:///{db.path}"
    if db.type == "postgresql":
        return (
            f"postgresql+psycopg2://{db.username}:{db.password}"
            f"@{db.host}:{db.port}/{db.database}"
        )
    raise ValueError(f"Unsupported database type: {db.type}")


def get_database_url() -> str:
    return _build_sqlalchemy_url()


def init_engine() -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        return
    database_url = _build_sqlalchemy_url()
    _engine = create_engine(database_url, pool_pre_ping=True, future=True)
    _SessionLocal = sessionmaker(bind=_engine, class_=Session, autoflush=False, autocommit=False)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    if _engine is None:
        init_engine()
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()
