"""Integration tests for the public health endpoint."""

from __future__ import annotations

from app.main import app


def test_health_endpoint(client) -> None:
    """The health endpoint should report an OK status."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["app"]


def test_list_domains(client) -> None:
    """The recommendation domains endpoint should list available capabilities."""
    response = client.get("/api/v1/recommendations")
    assert response.status_code == 200
    domains = response.json()
    assert any(item["domain"] == "stock" for item in domains)
    assert any(item["domain"] == "collections" for item in domains)


def test_openapi_includes_prefix(app=app) -> None:
    """The OpenAPI schema should mount under the configured prefix."""
    assert "/api/v1/health" in app.openapi()["paths"]
