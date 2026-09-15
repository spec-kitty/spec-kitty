"""StoredSession + Team dataclasses for the spec-kitty auth subsystem (feature 080).

These types are the public contract between every auth WP: flows produce a
``StoredSession``, ``TokenManager`` persists it via ``SecureStorage``, and
downstream consumers read the access token, team list, and identity from the
same shape.

Important field contracts (spec 080 §7.1, contracts/saas-amendment-refresh-ttl.md):

- The user identity field is ``email`` — sourced from ``GET /api/v1/me``'s
  ``.email`` field. There is no ``username`` field.
- ``refresh_token_expires_at`` is ``Optional[datetime]``. It is ``None`` when
  the SaaS does not provide ``refresh_token_expires_in`` in the token response
  (constraint C-012). The CLI NEVER hardcodes a TTL — if the server does not
  communicate refresh-token expiry, the client learns about expiry from a
  ``400 invalid_grant`` response during refresh (decision D-9).
- ``default_team_id`` is picked by the CLI client (preferring the team's
  ``is_private_teamspace`` flag, otherwise ``teams[0].id`` or an explicit user
  selection), not supplied by the server.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Literal

from kernel.clock import UTC, datetime, now_utc, parse_iso, timedelta

StorageBackend = Literal["file"]
#: ``client_credentials`` is the machine/CI mode (#3277): a ServicePrincipal's
#: client_id + client_secret exchanged at ``POST /oauth/token`` with no
#: browser, device flow, or human approval step. Every consumer downstream
#: of ``TokenManager`` treats it exactly like a human session; the SaaS
#: attributes each session it mints to the machine principal in its audit log.
AuthMethod = Literal["authorization_code", "device_code", "client_credentials"]


@dataclass(frozen=True)
class Team:
    """A team/tenant the authenticated user belongs to.

    Populated from the SaaS ``/api/v1/me`` response's ``teams`` array.
    """

    id: str
    name: str
    role: str  # "admin" | "member" | "owner" | ...
    is_private_teamspace: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Team:
        return cls(
            id=data["id"],
            name=data["name"],
            role=data["role"],
            is_private_teamspace=bool(data.get("is_private_teamspace", False)),
        )


def pick_default_team_id(teams: list[Team]) -> str:
    """Return the preferred default team id for new-session UI/login default display.

    Private Teamspace wins when present; otherwise preserves the legacy first-team
    fallback. This is *display-only* — it is **not** valid as a fallback for direct
    sync ingress. Direct-ingress code paths must use ``require_private_team_id`` paired
    with ``TokenManager.rehydrate_membership_if_needed()`` instead, which fails closed
    (returns ``None``) rather than returning a shared team.
    """
    for team in teams:
        if team.is_private_teamspace:
            return team.id
    return teams[0].id


def get_private_team_id(teams: list[Team]) -> str | None:
    """Return the user's Private Teamspace id when one is present."""
    for team in teams:
        if bool(getattr(team, "is_private_teamspace", False)):
            return team.id
    return None


def require_private_team_id(session: StoredSession) -> str | None:
    """Return the Private Teamspace id for direct sync ingress, else None.

    Pure function. No I/O. No mutation.

    Contract:
      - If any team in ``session.teams`` has ``is_private_teamspace=True``, return that team's id.
        When more than one team has ``is_private_teamspace=True`` (today: not expected from SaaS),
        the first such team is returned for determinism.
      - Otherwise, return ``None``.
      - NEVER returns ``session.default_team_id`` (even when set).
      - NEVER returns ``session.teams[0].id`` as a fallback.

    Pair with ``TokenManager.rehydrate_membership_if_needed()`` to recover from
    a session whose ``teams`` list is stale.
    """
    return get_private_team_id(session.teams)


