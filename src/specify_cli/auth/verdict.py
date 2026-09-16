"""The single typed authority for auth/session *health verdicts* (#3723).

Six diagnostics used to report healthy while the thing they described was
broken: ``sync status``/``auth status`` printed ``Authenticated`` above a
contradicting ``Access token: expired`` detail, and ``auth doctor`` printed
``No problems detected.`` for an expired token whose refresh chain was
failing. The root cause was that each surface *hand-rolled* its own green
banner alongside — never derived from — the detail it displayed.

This module removes the ability to do that. :class:`HealthVerdict` is a
tri-state (:data:`Health`) value object whose ``headline`` is a **computed
property derived from ``state``**, not a settable field. A caller therefore
*cannot* author a headline that disagrees with the detail, because both the
banner and the detail read from one verdict. Three mechanised rules
(mirroring #3723's proposed rules):

1. **Every definite claim names its evidence.** ``evidence`` is mandatory for
   ``ok``/``fail`` (enforced in :meth:`HealthVerdict.__post_init__`);
   ``unknown`` is the only state permitted to say "I could not check".
2. **A probe that cannot verify says ``unknown``, never ``ok``.**
   :func:`evaluate_auth_verdict` returns ``unknown`` — never ``ok`` — for an
   expired access token whose refresh chain has not been proven live.
3. **A headline may not contradict its own detail.** ``headline`` is derived
   from ``state``; there is no way to set it independently.
4. **A probe that ran and failed is a failure, never ``ok``** (#4607).
   :func:`evaluate_auth_verdict` returns ``fail`` for an inactive server
   probe even when the local access token is still valid — local token
   validity never overrides the answer the user explicitly asked the
   server for, so a CI gate reading ``auth doctor --server``'s exit code
   cannot pass cleanly through a backend outage.

Dependency direction: this is an **auth** concept (token-expiry semantics live
in ``auth/session.py``), so it lives under ``auth``. ``sync`` consumes it
(sync -> auth is legal); auth never imports sync.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from kernel.clock import datetime

from specify_cli.auth.session import StoredSession

#: Tri-state health. ``unknown`` is NOT ``ok`` — an unanswered probe must never
#: make a definite claim (rule 2).
Health = Literal["ok", "unknown", "fail"]

#: Headline text derived purely from the verdict state. This mapping is the ONE
#: place the positive-claim word ``Authenticated`` is authored; every render
#: surface must route through :attr:`HealthVerdict.headline` rather than
#: spelling it, which the ``test_status_line_honesty`` ratchet enforces.
_HEADLINES: dict[str, str] = {
    "ok": "Authenticated",
    "unknown": "Cannot verify",
    "fail": "Not authenticated",
}

_LOGIN_REMEDIATION = "spec-kitty auth login"
_SERVER_REMEDIATION = "spec-kitty auth doctor --server"


class ServerProbe(Protocol):
    """Structural shape of an opt-in server-session probe result.

    ``cli.commands._auth_doctor.ServerSessionStatus`` (a frozen dataclass)
    satisfies this without this module importing it (which would be an
    auth -> cli.commands wrong-direction dependency). The members are declared
    as read-only properties so a *frozen* dataclass's read-only fields match.
    """

    @property
    def active(self) -> bool: ...

    @property
    def error(self) -> str | None: ...


@dataclass(frozen=True)
class HealthVerdict:
    """A tri-state health claim that always names its evidence.

    ``headline`` is intentionally a computed property, not a field: it makes a
    banner that contradicts the detail structurally impossible (#3723 rule 3).
    """

    state: Health
    evidence: str
    detail: str | None = None
    remediation: str | None = None

    def __post_init__(self) -> None:
        # Rule 1 mechanised: a definite claim must carry evidence. ``unknown``
        # is the only state allowed to have said "I did not / could not check".
        if self.state in ("ok", "fail") and not self.evidence.strip():
            raise ValueError("HealthVerdict.evidence is required unless state == 'unknown'")

    @property
    def headline(self) -> str:
        """The human banner, derived from ``state`` (never settable)."""
        return _HEADLINES[self.state]


def _token_flags(session: StoredSession, now: datetime) -> tuple[bool, bool]:
    """Return ``(access_ok, refresh_ok)`` for *session* at *now*.

    A ``None`` refresh expiry is treated as valid (server-managed / legacy
    session; the client cannot decide it is expired — see C-012).
    """
    access_exp = session.access_token_expires_at
    refresh_exp = session.refresh_token_expires_at
    access_ok = access_exp is not None and access_exp > now
    refresh_ok = refresh_exp is None or refresh_exp > now
    return access_ok, refresh_ok


def _humanize(seconds: float) -> str:
    """Render an absolute second-delta compactly (``14m`` / ``6h`` / ``30d``)."""
    seconds = abs(seconds)
    if seconds < 3600:
        return f"{max(int(seconds // 60), 0)}m"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h"
    return f"{int(seconds // 86400)}d"


def _refresh_evidence(session: StoredSession, now: datetime) -> str:
    """Evidence fragment describing the refresh token's validity window."""
    refresh_exp = session.refresh_token_expires_at
    if refresh_exp is None:
        return "refresh server-managed"
    return f"refresh valid {_humanize((refresh_exp - now).total_seconds())}"


def _probe_failed_verdict(server_probe: ServerProbe) -> HealthVerdict:
    """Verdict for a server probe that ran and did not confirm the session.

    This is the #4607 fix: a failed ``auth doctor --server`` check is a
    ``fail`` even when the local access token is still valid — a probe that
    ran and could not confirm must never let the ladder answer ``ok``.
    """
    return HealthVerdict(
        state="fail",
        evidence=server_probe.error or "server rejected the session",
        remediation=_LOGIN_REMEDIATION,
    )


def _resolve_expired_access(server_probe: ServerProbe | None) -> HealthVerdict:
    """Verdict for an expired access token whose refresh token is still valid.

    This is the #3723 fix: with no server probe the refresh chain is
    **unproven**, so the honest verdict is ``unknown`` — never ``ok``. A
    probe that ran and failed never reaches here; the ladder's probe rule
    (#4607) has already answered ``fail``.
    """
    if server_probe is not None and server_probe.active:
        return HealthVerdict(
            state="ok",
            evidence="access token expired but server confirms the session is live",
        )
    return HealthVerdict(
        state="unknown",
        evidence="access token expired; refresh chain not verified offline",
        detail="Run with a server probe to confirm the session is live.",
        remediation=_SERVER_REMEDIATION,
    )


def evaluate_auth_verdict(
    session: StoredSession | None,
    now: datetime,
    *,
    server_probe: ServerProbe | None = None,
    session_assessment_reason: str | None = None,
) -> HealthVerdict:
    """Derive the one honest auth :class:`HealthVerdict` from a session + clock.

    Pure: no I/O; the clock and the optional server probe are injected. Decision
    ladder (the ONLY authority for this decision):

    - no session                         -> ``fail``    (no active session)
    - refresh token known-expired        -> ``fail``    (re-authenticate)
    - server probe ran and is inactive   -> ``fail``    (the #4607 fix — a failed
      check is a failure even when the local access token is valid)
    - access token valid                 -> ``ok``      (names both windows)
    - access expired, refresh valid, no probe    -> ``unknown``  (the #3723 fix)
    - access expired, refresh valid, probe live  -> ``ok``
    """
    if session is None and session_assessment_reason == "storage_decryption_failed":
        return HealthVerdict(
            state="fail",
            evidence="stored session could not be decrypted; unreadable session removed",
            remediation=_LOGIN_REMEDIATION,
        )
    if session is None:
        return HealthVerdict(
            state="fail",
            evidence="no active session",
            remediation=_LOGIN_REMEDIATION,
        )
    access_ok, refresh_ok = _token_flags(session, now)
    if not refresh_ok:
        refresh_exp = session.refresh_token_expires_at
        ago = _humanize((now - refresh_exp).total_seconds()) if refresh_exp else "0m"
        return HealthVerdict(
            state="fail",
            evidence=f"refresh token expired {ago} ago",
            remediation=_LOGIN_REMEDIATION,
        )
    if server_probe is not None and not server_probe.active:
        return _probe_failed_verdict(server_probe)
    if access_ok:
        access_left = _humanize((session.access_token_expires_at - now).total_seconds())
        return HealthVerdict(
            state="ok",
            evidence=f"access valid {access_left}; {_refresh_evidence(session, now)}",
        )
    return _resolve_expired_access(server_probe)


# ``Health`` (the tri-state alias) and ``ServerProbe`` (the probe Protocol) are
# module-internal: they are referenced only within this module's own type
# annotations, so they stay off ``__all__`` (no cross-module consumer) rather
# than becoming dead public symbols. Promote them if a consumer ever needs them.
__all__ = [
    "HealthVerdict",
    "evaluate_auth_verdict",
]
