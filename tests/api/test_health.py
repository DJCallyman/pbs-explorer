"""Tests for /api/v1/health endpoint."""
from __future__ import annotations


def test_health_ok(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
