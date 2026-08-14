"""Tests for the deterministic agents (inventory, planning, collections, cycle)."""

from __future__ import annotations

import pytest

from app.agents.base import STATUS_COMPLETED, STATUS_NOOP
from app.agents.registry import AgentRegistry
from app.services.backend_client import BackendApiError, BackendClient
from app.tools.executor import ToolExecutor


class _FakeClient(BackendClient):
    """BackendClient stand-in that records calls without networking."""

    def __init__(self) -> None:
        self.get_calls: list[tuple[str, dict | None]] = []
        self.post_calls: list[tuple[str, dict | None, dict | None]] = []
        self.get_responses: dict[tuple[str, str | None], object] = {}
        self.post_responses: dict[tuple[str, str | None, str | None], object] = {}
        self.fail: set[str] = set()

    async def get(self, path, *, params=None):
        self.get_calls.append((path, params))
        if path in self.fail:
            raise BackendApiError("boom", status_code=500)
        return self.get_responses.get((path, _key(params)))

    async def post(self, path, *, params=None, json=None):
        self.post_calls.append((path, params, json))
        if path in self.fail:
            raise BackendApiError("boom", status_code=500)
        return self.post_responses.get((path, _key(params), _key(json)))

    async def close(self) -> None:
        pass


def _key(value: object) -> str | None:
    """Return a hashable key for a request value (None stays None)."""
    return value if value is None else str(value)


@pytest.fixture
def client() -> _FakeClient:
    return _FakeClient()


@pytest.fixture
def registry(client: _FakeClient) -> AgentRegistry:
    return AgentRegistry(ToolExecutor(client))


LOW_STOCK = [
    {
        "sku_id": "sku-1",
        "sku_code": "MILK-1L",
        "sku_name": "Fresh Milk 1L",
        "available_quantity": 5.0,
        "unit": "liters",
    }
]


@pytest.mark.asyncio
async def test_inventory_agent_executes_restock(
    client: _FakeClient, registry: AgentRegistry
) -> None:
    client.get_responses[("/api/v1/inventory/low-stock", str({"threshold": "10.0"}))] = LOW_STOCK

    result = await registry.get("inventory_reorder").run({"execute": True})

    assert result.status == STATUS_COMPLETED
    assert "Restocked 1" in result.summary
    stock_in = [c for c in client.post_calls if c[0] == "/api/v1/inventory/stock-in"]
    assert len(stock_in) == 1
    path, params, body = stock_in[0]
    assert body["sku_id"] == "sku-1"
    assert body["quantity"] == 5
    assert body["unit"] == "liters"


@pytest.mark.asyncio
async def test_inventory_agent_propose_mode_skips_actions(
    client: _FakeClient, registry: AgentRegistry
) -> None:
    client.get_responses[("/api/v1/inventory/low-stock", str({"threshold": "10.0"}))] = LOW_STOCK

    result = await registry.get("inventory_reorder").run({"execute": False})

    assert result.status == STATUS_COMPLETED
    assert client.post_calls == []
    skipped = [s for s in result.steps if s.status == "skipped"]
    assert len(skipped) == 1


@pytest.mark.asyncio
async def test_inventory_agent_noop_when_stocked(
    client: _FakeClient, registry: AgentRegistry
) -> None:
    client.get_responses[("/api/v1/inventory/low-stock", str({"threshold": "10.0"}))] = [
        {
            "sku_id": "sku-9",
            "available_quantity": 50.0,
        }
    ]

    result = await registry.get("inventory_reorder").run({"execute": True})

    assert result.status == STATUS_NOOP
    assert client.post_calls == []


