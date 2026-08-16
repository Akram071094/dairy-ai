"""Validation of user JWTs forwarded from the frontend.

The Action Center is used by dairy-frontend users who are already logged
into dairy-backend. They forward their own access token; dairy-ai validates
it against dairy-backend (the authority) via ``GET /auth/me`` before running
any agent. Business actions still execute with dairy-ai's own service
account, so the forwarded token only gates access to the AI layer.

The ``organization_id`` claim is read from the (already validated) token
payload without re-verifying the signature — dairy-backend remains the
authority; the claim is used only for optional tenant pinning.

Role-based agent visibility is delegated to dairy-backend as well: the user's
authorization for the agents' required permission codes is resolved via
``POST /resolve/authorization/batch``, so dairy-ai never hardcodes roles.
"""

from __future__ import annotations

import base64
import json
import re
from typing import Any

import httpx
from pydantic import BaseModel, Field

from app.config import settings
from app.exceptions.errors import ForbiddenError, UnauthorizedError
from app.services.backend_client import BackendApiError, _unwrap_envelope
from app.utils.helpers import get_logger

logger = get_logger("forwarded_auth")

_JWT_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*$")


class ForwardedUser(BaseModel):
    """The authenticated dairy-backend user behind a forwarded token."""

    user_id: str | None = None
    email: str | None = None
    organization_id: str | None = None
    # Permission codes the user is authorized for (from /resolve/authorization/batch).
    permissions: set[str] = Field(default_factory=set)


def _decode_payload(token: str) -> dict[str, Any]:
    """Return the (unverified) JWT payload as a dict, or an empty dict."""
    if not _JWT_SEGMENT_RE.match(token or ""):
        return {}
    segment = token.split(".")[1]
    padding = "=" * (-len(segment) % 4)
    try:
        raw = base64.urlsafe_b64decode(segment + padding)
    except (ValueError, TypeError):
        return {}
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def organization_from_token(token: str) -> str | None:
    """Extract the ``organization_id`` claim without signature verification."""
    org = _decode_payload(token).get("organization_id")
    return str(org) if org else None


async def validate_forwarded_token(
    token: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ForwardedUser:
    """Validate a forwarded dairy-backend token and return its user.

    Raises:
        UnauthorizedError: Token is missing, malformed, expired, or revoked.
        ForbiddenError: The user belongs to a different organization than the
            pinned ``SERVICE_ORG_ID``.
        BackendApiError: dairy-backend could not be reached or returned an
            unexpected status while validating the token.
    """
    if not token:
        raise UnauthorizedError("Not authenticated.")

    async with httpx.AsyncClient(
        base_url=settings.backend_base_url,
        timeout=settings.agent_tool_timeout,
        transport=transport,
    ) as client:
        try:
            resp = await client.get(
                settings.backend_me_path,
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.HTTPError as exc:
            logger.warning("forwarded token validation failed: %s", exc)
            raise BackendApiError(f"dairy-backend unreachable: {exc}") from exc

    if resp.status_code == 401:
        raise UnauthorizedError("Not authenticated.")
    if resp.status_code >= 400:
        raise BackendApiError(
            f"dairy-backend {settings.backend_me_path} -> {resp.status_code}",
            status_code=502,
        )

    payload = resp.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise BackendApiError(
            "dairy-backend returned an invalid /auth/me response.",
            status_code=502,
        )

    organization_id = organization_from_token(token)
    if settings.service_org_id and organization_id != settings.service_org_id:
        raise ForbiddenError("Forbidden.")

    user_id = str(data["id"]) if data.get("id") else None
    permissions = await _resolve_permissions(token, user_id, transport=transport)

    return ForwardedUser(
        user_id=user_id,
        email=data.get("email"),
        organization_id=organization_id,
        permissions=permissions,
    )


async def _resolve_permissions(
    token: str,
    user_id: str | None,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> set[str]:
    """Ask dairy-backend which of the agents' required codes the user holds.

    Fails soft: any non-2xx or transport failure yields an empty set, which
    simply hides every permission-gated agent (the safe default).
    """
    from app.agents.registry import AgentRegistry  # lazy: avoids import cycles

    codes = AgentRegistry.required_permission_codes()
    if not codes or not user_id:
        return set()

    async with httpx.AsyncClient(
        base_url=settings.backend_base_url,
        timeout=settings.agent_tool_timeout,
        transport=transport,
    ) as client:
        try:
            resp = await client.post(
                settings.backend_authz_path,
                json={"user_id": user_id, "permissions": sorted(codes)},
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.HTTPError as exc:
            logger.warning("permission resolution failed: %s", exc)
            return set()

    if resp.status_code == 401:
        raise UnauthorizedError("Not authenticated.")
    if resp.status_code >= 400:
        logger.warning(
            "permission resolution returned %s; treating as unauthorized",
            resp.status_code,
        )
        return set()

    result = _unwrap_envelope(resp.json())
    results = result.get("results") if isinstance(result, dict) else None
    if not isinstance(results, list):
        return set()

    granted: set[str] = set()
    for item in results:
        if isinstance(item, dict) and item.get("authorized") is True:
            permission = item.get("permission")
            if permission:
                granted.add(permission)
    return granted
