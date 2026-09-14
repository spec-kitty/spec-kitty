"""spec-kitty auth — OAuth login, logout, and status.

This module is a thin Typer command shell. The actual implementation of
each command lives in a sibling ``_auth_<name>.py`` module that is imported
lazily when the command is invoked. This separation allows different work
packages to own different commands without file-level conflicts.

Owned by WP04 (login dispatch + shell). WP06 owns ``_auth_logout.py`` and
WP07 owns ``_auth_status.py``; those modules are lazy-imported inside the
respective command bodies and do not need to exist at WP04 land time.

Wiring: the ``login`` command dispatches to ``_auth_login.login_impl``,
which in turn uses ``get_token_manager`` from :mod:`specify_cli.auth`
and runs the ``AuthorizationCodeFlow`` from
:mod:`specify_cli.auth.flows.authorization_code` (which consumes the
loopback callback primitives from :mod:`specify_cli.auth.loopback`).
"""

from __future__ import annotations

import asyncio

import typer
from rich.markup import escape
from specify_cli.cli.console import console, sanitize_terminal_text

app = typer.Typer(name="auth", help="Authenticate with spec-kitty SaaS.")


@app.command()
def login(
    headless: bool = typer.Option(
        False,
        "--headless",
        help="Use device authorization flow (for SSH or no-browser environments).",
    ),
    machine: bool = typer.Option(
        False,
        "--machine",
        help=(
            "Non-interactive machine/CI login: exchange the ServicePrincipal "
            "credential from SPEC_KITTY_MACHINE_CLIENT_ID + "
            "SPEC_KITTY_MACHINE_CLIENT_SECRET(_FILE) via the OAuth "
            "client_credentials grant. No browser, device flow, or prompt."
        ),
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Re-authenticate even if already logged in.",
    ),
) -> None:
    """Log in to spec-kitty SaaS via browser OAuth (or device flow with --headless)."""
    from specify_cli.cli.commands._auth_login import login_impl

    if machine and headless:
        console.print(
            "[red]X --machine and --headless are mutually exclusive:[/red] "
            "--machine is already non-interactive (client credentials exchange, "
            "no device flow)."
        )
        raise typer.Exit(2)

    try:
        asyncio.run(login_impl(headless=headless, machine=machine, force=force))
    except KeyboardInterrupt:
        console.print("\n[yellow]Login cancelled by user.[/yellow]")
        raise typer.Exit(130) from None


@app.command()
def logout(
    force: bool = typer.Option(
        False,
        "--force",
        help="Skip server revocation; only delete local credentials.",
    ),
) -> None:
    """Log out and revoke the current session."""
    try:
        from specify_cli.cli.commands._auth_logout import logout_impl
    except ImportError as exc:
        console.print(
            "[red]Error:[/red] Logout is not yet implemented (waiting on WP06)."
        )
        raise typer.Exit(1) from exc

    try:
        asyncio.run(logout_impl(force=force))
    except KeyboardInterrupt:
        console.print("\n[yellow]Logout cancelled.[/yellow]")
        raise typer.Exit(130) from None


@app.command()
def status() -> None:
    """Show current authentication status."""
    try:
        from specify_cli.cli.commands._auth_status import status_impl
    except ImportError as exc:
        console.print(
            "[red]Error:[/red] Status is not yet implemented (waiting on WP07)."
        )
        raise typer.Exit(1) from exc

    status_impl()


@app.command()
def whoami() -> None:
    """Print the authenticated user's email and exit 0, or exit 1 if not authenticated."""
    from specify_cli.cli.commands._auth_whoami import whoami_impl

    whoami_impl()


@app.command()
def doctor(
    json_output: bool = typer.Option(
        False, "--json", help="Emit findings as JSON."
    ),
    unstick_lock: bool = typer.Option(
        False,
        "--unstick-lock",
        help="Force-release a stuck refresh lock.",
    ),
    stuck_threshold: float = typer.Option(
        60.0,
        "--stuck-threshold",
        help=(
            "Age (seconds) above which the refresh lock is considered stuck."
        ),
    ),
    server: bool = typer.Option(
        False,
        "--server",
        help="Check live server session status (makes outbound call).",
    ),
) -> None:
    """Diagnose CLI auth state. Default invocation is read-only."""
    from specify_cli.cli.commands._auth_doctor import doctor_impl

    try:
        exit_code = doctor_impl(
            json_output=json_output,
            unstick_lock=unstick_lock,
            stuck_threshold=stuck_threshold,
            server=server,
        )
    except Exception as exc:  # noqa: BLE001 - doctor converts unexpected failures to exit code 2
        message = escape(sanitize_terminal_text(str(exc)))
        console.print(f"[red]Internal error during doctor: {message}[/red]")
        raise typer.Exit(2) from exc
    raise typer.Exit(exit_code)


__all__ = ["app"]
