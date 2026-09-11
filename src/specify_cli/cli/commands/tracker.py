"""Tracker commands for provider bindings, mappings, and sync operations.

Dispatches to SaaS-backed providers (linear, jira, github, gitlab) via the
Spec Kitty SaaS control plane, or to local providers (beads, fp) via
direct connectors.  Provider credentials are never accepted for SaaS-backed
providers -- authentication flows through ``spec-kitty auth login``.
"""

from __future__ import annotations

from contextlib import suppress
import json
from pathlib import Path
from collections.abc import Mapping
from typing import Any

import typer
from rich.console import Console
from specify_cli.cli.console import console
from rich.table import Table

from specify_cli.cli.commands._teamspace_mission_state_gate import (
    enforce_teamspace_mission_state_ready,
)
from specify_cli.mission_metadata import load_meta
from specify_cli.tracker.config import (
    LOCAL_PROVIDERS,
    REMOVED_PROVIDERS,
    SAAS_PROVIDERS,
    TrackerProjectConfig,
    load_tracker_config,
    require_repo_root,
    _warn_legacy_ownership_key_once,
)
from specify_cli.identity.project import ensure_identity
from specify_cli.core.saas_sync_config import is_saas_sync_enabled, saas_sync_disabled_message
from specify_cli.tracker.discovery import BindResult, ResolutionResult
from specify_cli.tracker.saas_readiness import evaluate_readiness
from specify_cli.tracker.egress_verdict import EgressDestination, tracker_egress_verdict
from specify_cli.tracker.factory import normalize_provider
from specify_cli.tracker.saas_client import TRACKER_EGRESS_IDENTIFIER_KINDS, TrackerEgressRefusedError
from specify_cli.tracker.service import TrackerService, TrackerServiceError, parse_kv_pairs

app = typer.Typer(
    help=(
        "Task tracker integration commands.\n\n"
        "SaaS-backed providers (linear, jira, github, gitlab) route through "
        "the Spec Kitty SaaS control plane.  Local providers (beads, fp) use "
        "direct connectors."
    )
)
map_app = typer.Typer(help="Work-package mapping commands")
sync_app = typer.Typer(help="Tracker synchronization commands")
app.add_typer(map_app, name="map")
app.add_typer(sync_app, name="sync")

# ---------------------------------------------------------------------------
# Stable wording constants (asserted byte-for-byte by tests)
# ---------------------------------------------------------------------------


def _print_json(payload: Any) -> None:
    typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))

def _echo_saas_sync_summary(label: str, payload: Mapping[str, Any]) -> None:
    """Render the SaaS sync envelope shared by ``sync pull``/``push``/``run``.

    Status line, the authority used (``identity_path``, #1221), then the
    ``summary`` counters. One helper so the three commands cannot drift again.
    """
    summary = payload.get("summary", {})
    typer.echo(f"{label} {payload.get('status', 'complete')}")
    if payload.get("identity_path"):
        ip = payload["identity_path"]
        typer.echo(f"- provider: {ip.get('provider', 'unknown')}")
        typer.echo(f"- type: {ip.get('type', 'unknown')}")
    typer.echo(f"- total: {summary.get('total', 0)}")
    typer.echo(f"- succeeded: {summary.get('succeeded', 0)}")
    typer.echo(f"- failed: {summary.get('failed', 0)}")
    typer.echo(f"- skipped: {summary.get('skipped', 0)}")



def _print_ticket_rows(rows: list[dict[str, Any]]) -> None:
    if not rows:
        typer.echo("No tickets found")
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Identifier", style="bold")
    table.add_column("Title")
    table.add_column("State")

    for row in rows:
        state = row.get("state") if isinstance(row.get("state"), dict) else {}
        table.add_row(
            str(row.get("identifier") or ""),
            str(row.get("title") or ""),
            str(state.get("name") or ""),
        )

    console.print(table)


def _resolve_active_feature_slug(repo_root: Path) -> str | None:
    """Return the active feature slug from .kittify/meta.json, or None.

    Used by _check_readiness to supply a feature_slug when
    require_mission_binding=True.  A missing or unreadable meta.json is
    treated as "no active feature" — the readiness evaluator handles
    MISSING_MISSION_BINDING gracefully in that case.
    """
    data = load_meta(repo_root / ".kittify", on_malformed="none")
    if data is None:
        return None
    slug = data.get("feature_slug") or data.get("slug")
    return str(slug) if slug else None


def _resolve_output_policy_for_tracker() -> str:
    """Return the active coordinator OutputPolicy value for tracker rendering.

    Mission ``tracker-readiness-alignment-01KS7PZ7`` (WS5, issue #18): route
    hosted tracker readiness output through the same suppression buckets as
    the rest of the CLI.

    Strategy:
    1. Try the cached ``ReadinessResult`` on ``ctx.obj`` first via the central
       coordinator's ``get_readiness``. When the coordinator has run (it runs
       once per CLI invocation from the root callback) this gives us the
       authoritative bucket without re-deriving from argv.
    2. When no Click/Typer context is reachable (defensive — direct test
       invocation of ``_check_readiness`` outside a CLI run), fall back to
       deriving the policy from ``sys.argv`` via the coordinator's helper.

    Lazy-imports the coordinator to avoid an import cycle with
    ``specify_cli.tracker.saas_readiness``.
    """
    import click  # noqa: PLC0415 — keep coordinator import-time cheap
    from specify_cli.readiness.coordinator import (  # noqa: PLC0415
        OutputPolicy,
        _derive_output_policy,
        get_readiness,
    )

    try:
        click_ctx = click.get_current_context(silent=True)
    except Exception:  # noqa: BLE001 — defensive: never raise out of the readiness renderer
        click_ctx = None

    if click_ctx is not None:
        try:
            readiness = get_readiness(click_ctx)  # type: ignore[arg-type]
            if readiness.ran:
                return readiness.output_policy.value
        except Exception:  # noqa: BLE001
            pass

    # Fallback: derive from argv directly. This is the same logic the
    # coordinator uses on its enabled path; consulting it here keeps tracker
    # output buckets aligned with coordinator output buckets even when ctx is
    # unreachable.
    try:
        return _derive_output_policy().value
    except Exception:  # noqa: BLE001
        return OutputPolicy.INTERACTIVE.value


