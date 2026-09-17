"""Dashboard command implementation."""

from __future__ import annotations

import webbrowser

import typer

from specify_cli.cli.console import console
from specify_cli.cli.helpers import get_project_root_or_exit
from specify_cli.dashboard import ensure_dashboard_running, stop_dashboard


def dashboard(
    port: int | None = typer.Option(
        None,
        "--port",
        help="Preferred port for the dashboard (falls back to the first available port).",
    ),
    kill: bool = typer.Option(
        False,
        "--kill",
        help="Stop the running dashboard for this project and clear its metadata.",
    ),
    open_browser: bool = typer.Option(
        False,
        "--open",
        help="Open dashboard URL in your default browser (disabled by default).",
    ),
    emit_json: bool = typer.Option(
        False,
        "--json",
        help=(
            "Print the mission registry as JSON (keyed by mission_id) and exit. "
            "Does not start the dashboard server."
        ),
    ),
) -> None:
    """Open or stop the Spec Kitty dashboard."""
    project_root = get_project_root_or_exit(json_output=emit_json)

    # --json: emit mission registry keyed by mission_id and exit early.
    if emit_json:
        from specify_cli.dashboard.scanner import build_mission_registry, sort_missions_for_display

        registry = build_mission_registry(project_root)
        display_order = sort_missions_for_display(registry)
        payload = {
            "missions": registry,
            "display_order": display_order,
        }
        console.emit_json(payload)
        return

    console.print()

    if kill:
        stopped, message = stop_dashboard(project_root)
        console.print(f"[green]✅ {message}[/green]" if stopped else f"[yellow]⚠️  {message}[/yellow]")
        console.print()
        return

    if port is not None and not (1 <= port <= 65535):
        console.print("[red]❌ Invalid port specified. Use a value between 1 and 65535.[/red]")
        console.print()
        raise typer.Exit(1)

    # FR-006 caller contract (T025): charter preflight runs before the
    # dashboard starts. On failure we STILL launch the server so the
    # operator can see the running state, but we persist the
    # ``blocked_reason`` so the API surface can expose it as a critical
    # banner. Passed advisory warnings use the same persistence channel; a
    # clean success clears stale warning state.
    from charter.resolution import GitCommonDirUnavailableError, NotInsideRepositoryError

    from specify_cli.charter_runtime.preflight.dashboard_warning import (
        clear_preflight_warning,
        write_preflight_warning,
    )
    from specify_cli.charter_runtime.preflight.hook import run_preflight_for_dashboard
    from specify_cli.cli.helpers import exit_git_resolution_failure

    # #4123: a `spec-kitty init`-ed project that was never `git init`-ed
    # must get the actionable git-init message here, never a raw
    # NotInsideRepositoryError traceback (nor the misleading "re-run
    # init" advice the generic handler below used to print).
    try:
        preflight_result = run_preflight_for_dashboard(project_root)
    except (NotInsideRepositoryError, GitCommonDirUnavailableError) as exc:
        exit_git_resolution_failure(exc, project_root)
    warning = (
        preflight_result.blocked_reason
        if not preflight_result.passed
        else "\n".join(preflight_result.warnings) or None
    )
    if warning:
        write_preflight_warning(project_root, warning)
        console.print(f"[yellow]⚠ Charter preflight warning:[/yellow] {warning}")
    else:
        clear_preflight_warning(project_root)

    try:
        dashboard_url, active_port, started = ensure_dashboard_running(project_root, preferred_port=port)
    except FileNotFoundError as exc:  # Missing .kittify directory
        console.print("[red]❌ Dashboard metadata not found[/red]")
        console.print(f"   {exc}")
        console.print()
        console.print("[yellow]💡 Initialize this project first:[/yellow]")
        console.print(f"  [cyan]cd {project_root}[/cyan]")
        console.print("  [cyan]spec-kitty init .[/cyan]")
        console.print()
        raise typer.Exit(1) from exc
    except (NotInsideRepositoryError, GitCommonDirUnavailableError) as exc:  # #4123
        exit_git_resolution_failure(exc, project_root)
    except OSError as exc:  # Port conflict or permission error
        error_msg = str(exc).lower()
        if "address already in use" in error_msg or "port" in error_msg:
            console.print("[red]❌ Port conflict detected[/red]")
            console.print(f"   {exc}")
            console.print()
            console.print("[yellow]💡 Try these steps:[/yellow]")
            if port:
                console.print(f"  1. Use a different port: [cyan]spec-kitty dashboard --port {port + 1}[/cyan]")
            else:
                console.print("  1. Use a specific port: [cyan]spec-kitty dashboard --port 9238[/cyan]")
            console.print("  2. Or kill existing dashboard: [cyan]spec-kitty dashboard --kill[/cyan]")
            console.print()
        else:
            console.print("[red]❌ Unable to start dashboard[/red]")
            console.print(f"   {exc}")
            console.print()
        raise typer.Exit(1) from exc
    except Exception as exc:  # pragma: no cover
        console.print("[red]❌ Unable to start or locate the dashboard[/red]")
        console.print(f"   {exc}")
        console.print()
        console.print("[yellow]💡 Try running:[/yellow]")
        console.print(f"  [cyan]cd {project_root}[/cyan]")
        console.print("  [cyan]spec-kitty init .[/cyan]")
        console.print()
        raise typer.Exit(1) from exc

    console.print("[bold green]Spec Kitty Dashboard[/bold green]")
    console.print("[cyan]" + "=" * 60 + "[/cyan]")
    console.print()
    console.print(f"  [bold cyan]Project Root:[/bold cyan] {project_root}")
    console.print(f"  [bold cyan]URL:[/bold cyan] {dashboard_url}")
    console.print(f"  [bold cyan]Port:[/bold cyan] {active_port}")
    if port is not None and port != active_port:
        console.print(f"  [yellow]⚠️ Requested port {port} was unavailable; using {active_port} instead.[/yellow]")
    console.print()

    status_msg = (
        f"  [green]✅ Status:[/green] Started new dashboard instance on port {active_port}"
        if started
        else f"  [green]✅ Status:[/green] Dashboard already running on port {active_port}"
    )
    console.print(status_msg)
    console.print()
    console.print("[cyan]" + "=" * 60 + "[/cyan]")
    console.print()

    if open_browser:
        try:
            webbrowser.open(dashboard_url)
            console.print("[green]✅ Opening dashboard in your browser...[/green]")
            console.print()
        except Exception:
            console.print("[yellow]⚠️  Could not automatically open browser[/yellow]")
            console.print(f"   Please open this URL manually: [cyan]{dashboard_url}[/cyan]")
            console.print()
    else:
        console.print("[dim]Browser auto-open is disabled by default.[/dim]")
        console.print(f"[dim]Open manually: [cyan]{dashboard_url}[/cyan] (or use --open)[/dim]")
        console.print()


__all__ = ["dashboard"]
