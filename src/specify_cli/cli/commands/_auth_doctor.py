"""Implementation of ``spec-kitty auth doctor`` (WP06).

This module is the user-facing diagnostic surface for local CLI auth state.
It assembles a structured :class:`DoctorReport` from local-only state —
encrypted session and refresh-lock record — and renders it via Rich or as a
versioned JSON payload. The sync-daemon diagnostics (daemon summary, orphan
sweep, ``--reset``) were removed together with the sync transport (issue #5);
the surviving scope is auth session health, drift detection, refresh-lock
summary, and the opt-in server session check.

Default invocation contract (FR-015, C-007):

- Reads only local files. NEVER makes outbound network calls. NEVER writes,
  deletes, or mutates anything.
- One opt-in repair flag (``--unstick-lock``, C-008) runs the underlying
  repair primitive (``force_release``) only when the corresponding finding
  is present.

The ``--server`` flag (FR-011 through FR-015, FR-017) is an explicit opt-in
network path. It refreshes the access token if needed, then calls
``GET /api/v1/session-status``. C-007 still holds for the default path.
Before refreshing, it compares the stored session's ``issuer_url`` against
the resolved server target (the same comparison ``auth status`` renders):
a known mismatch — the session was minted by a server other than the one
currently configured — is reported directly, without attempting the
refresh. A refresh attempt in that state sends the previous server's
refresh token to a server that never issued it; the rejection is
indistinguishable from a truly revoked token and clears the local session
(issue #253), which is wrong for a read-adjacent diagnostic to do on a
migration path every user hits.

A check that fails — any ``active=False`` result, from an HTTP 500 to a
network error — is a critical F-008 finding and exits 1, even when the
local access token is still valid (issue #4607): a CI gate reading the
exit code must not pass cleanly through a total backend outage. The
verdict ladder in ``specify_cli.auth.verdict`` is the authority for that
decision; this module only renders it.

Public API (consumed by ``cli.commands.auth.doctor`` and tests):

- :class:`Finding`, :class:`SessionSummary`, :class:`LockSummary`,
  :class:`DoctorReport` — frozen dataclasses mirroring ``data-model.md``
  §"DoctorReport" (minus the removed daemon sections).
- :class:`ServerSessionStatus` — frozen dataclass for the opt-in server check.
- :func:`assemble_report` — pure data gather; no rendering, no mutation.
- :func:`render_report` — Rich rendering of the 5 sections.
- :func:`render_report_json` — ``--json`` payload (datetime → ISO-8601,
  Path → str).
- :func:`compute_exit_code` — 0 / 1 / 2 policy from findings list.
- :func:`doctor_impl` — orchestration entry point invoked by the typer
  shell.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from rich.console import Console
from rich.markup import escape
from specify_cli.cli.console import console, sanitize_terminal_text

from kernel.clock import datetime, now_utc

from specify_cli.auth import get_token_manager
from specify_cli.auth.server_target import ResolvedServerTarget, ServerTargetSplitBrainError, resolve_server_target
from specify_cli.auth.session import StoredSession
from specify_cli.auth.token_manager import _refresh_lock_path
from specify_cli.auth.verdict import HealthVerdict, evaluate_auth_verdict
from specify_cli.cli.commands._auth_saas_target import (
    format_saas_mismatch_warning,
    saas_source_name,
)
from specify_cli.cli.commands._auth_status import (
    format_auth_method,
    format_duration,
    format_storage_backend,
)
from kernel.locks import (
    LockRecord,
    force_release,
    read_lock_record,
)

__all__ = [
    "DoctorReport",
    "Finding",
    "LockSummary",
    "ServerSessionStatus",
    "SessionSummary",
    "assemble_report",
    "compute_exit_code",
    "doctor_impl",
    "render_report",
    "render_report_json",
]


# Schema version for the JSON payload. Bump on breaking schema changes.
# v3: sync-daemon diagnostics removed — `daemon` and `orphans` keys dropped
#     (and `--reset` with them) along with the sync transport (issue #5).
_SCHEMA_VERSION: int = 3

# Severity literal used by :class:`Finding`.
Severity = Literal["info", "warn", "critical"]


# ---------------------------------------------------------------------------
# Dataclasses (mirror data-model.md §"DoctorReport")
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    """A single diagnostic observation with optional remediation guidance.

    ``severity`` ladder:
        - ``info``     — observation, no action required.
        - ``warn``     — action recommended.
        - ``critical`` — action required (drives exit-code 1 unless repaired).
    """

    id: str
    severity: Severity
    summary: str
    remediation_command: str | None = None
    remediation_description: str | None = None


@dataclass(frozen=True)
class SessionSummary:
    """Local-state snapshot of the persisted auth session.

    ``auth_method`` (#3277) makes the auth mode — human browser, headless
    device flow, or machine ``client_credentials`` — visible in diagnostics
    without exposing any credential material: it is the stored session's
    ``AuthMethod`` literal, never a token or secret value.
    """

    present: bool
    session_id: str | None
    user_email: str | None
    access_token_remaining_s: float | None
    refresh_token_remaining_s: float | None
    storage_backend: str | None
    in_memory_drift: bool
    auth_method: str | None = None


@dataclass(frozen=True)
class LockSummary:
    """Local-state snapshot of the machine-wide refresh lock."""

    held: bool
    holder_pid: int | None
    started_at: datetime | None
    age_s: float | None
    stuck: bool
    stuck_threshold_s: float
    holder_host: str | None


@dataclass(frozen=True)
class DoctorReport:
    """Structured diagnostic report (versioned, JSON-serialisable)."""

    schema_version: int
    generated_at: datetime
    auth_root: Path
    session: SessionSummary | None
    refresh_lock: LockSummary
    auth_verdict: HealthVerdict
    findings: list[Finding] = field(default_factory=list)


@dataclass(frozen=True)
class ServerSessionStatus:
    """Result of an opt-in server-side session check (auth doctor --server).

    ``active=True`` means the server confirms the session is live.
    ``session_id`` is safe to display (not a secret).
    ``error`` is a brief human-readable failure reason; never contains
    raw tokens, token_family_id, is_revoked, or revocation_reason.
    """

    active: bool
    session_id: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Internal helpers — read-only state gathering
# ---------------------------------------------------------------------------


def _read_session_summary() -> tuple[SessionSummary | None, Any]:
    """Return (summary, raw_session). Both ``None`` when no session present.

    The raw session is returned alongside the summary so downstream callers
    (``render_report``) can reuse identity formatters from
    ``_auth_status.py`` without re-reading state.
    """
    tm = get_token_manager()
    session = tm.get_current_session()
    if session is None:
        return None, None

    now = now_utc()
    access_remaining = (session.access_token_expires_at - now).total_seconds()
    refresh_remaining: float | None = None if session.refresh_token_expires_at is None else (session.refresh_token_expires_at - now).total_seconds()

    in_memory_drift = _detect_persisted_drift(tm, session)

    summary = SessionSummary(
        present=True,
        session_id=session.session_id,
        user_email=session.email,
        access_token_remaining_s=access_remaining,
        refresh_token_remaining_s=refresh_remaining,
        storage_backend=session.storage_backend,
        in_memory_drift=in_memory_drift,
        auth_method=session.auth_method,
    )
    return summary, session


def _detect_persisted_drift(tm: Any, in_memory: Any) -> bool:
    """Return ``True`` when persisted material differs from in-memory state.

    During an in-flight refresh the persisted session may temporarily be
    ahead of the in-memory copy (or vice-versa). The check is best-effort:
    on any storage error we report ``False`` (no drift) so a transient
    backend hiccup never trips F-006.
    """
    try:
        persisted = tm._storage.read()
    except Exception:  # noqa: BLE001 - storage boundary: downgrade read errors to inconclusive (False) rather than fatal, so a transient backend hiccup never trips F-006
        # Storage read failure makes drift check inconclusive rather than fatal.
        return False
    if persisted is None:
        return False
    if persisted.session_id != in_memory.session_id:
        return True
    return bool(persisted.refresh_token != in_memory.refresh_token)


def _read_lock_summary(stuck_threshold_s: float) -> LockSummary:
    """Read the refresh lock record and synthesise a :class:`LockSummary`."""
    path = _refresh_lock_path()
    record: LockRecord | None = read_lock_record(path)
    if record is None:
        return LockSummary(
            held=False,
            holder_pid=None,
            started_at=None,
            age_s=None,
            stuck=False,
            stuck_threshold_s=stuck_threshold_s,
            holder_host=None,
        )
    age_s = record.age_s
    return LockSummary(
        held=True,
        holder_pid=record.pid,
        started_at=record.started_at,
        age_s=age_s,
        stuck=age_s > stuck_threshold_s,
        stuck_threshold_s=stuck_threshold_s,
        holder_host=record.host,
    )


def _read_auth_root() -> Path:
    """Return the auth-store directory (parent of the refresh lock)."""
    parent: Path = _refresh_lock_path().parent
    return parent


# ---------------------------------------------------------------------------
# Findings + exit-code policy (T025)
# ---------------------------------------------------------------------------


def _compute_findings(
    *,
    session: SessionSummary | None,
    refresh_lock: LockSummary,
    auth_verdict: HealthVerdict,
) -> list[Finding]:
    """Compute :class:`Finding` list from the read-only state snapshots.

    Order is stable so JSON consumers and humans see the same sequence.
    Finding IDs are stable across schema versions: the retired daemon checks
    (F-002/F-004/F-005) keep their historical IDs unused rather than having
    the surviving findings renumbered underneath consumers.
    """
    findings: list[Finding] = []

    # F-001 — no session loaded. When storage failed closed and its verdict
    # carries the failure detail (#4761, e.g. unsafe session-file
    # permissions), the finding names the real cause and the storage layer's
    # own remedy — the auth-login remediation is withheld because a re-login
    # would overwrite the very file storage refused to read.
    if session is None:
        if auth_verdict.detail:
            findings.append(
                Finding(
                    id="F-001",
                    severity="critical",
                    summary=f"No usable session — storage refused to load it: {auth_verdict.detail}",
                    remediation_command=None,
                    remediation_description=("Fix the storage problem named above (do NOT run spec-kitty auth login — it would overwrite the affected file)."),
                )
            )
        else:
            findings.append(
                Finding(
                    id="F-001",
                    severity="critical",
                    summary="No active session",
                    remediation_command="spec-kitty auth login",
                    remediation_description=("Authenticate with the SaaS to establish a session."),
                )
            )

    # F-003 — refresh lock stuck (age past threshold).
    if refresh_lock.stuck and refresh_lock.age_s is not None:
        findings.append(
            Finding(
                id="F-003",
                severity="critical",
                summary=(f"Refresh lock stuck (age {refresh_lock.age_s:.1f}s > threshold {refresh_lock.stuck_threshold_s:.1f}s)"),
                remediation_command="spec-kitty auth doctor --unstick-lock",
                remediation_description=("Force-release the refresh lock when its age exceeds the stuck threshold."),
            )
        )

    # F-006 — persisted/in-memory drift (after no in-flight refresh).
    if session is not None and session.in_memory_drift and not refresh_lock.held:
        findings.append(
            Finding(
                id="F-006",
                severity="warn",
                summary="Persisted session differs from in-memory state",
                remediation_command="spec-kitty auth doctor",
                remediation_description=("Re-run after a CLI command to confirm the divergence has settled (typical during in-flight refresh)."),
            )
        )

    # F-007 — lock holder is on a different host (NFS scenario).
    if refresh_lock.held and refresh_lock.holder_host is not None:
        local_host = socket.gethostname()
        if refresh_lock.holder_host != local_host:
            findings.append(
                Finding(
                    id="F-007",
                    severity="warn",
                    summary=(f"Lock holder is on a different host (holder={refresh_lock.holder_host}, this={local_host})"),
                    remediation_command=None,
                    remediation_description=("Manual investigation required (NFS-shared auth root)."),
                )
            )

    auth_finding = _auth_verdict_finding(session, auth_verdict)
    if auth_finding is not None:
        findings.append(auth_finding)

    return findings


def _auth_verdict_finding(
    session: SessionSummary | None,
    auth_verdict: HealthVerdict,
) -> Finding | None:
    """Emit F-008 when a present session is not confirmed healthy."""
    if session is None or auth_verdict.state == "ok":
        return None
    return Finding(
        id="F-008",
        severity="critical" if auth_verdict.state == "fail" else "warn",
        summary=f"Session health not confirmed: {auth_verdict.evidence}",
        remediation_command=auth_verdict.remediation,
        remediation_description=("The access token could not be confirmed valid; re-authenticate or re-run with --server to probe the live session."),
    )


def compute_exit_code(findings: list[Finding]) -> int:
    """Map ``findings`` to a process exit code per ``contracts/auth-doctor.md``.

    Exit policy:
        - ``0`` — no critical findings remain (default invocation healthy or
          repairs successfully cleared every critical finding).
        - ``1`` — at least one ``critical`` finding remains.
        - ``2`` — internal exception during diagnostic gathering (handled by
          the typer shell, not by this function).
    """
    for finding in findings:
        if finding.severity == "critical":
            return 1
    return 0


# ---------------------------------------------------------------------------
# Server-session check (T015) — opt-in network path for --server flag
# ---------------------------------------------------------------------------


def _server_issuer_mismatch_error(tm: Any, target: ResolvedServerTarget | None = None) -> str | None:
    """Return a mismatch message when the stored session predates the resolved server.

    Best-effort and side-effect-free: this never touches the token manager's
    persisted state, and any failure to read the current session is treated
    as "cannot determine" rather than blocking the caller — the normal
    ``get_access_token`` path decides in that case.
    ``asyncio.iscoroutine`` guards a test double built from a bare
    ``AsyncMock`` (its unconfigured attributes return coroutines, unlike the
    real synchronous ``TokenManager.get_current_session``); closing it avoids
    an "never awaited" warning without treating the double as a mismatch.
    """
    try:
        session = tm.get_current_session()
    except Exception:  # noqa: BLE001 - best-effort pre-check, never blocks the real check
        return None
    if asyncio.iscoroutine(session):
        session.close()
        return None
    if not isinstance(session, StoredSession) or session.issuer_url is None:
        return None
    if target is None:
        try:
            target = resolve_server_target()
        except Exception:  # noqa: BLE001 - standalone diagnostic remains best-effort
            return None
    # Explicit annotation: `specify_cli.*` is checked with follow_imports = "skip"
    # (pyproject.toml), so mypy sees format_saas_mismatch_warning's return as Any.
    warning: str | None = format_saas_mismatch_warning(
        session.issuer_url,
        source_name=saas_source_name(target),
        resolved_server_url=target.resolved_server_url,
    )
    return warning


async def _check_server_session() -> ServerSessionStatus:
    """Refresh token if needed, then GET /api/v1/session-status.

    Returns ServerSessionStatus. Never raises — all errors map to
    active=False with a brief, non-sensitive error description.

    A known issuer/server mismatch (see :func:`_server_issuer_mismatch_error`)
    short-circuits before any refresh is attempted (issue #253).
    """
    from specify_cli.auth import get_token_manager  # noqa: PLC0415 (avoid circular at module level)
    import httpx  # noqa: PLC0415

    from specify_cli.auth.errors import (  # noqa: PLC0415
        NotAuthenticatedError,
        RefreshTokenExpiredError,
        SessionInvalidError,
        TokenRefreshError,
    )
    from specify_cli.auth.refresh_transaction import RefreshLockTimeoutError  # noqa: PLC0415

    tm = get_token_manager()

    try:
        # Resolve once so issuer diagnostics and the bearer-token request use
        # the same configured target (#762).
        target = resolve_server_target(process_wide_override=False)
    except ServerTargetSplitBrainError as exc:
        return ServerSessionStatus(active=False, error=f"SaaS URL mismatch: {exc}")
    except Exception:  # noqa: BLE001 - SaaS config/resolution failure is reported as inactive server status
        return ServerSessionStatus(active=False, error="SaaS URL not configured")

    mismatch = _server_issuer_mismatch_error(tm, target)
    if mismatch is not None:
        return ServerSessionStatus(active=False, error=mismatch)

    # #4761: a storage refusal is not a server verdict — report the storage
    # layer's own message instead of attempting a refresh that would fail
    # with a NotAuthenticatedError indistinguishable from a revoked session.
    assessment = getattr(tm, "session_assessment", None)
    storage_refusal = getattr(assessment, "detail", None)
    if getattr(assessment, "reason", None) == "storage_permissions_unsafe" and storage_refusal:
        return ServerSessionStatus(active=False, error=storage_refusal)

    try:
        access_token = await tm.get_access_token()
    except (NotAuthenticatedError, RefreshTokenExpiredError, SessionInvalidError):
        return ServerSessionStatus(active=False, error="re-authenticate")
    except RefreshLockTimeoutError as exc:
        message = str(exc) or "Auth refresh is busy; retry later."
        return ServerSessionStatus(active=False, error=message)
    except TokenRefreshError:
        return ServerSessionStatus(
            active=False,
            error=("Could not refresh access token; run `spec-kitty auth login` if this persists."),
        )
    except Exception:  # noqa: BLE001 - token acquisition failures are translated to doctor status
        return ServerSessionStatus(active=False, error="Could not obtain access token.")

    saas_url = target.resolved_server_url

    url = f"{saas_url}/api/v1/session-status"
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
    except httpx.RequestError as exc:
        return ServerSessionStatus(active=False, error=f"Network error: {type(exc).__name__}")
    except Exception:  # noqa: BLE001 - unexpected server probe failures are translated to doctor status
        return ServerSessionStatus(active=False, error="Unexpected error during server check")

    if response.status_code == 200:
        try:
            body = response.json()
            session_id = body.get("session_id")
            return ServerSessionStatus(active=True, session_id=session_id)
        except ValueError:
            return ServerSessionStatus(active=False, error="Invalid response from server")

    if response.status_code == 401:
        return ServerSessionStatus(active=False, error="re-authenticate")

    return ServerSessionStatus(active=False, error=f"Server returned HTTP {response.status_code}")


# ---------------------------------------------------------------------------
# Public assembly + rendering API (T023, T024, T026)
# ---------------------------------------------------------------------------


def assemble_report(
    *,
    stuck_threshold_s: float = 60.0,
    server_probe: ServerSessionStatus | None = None,
) -> DoctorReport:
    """Gather local-only state into a :class:`DoctorReport`. No mutation.

    All inputs are local files (allowed by C-007). The function never
    writes, deletes, or touches refresh-lock files — that mutation is the
    responsibility of :func:`doctor_impl` when the user opts in via
    ``--unstick-lock``.
    """
    now = now_utc()
    session_summary, raw_session = _read_session_summary()
    assessment = getattr(get_token_manager(), "session_assessment", None)
    auth_verdict = evaluate_auth_verdict(
        raw_session,
        now,
        server_probe=server_probe,
        session_assessment_reason=getattr(assessment, "reason", None),
        session_assessment_detail=getattr(assessment, "detail", None),
    )
    refresh_lock = _read_lock_summary(stuck_threshold_s)

    findings = _compute_findings(
        session=session_summary,
        refresh_lock=refresh_lock,
        auth_verdict=auth_verdict,
    )

    return DoctorReport(
        schema_version=_SCHEMA_VERSION,
        generated_at=now,
        auth_root=_read_auth_root(),
        session=session_summary,
        refresh_lock=refresh_lock,
        auth_verdict=auth_verdict,
        findings=findings,
    )


def render_report(report: DoctorReport, console: Console, *, show_server_hint: bool = True) -> None:
    """Render a :class:`DoctorReport` as the 5-section Rich layout."""
    _render_identity_section(report, console)
    _render_token_section(report, console)
    _render_storage_section(report, console)
    _render_lock_section(report.refresh_lock, console)
    _render_findings_section(report, console)

    # Always present in offline mode — encourage server-aware check.
    if show_server_hint:
        console.print()
        console.print("[dim]Run [bold]spec-kitty auth doctor --server[/bold] to verify server session status.[/dim]")


def _render_identity_section(report: DoctorReport, console: Console) -> None:
    """Section 1 — Identity."""
    console.print("[bold]Identity[/bold]")
    if report.session is None:
        if report.auth_verdict.detail:
            # #4761: storage refused to load the session — render the cause
            # and its remedy instead of the not-authenticated/login pair,
            # which would misdiagnose a storage failure as "logged out".
            console.print("  [red]X Not authenticated — session storage refused[/red]")
            console.print(f"  {escape(sanitize_terminal_text(report.auth_verdict.detail))}")
        else:
            console.print("  [red]X Not authenticated[/red]")
            console.print("  Run [bold]spec-kitty auth login[/bold] to authenticate.")
    else:
        user_email = report.session.user_email or UNKNOWN_DISPLAY
        session_id = report.session.session_id or UNKNOWN_DISPLAY
        console.print(f"  User:           {escape(sanitize_terminal_text(user_email))}")
        console.print(f"  Session ID:     {escape(sanitize_terminal_text(session_id))}")
        if report.session.auth_method is not None:
            console.print(f"  Auth method:    {escape(sanitize_terminal_text(format_auth_method(report.session.auth_method)))}")
    console.print()


def _no_session_note(report: DoctorReport) -> str:
    """The Tokens/Storage placeholder line when no session is loaded.

    Distinguishes "nothing is stored" from "something is stored but storage
    refused to read it" (#4761) so neither section contributes to the
    no-session misdiagnosis. The unreadable flavour is gated on the session
    actually being absent, not on ``auth_verdict.detail`` truthiness alone:
    the ``unknown`` verdict — a *present, readable* session whose refresh
    chain is unproven offline — also carries a detail line, and a
    detail-truthiness gate made the Storage section claim a refusal for a
    session that loaded fine (#4761 squad pass 2 MINOR). With ``session is
    None``, a truthy ``detail`` can only come from the storage-refusal
    verdict rung — every other detail-carrying verdict requires a live
    session.
    """
    if report.session is None and report.auth_verdict.detail:
        return "(session unreadable — storage refused to load it)"
    return "(no session)"


def _render_token_section(report: DoctorReport, console: Console) -> None:
    """Section 2 — Tokens."""
    console.print("[bold]Tokens[/bold]")
    if report.session is None:
        console.print(f"  {_no_session_note(report)}")
    else:
        access = report.session.access_token_remaining_s
        if access is not None:
            console.print(f"  Access token:   {format_duration(access)}")
        if report.session.refresh_token_remaining_s is None:
            console.print("  Refresh token:  [dim]server-managed (legacy)[/dim]")
        else:
            console.print(f"  Refresh token:  {format_duration(report.session.refresh_token_remaining_s)}")
    console.print()


def _render_storage_section(report: DoctorReport, console: Console) -> None:
    """Section 3 — Storage."""
    console.print("[bold]Storage[/bold]")
    if report.session is None or report.session.storage_backend is None:
        console.print(f"  {_no_session_note(report)}")
    else:
        console.print(f"  Backend:        {escape(sanitize_terminal_text(format_storage_backend(report.session.storage_backend)))}")
        if report.session.in_memory_drift:
            console.print("  [dim]Note: persisted differs from in-memory (typical during in-flight refresh)[/dim]")
    console.print()


def _render_lock_section(lock: LockSummary, console: Console) -> None:
    """Section 4 — Refresh Lock."""
    console.print("[bold]Refresh Lock[/bold]")
    if not lock.held:
        console.print("  unheld")
    else:
        style = "[red]" if lock.stuck else ""
        end_style = "[/red]" if lock.stuck else ""
        console.print(f"  {style}Held by PID:    {lock.holder_pid}{end_style}")
        if lock.started_at is not None:
            console.print(f"  Acquired at:    {lock.started_at.isoformat()}")
        if lock.age_s is not None:
            console.print(f"  Age:            {lock.age_s:.1f}s")
        holder_host = lock.holder_host or UNKNOWN_DISPLAY
        console.print(f"  Host:           {escape(sanitize_terminal_text(holder_host))}")
        if lock.stuck:
            console.print(f"  [red]Stuck (age > {lock.stuck_threshold_s:.1f}s)[/red]")
    console.print()


def _render_findings_section(report: DoctorReport, console: Console) -> None:
    """Section 5 — Findings & Remediation."""
    console.print("[bold]Findings[/bold]")
    if report.auth_verdict.state == "ok" and not report.findings:
        console.print("  No problems detected.")
    else:
        severity_color = {
            "info": "cyan",
            "warn": "yellow",
            "critical": "red",
        }
        for finding in report.findings:
            color = severity_color[finding.severity]
            console.print(
                f"  [[{color}]{finding.severity}[/{color}]] {escape(sanitize_terminal_text(finding.id))}: {escape(sanitize_terminal_text(finding.summary))}"
            )
            if finding.remediation_command is not None:
                description = f" — {finding.remediation_description}" if finding.remediation_description else ""
                command = escape(sanitize_terminal_text(finding.remediation_command))
                console.print(f"      Run: {command}{escape(sanitize_terminal_text(description))}")


def render_report_json(report: DoctorReport) -> str:
    """Serialise a :class:`DoctorReport` as a JSON string.

    Datetime values are emitted as ISO-8601 strings; :class:`Path` becomes
    its ``str``. The ``schema_version`` field guards against breaking
    consumer upgrades — bump it on any breaking schema change.
    """
    payload: dict[str, Any] = {
        "schema_version": report.schema_version,
        "generated_at": report.generated_at.isoformat(),
        "auth_root": str(report.auth_root),
        "session": (None if report.session is None else dataclasses.asdict(report.session)),
        "refresh_lock": _lock_summary_to_dict(report.refresh_lock),
        "findings": [_finding_to_dict(f) for f in report.findings],
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _lock_summary_to_dict(lock: LockSummary) -> dict[str, Any]:
    """Hand-serialise :class:`LockSummary` so ``started_at`` becomes ISO."""
    return {
        "held": lock.held,
        "holder_pid": lock.holder_pid,
        "started_at": (lock.started_at.isoformat() if lock.started_at is not None else None),
        "age_s": lock.age_s,
        "stuck": lock.stuck,
        "stuck_threshold_s": lock.stuck_threshold_s,
        "holder_host": lock.holder_host,
    }


def _finding_to_dict(finding: Finding) -> dict[str, Any]:
    """Serialise a :class:`Finding` to the shape in ``data-model.md`` §5."""
    payload: dict[str, Any] = {
        "id": finding.id,
        "severity": finding.severity,
        "summary": finding.summary,
    }
    if finding.remediation_command is not None or finding.remediation_description is not None:
        payload["remediation"] = {
            "command": finding.remediation_command,
            "description": finding.remediation_description,
        }
    else:
        payload["remediation"] = None
    return payload


UNKNOWN_DISPLAY = "(unknown)"


# ---------------------------------------------------------------------------
# Repair helpers (extracted to keep doctor_impl within C901 complexity budget)
# ---------------------------------------------------------------------------


def _run_unstick_lock(
    report: DoctorReport,
    *,
    stuck_threshold: float,
    messages: list[str],
    server_probe: ServerSessionStatus | None = None,
) -> DoctorReport:
    """Orchestrate the ``--unstick-lock`` phase. Returns a refreshed report."""
    if not any(f.id == "F-003" for f in report.findings):
        messages.append("--unstick-lock: lock not stuck; no-op.")
        return report

    removed = force_release(_refresh_lock_path(), only_if_age_s=stuck_threshold)
    if removed:
        messages.append("--unstick-lock: stuck lock released.")
    else:
        messages.append("--unstick-lock: lock not removed (fresh, missing, or unreadable).")
    return assemble_report(
        stuck_threshold_s=stuck_threshold,
        server_probe=server_probe,
    )


def _render_server_status(status: ServerSessionStatus) -> None:
    """Render the optional server-session block in human output."""
    console.print("[bold]Server Session[/bold]")
    if status.active:
        sid = status.session_id or UNKNOWN_DISPLAY
        console.print(f"  Status:  [green]active[/green] (session: {sid})")
    else:
        reason = status.error or "unknown"
        if reason == "re-authenticate":
            console.print("  Status:  [red]invalid[/red] — Run [bold]spec-kitty auth login[/bold] to re-authenticate.")
        else:
            # escape(): `reason` can be the issuer-mismatch message, which
            # names the resolved-config source and may contain a literal
            # `[sync]`-shaped substring (#182) — unescaped, Rich markup
            # either drops the bracketed text or raises MarkupError.
            console.print(f"  Status:  [yellow]check failed[/yellow] — {escape(reason)}")
    console.print()


# ---------------------------------------------------------------------------
# Orchestration entry point (T027)
# ---------------------------------------------------------------------------


def doctor_impl(
    *,
    json_output: bool,
    unstick_lock: bool,
    stuck_threshold: float,
    server: bool = False,
) -> int:
    """Top-level dispatch for the ``spec-kitty auth doctor`` command.

    Default invocation (no flags) is read-only: gather state, render, exit.

    ``--unstick-lock`` runs the underlying repair primitive only when the
    corresponding finding is present. After any repair we re-run
    :func:`assemble_report` so the rendered output reflects the post-repair
    state.

    ``--server`` is an explicit opt-in that refreshes the access token and
    calls ``GET /api/v1/session-status``. The default path (server=False)
    makes ZERO outbound network calls (C-007).
    """
    server_status: ServerSessionStatus | None = None
    if server:
        server_status = asyncio.run(_check_server_session())

    report = assemble_report(
        stuck_threshold_s=stuck_threshold,
        server_probe=server_status,
    )
    repair_messages: list[str] = []

    if unstick_lock:
        report = _run_unstick_lock(
            report,
            stuck_threshold=stuck_threshold,
            messages=repair_messages,
            server_probe=server_status,
        )

    if json_output:
        # JSON consumers read the post-repair report state directly.
        payload = json.loads(render_report_json(report))
        if server_status is not None:
            payload["server_session"] = {
                "active": server_status.active,
                "session_id": server_status.session_id,
                "error": server_status.error,
            }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return compute_exit_code(report.findings)

    render_report(report, console, show_server_hint=not server)
    for message in repair_messages:
        console.print(message)

    if server and server_status is not None:
        _render_server_status(server_status)

    return compute_exit_code(report.findings)
