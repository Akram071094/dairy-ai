"""Pydantic schemas for API request/response serialization."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RecommendationDomain(str, enum.Enum):
    """Supported recommendation capabilities (deterministic for now)."""

    STOCK = "stock"
    COLLECTIONS = "collections"


class RecommendationRequest(BaseModel):
    """Payload describing the operational context for a recommendation."""

    organization_id: uuid.UUID = Field(..., description="Tenant/organization to analyze.")
    domain: RecommendationDomain = Field(
        default=RecommendationDomain.STOCK,
        description="Recommendation capability to run.",
    )
    top_n: int = Field(default=10, ge=1, le=100, description="Max recommendations to return.")
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional operational context (e.g. lookback days).",
    )


class RecommendationItem(BaseModel):
    """A single generated recommendation with supporting rationale."""

    item_id: str
    label: str
    score: float = Field(..., ge=0.0, le=1.0)
    reason: str = ""


class RecommendationResponse(BaseModel):
    """Response envelope wrapping a ranked list of recommendations."""

    organization_id: uuid.UUID
    domain: RecommendationDomain
    generated_at: datetime
    recommendations: list[RecommendationItem]


class RecommendationDomainInfo(BaseModel):
    """Metadata about an available recommendation capability."""

    domain: RecommendationDomain
    description: str


class HealthCheck(BaseModel):
    """Health check response payload."""

    status: str
    app: str
    version: str
