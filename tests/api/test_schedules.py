"""Tests for /api/v1/schedules endpoints."""
from __future__ import annotations

from tests.conftest import seed_schedules


def test_list_schedules_empty(client):
    resp = client.get("/api/v1/schedules")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


def test_list_schedules_with_data(client, db):
    seed_schedules(db, 3)
    resp = client.get("/api/v1/schedules")
    assert resp.status_code == 200
    assert resp.json()["_meta"]["total_records"] == 3


def test_get_schedule_found(client, db):
    seed_schedules(db, 1)
    resp = client.get("/api/v1/schedules/SC-0001")
    assert resp.status_code == 200
    assert resp.json()["schedule_code"] == "SC-0001"


def test_get_schedule_not_found(client):
    resp = client.get("/api/v1/schedules/NONEXISTENT")
    assert resp.status_code == 404