def _render_readiness_failure(result: Any) -> None:
    """Render a non-READY ``ReadinessResult`` per the active OutputPolicy.

    Mission ``tracker-readiness-alignment-01KS7PZ7`` (WS5, issue #18) AC#5/6:
    suppression rules from the central coordinator apply to hosted tracker
    readiness output too.

    - ``INTERACTIVE`` → existing 2-line human format (message + next_action).
    - ``MACHINE_OUTPUT`` (``--json`` / ``--quiet``) → single stderr line carrying
      the remediation only (or the message if no remediation is present).
      Stdout is untouched so the caller's JSON / quiet contract is preserved.
    - ``NON_INTERACTIVE`` (help / version / CI / non-TTY) → single stable
      machine-parseable line ``spec-kitty tracker: readiness=<state>
      next=spec-kitty-auth-login`` for the MISSING_AUTH state; for other states
      we slugify the remediation phrase.

    Always exits with ``typer.Exit(1)`` after writing.
    """
    policy = _resolve_output_policy_for_tracker()
    state_value = getattr(getattr(result, "state", None), "value", None) or "unknown"
    next_action = getattr(result, "next_action", None) or ""
    message = getattr(result, "message", None) or ""

    if policy == "interactive":
        # Existing 2-line human format — preserved verbatim for backward compat.
        typer.secho(message, fg=typer.colors.RED, err=True)
        if next_action:
            typer.echo(next_action, err=True)
        raise typer.Exit(1)

    if policy == "machine_output":
        # Stdout untouched. Single stderr line, plain (no colour) so JSON
        # callers piping stderr don't get ANSI escapes.
        if next_action:
            typer.echo(next_action, err=True)
        else:
            typer.echo(message, err=True)
        raise typer.Exit(1)

    # NON_INTERACTIVE: stable single-line machine-readable format.
    if state_value == "missing_auth":
        next_token = "spec-kitty-auth-login"  # noqa: S105 - command token, not a secret.
    else:
        # Deterministic slug from the remediation phrase; fallback to "unknown".
        next_token = "-".join(tok.strip("`.,").lower() for tok in next_action.split() if tok.strip("`.,")) or "unknown"
    typer.echo(
        f"spec-kitty tracker: readiness={state_value} next={next_token}",
        err=True,
    )
    raise typer.Exit(1)


def _check_readiness(
    *,
    require_mission_binding: bool,
    probe_reachability: bool,
) -> None:
    """Check hosted readiness; raise typer.Exit(1) with actionable message on failure.

    Calls evaluate_readiness with the supplied flags and the current repo root.
    On non-READY results, the renderer (``_render_readiness_failure``) consults
    the central coordinator's ``OutputPolicy`` so suppression buckets stay
    aligned with the rest of the CLI (see issue #18, mission
    ``tracker-readiness-alignment-01KS7PZ7``).
    """
    if require_mission_binding:
        try:
            repo_root = require_repo_root()
        except Exception as exc:  # noqa: BLE001 — repo-root resolution failure is reported to stderr then converted to Exit(1)
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(1) from exc
    else:
        try:
            repo_root = require_repo_root()
        except Exception:
            repo_root = Path.cwd()

    enforce_teamspace_mission_state_ready(
        console=console,
        command_name="spec-kitty tracker",
    )

    feature_slug = _resolve_active_feature_slug(repo_root)
    result = evaluate_readiness(
        repo_root=repo_root,
        feature_slug=feature_slug,
        require_mission_binding=require_mission_binding,
        probe_reachability=probe_reachability,
    )
    if not result.is_ready:
        _render_readiness_failure(result)


def _is_local_binding() -> bool:
    """Return True iff the current repo has a bound *local* tracker provider.

    Used to short-circuit readiness and daemon-policy checks for commands
    whose local-provider code path does not touch the SaaS surface.  Returns
    ``False`` when no binding is configured, when the binding is SaaS-backed,
    or when config loading fails for any reason — in all those cases callers
    fall through to the full SaaS readiness chain, which is the safer default.
    """
    with suppress(Exception):
        config = load_tracker_config(require_repo_root())
        if config.provider and normalize_provider(config.provider) in LOCAL_PROVIDERS:
            return True
    return False


