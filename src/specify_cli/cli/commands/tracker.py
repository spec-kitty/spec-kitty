"""Tracker commands for provider bindings, mappings, and sync operations.

Local providers (beads, fp) use direct connectors with credentials stored
locally. The former SaaS/hosted providers (linear, jira, github, gitlab) were
removed from open-core together with the hosted tracker surface (#6164) and are
now refused as removed providers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from specify_cli.tracker.config import (
    LOCAL_PROVIDERS,
    REMOVED_PROVIDERS,
    require_repo_root,
)
from specify_cli.tracker.factory import normalize_provider
from specify_cli.tracker.service import TrackerService, TrackerServiceError, parse_kv_pairs

app = typer.Typer(help=("Task tracker integration commands.\n\nLocal providers (beads, fp) use direct connectors with credentials stored locally."))
map_app = typer.Typer(help="Work-package mapping commands")
sync_app = typer.Typer(help="Tracker synchronization commands")
app.add_typer(map_app, name="map")
app.add_typer(sync_app, name="sync")


def _print_json(payload: Any) -> None:
    typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _service(*, root: Path | None = None) -> TrackerService:
    # ``root`` lets the sync commands pin the exact project root once and pass
    # the same value into the transport, so every gate judges one project.
    if root is not None:
        return TrackerService(root)
    return TrackerService(require_repo_root())


def _ownership_modes() -> tuple[str, ...]:
    return (
        "external_authoritative",
        "spec_kitty_authoritative",
        "split_ownership",
    )


# ---------------------------------------------------------------------------
# Shared CLI error boundary (#4233)
# ---------------------------------------------------------------------------


def _render_cli_error(exc: BaseException, *, json_mode: bool) -> None:
    """Render a caught service error as a clean CLI failure (#4233).

    Human path: one red line on stderr — the error message, plus any structured
    code/status the exception carries — never a traceback, never internal module
    paths. JSON path: the same failure additionally emitted as a
    machine-readable object on stdout, so ``--json`` consumers always get
    parseable output. Failures are never converted into successful empty
    results: the caller exits nonzero via ``Exit(1)``.
    """
    message = str(exc)
    error_code = getattr(exc, "error_code", None)
    status_code = getattr(exc, "status_code", None)

    context_parts = []
    if error_code:
        context_parts.append(f"error_code={error_code}")
    if status_code is not None:
        context_parts.append(f"http={status_code}")
    context = f" [{', '.join(context_parts)}]" if context_parts else ""
    typer.secho(f"{message}{context}", fg=typer.colors.RED, err=True)

    if json_mode:
        payload: dict[str, Any] = {"ok": False, "error": message}
        if error_code is not None:
            payload["error_code"] = error_code
        if status_code is not None:
            payload["http_status"] = status_code
        _print_json(payload)


def _run_or_exit(fn, *, json_mode: bool = False):  # type: ignore[no-untyped-def]
    """Run ``fn`` and render any RuntimeError/ValueError failure cleanly.

    The single error boundary every tracker command routes through (#4233):
    ``TrackerServiceError`` is a ``RuntimeError`` subclass, so it renders as a
    one-line error + ``Exit(1)`` — no uncaught traceback, no internal module
    paths. ``json_mode`` additionally emits a machine-readable failure object on
    stdout for commands invoked with ``--json``.
    """
    try:
        return fn()
    except (RuntimeError, ValueError) as exc:
        _render_cli_error(exc, json_mode=json_mode)
        raise typer.Exit(1) from exc


# ---------------------------------------------------------------------------
# providers
# ---------------------------------------------------------------------------


@app.command("providers")
def providers_command(
    as_json: bool = typer.Option(False, "--json", help="Render provider list as JSON"),
) -> None:
    """List supported tracker providers.

    Local providers use direct connectors with locally stored credentials. The
    former SaaS/hosted providers (linear, jira, github, gitlab) are no longer
    supported (#6164) and are listed only to explain the refusal a bind for one
    of them produces.

    This command is purely informational and prints the hard-coded provider
    categories.
    """

    def _run() -> None:
        local = sorted(LOCAL_PROVIDERS)
        removed = sorted(REMOVED_PROVIDERS)

        if as_json:
            _print_json({"local": local, "removed": removed})
            return

        typer.echo("Supported providers:")
        typer.echo("")
        typer.echo("  Local (direct connectors, credentials stored locally):")
        for p in local:
            typer.echo(f"    - {p}")
        typer.echo("")
        typer.echo("  Removed (no longer supported):")
        for p in removed:
            typer.echo(f"    - {p}")

    _run_or_exit(_run)


# ---------------------------------------------------------------------------
# bind
# ---------------------------------------------------------------------------


@app.command("bind")
def bind_command(
    provider: str = typer.Option(
        ...,
        "--provider",
        help="Provider name (beads, fp)",
    ),
    workspace: str | None = typer.Option(
        None,
        "--workspace",
        help="Provider workspace/team/project identifier",
    ),
    ownership_mode: str | None = typer.Option(
        None,
        "--ownership-mode",
        help="Ownership mode: external_authoritative | spec_kitty_authoritative | split_ownership",
    ),
    field_owners: list[str] = typer.Option(
        [],
        "--field-owner",
        help="Split ownership mapping: field=owner",
    ),
    credentials: list[str] = typer.Option(
        [],
        "--credential",
        help="Provider credential key/value: key=value",
    ),
) -> None:
    """Bind the current project to a local issue tracker (beads, fp).

    Requires --provider and --workspace; --credential supplies connector
    credentials stored locally.
    """

    def _run() -> None:
        provider_normalized = normalize_provider(provider)

        # Removed providers (includes the former SaaS/hosted providers, #6164).
        if provider_normalized in REMOVED_PROVIDERS:
            typer.secho(
                f"Error: Provider '{provider_normalized}' is no longer supported.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)

        # Local providers
        if provider_normalized in LOCAL_PROVIDERS:
            if not workspace:
                typer.secho(
                    "Error: --workspace is required for local providers.",
                    fg=typer.colors.RED,
                    err=True,
                )
                raise typer.Exit(code=1)

            selected_mode = ownership_mode or "external_authoritative"
            mode = selected_mode.strip().lower()
            if mode not in set(_ownership_modes()):
                raise TrackerServiceError(f"Invalid ownership mode '{selected_mode}'. Expected one of: {', '.join(_ownership_modes())}")

            parsed_field_owners = parse_kv_pairs(field_owners)
            parsed_credentials = parse_kv_pairs(credentials)

            config = _service().bind(
                provider=provider_normalized,
                workspace=workspace,
                ownership_mode=mode,
                ownership_field_owners=parsed_field_owners,
                credentials=parsed_credentials,
            )

            typer.echo("Tracker binding saved")
            typer.echo(f"- provider: {config.provider}")
            typer.echo(f"- workspace: {config.workspace}")
            typer.echo(f"- ownership_mode: {config.ownership_mode}")
            typer.echo(f"- field_owners: {len(config.ownership_field_owners)}")
            typer.echo(f"- credentials_saved: {'yes' if bool(parsed_credentials) else 'no'}")
            return

        # Unknown provider
        raise TrackerServiceError(f"Unknown provider '{provider_normalized}'. Supported: {', '.join(sorted(LOCAL_PROVIDERS))}")

    _run_or_exit(_run)


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


@app.command("status")
def status_command(
    as_json: bool = typer.Option(False, "--json", help="Render status as JSON"),
) -> None:
    """Show tracker binding and sync status.

    Displays local cache statistics and configuration for the bound local
    provider.
    """

    def _run() -> None:
        payload = _service().status()

        if as_json:
            _print_json(payload)
            return

        if payload.get("inert"):
            typer.echo(f"Tracker {payload['message']}")
            return

        if not payload.get("configured"):
            typer.echo("Tracker is not configured")
            return

        typer.echo("Tracker status")
        typer.echo(f"- provider: {payload.get('provider')}")
        typer.echo(f"- workspace: {payload.get('workspace')}")
        typer.echo(f"- ownership_mode: {payload.get('ownership_mode')}")
        typer.echo(f"- db_path: {payload.get('db_path')}")
        typer.echo(f"- issue_count: {payload.get('issue_count')}")
        typer.echo(f"- mapping_count: {payload.get('mapping_count')}")
        typer.echo(f"- credentials_present: {'yes' if payload.get('credentials_present') else 'no'}")

    _run_or_exit(_run, json_mode=as_json)


# ---------------------------------------------------------------------------
# map add
# ---------------------------------------------------------------------------


@map_app.command("add")
def map_add_command(
    wp_id: str = typer.Option(..., "--wp-id", help="Work package ID (e.g., WP01)"),
    external_id: str = typer.Option(..., "--external-id", help="External issue ID"),
    external_key: str | None = typer.Option(None, "--external-key", help="External issue key"),
    external_url: str | None = typer.Option(None, "--external-url", help="External issue URL"),
) -> None:
    """Add or update a WP-to-external issue mapping.

    Stores the mapping in the local SQLite database.
    """

    def _run() -> None:
        _service().map_add(
            wp_id=wp_id,
            external_id=external_id,
            external_key=external_key,
            external_url=external_url,
        )
        typer.echo(f"Mapping saved: {wp_id} -> {external_id}")

    _run_or_exit(_run)


# ---------------------------------------------------------------------------
# map list
# ---------------------------------------------------------------------------


@map_app.command("list")
def map_list_command(
    as_json: bool = typer.Option(False, "--json", help="Render mappings as JSON"),
) -> None:
    """List tracker mappings from the local SQLite database."""

    def _run() -> None:
        mappings = _service().map_list()
        if as_json:
            _print_json({"mappings": mappings})
            return

        if not mappings:
            typer.echo("No mappings found")
            return

        typer.echo("Mappings")
        for row in mappings:
            key = row.get("external_key") or row.get("external_id")
            typer.echo(f"- {row.get('wp_id')}: {row.get('system')}:{key}")

    _run_or_exit(_run, json_mode=as_json)


# ---------------------------------------------------------------------------
# sync pull
# ---------------------------------------------------------------------------


@sync_app.command("pull")
def sync_pull_command(
    limit: int = typer.Option(100, "--limit", min=1, max=10000),
    as_json: bool = typer.Option(False, "--json", help="Render sync result as JSON"),
) -> None:
    """Pull tracker updates into the local cache via the direct connector."""
    root = require_repo_root()

    def _run() -> None:
        payload = _service(root=root).sync_pull(limit=limit)
        if as_json:
            _print_json(payload)
            return

        stats = payload.get("stats", {})
        typer.echo(f"Pulled from {payload.get('provider')}")
        typer.echo(f"- created: {stats.get('pulled_created', 0)}")
        typer.echo(f"- updated: {stats.get('pulled_updated', 0)}")
        typer.echo(f"- skipped: {stats.get('skipped', 0)}")
        typer.echo(f"- conflicts: {len(payload.get('conflicts', []))}")
        typer.echo(f"- errors: {len(payload.get('errors', []))}")

    _run_or_exit(_run, json_mode=as_json)


# ---------------------------------------------------------------------------
# sync push
# ---------------------------------------------------------------------------


@sync_app.command("push")
def sync_push_command(
    limit: int = typer.Option(100, "--limit", min=1, max=10000, help="Max items"),
    as_json: bool = typer.Option(False, "--json", help="Render sync result as JSON"),
) -> None:
    """Push local mutations to the upstream provider via the direct connector."""
    root = require_repo_root()

    def _run() -> None:
        payload = _service(root=root).sync_push(limit=limit)
        if as_json:
            _print_json(payload)
            return

        stats = payload.get("stats", {})
        typer.echo(f"Pushed to {payload.get('provider')}")
        typer.echo(f"- created: {stats.get('pushed_created', 0)}")
        typer.echo(f"- updated: {stats.get('pushed_updated', 0)}")
        typer.echo(f"- skipped: {stats.get('skipped', 0)}")
        typer.echo(f"- conflicts: {len(payload.get('conflicts', []))}")
        typer.echo(f"- errors: {len(payload.get('errors', []))}")

    _run_or_exit(_run, json_mode=as_json)


# ---------------------------------------------------------------------------
# sync run
# ---------------------------------------------------------------------------


@sync_app.command("run")
def sync_run_command(
    limit: int = typer.Option(100, "--limit", min=1, max=10000),
    as_json: bool = typer.Option(False, "--json", help="Render sync result as JSON"),
) -> None:
    """Run pull+push synchronization in one operation via the direct connector."""
    root = require_repo_root()

    def _run() -> None:
        payload = _service(root=root).sync_run(limit=limit)
        if as_json:
            _print_json(payload)
            return

        stats = payload.get("stats", {})
        typer.echo(f"Sync run completed ({payload.get('provider')})")
        typer.echo(f"- pulled_created: {stats.get('pulled_created', 0)}")
        typer.echo(f"- pulled_updated: {stats.get('pulled_updated', 0)}")
        typer.echo(f"- pushed_created: {stats.get('pushed_created', 0)}")
        typer.echo(f"- pushed_updated: {stats.get('pushed_updated', 0)}")
        typer.echo(f"- skipped: {stats.get('skipped', 0)}")
        typer.echo(f"- conflicts: {len(payload.get('conflicts', []))}")
        typer.echo(f"- errors: {len(payload.get('errors', []))}")

    _run_or_exit(_run, json_mode=as_json)


# ---------------------------------------------------------------------------
# sync publish
# ---------------------------------------------------------------------------


@sync_app.command("publish")
def sync_publish_command(
    as_json: bool = typer.Option(False, "--json", help="Render publish result as JSON"),
) -> None:
    """Publish local tracker snapshot.

    Local providers (beads/fp) have no snapshot-publish transport; the facade
    raises a clean error directing the operator to ``tracker sync push``.
    """
    root = require_repo_root()

    def _run() -> None:
        payload = _service(root=root).sync_publish()
        if as_json:
            _print_json(payload)
            return

        typer.echo("Snapshot publish complete")
        typer.echo(f"- endpoint: {payload.get('endpoint')}")
        typer.echo(f"- status_code: {payload.get('status_code')}")
        typer.echo(f"- ok: {'yes' if payload.get('ok') else 'no'}")

    _run_or_exit(_run, json_mode=as_json)


# ---------------------------------------------------------------------------
# unbind
# ---------------------------------------------------------------------------


@app.command("unbind")
def unbind_command() -> None:
    """Remove tracker binding for this project."""

    def _run() -> None:
        _service().unbind()
        typer.echo("Tracker binding removed")

    _run_or_exit(_run)
