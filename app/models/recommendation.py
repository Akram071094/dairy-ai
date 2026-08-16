"""ORM model for the shared precomputed recommendations table.

This is the single table that dairy-ai owns: the scheduled/async job writes
recommendations here, and dairy-backend (or the UI) reads them through its
own endpoints. Existing platform tables are never modified.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AIRecommendation(Base):
    """A single precomputed recommendation row for an organization/domain."""

    __tablename__ = "ai_recommendations"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    domain: Mapped[str] = mapped_column(String(20), nullable=False)
    item_id: Mapped[str] = mapped_column(String(200), nullable=False)
    label: Mapped[str | None] = mapped_column(String(255))
    score: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    run_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_ai_recommendations_org_domain", "organization_id", "domain"),)


__all__ = ["AIRecommendation"]
