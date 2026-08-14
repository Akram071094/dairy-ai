"""Agent orchestration service.

Wires the tool executor + orchestrator for a request, runs the requested
agent(s), and persists every execution to the dairy-ai-owned
``agent_executions`` table for the audit trail.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.base import AgentResult
from app.models.agent import AgentExecution
from app.models.schemas import (
    AgentExecutionMode,
    AgentExecutionResult,
    AgentStepResponse,
)
from app.orchestrator import Orchestrator
from app.services.backend_client import BackendClient
from app.tools.executor import ToolExecutor
from app.utils.helpers import get_logger

logger = get_logger("agent_service")


class AgentService:
    """Execute agents and persist their runs."""

    def __init__(self, db: Session) -> None:
        self.db = db

    async def execute(
        self,
        agent_id: str,
        organization_id: uuid.UUID,
        context: dict | None = None,
        mode: AgentExecutionMode = AgentExecutionMode.EXECUTE,
    ) -> AgentExecutionResult:
        """Run one agent and persist the execution."""
        context = dict(context or {})
        context["organization_id"] = str(organization_id)
        context["execute"] = mode == AgentExecutionMode.EXECUTE

        async with BackendClient() as client:
            executor = ToolExecutor(client)
            result = await Orchestrator(executor).run_agent(agent_id, context)

        self._persist(agent_id, organization_id, result)
        return self._to_result(result)

    async def execute_all(
        self,
        organization_id: uuid.UUID,
        context: dict | None = None,
        mode: AgentExecutionMode = AgentExecutionMode.EXECUTE,
    ) -> list[AgentExecutionResult]:
        """Run every registered agent and persist each execution."""
        context = dict(context or {})
        context["organization_id"] = str(organization_id)
        context["execute"] = mode == AgentExecutionMode.EXECUTE

        async with BackendClient() as client:
            executor = ToolExecutor(client)
            results = await Orchestrator(executor).run_all(context)

        for result in results:
            self._persist(agent_id=result.agent_id, organization_id=organization_id, result=result)
        return [self._to_result(result) for result in results]

    def get_execution(self, execution_id: uuid.UUID) -> AgentExecution | None:
        """Return a persisted execution record, or ``None``."""
        return self.db.execute(
            select(AgentExecution).where(AgentExecution.id == execution_id)
        ).scalar_one_or_none()

    def list_executions(self, organization_id: uuid.UUID, limit: int = 50) -> list[AgentExecution]:
        """Return the most recent executions for an organization."""
        return list(
            self.db.execute(
                select(AgentExecution)
                .where(AgentExecution.organization_id == organization_id)
                .order_by(AgentExecution.created_at.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )

    def _persist(
        self,
        agent_id: str,
        organization_id: uuid.UUID,
        result: AgentResult,
    ) -> None:
        execution = AgentExecution(
            agent_id=agent_id,
            organization_id=organization_id,
            status=result.status,
            summary=result.summary,
            steps=[step.to_dict() for step in result.steps],
            completed_at=datetime.now(timezone.utc),
        )
        self.db.add(execution)
        try:
            self.db.commit()
        except Exception:  # noqa: BLE001 - audit write must not break the run
            logger.error("could not persist agent execution")
            self.db.rollback()

    @staticmethod
    def _to_result(result: AgentResult) -> AgentExecutionResult:
        return AgentExecutionResult(
            agent_id=result.agent_id,
            status=result.status,
            summary=result.summary,
            steps=[AgentStepResponse(**step.to_dict()) for step in result.steps],
        )
