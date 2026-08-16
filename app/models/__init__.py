"""Pydantic schemas and ORM models for the Dairy AI application."""

from __future__ import annotations

# Import the ORM models so ``Base.metadata`` knows about them for create_all().
from app.models.agent import AgentExecution  # noqa: F401
from app.models.recommendation import AIRecommendation  # noqa: F401
from app.models.schemas import (  # noqa: F401
    AgentActionInfo,
    AgentExecuteAllRequest,
    AgentExecuteRequest,
    AgentExecutionMode,
    AgentExecutionResult,
    AgentHealthResponse,
    AgentStepResponse,
    AvailableActionsResponse,
    HealthCheck,
    RecommendationDomain,
    RecommendationDomainInfo,
    RecommendationItem,
    RecommendationRequest,
    RecommendationResponse,
)
