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


# ---------------------------------------------------------------------------
# Agent platform (HLD-110, Phase 1)
# ---------------------------------------------------------------------------


class AgentExecutionMode(str, enum.Enum):
    """How an agent run should behave with respect to business actions."""

    EXECUTE = "execute"
    PROPOSE = "propose"


class AgentExecuteRequest(BaseModel):
    """Payload to trigger a single agent run."""

    agent_id: str = Field(..., description="Agent id, e.g. inventory_reorder.")
    organization_id: uuid.UUID = Field(..., description="Tenant/organization context.")
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Extra agent context (e.g. staff_id for assignments).",
    )
    mode: AgentExecutionMode = Field(
        default=AgentExecutionMode.EXECUTE,
        description="execute runs actions; propose records them without executing.",
    )


class AgentExecuteAllRequest(BaseModel):
    """Payload to run every registered agent."""

    organization_id: uuid.UUID = Field(..., description="Tenant/organization context.")
    context: dict[str, Any] = Field(default_factory=dict)
    mode: AgentExecutionMode = Field(default=AgentExecutionMode.EXECUTE)


class AgentActionInfo(BaseModel):
    """Metadata about one agent's capabilities (Action Center contract)."""

    agent_id: str
    name: str
    description: str
    actions: list[str]
    required_permissions: list[str] = Field(
        default_factory=list,
        description="Permission codes the caller must hold to run this agent.",
    )


class AvailableActionsResponse(BaseModel):
    """All agents and their actions for the Action Center."""

    agents: list[AgentActionInfo]


class AgentStepResponse(BaseModel):
    """A single recorded agent step."""

    tool_id: str
    action: str
    status: str
    detail: Any = None


class AgentExecutionResult(BaseModel):
    """Outcome of an agent run, returned synchronously from /execute."""

    agent_id: str
    status: str
    summary: str
    steps: list[AgentStepResponse] = Field(default_factory=list)


class AgentHealthResponse(BaseModel):
    """Agent platform liveness and capability summary."""

    status: str
    agents: list[str]
    tools: list[str]
