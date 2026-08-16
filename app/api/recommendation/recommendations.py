"""API endpoints for recommendation generation."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.schemas import (
    RecommendationDomain,
    RecommendationDomainInfo,
    RecommendationRequest,
    RecommendationResponse,
)
from app.services.recommendation_service import RecommendationService

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

DBSession = Annotated[Session, Depends(get_db)]

_DOMAIN_DESCRIPTIONS: dict[RecommendationDomain, str] = {
    RecommendationDomain.STOCK: "Replenishment priorities computed from inventory levels and outbound demand.",
    RecommendationDomain.COLLECTIONS: "Retailer collection follow-up ranked by outstanding balance and credit utilization.",
}


@router.get("", response_model=list[RecommendationDomainInfo])
def list_domains() -> list[RecommendationDomainInfo]:
    """List the recommendation capabilities available in the engine."""
    return [
        RecommendationDomainInfo(domain=domain, description=description)
        for domain, description in _DOMAIN_DESCRIPTIONS.items()
    ]


DomainQuery = Annotated[
    RecommendationDomain,
    Query(description="Which precomputed domain to return."),
]


@router.get("/stored/{organization_id}", response_model=RecommendationResponse)
def get_stored_recommendations(
    organization_id: uuid.UUID,
    db: DBSession,
    domain: DomainQuery = RecommendationDomain.STOCK,
) -> RecommendationResponse:
    """Return the latest precomputed recommendations stored by the async job."""
    service = RecommendationService(db)
    result = service.get_stored(organization_id, domain)
    return result


@router.post("", response_model=RecommendationResponse)
def generate_recommendations(
    payload: RecommendationRequest,
    db: DBSession,
) -> RecommendationResponse:
    """Generate deterministic recommendations for the requested domain."""
    service = RecommendationService(db)
    return service.recommend(
        organization_id=payload.organization_id,
        domain=payload.domain,
        top_n=payload.top_n,
    )
