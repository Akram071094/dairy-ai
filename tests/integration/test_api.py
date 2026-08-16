"""Integration tests for the health and recommendation endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app
from app.models.recommendation import AIRecommendation, Base
from app.models.schemas import RecommendationDomain

ORG_ID = uuid.UUID("a1b2c3d4-e5f6-7a8b-9c0d-e1f2a3b4c5d6")


@pytest.fixture
def stored_db():
    """Override the DB dependency with an in-memory SQLite session."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    session = Session(bind=engine, future=True)

    app.dependency_overrides[get_db] = lambda: session
    yield session
    app.dependency_overrides.pop(get_db, None)
    session.close()


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


def test_get_stored_recommendations(client, stored_db) -> None:
    """The stored endpoint should return precomputed rows for an org/domain."""
    stored_db.add(
        AIRecommendation(
            organization_id=ORG_ID,
            domain=RecommendationDomain.STOCK.value,
            item_id="sku-1",
            label="Whole Milk 1L",
            score=0.92,
            reason="Low stock vs demand",
            run_id=uuid.uuid4(),
            created_at=datetime.now(timezone.utc),
        )
    )
    stored_db.commit()

    response = client.get(f"/api/v1/recommendations/stored/{ORG_ID}?domain=stock")
    assert response.status_code == 200
    payload = response.json()
    assert payload["organization_id"] == str(ORG_ID)
    assert payload["domain"] == "stock"
    assert len(payload["recommendations"]) == 1
    assert payload["recommendations"][0]["item_id"] == "sku-1"
    assert payload["recommendations"][0]["score"] == 0.92


def test_get_stored_recommendations_empty_for_unknown_org(client, stored_db) -> None:
    """An org with no stored rows should return an empty recommendation list."""
    response = client.get(f"/api/v1/recommendations/stored/{uuid.uuid4()}?domain=collections")
    assert response.status_code == 200
    payload = response.json()
    assert payload["domain"] == "collections"
    assert payload["recommendations"] == []


def test_openapi_includes_prefix(app=app) -> None:
    """The OpenAPI schema should mount under the configured prefix."""
    assert "/api/v1/health" in app.openapi()["paths"]
    assert "/api/v1/recommendations/stored/{organization_id}" in app.openapi()["paths"]


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
