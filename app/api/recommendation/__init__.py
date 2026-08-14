"""API route endpoints organized by domain."""

from __future__ import annotations

from app.api.recommendation.health import router as health_router
from app.api.recommendation.recommendations import router as recommendations_router

__all__ = ["health_router", "recommendations_router"]