def _check_sync_readiness(*, root: Path | None = None) -> None:
    """Provider-aware readiness gate for sync subcommands.

    Local providers (beads, fp) reach the sync command without going through
    the SaaS *readiness* surface: no auth token, no ``SPEC_KITTY_SAAS_URL``,
    no reachability probe, no background daemon.  Their direct connectors handle
    connectivity errors on their own.  For those bindings this helper is a
    no-op — the rollout gate is already enforced by :func:`tracker_callback`
    and the binding itself is the proof that setup is complete.

    ``LocalTrackerService.sync_pull``/``sync_push``/``sync_run`` each
    consult ``tracker_egress_verdict`` as the first executable statement of
    their body (local subprocess spawns gate on the committed
    ``tracker.egress`` key; hosted sends ride the authenticated session).
    "No auth token, no reachability probe" still holds — nothing here calls
    the SaaS HTTP client. (The former hosted-sync consent channel retired
    with the sync transport, issue #5.)

    **HIGH-1 fix (2026-08-10):** for a SaaS-backed binding, the hosted egress
    verdict is now consulted *here*, before ``_check_readiness`` is ever
    called. Previously this function's first act on the hosted path was
    ``_check_readiness(..., probe_reachability=True)``, which -- when auth
    and host-config both resolve -- issues a real ``urllib.request.urlopen``
    HEAD probe to the configured SaaS host (``saas/readiness.py:_probe_reachability``)
    *before* ``SaaSTrackerClient._request``'s own Channel-1/Channel-2 gate ever
    ran. A project whose hosted-sync consent is absent or refused therefore
    still emitted one HTTP HEAD to the tracker host ahead of the eventual
    refusal, violating "refusal precedes any HTTP attempt." Refusing here,
    with the exact ``tracker_egress_verdict``/``TrackerEgressRefusedError``
    pairing ``SaaSTrackerClient._request`` already uses, keeps the message
    byte-identical to the transport-layer refusal while moving it ahead of
    the network probe. A permitted verdict changes nothing: execution falls
    through to the readiness probe exactly as before.

    SaaS-backed (or unknown/unconfigured) bindings get the full readiness
    chain plus the ``tracker_egress_verdict`` gate above.

    **Pass ``root`` so the pre-flight gate judges the same project the transport
    will.** ``SaaSTrackerClient._request`` resolves its own ``project_root``
    from the ``TrackerService`` the command builds (``_service`` →
    ``require_repo_root()``). If this pre-flight resolved ``require_repo_root()``
    independently, the two hosted gates could -- for a caller whose cwd is not
    the data-owning root -- answer for two different projects. The sync commands
    resolve the root once and thread the same value into both this gate and
    ``_service(root=...)``, so a single resolution decides both. Absent ``root``
    (direct callers) this falls back to ``require_repo_root()`` unchanged.
    """
    if _is_local_binding():
        return

    verdict = tracker_egress_verdict(
        root if root is not None else require_repo_root(),
        destination=EgressDestination.HOSTED_SERVICE,
        identifiers=TRACKER_EGRESS_IDENTIFIER_KINDS,
    )
    if verdict.refused:
        exc = TrackerEgressRefusedError(verdict.message)
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc

    _check_readiness(require_mission_binding=True, probe_reachability=True)


def _check_binding_readiness(*, probe_reachability: bool = False) -> None:
    """Provider-aware readiness gate for non-sync commands that act on a binding.

    Mirrors :func:`_check_sync_readiness` without its ``tracker_egress_verdict``
    gate: used by ``status``, ``map add``, ``map list``, and ``unbind`` which
    require a binding to operate on but never construct a connector or run a
    subprocess.

    **Does not inherit :func:`_check_sync_readiness`'s corrected note about
    ``tracker_egress_verdict`` and Channel 1 (#3108).** The commands this
    helper gates construct no connector and run no subprocess -- ``status``
    reaches ``load_tracker_config`` directly, and ``map add``/``map list``/
    ``unbind`` are deliberately left ungated by the tracker-egress verdict
    (only ``sync_pull``/``sync_push``/``sync_run`` consult it) -- so nothing
    reachable through this helper touches the hosted-sync consent chain at
    all, and the mirroring stops there.
    """
    if _is_local_binding():
        return
    _check_readiness(require_mission_binding=True, probe_reachability=probe_reachability)


def _service(*, allow_unbound: bool = False, root: Path | None = None) -> TrackerService:
    # ``root`` lets a caller pin the exact project root (see _check_sync_readiness):
    # the sync commands resolve the root once and pass the same value to both the
    # egress pre-flight and the transport, so the two hosted gates cannot answer
    # for different projects.
    if root is not None:
        return TrackerService(root)
    if allow_unbound:
        try:
            repo_root = require_repo_root()
        except Exception:
            repo_root = Path.cwd()
    else:
        repo_root = require_repo_root()
    return TrackerService(repo_root)


def _doctrine_modes() -> tuple[str, ...]:
    return (
        "external_authoritative",
        "spec_kitty_authoritative",
        "split_ownership",
    )


def _run_or_exit(fn):  # type: ignore[no-untyped-def]
    try:
        return fn()
    except (RuntimeError, ValueError) as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc


