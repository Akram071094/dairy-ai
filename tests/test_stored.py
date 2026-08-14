"""Tests for the async-job stored-recommendation read path."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.recommendation import AIRecommendation, Base
from app.models.schemas import RecommendationDomain
from app.services.recommendation_service import RecommendationService


def _make_session() -> Session:
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(bind=engine)
    return Session(bind=engine, future=True)


def test_get_stored_returns_precomputed_rows() -> None:
    org_id = uuid.uuid4()
    session = _make_session()

    run_id = uuid.uuid4()
    session.add(
        AIRecommendation(
            organization_id=org_id,
            domain=RecommendationDomain.STOCK.value,
            item_id="sku-1",
            label="Whole Milk 1L",
            score=0.92,
            reason="Low stock vs demand",
            run_id=run_id,
            created_at=datetime.now(timezone.utc),
        )
    )
    session.commit()

    service = RecommendationService(session)
    response = service.get_stored(org_id, RecommendationDomain.STOCK)

    assert response.organization_id == org_id
    assert response.domain == RecommendationDomain.STOCK
    assert len(response.recommendations) == 1
    item = response.recommendations[0]
    assert item.item_id == "sku-1"
    assert item.score == 0.92
    assert item.label == "Whole Milk 1L"


def test_get_stored_empty_for_unknown_org() -> None:
    session = _make_session()
    service = RecommendationService(session)
    response = service.get_stored(uuid.uuid4(), RecommendationDomain.COLLECTIONS)

    assert response.recommendations == []
    assert response.domain == RecommendationDomain.COLLECTIONS


def test_get_stored_filters_by_domain() -> None:
    org_id = uuid.uuid4()
    session = _make_session()

    session.add_all(
        [
            AIRecommendation(
                organization_id=org_id,
                domain=RecommendationDomain.STOCK.value,
                item_id="sku-1",
                label="Whole Milk 1L",
                score=0.9,
                reason="r",
                run_id=uuid.uuid4(),
                created_at=datetime.now(timezone.utc),
            ),
            AIRecommendation(
                organization_id=org_id,
                domain=RecommendationDomain.COLLECTIONS.value,
                item_id="ret-1",
                label="Retailer A",
                score=0.5,
                reason="r",
                run_id=uuid.uuid4(),
                created_at=datetime.now(timezone.utc),
            ),
        ]
    )
    session.commit()

    service = RecommendationService(session)
    stock = service.get_stored(org_id, RecommendationDomain.STOCK)
    collections = service.get_stored(org_id, RecommendationDomain.COLLECTIONS)

    assert {r.item_id for r in stock.recommendations} == {"sku-1"}
    assert {r.item_id for r in collections.recommendations} == {"ret-1"}


def test_ai_recommendation_model_columns() -> None:
    columns = set(AIRecommendation.__table__.columns.keys())
    assert {
        "id",
        "organization_id",
        "domain",
        "item_id",
        "label",
        "score",
        "reason",
        "run_id",
        "created_at",
    }.issubset(columns)
