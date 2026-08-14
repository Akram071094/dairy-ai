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


def test_agent_health(client) -> None:
    """The agent platform health endpoint should list agents and tools."""
    response = client.get("/api/v1/agents/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "inventory_reorder" in payload["agents"]
    assert "inventory.stock_in" in payload["tools"]


def test_agent_available_actions(auth_client) -> None:
    """The Action Center contract should list agents with their actions."""
    response = auth_client.get("/api/v1/agents/available-actions")
    assert response.status_code == 200
    payload = response.json()
    agent_ids = {agent["agent_id"] for agent in payload["agents"]}
    assert {
        "inventory_reorder",
        "delivery_planning",
        "collections_followup",
    }.issubset(agent_ids)
    planning = next(a for a in payload["agents"] if a["agent_id"] == "delivery_planning")
    assert "planning.review" in planning["actions"]
