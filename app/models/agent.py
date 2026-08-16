"""ORM model for the dairy-ai-owned agent execution audit table.

This is one of the tables dairy-ai owns (see AGENTS.md): every agent run is
persisted here for the audit trail and the Action Center history view.
Operational tables are never modified.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AgentExecution(Base):
    """A single agent run with its recorded steps."""

    __tablename__ = "agent_executions"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    summary: Mapped[str | None] = mapped_column(Text)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


__all__ = ["AgentExecution"]
