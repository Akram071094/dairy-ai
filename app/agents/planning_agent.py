"""Delivery planning agent (deterministic).

Rules (matching dairy-backend state transitions):
- planning batches in ``generated`` status are reviewed;
- planning batches in ``reviewed`` status are approved;
- when ``staff_id`` is supplied in the context, manifests of ``approved``
  batches are assigned to that staff member (the manifest id is resolved
  from the batch before calling ``assignment.assign``).

Execution can be paused with ``execute: false`` in the context, in which
case the agent records the intended actions without calling action tools.
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
from app.utils.helpers import get_logger

logger = get_logger("planning_agent")


class DeliveryPlanningAgent(BaseAgent):
    """Advance manifests through review and approval (and assignment)."""

    id = "delivery_planning"
    name = "Delivery Planning Agent"
    description = "Reviews and approves generated manifests, then assigns approved ones."
    required_permissions = ("delivery:read",)
    tool_ids = (
        "planning.list",
        "planning.review",
        "planning.approve",
        "planning.manifest",
        "assignment.assign",
    )

    async def run(self, context: dict[str, Any]) -> AgentResult:
        execute = bool(context.get("execute", True))
        staff_id = context.get("staff_id")
        self._steps = []

        pending_review = await self._call(
            "planning.list",
            params={"status": "generated"},
            action="fetch generated (awaiting review) batches",
        )
        pending_approval = await self._call(
            "planning.list",
            params={"status": "reviewed"},
            action="fetch reviewed (awaiting approval) batches",
        )

        reviewed = await self._process_batch(_extract_items(pending_review), "review", execute)
        approved = await self._process_batch(_extract_items(pending_approval), "approve", execute)
        assigned = 0
        if execute and staff_id:
            assigned = await self._assign_approved(staff_id)

        logger.info("planning agent")
        action_steps = [
            s
            for s in self._steps
            if s.tool_id in ("planning.review", "planning.approve", "assignment.assign")
        ]
        if not action_steps:
            return self._result(STATUS_NOOP, "No manifests waiting for review or approval")
        return self._result(
            STATUS_COMPLETED,
            f"Reviewed {reviewed}, approved {approved}, assigned {assigned} manifest(s)",
        )

    async def _process_batch(
        self, batches: list[dict[str, Any]], action: str, execute: bool
    ) -> int:
        """Review or approve a batch of planning batches; return the number progressed."""
        tool_id = f"planning.{action}"
        progressed = 0
        for batch in batches:
            batch_id = str(batch.get("id") or "")
            if not batch_id:
                continue
            label = f"{action} batch {batch_id}"
            if not execute:
                self._steps.append(AgentStep(tool_id, label, "skipped", {"mode": "propose"}))
                continue
            try:
                await self._call(
                    tool_id,
                    path_params={"planning_id": batch_id},
                    body={"notes": f"auto-{action} by delivery_planning agent"},
                    action=label,
                )
            except Exception:
                logger.warning("planning action failed")
                self._steps.append(AgentStep(tool_id, label, "error", f"{action} rejected"))
                continue
            progressed += 1
        return progressed

    async def _assign_approved(self, staff_id: str) -> int:
        """Assign approved batches' manifests to a staff member; return count assigned."""
        try:
            payload = await self._call(
                "planning.list",
                params={"status": "approved"},
                action="fetch approved batches",
            )
        except Exception:
            logger.warning("could not list approved batches; skipping assignment")
            return 0

        assigned = 0
        for batch in _extract_items(payload):
            batch_id = str(batch.get("id") or "")
            if not batch_id:
                continue
            manifest_id = await self._resolve_manifest_id(batch_id)
            if not manifest_id:
                continue
            label = f"assign manifest {manifest_id} to staff {staff_id}"
            try:
                await self._call(
                    "assignment.assign",
                    body={
                        "manifest_id": manifest_id,
                        "assigned_staff_id": str(staff_id),
                        "delivery_session": "BOTH",
                        "notes": "auto-assigned by delivery_planning agent",
                    },
                    action=label,
                )
            except Exception:
                logger.warning("assignment failed")
                self._steps.append(
                    AgentStep("assignment.assign", label, "error", "assign rejected")
                )
                continue
            assigned += 1
        return assigned

    async def _resolve_manifest_id(self, batch_id: str) -> str | None:
        """Return the manifest id for a planning batch, or ``None``."""
        try:
            manifest = await self._call(
                "planning.manifest",
                path_params={"planning_id": batch_id},
                action=f"resolve manifest for batch {batch_id}",
            )
        except Exception:
            logger.warning("could not resolve manifest for batch")
            return None
        manifest_id = str((manifest or {}).get("id") or "")
        return manifest_id or None
