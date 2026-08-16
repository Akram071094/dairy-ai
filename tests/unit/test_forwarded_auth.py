"""Unit tests for forwarded-user JWT validation."""

from __future__ import annotations

import base64
import json
import uuid

import httpx
import pytest

from app.config import settings
from app.exceptions.errors import ForbiddenError, UnauthorizedError
from app.services.backend_client import BackendApiError
from app.services.forwarded_auth import (
    organization_from_token,
    validate_forwarded_token,
)

ORG_ID = str(uuid.UUID("11111111-1111-1111-1111-111111111111"))
USER_ID = str(uuid.UUID("22222222-2222-2222-2222-222222222222"))

_ME_BODY = {
    "success": True,
    "data": {"id": USER_ID, "email": "owner@org.com"},
}


def _encode_segment(data: dict) -> str:
    raw = json.dumps(data).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def make_token(organization_id: str | None = ORG_ID) -> str:
    header = _encode_segment({"alg": "HS256", "typ": "JWT"})
    payload: dict = {"sub": "u1", "email": "owner@org.com"}
    if organization_id is not None:
        payload["organization_id"] = organization_id
    return f"{header}.{_encode_segment(payload)}.fake-signature"


def _router_handler(
    *,
    authz_status: int = 200,
    authz_body: dict | None = None,
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/auth/me"):
            return httpx.Response(status_code=200, json=_ME_BODY)
        if request.url.path.endswith("/resolve/authorization/batch"):
            return httpx.Response(
                status_code=authz_status,
                json=authz_body or {"success": True, "data": {"results": []}},
            )
        return httpx.Response(status_code=404)

    return httpx.MockTransport(handler)


async def test_valid_token_maps_user() -> None:
    transport = _router_handler()
    user = await validate_forwarded_token(make_token(), transport=transport)
    assert user.user_id == USER_ID
    assert user.email == "owner@org.com"
    assert user.organization_id == ORG_ID


async def test_backend_401_raises_unauthorized() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(status_code=401, json={"detail": "Invalid token"})
    )
    with pytest.raises(UnauthorizedError):
        await validate_forwarded_token(make_token(), transport=transport)


async def test_backend_5xx_raises_api_error() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(status_code=500, json={"detail": "boom"})
    )
    with pytest.raises(BackendApiError):
        await validate_forwarded_token(make_token(), transport=transport)


async def test_missing_token_raises_unauthorized() -> None:
    with pytest.raises(UnauthorizedError):
        await validate_forwarded_token(
            "", transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"data": {}}))
        )


async def test_transport_failure_raises_api_error() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("unreachable", request=request)

    with pytest.raises(BackendApiError):
        await validate_forwarded_token(make_token(), transport=httpx.MockTransport(boom))


async def test_org_pin_rejects_foreign_user(monkeypatch) -> None:
    monkeypatch.setattr(settings, "service_org_id", ORG_ID)
    transport = _router_handler()
    token = make_token(organization_id="99999999-9999-9999-9999-999999999999")
    with pytest.raises(ForbiddenError):
        await validate_forwarded_token(token, transport=transport)


async def test_org_pin_accepts_matching_user(monkeypatch) -> None:
    monkeypatch.setattr(settings, "service_org_id", ORG_ID)
    transport = _router_handler()
    user = await validate_forwarded_token(make_token(), transport=transport)
    assert user.organization_id == ORG_ID


async def test_permission_resolution_populates_authorized_codes() -> None:
    authz_body = {
        "success": True,
        "data": {
            "user_id": USER_ID,
            "results": [
                {"authorized": True, "permission": "inventory:read"},
                {"authorized": False, "permission": "delivery:read"},
                {"authorized": True, "permission": "collection:read"},
            ],
        },
    }
    transport = _router_handler(authz_body=authz_body)
    user = await validate_forwarded_token(make_token(), transport=transport)
    assert user.permissions == {"inventory:read", "collection:read"}


async def test_permission_resolution_fails_soft_on_5xx() -> None:
    transport = _router_handler(authz_status=500, authz_body={"detail": "boom"})
    user = await validate_forwarded_token(make_token(), transport=transport)
    assert user.permissions == set()


async def test_permission_resolution_401_raises_unauthorized() -> None:
    transport = _router_handler(authz_status=401, authz_body={"detail": "x"})
    with pytest.raises(UnauthorizedError):
        await validate_forwarded_token(make_token(), transport=transport)


def test_organization_from_token_extracts_claim() -> None:
    assert organization_from_token(make_token()) == ORG_ID
    assert organization_from_token(make_token(organization_id=None)) is None
    assert organization_from_token("not-a-jwt") is None
    assert organization_from_token("") is None
