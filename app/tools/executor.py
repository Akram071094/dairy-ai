"""Tool execution: turn tool ids + params into real backend calls."""

from __future__ import annotations

from typing import Any

from app.services.backend_client import BackendClient
from app.tools.registry import ToolRegistry, tool_registry
from app.utils.helpers import get_logger

logger = get_logger("tools")


class ToolNotFoundError(KeyError):
    """Raised when an unknown tool id is requested."""


class ToolExecutor:
    """Executes tools against dairy-backend through a :class:`BackendClient`."""

    def __init__(self, client: BackendClient, registry: ToolRegistry = tool_registry) -> None:
        self.client = client
        self.registry = registry

    def get_tool(self, tool_id: str):
        """Return the tool definition."""
        try:
            return self.registry.get(tool_id)
        except KeyError as exc:
            raise ToolNotFoundError(f"unknown tool: {tool_id}") from exc

    def _build_path(self, path: str, path_params: dict[str, Any]) -> str:
        """Substitute ``{param}`` placeholders in the tool path."""
        try:
            return path.format(**path_params)
        except KeyError as exc:
            raise ValueError(f"missing path param {exc} for {path}") from exc

    async def execute(
        self,
        tool_id: str,
        *,
        path_params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Execute ``tool_id`` and return the backend JSON payload."""
        tool = self.get_tool(tool_id)
        path = self._build_path(tool.path, path_params or {})
        logger.info("tool execute")
        if tool.method == "GET":
            return await self.client.get(path, params=params)
        return await self.client.post(path, params=params, json=body or {})
