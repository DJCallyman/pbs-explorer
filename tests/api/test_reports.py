from __future__ import annotations

from fastapi.testclient import TestClient

from main import create_app


def test_items_by_program_endpoint() -> None:
    """Test that items-by-program endpoint returns data in correct format."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/api/v1/reports/items-by-program")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert isinstance(data["data"], list)


def test_items_by_benefit_type_endpoint() -> None:
    """Test that items-by-benefit-type endpoint returns data in correct format."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/api/v1/reports/items-by-benefit-type")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert isinstance(data["data"], list)


def test_items_by_atc_level_endpoint() -> None:
    """Test that items-by-atc-level endpoint returns data in correct format."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/api/v1/reports/items-by-atc-level")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert isinstance(data["data"], list)


def test_price_changes_endpoint() -> None:
    """Test that price-changes endpoint returns data in correct format."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/api/v1/reports/price-changes")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert isinstance(data["data"], list)


def test_restriction_changes_endpoint() -> None:
    """Test that restriction-changes endpoint returns data in correct format."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/api/v1/reports/restriction-changes")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert isinstance(data["data"], list)
