"""Agent registry: discovers and instantiates deterministic agents."""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.agents.business_cycle_agent import BusinessCycleAgent
from app.agents.collections_agent import CollectionsFollowUpAgent
from app.agents.inventory_agent import InventoryReorderAgent
from app.agents.onboarding_agent import UserOnboardingAgent
from app.agents.planning_agent import DeliveryPlanningAgent
from app.tools.executor import ToolExecutor


class AgentNotFoundError(KeyError):
    """Raised when an unknown agent id is requested."""


class AgentRegistry:
    """Registry of deterministic agents, built against a shared executor."""

    _AGENT_CLASSES = (
        BusinessCycleAgent,
        InventoryReorderAgent,
        DeliveryPlanningAgent,
        CollectionsFollowUpAgent,
        UserOnboardingAgent,
    )

    def __init__(self, executor: ToolExecutor) -> None:
        self._agents: dict[str, BaseAgent] = {
            agent.id: agent for agent in (cls(executor) for cls in self._AGENT_CLASSES)
        }

    def get(self, agent_id: str) -> BaseAgent:
        """Return the agent or raise :class:`AgentNotFoundError`."""
        try:
            return self._agents[agent_id]
        except KeyError as exc:
            raise AgentNotFoundError(f"unknown agent: {agent_id}") from exc

    def agents(self) -> list[BaseAgent]:
        """Return all registered agents."""
        return list(self._agents.values())

    def all_ids(self) -> list[str]:
        """Return all agent ids, sorted."""
        return sorted(self._agents)

    @classmethod
    def class_ids(cls) -> list[str]:
        """Return the ids of every registered agent class (no executor needed)."""
        return sorted(agent_cls.id for agent_cls in cls._AGENT_CLASSES)

    @classmethod
    def definitions(cls) -> list[dict]:
        """Return metadata for every registered agent class (no executor needed)."""
        return [cls_metadata(agent_cls) for agent_cls in cls._AGENT_CLASSES]

    @classmethod
    def required_permission_codes(cls) -> set[str]:
        """Return the union of permission codes needed by any registered agent."""
        codes: set[str] = set()
        for agent_cls in cls._AGENT_CLASSES:
            codes.update(agent_cls.required_permissions)
        return codes

    @classmethod
    def required_permissions_for(cls, agent_id: str) -> tuple[str, ...]:
        """Return the permission codes required to run an agent by id."""
        for agent_cls in cls._AGENT_CLASSES:
            if agent_cls.id == agent_id:
                return agent_cls.required_permissions
        raise AgentNotFoundError(f"unknown agent: {agent_id}")


def cls_metadata(agent_cls: type[BaseAgent]) -> dict:
    """Return catalog metadata for an agent class."""
    return {
        "agent_id": agent_cls.id,
        "name": agent_cls.name,
        "description": agent_cls.description,
        "actions": list(agent_cls.tool_ids),
        "required_permissions": list(agent_cls.required_permissions),
    }
