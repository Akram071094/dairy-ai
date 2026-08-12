"""Unit tests for the deterministic decision engine."""

from __future__ import annotations

import pandas as pd

from app.models.schemas import RecommendationDomain
from ml.engine.decision_engine import DecisionEngine
from ml.features.engineering import build_collection_features, build_stock_features


def test_stock_engine_ranks_below_threshold_first(sample_inventory, sample_stock_movements) -> None:
    """SKUs below their low-stock threshold should rank above healthy stock."""
    features = build_stock_features(sample_inventory, sample_stock_movements, lookback_days=30)
    items = DecisionEngine().recommend(features, domain=RecommendationDomain.STOCK, top_n=10)

    assert len(items) == 3
    assert scores_are_sorted(items)

    ranked_sku_ids = [item["item_id"] for item in items]

    below_sku_id = str(features.loc[features["below_threshold"], "sku_id"].iloc[0])
    healthy_sku_id = str(sample_inventory["sku_id"].iloc[2])
    assert ranked_sku_ids.index(below_sku_id) < ranked_sku_ids.index(healthy_sku_id)
    assert items[0]["item_id"] == below_sku_id


def test_collections_engine_ranks_overdue_first(sample_outstandings, sample_retailers) -> None:
    """Retailers with higher overdue amounts should rank first."""
    features = build_collection_features(sample_outstandings, sample_retailers)
    items = DecisionEngine().recommend(features, domain=RecommendationDomain.COLLECTIONS, top_n=10)

    assert len(items) == 3
    assert scores_are_sorted(items)
    assert items[0]["item_id"] == str(sample_outstandings["retailer_id"].iloc[0])


def test_engine_empty_features_yields_nothing() -> None:
    """An empty feature matrix should yield no recommendations."""
    engine = DecisionEngine()
    empty_stock = build_stock_features(pd.DataFrame(), pd.DataFrame())
    empty_collections = build_collection_features(pd.DataFrame())

    assert engine.recommend(empty_stock, domain=RecommendationDomain.STOCK) == []
    assert engine.recommend(empty_collections, domain=RecommendationDomain.COLLECTIONS) == []


def scores_are_sorted(items: list[dict]) -> bool:
    """Return True if item scores are in non-increasing order."""
    values = [item["score"] for item in items]
    return all(values[i] >= values[i + 1] for i in range(len(values) - 1))
