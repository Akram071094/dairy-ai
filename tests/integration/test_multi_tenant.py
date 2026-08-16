"""Action Center tests across two tenants and their roles.

Exercises the real HTTP endpoints (available-actions, execute, execute-all)
for two distinct organizations. Positive execute paths stub the orchestration
service so the full authz gate -> handler chain is tested without a database
or live dairy-backend.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_forwarded_user
from app.main import app
from app.models.schemas import AgentExecutionMode, AgentExecutionResult
from app.services.agent_service import AgentService
from app.services.forwarded_auth import ForwardedUser

ORG_A = str(uuid.UUID("11111111-1111-1111-1111-111111111111"))
ORG_B = str(uuid.UUID("22222222-2222-2222-2222-222222222222"))

ALL_AGENTS = {
    "business_cycle",
    "inventory_reorder",
    "delivery_planning",
    "collections_followup",
    "onboarding",
}
PERM_ALL = {"inventory:read", "delivery:read", "collection:read", "user:manage"}


def _uid(n: int) -> str:
    return f"{n:08d}-0000-0000-0000-000000000000"


def _user(n: int, email: str, org: str, permissions: set[str]) -> ForwardedUser:
    return ForwardedUser(
        user_id=_uid(n),
        email=email,
        organization_id=org,
        permissions=set(permissions),
    )


# --- Two tenants and their roles -------------------------------------------
class TenantRoles:
    def __init__(self, org: str, domain: str, n: int) -> None:
        self.owner = _user(n + 1, f"owner@{domain}", org, PERM_ALL)
        self.manager = _user(n + 2, f"manager@{domain}", org, {"delivery:read", "collection:read"})
        self.viewer = _user(n + 3, f"viewer@{domain}", org, set())


TENANT_A = TenantRoles(ORG_A, "acme.example", 100)
TENANT_B = TenantRoles(ORG_B, "sunnydale.example", 200)


@pytest.fixture
def as_user():
    """Apply a get_forwarded_user override for the duration of one test."""

    def _apply(user: ForwardedUser) -> None:
        app.dependency_overrides[get_forwarded_user] = lambda: user

    yield _apply
    app.dependency_overrides.pop(get_forwarded_user, None)


@pytest.fixture
def stub_execute(monkeypatch) -> list[dict]:
    """Stub AgentService so authorized runs return without DB or backend calls."""
    calls: list[dict] = []

    async def _execute(
        self, agent_id, organization_id, context=None, mode=None
    ) -> AgentExecutionResult:
        calls.append({"agent_id": agent_id, "organization_id": str(organization_id), "mode": mode})
        return AgentExecutionResult(
            agent_id=agent_id,
            status="completed",
            summary=f"ran {agent_id}",
            steps=[],
        )

    async def _execute_all(
        self, organization_id, context=None, mode=None
    ) -> list[AgentExecutionResult]:
        return [
            AgentExecutionResult(agent_id=agent_id, status="completed", summary="ok", steps=[])
            for agent_id in sorted(ALL_AGENTS)
        ]

    monkeypatch.setattr(AgentService, "execute", _execute)
    monkeypatch.setattr(AgentService, "execute_all", _execute_all)
    return calls


# --- available-actions ------------------------------------------------------
@pytest.mark.parametrize(
    ("user", "expected"),
    [
        (TENANT_A.owner, ALL_AGENTS),
        (TENANT_A.manager, {"delivery_planning", "collections_followup"}),
        (TENANT_A.viewer, set()),
        (TENANT_B.owner, ALL_AGENTS),
        (TENANT_B.manager, {"delivery_planning", "collections_followup"}),
        (TENANT_B.viewer, set()),
    ],
)
def test_available_actions_filters_by_role_per_tenant(
    client: TestClient, as_user, user: ForwardedUser, expected: set[str]
) -> None:
    """The Action Center lists only agents the role's permissions allow."""
    as_user(user)
    response = client.get("/api/v1/agents/available-actions")
    assert response.status_code == 200
    agents = response.json()["agents"]
    assert {agent["agent_id"] for agent in agents} == expected
    for agent in agents:
        assert "required_permissions" in agent


def test_available_actions_advertises_required_permissions(client: TestClient, as_user) -> None:
    """The contract advertises the permission codes for each agent."""
    as_user(TENANT_A.owner)
    response = client.get("/api/v1/agents/available-actions")
    by_id = {agent["agent_id"]: agent for agent in response.json()["agents"]}
    assert by_id["business_cycle"]["required_permissions"] == [
        "inventory:read",
        "delivery:read",
        "collection:read",
    ]
    assert by_id["onboarding"]["required_permissions"] == ["user:manage"]


# --- execute ----------------------------------------------------------------
@pytest.mark.parametrize(
    ("user", "agent_id", "payload_org", "expected"),
    [
        (TENANT_A.owner, "inventory_reorder", ORG_A, 200),
        (TENANT_A.manager, "delivery_planning", ORG_A, 200),
        (TENANT_A.manager, "inventory_reorder", ORG_A, 403),
        (TENANT_A.viewer, "delivery_planning", ORG_A, 403),
        (TENANT_B.owner, "collections_followup", ORG_B, 200),
        (TENANT_B.owner, "inventory_reorder", ORG_A, 403),
        (TENANT_B.manager, "delivery_planning", ORG_B, 200),
        (TENANT_B.manager, "inventory_reorder", ORG_B, 403),
        (TENANT_B.manager, "onboarding", ORG_B, 403),
        (TENANT_A.owner, "delivery_planning", ORG_B, 403),
    ],
)
def test_execute_enforces_tenant_and_role(
    client: TestClient,
    as_user,
    stub_execute,
    user: ForwardedUser,
    agent_id: str,
    payload_org: str,
    expected: int,
) -> None:
    """Runs are allowed only within the caller's tenant and role scope."""
    as_user(user)
    response = client.post(
        "/api/v1/agents/execute",
        json={"agent_id": agent_id, "organization_id": payload_org, "mode": "propose"},
    )
    assert response.status_code == expected
    if expected == 200:
        assert response.json()["agent_id"] == agent_id


def test_execute_scopes_authorized_run_to_user_tenant(
    client: TestClient, as_user, stub_execute
) -> None:
    """An allowed run is handed the caller's own organization id."""
    as_user(TENANT_B.owner)
    response = client.post(
        "/api/v1/agents/execute",
        json={"agent_id": "inventory_reorder", "organization_id": ORG_B, "mode": "propose"},
    )
    assert response.status_code == 200
    assert stub_execute[-1]["organization_id"] == ORG_B
    assert stub_execute[-1]["mode"] == AgentExecutionMode.PROPOSE


# --- execute-all ------------------------------------------------------------
def test_execute_all_runs_every_agent_for_own_tenant(
    client: TestClient, as_user, stub_execute
) -> None:
    """A tenant owner may run every registered agent for their own tenant."""
    as_user(TENANT_B.owner)
    response = client.post(
        "/api/v1/agents/execute-all",
        json={"organization_id": ORG_B, "mode": "propose"},
    )
    assert response.status_code == 200
    assert {result["agent_id"] for result in response.json()} == ALL_AGENTS


def test_execute_all_blocked_when_role_lacks_any_permission(
    client: TestClient, as_user, stub_execute
) -> None:
    """A manager missing one agent's permission cannot run the full cycle."""
    as_user(TENANT_A.manager)
    response = client.post(
        "/api/v1/agents/execute-all",
        json={"organization_id": ORG_A, "mode": "propose"},
    )
    assert response.status_code == 403
