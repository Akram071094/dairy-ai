"""Tests for the dairy-backend HTTP client (JWT lifecycle + error mapping)."""

from __future__ import annotations

import httpx
import pytest

from app.services.backend_client import BackendApiError, BackendAuthError, BackendClient


def _make_transport(handler):
    return httpx.MockTransport(handler)


def _login_handler(*, access="access-1", refresh="refresh-1"):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/auth/login":
            return httpx.Response(
                200,
                json={
                    "access_token": access,
                    "refresh_token": refresh,
                    "expires_in": 3600,
                    "token_type": "Bearer",
                },
            )
        if request.url.path == "/api/v1/auth/refresh":
            return httpx.Response(
                200, json={"access_token": "refreshed-access", "expires_in": 3600}
            )
        return httpx.Response(404)

    return handler


def _make_client(handler, **kwargs) -> BackendClient:
    kwargs.setdefault("max_retries", 0)
    return BackendClient(
        base_url="http://testserver",
        user="agent@dairy.ai",
        password="secret",
        transport=_make_transport(handler),
        **kwargs,
    )


def _login_ok(handler):
    """Wrap a handler so the login path always succeeds first."""

    def wrapped(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/auth/login":
            return httpx.Response(
                200,
                json={
                    "access_token": "access-1",
                    "refresh_token": "refresh-1",
                    "expires_in": 3600,
                },
            )
        return handler(request)

    return wrapped


@pytest.mark.asyncio
async def test_login_then_authorized_request() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path == "/api/v1/auth/login":
            return httpx.Response(
                200,
                json={
                    "access_token": "access-1",
                    "refresh_token": "refresh-1",
                    "expires_in": 3600,
                },
            )
        if request.url.path == "/api/v1/inventory/low-stock":
            assert request.headers["authorization"] == "Bearer access-1"
            return httpx.Response(200, json=[{"sku_id": "x"}])
        return httpx.Response(404)

    client = _make_client(handler)
    try:
        data = await client.get("/api/v1/inventory/low-stock")
    finally:
        await client.close()

    assert data == [{"sku_id": "x"}]
    assert [c.url.path for c in calls] == ["/api/v1/auth/login", "/api/v1/inventory/low-stock"]


@pytest.mark.asyncio
async def test_refresh_on_401() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/api/v1/auth/login":
            return httpx.Response(
                200,
                json={
                    "access_token": "access-1",
                    "refresh_token": "refresh-1",
                    "expires_in": 3600,
                },
            )
        if request.url.path == "/api/v1/auth/refresh":
            return httpx.Response(
                200, json={"access_token": "refreshed-access", "expires_in": 3600}
            )
        if request.headers["authorization"] == "Bearer access-1":
            return httpx.Response(401, json={"detail": "token expired"})
        return httpx.Response(200, json={"ok": True})

    client = _make_client(handler)
    try:
        data = await client.get("/api/v1/data")
    finally:
        await client.close()

    assert data == {"ok": True}
    assert calls == [
        "/api/v1/auth/login",
        "/api/v1/data",
        "/api/v1/auth/refresh",
        "/api/v1/data",
    ]


@pytest.mark.asyncio
async def test_login_failure_raises_auth_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "Invalid credentials"})

    client = _make_client(handler)
    try:
        with pytest.raises(BackendAuthError):
            await client.get("/api/v1/inventory/low-stock")
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_backend_4xx_raises_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "not found"})

    client = _make_client(_login_ok(handler))
    try:
        with pytest.raises(BackendApiError) as excinfo:
            await client.get("/api/v1/nope")
    finally:
        await client.close()

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_transport_error_raises_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = BackendClient(
        base_url="http://testserver",
        user="agent@dairy.ai",
        password="secret",
        transport=_make_transport(_login_ok(handler)),
        max_retries=1,
    )
    try:
        with pytest.raises(BackendApiError):
            await client.get("/api/v1/inventory/low-stock")
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_5xx_retried_then_raised() -> None:
    responses = [
        httpx.Response(500, json={"detail": "boom"}),
        httpx.Response(500, json={"detail": "boom"}),
        httpx.Response(503, json={"detail": "down"}),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return responses.pop(0)

    client = _make_client(_login_ok(handler), max_retries=2)
    try:
        with pytest.raises(BackendApiError) as excinfo:
            await client.get("/api/v1/inventory/low-stock")
    finally:
        await client.close()

    assert excinfo.value.status_code == 503
