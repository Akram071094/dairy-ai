"""Inventory reorder agent (deterministic).

Rule: for every SKU whose ``available_quantity`` is below its
``low_stock_threshold``, record a stock-in to top it back up to the
threshold. In ``propose`` mode the agent only records the proposed actions
without calling backend action tools.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.agents.base import (
    STATUS_COMPLETED,
    STATUS_NOOP,
    AgentResult,
    AgentStep,
    BaseAgent,
    _extract_items,
)
from app.utils.helpers import get_logger, to_float

logger = get_logger("inventory_agent")


class InventoryReorderAgent(BaseAgent):
    """Restock low-inventory SKUs to their configured threshold."""

    id = "inventory_reorder"
    name = "Inventory Reorder Agent"
    description = "Restock low-inventory SKUs to their threshold."
    tool_ids = ("inventory.low_stock", "inventory.stock_in")
    required_permissions = ("inventory:read",)

    async def run(self, context: dict[str, Any]) -> AgentResult:
        execute = bool(context.get("execute", True))
        self._steps = []

        threshold = to_float(context.get("restock_threshold"), default=10.0)
        payload = await self._call(
            "inventory.low_stock",
            params={"threshold": str(threshold)},
            action="fetch low-stock items",
        )
        items = _extract_items(payload)
        logger.info("inventory agent")

        restocked = 0
        for item in items:
            sku_id = str(item.get("sku_id") or "")
            if not sku_id:
                continue
            available = to_float(item.get("available_quantity"))
            quantity = int(threshold - available)
            if quantity <= 0:
                continue
            name = item.get("sku_name") or item.get("sku_code") or sku_id
            action_text = (
                f"restock {name} by {quantity} (available {available} < threshold {threshold})"
            )
            if not execute:
                self._steps.append(
                    AgentStep("inventory.stock_in", action_text, "skipped", {"mode": "propose"})
                )
                continue
            try:
                await self._call(
                    "inventory.stock_in",
                    body={
                        "sku_id": sku_id,
                        "quantity": quantity,
                        "unit": item.get("unit") or "liters",
                        "source": "agent_auto_restock",
                        "notes": "auto-restock by inventory_reorder agent",
                        "effective_date": str(date.today().isoformat()),
                    },
                    action=action_text,
                )
            except Exception:
                logger.warning("stock-in failed")
                self._steps.append(
                    AgentStep("inventory.stock_in", action_text, "error", "stock-in rejected")
                )
                continue
            restocked += 1

        restock_steps = [s for s in self._steps if s.tool_id == "inventory.stock_in"]
        if not restock_steps:
            return self._result(STATUS_NOOP, f"No restock needed ({len(items)} low-stock items)")
        return self._result(
            STATUS_COMPLETED,
            f"Restocked {restocked} low-stock item(s) out of {len(items)} reviewed",
        )
