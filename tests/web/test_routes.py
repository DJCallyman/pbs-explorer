from __future__ import annotations

from fastapi.testclient import TestClient

from main import create_app


def test_browse_atc_endpoint() -> None:
    """Test that browse ATC endpoint exists."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/browse/atc")
    assert response.status_code in {200, 500}


def test_browse_programs_endpoint() -> None:
    """Test that browse programs endpoint exists."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/browse/programs")
    assert response.status_code in {200, 500}


def test_browse_manufacturers_endpoint() -> None:
    """Test that browse manufacturers endpoint exists."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/browse/manufacturers")
    assert response.status_code in {200, 500}


def test_browse_therapeutic_groups_endpoint() -> None:
    """Test that browse therapeutic groups endpoint exists and doesn't 404."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/browse/therapeutic-groups")
    # Should not be 404 anymore
    assert response.status_code in {200, 500}
    assert response.status_code != 404
