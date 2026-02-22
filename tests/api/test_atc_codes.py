"""Tests for /api/v1/atc-codes endpoints."""
from __future__ import annotations

from tests.conftest import seed_atc_codes


def test_list_atc_codes_empty(client):
    resp = client.get("/api/v1/atc-codes")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


def test_list_atc_codes_with_data(client, db):
    seed_atc_codes(db, 3)
    resp = client.get("/api/v1/atc-codes")
    assert resp.status_code == 200
    assert resp.json()["_meta"]["total_records"] == 3


def test_get_atc_code_found(client, db):
    seed_atc_codes(db, 1)
    resp = client.get("/api/v1/atc-codes/A01")
    assert resp.status_code == 200
    assert resp.json()["atc_code"] == "A01"


def test_get_atc_code_not_found(client):
    resp = client.get("/api/v1/atc-codes/NONEXISTENT")
    assert resp.status_code == 404
