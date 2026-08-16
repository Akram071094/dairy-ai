"""API package - routers and endpoint definitions."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.recommendation import health_router, recommendations_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(recommendations_router)


__all__ = ["api_router"]
