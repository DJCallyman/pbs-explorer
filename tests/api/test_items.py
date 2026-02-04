from __future__ import annotations

from fastapi.testclient import TestClient

from main import create_app


def test_items_endpoint_exists() -> None:
    app = create_app()
    client = TestClient(app)
    response = client.get("/api/v1/items")
    assert response.status_code in {200, 500}