@app.callback()
def tracker_callback() -> None:
    """Rollout gate for tracker commands.

    Registration in cli/commands/__init__.py is unconditional, so this
    callback is the sole gate: it checks env-var state at invocation time
    and blocks every tracker command when the rollout flag is off.
    Per-command readiness checks handle all prerequisite validation beyond
    the rollout gate.
    """
    if not is_saas_sync_enabled():
        typer.secho(saas_sync_disabled_message(), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


def issue_search_command(
    provider: str = typer.Option(..., "--provider", help="Tracker provider slug"),
    query: str = typer.Option(..., "--query", help="Issue identifier or search text"),
    as_json: bool = typer.Option(False, "--json", help="Render tickets as a JSON array"),
) -> None:
    """Search external tracker issues via the hosted read path."""
    if not is_saas_sync_enabled():
        typer.secho(saas_sync_disabled_message(), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    _check_readiness(require_mission_binding=False, probe_reachability=False)

    def _run() -> None:
        rows = _service(allow_unbound=True).issue_search(provider=provider, query=query)
        if as_json:
            _print_json(rows)
            return
        _print_ticket_rows(rows)

    _run_or_exit(_run)


# ---------------------------------------------------------------------------
# providers
# ---------------------------------------------------------------------------


@app.command("providers")
def providers_command(
    as_json: bool = typer.Option(False, "--json", help="Render provider list as JSON"),
) -> None:
    """List supported tracker providers, categorized by backend type.

    SaaS-backed providers authenticate through ``spec-kitty auth login`` and
    route sync operations through the Spec Kitty SaaS control plane.

    Local providers use direct connectors with locally stored credentials.

    This command is purely informational and prints the hard-coded provider
    categories.  It does **not** consult hosted readiness — ``tracker_callback``
    is the sole rollout gate for the tracker Typer app, which is all the
    gating this static output needs.
    """

    def _run() -> None:
        saas = sorted(SAAS_PROVIDERS)
        local = sorted(LOCAL_PROVIDERS)

        if as_json:
            _print_json({"saas": saas, "local": local})
            return

        typer.echo("Supported providers:")
        typer.echo("")
        typer.echo("  SaaS-backed (authenticate via spec-kitty auth login):")
        for p in saas:
            typer.echo(f"    - {p}")
        typer.echo("")
        typer.echo("  Local (direct connectors, credentials stored locally):")
        for p in local:
            typer.echo(f"    - {p}")

    _run_or_exit(_run)


# ---------------------------------------------------------------------------
# discover
# ---------------------------------------------------------------------------


@app.command("discover")
def discover_command(
    provider: str = typer.Option(..., "--provider", help="Provider name"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Discover bindable tracker resources under your installation.

    Lists all resources (projects, teams, boards) available for binding
    with the specified provider.  Each row is numbered 1-indexed to align
    with ``tracker bind --select N``.

    ``discover`` is explicitly the *pre-binding* command — it is how users
    find something to bind to — so it MUST NOT require an existing mission
    binding.  Requiring a binding here would make fresh bind flows
    impossible.
    """
    _check_readiness(require_mission_binding=False, probe_reachability=False)
    normalized = normalize_provider(provider)

    # Route the service call through the shared ``_run_or_exit`` helper, which
    # catches the ``RuntimeError`` family (both ``TrackerServiceError`` and its
    # sibling ``SaaSTrackerClientError`` derive from ``RuntimeError``). Every
    # other tracker command already renders errors this way; ``discover`` alone
    # hand-rolled a narrow ``except TrackerServiceError`` that let a SaaS non-2xx
    # (``SaaSTrackerClientError`` on 403/404/429/5xx) escape as an uncaught
    # exception, leaking a raw Rich traceback with internal module paths
    # (issue #4233). Reusing the helper closes the class rather than enumerating
    # one sibling at a time.
    resources = _run_or_exit(lambda: _service().discover(provider=normalized))

    if not resources:
        typer.echo(f"No bindable resources found for provider '{normalized}'.")
        typer.echo("Verify the tracker is connected in the SaaS dashboard.")
        raise typer.Exit(0)

    if json_output:
        # Full payload, no truncation — all BindableResource fields included
        output = [
            {
                "number": idx + 1,
                "candidate_token": r.candidate_token,
                "display_label": r.display_label,
                "provider": r.provider,
                "provider_context": r.provider_context,
                "binding_ref": r.binding_ref,
                "bound_project_slug": r.bound_project_slug,
                "bound_at": r.bound_at,
                "is_bound": r.is_bound,
            }
            for idx, r in enumerate(resources)
        ]
        typer.echo(json.dumps(output, indent=2, default=str))
        return

    # Rich table output — numbered rows for alignment with --select N.
    # Numbering is 1-indexed: discover row N corresponds to --select N
    # because discover lists resources in host-returned order and
    # --select N maps to the Nth item (1-based).
    table = Table(title="Bindable Resources")
    table.add_column("#", justify="right", style="cyan", no_wrap=True)
    table.add_column("Resource", style="bold")
    table.add_column("Provider")
    table.add_column("Workspace")
    table.add_column("Status")

    for idx, r in enumerate(resources):
        status = "bound" if r.is_bound else "available"
        table.add_row(
            str(idx + 1),
            r.display_label,
            r.provider,
            r.provider_context.get("workspace_name", ""),
            status,
        )

    console.print(table)


# ---------------------------------------------------------------------------
# bind
# ---------------------------------------------------------------------------


@app.command("bind")
def bind_command(
    provider: str = typer.Option(
        ...,
        "--provider",
        help="Provider name (linear, jira, github, gitlab, beads, fp)",
    ),
    bind_ref: str | None = typer.Option(
        None,
        "--bind-ref",
        help="Binding reference for CI/automation (validates against host)",
    ),
    select: int | None = typer.Option(
        None,
        "--select",
        help="Auto-select candidate by number (non-interactive)",
    ),
    workspace: str | None = typer.Option(
        None,
        "--workspace",
        help="Provider workspace/team/project identifier (local providers only)",
    ),
    ownership_mode: str | None = typer.Option(
        None,
        "--ownership-mode",
        help="Ownership mode: external_authoritative | spec_kitty_authoritative | split_ownership",
    ),
    doctrine_mode: str | None = typer.Option(
        None,
        "--doctrine-mode",
        help="Deprecated alias for --ownership-mode",
        hidden=True,
    ),
    field_owners: list[str] = typer.Option(
        [],
        "--field-owner",
        help="Split ownership mapping: field=owner (local providers only)",
    ),
    credentials: list[str] = typer.Option(
        [],
        "--credential",
        help="Provider credential key/value: key=value (local providers only)",
    ),
) -> None:
    """Bind the current project to an issue tracker.

    For SaaS-backed providers (linear, jira, github, gitlab):
      Uses discovery to find bindable resources automatically.
      Use --bind-ref for CI/automation, --select N for non-interactive.
      Authentication via ``spec-kitty auth login``.

    For local providers (beads, fp):
      Requires --provider, --workspace, and --credential flags.
    """
    # HIGH-3 fix (#3174, 2026-08-10): a local-provider bind must not require hosted
    # readiness. `bind` creates the binding, so `_is_local_binding()` (which reads an
    # *existing* config) cannot be used here -- gate on the `--provider` argument itself
    # instead, mirroring how the sync commands skip readiness for an already-local binding.
    # SaaS providers (and removed/unknown provider strings, which `_run` rejects on their
    # own terms below) keep the existing hosted readiness check.
    if normalize_provider(provider) not in LOCAL_PROVIDERS:
        _check_readiness(require_mission_binding=False, probe_reachability=False)

    def _run() -> None:
        provider_normalized = normalize_provider(provider)

        # FR-013: Removed providers
        if provider_normalized in REMOVED_PROVIDERS:
            typer.secho(
                f"Error: Provider '{provider_normalized}' is no longer supported.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)

        # SaaS-backed providers
        if provider_normalized in SAAS_PROVIDERS:
            # FR-010: Hard-fail --credential for SaaS
            if credentials:
                typer.secho(
                    f"Error: Direct provider credentials are no longer supported for {provider_normalized}.\n"
                    "Run `spec-kitty auth login` to authenticate.\n"
                    "Then connect your provider in the Spec Kitty dashboard.",
                    fg=typer.colors.RED,
                    err=True,
                )
                raise typer.Exit(code=1)

            cancelled = _bind_saas(provider_normalized, bind_ref=bind_ref, select_n=select)
            if cancelled:
                typer.echo("Bind cancelled.")
            return

        # Local providers
        if provider_normalized in LOCAL_PROVIDERS:
            if not workspace:
                typer.secho(
                    "Error: --workspace is required for local providers.",
                    fg=typer.colors.RED,
                    err=True,
                )
                raise typer.Exit(code=1)

            selected_mode = ownership_mode or doctrine_mode or "external_authoritative"
            if doctrine_mode is not None and ownership_mode is None:
                _warn_legacy_ownership_key_once()

            mode = selected_mode.strip().lower()
            if mode not in set(_doctrine_modes()):
                raise TrackerServiceError(f"Invalid ownership mode '{selected_mode}'. Expected one of: {', '.join(_doctrine_modes())}")

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
        raise TrackerServiceError(f"Unknown provider '{provider_normalized}'. Supported: {', '.join(sorted(SAAS_PROVIDERS | LOCAL_PROVIDERS))}")

    _run_or_exit(_run)


def _bind_saas(
    provider: str,
    *,
    bind_ref: str | None,
    select_n: int | None,
) -> bool:
    """Execute the SaaS discovery-bind flow.

    Handles: re-bind confirmation, project identity derivation,
    interactive candidate selection, --bind-ref validation, and
    --select N auto-selection.

    Returns ``True`` if the user cancelled re-bind, ``False`` otherwise.
    Raises ``TrackerServiceError`` on failures (caught by ``_run_or_exit``).
    Raises ``typer.Exit(1)`` for user input errors.
    """
    repo_root = require_repo_root()

    # Re-bind confirmation (skip for non-interactive modes)
    if bind_ref is None and select_n is None:
        existing = load_tracker_config(repo_root)
        if existing.is_configured and existing.provider in SAAS_PROVIDERS:
            label = existing.display_label or existing.binding_ref or existing.project_slug
            console.print(f"[yellow]Warning:[/yellow] Existing binding: {label}")
            confirm = input("Replace existing binding? (y/N): ")
            if confirm.strip().lower() != "y":
                return True

    # Derive project identity.
    # WRITE-AUTHORIZED BOUNDARY (#2263, FR-003 / AS-5): `tracker bind` is an explicit,
    # user-initiated bind command, so persisting a completed identity to
    # .kittify/config.yaml here is allowed. Do NOT swap to resolve_identity — that
    # would silently turn an intentional persist into a no-op.
    identity = ensure_identity(repo_root)
    project_identity = {
        "uuid": str(identity.project_uuid),
        "slug": identity.project_slug,
        "node_id": identity.node_id,
        "repo_slug": identity.repo_slug,
        "build_id": identity.build_id,
    }

    # Dispatch to facade (TrackerServiceError propagates to _run_or_exit)
    result = _service().bind(
        provider=provider,
        project_identity=project_identity,
        bind_ref=bind_ref,
        select_n=select_n,
    )

    # Handle bind success (auto-bind, --bind-ref, or --select N)
    if isinstance(result, BindResult | TrackerProjectConfig):
        _display_bind_success(result, provider)
        return False

    # Handle ResolutionResult with candidates (interactive selection needed)
    if isinstance(result, ResolutionResult) and result.candidates:
        _handle_candidate_selection(console, result, provider, project_identity)
        return False

    # No candidates (should not reach here -- service raises on no-match)
    raise TrackerServiceError(f"No bindable resources found for provider '{provider}'.")


def _display_bind_success(
    result: BindResult | TrackerProjectConfig,
    provider: str,
) -> None:
    """Display success output after binding."""
    provider_name = result.provider or provider
    binding_ref = result.binding_ref or result.project_slug or "unknown"
    display_label = result.display_label or result.project_slug or binding_ref

    typer.echo("Tracker binding saved")
    typer.echo(f"- provider: {provider_name}")
    typer.echo(f"- binding_ref: {binding_ref}")
    typer.echo(f"- display_label: {display_label}")


def _handle_candidate_selection(
    console: Console,
    resolution: ResolutionResult,
    provider: str,
    project_identity: dict[str, Any],
) -> None:
    """Display candidates and get interactive user selection."""
    console.print(f"\nMultiple resources found for provider '{provider}':\n")
    for candidate in resolution.candidates:
        num = candidate.sort_position + 1
        console.print(f"  {num}. {candidate.display_label} ({candidate.confidence} confidence)")
        console.print(f"     Reason: {candidate.match_reason}")

    console.print()
    choice = input(f"Select resource (1-{len(resolution.candidates)}): ")
    try:
        select_n = int(choice.strip())
    except ValueError:
        raise TrackerServiceError("Invalid selection.") from None

    # Call bind again with the selected candidate
    final = _service().bind(
        provider=provider,
        project_identity=project_identity,
        select_n=select_n,
    )

    if isinstance(final, BindResult):
        _display_bind_success(final, provider)
    else:
        raise TrackerServiceError("Unexpected result from bind operation.")


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


@app.command("status")
def status_command(
    all_installations: bool = typer.Option(False, "--all", help="Show installation-wide status (SaaS providers only)"),
    as_json: bool = typer.Option(False, "--json", help="Render status as JSON"),
) -> None:
    """Show tracker binding and sync status.

    For SaaS-backed providers: displays identity path, sync state, and
    provider info from the SaaS control plane.

    For local providers: displays local cache statistics and configuration.

    With --all: shows installation-wide summary across all bindings
    (SaaS providers only).
    """
    _check_binding_readiness(probe_reachability=False)

    def _run() -> None:
        payload = _service().status(all=all_installations)

        if as_json:
            _print_json(payload)
            return

        # Installation-wide output uses Rich for distinct formatting
        if all_installations:
            _print_installation_wide_status(payload)
            return

        if not payload.get("configured"):
            typer.echo("Tracker is not configured")
            return

        typer.echo("Tracker status")
        typer.echo(f"- provider: {payload.get('provider')}")

        # SaaS-specific fields
        if payload.get("identity_path"):
            ip = payload["identity_path"]
            typer.echo(f"- type: {ip.get('type', 'unknown')}")
            typer.echo(f"- sync_state: {payload.get('sync_state', 'unknown')}")
        # Local-specific fields
        else:
            typer.echo(f"- workspace: {payload.get('workspace')}")
            typer.echo(f"- doctrine_mode: {payload.get('doctrine_mode')}")
            typer.echo(f"- db_path: {payload.get('db_path')}")
            typer.echo(f"- issue_count: {payload.get('issue_count')}")
            typer.echo(f"- mapping_count: {payload.get('mapping_count')}")
            typer.echo(f"- credentials_present: {'yes' if payload.get('credentials_present') else 'no'}")

    _run_or_exit(_run)


def _print_installation_wide_status(payload: dict) -> None:
    """Render installation-wide tracker status using Rich for visual distinction."""
    from rich.panel import Panel
    from rich.table import Table

    provider = payload.get("provider", "unknown")
    connected = payload.get("connected", payload.get("status", "unknown"))
    bindings = payload.get("bindings")

    if isinstance(bindings, list):
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Project", style="bold")
        table.add_column("Provider")
        table.add_column("Status")
        table.add_column("Bound At")

        if bindings:
            for binding in bindings:
                if isinstance(binding, dict):
                    table.add_row(
                        _binding_project_label(binding),
                        str(binding.get("provider") or provider),
                        _binding_status_label(binding),
                        str(binding.get("bound_at") or "-"),
                    )
                else:
                    table.add_row(str(binding), str(provider), "unknown", "-")
        else:
            table.add_row("No bindings", str(provider), str(connected), "-")

        if "resource_count" in payload:
            table.caption = f"Connected: {connected} | Resources: {payload['resource_count']}"

        panel = Panel(table, title="Installation-wide tracker status", border_style="green")
        console.print(panel)
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Field", style="bold")
    table.add_column("Value")

    table.add_row("Provider", str(provider))
    table.add_row("Connected", str(connected))

    # Show binding/resource counts if present
    if "bindings" in payload and isinstance(bindings, int):
        table.add_row("Bindings", str(bindings))

    if "resource_count" in payload:
        table.add_row("Resources", str(payload["resource_count"]))

    # Include any additional top-level keys that aren't already covered
    _skip = {"provider", "connected", "status", "bindings", "resource_count"}
    for key, value in sorted(payload.items()):
        if key not in _skip:
            table.add_row(key, str(value))

    panel = Panel(table, title="Installation-wide tracker status", border_style="green")
    console.print(panel)


def _binding_project_label(binding: dict[str, Any]) -> str:
    """Return the most useful project identifier from a binding payload."""
    return str(
        binding.get("project_name")
        or binding.get("project_slug")
        or binding.get("project")
        or binding.get("slug")
        or binding.get("name")
        or binding.get("display_label")
        or "unknown"
    )


def _binding_status_label(binding: dict[str, Any]) -> str:
    """Return a normalized status label for installation-wide bindings."""
    return str(binding.get("status") or binding.get("sync_state") or ("bound" if binding.get("binding_ref") or binding.get("bound_at") else "unknown"))


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

    For local providers: stores the mapping in the local SQLite database.

    For SaaS-backed providers: this command is not available.  Manage
    mappings in the Spec Kitty dashboard instead.
    """
    _check_binding_readiness(probe_reachability=False)

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
    provider: str | None = typer.Option(
        None,
        "--provider",
        help="Read SaaS mappings by provider without requiring a bound project",
    ),
    as_json: bool = typer.Option(False, "--json", help="Render mappings as JSON"),
) -> None:
    """List tracker mappings.

    For local providers: shows mappings from the local SQLite database.

    For SaaS-backed providers: shows SaaS-authoritative mappings from the
    control plane.
    """
    if provider is None:
        _check_binding_readiness(probe_reachability=False)
    else:
        _check_readiness(require_mission_binding=False, probe_reachability=False)

    def _run() -> None:
        mappings_result = _service(allow_unbound=provider is not None).map_list(provider=provider)
        pending_binding_upgrade = getattr(mappings_result, "pending_binding_upgrade", None)
        mappings = list(mappings_result)
        if as_json:
            _print_json(
                {
                    "mappings": mappings,
                    "pending_binding_upgrade": pending_binding_upgrade,
                }
            )
            return

        if not mappings:
            typer.echo("No mappings found")
            if pending_binding_upgrade:
                typer.echo(f"Tracker binding upgrade available: {pending_binding_upgrade}. Run `spec-kitty tracker bind` to apply.")
            return

        typer.echo("Mappings")
        for row in mappings:
            key = row.get("external_key") or row.get("external_id")
            typer.echo(f"- {row.get('wp_id')}: {row.get('system')}:{key}")
        if pending_binding_upgrade:
            typer.echo(f"Tracker binding upgrade available: {pending_binding_upgrade}. Run `spec-kitty tracker bind` to apply.")

    _run_or_exit(_run)


@app.command("list-tickets")
def list_tickets_command(
    provider: str = typer.Option(..., "--provider", help="Tracker provider slug"),
    limit: int = typer.Option(20, "--limit", min=1, max=100),
    as_json: bool = typer.Option(False, "--json", help="Render tickets as a JSON array"),
) -> None:
    """Browse visible tickets for the resolved provider resource."""
    _check_readiness(require_mission_binding=False, probe_reachability=False)

    def _run() -> None:
        rows = _service(allow_unbound=True).list_tickets(provider=provider, limit=limit)
        if as_json:
            _print_json(rows)
            return
        _print_ticket_rows(rows)

    _run_or_exit(_run)


# ---------------------------------------------------------------------------
# sync pull
# ---------------------------------------------------------------------------


@sync_app.command("pull")
def sync_pull_command(
    limit: int = typer.Option(100, "--limit", min=1, max=10000),
    as_json: bool = typer.Option(False, "--json", help="Render sync result as JSON"),
) -> None:
    """Pull tracker updates into the local cache.

    For SaaS-backed providers: pulls items via the SaaS control plane.
    The response includes an identity_path and summary envelope.

    For local providers: pulls directly from the tracker API.
    """
    root = require_repo_root()
    _check_sync_readiness(root=root)

    def _run() -> None:
        payload = _service(root=root).sync_pull(limit=limit)
        if as_json:
            _print_json(payload)
            return

        # SaaS envelope format
        if "summary" in payload:
            _echo_saas_sync_summary("Pull", payload)
            if payload.get("has_more"):
                typer.echo(f"- has_more: yes (next_cursor: {payload.get('next_cursor', 'N/A')})")
        # Local format
        else:
            stats = payload.get("stats", {})
            typer.echo(f"Pulled from {payload.get('provider')}")
            typer.echo(f"- created: {stats.get('pulled_created', 0)}")
            typer.echo(f"- updated: {stats.get('pulled_updated', 0)}")
            typer.echo(f"- skipped: {stats.get('skipped', 0)}")
            typer.echo(f"- conflicts: {len(payload.get('conflicts', []))}")
            typer.echo(f"- errors: {len(payload.get('errors', []))}")

    _run_or_exit(_run)


# ---------------------------------------------------------------------------
# sync push
# ---------------------------------------------------------------------------


@sync_app.command("push")
def sync_push_command(
    limit: int = typer.Option(100, "--limit", min=1, max=10000, help="Max items (local providers only)"),
    items_json: str | None = typer.Option(
        None,
        "--items-json",
        help="Path to JSON file with PushItem[] array (SaaS providers). Use '-' for stdin.",
    ),
    as_json: bool = typer.Option(False, "--json", help="Render sync result as JSON"),
) -> None:
    """Push explicit mutations to the upstream provider.

    For SaaS-backed providers: requires --items-json with a JSON array of
    PushItem objects per the PRI-12 TrackerPushRequest contract.  Each item
    must have ``ref``, ``action``, and optionally ``patch`` / ``target_status``.

    For full bidirectional sync, use ``tracker sync run`` instead.

    For local providers: pushes directly to the tracker API using --limit.
    """
    root = require_repo_root()
    _check_sync_readiness(root=root)
    import sys as _sys

    def _run() -> None:
        service = _service(root=root)
        config = load_tracker_config(root)

        if config.provider and config.provider in SAAS_PROVIDERS:
            # --- SaaS path: explicit items required ---
            if items_json is None:
                typer.secho(
                    "Error: --items-json is required for SaaS-backed providers.\n"
                    "Provide a JSON file with PushItem[] mutations, or use '-' for stdin.\n"
                    "For full bidirectional sync, use: tracker sync run",
                    fg=typer.colors.RED,
                    err=True,
                )
                raise typer.Exit(code=1)

            if items_json == "-":
                raw = _sys.stdin.read()
            else:
                from pathlib import Path as _Path  # noqa: PLC0415

                raw = _Path(items_json).read_text(encoding="utf-8")
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                typer.secho(
                    "Error: --items-json must contain a JSON array of PushItem objects.",
                    fg=typer.colors.RED,
                    err=True,
                )
                raise typer.Exit(code=1)

            payload = service.sync_push(items=parsed)
        else:
            # --- Local path: push via direct connector ---
            payload = service.sync_push(limit=limit)

        if as_json:
            _print_json(payload)
            return

        # SaaS envelope format
        if "summary" in payload:
            _echo_saas_sync_summary("Push", payload)
        # Local format
        else:
            stats = payload.get("stats", {})
            typer.echo(f"Pushed to {payload.get('provider')}")
            typer.echo(f"- created: {stats.get('pushed_created', 0)}")
            typer.echo(f"- updated: {stats.get('pushed_updated', 0)}")
            typer.echo(f"- skipped: {stats.get('skipped', 0)}")
            typer.echo(f"- conflicts: {len(payload.get('conflicts', []))}")
            typer.echo(f"- errors: {len(payload.get('errors', []))}")

    _run_or_exit(_run)


# ---------------------------------------------------------------------------
# sync run
# ---------------------------------------------------------------------------


@sync_app.command("run")
def sync_run_command(
    limit: int = typer.Option(100, "--limit", min=1, max=10000),
    as_json: bool = typer.Option(False, "--json", help="Render sync result as JSON"),
) -> None:
    """Run pull+push synchronization in one operation.

    For SaaS-backed providers: executes a full sync cycle via the SaaS
    control plane.

    For local providers: runs pull then push using direct connectors.
    """
    root = require_repo_root()
    _check_sync_readiness(root=root)

    def _run() -> None:
        payload = _service(root=root).sync_run(limit=limit)
        if as_json:
            _print_json(payload)
            return

        # SaaS envelope format
        if "summary" in payload:
            _echo_saas_sync_summary("Sync run", payload)
        # Local format
        else:
            stats = payload.get("stats", {})
            typer.echo(f"Sync run completed ({payload.get('provider')})")
            typer.echo(f"- pulled_created: {stats.get('pulled_created', 0)}")
            typer.echo(f"- pulled_updated: {stats.get('pulled_updated', 0)}")
            typer.echo(f"- pushed_created: {stats.get('pushed_created', 0)}")
            typer.echo(f"- pushed_updated: {stats.get('pushed_updated', 0)}")
            typer.echo(f"- skipped: {stats.get('skipped', 0)}")
            typer.echo(f"- conflicts: {len(payload.get('conflicts', []))}")
            typer.echo(f"- errors: {len(payload.get('errors', []))}")

    _run_or_exit(_run)


# ---------------------------------------------------------------------------
# sync publish
# ---------------------------------------------------------------------------


@sync_app.command("publish")
def sync_publish_command(
    as_json: bool = typer.Option(False, "--json", help="Render publish result as JSON"),
) -> None:
    """Publish local tracker snapshot.

    This command is not supported for SaaS-backed providers.  Use
    ``spec-kitty tracker sync push`` instead.

    For local providers: the facade will raise an error if this operation
    is not supported by the bound provider.
    """
    root = require_repo_root()
    _check_sync_readiness(root=root)

    def _run() -> None:
        payload = _service(root=root).sync_publish()
        if as_json:
            _print_json(payload)
            return

        typer.echo("Snapshot publish complete")
        typer.echo(f"- endpoint: {payload.get('endpoint')}")
        typer.echo(f"- status_code: {payload.get('status_code')}")
        typer.echo(f"- ok: {'yes' if payload.get('ok') else 'no'}")

    _run_or_exit(_run)


# ---------------------------------------------------------------------------
# unbind
# ---------------------------------------------------------------------------


@app.command("unbind")
def unbind_command() -> None:
    """Remove tracker binding for this project.

    For SaaS-backed providers this clears only local project configuration.
    Provider unlinking remains a SaaS dashboard action.
    """
    _check_binding_readiness(probe_reachability=False)

    def _run() -> None:
        _service().unbind()
        typer.echo("Tracker binding removed")

    _run_or_exit(_run)
