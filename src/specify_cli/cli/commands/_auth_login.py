"""Implementation of ``spec-kitty auth login``. Owned by WP04.

This module is lazy-imported from ``cli.commands.auth`` when the ``login``
command fires. Separating the implementation from the Typer command shell
lets WP06 (logout) and WP07 (status) ship their own per-command modules
without file-level conflicts on ``auth.py``.

The ``--headless`` branch lazy-imports a future ``auth.flows.device_code``
module that WP05 will supply. Until WP05 lands, attempting to use
``--headless`` surfaces a clear "not yet implemented" error.

The ``--machine`` branch (#3277) lazy-imports
``auth.flows.client_credentials`` — the non-interactive CI/machine mode.
Its credential pair is loaded from the environment (fail closed, never
prompted, never printed), exchanged via the OAuth ``client_credentials``
grant, and persisted as an ordinary session tagged
``auth_method="client_credentials"`` so every TokenManager consumer works
unchanged.

This module never hardcodes a SaaS URL. It resolves the login target through the
canonical resolver :func:`specify_cli.auth.server_target.resolve_server_target`,
which folds ``SPEC_KITTY_SAAS_URL`` (env) over ``[sync].server_url`` in
``config.toml`` and falls back to the packaged default — the same
precedence every hosted surface uses.
This is deliberate (#3406, FR-005): login previously read the env-only accessor
``get_saas_base_url`` and errored when the env var was unset, even when the user
had already set a server via ``config.toml``. That inconsistency meant
a token could be obtained one way while sync targeted another; resolving both the
same way removes it.

#4259 adds two pre-flight duties on top of that resolution:

- **Target/provenance diagnostics.** Before any browser or device flow starts,
  login prints the resolved target *and* the configuration source it came from
  (the same provenance suffix ``auth status`` renders), and warns — never
  rejects — when the target is a noncanonical first-party endpoint (the retired
  ``app.spec-kitty.ai`` address foremost). A custom/self-hosted endpoint is
  never rewritten and never blocked, only labelled as custom.
- **Issuer-safe session handling.** A stored session minted for a different
  endpoint is never *relabeled* as valid for the resolved target nor silently
  forwarded to it: plain ``auth login`` refuses with the mismatch remedy, and
  only ``--force`` re-authenticates (minting fresh credentials against the
  resolved target). The non-interactive bridge enforces the same boundary at
  :func:`specify_cli.saas_client.auth._guard_session_issuer` (#234).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

import typer
from rich.markup import escape
from specify_cli.cli.console import console, sanitize_terminal_text

from specify_cli.auth import (
    AuthenticationError,
    BrowserLaunchError,
    CallbackTimeoutError,
    CallbackValidationError,
    get_token_manager,
    NetworkError,
)
from specify_cli.auth.config import (
    DEFAULT_HOSTED_SAAS_URL,
    is_noncanonical_first_party_url,
    is_retired_first_party_url,
)
from specify_cli.auth.errors import ConfigurationError
from specify_cli.auth.server_target import ResolvedServerTarget, resolve_server_target
from specify_cli.cli.commands._auth_saas_target import (
    format_saas_mismatch_warning,
    format_saas_provenance,
    saas_source_name,
)

if TYPE_CHECKING:
    from specify_cli.auth.session import StorageBackend, StoredSession
    from specify_cli.auth.token_manager import TokenManager

log = logging.getLogger(__name__)


async def login_impl(*, headless: bool, force: bool, machine: bool = False) -> None:
    """Run the login flow. Called by ``cli.commands.auth.login``.

    Args:
        headless: When True, dispatches to the device authorization flow
            (WP05). Defaults to False (browser PKCE flow).
        force: When True, re-authenticates even if a session is already
            present. Defaults to False.
        machine: When True, dispatches to the non-interactive
            ``client_credentials`` machine flow (#3277) — credentials come
            from the environment, fail closed, and no browser, device flow,
            or prompt is ever offered. Mutually exclusive with ``headless``
            (enforced by the Typer shell).

    Note:
        Identity acquisition is intentionally decoupled from TeamSpace
        mission-state readiness (DDD: Identity & Access vs TeamSpace
        contexts). Sync / tracker / connect commands continue to call
        ``enforce_teamspace_mission_state_ready`` themselves — those are
        the commands that actually depend on TeamSpace state.
    """
    # Resolve the login target the same way every hosted surface does — env over
    # config.toml (#3406, FR-005; #4259: an explicitly-set env value is a real
    # opinion even when it equals the packaged default). The resolver fails
    # closed (#179) when neither source names a server; surface its remedy
    # verbatim instead of duplicating the message here so login and the
    # resolver cannot drift apart again.
    try:
        target = resolve_server_target()
    except ConfigurationError as exc:
        # escape(): the remedy names `[sync].server_url` — unescaped, Rich
        # markup parses "[sync]" as a style tag and silently drops it (#182).
        console.print(f"[red]X {escape(str(exc))}[/red]")
        raise typer.Exit(1) from None
    saas_url = target.resolved_server_url
    # Before any flow starts (#4259): show what will be authenticated against
    # and where that target came from, and warn — never reject — on a
    # noncanonical first-party endpoint.
    _print_login_target(target)

    tm = get_token_manager()

    if tm.is_authenticated and not force:
        session = tm.get_current_session()
        assert session is not None  # is_authenticated guarantees this
        mismatch = format_saas_mismatch_warning(
            session.issuer_url,
            source_name=saas_source_name(target),
            resolved_server_url=saas_url,
        )
        if mismatch is not None:
            # Issuer boundary (#4259, same refusal as #234's non-interactive
            # guard): the stored session was minted for a different endpoint.
            # It is never relabeled as valid for this target, and its bearer
            # is never forwarded here — fresh authentication is required.
            # escape(): both URLs are operator-controlled (#182/#202).
            console.print(f"[yellow]! {escape(sanitize_terminal_text(mismatch))}[/yellow]")
            console.print(
                "Credentials minted for one endpoint are never reused against "
                "another; fresh authentication is required."
            )
            return
        console.print(
            f"[green]+ Already logged in as {escape(session.email)}[/green]"
        )
        console.print(
            "Run [bold]spec-kitty auth login --force[/bold] to re-authenticate, "
            "or [bold]spec-kitty auth logout[/bold] first."
        )
        return

    if force and tm.is_authenticated:
        console.print("[dim]Forcing re-authentication...[/dim]")
        tm.clear_session()

    if machine:
        await _run_machine_flow(tm, saas_url)
    elif headless:
        await _run_device_flow(tm, saas_url)
    else:
        await _run_browser_flow(tm, saas_url)


def _print_login_target(target: ResolvedServerTarget) -> None:
    """Print the resolved login target, its configuration source, and any
    noncanonical-endpoint warning (#4259).

    Printed once in :func:`login_impl`, before the already-logged-in check
    and before either flow starts, so the operator sees *what* will be
    authenticated against and *where it came from* (the same provenance
    suffix ``auth status`` renders — shared via
    :func:`format_saas_provenance`) with enough time to abort. The warnings
    never reject and never rewrite: a retired or otherwise noncanonical
    first-party endpoint is named as such, and a custom/self-hosted
    endpoint is labelled custom — self-hosting is supported, so it gets an
    informational line, not a warning.
    """
    url = target.resolved_server_url
    # escape()+sanitize_terminal_text() over each rendered message: url and
    # any remedy naming `[sync].server_url` are operator-controlled and
    # bracket-shaped — unescaped, Rich markup drops or chokes on them
    # (#182/#202). The canonical URL is a fixed safe literal.
    console.print(
        f"[dim]SaaS: {escape(sanitize_terminal_text(url))} "
        f"{escape(sanitize_terminal_text(format_saas_provenance(target)))}[/dim]"
    )
    if is_retired_first_party_url(url):
        message = (
            f"{url} is the retired first-party endpoint; the canonical hosted "
            f"endpoint is {DEFAULT_HOSTED_SAAS_URL}. Run spec-kitty upgrade to "
            "migrate a stale config.toml target, or correct SPEC_KITTY_SAAS_URL / "
            "config.toml [sync].server_url — proceeding against the configured target."
        )
        console.print(f"[yellow]! {escape(sanitize_terminal_text(message))}[/yellow]")
        return
    if is_noncanonical_first_party_url(url):
        message = (
            f"{url} is a noncanonical first-party endpoint; the canonical "
            f"hosted endpoint is {DEFAULT_HOSTED_SAAS_URL}."
        )
        console.print(f"[yellow]! {escape(sanitize_terminal_text(message))}[/yellow]")
        return
    if url != DEFAULT_HOSTED_SAAS_URL:
        console.print(
            f"[dim]Custom endpoint (not the canonical {escape(DEFAULT_HOSTED_SAAS_URL)}); "
            "self-hosted targets are supported and left unchanged.[/dim]"
        )


async def _run_browser_flow(tm: TokenManager, saas_url: str) -> None:
    """Run the browser-based OAuth Authorization Code + PKCE flow."""
    from specify_cli.auth.flows.authorization_code import AuthorizationCodeFlow

    console.print("Opening browser for OAuth authentication...")

    flow = AuthorizationCodeFlow(
        saas_base_url=saas_url,
        storage_backend=cast("StorageBackend", tm._storage.backend_name),
    )

    try:
        session = await flow.login()
    except CallbackTimeoutError:
        console.print("[red]X Authentication timed out (5 minutes elapsed)[/red]")
        console.print("Run [bold]spec-kitty auth login[/bold] again.")
        raise typer.Exit(1) from None
    except CallbackValidationError as exc:
        # escape(): exception text can embed attacker-influenced callback data;
        # unescaped, Rich markup parses it and can raise MarkupError (#202/#182/#383).
        console.print(f"[red]X Callback validation failed: {escape(str(exc))}[/red]")
        console.print(
            "This may indicate a CSRF attack or a stale browser tab. "
            "Run [bold]spec-kitty auth login[/bold] again."
        )
        raise typer.Exit(1) from exc
    except BrowserLaunchError as exc:
        # escape(): see CallbackValidationError above.
        console.print(f"[red]X Could not launch browser: {escape(str(exc))}[/red]")
        console.print("Try [bold]spec-kitty auth login --headless[/bold] instead.")
        raise typer.Exit(1) from exc
    except AuthenticationError as exc:
        # escape(): the message can embed the raw SaaS token-exchange response
        # body (authorization_code.py); unescaped, a hostile/compromised SaaS
        # response containing markup-like text can raise MarkupError instead of
        # a clean error exit (#526).
        console.print(f"[red]X Authentication failed: {escape(str(exc))}[/red]")
        raise typer.Exit(1) from exc

    tm.set_session(session)
    _print_success(session)


async def _run_device_flow(tm: TokenManager, saas_url: str) -> None:
    """Run the device authorization flow (RFC 8628).

    The actual ``DeviceCodeFlow`` orchestrator is provided by WP05 in
    ``specify_cli.auth.flows.device_code``. Until that module lands, the
    import below raises ``ImportError`` which we surface as a clear
    "not yet implemented" message.
    """
    try:
        # Lazy import: WP05 ships this module. Until it lands, this import
        # fails at runtime and we surface a "not yet implemented" error.
        # mypy silencing: the module does not exist in lane-a yet, and any
        # stale bytecode in sibling checkouts may confuse import analysis.
        from specify_cli.auth.flows.device_code import (  # type: ignore[import-not-found,import-untyped,unused-ignore]
            DeviceCodeFlow,
        )
    except ImportError as exc:
        console.print(
            "[red]X Headless login is not yet implemented (waiting on WP05).[/red]"
        )
        raise typer.Exit(1) from exc

    flow = DeviceCodeFlow(
        saas_base_url=saas_url,
        storage_backend=cast("StorageBackend", tm._storage.backend_name),
    )

    try:
        session = await flow.login(progress_writer=console.print)
    except AuthenticationError as exc:
        # escape(): see the browser-flow AuthenticationError handler above (#526).
        console.print(f"[red]X Device flow failed: {escape(str(exc))}[/red]")
        raise typer.Exit(1) from exc

    tm.set_session(session)
    _print_success(session)


async def _run_machine_flow(tm: TokenManager, saas_url: str) -> None:
    """Run the non-interactive ``client_credentials`` machine flow (#3277).

    Every failure here fails closed with a precise remediation naming the
    configuration variables or the server-side provisioning commands — a
    machine misconfiguration must never degrade into a device-flow or
    browser prompt, and the secret value must never appear in output.
    """
    from specify_cli.auth.flows.client_credentials import (
        ClientCredentialsFlow,
        load_machine_credentials,
    )

    console.print("Authenticating with machine credentials (client_credentials)...")
    console.print(f"[dim]SaaS: {saas_url}[/dim]")

    try:
        credentials = load_machine_credentials()
    except ConfigurationError as exc:
        # escape(): the remedy names ``SPEC_KITTY_*`` variables — bracket-free
        # today, but escape() keeps that invariant from depending on future
        # variable spelling (#182).
        console.print(f"[red]X {escape(str(exc))}[/red]")
        raise typer.Exit(1) from None

    flow = ClientCredentialsFlow(
        saas_base_url=saas_url,
        storage_backend=cast("StorageBackend", tm._storage.backend_name),
    )

    try:
        session = await flow.login(credentials)
    except NetworkError as exc:
        console.print(f"[red]X Could not reach the SaaS: {escape(str(exc))}[/red]")
        console.print("Check SPEC_KITTY_SAAS_URL and network access from this runner.")
        raise typer.Exit(1) from exc
    except AuthenticationError as exc:
        # The flow's messages are self-contained (they name the remediation
        # path); printed verbatim so CLI output and the raised error cannot
        # drift apart.
        console.print(f"[red]X {escape(str(exc))}[/red]")
        raise typer.Exit(1) from exc

    tm.set_session(session)
    _print_machine_success(session)


def _print_machine_success(session: StoredSession) -> None:
    """Print the post-login success message for the machine flow.

    Deliberately quieter than the human message: no team default (a machine
    credential's authority is its server-side scope, not a client-picked
    team), and the scope — which is not secret — is echoed so a CI log
    records exactly what the credential can reach.
    """
    console.print()
    console.print(f"[green]+ Authenticated as {session.email} (machine)[/green]")
    console.print(f"  Scope: {session.scope or '(none reported)'}")
    console.print("  Rotating the credential? Re-provision, then re-run auth login --machine --force.")


def _print_success(session: StoredSession) -> None:
    """Print the post-login success message."""
    console.print()
    console.print(f"[green]+ Authenticated as {escape(session.email)}[/green]")
    if session.teams:
        default_team = next(
            (t for t in session.teams if t.id == session.default_team_id),
            None,
        )
        if default_team:
            suffix = " [Private Teamspace]" if default_team.is_private_teamspace else ""
            console.print(f"  Default team: {escape(default_team.name)}{suffix}")


__all__ = ["login_impl"]
