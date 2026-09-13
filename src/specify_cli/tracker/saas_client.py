"""SaaS Tracker HTTP client with auth, retry, polling, and error handling.

All SaaS-backed tracker operations flow through ``SaaSTrackerClient``.
Endpoint paths match the PRI-12 frozen contract exactly.

Authentication (WP08 rewiring):
    Tokens and team context are read from the process-wide ``TokenManager``
    via ``specify_cli.auth.get_token_manager()``. Because the public surface
    is synchronous (``httpx.Client``) but ``TokenManager`` is async, a small
    sync bridge (``_fetch_access_token_sync`` + ``_force_refresh_sync``)
    runs token operations on a short-lived event loop.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
import hashlib
import json as json_module
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from kernel.clock import datetime, now_utc, timedelta
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit, urlunsplit

import httpx

from specify_cli.auth import get_token_manager
from specify_cli.auth.errors import (
    AuthenticationError,
    NotAuthenticatedError,
)
from specify_cli.auth.session import require_private_team_id
from specify_cli.core.contract_gate import validate_outbound_payload
from specify_cli.auth.server_target import resolve_server_target
from specify_cli.tracker.egress_verdict import (
    EgressDestination,
    TrackerEgressVerdict,
    tracker_egress_verdict,
)

_SESSION_EXPIRED_MESSAGE = "Session expired. Run `spec-kitty auth login` to re-authenticate."
_UNAUTHENTICATED_CATEGORY = "unauthenticated"

#: Poll vocabulary for async operations, local to this module: the durable
#: attempt ledger these states once fed belonged to the deleted sync transport.
_OUTCOME_DELIVERED = "delivered"
_OUTCOME_REFUSED = "refused"
_OUTCOME_PENDING = "pending"
_OUTCOME_UNKNOWN = "unknown"


def _normalize_origin(url: str) -> str:
    """Return the exact HTTP authority used for target-admission binding."""

    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in {"http", "https"} or parts.hostname is None:
        raise ValueError("SaaS URL must contain an http(s) origin")
    host = parts.hostname.encode("idna").decode("ascii").lower()
    default_port = 443 if parts.scheme.lower() == "https" else 80
    netloc = host if parts.port in {None, default_port} else f"{host}:{parts.port}"
    return urlunsplit((parts.scheme.lower(), netloc, "", "", ""))


#: This transport's own identifier-set fragment, rendered into the shared refusal
#: template in ``specify_cli/egress.py``. It is an **argument**, not a second
#: presentation of the policy (FR-008/SC-015) — each transport passes its own
#: because the two sets are asymmetric: this client carries ``mission_slug`` and
#: verbatim issue titles (both engagement names) and **no** ``decision_id``, so
#: naming a decision id here would tell an operator that something was at stake
#: which this transport cannot transmit (US2-AS2).
#:
#: Scope (ruling PB-3): the identifiers **of the project whose consent was
#: refused** — not the destination team, and not recipient ids.
TRACKER_EGRESS_IDENTIFIER_KINDS = "mission and engagement identifiers"


@dataclass(frozen=True, slots=True)
class _HostedTrackerAuthority:
    account_identity: str
    private_teamspace_id: str
    collaborative_team_slug: str


class SaaSTrackerClientError(RuntimeError):
    """Raised when a SaaS tracker API call fails.

    Attributes carry structured PRI-12 error envelope data for
    programmatic inspection (e.g., stale-binding detection).
    Backward compatible: ``SaaSTrackerClientError("msg")`` still works,
    and ``str(e)`` returns the message.
    """

    def __init__(
        self,
        message: str,
        *,
        error_code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
        user_action_required: bool = False,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        self.user_action_required = user_action_required


class TrackerEgressRefusedError(SaaSTrackerClientError):
    """Raised when the project owning the data has not consented to hosted sync.

    A subclass of :class:`SaaSTrackerClientError` deliberately: every existing
    caller already handles that type (``tracker/origin.py`` converts it to
    ``OriginBindingError``; ``saas_service.py`` to ``TrackerServiceError``), so a
    refusal degrades along the paths the codebase already has instead of arriving
    as an unhandled exception. ``error_code="project_consent_denied"`` makes it
    distinguishable from a transport or authorization failure — an operator told
    "HTTP 403" would go and check their token, which is not the problem.

    It is an **error**, not a silent no-op: these are interactive commands, and
    someone running ``sync push`` deserves to be told the push refused and why.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(
            f"Refusing to send tracker data to Spec Kitty SaaS: {reason}",
            error_code="project_consent_denied",
            status_code=None,
            details={"category": "project_consent_denied", "reason": reason},
            user_action_required=True,
        )


def _run_in_fresh_loop(coro: Any) -> Any:
    """Run ``coro`` on a fresh asyncio loop and return its result.

    Assumes the caller is not running inside an event loop itself. The
    SaaSTrackerClient is a synchronous transport so this assumption holds
    for the CLI code paths that use it.
    """
    new_loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(new_loop)
        return new_loop.run_until_complete(coro)
    finally:
        with suppress(Exception):
            asyncio.set_event_loop(None)
        new_loop.close()


def _fetch_access_token_sync() -> str | None:
    """Return a valid access token from TokenManager, or ``None`` if unauth."""
    tm = get_token_manager()
    if not tm.is_authenticated:
        return None
    try:
        return cast("str | None", _run_in_fresh_loop(tm.get_access_token()))
    except AuthenticationError:
        return None


