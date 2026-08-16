"""End-to-end business cycle agent (deterministic).

Runs the full daily business flow in order, delegating each phase to the
focused domain agents and adding the delivery-readiness handoff:

1. ``inventory_reorder`` — restock low-inventory SKUs;
2. ``delivery_planning`` — review, approve, and assign manifests;
3. delivery execution readiness — surface assignments awaiting field
   execution (and start executions when explicitly authorized);
4. ``collections_followup`` — raise overdue collection exceptions.

Every phase goes through dairy-backend REST APIs; in ``propose`` mode
(``execute: false``) the agent records the intended actions without calling
action tools.
"""

from __future__ import annotations

from typing import Any

from app.agents.base import (
    STATUS_COMPLETED,
    STATUS_NOOP,
    AgentResult,
    AgentStep,
    BaseAgent,
    _extract_items,
)
from app.agents.collections_agent import CollectionsFollowUpAgent
from app.agents.inventory_agent import InventoryReorderAgent
from app.agents.planning_agent import DeliveryPlanningAgent
from app.utils.helpers import get_logger

logger = get_logger("business_cycle_agent")


class BusinessCycleAgent(BaseAgent):
    """Coordinate the full business flow in a single end-to-end run."""

    id = "business_cycle"
    name = "Business Cycle Agent"
    description = (
        "Runs the entire daily business flow: restock, plan and approve, "
        "assign, prepare deliveries, and follow up on collections."
    )
    tool_ids = (
        "inventory.low_stock",
        "inventory.stock_in",
        "planning.list",
        "planning.review",
        "planning.approve",
        "planning.manifest",
        "assignment.assign",
        "assignment.list",
        "execution.start",
        "collections.outstanding",
        "collections.exceptions",
        "exceptions.detect",
    )
    required_permissions = ("inventory:read", "delivery:read", "collection:read")

    _PHASES = (InventoryReorderAgent, DeliveryPlanningAgent, CollectionsFollowUpAgent)

    async def run(self, context: dict[str, Any]) -> AgentResult:
        self._steps = []
        summaries: list[str] = []

        for agent_cls in self._PHASES:
            agent = agent_cls(self.executor)
            result = await agent.run(context)
            self._steps.extend(result.steps)
            summaries.append(result.summary)

        execution_summary = await self._delivery_readiness(context)
        if execution_summary:
            summaries.append(execution_summary)

        logger.info("business cycle agent")
        action_steps = [
            s
            for s in self._steps
            if s.tool_id
            in (
                "inventory.stock_in",
                "planning.review",
                "planning.approve",
                "assignment.assign",
                "execution.start",
                "exceptions.detect",
            )
        ]
        if not action_steps:
            return self._result(STATUS_NOOP, "Nothing to act on across the daily business cycle")
        summary = "; ".join(s for s in summaries if s)
        return self._result(STATUS_COMPLETED, summary or "Business cycle complete")

    async def _delivery_readiness(self, context: dict[str, Any]) -> str:
        """Surface assignments awaiting field execution; optionally start them.

        Executions are only started when ``context["start_executions"]`` is
        truthy (the backend requires the assigned staff identity), so the
        default is a read-only readiness report.
        """
        start = bool(context.get("start_executions"))
        try:
            payload = await self._call(
                "assignment.list",
                action="fetch assignments needing delivery execution",
            )
        except Exception:
            logger.warning("could not list assignments for delivery readiness")
            return ""
        assignments = _extract_items(payload)
        awaiting = [
            a
            for a in assignments
            if (a.get("assignment_status") or "").lower() in ("accepted", "in_progress")
        ]
        if not awaiting:
            return ""

        if not start:
            for assignment in awaiting:
                assignment_id = str(assignment.get("id") or "")
                if not assignment_id:
                    continue
                label = f"assignment {assignment_id} ready for delivery execution"
                self._steps.append(
                    AgentStep("assignment.list", label, "skipped", {"awaiting": "field execution"})
                )
            return f"{len(awaiting)} assignment(s) ready for delivery execution"

        started = 0
        for assignment in awaiting:
            assignment_id = str(assignment.get("id") or "")
            if not assignment_id:
                continue
            label = f"start execution for assignment {assignment_id}"
            try:
                await self._call(
                    "execution.start",
                    body={"assignment_id": assignment_id},
                    action=label,
                )
            except Exception:
                logger.warning("execution start failed")
                self._steps.append(AgentStep("execution.start", label, "error", "start rejected"))
                continue
            started += 1
        return f"Started {started} delivery execution(s) out of {len(awaiting)} ready"
