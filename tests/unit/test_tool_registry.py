"""Tests for the tool registry and executor."""

from __future__ import annotations

import pytest

from app.services.backend_client import BackendApiError, BackendClient
from app.tools.executor import ToolExecutor, ToolNotFoundError
from app.tools.registry import RiskLevel, tool_registry


class _FakeClient(BackendClient):
    """BackendClient stand-in that records calls without networking."""

    def __init__(self) -> None:
        self.get_calls: list[tuple[str, dict | None]] = []
        self.post_calls: list[tuple[str, dict | None, dict | None]] = []
        self.responses: dict[str, object] = {}
        self.fail_paths: set[str] = set()

    async def get(self, path, *, params=None):
        self.get_calls.append((path, params))
        if path in self.fail_paths:
            raise BackendApiError("nope", status_code=500)
        return self.responses.get(path)

    async def post(self, path, *, params=None, json=None):
        self.post_calls.append((path, params, json))
        if path in self.fail_paths:
            raise BackendApiError("nope", status_code=500)
        return self.responses.get(path)

    async def close(self) -> None:
        pass


def _executor() -> tuple[ToolExecutor, _FakeClient]:
    client = _FakeClient()
    return ToolExecutor(client), client


def test_catalogue_has_core_tools() -> None:
    ids = tool_registry.all_ids()
    for expected in (
        "inventory.low_stock",
        "planning.review",
        "planning.approve",
        "assignment.assign",
        "inventory.stock_in",
        "collections.collect",
        "exceptions.detect",
    ):
        assert expected in ids


@pytest.mark.asyncio
async def test_read_tool_executes_get() -> None:
    executor, client = _executor()
    client.responses["/api/v1/inventory/low-stock"] = [{"sku_id": "s1"}]

    result = await executor.execute("inventory.low_stock", params={"threshold": 10})

    assert result == [{"sku_id": "s1"}]
    assert client.get_calls == [("/api/v1/inventory/low-stock", {"threshold": 10})]


@pytest.mark.asyncio
async def test_action_tool_substitutes_path_params() -> None:
    executor, client = _executor()
    client.responses["/api/v1/planning/abc/review"] = {"status": "awaiting_approval"}

    result = await executor.execute(
        "planning.review",
        path_params={"planning_id": "abc"},
        body={"notes": "auto-reviewed"},
    )

    assert result == {"status": "awaiting_approval"}
    assert client.post_calls == [("/api/v1/planning/abc/review", None, {"notes": "auto-reviewed"})]


@pytest.mark.asyncio
async def test_unknown_tool_raises() -> None:
    executor, _ = _executor()
    with pytest.raises(ToolNotFoundError):
        await executor.execute("does.not.exist")


@pytest.mark.asyncio
async def test_missing_path_param_raises() -> None:
    executor, _ = _executor()
    with pytest.raises(ValueError):
        await executor.execute("planning.review", body={"notes": "x"})


def test_action_tools_are_flagged_high_risk() -> None:
    executor, _ = _executor()
    for tool_id in ("inventory.stock_in", "assignment.assign", "collections.collect"):
        tool = executor.get_tool(tool_id)
        assert tool.risk_level == RiskLevel.HIGH


def test_required_capabilities_map_to_platform_permissions() -> None:
    assert tool_registry.get("planning.review").required_capability == "Planning.Review"
    assert tool_registry.get("inventory.stock_in").required_capability == "Inventory.RecordMovement"
    assert (
        tool_registry.get("exceptions.detect").required_capability
        == "CollectionException.Acknowledge"
    )