@pytest.mark.asyncio
async def test_planning_agent_reviews_and_approves(
    client: _FakeClient, registry: AgentRegistry
) -> None:
    generated = [{"id": "b-1", "status": "generated"}]
    reviewed = [{"id": "b-2", "status": "reviewed"}]
    client.get_responses[("/api/v1/planning", str({"status": "generated"}))] = generated
    client.get_responses[("/api/v1/planning", str({"status": "reviewed"}))] = reviewed

    result = await registry.get("delivery_planning").run({"execute": True})

    assert result.status == STATUS_COMPLETED
    assert "Reviewed 1, approved 1" in result.summary
    review = [c for c in client.post_calls if c[0].endswith("/review")]
    approve = [c for c in client.post_calls if c[0].endswith("/approve")]
    assert len(review) == 1 and review[0][0] == "/api/v1/planning/b-1/review"
    assert len(approve) == 1 and approve[0][0] == "/api/v1/planning/b-2/approve"


@pytest.mark.asyncio
async def test_planning_agent_assigns_with_staff_id(
    client: _FakeClient, registry: AgentRegistry
) -> None:
    client.get_responses[("/api/v1/planning", str({"status": "generated"}))] = []
    client.get_responses[("/api/v1/planning", str({"status": "reviewed"}))] = []
    client.get_responses[("/api/v1/planning", str({"status": "approved"}))] = [
        {"id": "b-3", "status": "approved"}
    ]
    client.get_responses[("/api/v1/planning/b-3/manifest", None)] = {"id": "m-3"}

    result = await registry.get("delivery_planning").run({"execute": True, "staff_id": "staff-9"})

    assert "assigned 1" in result.summary
    assign = [c for c in client.post_calls if c[0] == "/api/v1/assignments/assign"]
    assert len(assign) == 1
    assert assign[0][2]["assigned_staff_id"] == "staff-9"
    assert assign[0][2]["manifest_id"] == "m-3"


@pytest.mark.asyncio
async def test_collections_agent_raises_exceptions(
    client: _FakeClient, registry: AgentRegistry
) -> None:
    overdue = [
        {
            "id": "out-1",
            "retailer_id": "ret-1",
            "outstanding_amount": 1000.0,
            "overdue_amount": 500.0,
            "has_overdue": True,
        }
    ]
    client.get_responses[("/api/v1/outstanding", str({"has_overdue": "true"}))] = overdue
    client.get_responses[("/api/v1/exceptions", None)] = []

    result = await registry.get("collections_followup").run({"execute": True})

    assert result.status == STATUS_COMPLETED
    assert "Raised 1" in result.summary
    detect = [c for c in client.post_calls if c[0] == "/api/v1/exceptions"]
    assert len(detect) == 1
    assert detect[0][2]["retailer_id"] == "ret-1"
    assert detect[0][2]["exception_type"] == "overdue_payment"


@pytest.mark.asyncio
async def test_collections_agent_skips_existing_exception(
    client: _FakeClient, registry: AgentRegistry
) -> None:
    overdue = [
        {"id": "out-1", "retailer_id": "ret-1", "has_overdue": True, "overdue_amount": 500.0}
    ]
    existing = [{"id": "exc-1", "retailer_id": "ret-1"}]
    client.get_responses[("/api/v1/outstanding", str({"has_overdue": "true"}))] = overdue
    client.get_responses[("/api/v1/exceptions", None)] = existing

    result = await registry.get("collections_followup").run({"execute": True})

    assert result.status == STATUS_NOOP
    assert client.post_calls == []


@pytest.mark.asyncio
async def test_business_cycle_runs_all_phases(client: _FakeClient, registry: AgentRegistry) -> None:
    client.get_responses[("/api/v1/inventory/low-stock", str({"threshold": "10.0"}))] = LOW_STOCK
    client.get_responses[("/api/v1/planning", str({"status": "generated"}))] = []
    client.get_responses[("/api/v1/planning", str({"status": "reviewed"}))] = []
    client.get_responses[("/api/v1/outstanding", str({"has_overdue": "true"}))] = []
    client.get_responses[("/api/v1/exceptions", None)] = []
    client.get_responses[("/api/v1/assignments", None)] = [
        {"id": "a-1", "assignment_status": "accepted"}
    ]

    result = await registry.get("business_cycle").run({"execute": True})

    assert result.status == STATUS_COMPLETED
    assert "Restocked 1" in result.summary
    stock_in = [c for c in client.post_calls if c[0] == "/api/v1/inventory/stock-in"]
    assert len(stock_in) == 1
    readiness = [s for s in result.steps if s.tool_id == "assignment.list"]
    assert len(readiness) >= 1


