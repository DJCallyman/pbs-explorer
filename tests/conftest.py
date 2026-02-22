"""Shared test fixtures.

Provides an in-memory SQLite database and a FastAPI ``TestClient``
so that every test runs against an isolated, empty database.
"""
from __future__ import annotations

from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from db.base import Base
import db.models  # noqa: F401 — register ALL models with Base.metadata
from db.models import Item, Restriction, ATCCode, Organisation, Schedule
from api.deps import get_db
from main import create_app

# In-memory SQLite shared across a single test session.
# StaticPool ensures every connection shares the same underlying database
# so that tables created in fixtures are visible to the app under test.
_TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSession = sessionmaker(bind=_TEST_ENGINE, autoflush=False, autocommit=False)


@pytest.fixture(autouse=True)
def _setup_tables():
    """Create all tables before each test and drop them afterwards."""
    Base.metadata.create_all(bind=_TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=_TEST_ENGINE)


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    """Yield a database session that rolls back after each test."""
    session = _TestSession()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def client(db: Session) -> TestClient:
    """FastAPI test client wired to the in-memory test database."""
    app = create_app()

    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app, raise_server_exceptions=False)


# ── Seed-data helpers ──


def seed_items(db: Session, count: int = 3) -> list[Item]:
    """Insert ``count`` test items into the database."""
    items = []
    for i in range(1, count + 1):
        item = Item(
            li_item_id=f"TEST-{i:04d}",
            drug_name=f"TestDrug{i}",
            brand_name=f"Brand{i}",
            pbs_code=f"PBS{i:04d}",
            program_code="GE",
            benefit_type_code="S",
            schedule_code="9999",
        )
        db.add(item)
        items.append(item)
    db.commit()
    return items


def seed_restrictions(db: Session, count: int = 3) -> list[Restriction]:
    items = []
    for i in range(1, count + 1):
        r = Restriction(
            res_code=f"RES-{i:04d}",
            restriction_number=i,
            authority_method="STREAMLINED",
            schedule_code="9999",
        )
        db.add(r)
        items.append(r)
    db.commit()
    return items


def seed_atc_codes(db: Session, count: int = 3) -> list[ATCCode]:
    items = []
    for i in range(1, count + 1):
        a = ATCCode(
            atc_code=f"A{i:02d}",
            atc_description=f"Description {i}",
            atc_level=i,
            schedule_code="9999",
        )
        db.add(a)
        items.append(a)
    db.commit()
    return items


def seed_schedules(db: Session, count: int = 3) -> list[Schedule]:
    items = []
    for i in range(1, count + 1):
        s = Schedule(
            schedule_code=f"SC-{i:04d}",
            effective_year=2025,
            effective_month=f"{i:02d}",
        )
        db.add(s)
        items.append(s)
    db.commit()
    return items


def seed_organisations(db: Session, count: int = 3) -> list[Organisation]:
    items = []
    for i in range(1, count + 1):
        o = Organisation(
            organisation_id=i,
            name=f"Org{i}",
            city="Sydney",
            state="NSW",
            postcode="2000",
            schedule_code="9999",
        )
        db.add(o)
        items.append(o)
    db.commit()
    return items
