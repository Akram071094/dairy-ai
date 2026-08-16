"""Data loading helpers for the decision engine pipelines."""

from __future__ import annotations

import uuid

import pandas as pd
from sqlalchemy.orm import Session

from app.exceptions.errors import DatabaseError
from app.models.schemas import RecommendationDomain
from app.services.data_service import DataService
from ml.features.engineering import build_collection_features, build_stock_features

DEFAULT_LOOKBACK_DAYS = 30


def load_feature_frame(
    db: Session,
    organization_id: uuid.UUID,
    domain: RecommendationDomain,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> pd.DataFrame:
    """Load and preprocess operational data into a domain feature matrix."""
    service = DataService(db)
    if domain == RecommendationDomain.STOCK:
        inventory = service.fetch_inventory(organization_id)
        if inventory.empty:
            raise DatabaseError(f"No inventory records found for organization_id={organization_id}")
        movements = service.fetch_stock_movements(organization_id, days=lookback_days)
        return build_stock_features(inventory, movements, lookback_days=lookback_days)

    if domain == RecommendationDomain.COLLECTIONS:
        outstandings = service.fetch_outstandings(organization_id)
        if outstandings.empty:
            raise DatabaseError(
                f"No outstanding records found for organization_id={organization_id}"
            )
        retailers = service.fetch_retailers(organization_id)
        return build_collection_features(outstandings, retailers)

    raise ValueError(f"Unsupported recommendation domain: {domain}")


__all__ = ["load_feature_frame"]
