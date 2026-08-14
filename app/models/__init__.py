"""Pydantic schemas and ORM models for the Dairy AI application."""

from __future__ import annotations

# Import the ORM models so ``Base.metadata`` knows about them for create_all().
from app.models.recommendation import AIRecommendation  # noqa: F401
from app.models.schemas import (  # noqa: F401
    HealthCheck,
    RecommendationDomain,
    RecommendationDomainInfo,
    RecommendationItem,
    RecommendationRequest,
    RecommendationResponse,
)
