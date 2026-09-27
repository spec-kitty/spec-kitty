"""HTTP clients and fallback helpers shared by the auth subsystem.

Two client flavors live here:

* ``PublicHttpClient`` for unauthenticated SaaS calls such as
  ``POST /oauth/token`` and ``GET /api/v1/me`` during browser login.
* ``OAuthHttpClient`` for authenticated SaaS calls that inject a bearer token
  and retry once on ``401`` after forcing a refresh.

Both clients share one transport hardening layer:

1. Use ``httpx.AsyncClient`` as the primary async transport.
2. If the request targets the configured SaaS host and ``httpx`` raises a
   transport error, retry the request once through a stdlib HTTPS path that
   explicitly prefers IPv6 before IPv4.
3. Translate any remaining transport failures into :class:`NetworkError`.

This keeps auth, refresh, WebSocket pre-connect, and sync-adjacent probes on
one hardened transport surface rather than each flow re-creating its own client
semantics.
"""

from __future__ import annotations

import asyncio
import http.client
import socket
import ssl
from types import TracebackType
from typing import Any
from urllib.parse import urlsplit

import httpx
from kernel.clock import now_utc, timedelta

from specify_cli.auth import get_token_manager
from specify_cli.auth.server_target import resolve_server_target_or_none
from specify_cli.auth.errors import (
    NetworkError,
    NotAuthenticatedError,
    TokenRefreshError,
)
from specify_cli.auth.refresh_transaction import RefreshLockTimeoutError

# Default timeout for all HTTP operations (per WP08 spec).
DEFAULT_TIMEOUT_SECONDS = 30.0


