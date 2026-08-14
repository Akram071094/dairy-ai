"""Agent base classes and result types.

Phase 1 agents are deterministic, rule-based (per HLD-110). Each agent
reads operational state through read tools, applies explicit rules, and
executes actions through action tools — always against dairy-backend.
Every step is recorded for the audit trail and the Action Center.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.tools.executor import ToolExecutor
from app.utils.helpers import get_logger

logger = get_logger("agents")

STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_NOOP = "noop"


@dataclass
class AgentStep:
    """A single recorded step performed by an agent."""

    tool_id: str
    action: str  # human-readable description
    status: str  # ok | skipped | error
    detail: Any = None

    def to_dict(self) -> dict[str, Any]:
        """Serialise for persistence and API responses."""
        return {
            "tool_id": self.tool_id,
            "action": self.action,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass
class AgentResult:
    """Outcome of a single agent run."""

    agent_id: str
    status: str
    summary: str
    steps: list[AgentStep] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialise for persistence and API responses."""
        return {
            "agent_id": self.agent_id,
            "status": self.status,
            "summary": self.summary,
            "steps": [step.to_dict() for step in self.steps],
        }


class BaseAgent(ABC):
    """Base class for deterministic rule agents."""

    id: str = ""
    name: str = ""
    description: str = ""
    tool_ids: tuple[str, ...] = ()
    # Permission business codes (dairy-backend seed format, e.g. "inventory:read")
    # that a user must hold to see or run this agent. Empty = visible to all.
    required_permissions: tuple[str, ...] = ()

    def __init__(self, executor: ToolExecutor) -> None:
        self.executor = executor
        self._steps: list[AgentStep] = []

    @abstractmethod
    async def run(self, context: dict[str, Any]) -> AgentResult:
        """Execute the agent's rules; subclasses implement this."""

    async def _call(
        self,
        tool_id: str,
        *,
        path_params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        action: str | None = None,
    ) -> dict[str, Any] | None:
        """Execute a tool and record the step."""
        action_text = action or tool_id
        try:
            data = await self.executor.execute(
                tool_id, path_params=path_params, body=body, params=params
            )
        except Exception as exc:  # noqa: BLE001 - step-level capture; agent decides handling
            logger.warning("tool step failed")
            self._steps.append(AgentStep(tool_id, action_text, "error", str(exc)))
            raise
        self._steps.append(AgentStep(tool_id, action_text, "ok", data))
        return data

    def _result(self, status: str, summary: str) -> AgentResult:
        """Build the result from the recorded steps."""
        return AgentResult(self.id, status, summary, list(self._steps))

    def to_info(self) -> dict[str, Any]:
        """Agent metadata consumed by the Action Center and /agents endpoints."""
        return {
            "agent_id": self.id,
            "name": self.name,
            "description": self.description,
            "actions": list(self.tool_ids),
        }


def _extract_items(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Extract a list from a backend payload (list or {data|items|results: [...]})."""
    if not payload:
        return []
    if isinstance(payload, list):
        return payload
    for key in ("data", "items", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []
