"""Integration tests for Action Center authentication (forwarded user JWT)."""

from __future__ import annotations

import uuid

from app.api.deps import get_forwarded_user
from app.main import app
from app.services.forwarded_auth import ForwardedUser

OTHER_ORG = uuid.UUID("22222222-2222-2222-2222-222222222222")


def test_agent_endpoints_require_authentication(client) -> None:
    """Agent endpoints should reject requests without a forwarded token."""
    response = client.get("/api/v1/agents/available-actions")
    assert response.status_code == 401

    response = client.post(
        "/api/v1/agents/execute",
        json={
            "agent_id": "inventory_reorder",
            "organization_id": str(OTHER_ORG),
            "mode": "propose",
        },
    )
    assert response.status_code == 401


def test_execute_rejects_cross_organization(client) -> None:
    """A forwarded user must not run agents for another organization."""
    foreign = ForwardedUser(
        user_id="22222222-2222-2222-2222-222222222222",
        email="other@org.com",
        organization_id=str(OTHER_ORG),
    )
    app.dependency_overrides[get_forwarded_user] = lambda: foreign
    try:
        response = client.post(
            "/api/v1/agents/execute",
            json={
                "agent_id": "inventory_reorder",
                "organization_id": "11111111-1111-1111-1111-111111111111",
                "mode": "propose",
            },
        )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.pop(get_forwarded_user, None)


def test_execute_rejects_missing_permission(client) -> None:
    """A user without the agent's permission must get 403."""
    manager = ForwardedUser(
        user_id="33333333-3333-3333-3333-333333333333",
        email="manager@org.com",
        organization_id="11111111-1111-1111-1111-111111111111",
        permissions={"delivery:read"},
    )
    app.dependency_overrides[get_forwarded_user] = lambda: manager
    try:
        response = client.post(
            "/api/v1/agents/execute",
            json={
                "agent_id": "inventory_reorder",
                "organization_id": "11111111-1111-1111-1111-111111111111",
                "mode": "propose",
            },
        )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.pop(get_forwarded_user, None)


def test_available_actions_filters_by_permission(client) -> None:
    """The Action Center only lists agents the user's permissions allow."""
    manager = ForwardedUser(
        user_id="33333333-3333-3333-3333-333333333333",
        email="manager@org.com",
        organization_id="11111111-1111-1111-1111-111111111111",
        permissions={"delivery:read"},
    )
    app.dependency_overrides[get_forwarded_user] = lambda: manager
    try:
        response = client.get("/api/v1/agents/available-actions")
        assert response.status_code == 200
        agent_ids = {agent["agent_id"] for agent in response.json()["agents"]}
        assert agent_ids == {"delivery_planning"}
    finally:
        app.dependency_overrides.pop(get_forwarded_user, None)


def test_available_actions_accepts_authenticated_user(auth_client) -> None:
    """The Action Center loads once the forwarded user is authenticated."""
    response = auth_client.get("/api/v1/agents/available-actions")
    assert response.status_code == 200
