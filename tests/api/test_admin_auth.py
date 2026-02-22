"""Tests for admin endpoint authentication."""
from __future__ import annotations

from unittest.mock import patch

from config import Settings


def test_admin_no_key_configured(client):
    """When no admin key is configured, all admin endpoints return 403."""
    resp = client.get("/api/v1/admin/sync/endpoints")
    assert resp.status_code == 403
    assert "not configured" in resp.json()["detail"]


def test_admin_missing_header(client):
    """When key is configured but header is missing, return 401."""
    settings = Settings()
    settings.server.admin_api_key = "test-secret-key"
    with patch("api.deps.get_settings", return_value=settings):
        resp = client.get("/api/v1/admin/sync/endpoints")
    assert resp.status_code == 401


def test_admin_wrong_key(client):
    """When key is configured but wrong key given, return 403."""
    settings = Settings()
    settings.server.admin_api_key = "test-secret-key"
    with patch("api.deps.get_settings", return_value=settings):
        resp = client.get(
            "/api/v1/admin/sync/endpoints",
            headers={"X-Admin-API-Key": "wrong-key"},
        )
    assert resp.status_code == 403
    assert "Invalid" in resp.json()["detail"]


def test_admin_correct_key(client):
    """When correct key is given, admin endpoints are accessible."""
    settings = Settings()
    settings.server.admin_api_key = "test-secret-key"
    with patch("api.deps.get_settings", return_value=settings):
        resp = client.get(
            "/api/v1/admin/sync/endpoints",
            headers={"X-Admin-API-Key": "test-secret-key"},
        )
    assert resp.status_code == 200
    assert "endpoints" in resp.json()
