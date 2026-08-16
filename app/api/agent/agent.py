"""API endpoints for the agent platform (HLD-110, Phase 1)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import ForwardedUserDep
from app.database import get_db
from app.exceptions.errors import ForbiddenError, NotFoundError
from app.models.schemas import (
    AgentActionInfo,
    AgentExecuteAllRequest,
    AgentExecuteRequest,
    AgentExecutionResult,
    AgentHealthResponse,
    AgentStepResponse,
    AvailableActionsResponse,
)
from app.services.agent_service import AgentService
from app.services.forwarded_auth import ForwardedUser
from app.tools.registry import tool_registry

router = APIRouter(prefix="/agents", tags=["agents"])

DBSession = Annotated[Session, Depends(get_db)]


def _has_permissions(codes: tuple[str, ...], forwarded: ForwardedUser) -> bool:
    """Whether the forwarded user holds every required permission code."""
    return all(code in forwarded.permissions for code in codes)


@router.get("/health", response_model=AgentHealthResponse)
def agent_health() -> AgentHealthResponse:
    """Return agent platform liveness and capability summary."""
    from app.agents.registry import AgentRegistry

    return AgentHealthResponse(
        status="ok",
        agents=AgentRegistry.class_ids(),
        tools=tool_registry.all_ids(),
    )


@router.get("/available-actions", response_model=AvailableActionsResponse)
def available_actions(forwarded: ForwardedUserDep) -> AvailableActionsResponse:
    """Return agent capabilities for the Action Center, filtered by role."""
    from app.agents.registry import AgentRegistry

    agents = [
        AgentActionInfo(**meta)
        for meta in AgentRegistry.definitions()
        if _has_permissions(tuple(meta["required_permissions"]), forwarded)
    ]
    return AvailableActionsResponse(agents=agents)


def _assert_org_matches(organization_id: uuid.UUID, forwarded: ForwardedUserDep) -> None:
    """Reject payloads targeting an organization outside the pinned tenant."""
    if forwarded.organization_id is None:
        return
    if str(organization_id) != forwarded.organization_id:
        raise ForbiddenError("Forbidden.")


def _assert_agent_authorized(agent_id: str, forwarded: ForwardedUserDep) -> None:
    """Reject running an agent the caller lacks permission for."""
    from app.agents.registry import AgentRegistry

    if not _has_permissions(AgentRegistry.required_permissions_for(agent_id), forwarded):
        raise ForbiddenError("Forbidden.")


@router.post("/execute", response_model=AgentExecutionResult)
async def execute_agent(
    payload: AgentExecuteRequest,
    db: DBSession,
    forwarded: ForwardedUserDep,
) -> AgentExecutionResult:
    """Run a single agent and persist the execution."""
    _assert_org_matches(payload.organization_id, forwarded)
    _assert_agent_authorized(payload.agent_id, forwarded)
    service = AgentService(db)
    return await service.execute(
        agent_id=payload.agent_id,
        organization_id=payload.organization_id,
        context=payload.context,
        mode=payload.mode,
    )


@router.post("/execute-all", response_model=list[AgentExecutionResult])
async def execute_all_agents(
    payload: AgentExecuteAllRequest,
    db: DBSession,
    forwarded: ForwardedUserDep,
) -> list[AgentExecutionResult]:
    """Run every registered agent in order and persist each execution."""
    from app.agents.registry import AgentRegistry

    _assert_org_matches(payload.organization_id, forwarded)
    for agent_id in AgentRegistry.class_ids():
        _assert_agent_authorized(agent_id, forwarded)
    service = AgentService(db)
    return await service.execute_all(
        organization_id=payload.organization_id,
        context=payload.context,
        mode=payload.mode,
    )


@router.get("/executions/{execution_id}", response_model=AgentExecutionResult)
def get_execution(
    execution_id: uuid.UUID,
    db: DBSession,
    _: ForwardedUserDep,
) -> AgentExecutionResult:
    """Return a persisted agent execution record."""
    service = AgentService(db)
    execution = service.get_execution(execution_id)
    if execution is None:
        raise NotFoundError("Agent execution not found.")
    return AgentExecutionResult(
        agent_id=execution.agent_id,
        status=execution.status,
        summary=execution.summary or "",
        steps=[
            AgentStepResponse(
                tool_id=step.get("tool_id", ""),
                action=step.get("action", ""),
                status=step.get("status", ""),
                detail=step.get("detail"),
            )
            for step in (execution.steps or [])
        ],
    )
