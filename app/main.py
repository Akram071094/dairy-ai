"""Main FastAPI application entry point.

Creates and configures the FastAPI application, registers exception
handlers and routers, and exposes ``app`` as the ASGI target for uvicorn.
"""

from __future__ import annotations

from fastapi import FastAPI

from app import __version__
from app.api import api_router
from app.config import settings
from app.exceptions.errors import register_exception_handlers


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    application = FastAPI(
        title=settings.app_name,
        version=__version__,
        debug=settings.debug,
    )

    register_exception_handlers(application)
    application.include_router(api_router, prefix=settings.api_prefix)

    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.debug)
