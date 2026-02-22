"""Tests for /api/v1/organisations endpoints."""
from __future__ import annotations

from tests.conftest import seed_organisations


def test_list_organisations_empty(client):
    resp = client.get("/api/v1/organisations")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


def test_list_organisations_with_data(client, db):
    seed_organisations(db, 3)
    resp = client.get("/api/v1/organisations")
    assert resp.status_code == 200
    assert resp.json()["_meta"]["total_records"] == 3


def test_get_organisation_found(client, db):
    seed_organisations(db, 1)
    resp = client.get("/api/v1/organisations/1")
    assert resp.status_code == 200
    assert resp.json()["organisation_id"] == 1


def test_get_organisation_not_found(client):
    resp = client.get("/api/v1/organisations/99999")
    assert resp.status_code == 404
