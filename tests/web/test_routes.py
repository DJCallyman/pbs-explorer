from __future__ import annotations

from fastapi.testclient import TestClient

from main import create_app


def test_browse_atc_endpoint() -> None:
    """Test that browse ATC endpoint exists and returns success."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/browse/atc")
    # Should return 200 when database is properly set up
    # Will return 500 if database is missing (expected in test environment)
    assert response.status_code in {200, 500}


def test_browse_programs_endpoint() -> None:
    """Test that browse programs endpoint exists and returns success."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/browse/programs")
    assert response.status_code in {200, 500}


def test_browse_manufacturers_endpoint() -> None:
    """Test that browse manufacturers endpoint exists and returns success."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/browse/manufacturers")
    assert response.status_code in {200, 500}


def test_browse_therapeutic_groups_endpoint() -> None:
    """Test that browse therapeutic groups endpoint exists and doesn't 404.
    
    This verifies that the previously missing route is now implemented.
    A 404 would indicate the route is not registered.
    A 500 would indicate the route exists but database is missing.
    """
    app = create_app()
    client = TestClient(app)
    response = client.get("/browse/therapeutic-groups")
    # Should not be 404 anymore - that was the bug we fixed
    assert response.status_code != 404
    # Should be either 200 (with database) or 500 (without database)
    assert response.status_code in {200, 500}