class _ResolvedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPSConnection pinned to a single resolved socket address."""

    def __init__(
        self,
        host: str,
        *,
        port: int,
        timeout: float,
        family: socket.AddressFamily,
        sockaddr: tuple[Any, ...],
    ) -> None:
        self._ssl_context = ssl.create_default_context()
        super().__init__(
            host,
            port=port,
            timeout=timeout,
            context=self._ssl_context,
        )
        self._family = family
        self._sockaddr = sockaddr

    def connect(self) -> None:
        raw = socket.socket(self._family, socket.SOCK_STREAM)
        raw.settimeout(self.timeout)
        raw.connect(self._sockaddr)
        self.sock = self._ssl_context.wrap_socket(raw, server_hostname=self.host)


class _BaseHttpClient:
    """Shared transport behavior for auth-related async HTTP clients."""

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._timeout = timeout
        self._client = client

    async def __aenter__(self) -> _BaseHttpClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    async def aclose(self) -> None:
        return None

    async def _send_with_fallback(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        try:
            return await self._request_with_httpx(method, url, **kwargs)
        except httpx.RequestError as exc:
            response = await self._try_stdlib_fallback(method, url, kwargs)
            if response is not None:
                return response
            raise NetworkError(f"HTTP transport error: {exc}") from exc

    async def _request_with_httpx(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        if self._client is not None:
            return await self._client.request(method, url, **kwargs)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            return await client.request(method, url, **kwargs)

    async def _try_stdlib_fallback(
        self,
        method: str,
        url: str,
        kwargs: dict[str, Any],
    ) -> httpx.Response | None:
        """Retry SaaS-bound requests via stdlib HTTPS when httpx transport fails."""
        if not _targets_configured_saas(url):
            return None
        try:
            return await asyncio.to_thread(
                _request_with_stdlib,
                method,
                url,
                kwargs,
                self._timeout,
            )
        except Exception as exc:  # noqa: BLE001 - stdlib fallback converts transport failures to NetworkError
            raise NetworkError(f"HTTP transport error: {exc}") from exc

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("PUT", url, **kwargs)

    async def patch(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("PATCH", url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("DELETE", url, **kwargs)

    async def request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        raise NotImplementedError


class PublicHttpClient(_BaseHttpClient):
    """Async HTTP client for unauthenticated SaaS calls."""

    async def request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        return await self._send_with_fallback(method, url, **kwargs)


class OAuthHttpClient(_BaseHttpClient):
    """Async HTTP client that injects OAuth bearer tokens and retries once on 401.

    Usage:
        async with OAuthHttpClient() as client:
            response = await client.get("https://api.example.com/v1/teams")
            response.raise_for_status()
            data = response.json()

    All HTTP methods (`get`, `post`, `put`, `patch`, `delete`, `request`) accept
    the same kwargs as `httpx.AsyncClient.request()`. If the caller supplies an
    explicit `Authorization` header in `headers`, it is overwritten with the
    bearer token produced by `TokenManager.get_access_token()`.
    """

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(timeout=timeout, client=client)

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Perform an HTTP request with bearer injection + 401 retry-once.

        Raises:
            NotAuthenticatedError: If no session is available or the refresh
                fails to produce a usable token.
            TokenRefreshError: If refresh explicitly fails (propagated).
            NetworkError: If the underlying transport raises
                `httpx.TransportError` (DNS, connection, timeout, etc.).
        """
        tm = get_token_manager()

        # First attempt: inject the current access token (auto-refresh if near expiry).
        try:
            access_token = await tm.get_access_token()
        except RefreshLockTimeoutError as exc:
            raise TokenRefreshError(str(exc)) from exc
        except (NotAuthenticatedError, TokenRefreshError):
            # Propagate auth errors unchanged — callers differentiate these.
            raise

        response = await self._send(method, url, access_token, kwargs)

        # If the server rejected our token, try a forced refresh + retry-once.
        if response.status_code == 401:
            # Close the stale response body before retrying (httpx best practice).
            await response.aclose()

            # The server's 401 is authoritative: the token is invalid even if
            # our local expiry timer says it's still good. Mark the current
            # access token as expired so `refresh_if_needed()` will actually
            # refresh rather than short-circuit as a no-op.
            self._force_access_token_expired(tm)

            # Force a refresh. If the server invalidated our session mid-flight,
            # `refresh_if_needed()` will raise RefreshTokenExpiredError /
            # SessionInvalidError (both subclasses of TokenRefreshError).
            try:
                await tm.refresh_if_needed()
            except RefreshLockTimeoutError as exc:
                raise TokenRefreshError(str(exc)) from exc

            # Re-fetch the (now-refreshed) access token.
            try:
                access_token = await tm.get_access_token()
            except RefreshLockTimeoutError as exc:
                raise TokenRefreshError(str(exc)) from exc

            response = await self._send(method, url, access_token, kwargs)

            if response.status_code == 401:
                # Still unauthorized after a fresh token — the session is dead.
                await response.aclose()
                raise NotAuthenticatedError(
                    "Authentication failed after token refresh. Please log in again.",
                )

        return response

    @staticmethod
    def _force_access_token_expired(tm: Any) -> None:
        """Mark the current session's access token as expired.

        This is the minimal-surface-area way to force the single-flight
        `refresh_if_needed()` path to actually refresh after a server-side 401.
        If there is no current session we leave the TokenManager untouched —
        the subsequent ``refresh_if_needed()`` will raise
        ``NotAuthenticatedError`` naturally.
        """
        session = tm.get_current_session()
        if session is None:
            return
        # Bump expiry well into the past so any buffer window still classifies
        # as expired.
        session.access_token_expires_at = now_utc() - timedelta(seconds=60)

    async def _send(
        self,
        method: str,
        url: str,
        access_token: str,
        kwargs: dict[str, Any],
    ) -> httpx.Response:
        """Inject the bearer header and delegate to httpx, translating network errors."""
        # Merge Authorization into caller-supplied headers (without mutating the caller's dict).
        caller_headers = kwargs.get("headers") or {}
        headers = dict(caller_headers)
        headers["Authorization"] = f"Bearer {access_token}"
        send_kwargs = dict(kwargs)
        send_kwargs["headers"] = headers
        return await self._send_with_fallback(method, url, **send_kwargs)


