"""Tests for /api/v1/items endpoints."""
from __future__ import annotations

from tests.conftest import seed_items


def test_list_items_empty(client):
    resp = client.get("/api/v1/items")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == []
    assert body["_meta"]["total_records"] == 0


def test_list_items_with_data(client, db):
    seed_items(db, 5)
    resp = client.get("/api/v1/items")
    assert resp.status_code == 200
    body = resp.json()
    assert body["_meta"]["total_records"] == 5
    assert len(body["data"]) == 5


def test_list_items_pagination(client, db):
    seed_items(db, 5)
    resp = client.get("/api/v1/items?page=1&limit=2")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 2
    assert body["_meta"]["total_records"] == 5
    assert body["_meta"]["total_pages"] == 3


def test_list_items_filter_drug_name(client, db):
    seed_items(db, 3)
    resp = client.get("/api/v1/items?drug_name=TestDrug1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["_meta"]["total_records"] == 1
    assert body["data"][0]["drug_name"] == "TestDrug1"


def test_list_items_filter_program_code(client, db):
    seed_items(db, 3)
    resp = client.get("/api/v1/items?program_code=GE")
    assert resp.status_code == 200
    assert resp.json()["_meta"]["total_records"] == 3


def test_get_item_found(client, db):
    seed_items(db, 1)
    resp = client.get("/api/v1/items/TEST-0001")
    assert resp.status_code == 200
    assert resp.json()["li_item_id"] == "TEST-0001"


def test_get_item_not_found(client):
    resp = client.get("/api/v1/items/NONEXISTENT")
    assert resp.status_code == 404
