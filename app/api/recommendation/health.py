"""API endpoints for health checks."""

from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.config import settings
from app.models.schemas import HealthCheck

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthCheck)
def health_check() -> HealthCheck:
    """Return a simple liveness response for load balancers and probes."""
    return HealthCheck(status="ok", app=settings.app_name, version=__version__)