def _force_refresh_sync() -> bool:
    """Force a token refresh via TokenManager (sync bridge).

    Marks the current session's access token as expired so the single-flight
    ``refresh_if_needed()`` actually runs. Returns ``True`` on success,
    raises ``AuthenticationError`` if refresh fails.
    """
    tm = get_token_manager()
    session = tm.get_current_session()
    if session is None:
        raise NotAuthenticatedError("No session to refresh")
    # Bump expiry so refresh_if_needed treats the token as stale.
    session.access_token_expires_at = now_utc() - timedelta(seconds=60)
    _run_in_fresh_loop(tm.refresh_if_needed())
    return True


def _hosted_authority_for_token(token: str) -> _HostedTrackerAuthority | None:
    """Derive exact hosted authority solely from the token-matched session."""
    session = get_token_manager().get_current_session()
    if session is None or not secrets.compare_digest(session.access_token, token):
        return None
    private_teamspace_id = require_private_team_id(session)
    if private_teamspace_id is None:
        return None
    collaborative_ids = {team.id.strip() for team in session.teams if not team.is_private_teamspace and isinstance(team.id, str) and team.id.strip()}
    if len(collaborative_ids) != 1:
        return None
    return _HostedTrackerAuthority(
        account_identity=session.user_id,
        private_teamspace_id=private_teamspace_id,
        collaborative_team_slug=collaborative_ids.pop(),
    )


# ---------------------------------------------------------------------------
# Error-envelope helpers
# ---------------------------------------------------------------------------


def _parse_error_envelope(response: httpx.Response) -> dict[str, Any]:
    """Extract PRI-12 error envelope fields from a non-2xx response.

    Returns a dict with keys: error_code, error_category, message, retryable,
    user_action_required, source, retry_after_seconds.
    Missing keys default to ``None`` (or ``False`` for booleans).

    Canonical-code coordination with #2944: the frozen PRI-12 ``ErrorEnvelope``
    spells the machine code ``code`` and current SaaS runtime producers emit
    ``code``, while the discovery-era control plane (and the observed
    ``FEATURE_DISABLED`` 403 in #4233) emits ``error_code``. ``code`` is read
    as canonical with ``error_code`` retained as a documented fallback — no
    second code taxonomy is invented here. Likewise the human message is read
    from ``message`` first, then a string ``error`` (the shape the live
    discovery 403 payload carries), then the bare HTTP status.
    """
    try:
        body: dict[str, Any] = response.json()
    except Exception:
        return {
            "error_code": None,
            "error_category": None,
            "message": f"HTTP {response.status_code}",
            "retryable": False,
            "user_action_required": None,
            "source": None,
            "retry_after_seconds": None,
        }

    code = body.get("code")
    if not isinstance(code, str):
        code = body.get("error_code") if isinstance(body.get("error_code"), str) else None
    message = body.get("message")
    if not isinstance(message, str):
        error_field = body.get("error")
        message = error_field if isinstance(error_field, str) else None
    return {
        "error_code": code,
        "error_category": body.get("error_category"),
        "message": message or f"HTTP {response.status_code}",
        "retryable": body.get("retryable", False),
        "user_action_required": body.get("user_action_required"),
        "source": body.get("source"),
        "retry_after_seconds": body.get("retry_after_seconds"),
        "idempotency_key": body.get("idempotency_key"),
        "operation_id": body.get("operation_id"),
        "status": body.get("status"),
        "effect_certainty": body.get("effect_certainty"),
    }