@dataclass
class StoredSession:
    """The persisted representation of an authenticated spec-kitty session.

    Serialized to JSON by ``to_json`` / ``from_json`` for encrypted file
    storage and to a dict by ``to_dict`` / ``from_dict`` for the same store.

    Use ``is_access_token_expired`` to decide when to refresh the access token
    and ``is_refresh_token_expired`` to detect a known-expired refresh token
    (only meaningful when ``refresh_token_expires_at`` is set — see C-012).
    """

    user_id: str
    email: str  # sourced from /api/v1/me .email (NOT "username")
    name: str
    teams: list[Team]
    default_team_id: str  # CLIENT-PICKED, not server-supplied

    access_token: str
    refresh_token: str
    session_id: str

    issued_at: datetime
    access_token_expires_at: datetime
    refresh_token_expires_at: datetime | None
    # ``None`` when SaaS does not provide refresh_token_expires_in.
    # The CLI never hardcodes a TTL. See C-012 in spec.md and decision D-9.

    scope: str
    storage_backend: StorageBackend
    last_used_at: datetime
    auth_method: AuthMethod

    generation: int | None = None  # Tranche 2 token-family generation counter; None for pre-Tranche-2 sessions

    # Base URL of the SaaS this session was minted against, recorded at login
    # so ``auth status`` can flag a session that predates a server move.
    # ``None`` for sessions written before the field existed (no mismatch can
    # be claimed without knowing where the tokens came from).
    issuer_url: str | None = None

    def __post_init__(self) -> None:
        """Keep persisted auth timestamps comparable with UTC ``now`` values."""
        self.issued_at = _coerce_utc(self.issued_at)
        self.access_token_expires_at = _coerce_utc(self.access_token_expires_at)
        if self.refresh_token_expires_at is not None:
            self.refresh_token_expires_at = _coerce_utc(self.refresh_token_expires_at)
        self.last_used_at = _coerce_utc(self.last_used_at)

    def is_access_token_expired(self, buffer_seconds: int = 0) -> bool:
        """Return True if the access token expires within ``buffer_seconds``.

        A ``buffer_seconds`` of 0 means "expired". Values > 0 let callers
        refresh proactively before the current token lapses.
        """
        now = now_utc()
        return self.access_token_expires_at <= now + timedelta(seconds=buffer_seconds)

    def is_refresh_token_expired(self) -> bool:
        """Return True only if we have a known refresh expiry that has passed.

        When ``refresh_token_expires_at`` is ``None`` (the SaaS amendment has
        not landed, see C-012), this method returns ``False``. The CLI then
        learns about refresh expiry from a ``400 invalid_grant`` response on
        the next refresh attempt.
        """
        if self.refresh_token_expires_at is None:
            return False  # server-managed; client cannot decide proactively
        return self.refresh_token_expires_at <= now_utc()

    def touch(self) -> None:
        """Update ``last_used_at`` to the current UTC time."""
        self.last_used_at = now_utc()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict."""
        return {
            "user_id": self.user_id,
            "email": self.email,
            "name": self.name,
            "teams": [t.to_dict() for t in self.teams],
            "default_team_id": self.default_team_id,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "session_id": self.session_id,
            "issued_at": self.issued_at.isoformat(),
            "access_token_expires_at": self.access_token_expires_at.isoformat(),
            "refresh_token_expires_at": (
                self.refresh_token_expires_at.isoformat()
                if self.refresh_token_expires_at is not None
                else None
            ),
            "scope": self.scope,
            "storage_backend": self.storage_backend,
            "last_used_at": self.last_used_at.isoformat(),
            "auth_method": self.auth_method,
            "generation": self.generation,
            "issuer_url": self.issuer_url,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StoredSession:
        """Deserialize from the dict produced by ``to_dict``."""
        refresh_exp_raw = data.get("refresh_token_expires_at")
        refresh_exp = (
            parse_iso(refresh_exp_raw) if refresh_exp_raw else None
        )
        return cls(
            user_id=data["user_id"],
            email=data["email"],
            name=data["name"],
            teams=[Team.from_dict(t) for t in data["teams"]],
            default_team_id=data["default_team_id"],
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            session_id=data["session_id"],
            issued_at=parse_iso(data["issued_at"]),
            access_token_expires_at=parse_iso(data["access_token_expires_at"]),
            refresh_token_expires_at=refresh_exp,
            scope=data["scope"],
            storage_backend=data["storage_backend"],
            last_used_at=parse_iso(data["last_used_at"]),
            auth_method=data["auth_method"],
            generation=data.get("generation"),
            issuer_url=data.get("issuer_url"),
        )

    def to_json(self) -> str:
        """Serialize to a JSON string for encrypted file persistence."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, raw: str) -> StoredSession:
        """Deserialize from a JSON string produced by the encrypted file store."""
        return cls.from_dict(json.loads(raw))


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
