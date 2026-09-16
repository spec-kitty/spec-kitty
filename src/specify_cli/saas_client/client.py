"""SaaS HTTP client for the Widen Mode feature.

Provides a thin, mockable wrapper around ``httpx`` for all SaaS calls made
by the widen flow and prereq checker.  Dependency-inject a custom
``httpx.Client`` via the ``_http`` parameter for unit tests.

All public methods:
- Raise ``SaasClientError`` (or a subclass) on any failure — raw ``httpx``
  exceptions are never propagated to callers.
- Map HTTP status codes to typed exception subclasses.
- Accept per-call timeout overrides where documented.
"""

from __future__ import annotations

import json as json_module
import logging
import secrets
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlencode

import httpx

from specify_cli.auth import get_token_manager
from specify_cli.auth.session import require_private_team_id
from specify_cli.saas_client.auth import AuthContext, load_auth_context
from specify_cli.saas_client.endpoints import AdmissionAnswer, AudienceMember, DiscussionData, DiscussionMessage, WidenResponse
from specify_cli.saas_client.errors import (
    SaasAuthError,
    SaasClientError,
    SaasConsentError,
    SaasNotFoundError,
    SaasTimeoutError,
)
from specify_cli.saas_client.project_authority import resolve_project_team_slug

logger = logging.getLogger(__name__)

# Timeout constants (seconds)
_TIMEOUT_DEFAULT = 5.0
_TIMEOUT_PREREQ_PROBE = 0.5
_TIMEOUT_DISCUSSION = 10.0


def _authenticated_authority_for_token(token: str) -> tuple[str, str, str] | None:
    """Resolve exact account, Private and Collaborative Teamspaces from auth."""
    session = get_token_manager().get_current_session()
    if session is None or not secrets.compare_digest(session.access_token, token):
        return None
    private_teamspace_id = require_private_team_id(session)
    if private_teamspace_id is None:
        return None
    collaborative_ids = {team.id.strip() for team in session.teams if not team.is_private_teamspace and isinstance(team.id, str) and team.id.strip()}
    if len(collaborative_ids) != 1:
        return None
    return session.user_id, private_teamspace_id, collaborative_ids.pop()


def _map_http_error(resp: httpx.Response, context: str) -> SaasClientError:
    """Convert a non-2xx ``httpx.Response`` into a typed ``SaasClientError``."""
    status = resp.status_code
    try:
        body = resp.text[:200]
    except Exception:
        body = ""
    msg = f"{context}: HTTP {status}" + (f" — {body}" if body else "")
    if status in (401, 403):
        return SaasAuthError(msg, status_code=status)
    if status == 404:
        return SaasNotFoundError(msg, status_code=status)
    return SaasClientError(msg, status_code=status)


