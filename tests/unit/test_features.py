"""Unit tests for the feature engineering module."""

from __future__ import annotations

import pandas as pd

from ml.features.engineering import build_collection_features, build_stock_features


def test_build_stock_features_exposes_expected_columns(
    sample_inventory, sample_stock_movements
) -> None:
    """Stock features should contain the derived demand columns."""
    features = build_stock_features(sample_inventory, sample_stock_movements, lookback_days=30)
    assert "daily_demand" in features.columns
    assert "below_threshold" in features.columns
    assert "days_of_stock" in features.columns


def test_build_stock_features_empty_inventory() -> None:
    """An empty inventory frame should produce an empty feature frame."""
    features = build_stock_features(pd.DataFrame(), pd.DataFrame())
    assert features.empty


def test_build_collection_features_owns_display_name(sample_outstandings, sample_retailers) -> None:
    """Collection features should carry the retailer display name."""
    features = build_collection_features(sample_outstandings, sample_retailers)
    assert "credit_utilization" in features.columns
    assert "display_name" in features.columns
    assert len(features) == 3


def test_build_collection_features_empty() -> None:
    """An empty outstandings frame should produce an empty feature frame."""
    features = build_collection_features(pd.DataFrame())
    assert features.empty
