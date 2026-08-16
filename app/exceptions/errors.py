"""Custom exception types and FastAPI exception handlers."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class DairyAIError(Exception):
    """Base exception for all application-specific errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None) -> None:
        if message is not None:
            self.message = message
        super().__init__(self.message)


class UnauthorizedError(DairyAIError):
    """Raised when a request is not authenticated."""

    status_code = status.HTTP_401_UNAUTHORIZED
    message = "Not authenticated."


class ForbiddenError(DairyAIError):
    """Raised when an authenticated user lacks access to a resource."""

    status_code = status.HTTP_403_FORBIDDEN
    message = "Forbidden."


class NotFoundError(DairyAIError):
    """Raised when a requested resource does not exist."""

    status_code = status.HTTP_404_NOT_FOUND
    message = "Resource not found."


class ConflictError(DairyAIError):
    """Raised when a request conflicts with current state."""

    status_code = status.HTTP_409_CONFLICT
    message = "Resource conflict."


class DatabaseError(DairyAIError):
    """Raised when a database operation fails."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    message = "Database operation failed."


class RecommendationError(DairyAIError):
    """Raised when recommendation generation fails."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    message = "Could not generate recommendations."


def register_exception_handlers(app: FastAPI) -> None:
    """Attach JSON exception handlers for all custom exceptions to *app*."""

    @app.exception_handler(DairyAIError)
    async def dairy_ai_error_handler(request: Request, exc: DairyAIError) -> JSONResponse:
        """Convert :class:`DairyAIError` into a structured JSON response."""
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )
