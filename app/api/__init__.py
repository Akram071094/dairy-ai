"""API package - routers and endpoint definitions."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.endpoints import health, recommendations

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(recommendations.router)


__all__ = ["api_router"]
