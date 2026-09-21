"""Implementation of ``spec-kitty auth logout``. Owned by WP02.

This module is lazy-imported from ``cli.commands.auth`` when the ``logout``
command fires. The dispatch shell in ``auth.py`` (owned by WP04) imports
:func:`logout_impl` on demand so WP02 can ship independently.

Behavior (spec 080 FR-001–FR-005, FR-011, FR-016):

- **FR-001/FR-002**: On normal logout, POST ``/oauth/revoke`` with the
  refresh token as a form-encoded body (RFC 7009). No ``Authorization``
  header — token possession is authorization.
- **FR-003**: ``RevokeOutcome`` models four states: REVOKED, SERVER_FAILURE,
  NETWORK_ERROR, NO_REFRESH_TOKEN. Each maps to a distinct console message.
- **FR-004**: Server revocation failure must NEVER block local credential
  deletion. Whether the server returns 200, 4xx, 5xx, or the call fails
  with a network error, the local session is cleared unconditionally.
- **FR-005**: If local cleanup fails (``tm.clear_session()`` raises), print
  an error message and exit with code 1.
- **FR-016**: The final ``Logged out`` banner runs only when local cleanup
  succeeds.

Security invariant: the refresh token value must never appear in any log
line, error message, console output, or exception string.
"""

from __future__ import annotations

import logging

import typer
from rich.markup import escape
from specify_cli.cli.console import console, sanitize_terminal_text

from specify_cli.auth import get_token_manager
from specify_cli.auth.errors import IssuerTargetMismatchError
from specify_cli.auth.flows.revoke import RevokeFlow, RevokeOutcome
from specify_cli.auth.server_target import ServerTargetSplitBrainError, resolve_token_endpoint
from specify_cli.auth.session import StoredSession

log = logging.getLogger(__name__)


async def logout_impl(*, force: bool) -> None:
    """Run the logout flow.

    Server-side revocation failure does not block local credential deletion
    (FR-004). The ``force`` flag skips the server call entirely and only
    deletes the local session.

    Args:
        force: When True, skip the server-side revocation and delete only
            the local session. Use this when the SaaS is unreachable or
            the user wants a purely local cleanup.
    """
    tm = get_token_manager()
    session = tm.get_current_session()

    if session is None:
        # Already logged out — exit 0 with a friendly notice. This is not
        # an error condition; re-running logout is idempotent.
        console.print("[dim]i[/dim] Not logged in.")
        return

    if force:
        console.print("[dim]Skipping server revocation (--force).[/dim]")
    else:
        # Try to revoke the refresh token server-side. Any failure is
        # reported to the user but does NOT block local cleanup below.
        # #3980: the target always resolves now (env override or the packaged
        # default), so the former "no URL configured → local logout only"
        # branch is gone; a transport failure is reported by the outcome.
        outcome = await RevokeFlow().revoke(session)
        _print_revoke_outcome(outcome, session)

    # FR-004: local cleanup is unconditional. This runs regardless of the
    # server-call outcome — 200, 4xx/5xx, network error, config error, or
    # --force. If clear_session() raises, we report the error and exit 1.
    try:
        tm.clear_session()
    except Exception as exc:  # noqa: BLE001 - logout must report any local credential deletion failure
        console.print(f"[red]✗ Local credentials could not be deleted: {type(exc).__name__}. You may need to delete them manually.[/red]")
        raise typer.Exit(code=1)

    console.print("[green]+ Logged out.[/green]")


def _print_revoke_outcome(outcome: RevokeOutcome, session: StoredSession) -> None:
    """Print the appropriate console message for the given revoke outcome."""
    if outcome is RevokeOutcome.REVOKED:
        console.print("[green]✓ Server revocation confirmed.[/green]")
    elif outcome is RevokeOutcome.NO_REFRESH_TOKEN:
        console.print("[yellow]! Server revocation could not be attempted (no refresh token). Local credentials will still be deleted.[/yellow]")
    elif outcome is RevokeOutcome.NETWORK_ERROR:
        console.print("[yellow]! Server revocation not confirmed (network error). Local credentials will still be deleted.[/yellow]")
    elif outcome is RevokeOutcome.ISSUER_MISMATCH:
        _print_issuer_mismatch_warning(session)
    else:  # SERVER_FAILURE
        console.print("[yellow]! Server revocation not confirmed (server error). Local credentials will still be deleted.[/yellow]")


def _print_issuer_mismatch_warning(session: StoredSession) -> None:
    """Warn that server-side revocation was refused/skipped over an issuer mismatch.

    ``RevokeFlow.revoke`` collapses both a mismatch and a split-brain
    ambiguity into ``RevokeOutcome.ISSUER_MISMATCH`` (no payload), so the
    specific, actionable detail (issuer host, resolved host, remedy) is
    re-derived here via :func:`resolve_token_endpoint` — a pure, network-free
    recomputation of the same decision ``revoke()`` already made, not a
    second network attempt. NFR-006: the resulting message never contains
    token material, only host names and the remedy command.
    """
    try:
        resolve_token_endpoint(session)
    except IssuerTargetMismatchError as exc:
        detail = escape(sanitize_terminal_text(str(exc)))
        console.print(f"[yellow]! Server-side revocation skipped: {detail} Local credentials will still be deleted.[/yellow]")
    except ServerTargetSplitBrainError as exc:
        detail = escape(sanitize_terminal_text(str(exc)))
        console.print(f"[yellow]! Server-side revocation skipped (server target is ambiguous): {detail} Local credentials will still be deleted.[/yellow]")
    else:
        # The target now resolves cleanly (e.g. reconfigured mid-run) —
        # nothing specific left to report beyond the generic skip.
        console.print("[yellow]! Server-side revocation skipped due to a target mismatch. Local credentials will still be deleted.[/yellow]")


__all__ = ["logout_impl"]
