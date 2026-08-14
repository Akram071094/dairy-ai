"""Shared FastAPI dependencies (forwarded-user authentication)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.exceptions.errors import UnauthorizedError
from app.services.forwarded_auth import ForwardedUser, validate_forwarded_token

bearer_scheme = HTTPBearer(auto_error=False)

AuthCredentials = Annotated[
    HTTPAuthorizationCredentials | None,
    Depends(bearer_scheme),
]


async def get_forwarded_user(credentials: AuthCredentials) -> ForwardedUser:
    """Resolve the dairy-backend user behind the forwarded Bearer token.

    Used on Action Center endpoints so that a frontend user's login is the
    single authentication both services trust. Raises 401 when the token is
    missing/invalid and 403 when the user is outside the pinned organization.
    """
    if credentials is None:
        raise UnauthorizedError("Not authenticated.")
    return await validate_forwarded_token(credentials.credentials)


ForwardedUserDep = Annotated[ForwardedUser, Depends(get_forwarded_user)]
