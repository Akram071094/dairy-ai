"""Deterministic decision engine (rule-based, no ML models yet).

Computes recommendations from operational data using pure backend
calculations. Domain-specific rules are applied heuristically, and their
scores are normalized to the 0..1 range. Ollama/LLM integration can later
replace this scoring while keeping the API contract unchanged.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.models.schemas import RecommendationDomain


class DecisionEngine:
    """Pure-computation engine producing ranked domain recommendations."""

    def recommend(
        self,
        features: pd.DataFrame,
        domain: RecommendationDomain,
        top_n: int = 10,
    ) -> list[dict[str, Any]]:
        """Rank *features* by deterministic rules for the given *domain*."""
        if features.empty:
            return []

        if domain == RecommendationDomain.STOCK:
            ranked = self._rank_stock(features)
        elif domain == RecommendationDomain.COLLECTIONS:
            ranked = self._rank_collections(features)
        else:  # pragma: no cover - guarded by schema validation
            return []

        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked[:top_n]

    @classmethod
    def _rank_stock(cls, features: pd.DataFrame) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        max_outflow = float(features["daily_demand"].max()) or 1.0
        for _, row in features.iterrows():
            sku_id = row["sku_id"]
            available = float(row["available_quantity"])
            threshold = float(row["low_stock_threshold"])
            daily_demand = float(row["daily_demand"])

            threshold_gap = (threshold - available) / (threshold + 1e-9)
            urgency = max(0.0, min(threshold_gap, 1.0))

            velocity = max(0.0, min(daily_demand / max_outflow, 1.0))

            stock_out_days = available / daily_demand if daily_demand > 0 else float("inf")
            depletion = _depletion_risk(stock_out_days)

            score = round(0.5 * urgency + 0.3 * velocity + 0.2 * depletion, 3)

            sku_name = row.get("sku_name", sku_id)
            items.append(
                {
                    "item_id": str(sku_id),
                    "label": str(sku_name),
                    "score": score,
                    "reason": _stock_reason(
                        sku_name, available, threshold, daily_demand, stock_out_days, row
                    ),
                }
            )
        return items

    @classmethod
    def _rank_collections(cls, features: pd.DataFrame) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        max_outstanding = max(1e-9, float(features["outstanding_amount"].max()))
        for _, row in features.iterrows():
            retailer_id = row["retailer_id"]
            outstanding = float(row["outstanding_amount"])
            overdue = float(row.get("overdue_amount", 0.0))
            utilization = float(row.get("credit_utilization", 0.0))

            overdue_ratio = overdue / outstanding if outstanding > 0 else 0.0
            amount_share = outstanding / max_outstanding

            score = round(0.5 * overdue_ratio + 0.3 * utilization + 0.2 * amount_share, 3)

            label = str(row.get("display_name", retailer_id))
            items.append(
                {
                    "item_id": str(retailer_id),
                    "label": label,
                    "score": score,
                    "reason": (
                        f"Outstanding {outstanding:.2f} with {overdue:.2f} overdue; "
                        f"credit utilized {utilization * 100:.0f}%."
                    ),
                }
            )
        return items


def _depletion_risk(days: float) -> float:
    if days >= 7.0:
        return 0.0
    if days <= 1.0:
        return 1.0
    return round(1.0 - (days - 1.0) / 6.0, 3)


def _stock_reason(
    sku_name: Any,
    available: float,
    threshold: float,
    daily_demand: float,
    stock_out_days: float,
    row: pd.Series,
) -> str:
    reasons: list[str] = []
    if available < threshold:
        reasons.append(f"below threshold ({available:.1f} on hand vs {threshold:.1f} min)")
    if daily_demand > 0:
        horizon = f"{stock_out_days:.1f}" if stock_out_days < 100 else "∞"
        reasons.append(f"~{horizon} days of stock left at current demand")
    if not reasons:
        return f"{sku_name}: stock level adequate."
    return f"{sku_name}: " + ", ".join(reasons) + " — consider restocking."