def _unauthenticated_error(message: str) -> SaaSTrackerClientError:
    return SaaSTrackerClientError(
        message,
        error_code=_UNAUTHENTICATED_CATEGORY,
        status_code=401,
        details={"category": _UNAUTHENTICATED_CATEGORY},
        user_action_required=True,
    )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class SaaSTrackerClient:
    """Low-level synchronous HTTP transport for the SaaS tracker API.

    Parameters
    ----------
    project_root:
        The checkout that **owns the data this client will send** — the mission's
        own repository, not the process's current working directory (#3030
        FR-029).  Every request is refused unless that project has consented to
        hosted sync.  Defaults to ``None``, which **denies**: a transport
        constructed without being told whose data it carries cannot resolve
        consent, and inability to determine consent is never consent (FR-003 /
        NFR-001).  The default is deliberately the refusing one so that a future
        construction site that forgets to pass it fails loudly rather than
        leaking silently.
    timeout:
        Per-request HTTP timeout in seconds (default 30).

    Notes
    -----
    Tokens and team slug are sourced from the process-wide TokenManager
    (see module docstring). Callers no longer pass a credential store.
    Authentication and team scope are **not** consent: the 2026-07-27 incident
    was carried by a correctly authenticated client with a correct team header.
    """

    def __init__(
        self,
        *,
        project_root: Path | None = None,
        timeout: float = 30.0,
        monotonic_clock: Callable[[], float] | None = None,
        jitter_randbelow: Callable[[int], int] | None = None,
    ) -> None:
        if project_root is None:
            self._project_root = None
        else:
            try:
                self._project_root = Path(project_root).resolve()
            except (OSError, RuntimeError) as exc:
                raise SaaSTrackerClientError(
                    f"Cannot resolve project root {project_root}: {exc}",
                    error_code="project_root_resolution_failed",
                    details={"project_root": str(project_root), "reason": str(exc)},
                ) from exc
        # Canonical server-target authority (#2146, re-homed from the deleted
        # sync config in issue #5): resolve the URL we will actually hit —
        # folding in SPEC_KITTY_SAAS_URL precedence — instead of the raw
        # config.toml accessor, which would silently ignore an env override.
        # #3980 (D-5 revised): an unconfigured machine resolves to the
        # packaged default target, so construction no longer fails closed on
        # a missing target — only an ambiguous env/config split-brain still
        # refuses. process_wide_override=False (#117): this client sends a
        # bearer token
        # with no human confirming the target at call time, so an ambiguous
        # env/config disagreement must fail closed here rather than silently
        # letting the env value win, the way the interactive `auth login`
        # command's whole-process override is allowed to.
        self._base_url = _normalize_origin(resolve_server_target(process_wide_override=False).resolved_server_url)
        self._timeout = timeout
        # Instance-scoped seam (#3187): retry/poll delays call ``self._sleep``
        # rather than the bare ``time.sleep``. ``time.sleep`` is a single
        # process-wide stdlib attribute, so a test that patches it (even via
        # ``specify_cli.tracker.saas_client.time.sleep``) records a call from
        # ANY code in the process during the patch window -- another thread's
        # leaked retry loop, or CPython's own ``subprocess.Popen._wait`` busy
        # loop, not just this client's own retry logic. Binding the callable
        # once per instance means only this object's own two call sites can
        # ever write to it, so a test can patch ``client._sleep`` and see
        # exactly its own calls, nothing else running in the process.
        self._sleep: Callable[[float], None] = time.sleep
        self._monotonic: Callable[[], float] = monotonic_clock or time.monotonic
        self._randbelow: Callable[[int], int] = jitter_randbelow or secrets.randbelow

    _STATUS_PATH = "/api/v1/tracker/status/"
    _MAPPINGS_PATH = "/api/v1/tracker/mappings/"
    _PULL_PATH = "/api/v1/tracker/pull/"
    _PUSH_PATH = "/api/v1/tracker/push/"
    _RUN_PATH = "/api/v1/tracker/run/"
    _OPERATIONS_PATH = "/api/v1/tracker/operations/{operation_id}/"
    _SEARCH_ISSUES_PATH = "/api/v1/tracker/issue-search/"
    _LIST_TICKETS_PATH = "/api/v1/tracker/list-tickets/"
    _BIND_ORIGIN_PATH = "/api/v1/tracker/mission-origin/bind/"
    _RESOURCES_PATH = "/api/v1/tracker/resources/"
    _BIND_RESOLVE_PATH = "/api/v1/tracker/bind-resolve/"
    _BIND_CONFIRM_PATH = "/api/v1/tracker/bind-confirm/"
    _BIND_VALIDATE_PATH = "/api/v1/tracker/bind-validate/"
    # Bounds how long an unchanged write's minted key stays fixed (#61
    # squad pass 2). Without this, a content-addressed key never changes for
    # a logically-static write (e.g. `run`'s payload is a config constant),
    # so the server's receipt store — which has no TTL/reaper — would let
    # the write execute exactly once per checkout forever, and would let one
    # transient "retryable: True" failure wedge every future resend
    # permanently. Matches the deleted durable allocator's own bound
    # (`sync/transport_attempts.py`'s `_LOGICAL_OPERATION_MAX_LIFETIME`).
    _IDEMPOTENCY_RESEND_WINDOW = timedelta(hours=1)

    # ----- routing helpers -----

    def _routing_params(
        self,
        provider: str,
        project_slug: str | None,
        binding_ref: str | None,
    ) -> dict[str, str]:
        """Build the routing-key dict for an API call.

        When *binding_ref* is provided it takes precedence over
        *project_slug*.  If neither is supplied a
        ``SaaSTrackerClientError`` with ``error_code="missing_routing_key"``
        is raised.
        """
        params: dict[str, str] = {"provider": provider}
        if binding_ref:
            params["binding_ref"] = binding_ref
        elif project_slug:
            params["project_slug"] = project_slug
        else:
            raise SaaSTrackerClientError(
                "Either project_slug or binding_ref must be provided.",
                error_code="missing_routing_key",
                status_code=None,
            )
        return params

    # ----- low-level request helpers -----

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        expected_team_slug: str | None = None,
        expected_account_identity: str | None = None,
        expected_private_teamspace_id: str | None = None,
        timeout_seconds: float | None = None,
    ) -> httpx.Response:
        """Issue a single HTTP request with auth + team-slug headers.

        Tokens and team slug come from the process-wide ``TokenManager``
        via the sync bridge helpers at the top of this module. No direct
        filesystem or credential-store access.

        **The per-project consent gate** (#3030 FR-029) is enforced by
        :meth:`_enforce_tracker_egress_consent`, called both here and at
        ``_request_with_retry``'s own entry — the two reachable entry points
        all ten endpoints and the operation poller pass through, so a new
        endpoint method cannot be added without inheriting it. It runs
        *before* the token is fetched: a refusal must not depend on auth state,
        must not mint a token for a project that may not transmit, and must be
        reported as a consent decision rather than as an authentication failure.

        Transport-migration note (an *unrelated* mission's FR-030 — not #3030's,
        which is the ``saas_client/`` package's gate; the two are adjacent here by
        accident of numbering): this module remains on the legacy
        ``httpx.Client(...)`` instantiation pattern because 130+
        downstream tests (under ``tests/tracker/``) patch
        ``specify_cli.tracker.saas_client.httpx.Client`` directly. The
        architectural test in
        ``tests/architectural/test_auth_transport_singleton.py``
        explicitly allowlists this file with a tracked follow-up — the
        centralized :class:`AuthenticatedClient` exists and is the
        target for the next migration wave (sync, websocket, and
        widen-mode SaaS).
        """
        self._enforce_tracker_egress_consent()

        access_token = _fetch_access_token_sync()
        if access_token is None:
            raise _unauthenticated_error("No valid access token. Run `spec-kitty auth login` to authenticate.")

        authenticated_authority = _hosted_authority_for_token(access_token)
        if authenticated_authority is None:
            raise _unauthenticated_error(
                "Token-matched account, Private Teamspace, and exactly one Collaborative Teamspace are required. Run `spec-kitty auth login` to authenticate."
            )
        if expected_team_slug is not None and authenticated_authority.collaborative_team_slug != expected_team_slug:
            raise SaaSTrackerClientError(
                "Authenticated team changed after durable operation allocation.",
                error_code="target_authority_mismatch",
                details={
                    "error_category": "target_authority_mismatch",
                    "effect_certainty": "no_effect",
                },
                user_action_required=True,
            )
        if (
            expected_account_identity is not None
            and expected_private_teamspace_id is not None
            and (
                authenticated_authority.account_identity != expected_account_identity
                or authenticated_authority.private_teamspace_id != expected_private_teamspace_id
            )
        ):
            raise SaaSTrackerClientError(
                "Authenticated account or Private Teamspace changed after durable allocation.",
                error_code="target_authority_mismatch",
                details={
                    "error_category": "target_authority_mismatch",
                    "effect_certainty": "no_effect",
                },
                user_action_required=True,
            )

        merged_headers: dict[str, str] = {
            "Authorization": f"Bearer {access_token}",
            "X-Team-Slug": authenticated_authority.collaborative_team_slug,
        }
        if headers:
            merged_headers.update(headers)

        url = f"{self._base_url}{path}"

        try:
            with httpx.Client(timeout=timeout_seconds or self._timeout) as client:
                return client.request(
                    method,
                    url,
                    json=json,
                    headers=merged_headers,
                    params=params,
                )
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout) as exc:
            raise SaaSTrackerClientError(
                f"Cannot connect to Spec Kitty SaaS at {url}. Check your network connection.",
                details={"effect_certainty": "no_effect"},
            ) from exc
        except httpx.TimeoutException as exc:
            raise SaaSTrackerClientError(
                f"Cannot connect to Spec Kitty SaaS at {url}. Check your network connection.",
                details={"effect_certainty": "unknown"},
            ) from exc

    def _physical_request_with_retry(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        authority: _HostedTrackerAuthority,
        deadline: datetime,
        monotonic_deadline: float,
        allow_error_response: bool = False,
    ) -> httpx.Response:
        """Issue a request with 401-refresh and 429-rate-limit retry logic."""
        request_timeout = min(
            self._timeout,
            self._remaining_transport_seconds(deadline, monotonic_deadline),
        )
        if request_timeout <= 0:
            raise SaaSTrackerClientError(
                "Hosted tracker operation exceeded its transport deadline before I/O.",
                error_code="deadline_exceeded",
                details={"effect_certainty": "no_effect"},
                user_action_required=True,
            )
        response = self._request(
            method,
            path,
            json=json,
            headers=headers,
            params=params,
            expected_team_slug=authority.collaborative_team_slug,
            expected_account_identity=authority.account_identity,
            expected_private_teamspace_id=authority.private_teamspace_id,
            timeout_seconds=request_timeout,
        )

        # --- 401: one refresh + retry ---
        if response.status_code == 401:
            try:
                # Force a refresh via TokenManager (sync bridge). The single-flight
                # lock inside TokenManager guarantees at most one concurrent refresh
                # across threads / callers.
                _force_refresh_sync()
            except AuthenticationError as exc:
                raise SaaSTrackerClientError(
                    _SESSION_EXPIRED_MESSAGE,
                    error_code="session_expired",
                    status_code=401,
                    details={"effect_certainty": "no_effect"},
                    user_action_required=True,
                ) from exc
            except Exception as exc:
                raise SaaSTrackerClientError(
                    _SESSION_EXPIRED_MESSAGE,
                    error_code="session_expired",
                    status_code=401,
                    details={"effect_certainty": "no_effect"},
                    user_action_required=True,
                ) from exc

            remaining_after_refresh = self._remaining_transport_seconds(
                deadline,
                monotonic_deadline,
            )
            if remaining_after_refresh <= 0:
                raise SaaSTrackerClientError(
                    "Authentication retry exceeded the transport operation deadline.",
                    error_code="deadline_exceeded",
                    status_code=401,
                    details={"effect_certainty": "no_effect"},
                    user_action_required=True,
                )
            response = self._request(
                method,
                path,
                json=json,
                headers=headers,
                params=params,
                expected_team_slug=authority.collaborative_team_slug,
                expected_account_identity=authority.account_identity,
                expected_private_teamspace_id=authority.private_teamspace_id,
                timeout_seconds=min(self._timeout, remaining_after_refresh),
            )
            if response.status_code == 401:
                raise SaaSTrackerClientError(
                    _SESSION_EXPIRED_MESSAGE,
                    error_code="session_expired",
                    status_code=401,
                    details={"effect_certainty": "no_effect"},
                    user_action_required=True,
                )

        # --- 429: respect retry_after_seconds ---
        if response.status_code == 429:
            envelope = _parse_error_envelope(response)
            wait_seconds = envelope.get("retry_after_seconds")
            if wait_seconds is None or not isinstance(wait_seconds, (int, float)):
                wait_seconds = 5
            if float(wait_seconds) >= self._remaining_transport_seconds(
                deadline,
                monotonic_deadline,
            ):
                raise SaaSTrackerClientError(
                    "Rate-limit retry would exceed the transport operation deadline.",
                    error_code="deadline_exceeded",
                    status_code=429,
                    details={"effect_certainty": "no_effect"},
                    user_action_required=True,
                )
            self._sleep(float(wait_seconds))

            remaining_after_sleep = self._remaining_transport_seconds(
                deadline,
                monotonic_deadline,
            )
            if remaining_after_sleep <= 0:
                raise SaaSTrackerClientError(
                    "Rate-limit backoff exhausted the transport operation deadline.",
                    error_code="deadline_exceeded",
                    status_code=429,
                    details={"effect_certainty": "no_effect"},
                    user_action_required=True,
                )

            response = self._request(
                method,
                path,
                json=json,
                headers=headers,
                params=params,
                expected_team_slug=authority.collaborative_team_slug,
                expected_account_identity=authority.account_identity,
                expected_private_teamspace_id=authority.private_teamspace_id,
                timeout_seconds=min(self._timeout, remaining_after_sleep),
            )
            if response.status_code == 429:
                envelope = _parse_error_envelope(response)
                raise SaaSTrackerClientError(
                    envelope.get("message") or "Rate limited by SaaS API.",
                    error_code="rate_limited",
                    status_code=429,
                    details={**envelope, "effect_certainty": "no_effect"},
                )

        # --- Other non-2xx ---
        if response.status_code >= 400:
            if allow_error_response:
                return response
            envelope = _parse_error_envelope(response)
            msg = envelope.get("message") or f"HTTP {response.status_code}"
            # user_action_required is a boolean per PRI-12 ErrorEnvelope.
            # When True, suffix the message with generic guidance.
            if envelope.get("user_action_required"):
                msg += " (action required — check the Spec Kitty dashboard)"
            raise SaaSTrackerClientError(
                msg,
                # PRI-12 ``code`` is canonical (#2944 coordination): the stable
                # machine code must survive onto the exception, with the
                # category kept only as a fallback when no code was emitted —
                # the old category-first order masked ``binding_not_found`` and
                # friends from every code-driven consumer.
                error_code=envelope.get("error_code") or envelope.get("error_category"),
                status_code=response.status_code,
                details=envelope,
                user_action_required=bool(envelope.get("user_action_required")),
            )

        return response

    def _request_with_retry(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        poll_async: bool = True,
    ) -> httpx.Response:
        """Run one logical tracker operation across all physical retries.

        Consent gate → token → hosted authority, then the physical request with
        its 401-refresh and 429-backoff retries. A write answered ``202`` polls
        its operations endpoint to a terminal outcome before returning.

        Nothing is persisted locally between calls, but for writes the minted
        idempotency key is a deterministic digest of (project identity, write
        kind, payload, coarse resend-window bucket) — see ``_content_digest``
        — unless the caller supplies its own key. Because the digest is
        deterministic, a byte-identical resend from a *new* process after the
        original died mid-flight mints the same key within the same
        ``_IDEMPOTENCY_RESEND_WINDOW`` bucket, so the server's receipt store
        dedupes it exactly as it would a same-process physical retry; the
        property survives process death, not just this invocation's retries.
        A resend with different payload content mints a different key and is
        never mistaken for the earlier attempt. The resend-window bucket
        bounds how long an unchanged write's key stays fixed, so a
        logically-static write is not stuck executing only once per checkout
        forever, and a stale ``retryable: True`` failure receipt does not
        wedge every future resend permanently — only resends within the same
        window.
        """
        self._enforce_tracker_egress_consent()
        access_token = _fetch_access_token_sync()
        if access_token is None:
            raise _unauthenticated_error("No valid access token. Run `spec-kitty auth login` to authenticate.")
        authority = _hosted_authority_for_token(access_token)
        if authority is None:
            raise _unauthenticated_error(
                "Token-matched account, Private Teamspace, and exactly one Collaborative Teamspace are required. Run `spec-kitty auth login` to authenticate."
            )
        caller_key = (headers or {}).get("Idempotency-Key")
        if caller_key is not None and not caller_key.strip():
            raise SaaSTrackerClientError("Idempotency-Key must be non-empty", error_code="invalid_operation_request")
        is_write = path in {
            self._BIND_ORIGIN_PATH,
            self._BIND_CONFIRM_PATH,
            self._PUSH_PATH,
            self._RUN_PATH,
        }
        # A minted key must be deterministic across process death, not just
        # across physical retries of one invocation: a crash-and-resend of an
        # unchanged write should collide with the earlier attempt's key so the
        # server's receipt store (unique on (team, direction, operation_name,
        # idempotency_key)) dedupes it, rather than a random key reapplying
        # the write (#61). Digest locally resolvable project identity + write
        # kind + payload, bounded by a coarse resend-window bucket — no store
        # needed, and it keeps the wire shape the deleted durable allocator
        # used (``logical-operation:write:`` + 64 hex) that the server's
        # non-emptiness check accepts. The bucket is required, not cosmetic:
        # without it a logically-static write (e.g. `run`'s config-derived
        # payload) mints the same key forever, so the server's receipt store
        # (no TTL, no reaper) lets it execute exactly once per checkout, and
        # lets one transient "retryable: True" failure wedge every future
        # resend permanently (squad pass 2, #61 fix round).
        native_identity = caller_key.strip() if caller_key is not None else f"logical-operation:write:{self._content_digest(path, json)}"
        physical_headers = dict(headers or {})
        if is_write:
            physical_headers.setdefault("Idempotency-Key", native_identity)
        deadline = now_utc() + timedelta(seconds=min(max(self._timeout * 4, 30.0), 300.0))
        monotonic_deadline = self._monotonic() + max(0.0, self._remaining_seconds(deadline))
        response = self._physical_request_with_retry(
            method,
            path,
            json=json,
            headers=physical_headers or None,
            params=params,
            authority=authority,
            deadline=deadline,
            monotonic_deadline=monotonic_deadline,
        )
        if response.status_code == 202 and is_write:
            operation_id = self._required_operation_id(response)
            if not poll_async:
                return response
            return self._poll_operation(
                authority,
                operation_id=operation_id,
                method=method,
                path=path,
                deadline=deadline,
                monotonic_deadline=monotonic_deadline,
            )
        return response

    def _content_digest(self, path: str, payload: dict[str, Any] | None) -> str:
        """Deterministic 64-hex digest of (project identity, write kind, payload, resend window).

        A byte-identical repeat of the same logical write — including one
        replayed from a fresh process after the original died mid-flight —
        hashes to the same digest as long as both attempts fall in the same
        ``_IDEMPOTENCY_RESEND_WINDOW`` bucket, so the server dedupes it. A
        write with different content (a later push with new items, a
        different provider) hashes differently and is never mistaken for the
        earlier one. Once the current bucket elapses, an otherwise-unchanged
        write mints a new digest: a logically-static write (e.g. ``run``'s
        config-derived payload) can still execute again after the window,
        and a resend of a write whose only prior receipt is a stale
        ``retryable: True`` failure is not wedged forever — it is wedged for
        at most one window.
        """
        window_seconds = self._IDEMPOTENCY_RESEND_WINDOW.total_seconds()
        resend_bucket = int(now_utc().timestamp() // window_seconds)
        # No `default=str` (#315): every real payload here already came from
        # `json.loads` on its way in, so the fallback's only actual effect
        # was to make a non-JSON-serialisable member (an object with no
        # stable `__str__`, e.g. its default `repr` memory address, or a
        # `set`'s hash-seed-dependent iteration order) mint a different
        # digest per process instead of raising loudly — the opposite of
        # this method's determinism contract above.
        canonical = json_module.dumps(
            {
                "project_root": str(self._project_root) if self._project_root is not None else "",
                "write_kind": path,
                "payload": payload or {},
                "resend_bucket": resend_bucket,
            },
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()  # noqa: TID251 - idempotency-key body checksum, not charter content

    def _current_tracker_egress_verdict(self) -> TrackerEgressVerdict:
        """Evaluate Channel 2 without duplicating the policy call-site seam."""

        return tracker_egress_verdict(
            self._project_root,
            destination=EgressDestination.HOSTED_SERVICE,
            identifiers=TRACKER_EGRESS_IDENTIFIER_KINDS,
        )

    def _enforce_tracker_egress_consent(self) -> None:
        """Raise :class:`TrackerEgressRefusedError` when Channel 2 refuses.

        The single implementation of the per-project consent gate (#3030
        FR-029). Called from both ``_request`` and ``_request_with_retry`` —
        each is an entry point a caller can reach directly, and each must
        refuse *before* fetching/minting a token for a project that may not
        transmit (#458: previously each call site duplicated the
        ``verdict``/``raise`` pair textually instead of sharing one
        implementation).
        """
        verdict = self._current_tracker_egress_verdict()
        if verdict.refused:
            raise TrackerEgressRefusedError(verdict.message)

    @staticmethod
    def _required_operation_id(response: httpx.Response) -> str:
        try:
            body = response.json()
        except Exception as exc:
            raise SaaSTrackerClientError(
                "Async tracker response did not contain valid JSON.",
                error_code="invalid_async_response",
            ) from exc
        operation_id = body.get("operation_id") if isinstance(body, dict) else None
        if not isinstance(operation_id, str) or not operation_id.strip():
            raise SaaSTrackerClientError(
                "Async tracker response did not contain operation_id.",
                error_code="invalid_async_response",
            )
        return operation_id

    @staticmethod
    def _remaining_seconds(deadline: datetime) -> float:
        return (deadline - now_utc()).total_seconds()

    def _remaining_transport_seconds(
        self,
        deadline: datetime,
        monotonic_deadline: float,
    ) -> float:
        """Return the tighter wall-clock and injected-monotonic budget."""
        return min(
            self._remaining_seconds(deadline),
            monotonic_deadline - self._monotonic(),
        )

    # ----- polling -----

    def _poll_operation(
        self,
        authority: _HostedTrackerAuthority,
        *,
        operation_id: str,
        method: str,
        path: str,
        deadline: datetime,
        monotonic_deadline: float,
    ) -> httpx.Response:
        """Poll one async operation to a terminal outcome.

        The timing contract is unchanged from the leased poller it replaces:
        base delay 1.0 s doubling per still-running poll, capped at 30 s, each
        interval scaled by jitter in ``[0.8, 1.2)``, refusing rather than
        sleeping past the remaining budget.
        """
        delay = 1.0
        while True:
            value = self._physical_request_with_retry(
                "GET",
                self._OPERATIONS_PATH.format(operation_id=operation_id),
                authority=authority,
                deadline=deadline,
                monotonic_deadline=monotonic_deadline,
                allow_error_response=True,
            )
            outcome, category = self._classify_operation_query_response(
                value,
                expected_operation_id=operation_id,
            )
            if outcome == _OUTCOME_DELIVERED:
                reference = self._terminal_operation_result_reference(value)
                assert reference is not None
                return httpx.Response(
                    200,
                    content=reference.encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    request=httpx.Request(method, f"{self._base_url}{path}"),
                )
            if outcome == _OUTCOME_REFUSED:
                message, details = self._operation_failure_details(value)
                raise SaaSTrackerClientError(
                    message,
                    error_code=category or "remote_operation_failed",
                    details={**details, "error_category": category, "operation_id": operation_id},
                    user_action_required=True,
                )
            if outcome == _OUTCOME_UNKNOWN:
                raise SaaSTrackerClientError(
                    "Hosted tracker query outcome is unknown and requires operator recovery.",
                    error_code="recovery_required",
                    details={"operation_id": operation_id},
                    user_action_required=True,
                )
            remaining = self._remaining_transport_seconds(
                deadline,
                monotonic_deadline,
            )
            jitter_factor = 0.8 + (self._randbelow(4000) / 10000)
            sleep_for = min(delay, 30.0) * jitter_factor
            if sleep_for >= remaining:
                raise SaaSTrackerClientError(
                    "Tracker operation polling exceeded its transport deadline.",
                    error_code="recovery_required",
                    details={"operation_id": operation_id},
                    user_action_required=True,
                )
            self._sleep(sleep_for)
            delay = min(delay * 2, 30.0)

    @staticmethod
    def _classify_operation_query_response(
        response: object,
        *,
        expected_operation_id: str | None = None,
    ) -> tuple[str, str | None]:
        """Classify one operations-endpoint answer into the poll vocabulary."""
        if not isinstance(response, httpx.Response):
            raise SaaSTrackerClientError("Tracker operation query returned an invalid response")
        try:
            body = response.json()
        except Exception:
            return _OUTCOME_UNKNOWN, None
        if not isinstance(body, dict):
            return _OUTCOME_UNKNOWN, None
        if expected_operation_id is not None and body.get("operation_id") is not None and body.get("operation_id") != expected_operation_id:
            return _OUTCOME_UNKNOWN, None
        status = body.get("status")
        if status == "completed":
            return _OUTCOME_DELIVERED, None
        if status == "failed":
            error = body.get("error")
            category = error.get("error_category") if isinstance(error, dict) else None
            if (
                category == "project_not_admitted"
                and body.get("operation_id") == expected_operation_id
                and isinstance(error, dict)
                and error.get("retryable") is False
            ):
                return _OUTCOME_REFUSED, "project_not_admitted"
            return _OUTCOME_REFUSED, "remote_operation_failed"
        if status in {"pending", "running"}:
            return _OUTCOME_PENDING, None
        if (
            response.status_code == 400
            and body.get("error_category") == "project_not_admitted"
            and body.get("status") == "rejected"
            and body.get("retryable") is False
            and body.get("operation_id") == expected_operation_id
        ):
            return _OUTCOME_REFUSED, "project_not_admitted"
        return _OUTCOME_UNKNOWN, None

    @staticmethod
    def _terminal_operation_result_reference(response: object) -> str | None:
        """Serialized result payload of a completed operation, or ``None``."""
        if not isinstance(response, httpx.Response):
            return None
        try:
            body = response.json()
        except Exception:
            return None
        if not isinstance(body, dict) or body.get("status") != "completed":
            return None
        result = body.get("result", body)
        return json_module.dumps(
            result,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @staticmethod
    def _operation_failure_details(response: httpx.Response) -> tuple[str, dict[str, Any]]:
        try:
            body = response.json()
        except Exception:
            return "Operation failed", {}
        error = body.get("error") if isinstance(body, dict) else None
        if isinstance(error, dict):
            message = str(error.get("message") or "Operation failed")
            if error.get("user_action_required"):
                message += " (action required — check the Spec Kitty dashboard)"
            return message, dict(error)
        if isinstance(error, str) and error:
            return error, {}
        return "Operation failed", {}

    # ----- synchronous endpoints -----

    def pull(
        self,
        provider: str,
        project_slug: str | None = None,
        *,
        binding_ref: str | None = None,
        limit: int = 100,
        cursor: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """POST /api/v1/tracker/pull -- pull items from external tracker."""
        payload: dict[str, Any] = {
            **self._routing_params(provider, project_slug, binding_ref),
            "limit": limit,
        }
        if cursor is not None:
            payload["cursor"] = cursor
        if filters is not None:
            payload["filters"] = filters

        response = self._request_with_retry("POST", self._PULL_PATH, json=payload)
        result: dict[str, Any] = response.json()
        return result

    def status(
        self,
        provider: str,
        project_slug: str | None = None,
        *,
        binding_ref: str | None = None,
        installation_wide: bool = False,
    ) -> dict[str, Any]:
        """GET /api/v1/tracker/status -- connection/sync status.

        When *installation_wide* is True, sends only ``provider`` as a query
        param (no project_slug or binding_ref). The SaaS host returns
        installation-level status for that provider.
        """
        if installation_wide:
            params: dict[str, str] = {"provider": provider}
        else:
            params = self._routing_params(provider, project_slug, binding_ref)
        response = self._request_with_retry(
            "GET",
            self._STATUS_PATH,
            params=params,
        )
        result: dict[str, Any] = response.json()
        return result

    def mappings(
        self,
        provider: str,
        project_slug: str | None = None,
        *,
        binding_ref: str | None = None,
    ) -> dict[str, Any]:
        """GET /api/v1/tracker/mappings -- field mappings."""
        params = self._routing_params(provider, project_slug, binding_ref) if binding_ref or project_slug else {"provider": provider}
        response = self._request_with_retry(
            "GET",
            self._MAPPINGS_PATH,
            params=params,
        )
        result: dict[str, Any] = response.json()
        return result

    def search_issues(
        self,
        provider: str,
        project_slug: str | None = None,
        *,
        binding_ref: str | None = None,
        query_text: str | None = None,
        query_key: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """POST search endpoint — find candidate issues for origin binding.

        Returns a dict with 'candidates' list and routing context
        ('resource_type', 'resource_id').

        query_key takes precedence over query_text when both provided.
        """
        payload: dict[str, Any] = {"provider": provider, "limit": limit}
        if binding_ref:
            payload["binding_ref"] = binding_ref
        elif project_slug:
            payload["project_slug"] = project_slug
        if query_key is not None:
            payload["query_key"] = query_key
        if query_text is not None:
            payload["query_text"] = query_text

        response = self._request_with_retry("POST", self._SEARCH_ISSUES_PATH, json=payload)
        result: dict[str, Any] = response.json()
        return result

    def list_tickets(
        self,
        provider: str,
        project_slug: str | None = None,
        *,
        binding_ref: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """POST browse endpoint — list visible tickets in the mapped resource."""
        payload: dict[str, Any] = {"provider": provider, "limit": limit}
        if binding_ref:
            payload["binding_ref"] = binding_ref
        elif project_slug:
            payload["project_slug"] = project_slug

        response = self._request_with_retry("POST", self._LIST_TICKETS_PATH, json=payload)
        result: dict[str, Any] = response.json()
        return result

    def bind_mission_origin(
        self,
        provider: str,
        project_slug: str | None = None,
        *,
        binding_ref: str | None = None,
        mission_id: str,
        mission_slug: str | None = None,
        external_issue_id: str,
        external_issue_key: str,
        external_issue_url: str,
        title: str,
        external_status: str = "",
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """POST bind endpoint — create MissionOriginLink on SaaS.

        This is the authoritative write for the control-plane record.
        Same-origin re-bind returns success (no-op). Different-origin
        returns 409.
        """
        payload: dict[str, Any] = {
            "provider": provider,
            "mission_id": mission_id,
            "external_issue_id": external_issue_id,
            "external_issue_key": external_issue_key,
            "external_issue_url": external_issue_url,
            "external_title": title,
            "external_status": external_status,
        }
        if mission_slug:
            payload["mission_slug"] = mission_slug
        if binding_ref:
            payload["binding_ref"] = binding_ref
        elif project_slug:
            payload["project_slug"] = project_slug
        else:
            raise SaaSTrackerClientError(
                "Either project_slug or binding_ref must be provided.",
                error_code="invalid_routing",
                status_code=400,
            )
        response = self._request_with_retry(
            "POST",
            self._BIND_ORIGIN_PATH,
            json=payload,
            headers={"Idempotency-Key": idempotency_key} if idempotency_key else None,
        )
        result: dict[str, Any] = response.json()
        return result

    # ----- discovery and binding endpoints -----

    def resources(self, provider: str) -> dict[str, Any]:
        """GET /api/v1/tracker/resources/ -- enumerate bindable resources."""
        response = self._request_with_retry(
            "GET",
            self._RESOURCES_PATH,
            params={"provider": provider},
        )
        result: dict[str, Any] = response.json()
        return result

    def bind_resolve(
        self,
        provider: str,
        project_identity: dict[str, Any],
    ) -> dict[str, Any]:
        """POST /api/v1/tracker/bind-resolve/ -- resolve identity to bind candidates."""
        validate_outbound_payload(project_identity, "tracker_bind")
        payload: dict[str, Any] = {
            "provider": provider,
            "project_identity": project_identity,
        }
        response = self._request_with_retry(
            "POST",
            self._BIND_RESOLVE_PATH,
            json=payload,
        )
        result: dict[str, Any] = response.json()
        return result

    def bind_confirm(
        self,
        provider: str,
        candidate_token: str,
        project_identity: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """POST /api/v1/tracker/bind-confirm/ -- confirm bind selection."""
        validate_outbound_payload(project_identity, "tracker_bind")
        payload: dict[str, Any] = {
            "provider": provider,
            "candidate_token": candidate_token,
            "project_identity": project_identity,
        }
        response = self._request_with_retry(
            "POST",
            self._BIND_CONFIRM_PATH,
            json=payload,
            headers={"Idempotency-Key": idempotency_key} if idempotency_key else None,
        )
        result: dict[str, Any] = response.json()
        return result

    def bind_validate(
        self,
        provider: str,
        binding_ref: str,
        project_identity: dict[str, Any],
    ) -> dict[str, Any]:
        """POST /api/v1/tracker/bind-validate/ -- validate binding ref."""
        validate_outbound_payload(project_identity, "tracker_bind")
        payload: dict[str, Any] = {
            "provider": provider,
            "binding_ref": binding_ref,
            "project_identity": project_identity,
        }
        response = self._request_with_retry(
            "POST",
            self._BIND_VALIDATE_PATH,
            json=payload,
        )
        result: dict[str, Any] = response.json()
        return result

    # ----- async-capable endpoints -----

    def push(
        self,
        provider: str,
        project_slug: str | None = None,
        items: list[dict[str, Any]] | None = None,
        *,
        binding_ref: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """POST /api/v1/tracker/push -- push items to external tracker.

        May return 200 (sync) or 202 (async -> poll).
        """
        payload: dict[str, Any] = {
            **self._routing_params(provider, project_slug, binding_ref),
            "items": items or [],
        }
        response = self._request_with_retry(
            "POST",
            self._PUSH_PATH,
            json=payload,
            headers={"Idempotency-Key": idempotency_key} if idempotency_key else None,
        )

        result: dict[str, Any] = response.json()
        return result

    def run(
        self,
        provider: str,
        project_slug: str | None = None,
        *,
        binding_ref: str | None = None,
        pull_first: bool = True,
        limit: int = 100,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """POST /api/v1/tracker/run -- full sync cycle.

        May return 200 (sync) or 202 (async -> poll).
        """
        payload: dict[str, Any] = {
            **self._routing_params(provider, project_slug, binding_ref),
            "pull_first": pull_first,
            "limit": limit,
        }
        response = self._request_with_retry(
            "POST",
            self._RUN_PATH,
            json=payload,
            headers={"Idempotency-Key": idempotency_key} if idempotency_key else None,
        )

        result: dict[str, Any] = response.json()
        return result