def _targets_configured_saas(url: str) -> bool:
    """True when ``url`` matches the resolved hosted target.

    T028 item 13 (D4): resolved through
    :func:`~specify_cli.auth.server_target.resolve_server_target_or_none`
    rather than the env-only ``get_saas_base_url()`` — with
    ``get_saas_base_url()`` now env-only-and-raising (endpoint opt-in,
    FR-011), the old call here would have silently disabled the stdlib
    fallback for every ``config.toml``-only-configured user. ``None`` (no
    endpoint configured, or an ambiguous split-brain) means the stdlib
    fallback is not applicable.
    """
    target = urlsplit(url)
    try:
        resolved = resolve_server_target_or_none()
    except Exception:  # noqa: BLE001 - split-brain/other faults mean stdlib fallback is not applicable
        return False
    if resolved is None:
        return False
    saas = urlsplit(resolved.resolved_server_url)
    return bool(target.hostname) and target.scheme == saas.scheme and target.hostname == saas.hostname and (target.port or 443) == (saas.port or 443)


def _request_with_stdlib(
    method: str,
    url: str,
    kwargs: dict[str, Any],
    timeout: float,
) -> httpx.Response:
    """Execute a request via stdlib HTTPS, preferring IPv6 before IPv4."""
    request = httpx.Request(method, url, **kwargs)
    url_obj = request.url
    host = str(url_obj.host)
    port = int(url_obj.port or 443)
    raw_path = url_obj.raw_path
    path = raw_path.decode("ascii") if isinstance(raw_path, bytes) else str(raw_path)
    body = request.read()
    headers = dict(request.headers)
    headers.setdefault("Connection", "close")

    last_exc: Exception | None = None
    for family, sockaddr in _resolve_candidate_addresses(host, port):
        conn: _ResolvedHTTPSConnection | None = None
        try:
            conn = _ResolvedHTTPSConnection(
                host,
                port=port,
                timeout=timeout,
                family=family,
                sockaddr=sockaddr,
            )
            conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            for key, value in headers.items():
                conn.putheader(key, value)
            conn.endheaders(body if body else None)
            response = conn.getresponse()
            content = response.read()
            return httpx.Response(
                response.status,
                headers=dict(response.getheaders()),
                content=content,
                request=request,
            )
        except Exception as exc:  # noqa: BLE001 - each address failure is retried before surfacing final transport error
            last_exc = exc
        finally:
            if conn is not None:
                conn.close()

    if last_exc is not None:
        raise last_exc
    raise OSError(f"Could not resolve any socket addresses for {host}:{port}")


def request_with_stdlib_fallback_sync(
    method: str,
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    **kwargs: Any,
) -> httpx.Response | None:
    """Attempt the stdlib HTTPS fallback for SaaS-bound synchronous requests."""
    if not _targets_configured_saas(url):
        return None
    last_exc: Exception | None = None
    for _ in range(3):
        try:
            return _request_with_stdlib(method, url, kwargs, timeout)
        except Exception as exc:  # noqa: BLE001 - retry loop converts final stdlib transport failure to NetworkError
            last_exc = exc
    assert last_exc is not None
    raise NetworkError(f"HTTP transport error: {last_exc}") from last_exc


def request_with_fallback_sync(
    method: str,
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    client: httpx.Client | None = None,
    **kwargs: Any,
) -> httpx.Response:
    """Perform a synchronous request with the shared SaaS fallback policy."""
    last_exc: Exception | None = None
    for _ in range(3):
        try:
            if client is not None:
                return client.request(method, url, **kwargs)
            with httpx.Client(timeout=timeout) as sync_client:
                return sync_client.request(method, url, **kwargs)
        except httpx.RequestError as exc:
            last_exc = exc
            response = request_with_stdlib_fallback_sync(method, url, timeout=timeout, **kwargs)
            if response is not None:
                return response
    assert last_exc is not None
    raise NetworkError(f"HTTP transport error: {last_exc}") from last_exc


def _resolve_candidate_addresses(
    host: str,
    port: int,
) -> list[tuple[socket.AddressFamily, tuple[Any, ...]]]:
    infos = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
    ordered = sorted(
        infos,
        key=lambda item: 0 if item[0] == socket.AF_INET6 else 1,
    )
    candidates: list[tuple[socket.AddressFamily, tuple[Any, ...]]] = []
    seen: set[tuple[socket.AddressFamily, tuple[Any, ...]]] = set()
    for family, _socktype, _proto, _canonname, sockaddr in ordered:
        candidate = (family, sockaddr)
        if candidate in seen:
            continue
        seen.add(candidate)
        candidates.append(candidate)
    return candidates
