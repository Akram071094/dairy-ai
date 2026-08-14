"""Collections follow-up agent (deterministic).

Rule: for every outstanding balance flagged ``has_overdue``, raise a
``overdue_payment`` collection exception unless one already exists for that
retailer. This surfaces overdue accounts in the collections workflow
without fabricating payment events.
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

logger = get_logger("collections_agent")


class CollectionsFollowUpAgent(BaseAgent):
    """Detect overdue balances and raise follow-up collection exceptions."""

    id = "collections_followup"
    name = "Collections Follow-up Agent"
    description = "Detects overdue balances and raises collection exceptions for follow-up."
    tool_ids = ("collections.outstanding", "collections.exceptions", "exceptions.detect")
    required_permissions = ("collection:read",)

    async def run(self, context: dict[str, Any]) -> AgentResult:
        execute = bool(context.get("execute", True))
        self._steps = []

        outstanding = await self._call(
            "collections.outstanding",
            params={"has_overdue": "true"},
            action="fetch overdue outstanding balances",
        )
        overdue = _extract_items(outstanding)
        logger.info("collections agent")
        if not overdue:
            return self._result(STATUS_NOOP, "No overdue outstanding balances")

        open_retailer_ids = await self._fetch_open_retailer_ids()

        raised = 0
        for item in overdue:
            retailer_id = str(item.get("retailer_id") or "")
            if not retailer_id or retailer_id in open_retailer_ids:
                continue
            amount = item.get("overdue_amount") or item.get("outstanding_amount")
            label = f"raise overdue exception for retailer {retailer_id}"
            if not execute:
                self._steps.append(
                    AgentStep("exceptions.detect", label, "skipped", {"mode": "propose"})
                )
                continue
            try:
                await self._call(
                    "exceptions.detect",
                    body={
                        "retailer_id": retailer_id,
                        "exception_type": "overdue_payment",
                        "description": (
                            f"Auto-detected overdue balance of {amount} "
                            "by collections_followup agent"
                        ),
                        "amount": float(amount) if amount else None,
                    },
                    action=label,
                )
            except Exception:
                logger.warning("exception detect failed")
                self._steps.append(
                    AgentStep("exceptions.detect", label, "error", "detect rejected")
                )
                continue
            raised += 1

        detect_steps = [s for s in self._steps if s.tool_id == "exceptions.detect"]
        if not detect_steps:
            return self._result(STATUS_NOOP, "No new overdue follow-ups to raise")
        return self._result(
            STATUS_COMPLETED,
            f"Raised {raised} overdue exception(s) from {len(overdue)} overdue account(s)",
        )

    async def _fetch_open_retailer_ids(self) -> set[str]:
        """Return retailer ids that already have open collection exceptions."""
        try:
            payload = await self._call(
                "collections.exceptions", action="fetch open collection exceptions"
            )
        except Exception:
            logger.warning("could not fetch existing exceptions; assuming none")
            return set()
        return {str(e.get("retailer_id") or "") for e in _extract_items(payload)}
