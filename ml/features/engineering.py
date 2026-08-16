"""Feature engineering for the decision engine.

Transforms raw operational DataFrames (inventory, stock movements,
outstandings, retailers) into per-item feature matrices consumed by the
deterministic scoring rules.
"""

from __future__ import annotations

import pandas as pd

OUTBOUND_MOVEMENT_TYPES = frozenset({"stock_out"})


def build_stock_features(
    inventory: pd.DataFrame,
    movements: pd.DataFrame,
    lookback_days: int = 30,
) -> pd.DataFrame:
    """Aggregate inventory + outbound movements into per-SKU stock features."""
    if inventory.empty:
        return pd.DataFrame()

    features = inventory.copy()

    features["available_quantity"] = pd.to_numeric(
        features["available_quantity"], errors="coerce"
    ).fillna(0.0)
    features["low_stock_threshold"] = pd.to_numeric(
        features["low_stock_threshold"], errors="coerce"
    ).fillna(0.0)

    if not movements.empty:
        outbound = movements[movements["movement_type"].isin(OUTBOUND_MOVEMENT_TYPES)]
        outbound = outbound.copy()
        outbound["quantity"] = pd.to_numeric(outbound["quantity"], errors="coerce").fillna(0.0)
        outflow = outbound.groupby("sku_id")["quantity"].sum().rename("outflow_qty")
        features = features.merge(outflow, on="sku_id", how="left")
    else:
        features["outflow_qty"] = 0.0

    features["outflow_qty"] = features["outflow_qty"].fillna(0.0)
    features["daily_demand"] = features["outflow_qty"] / max(lookback_days, 1)

    zero_demand = features["daily_demand"] <= 0
    features["days_of_stock"] = float("inf")
    features.loc[~zero_demand, "days_of_stock"] = (
        features.loc[~zero_demand, "available_quantity"]
        / features.loc[~zero_demand, "daily_demand"]
    )

    features["below_threshold"] = features["available_quantity"] < features["low_stock_threshold"]
    return features


def build_collection_features(
    outstandings: pd.DataFrame,
    retailers: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Aggregate outstanding balances into per-retailer collection features."""
    if outstandings.empty:
        return pd.DataFrame()

    features = outstandings.copy()

    for col in ("outstanding_amount", "overdue_amount", "credit_limit", "available_credit"):
        if col in features.columns:
            features[col] = pd.to_numeric(features[col], errors="coerce").fillna(0.0)

    if "credit_limit" in features.columns:
        features["credit_utilization"] = (
            (features["credit_limit"] - features["available_credit"]) / features["credit_limit"]
        ).clip(lower=0.0, upper=1.0)
        features.loc[features["credit_limit"] <= 0, "credit_utilization"] = 0.0
    else:
        features["credit_utilization"] = 0.0

    if retailers is not None and not retailers.empty:
        features = features.merge(retailers, on="retailer_id", how="left")

    return features
