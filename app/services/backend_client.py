"""Async HTTP client for dairy-backend (JWT auth + typed calls).

The agent platform never executes business actions itself: it talks to
dairy-backend over REST APIs (double authorization — the backend remains the
final authority). This client owns the JWT lifecycle (login + refresh),
retries transient failures, and surfaces backend errors predictably.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.config import settings
from app.exceptions.errors import DairyAIError
from app.utils.helpers import get_logger

logger = get_logger("backend_client")


def _unwrap_envelope(payload: Any) -> Any:
    """Unwrap the standard dairy-backend response envelope.

    dairy-backend wraps every payload in ``{"success": bool, "data": ...}``;
    callers expect the ``data`` value (dict, list, or None).
    """
    if isinstance(payload, dict) and "success" in payload and "data" in payload:
        return payload["data"]
    return payload


class BackendAuthError(DairyAIError):
    """Raised when the agent cannot authenticate to dairy-backend."""

    status_code = 502
    message = "dairy-backend authentication failed."


class BackendApiError(DairyAIError):
    """Raised when a dairy-backend API call fails (non-2xx or transport)."""

    message = "dairy-backend API call failed."

    def __init__(
        self,
        message: str | None = None,
        *,
        status_code: int = 502,
        payload: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class BackendClient:
    """Authenticated HTTP client for dairy-backend.

    Args:
        base_url: Backend base URL (overrides settings when provided).
        user: Agent service-account email.
        password: Agent service-account password.
        login_path: Backend login endpoint path.
        refresh_path: Backend token refresh endpoint path.
        timeout: Per-request timeout in seconds.
        max_retries: Number of retries for 5xx/transport failures.
        transport: Optional httpx transport (used by tests, e.g. MockTransport).
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        user: str | None = None,
        password: str | None = None,
        login_path: str | None = None,
        refresh_path: str | None = None,
        timeout: int | None = None,
        max_retries: int | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = (base_url or settings.backend_base_url).rstrip("/")
        self.user = user or settings.backend_user
        self.password = password or settings.backend_password
        self.login_path = login_path or settings.backend_login_path
        self.refresh_path = refresh_path or settings.backend_refresh_path
        self.timeout = timeout or settings.agent_tool_timeout
        self.max_retries = (
            max_retries if max_retries is not None else settings.agent_tool_max_retries
        )
        self._client = httpx.AsyncClient(
            base_url=self.base_url, timeout=self.timeout, transport=transport
        )
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at: float | None = None

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> BackendClient:
        """Support ``async with BackendClient() as client``."""
        return self

    async def __aexit__(self, *exc: object) -> None:
        """Close the client when the async context exits."""
        await self.close()

    # ------------------------------------------------------------------
    # Auth lifecycle
    # ------------------------------------------------------------------

    async def _login(self) -> None:
        """Authenticate and store access/refresh tokens."""
        logger.info("backend login")
        resp = await self._client.post(
            self.login_path, json={"email": self.user, "password": self.password}
        )
        if resp.status_code != 200:
            raise BackendAuthError(
                f"dairy-backend login failed ({resp.status_code}): {resp.text[:200]}"
            )
        data = _unwrap_envelope(resp.json())
        self._access_token = data["access_token"]
        self._refresh_token = data.get("refresh_token") or self._refresh_token
        self._expires_at = time.monotonic() + int(data.get("expires_in", 3600)) - 60

    async def _refresh(self) -> None:
        """Refresh the access token; fall back to full login on failure."""
        if not self._refresh_token:
            await self._login()
            return
        resp = await self._client.post(
            self.refresh_path, json={"refresh_token": self._refresh_token}
        )
        if resp.status_code != 200:
            logger.warning("backend token refresh failed; re-logging in")
            await self._login()
            return
        data = _unwrap_envelope(resp.json())
        self._access_token = data["access_token"]
        self._expires_at = time.monotonic() + int(data.get("expires_in", 3600)) - 60

    async def _ensure_token(self) -> None:
        """Ensure a valid access token is available."""
        if not self._access_token:
            await self._login()
        elif self._expires_at is not None and time.monotonic() >= self._expires_at:
            await self._refresh()

    # ------------------------------------------------------------------
    # Request helper
    # ------------------------------------------------------------------

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Send an authenticated request to dairy-backend.

        Retries once after a token refresh on 401 and up to ``max_retries``
        times on 5xx/transport failures. Raises :class:`BackendApiError` on
        non-2xx and :class:`BackendAuthError` when authentication fails.
        """
        await self._ensure_token()
        headers = {"Authorization": f"Bearer {self._access_token}"}

        refresh_attempted = False
        attempt = 0
        while True:
            try:
                resp = await self._client.request(
                    method, path, params=params, json=json, headers=headers
                )
            except httpx.HTTPError as exc:
                if attempt < self.max_retries:
                    logger.warning("backend transport error; retrying")
                    attempt += 1
                    continue
                raise BackendApiError(f"dairy-backend unreachable: {exc}") from exc

            if resp.status_code == 401 and not refresh_attempted:
                refresh_attempted = True
                await self._refresh()
                headers = {"Authorization": f"Bearer {self._access_token}"}
                continue

            if 500 <= resp.status_code < 600 and attempt < self.max_retries:
                logger.warning("backend 5xx; retrying")
                attempt += 1
                continue

            if resp.status_code >= 400:
                payload: dict[str, Any] | None = None
                if resp.content:
                    try:
                        payload = resp.json()
                    except ValueError:
                        payload = None
                raise BackendApiError(
                    f"dairy-backend {method} {path} -> {resp.status_code}: {resp.text[:300]}",
                    status_code=resp.status_code,
                    payload=payload,
                )

            if resp.status_code == 204 or not resp.content:
                return None
            try:
                return _unwrap_envelope(resp.json())
            except ValueError:
                return None

    async def get(
        self, path: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """Send a GET request."""
        return await self.request("GET", path, params=params)

    async def post(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Send a POST request."""
        return await self.request("POST", path, params=params, json=json)
