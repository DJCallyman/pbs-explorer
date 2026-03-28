from __future__ import annotations

import base64
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.deps import get_db
from config import Settings
from main import create_app


def _basic_auth_header(username: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def test_search_requires_basic_auth_when_configured(db):
    settings = Settings()
    settings.server.web_username = "alice"
    settings.server.web_password = "secret-password"

    with patch("main.get_settings", return_value=settings):
        app = create_app()

    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/search")
    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Basic")


def test_search_allows_basic_auth_when_configured(db):
    settings = Settings()
    settings.server.web_username = "alice"
    settings.server.web_password = "secret-password"

    with patch("main.get_settings", return_value=settings):
        app = create_app()

    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/search", headers=_basic_auth_header("alice", "secret-password"))
    assert response.status_code == 200


def test_admin_routes_allow_authenticated_web_user_without_admin_key(db):
    settings = Settings()
    settings.server.web_username = "alice"
    settings.server.web_password = "secret-password"
    settings.server.admin_api_key = ""

    with patch("main.get_settings", return_value=settings):
        app = create_app()

    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get(
        "/api/v1/admin/sync/endpoints",
        headers=_basic_auth_header("alice", "secret-password"),
    )
    assert response.status_code == 200
    assert "endpoints" in response.json()
