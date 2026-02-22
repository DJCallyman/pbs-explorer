"""Tests for /api/v1/restrictions endpoints."""
from __future__ import annotations

from tests.conftest import seed_restrictions


def test_list_restrictions_empty(client):
    resp = client.get("/api/v1/restrictions")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


def test_list_restrictions_with_data(client, db):
    seed_restrictions(db, 3)
    resp = client.get("/api/v1/restrictions")
    assert resp.status_code == 200
    assert resp.json()["_meta"]["total_records"] == 3


def test_list_restrictions_pagination(client, db):
    seed_restrictions(db, 5)
    resp = client.get("/api/v1/restrictions?page=2&limit=2")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 2
    assert body["_meta"]["total_pages"] == 3


def test_get_restriction_found(client, db):
    seed_restrictions(db, 1)
    resp = client.get("/api/v1/restrictions/RES-0001")
    assert resp.status_code == 200
    assert resp.json()["res_code"] == "RES-0001"


def test_get_restriction_not_found(client):
    resp = client.get("/api/v1/restrictions/NONEXISTENT")
    assert resp.status_code == 404
