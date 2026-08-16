"""Agent orchestrator: coordinates agent runs against the tool executor.

The orchestrator is deliberately stateless and holds no business logic —
agents execute business actions exclusively through dairy-backend REST
APIs. Its job is discovery, dispatch, and result aggregation.
"""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentResult
from app.agents.registry import AgentNotFoundError, AgentRegistry
from app.tools.executor import ToolExecutor
from app.utils.helpers import get_logger

logger = get_logger("orchestrator")


class Orchestrator:
    """Coordinates agent execution."""

    def __init__(self, executor: ToolExecutor, registry: AgentRegistry | None = None) -> None:
        self.executor = executor
        self.registry = registry or AgentRegistry(executor)

    async def run_agent(self, agent_id: str, context: dict[str, Any] | None = None) -> AgentResult:
        """Run a single agent by id and return its :class:`AgentResult`."""
        try:
            agent = self.registry.get(agent_id)
        except KeyError as exc:
            raise AgentNotFoundError(f"unknown agent: {agent_id}") from exc
        logger.info("orchestrator run_agent")
        return await agent.run(context or {})

    async def run_all(self, context: dict[str, Any] | None = None) -> list[AgentResult]:
        """Run every registered agent in order and return the results."""
        results = []
        for agent in self.registry.agents():
            results.append(await agent.run(context or {}))
        return results

    def available_actions(self) -> list[dict[str, Any]]:
        """Agent metadata for the Action Center (/agents/available-actions)."""
        return [agent.to_info() for agent in self.registry.agents()]
