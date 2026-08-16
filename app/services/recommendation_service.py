"""Recommendation orchestration service.

Pulls operational data for the requested domain, builds feature matrices,
and delegates scoring to the decision engine to produce recommendations.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pandas as pd

from app.models.recommendation import AIRecommendation
from app.models.schemas import (
    RecommendationDomain,
    RecommendationItem,
    RecommendationResponse,
)
from app.services.data_service import DataService
from ml.engine.decision_engine import DecisionEngine
from ml.features.engineering import build_collection_features, build_stock_features

DEFAULT_LOOKBACK_DAYS = 30


class RecommendationService:
    """Coordinate data access and scoring for recommendation requests."""

    def __init__(self, db, engine: DecisionEngine | None = None) -> None:
        self.data_service = DataService(db)
        self.engine = engine or DecisionEngine()

    def recommend(
        self,
        organization_id: uuid.UUID,
        domain: RecommendationDomain,
        top_n: int = 10,
    ) -> RecommendationResponse:
        """Generate and return the top *top_n* recommendations for *org_id*."""
        context = {"lookback_days": DEFAULT_LOOKBACK_DAYS}
        features = self._load_features(organization_id, domain, context)
        ranked = self.engine.recommend(features, domain=domain, top_n=top_n)

        items = [
            RecommendationItem(
                item_id=row["item_id"],
                label=row.get("label", row["item_id"]),
                score=float(row["score"]),
                reason=row.get("reason", ""),
            )
            for row in ranked
        ]
        return RecommendationResponse(
            organization_id=organization_id,
            domain=domain,
            generated_at=datetime.now(timezone.utc),
            recommendations=items,
        )

    def get_stored(
        self,
        organization_id: uuid.UUID,
        domain: RecommendationDomain,
        top_n: int = 100,
    ) -> RecommendationResponse:
        """Return the latest precomputed recommendations stored by the job."""
        from sqlalchemy import select

        rows = (
            self.data_service.db.execute(
                select(AIRecommendation)
                .where(
                    AIRecommendation.organization_id == organization_id,
                    AIRecommendation.domain == domain.value,
                )
                .order_by(AIRecommendation.created_at.desc())
                .limit(top_n)
            )
            .scalars()
            .all()
        )

        items = [
            RecommendationItem(
                item_id=row.item_id,
                label=row.label or row.item_id,
                score=float(row.score),
                reason=row.reason or "",
            )
            for row in rows
        ]
        return RecommendationResponse(
            organization_id=organization_id,
            domain=domain,
            generated_at=rows[0].created_at if rows else datetime.now(timezone.utc),
            recommendations=items,
        )

    def _load_features(
        self,
        organization_id: uuid.UUID,
        domain: RecommendationDomain,
        context: dict,
    ):
        if domain == RecommendationDomain.STOCK:
            lookback = context.get("lookback_days") or DEFAULT_LOOKBACK_DAYS
            inventory = self.data_service.fetch_inventory(organization_id)
            movements = self.data_service.fetch_stock_movements(organization_id, days=lookback)
            return build_stock_features(inventory, movements, lookback_days=lookback)

        if domain == RecommendationDomain.COLLECTIONS:
            outstandings = self.data_service.fetch_outstandings(organization_id)
            retailers = self.data_service.fetch_retailers(organization_id)
            return build_collection_features(outstandings, retailers)

        return pd.DataFrame()  # pragma: no cover - guarded upstream