class SaasClient:
    """Thin HTTP client for spec-kitty SaaS endpoints.

    Args:
        base_url: Root URL of the SaaS API (from ``SPEC_KITTY_SAAS_URL`` /
            auth context; D-5 — no hardcoded domain).
        token: Bearer token for authentication.
        timeout: Default request timeout in seconds.  Individual methods may
            override this for their specific use-case.
        _http: Optional pre-constructed ``httpx.Client``.  Pass a mock client
            in tests to intercept HTTP calls without network access.
        project_root: The checkout that **owns the data this client will send**
            — the repository holding the mission or decision record. Team-scoped
            collaboration requests require this checkout's canonical hosted
            admission to match the authenticated team (#3178). ``None`` refuses
            collaboration because session membership alone cannot establish the
            project's destination.
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        team_slug: str | None = None,
        timeout: float = _TIMEOUT_DEFAULT,
        _http: httpx.Client | None = None,
        project_root: Path | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._team_slug = team_slug
        self._timeout = timeout
        self._project_root = Path(project_root) if project_root is not None else None
        # A CLI client is command-scoped and its token/project root are immutable.
        # Cache one positive admission for the command; mid-command revocation is
        # enforced on the next client/command rather than adding a round trip to
        # every collaboration endpoint in the same flow.
        self._resolved_project_team_slug: str | None = None
        self._http = _http or httpx.Client(
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # Public auth helpers
    # ------------------------------------------------------------------

    @property
    def has_token(self) -> bool:
        """Return ``True`` when a non-empty bearer token is configured.

        Use this instead of accessing ``_token`` directly so callers are
        insulated from the private attribute name.
        """
        return bool(self._token)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls, repo_root: object = None) -> SaasClient:
        """Construct from environment variables or ``.kittify/saas-auth.json``.

        Args:
            repo_root: Optional :class:`~pathlib.Path` to the repo root, passed
                through to :func:`~specify_cli.saas_client.auth.load_auth_context`
                **and** carried on the client as the project whose consent gates
                every send (#3030 FR-030).  Omitting it yields a client that
                refuses every request, because there is then no project whose
                consent could be resolved.

        Returns:
            A fully initialised :class:`SaasClient`.

        Raises:
            SaasAuthError: If authentication credentials cannot be resolved.
        """
        root: Path | None = Path(str(repo_root)) if repo_root is not None else None
        ctx: AuthContext = load_auth_context(repo_root=root)
        return cls(
            base_url=ctx.saas_url,
            token=ctx.token,
            team_slug=ctx.team_slug,
            project_root=root,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(
        self,
        path: str,
        *,
        timeout: float | None = None,
    ) -> httpx.Response:
        """Issue a GET request, mapping exceptions to ``SaasClientError``."""
        return self._exchange("GET", path, timeout=timeout)

    def _post(
        self,
        path: str,
        *,
        json: object,
        timeout: float | None = None,
    ) -> httpx.Response:
        """Issue a POST request with a JSON body, mapping exceptions to ``SaasClientError``."""
        return self._exchange("POST", path, json=json, timeout=timeout)

    def _exchange(
        self,
        method: str,
        path: str,
        *,
        json: object | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        """Run one consent-gated HTTP exchange against the SaaS API.

        The gate runs before the URL is used, then the request goes straight to
        the transport. Nothing is persisted: an exchange that ends without a
        response raises here and is simply lost, because every endpoint this
        client serves is an interactive lookup whose moment has passed by the
        time an operator could retry it.
        """
        if _authenticated_authority_for_token(self._token) is None:
            raise SaasConsentError("target_authority_mismatch: token-matched account, Private Teamspace, and one Collaborative Teamspace are required")
        url = f"{self._base_url}{path}"
        effective_timeout = timeout if timeout is not None else self._timeout
        try:
            response = self._http.get(url, timeout=effective_timeout) if method == "GET" else self._http.post(url, json=json, timeout=effective_timeout)
        except httpx.TimeoutException as exc:
            raise SaasTimeoutError(f"{method} {url} timed out after {effective_timeout}s") from exc
        except httpx.RequestError as exc:
            raise SaasClientError(f"{method} {url} failed: {exc}") from exc
        if not response.is_success:
            body = self._response_body(response)
            if body is not None and body.get("error_category") == "project_not_admitted":
                raise SaasConsentError(self._generic_refusal_message(self._generic_refusal_reference(response)))
            raise _map_http_error(response, f"{method} {url}")
        return response

    @staticmethod
    def _response_body(response: httpx.Response) -> dict[str, object] | None:
        try:
            body = response.json()
        except Exception:
            return None
        return body if isinstance(body, dict) else None

    @classmethod
    def _generic_refusal_reference(cls, response: httpx.Response) -> str:
        body = cls._response_body(response) or {}
        envelope = {
            key: body[key]
            for key in (
                "error_category",
                "idempotency_key",
                "message",
                "retryable",
                "status",
            )
            if key in body
        }
        return json_module.dumps(
            {"http_status": response.status_code, "envelope": envelope},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @staticmethod
    def _generic_refusal_message(reference: str | None) -> str:
        if reference is None:
            return "project_not_admitted: hosted target refused this project"
        try:
            value = json_module.loads(reference)
            envelope = value["envelope"]
            message = envelope.get("message")
        except (KeyError, TypeError, json_module.JSONDecodeError):
            return "project_not_admitted: hosted target refused this project"
        return str(message) if isinstance(message, str) and message else "project_not_admitted: hosted target refused this project"

    def _resolve_team_slug(self, team_slug: str | None = None) -> str:
        authority = _authenticated_authority_for_token(self._token)
        if authority is None:
            raise SaasAuthError("Exactly one token-matched Collaborative Teamspace is required")
        slug = self._resolved_project_team_slug
        if slug is None:
            slug = resolve_project_team_slug(self._project_root, authority[2], self.check_repo_admission)
            self._resolved_project_team_slug = slug
        if team_slug is not None and team_slug.strip() != slug:
            raise SaasConsentError("target_authority_mismatch: collaborative team path substitution refused")
        if self._team_slug is not None and self._team_slug.strip() != slug:
            raise SaasConsentError("target_authority_mismatch: collaborative team path substitution refused")
        return slug

    def _team_path(self, team_slug: str | None, path: str) -> str:
        return f"/a/{self._resolve_team_slug(team_slug)}/collaboration{path}"

    # ------------------------------------------------------------------
    # Public endpoint methods
    # ------------------------------------------------------------------

    def get_audience_default(self, mission_id: str, *, team_slug: str | None = None) -> list[AudienceMember]:
        """Fetch the default audience for a mission.

        ``GET /a/{team_slug}/collaboration/missions/{id}/audience-default``

        Returns Teamspace member dicts containing at least ``user_id`` and
        ``display_name``. Legacy bare-string responses are tolerated for older
        test stubs by returning display-name-only member dicts.

        Args:
            mission_id: ULID or slug identifying the mission.

        Returns:
            List of audience member display names.

        Raises:
            SaasClientError: On any HTTP or network failure.
            SaasNotFoundError: If the mission does not exist (HTTP 404).
            SaasAuthError: On auth failure (HTTP 401/403).
            SaasTimeoutError: If the request exceeds the default timeout.
        """
        path = self._team_path(team_slug, f"/missions/{mission_id}/audience-default")
        resp = self._get(path)
        data = resp.json()
        # Accept either {"members": [...]} or a bare list
        members = data if isinstance(data, list) else data.get("members", [])
        normalized: list[AudienceMember] = []
        for member in members:
            if isinstance(member, dict):
                normalized.append(cast(AudienceMember, dict(member)))
            else:
                normalized.append({"display_name": str(member)})
        return normalized

    def post_widen(
        self,
        decision_id: str,
        invited: list[int],
        *,
        team_slug: str | None = None,
    ) -> WidenResponse:
        """Widen a decision point by inviting external participants.

        ``POST /a/{team_slug}/collaboration/decision-points/{id}/widen``

        Args:
            decision_id: ULID of the decision point to widen.
            invited: List of Teamspace user IDs to invite.

        Returns:
            :class:`~specify_cli.saas_client.endpoints.WidenResponse` with
            ``decision_id``, ``widened_at``, ``slack_thread_url``, and
            ``invited_count``.

        Raises:
            SaasClientError: On any HTTP or network failure.
            SaasAuthError: On auth failure (HTTP 401/403).
            SaasTimeoutError: If the request exceeds the default timeout.
        """
        path = self._team_path(team_slug, f"/decision-points/{decision_id}/widen")
        resp = self._post(path, json={"invited_user_ids": invited})
        data: dict[str, Any] = resp.json()
        return WidenResponse(
            decision_id=str(data.get("decision_id", decision_id)),
            widened_at=str(data.get("widened_at", "")),
            slack_thread_url=data.get("slack_thread_url") or None,
            invited_count=data.get("invited_count") or None,
        )

    def get_team_integrations(self, team_slug: str) -> list[str]:
        """Fetch the list of active integrations for a team.

        ``GET /a/{team_slug}/collaboration/integrations/``

        Used by the prereq checker (500ms timeout — it is a fast probe).

        Args:
            team_slug: The team's URL slug.

        Returns:
            List of integration names, e.g. ``["slack", "github"]``.

        Raises:
            SaasClientError: On any HTTP or network failure.
            SaasTimeoutError: If the request exceeds the 500ms probe timeout.
        """
        path = self._team_path(team_slug, "/integrations/")
        resp = self._get(path, timeout=_TIMEOUT_PREREQ_PROBE)
        data = resp.json()
        if isinstance(data, list):
            return [str(i) for i in data]
        integrations = data.get("integrations", [])
        return [str(i) for i in integrations]

    def health_probe(self) -> bool:
        """Check whether the SaaS API is reachable.

        ``GET /api/v1/health``

        Uses a short 500ms timeout.  Returns ``False`` on any error — this
        method never raises.

        Returns:
            ``True`` if the API responds with HTTP 200, ``False`` otherwise.
        """
        try:
            self._get("/api/v1/health", timeout=_TIMEOUT_PREREQ_PROBE)
            return True
        except SaasClientError:
            return False

    def fetch_discussion(self, decision_id: str, *, team_slug: str | None = None) -> DiscussionData:
        """Fetch the discussion thread for a widened decision point.

        ``GET /a/{team_slug}/collaboration/decision-points/{id}/discussion/``

        Uses a longer 10-second timeout (per NFR-002) because discussion
        payloads may be large.

        Args:
            decision_id: ULID of the widened decision point.

        Returns:
            :class:`~specify_cli.saas_client.endpoints.DiscussionData`.

        Raises:
            SaasClientError: On any HTTP or network failure.
            SaasNotFoundError: If the decision point does not exist (HTTP 404).
            SaasAuthError: On auth failure (HTTP 401/403).
            SaasTimeoutError: If the request exceeds the 10-second timeout.
        """
        path = self._team_path(team_slug, f"/decision-points/{decision_id}/discussion/")
        resp = self._get(path, timeout=_TIMEOUT_DISCUSSION)
        data: dict[str, Any] = resp.json()

        raw_messages = data.get("messages", []) or []
        messages: list[DiscussionMessage] = [
            {
                "author": str(m.get("author") or m.get("author_display_name") or ""),
                "text": str(m.get("text", "")),
                "timestamp": m.get("timestamp") or m.get("ts") or None,
            }
            for m in raw_messages
            if isinstance(m, dict)
        ]

        raw_participants = data.get("participants", []) or []
        participants = [
            str(p.get("display_name") or p.get("teamspace_user_id") or p.get("slack_user_id")) if isinstance(p, dict) else str(p) for p in raw_participants
        ]

        return DiscussionData(
            decision_id=str(data.get("decision_id", decision_id)),
            participants=participants,
            messages=messages,
            thread_url=data.get("thread_url") or None,
            message_count=int(data.get("message_count", len(messages))),
        )

    def check_repo_admission(self, repo_slug: str, host: str | None = None) -> AdmissionAnswer:
        """Check which team (if any) ``repo_slug`` is admitted into.

        ``GET /api/v1/sync/repo-admission/?repo_slug=<>&host=<>``
        (TEAM-ADMIT-M2-07/08, ADR-TEAM-REPO-ADMISSION-2026-08-24 §4.2/§4.3).

        This is a plain lookup, not team-scoped like the collaboration
        endpoints above: the whole point of the call is to *discover* which
        team (if any) admits the repo, so unlike ``_team_path()`` callers
        there is no team slug to require up front.

        ``host`` is optional but recommended — ``repo_slug`` alone cannot
        distinguish the same ``owner/repo`` slug hosted on two different git
        providers (e.g. github.com vs. a self-hosted GitLab); the server uses
        it to disambiguate by provider when given.

        Args:
            repo_slug: ``owner/repo``-style slug parsed from the git remote.
            host: Bare git remote hostname.

        Returns:
            :class:`~specify_cli.saas_client.endpoints.AdmissionAnswer`.
            Both response shapes are HTTP 200 — check ``admitted`` to tell
            them apart; a not-admitted answer is a normal return value, not
            an exception.

        Raises:
            SaasClientError: On any HTTP or network failure — distinguishable
                from a genuine ``admitted: False`` answer, which is returned
                rather than raised.
            SaasAuthError: On auth failure (HTTP 401/403).
            SaasTimeoutError: If the request exceeds the default timeout.
        """
        params = {"repo_slug": repo_slug}
        if host is not None:
            params["host"] = host
        path = f"/api/v1/sync/repo-admission/?{urlencode(params)}"
        resp = self._get(path)
        try:
            data = resp.json()
        except ValueError as exc:
            raise SaasConsentError("project_authority_unavailable: admission response is not JSON") from exc
        if not isinstance(data, dict):
            raise SaasConsentError("project_authority_unavailable: admission response is not an object")
        if data.get("admitted") is True and not isinstance(data.get("repo_slug"), str):
            raise SaasConsentError("project_authority_unavailable: admission response does not identify the repository")
        return cast(
            AdmissionAnswer,
            {
                "admitted": data.get("admitted") is True,
                "team": data.get("team"),
                "provider": data.get("provider"),
                "repo_slug": str(data.get("repo_slug", repo_slug)),
                "checked_at": data.get("checked_at"),
                "reason": data.get("reason"),
            },
        )