@pytest.mark.asyncio
async def test_business_cycle_propose_mode_skips_actions(
    client: _FakeClient, registry: AgentRegistry
) -> None:
    client.get_responses[("/api/v1/inventory/low-stock", str({"threshold": "10.0"}))] = LOW_STOCK
    client.get_responses[("/api/v1/planning", str({"status": "generated"}))] = []
    client.get_responses[("/api/v1/planning", str({"status": "reviewed"}))] = []
    client.get_responses[("/api/v1/outstanding", str({"has_overdue": "true"}))] = []
    client.get_responses[("/api/v1/exceptions", None)] = []
    client.get_responses[("/api/v1/assignments", None)] = []

    result = await registry.get("business_cycle").run({"execute": False})

    assert result.status == STATUS_COMPLETED
    assert client.post_calls == []
    skipped = [s for s in result.steps if s.status == "skipped"]
    assert len(skipped) >= 1


@pytest.mark.asyncio
async def test_business_cycle_noop_when_nothing_to_do(
    client: _FakeClient, registry: AgentRegistry
) -> None:
    client.get_responses[("/api/v1/inventory/low-stock", str({"threshold": "10.0"}))] = []
    client.get_responses[("/api/v1/planning", str({"status": "generated"}))] = []
    client.get_responses[("/api/v1/planning", str({"status": "reviewed"}))] = []
    client.get_responses[("/api/v1/outstanding", str({"has_overdue": "true"}))] = []
    client.get_responses[("/api/v1/exceptions", None)] = []
    client.get_responses[("/api/v1/assignments", None)] = []

    result = await registry.get("business_cycle").run({"execute": True})

    assert result.status == STATUS_NOOP
    assert client.post_calls == []


@pytest.mark.asyncio
async def test_onboarding_invites_new_user(client: _FakeClient, registry: AgentRegistry) -> None:
    client.get_responses[("/api/v1/roles", None)] = {
        "data": [{"id": "role-1", "business_code": "DELIVERY_STAFF"}]
    }
    client.get_responses[("/api/v1/users", None)] = {"data": []}

    result = await registry.get("onboarding").run(
        {
            "invites": [
                {
                    "email": "new@example.com",
                    "first_name": "New",
                    "last_name": "User",
                    "role_codes": ["DELIVERY_STAFF"],
                }
            ]
        }
    )

    assert result.status == STATUS_COMPLETED
    assert "Invited 1" in result.summary
    invites = [c for c in client.post_calls if c[0] == "/api/v1/users"]
    assert len(invites) == 1
    body = invites[0][2]
    assert body["email"] == "new@example.com"
    assert body["role_ids"] == ["role-1"]


@pytest.mark.asyncio
async def test_onboarding_skips_existing_email(
    client: _FakeClient, registry: AgentRegistry
) -> None:
    client.get_responses[("/api/v1/roles", None)] = {"data": []}
    client.get_responses[("/api/v1/users", None)] = {"data": [{"email": "existing@example.com"}]}

    result = await registry.get("onboarding").run({"invites": [{"email": "existing@example.com"}]})

    assert result.status == STATUS_NOOP
    assert client.post_calls == []


@pytest.mark.asyncio
async def test_onboarding_noop_without_invites(
    client: _FakeClient, registry: AgentRegistry
) -> None:
    result = await registry.get("onboarding").run({})
    assert result.status == STATUS_NOOP
    assert client.post_calls == []


def test_unknown_agent_raises(registry: AgentRegistry) -> None:
    with pytest.raises(KeyError):
        registry.get("does_not_exist")
