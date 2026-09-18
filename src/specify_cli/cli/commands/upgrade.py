"""Upgrade command implementation for Spec Kitty CLI.

This module exposes ``spec-kitty upgrade`` with the following flag surface
(C-006 — all existing flags preserved, new flags are additive):

Existing flags (preserved unchanged):
  --dry-run           Preview changes without applying.
  --force             Skip confirmation prompts.
  --target VERSION    Target version (defaults to current CLI version).
  --json              Output results as JSON (project-upgrade contract).
  --verbose / -v      Show detailed migration information.
  --no-worktrees      Skip upgrading worktrees.

New flags (WP09):
  --cli               Restrict to CLI guidance only (FR-014).  Works outside
                      any project; skip project-side flow entirely.
  --project           Restrict to current-project compat + migrations (FR-015).
                      Errors when invoked outside a project.
  --yes / -y          Non-interactive confirmation; alias for --force (FR-017).
  --no-nag            Suppress upgrade-nag output explicitly.

Mutual exclusion:
  --cli + --project together → exit 2 (BLOCK_INCOMPATIBLE_FLAGS).

JSON contract (--json with --cli or --project):
  Emits the compat-planner contract from
  ``contracts/compat-planner.json`` (schema_version: 1).  See R-09.

Exit codes (R-08):
  0  ALLOW / ALLOW_WITH_NAG / dry-run always 0
  2  BLOCK_INCOMPATIBLE_FLAGS (--cli + --project)
  4  BLOCK_PROJECT_MIGRATION
  5  BLOCK_CLI_UPGRADE (project too new — not overridable by --yes)
  6  BLOCK_PROJECT_CORRUPT

See also: docs/guides/install-and-upgrade.md
"""

from __future__ import annotations

import functools
import json
import os
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager, suppress
from kernel.clock import now_utc
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer
import click

if TYPE_CHECKING:
    from specify_cli.upgrade.assessment import PreparedUpgradeRepairs
    from specify_cli.tool_surface.operations import FileState
    from specify_cli.tool_surface.repair import DriftPolicySummary
    from specify_cli.upgrade.migrations.base import BaseMigration
from rich.panel import Panel
from rich.table import Table

from specify_cli.cli.console import console
from specify_cli.cli.helpers import show_banner
from specify_cli.cli.commands._teamspace_mission_state_gate import (
    offer_teamspace_mission_state_migration,
)
from specify_cli.core.env import is_truthy
from specify_cli.core.version_compare import is_version_newer
from specify_cli.gitignore_manager import GitignorePathError
from specify_cli.upgrade import autocommit
from specify_cli.upgrade.autocommit import (
    capture_upgrade_baseline,
    should_auto_commit,
    should_auto_commit_for_worktree,
)
from specify_cli.upgrade.outcome import RepairOutcome, UpgradeOutcome
from specify_cli.upgrade.runner import UpgradeResult


_PROJECT_COMPAT_CHECK_COMMAND = ("__project_compat_check__",)

_LEFT_UNCOMMITTED_MESSAGE = "[yellow]⚠ Changes were left uncommitted (auto_commit is disabled) — commit them yourself.[/yellow]"


def _collect_manual_review_paths(migration_results: dict[str, object]) -> list[str]:
    """Return sorted preserved/archive paths that require operator review."""
    manual_review_paths: set[str] = set()
    for result in migration_results.values():
        if not getattr(result, "manual_review_required", False):
            continue
        manual_review_paths.update(getattr(result, "preserved_paths", []))
    return sorted(manual_review_paths)


# ---------------------------------------------------------------------------
# T035 — --cli mode helper
# ---------------------------------------------------------------------------


def _run_cli_mode(
    *,
    json_output: bool,
    dry_run: bool,
    no_nag: bool,
    latest_version_provider: object = None,
) -> None:
    """Execute the --cli mode: emit CLI guidance without touching the project.

    Builds an Invocation with command_path=("upgrade",), calls compat.plan(),
    and either prints rendered_human (default) or renders_json (--json).

    This path is project-agnostic; it succeeds even outside any Spec Kitty
    project (FR-014).

    Args:
        json_output: When True, emit JSON instead of human text.
        dry_run: Passed through to exit-code logic (dry-run → always exit 0).
        no_nag: When True, set flag_no_nag in the Invocation.
        latest_version_provider: Optional override for tests.
    """
    from specify_cli.compat.planner import Invocation, is_ci_env, plan

    raw_args: tuple[str, ...] = ("--cli",)
    if dry_run:
        raw_args = raw_args + ("--dry-run",)

    # Keep the real environment for output policy; an explicit query can fetch
    # the version even when stdout is piped or CI is set.
    invocation = Invocation(
        command_path=("upgrade",),
        raw_args=raw_args,
        is_help=False,
        is_version=False,
        flag_no_nag=no_nag,
        env_ci=is_ci_env(),
        stdout_is_tty=sys.stdout.isatty(),
    )

    kwargs: dict[str, object] = {}
    if latest_version_provider is not None:
        kwargs["latest_version_provider"] = latest_version_provider

    result = plan(invocation, read_only=True, query_latest=True, **kwargs)  # type: ignore[arg-type]

    if json_output:
        exit_code = 0 if dry_run else result.exit_code
        payload = dict(result.rendered_json)
        print(json.dumps(payload, indent=2))
        raise typer.Exit(exit_code)

    if result.rendered_human:
        print(result.rendered_human)

    raise typer.Exit(0)


# ---------------------------------------------------------------------------
# Agent-host upgrade prompt helpers
# ---------------------------------------------------------------------------


def _agent_check_payload() -> dict[str, object]:
    """Return machine-readable upgrade readiness for agent prompt preambles."""
    from specify_cli.compat import (
        Invocation,
        NagCache,
        UpgradeConfig,
        build_upgrade_hint,
        detect_runtime,
        is_ci_env,
        plan as compat_plan,
    )
    from specify_cli.compat._detect.install_method import is_safe_for_auto_upgrade
    from specify_cli.readiness.upgrade_ux import (
        ENV_UPGRADE_DISABLED,
        is_currently_snoozed,
        needs_reset,
        resolve_effective_preference,
    )

    now = now_utc()
    invocation = Invocation(
        command_path=("upgrade",),
        raw_args=("--agent-check", "--json"),
        is_help=False,
        is_version=False,
        flag_no_nag=False,
        env_ci=is_ci_env(),
        stdout_is_tty=True,
    )
    result = compat_plan(invocation, now=now)
    cli_status = result.cli_status
    install_method = detect_runtime().install_method
    latest_version = cli_status.latest_version
    hint = build_upgrade_hint(install_method, target_version=latest_version)

    payload: dict[str, object] = {
        "schema_version": 1,
        "action": "none",
        "installed_version": cli_status.installed_version,
        "latest_version": cli_status.latest_version,
        "latest_source": cli_status.latest_source,
        "install_method": str(install_method),
        "upgrade_command": hint.command,
        "upgrade_note": hint.note,
        "reason": "up_to_date",
    }

    config = UpgradeConfig.load()
    if not config.nag_enabled:
        payload["reason"] = "nag_disabled"
        return payload

    if not is_version_newer(latest_version, cli_status.installed_version):
        return payload

    if is_truthy(os.environ.get(ENV_UPGRADE_DISABLED)):
        payload["reason"] = "upgrade_disabled"
        return payload

    cache = NagCache.default()
    existing = cache.read()
    remote_version_seen = existing.remote_version_seen if existing is not None else None
    reset_anchor = needs_reset(record_remote_version=remote_version_seen, current_latest=latest_version)
    snoozed_until = None if reset_anchor or existing is None else existing.snoozed_until
    persisted_never_ask = False if reset_anchor or existing is None else existing.never_ask
    persisted_always_upgrade = False if existing is None else existing.always_upgrade

    pref = resolve_effective_preference(
        persisted_never_ask=persisted_never_ask,
        persisted_always_upgrade=persisted_always_upgrade,
    )
    if pref.disabled:
        payload["reason"] = "upgrade_disabled"
        return payload
    if pref.never_ask:
        payload["reason"] = "never_ask"
        return payload
    if is_currently_snoozed(snoozed_until=snoozed_until, now=now):
        payload["reason"] = "snoozed"
        return payload

    safe = is_safe_for_auto_upgrade(install_method)
    if pref.always_upgrade:
        payload["action"] = "auto_upgrade" if safe and hint.command is not None else "guidance"
        payload["reason"] = "always_upgrade"
        return payload

    if hint.command is None:
        payload["action"] = "guidance"
        payload["reason"] = "manual_upgrade_required"
        return payload

    payload["action"] = "prompt"
    payload["reason"] = "upgrade_available"
    return payload


def _run_agent_check(*, json_output: bool) -> None:
    payload = _agent_check_payload()
    if json_output:
        print(json.dumps(payload, indent=2))
    elif payload.get("action") != "none":
        latest = payload.get("latest_version") or "unknown"
        installed = payload.get("installed_version") or "unknown"
        print(f"Spec Kitty upgrade available: {installed} -> {latest}")
    raise typer.Exit(0)


def _record_agent_choice(
    *,
    choice_raw: str,
    latest_version: str | None,
    json_output: bool,
) -> None:
    from specify_cli import __version__
    from specify_cli.compat import NagCache, NagCacheRecord
    from specify_cli.readiness.upgrade_ux import UpgradeChoice, apply_choice, needs_reset

    try:
        choice = UpgradeChoice(choice_raw)
    except ValueError:
        payload = {"status": "error", "error": "invalid_agent_choice", "choice": choice_raw}
        print(json.dumps(payload) if json_output else "Error: invalid agent choice")
        raise typer.Exit(2) from None

    if not latest_version:
        payload = {"status": "error", "error": "missing_agent_latest"}
        print(json.dumps(payload) if json_output else "Error: --agent-latest is required")
        raise typer.Exit(2)

    now = now_utc()
    cache = NagCache.default()
    existing = cache.read()
    reset_anchor = existing is not None and needs_reset(
        record_remote_version=existing.remote_version_seen,
        current_latest=latest_version,
    )
    record_kwargs: dict[str, object] = {
        "cli_version_key": __version__,
        "latest_version": latest_version,
        "latest_source": "pypi",
        "fetched_at": now,
        "last_shown_at": now,
        "remote_version_seen": None if reset_anchor or existing is None else existing.remote_version_seen,
        "snooze_step": None if reset_anchor or existing is None else existing.snooze_step,
        "snoozed_until": None if reset_anchor or existing is None else existing.snoozed_until,
        "always_upgrade": False if existing is None else existing.always_upgrade,
        "never_ask": False if reset_anchor or existing is None else existing.never_ask,
    }
    updated = apply_choice(record_kwargs, choice=choice, current_latest=latest_version, now=now)
    cache.write(NagCacheRecord(**updated))

    payload = {"status": "recorded", "choice": choice.value, "latest_version": latest_version}
    print(json.dumps(payload, indent=2) if json_output else f"Recorded {choice.value}")
    raise typer.Exit(0)


def _dispatch_agent_flags(
    *,
    agent_check: bool,
    agent_choice: str | None,
    agent_latest: str | None,
    json_output: bool,
) -> None:
    """T018: handle the ``--agent-check``/``--agent-choice`` mux.

    Every reachable branch here raises ``typer.Exit`` (via ``_run_agent_check``
    / ``_record_agent_choice`` / the mutual-exclusion error) — this function
    only returns normally when NEITHER flag was supplied, in which case the
    caller continues the normal upgrade flow. Pure extraction; behavior
    identical to the pre-extraction inline checks.
    """
    if agent_check and agent_choice is not None:
        console.print("[red]Error:[/red] --agent-check and --agent-choice are mutually exclusive.")
        raise typer.Exit(2)
    if agent_check:
        _run_agent_check(json_output=json_output)
        return
    if agent_choice is not None:
        _record_agent_choice(
            choice_raw=agent_choice,
            latest_version=agent_latest,
            json_output=json_output,
        )
        return


# ---------------------------------------------------------------------------
# T036 — helpers for project mode (skip CLI nag in output)
# ---------------------------------------------------------------------------


def _is_in_project(project_path: Path) -> bool:
    """Return True when *project_path* appears to be a Spec Kitty project."""
    return (project_path / ".kittify").exists() or (project_path / ".specify").exists()


def _guard_project_or_fallback_to_cli(
    project_path: Path,
    *,
    project: bool,
    json_output: bool,
    dry_run: bool,
    no_nag: bool,
) -> None:
    """T019: fail fast for ``--project`` outside a project, or fall back to
    ``--cli`` guidance for the default (bare) invocation.

    Pure extraction of the pre-refactor inline guard — detection semantics are
    unchanged (#3652 stays out of scope, C-001). Returns normally only when
    *project_path* is a real Spec Kitty project; every other path raises
    ``typer.Exit`` (directly, or via ``_run_cli_mode``, which always exits).
    """
    if _is_in_project(project_path):
        return

    if project:
        # --project was explicit; surface a clear "no project" error.
        if json_output:
            print(json.dumps({"error": "Not a Spec Kitty project", "case": "project_not_initialized"}))
        else:
            console.print("[red]Error:[/red] Not a Spec Kitty project.")
            console.print("[dim]Run 'spec-kitty init' to initialize a project.[/dim]")
            console.print("[dim]Tip: use 'spec-kitty upgrade --cli' for CLI guidance outside a project.[/dim]")
        raise typer.Exit(1)

    # Default mode (bare `spec-kitty upgrade` outside any project):
    # FR-014 says this should fall through to CLI guidance behavior rather
    # than erroring. Only error when --project is explicit.
    _run_cli_mode(json_output=json_output, dry_run=dry_run, no_nag=no_nag)


def _repair_stale_command_manifest(project_path: Path, *, json_output: bool) -> None:
    """Self-heal a stale command-skill manifest during upgrade.

    FR-030: a manifest whose entry count is behind the canonical command set
    (e.g. an rc44-era 11-entry manifest) is auto-repaired to the canonical
    count without prompting. FR-032: unsafe symlink artifacts under
    ``.agents/skills/`` are removed. Drifted (user-edited) generated files are
    NOT touched here — they flow through the drift policy in
    ``run_surface_repair``. Failures are non-fatal: upgrade must never abort
    because of manifest repair.
    """
    manifest_path = project_path / ".kittify" / "command-skills-manifest.json"
    if not manifest_path.exists():
        return
    try:
        from specify_cli.skills.command_installer import CANONICAL_COMMANDS
        from specify_cli.skills.manifest_store import (
            remove_unsafe_symlinks,
            repair_stale_manifest,
        )

        symlink_result = remove_unsafe_symlinks(project_path)
        repair_result = repair_stale_manifest(
            project_path,
            canonical_commands=list(CANONICAL_COMMANDS),
        )
        if json_output:
            return
        if repair_result.added or repair_result.removed:
            console.print(f"[dim]Repaired command-skill manifest (+{len(repair_result.added)}/-{len(repair_result.removed)} entries)[/dim]")
        if symlink_result.symlinks_removed:
            console.print(f"[dim]Removed {len(symlink_result.symlinks_removed)} unsafe symlink artifact(s)[/dim]")
    except Exception as manifest_exc:  # noqa: BLE001
        if not json_output:
            console.print(f"[dim]Note: Could not repair command-skill manifest: {manifest_exc}[/dim]")


def _run_upgrade_surface_repair(
    project_path: Path,
    *,
    confirm: bool,
    dry_run: bool,
    json_output: bool,
) -> DriftPolicySummary | None:
    """Run tool-surface repair after an upgrade and report the outcome.

    FR-001/FR-002 wiring: this MUST run on every ``upgrade`` invocation —
    including the "already up to date" path where no migrations are pending —
    so that missing or stale generated surfaces (agent profiles, command-skill
    manifests) are healed even when the project version is unchanged.

    NFR-007: ``--yes``/``--force`` sets ``interactive=False``, which triggers
    Rule 4 (report-only) for drifted files — NOT Rule 5 (overwrite). Overwrite
    requires an explicit ``--repair-drift=overwrite`` flag (not yet exposed,
    defaults False). FR-006: a non-interactive run exits non-zero when drift is
    detected and was not explicitly overwritten.

    T017/C4: this is one of the finalizer's injected callables (the caller
    wraps it to return a bool). It reports drift but no longer raises
    ``typer.Exit`` itself (D-5) — the caller derives ``surface_drift_failed``
    from the returned summary via :func:`_surface_drift_exit_required` and
    folds it into the single, outcome-derived exit code.
    """
    if dry_run:
        return None
    try:
        _repair_stale_command_manifest(project_path, json_output=json_output)

        from specify_cli.tool_surface.repair import (
            render_surface_summary_lines,
            run_surface_repair,
        )

        summary = run_surface_repair(
            project_path,
            interactive=not confirm,
            repair_drift=False,
        )
        if not json_output:
            for line in render_surface_summary_lines(summary):
                console.print(line)
        return summary
    except Exception as surf_exc:  # noqa: BLE001
        # Never fail upgrade due to surface repair errors; report and continue.
        if not json_output:
            console.print(f"[dim]Note: Could not run tool surface repair: {surf_exc}[/dim]")
        return None


def _surface_repair_payload(
    summary: DriftPolicySummary | None,
) -> dict[str, list[str]]:
    """Return a machine-readable drift-policy summary for upgrade JSON."""
    if summary is None:
        return {
            "created": [],
            "repaired": [],
            "drifted_overwritten": [],
            "drifted_reported": [],
            "skipped": [],
        }
    return {
        "created": [str(path) for path in summary.created],
        "repaired": [str(path) for path in summary.repaired],
        "drifted_overwritten": [str(path) for path in summary.drifted_overwritten],
        "drifted_reported": [str(path) for path in summary.drifted_reported],
        "skipped": [str(path) for path in summary.skipped],
    }


def _surface_drift_exit_required(
    summary: DriftPolicySummary | None,
    *,
    confirm: bool,
) -> bool:
    """Return True when non-interactive upgrade reported unresolved drift."""
    return bool(confirm and summary is not None and summary.drifted_reported)


def _surface_drift_error(summary: DriftPolicySummary) -> str:
    return f"Unresolved tool-surface drift in {len(summary.drifted_reported)} file(s); run 'spec-kitty doctor tool-surfaces' to review."


def _provision_missing_mission_type_activations(project_path: Path, *, dry_run: bool) -> list[str]:
    """Backfill a missing ``mission_type_activations`` key on upgrade.

    Fold for PR #3246 (mission ``resolution-activation-foundation-01KZ9FKG``,
    WP04): removing the config-absent implicit "all four built-ins" backfill
    made mission creation fail closed (``CharterPackConfigError``) whenever
    the project's activation authority lacks ``mission_type_activations``.
    Fresh ``spec-kitty init`` got a provisioner
    (:func:`specify_cli.provisioning.default_charter.provision_default_mission_type_activations`)
    but ``upgrade`` had no equivalent — the only seeder was the version-pinned
    ``3.2.0rc35_activate_builtin_mission_types`` migration, and
    ``MigrationRegistry.get_applicable``'s ``from_v < target <= to_v`` window
    never selects it for a project first initialised on rc36-rc38 (already
    past rc35) upgrading to a later target. Such projects are stranded: every
    ``mission create`` fails, even though the create-gate's own error message
    tells the operator to run ``spec-kitty upgrade``.

    WP01 (#3282): the fix above wrote into ``.kittify/config.yaml``
    unconditionally, but a pointer-based/migrated project (``config.yaml``
    carries a ``charter:`` pointer) reads activations from the pointed-at
    ``charter.yaml`` (``PackContext.from_config`` — INV-2). The write side
    was pointer-blind, so the key it wrote was never read by anything. This
    now seeds through :func:`charter.activation.compiler.provision_mission_type_activations`
    — the SAME pointer-aware writer ``spec-kitty charter generate``/``activate``
    use, which resolves the write target via
    :func:`charter.activation.pack_manager.resolve_activation_write_target` (``charter.yaml``
    for a migrated project, ``config.yaml`` for a legacy one — the identical
    authority the read side already consults). This is an intentional
    divergence from fresh ``init``, not a regression: ``init`` still seeds
    through the pointer-blind ``provision_default_mission_type_activations``
    (a freshly-initialised project has no pointer yet, so there is nothing to
    resolve), while ``upgrade`` may be healing an already-migrated project and
    must target whichever authority that project actually reads.

    Both provisioners share the same seed-read
    (:func:`charter.activation.default_pack.load_default_mission_type_activations`) so
    they can never seed a divergent activation set — only the write target
    differs, additive-only (never overwrites an authored list, including an
    authored empty ``[]``), idempotent (a second call is a no-op), and
    fail-closed if the shipped ``src/charter/activation/packs/default.yaml`` is missing
    or the resolved ``charter:`` pointer is dangling/unreadable.

    Must run on every real ``upgrade`` invocation, mirroring
    ``_run_upgrade_surface_repair``'s "even when no migrations are pending"
    wiring (FR-001/FR-002) — this exact gap is why the rc36-rc38 stranding
    survived the version-pinned migration path. Never writes during
    ``--dry-run``.

    Returns:
        A list of human-readable error messages (empty on success/no-op).
    """
    if dry_run:
        return []

    from charter.activation.compiler import provision_mission_type_activations
    from charter.activation.pack_context import CharterPackConfigError

    try:
        provision_mission_type_activations(project_path)
    except CharterPackConfigError as exc:
        return [exc.body]
    return []


def _mission_type_activation_provisioning_pending(project_path: Path) -> bool:
    """Return True when a real upgrade would seed ``mission_type_activations``.

    Mirrors :func:`charter.activation.compiler.provision_mission_type_activations`'s
    additive no-op rule (FR-009 preview parity, C-WP01): the seed writes only
    when the key is *entirely absent* from the resolved write target. A
    ``--dry-run`` skips the real seed, so this predicate is how the preview
    stays honest about it.

    WP01 (#3282): keys on KEY-PRESENCE in the resolved write target itself —
    the same ``(path, data, save)`` triple
    :func:`charter.activation.pack_manager.resolve_activation_write_target` hands the
    real writer (``charter.yaml`` for a pointer/migrated project,
    ``config.yaml`` for a legacy one) — NOT on
    ``PackContext.from_config(...).activated_mission_types`` non-emptiness.
    That distinction matters: an authored empty ``mission_type_activations: []``
    resolves to an EMPTY ``activated_mission_types`` frozenset, which would
    make a non-emptiness check falsely report ``pending=True`` even though a
    real upgrade correctly leaves the deliberate empty list untouched —
    breaking authored-empty preview parity for pointer projects.

    A dangling/unreadable ``charter:`` pointer makes the resolver fail-loud
    with ``CharterPackConfigError`` (INV-5) — the correct contract for the
    REAL write (there is nowhere safe to seed). This PREVIEW predicate keeps
    a defined, non-crashing contract instead: it reports ``True`` (pending)
    rather than letting the exception propagate through the dry-run surface,
    or silently returning ``False`` and hiding the broken pointer from the
    operator.

    Args:
        project_path: Root of the project directory (``.kittify``'s parent).

    Returns:
        True if the seed would create the key on a real run, else False.
    """
    from charter.activation.pack_context import CharterPackConfigError

    try:
        from charter.activation.pack_manager import resolve_activation_write_target

        _target_path, data, _save = resolve_activation_write_target(project_path)
    except CharterPackConfigError:
        return True
    except Exception:  # noqa: BLE001 — unreadable/malformed config: do not claim a pending seed
        return False
    return "mission_type_activations" not in data


def _print_dry_run_provisioning_notice(project_path: Path, *, dry_run: bool, json_output: bool) -> None:
    """Print a human-readable preview line for the provisioning seed.

    FR-009: a ``--dry-run`` skips the real ``mission_type_activations`` seed, so
    the human preview must still say it would happen. No-ops outside dry-run and
    for the ``--json`` surface (which reports ``pending_provisioning`` instead).
    """
    if not dry_run or json_output:
        return
    if _mission_type_activation_provisioning_pending(project_path):
        console.print("[dim]Would provision missing mission_type_activations (seeded on a real upgrade).[/dim]")


def _check_project_not_too_new(
    project_path: Path,
    *,
    json_output: bool,
) -> None:
    """Exit 5 if the project schema is newer than this CLI supports.

    CHK037 / A-006: ``--yes`` and ``--force`` do NOT bypass this check.
    A too-new project cannot be migrated downward from the project side;
    the only fix is to upgrade the CLI.  The function always exits 5 on a
    too-new project regardless of ``--dry-run`` (see WP09 T036 spec).

    Args:
        project_path: Path to the current project directory.
        json_output: When True, emit a JSON error payload.
    """
    try:
        from specify_cli.migration.schema_version import (
            MAX_SUPPORTED_SCHEMA,
            get_project_schema_version,
        )

        schema_v = get_project_schema_version(project_path)
        if schema_v is None:
            return  # No schema_version field → LEGACY; handled elsewhere
        if not isinstance(schema_v, int):
            return  # Corrupt; handled by MigrationRunner

        if schema_v > MAX_SUPPORTED_SCHEMA:
            if json_output:
                from specify_cli.compat.planner import Invocation, plan as _plan

                inv = Invocation(
                    # This JSON describes current-project compatibility, not
                    # the safe remediation command itself.
                    command_path=_PROJECT_COMPAT_CHECK_COMMAND,
                    raw_args=("--project",),
                    is_help=False,
                    is_version=False,
                    flag_no_nag=True,
                    env_ci=False,
                    stdout_is_tty=False,
                )
                result = _plan(inv)
                print(json.dumps(result.rendered_json, indent=2))
            else:
                from specify_cli.compat._detect.runtime import detect_runtime as _detect_runtime
                from specify_cli.compat.upgrade_hint import build_upgrade_hint

                method = _detect_runtime().install_method
                hint = build_upgrade_hint(method)
                hint_str = hint.command if hint.command is not None else hint.note or "Upgrade your CLI."
                console.print(
                    f"[red]Error:[/red] This project uses Spec Kitty project schema {schema_v}, but this CLI supports up to schema {MAX_SUPPORTED_SCHEMA}."
                )
                console.print(f"[cyan]Upgrade your CLI:[/cyan] {hint_str}")
            raise typer.Exit(5)
    except typer.Exit:
        raise
    except Exception:  # noqa: BLE001 — fail-open; let the runner handle other errors
        pass


# ---------------------------------------------------------------------------
# Main upgrade command
# ---------------------------------------------------------------------------


def _show_migration_plan_and_confirm(
    migrations_needed: Sequence[BaseMigration],
    *,
    project_path: Path,
    json_output: bool,
    dry_run: bool,
    verbose: bool,
    confirm: bool,
) -> None:
    """T021: render the migration-plan table and gate on the confirm prompt.

    Pure display plus a legitimate PRE-finalizer gate: no migration has run
    yet at this point, so a decline here (``raise typer.Exit(0)``) is a
    user-cancellation exit, not one of the tail's outcome-derived exits (C4
    reviewer note — pre-finalizer exits are allowed; only the tail must derive
    its exit code exactly once).
    """
    if not json_output:
        table = Table(title="Migration Plan", show_lines=False, header_style="bold cyan")
        table.add_column("Migration", style="bright_white")
        table.add_column("Description", style="dim")
        table.add_column("Target", style="cyan")

        for migration in migrations_needed:
            table.add_row(
                migration.migration_id,
                migration.description,
                migration.target_version,
            )

        console.print(table)
        console.print()

        _print_dry_run_provisioning_notice(project_path, dry_run=dry_run, json_output=json_output)

        if verbose:
            # Show detection results
            console.print("[dim]Detection results:[/dim]")
            for migration in migrations_needed:
                # A symlinked `.gitignore`/`.claudeignore` makes detect() fail
                # closed with GitignorePathError rather than follow it
                # (gitignore_manager.py) -- report it as skipped instead of
                # crashing the whole upgrade command in verbose mode.
                try:
                    detected = migration.detect(project_path)
                    detect_error: str | None = None
                except GitignorePathError as exc:
                    detected = False
                    detect_error = str(exc)
                can_apply, reason = migration.can_apply(project_path)
                status = "[green]ready[/green]" if detected and can_apply else "[yellow]skipped[/yellow]"
                console.print(f"  {migration.migration_id}: {status}")
                if detect_error:
                    console.print(f"    [dim]{detect_error}[/dim]")
                elif not can_apply and reason:
                    console.print(f"    [dim]{reason}[/dim]")
            console.print()

    # T034 — confirm uses `confirm` (yes or force) instead of bare `force`
    if not dry_run and not confirm:
        proceed = typer.confirm(
            f"Apply {len(migrations_needed)} migration(s)?",
            default=True,
        )
        if not proceed:
            console.print("[yellow]Upgrade cancelled.[/yellow]")
            raise typer.Exit(0)


def _stamp_no_migrations_metadata(kittify_dir: Path, *, target_version: str, dry_run: bool) -> None:
    """Bump the version stamp (and repair a missing schema stamp, #1158) when
    no migrations ran but the target version differs from the recorded one."""
    from specify_cli.upgrade.metadata import ProjectMetadata

    metadata = ProjectMetadata.load(kittify_dir)
    if metadata and metadata.version != target_version and not dry_run:
        metadata.version = target_version
        metadata.last_upgraded_at = now_utc()
        metadata.save(kittify_dir)

    if not dry_run:
        from specify_cli.migration.schema_version import REQUIRED_SCHEMA_VERSION
        from specify_cli.upgrade.runner import MigrationRunner

        if REQUIRED_SCHEMA_VERSION is not None:
            MigrationRunner._stamp_schema_version(kittify_dir, REQUIRED_SCHEMA_VERSION)


def _run_no_migrations_worktree_stamp(
    project_path: Path,
    *,
    target_version: str,
    current_version: str,
    dry_run: bool,
    no_worktrees: bool,
) -> tuple[list[str], list[str]]:
    """Stamp worktree metadata when the main checkout is already current.

    Mirrors the pre-refactor no-migrations branch's worktree-only stamp pass
    (unchanged semantics). Returns ``(warnings, worktree_failures)`` for the
    caller to fold into the synthesized outcome (FR-012).
    """
    if no_worktrees or current_version != target_version:
        return [], []

    from specify_cli.upgrade.runner import MigrationRunner

    # auto_commit: each worktree's upgrade churn lands on its own branch
    # (#2385) so a later `spec-kitty merge` isn't blocked by dirty coord/lane
    # worktrees. D-10: the worktree-scope decision, not a bare `not dry_run`.
    worktrees_result = MigrationRunner(project_path, console).upgrade_worktrees_only(
        target_version,
        dry_run=dry_run,
        auto_commit=should_auto_commit_for_worktree(project_path, dry_run=dry_run),
    )
    warnings = list(worktrees_result.get("warnings", []))
    if worktrees_result.get("errors"):
        warnings.extend(worktrees_result["errors"])
        warnings.append("Some worktrees had issues - check errors above")
    worktree_failures = list(worktrees_result.get("worktree_failures", []))
    return warnings, worktree_failures


def _build_no_migrations_outcome(
    *,
    project_path: Path,
    kittify_dir: Path,
    current_version: str,
    target_version: str,
    dry_run: bool,
    no_worktrees: bool,
) -> UpgradeOutcome:
    """T017/D-3: normalize the no-migrations branch into a synthetic
    ``UpgradeResult`` wrapped in an ``UpgradeOutcome`` — the SAME shape the
    finalizer consumes for the migrations-pending branch, so both branches
    converge on one tail (one finalizer call, one renderer, one exit code)."""
    _stamp_no_migrations_metadata(kittify_dir, target_version=target_version, dry_run=dry_run)
    worktree_warnings, worktree_failures = _run_no_migrations_worktree_stamp(
        project_path,
        target_version=target_version,
        current_version=current_version,
        dry_run=dry_run,
        no_worktrees=no_worktrees,
    )
    result = UpgradeResult(
        success=True,
        from_version=current_version,
        to_version=target_version,
        dry_run=dry_run,
        warnings=worktree_warnings,
    )
    return UpgradeOutcome(result=result, worktree_failures=worktree_failures)


def _combined_errors(outcome: UpgradeOutcome, surface_repair_summary: DriftPolicySummary | None) -> list[str]:
    """Fold the errors channel (data-model.md): ``result.errors`` +
    ``activation_errors`` + ``worktree_failures`` + the surface-drift
    message, read from the finalized outcome — the one place both renderers
    source errors from.

    ``worktree_failures`` is what ``effective_success`` keys on to flip
    ``success: false`` (FR-012), so it must be visible here too — otherwise a
    ``--json`` consumer sees a failed run with an empty ``errors`` array. The
    migrations-pending path (``MigrationRunner._upgrade_worktrees``) already
    mirrors the same failure strings into ``result.errors`` from the SAME
    list, so folding is deduplicated against what's already present rather
    than blindly extended, or that path would report each failure twice.
    """
    errors = list(outcome.result.errors)
    errors.extend(outcome.activation_errors)
    seen = set(errors)
    for failure in outcome.worktree_failures:
        if failure not in seen:
            errors.append(failure)
            seen.add(failure)
    if outcome.surface_drift_failed and surface_repair_summary is not None:
        errors.append(_surface_drift_error(surface_repair_summary))
    return errors


def _build_migration_json_payload(
    outcome: UpgradeOutcome,
    migrations_needed: Sequence[BaseMigration],
    *,
    manual_review_paths: list[str],
    auto_commit_paths: list[str],
    surface_repair_summary: DriftPolicySummary | None,
) -> dict[str, object]:
    """T020: build the JSON payload for the migrations-pending path.

    A pure function of the finalized ``UpgradeOutcome`` — no printing, no
    exit derivation (that happens exactly once, at the command boundary, D-5).
    """
    result = outcome.result
    migrations_detail = []
    for migration in migrations_needed:
        if migration.migration_id in result.migrations_applied:
            status = "applied"
        elif migration.migration_id in result.migrations_skipped:
            status = "skipped"
        else:
            status = "pending"
        migrations_detail.append(
            {
                "id": migration.migration_id,
                "description": migration.description,
                "target_version": migration.target_version,
                "status": status,
                "manual_review_required": (
                    result.migration_results.get(migration.migration_id).manual_review_required if migration.migration_id in result.migration_results else False
                ),
                "preserved_paths": (
                    result.migration_results.get(migration.migration_id).preserved_paths if migration.migration_id in result.migration_results else []
                ),
            }
        )

    # Surface per-migration schema-shaped JSON reports (e.g. the
    # 3.2.0rc35_unified_bundle contract-shaped payload). Each migration emits
    # its report as a single JSON string inside
    # ``MigrationResult.changes_made[0]``; decode it so operators see a
    # structured object rather than an opaque string.
    migration_reports: dict[str, object] = {}
    for mid, mres in result.migration_results.items():
        if not mres.changes_made:
            continue
        payload = mres.changes_made[0]
        try:
            migration_reports[mid] = json.loads(payload)
        except (TypeError, ValueError):
            # Migration emitted a non-JSON change string; skip rather than
            # break the operator contract.
            continue

    success = outcome.effective_success
    return {
        "status": "success" if success else "failed",
        "current_version": result.from_version,
        "target_version": result.to_version,
        "dry_run": result.dry_run,
        "migrations": migrations_detail,
        "migrations_applied": result.migrations_applied,
        "migrations_skipped": result.migrations_skipped,
        "migration_reports": migration_reports,
        "success": success,
        "errors": _combined_errors(outcome, surface_repair_summary),
        "warnings": result.warnings,
        "manual_review_required": bool(manual_review_paths),
        "manual_review_paths": manual_review_paths,
        "auto_committed": outcome.committed,
        "auto_commit_paths": auto_commit_paths,
        "surface_repair": _surface_repair_payload(surface_repair_summary),
    }


def _build_no_migrations_json_payload(
    outcome: UpgradeOutcome,
    *,
    auto_commit_paths: list[str],
    surface_repair_summary: DriftPolicySummary | None,
) -> dict[str, object]:
    """Build the JSON payload for the up-to-date (no-migrations) path.

    Keeps the pre-existing ``status: up_to_date`` contract shape (pinned by
    ``tests/upgrade/test_upgrade_auto_commit_unit.py``) while sourcing every
    value from the finalized ``UpgradeOutcome`` (D-3/D-5) instead of the old,
    separately-computed ``upgrade_failed`` formula (#3392).
    """
    result = outcome.result
    success = outcome.effective_success
    return {
        "status": "up_to_date" if success else "failed",
        "current_version": result.from_version,
        "target_version": result.to_version,
        "success": success,
        "errors": _combined_errors(outcome, surface_repair_summary),
        "auto_committed": outcome.committed,
        "auto_commit_paths": auto_commit_paths,
        "warnings": result.warnings,
        "surface_repair": _surface_repair_payload(surface_repair_summary),
    }


def _display_no_migrations_results(outcome: UpgradeOutcome, *, auto_commit_paths: list[str], left_uncommitted: bool = False) -> None:
    """Render the human-readable up-to-date (no-migrations) outcome.

    Pure rendering (T022): never raises. The caller derives the exit code
    exactly once, from ``UpgradeOutcome.exit_code`` (D-5).
    """
    result = outcome.result
    console.print("[green]Project is already up to date![/green]")
    for warning in result.warnings:
        console.print(f"[yellow]Warning:[/yellow] {warning}")
    for error in outcome.activation_errors:
        console.print(f"[red]Error:[/red] {error}")
    if outcome.committed:
        console.print(f"[cyan]→ Auto-committed upgrade changes ({len(auto_commit_paths)} files)[/cyan]")
    elif left_uncommitted:
        console.print(_LEFT_UNCOMMITTED_MESSAGE)


class _FinalizerRenderContext:
    """Mutable side-channel for the finalizer's injected callables (T017/T018-21).

    ``finalize_upgrade``'s step contracts return only what the exit-code
    computation needs (``list[str]``/``bool``/``RepairOutcome`` — see C4).
    The renderers additionally need the surface-repair summary object and the
    concrete committed paths, which are not part of that contract — this
    small holder threads them out of the ``functools.partial``-bound step
    functions below without resorting to closures (closures nested inside
    ``upgrade()`` inflate its cyclomatic complexity past the NFR-004 ceiling,
    D-12).
    """

    def __init__(self) -> None:
        self.surface_repair_summary: DriftPolicySummary | None = None
        self.commit_paths: list[str] = []
        self.commit_warning: str | None = None
        self.prepared_repairs: PreparedUpgradeRepairs | None = None


def _finalizer_step_provision(project_path: Path, *, dry_run: bool, prepared: PreparedUpgradeRepairs | None = None) -> list[str]:
    """Injected ``provision_activations`` step (C4 order position 1)."""
    if prepared is None:
        return _provision_missing_mission_type_activations(project_path, dry_run=dry_run)
    try:
        prepared.provisioning.apply()
    except (OSError, ValueError) as exc:
        return [str(exc)]
    return []


def _prepare_finalizer_repairs(project_path: Path, ctx: _FinalizerRenderContext) -> tuple[str, ...]:
    from specify_cli.upgrade.assessment import prepare_upgrade_repairs
    from specify_cli.tool_surface.operations import ApplyConsent
    from specify_cli.core.agent_config import AgentConfigError

    try:
        ctx.prepared_repairs = prepare_upgrade_repairs(project_path, consent=ApplyConsent(automatic=True))
    except (OSError, ValueError, AgentConfigError) as exc:
        return (str(exc),)
    return ()


@contextmanager
def _finalizer_repair_preflight(prepared: PreparedUpgradeRepairs | None, errors: tuple[str, ...]) -> Iterator[tuple[str, ...]]:
    if prepared is None:
        yield errors
        return
    from specify_cli.upgrade.assessment import preflight_upgrade_repairs

    with preflight_upgrade_repairs(prepared) as diagnostics:
        yield errors + tuple(d.message for d in diagnostics)


def _supporting_repair_preview(project_path: Path) -> tuple[str, bool]:
    """Describe canonical retained effects without entering any write boundary."""
    from specify_cli.core.agent_config import AgentConfigError
    from specify_cli.tool_surface.operations import ApplyConsent
    from specify_cli.upgrade.assessment import prepare_upgrade_repairs

    hint = "Use --plan-json for full repair details."
    try:
        prepared = prepare_upgrade_repairs(project_path, consent=ApplyConsent())
        if not prepared.complete:
            detail = "; ".join(d.message for d in prepared.diagnostics if d.severity == "error")
            return f"Supporting repair preview incomplete: {detail[:350] or 'Required owner assessment incomplete'}. {hint}", True
        effects = prepared.effects
    except (OSError, ValueError, AgentConfigError) as exc:
        return f"Supporting repair preview incomplete: {str(exc)[:350]}. {hint}", True
    preserved = sum(d.state == "consent_required" for owner in prepared.owners for d in owner.dispositions)
    if not effects and not preserved:
        return "", False
    manifests = sum(effect.after.kind != "directory" and "manifest" in Path(effect.path).name.lower() for effect in effects)
    lines = [f"Would repair {len(effects)} supporting surface paths (including {manifests} manifests)."] if effects else []
    if preserved:
        lines.append(f"Would preserve {preserved} paths requiring separate consent.")
    return " ".join((*lines, hint)), False


def _finalizer_step_surface_repair(
    outcome: UpgradeOutcome,
    ctx: _FinalizerRenderContext,
    *,
    project_path: Path,
    confirm: bool,
    dry_run: bool,
    json_output: bool,
) -> bool:
    """Injected ``run_surface_repair`` step (C4 order position 2).

    Gated on ``outcome.result.success`` — surface repair (and its own
    JSON/human output) never runs after a failed migration, mirroring the
    pre-refactor behavior.
    """
    if not outcome.result.success:
        return False
    if dry_run:
        notice, incomplete = _supporting_repair_preview(project_path)
        if notice and not json_output:
            console.print(notice, markup=False)
        if incomplete:
            outcome.result.errors.append(notice)
        return incomplete
    if ctx.prepared_repairs is not None:
        from specify_cli.upgrade.assessment import apply_upgrade_repairs
        from specify_cli.tool_surface.repair import DriftPolicySummary

        prepared = ctx.prepared_repairs
        results = apply_upgrade_repairs(prepared)
        succeeded = {effect_id for result in results for effect_id in result.succeeded}
        summary = DriftPolicySummary()
        for effect in prepared.effects:
            if effect.id in succeeded:
                (summary.created if effect.action == "create" else summary.repaired).append(effect.destination)
        for owner in prepared.owners:
            summary.drifted_reported.extend(
                owner.root.path / disposition.path for disposition in owner.dispositions
                if disposition.state == "consent_required" and disposition.path is not None
            )
        ctx.surface_repair_summary = summary
        outcome.result.errors.extend(d.message for result in results for d in result.diagnostics if d.severity == "error")
        return bool(summary.drifted_reported) or any(result.outcome not in {"applied", "skipped"} for result in results)
    ctx.surface_repair_summary = _run_upgrade_surface_repair(
        project_path,
        confirm=confirm,
        dry_run=dry_run,
        json_output=json_output,
    )
    return _surface_drift_exit_required(ctx.surface_repair_summary, confirm=confirm)


def _finalizer_step_commit_churn(
    outcome: UpgradeOutcome,
    ctx: _FinalizerRenderContext,
    *,
    project_path: Path,
    baseline_changed_paths: set[str] | None,
) -> bool:
    """Injected ``commit_churn`` step (C4 order position 3) — the single
    main-checkout churn commit, run only when ``should_commit`` is True."""
    committed, paths, warning = autocommit.commit_touched_checkout(
        project_path,
        baseline_changed_paths,
        outcome.result.from_version,
        outcome.result.to_version,
    )
    ctx.commit_paths = paths
    ctx.commit_warning = warning
    return committed


def _churn_left_uncommitted_by_config(
    outcome: UpgradeOutcome,
    *,
    dry_run: bool,
    should_commit_main: bool,
    project_path: Path,
    baseline_changed_paths: set[str] | None,
) -> bool:
    """True when main-checkout churn exists but was left uncommitted purely
    because the project's ``auto_commit`` config is disabled (FR-003 /
    User Story 2 scenario 1: "the command reports that changes were left
    uncommitted").

    Deliberately excludes two other "not committed" paths that already
    report their own state and must not be double-warned: ``--dry-run``
    (nothing was ever meant to be written or committed, FR-003 scenario 3)
    and manual-review preservation (its own warning is already appended to
    ``result.warnings``, D-10). What remains — ``should_commit_main`` False
    for neither of those reasons — can only be the config opt-out
    (``autocommit.should_auto_commit``'s sole remaining gate, C2).

    Uses :func:`autocommit.prepare_upgrade_commit_files` — the same,
    side-effect-free churn-detection routine ``commit_touched_checkout``
    itself uses — so "would there have been anything to commit" never
    duplicates or drifts from the real eligibility/baseline-diff rules.
    """
    if dry_run or outcome.manual_review_paths or should_commit_main or outcome.committed:
        return False
    return bool(autocommit.prepare_upgrade_commit_files(project_path, baseline_changed_paths))


def _finalizer_step_offer_repair(
    outcome: UpgradeOutcome,
    *,
    project_path: Path,
    confirm: bool,
    dry_run: bool,
    json_output: bool,
) -> RepairOutcome:
    """Injected ``offer_repair`` step (C4 order position 4).

    Mirrors the pre-refactor gating: the interactive mission-state prompt
    never runs under ``--json``, nor after a failed migration.
    """
    if json_output or not outcome.result.success:
        return RepairOutcome(pending=True, message="Repair prompt skipped (json output or failed migration).")
    return offer_teamspace_mission_state_migration(
        project_path,
        console=console,
        dry_run=dry_run,
        assume_yes=confirm,
    )


def _resolve_upgrade_target(target: str | None) -> str:
    if target is not None:
        return target
    from specify_cli import __version__

    return __version__


def _reject_downgrade_target(validation_error: str | None, *, current_version: str, target_version: str, json_output: bool) -> None:
    """Raise ``typer.Exit(1)`` when *validation_error* is set (a downgrade
    target); a no-op otherwise. Pure extraction — this is a legitimate
    pre-finalizer gate (no ``UpgradeOutcome`` exists yet at this point)."""
    if not validation_error:
        return
    if json_output:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "current_version": current_version,
                    "target_version": target_version,
                    "success": False,
                    "errors": [validation_error],
                    "warnings": [],
                    "auto_committed": False,
                    "auto_commit_paths": [],
                }
            )
        )
    else:
        console.print(f"[red]Error:[/red] {validation_error}")
    raise typer.Exit(1)


def _full_plan_compatibility(project_path: Path) -> tuple[dict[str, object], int]:
    """Return the frozen compatibility envelope without network or writes."""
    from specify_cli.compat.planner import Invocation, plan

    result = plan(
        Invocation(
            command_path=_PROJECT_COMPAT_CHECK_COMMAND,
            raw_args=("--project", "--plan-json"),
            is_help=False,
            is_version=False,
            flag_no_nag=True,
            env_ci=True,
            stdout_is_tty=False,
        ),
        read_only=True,
        project_root_resolver=lambda _path: project_path,
        include_migrations=False,
    )
    return dict(result.rendered_json), result.exit_code


def _empty_full_plan(
    *, project_path: Path, target: str | None, project: bool,
    no_worktrees: bool, confirm: bool,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "mode": "preview",
        "intent": {
            "project_mode": project,
            "requested_target": target,
            "include_worktrees": not no_worktrees,
            "confirm": confirm,
        },
        "target": {"current": None, "requested": target, "relation": "unknown", "valid": False, "reason": ""},
        "compatibility": {},
        "complete": False,
        "decision": "blocked",
        "process_exit_code": 1,
        "roots": [{"id": "project", "scope": "project", "path": str(project_path.resolve())}],
        "migrations": [],
        "effects": [],
        "dispositions": [],
        "diagnostics": [],
        "execution_artifacts": [],
        "commit_policy": {"project_enabled": False, "worktrees_enabled": False, "mission_repair_included": False},
    }


def _emit_blocked_full_plan(
    *, project_path: Path, target: str | None, project: bool,
    no_worktrees: bool, confirm: bool, code: int,
    diagnostic_code: str, message: str,
) -> None:
    payload = _empty_full_plan(
        project_path=project_path, target=target, project=project,
        no_worktrees=no_worktrees, confirm=confirm,
    )
    payload["process_exit_code"] = code
    with suppress(Exception):
        payload["compatibility"], _compat_code = _full_plan_compatibility(project_path)
    payload["target"] = {
        "current": None, "requested": target, "relation": "unknown",
        "valid": diagnostic_code != "invalid_target", "reason": message,
    }
    payload["diagnostics"] = [{"code": diagnostic_code, "owner": None, "severity": "error", "message": message}]
    print(json.dumps(payload, indent=2))
    raise typer.Exit(code)


def _state_json(state: FileState) -> dict[str, object]:
    return {
        "kind": state.kind,
        "sha256": state.sha256,
        "target": state.target,
        "mode": state.mode,
    }


def _run_full_plan_json(
    *, project_path: Path, requested_target: str | None, project: bool,
    include_worktrees: bool, confirm: bool,
) -> None:
    """Render the complete retained assessment. The document is never replayable."""
    from packaging.version import InvalidVersion, Version
    from specify_cli.migration.schema_version import MAX_SUPPORTED_SCHEMA, get_project_schema_version
    from specify_cli.tool_surface.operations import ApplyConsent
    from specify_cli.upgrade.assessment import prepare_upgrade_repairs
    from specify_cli.upgrade.detector import VersionDetector
    from specify_cli.upgrade.runner import validate_upgrade_target

    target = _resolve_upgrade_target(requested_target)
    current = VersionDetector(project_path).detect_version()
    compatibility, _compat_code = _full_plan_compatibility(project_path)
    payload = _empty_full_plan(
        project_path=project_path, target=requested_target, project=project,
        no_worktrees=not include_worktrees, confirm=confirm,
    )
    payload["compatibility"] = compatibility
    relation = "unknown"
    try:
        requested_v = Version(target)
        relation = "unknown" if current == "unknown" else (
            "lower" if requested_v < Version(current) else "equal" if requested_v == Version(current) else "higher"
        )
    except InvalidVersion:
        relation = "invalid"
    target_error = validate_upgrade_target(current, target)
    payload["target"] = {
        "current": current,
        "requested": target,
        "relation": relation,
        "valid": target_error is None,
        "reason": target_error or "Target is valid",
    }
    schema_version = get_project_schema_version(project_path)
    compatibility_decision = compatibility.get("decision")
    if compatibility_decision == "BLOCK_PROJECT_CORRUPT":
        payload.update(decision="blocked", process_exit_code=6)
        payload["diagnostics"] = [{
            "code": "project_corrupt", "owner": None, "severity": "error",
            "message": str(compatibility.get("rendered_human") or "Project metadata is corrupt"),
        }]
        print(json.dumps(payload, indent=2))
        raise typer.Exit(6)
    if schema_version is not None and not isinstance(schema_version, int):
        _emit_blocked_full_plan(
            project_path=project_path, target=requested_target, project=project,
            no_worktrees=not include_worktrees, confirm=confirm, code=6,
            diagnostic_code="project_corrupt", message="Project metadata schema version is corrupt",
        )
    if isinstance(schema_version, int) and schema_version > MAX_SUPPORTED_SCHEMA:
        payload.update(decision="blocked", process_exit_code=5)
        payload["diagnostics"] = [{
            "code": "cli_upgrade_required", "owner": None, "severity": "error",
            "message": f"Project schema {schema_version} exceeds supported schema {MAX_SUPPORTED_SCHEMA}",
        }]
        print(json.dumps(payload, indent=2))
        raise typer.Exit(5)
    if target_error:
        payload.update(decision="blocked", process_exit_code=2)
        payload["diagnostics"] = [{"code": "invalid_target", "owner": None, "severity": "error", "message": target_error}]
        print(json.dumps(payload, indent=2))
        raise typer.Exit(2)
    try:
        prepared = prepare_upgrade_repairs(project_path, consent=ApplyConsent())
    except Exception as exc:  # noqa: BLE001 - assessment failure is contract data
        payload.update(decision="incomplete", process_exit_code=1)
        payload["diagnostics"] = [{"code": "assessment_failed", "owner": None, "severity": "error", "message": str(exc)}]
        print(json.dumps(payload, indent=2))
        raise typer.Exit(1) from None

    owners = prepared.owners
    roots = {owner.root.root_id: owner.root for owner in owners}
    roots[prepared.root.root_id] = prepared.root
    payload["roots"] = [
        {"id": root.root_id, "scope": root.scope, "path": str(root.path)}
        for root in sorted(roots.values(), key=lambda item: item.root_id)
    ]
    payload["migrations"] = _real_pending_migrations_contract(project_path, target)
    payload["effects"] = [
        {
            "id": effect.id, "phase": effect.phase, "owner": effect.owner,
            "logical_owners": list(effect.logical_owners), "surface_ids": list(effect.surface_ids),
            "root_id": effect.root.root_id, "path": effect.path, "action": effect.action,
            "before": _state_json(effect.before), "after": _state_json(effect.after),
            "reason": effect.reason,
            "ownership": {"kind": effect.ownership[0].kind, "reference": effect.ownership[0].reference},
        }
        for effect in prepared.effects
    ]
    payload["dispositions"] = [
        {"owner": item.owner, "root_id": item.root_id, "path": item.path, "state": item.state, "reason": item.reason}
        for owner in owners for item in owner.dispositions
    ]
    payload["diagnostics"] = [
        {"code": item.code, "owner": item.owner, "severity": item.severity, "message": item.message}
        for item in prepared.diagnostics
    ]
    artifacts: list[dict[str, object]] = []
    for owner in owners:
        for artifact in getattr(owner.prepared, "execution_artifacts", ()):
            if hasattr(artifact, "directory"):
                directory, pattern, purpose = artifact.directory, artifact.name_pattern, artifact.purpose
            else:
                directory, pattern, purpose = artifact
            artifacts.append({
                "owner": owner.owner_key, "root_id": owner.root.root_id,
                "directory": directory, "name_pattern": pattern, "purpose": purpose,
            })
    payload["execution_artifacts"] = artifacts
    payload["complete"] = prepared.complete
    payload["decision"] = "ready" if prepared.complete else "incomplete"
    payload["process_exit_code"] = 0 if prepared.complete else 1
    payload["commit_policy"] = {
        "project_enabled": should_auto_commit(project_path, dry_run=False, manual_review=False),
        "worktrees_enabled": include_worktrees,
        "mission_repair_included": False,
    }
    print(json.dumps(payload, indent=2))
    raise typer.Exit(int(payload["process_exit_code"]))


def _check_upgrade_intent_conflicts(
    *, json_output: bool, plan_json: bool, target: str | None, project: bool, no_worktrees: bool,
) -> None:
    """Preserve the parser conflict contract before dispatching upgrade work."""
    current_context = click.get_current_context(silent=True)
    intent = current_context.meta.get("upgrade_intent") if current_context is not None else None
    if intent is not None and intent.conflicts:
        message = "\n".join(intent.conflicts)
        if json_output or plan_json:
            if plan_json:
                _emit_blocked_full_plan(
                    project_path=Path.cwd(), target=target, project=project,
                    no_worktrees=no_worktrees, confirm=False, code=2,
                    diagnostic_code="incompatible_flags", message=message,
                )
            from specify_cli.compat.planner import Invocation, plan

            payload = dict(plan(Invocation(
                command_path=("upgrade",), raw_args=("--cli", "--project"),
                is_help=False, is_version=False, flag_no_nag=True,
                env_ci=True, stdout_is_tty=False,
            ), read_only=True, project_root_resolver=lambda _path: Path.cwd(), include_migrations=False).rendered_json)
            payload.update(decision="BLOCK_INCOMPATIBLE_FLAGS", case="none", exit_code=2, pending_migrations=[], rendered_human=message[:1024])
            print(json.dumps(payload))
        else:
            console.print(message, markup=False)
        raise typer.Exit(2)


def _load_upgrade_system_with_heal() -> tuple[Any, Any, Any, Any]:
    """Import the upgrade system and auto-discover migrations (#4124 heal seam).

    The lazy imports avoid circular imports; the heal wrapper repairs a stale
    ``.pyc`` bytecode cache (interrupted install) once before treating an
    import failure as real. Returns ``(VersionDetector, MigrationRegistry,
    MigrationRunner, validate_upgrade_target)``.
    """
    from specify_cli.bytecode_heal import invoke_with_bytecode_heal

    def _load() -> tuple[Any, Any, Any, Any]:
        from specify_cli.upgrade.detector import VersionDetector
        from specify_cli.upgrade.migrations import auto_discover_migrations
        from specify_cli.upgrade.registry import MigrationRegistry
        from specify_cli.upgrade.runner import MigrationRunner, validate_upgrade_target

        auto_discover_migrations()
        return VersionDetector, MigrationRegistry, MigrationRunner, validate_upgrade_target

    def _report_heal(removed: int) -> None:
        console.print(
            f"[yellow]Repaired {removed} stale bytecode cache file(s) left by an "
            "interrupted install; migrations reloaded from source.[/yellow]"
        )

    return invoke_with_bytecode_heal(_load, on_healed=_report_heal)


def upgrade(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without applying"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation prompts"),
    target: str | None = typer.Option(None, "--target", help="Target version (defaults to current CLI version)"),
    json_output: bool = typer.Option(False, "--json", help="Output results as JSON"),
    plan_json: bool = typer.Option(False, "--plan-json", help="Output the complete preview plan as JSON"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed migration information"),
    no_worktrees: bool = typer.Option(False, "--no-worktrees", help="Skip upgrading worktrees"),
    # --- WP09 new flags (T034) ---
    cli: bool = typer.Option(False, "--cli", help="Restrict to CLI guidance only; works outside any project (FR-014)"),
    project: bool = typer.Option(False, "--project", help="Restrict to current-project compat + migrations (FR-015)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Non-interactive confirmation; alias for --force (FR-017)"),
    no_nag: bool = typer.Option(False, "--no-nag", help="Suppress upgrade-nag output explicitly"),
    agent_check: bool = typer.Option(False, "--agent-check", help="Emit agent-host upgrade prompt JSON", hidden=True),
    agent_choice: str | None = typer.Option(None, "--agent-choice", help="Record an agent-host upgrade choice", hidden=True),
    agent_latest: str | None = typer.Option(None, "--agent-latest", help="Latest version for --agent-choice", hidden=True),
) -> None:
    """Upgrade a Spec Kitty project to the current version.

    Detects the project's current version and applies all necessary migrations
    to bring it up to date with the installed CLI version.

    **New flags (WP09)**:
      ``--cli``     Emit CLI upgrade guidance only.  No project detection;
                    succeeds outside any project (FR-014).
      ``--project`` Run project migrations only; suppresses CLI nag.
                    Errors outside a project.
      ``--yes``/``-y``  Non-interactive confirmation (alias for ``--force``).
                        Does NOT bypass schema-incompatibility blocks (CHK037/A-006).
      ``--no-nag``  Suppress upgrade-nag banner even when a CLI update exists.

    Mutual exclusion: ``--cli`` and ``--project`` together exit 2.

    **Exit codes** (R-08):
      0  Success / ALLOW / ALLOW_WITH_NAG / any ``--dry-run``
      2  ``--cli --project`` flag conflict
      4  Project migration required (BLOCK_PROJECT_MIGRATION)
      5  Project is too new for this CLI (BLOCK_CLI_UPGRADE) — not bypassable
      6  Project metadata corrupt (BLOCK_PROJECT_CORRUPT)
      1  General error

    See also: ``docs/guides/install-and-upgrade.md``

    Examples:
        spec-kitty upgrade              # Upgrade to current version
        spec-kitty upgrade --dry-run    # Preview changes
        spec-kitty upgrade --target 0.6.5  # Upgrade to specific version
        spec-kitty upgrade --cli        # Show CLI upgrade hint, no project needed
        spec-kitty upgrade --project    # Project migrations only
        spec-kitty upgrade --yes        # Non-interactive (same as --force)
        spec-kitty upgrade --dry-run --json  # Machine-readable plan
    """
    _check_upgrade_intent_conflicts(
        json_output=json_output, plan_json=plan_json, target=target, project=project, no_worktrees=no_worktrees,
    )

    _dispatch_agent_flags(
        agent_check=agent_check,
        agent_choice=agent_choice,
        agent_latest=agent_latest,
        json_output=json_output,
    )

    # T034 — mutual exclusion check
    if cli and project:
        console.print("[red]Error:[/red] --cli and --project are mutually exclusive.")
        console.print("[dim]Use --cli for CLI guidance only, or --project for project migrations only.[/dim]")
        raise typer.Exit(2)

    # T034 — --yes aliases --force (both remain functional)
    confirm = (yes is True) or (force is True)

    # T035 — --cli mode: project-agnostic CLI guidance
    if cli:
        _run_cli_mode(
            json_output=json_output,
            dry_run=dry_run,
            no_nag=no_nag,
        )
        return  # _run_cli_mode always raises typer.Exit; belt-and-suspenders

    # --- Project-mode and default upgrade flow ---

    # T036/T019 — in --project mode, fail fast outside a project; the
    # default (bare) invocation falls back to --cli guidance instead.
    project_path = Path.cwd()
    kittify_dir = project_path / ".kittify"
    if plan_json and not _is_in_project(project_path):
        _emit_blocked_full_plan(
            project_path=project_path, target=target, project=project,
            no_worktrees=no_worktrees, confirm=False, code=1,
            diagnostic_code="project_not_initialized", message="Not a Spec Kitty project",
        )
    _guard_project_or_fallback_to_cli(
        project_path,
        project=project,
        json_output=json_output,
        dry_run=dry_run,
        no_nag=no_nag,
    )

    if plan_json:
        _run_full_plan_json(
            project_path=project_path,
            requested_target=target,
            project=project,
            include_worktrees=not no_worktrees,
            confirm=False,
        )

    # CHK037 / A-006 — Check if project is too new for this CLI.
    # This check runs BEFORE the existing upgrade flow so that
    # --yes / --force do NOT bypass the block.
    # The upgrade command is SAFE (remediation path), so the planner's
    # decide() would ALLOW it, but the command itself must refuse to
    # run migrations against a project with schema > MAX_SUPPORTED.
    _check_project_not_too_new(project_path, json_output=json_output)

    # T037 — --json with compat-planner contract (for --project or default with --json)
    # When --json is passed (with or without --dry-run), we emit the contract
    # from contracts/compat-planner.json in addition to (or instead of) the
    # old project-upgrade JSON.  For --project mode, the planner is always
    # consulted; for default mode, the planner runs only when --json is used.
    if json_output and (project or dry_run):
        # Emit compat-planner contract. FR-009: the pending set is computed
        # against the same target the real run would use (explicit --target, or
        # the installed CLI version) so the preview matches the applied set.
        _run_planner_json(
            dry_run=dry_run,
            no_nag=no_nag,
            project_path=project_path,
            target_version=_resolve_upgrade_target(target),
        )
        return  # _run_planner_json always raises typer.Exit

    if not json_output:
        show_banner()

    baseline_changed_paths = capture_upgrade_baseline(project_path)

    # Import upgrade system (lazy to avoid circular imports), healing a stale
    # bytecode cache once if the import chain is broken by an interrupted
    # install (#4124).
    VersionDetector, MigrationRegistry, MigrationRunner, validate_upgrade_target = (
        _load_upgrade_system_with_heal()
    )

    # Detect current version
    detector = VersionDetector(project_path)
    current_version = detector.detect_version()

    # Determine target version
    target_version = _resolve_upgrade_target(target)

    validation_error = validate_upgrade_target(current_version, target_version)
    _reject_downgrade_target(
        validation_error,
        current_version=current_version,
        target_version=target_version,
        json_output=json_output,
    )

    if not json_output:
        console.print(f"[cyan]Current version:[/cyan] {current_version}")
        console.print(f"[cyan]Target version:[/cyan]  {target_version}")
        console.print()

    # Get needed migrations
    # Handle "unknown" version by treating it as very old (0.0.0)
    version_for_migration = "0.0.0" if current_version == "unknown" else current_version
    migrations_needed = MigrationRegistry.get_applicable(version_for_migration, target_version, project_path=project_path)

    manual_review_paths: list[str] = []
    if not migrations_needed:
        outcome = _build_no_migrations_outcome(
            project_path=project_path,
            kittify_dir=kittify_dir,
            current_version=current_version,
            target_version=target_version,
            dry_run=dry_run,
            no_worktrees=no_worktrees,
        )
    else:
        _show_migration_plan_and_confirm(
            migrations_needed,
            project_path=project_path,
            json_output=json_output,
            dry_run=dry_run,
            verbose=verbose,
            confirm=confirm,
        )

        # auto_commit: the runner commits each worktree's upgrade churn on its
        # own branch (#2385) so a later `spec-kitty merge` isn't blocked by
        # dirty coord/lane worktrees. D-10: the worktree-scope decision, not a
        # bare `not dry_run`. The main checkout is committed by the finalizer
        # below.
        result = MigrationRunner(project_path, console).upgrade(
            target_version,
            dry_run=dry_run,
            force=confirm,  # pass the unified confirm flag
            include_worktrees=not no_worktrees,
            auto_commit=should_auto_commit_for_worktree(project_path, dry_run=dry_run),
        )
        manual_review_paths = _collect_manual_review_paths(result.migration_results)
        if manual_review_paths:
            result.warnings.append("Skipped auto-commit because the upgrade preserved customized files that require manual review.")
        outcome = UpgradeOutcome(
            result=result,
            manual_review_paths=[Path(p) for p in manual_review_paths],
            worktree_failures=list(result.worktree_failures),
        )

    # T017/C4 — one shared tail: wire the finalizer with the step
    # implementations as injected callables (the finalizer itself does not
    # import cli.commands — see upgrade/finalize.py's module docstring).
    should_commit_main = should_auto_commit(
        project_path, dry_run=dry_run, manual_review=bool(outcome.manual_review_paths)
    )
    render_ctx = _FinalizerRenderContext()
    preparation_errors: tuple[str, ...] = ()
    if not dry_run and outcome.result.success:
        preparation_errors = _prepare_finalizer_repairs(project_path, render_ctx)

    from specify_cli.upgrade.finalize import finalize_upgrade

    outcome = finalize_upgrade(
        outcome,
        provision_activations=functools.partial(_finalizer_step_provision, project_path, dry_run=dry_run, prepared=render_ctx.prepared_repairs),
        run_surface_repair=functools.partial(
            _finalizer_step_surface_repair,
            outcome,
            render_ctx,
            project_path=project_path,
            confirm=confirm,
            dry_run=dry_run,
            json_output=json_output,
        ),
        commit_churn=functools.partial(
            _finalizer_step_commit_churn,
            outcome,
            render_ctx,
            project_path=project_path,
            baseline_changed_paths=baseline_changed_paths,
        ),
        offer_repair=functools.partial(
            _finalizer_step_offer_repair,
            outcome,
            project_path=project_path,
            confirm=confirm,
            dry_run=dry_run,
            json_output=json_output,
        ),
        should_commit=should_commit_main,
        repair_preflight=_finalizer_repair_preflight(render_ctx.prepared_repairs, preparation_errors),
    )

    surface_repair_summary = render_ctx.surface_repair_summary
    if render_ctx.commit_warning:
        outcome.result.warnings.append(render_ctx.commit_warning)
    auto_commit_paths = list(render_ctx.commit_paths)
    # Human-mode-only (FR-003/US2 scenario 1): the JSON contract already
    # reports the config opt-out honestly via `auto_committed: false`, so
    # this extra churn-detection git-status call is skipped for `--json`.
    left_uncommitted = not json_output and _churn_left_uncommitted_by_config(
        outcome,
        dry_run=dry_run,
        should_commit_main=should_commit_main,
        project_path=project_path,
        baseline_changed_paths=baseline_changed_paths,
    )

    if json_output:
        json_payload = (
            _build_migration_json_payload(
                outcome,
                migrations_needed,
                manual_review_paths=manual_review_paths,
                auto_commit_paths=auto_commit_paths,
                surface_repair_summary=surface_repair_summary,
            )
            if migrations_needed
            else _build_no_migrations_json_payload(
                outcome,
                auto_commit_paths=auto_commit_paths,
                surface_repair_summary=surface_repair_summary,
            )
        )
        print(json.dumps(json_payload))
    elif migrations_needed:
        _display_upgrade_results(
            outcome.result,
            manual_review_paths=manual_review_paths,
            auto_committed=outcome.committed,
            auto_commit_paths=auto_commit_paths,
            effective_success=outcome.effective_success,
            errors=_combined_errors(outcome, surface_repair_summary),
            left_uncommitted=left_uncommitted,
        )
    else:
        _display_no_migrations_results(
            outcome, auto_commit_paths=auto_commit_paths, left_uncommitted=left_uncommitted
        )
        # Dry-run parity: the finalizer provisions mission_type_activations on
        # BOTH the migration and no-migrations paths (upgrade/finalize.py — the
        # single tail), so an up-to-date project still missing the key is seeded
        # on a real run. The migration path previews that via
        # _show_migration_plan_and_confirm; the up-to-date path must too, or a
        # --dry-run silently under-reports the pending seed (no-ops for --json
        # and outside dry-run).
        _print_dry_run_provisioning_notice(
            project_path, dry_run=dry_run, json_output=json_output
        )

    # D-5 — the exit code is derived exactly once, here, from the finalized
    # outcome. No other site in the tail may raise typer.Exit. A successful
    # outcome falls through to a bare return (exit code 0 either via Click's
    # normal command-return path, or — for tests that call this function
    # directly — without raising at all, matching the pre-refactor contract).
    if outcome.exit_code != 0:
        raise typer.Exit(outcome.exit_code)


def _print_upgrade_section(header: str, items: list[str], item_prefix: str) -> None:
    """Print a titled list section, emitting nothing when *items* is empty."""
    if not items:
        return
    console.print(header)
    for item in items:
        console.print(f"{item_prefix}{item}")


def _display_upgrade_results(
    result: UpgradeResult,
    *,
    manual_review_paths: list[str],
    auto_committed: bool,
    auto_commit_paths: list[str],
    effective_success: bool,
    errors: list[str],
    left_uncommitted: bool = False,
) -> None:
    """Render the human-readable upgrade outcome.

    Pure rendering (T022, FR-008/#3392): this function never raises. The
    caller derives the exit code exactly once, from
    ``UpgradeOutcome.exit_code`` (D-5), after every renderer has run.

    WP02 / FR-013 (#1784 P3 crumb): a ``--dry-run`` invocation must never print
    a success line implying changes were applied — the closing line is
    dry-run-specific ("Dry run complete — no changes applied."), while a real
    successful run keeps the "Upgrade complete!" line unchanged.

    ``effective_success``/``errors`` come from the finalized
    ``UpgradeOutcome`` rather than ``result.success``/``result.errors``
    directly: activation errors and surface-repair drift are finalizer-owned
    signals that are not folded into ``result`` itself (D-3).
    """
    console.print()

    if result.dry_run:
        console.print(
            Panel(
                "[yellow]DRY RUN[/yellow] - No changes were made",
                border_style="yellow",
            )
        )

    _print_upgrade_section("[green]Migrations applied:[/green]", result.migrations_applied, "  [green]✓[/green] ")
    _print_upgrade_section(
        "[dim]Migrations skipped (already applied or not needed):[/dim]",
        result.migrations_skipped,
        "  [dim]○[/dim] ",
    )
    _print_upgrade_section("[yellow]Warnings:[/yellow]", result.warnings, "  [yellow]![/yellow] ")
    _print_upgrade_section("[red]Errors:[/red]", errors, "  [red]✗[/red] ")
    _print_upgrade_section("[yellow]Manual review required:[/yellow]", manual_review_paths, "  [yellow]![/yellow] ")

    console.print()
    if not effective_success:
        console.print("[bold red]Upgrade failed.[/bold red]")
        return
    if result.dry_run:
        # Honest dry-run: nothing was applied, so do not imply it was.
        console.print(f"[bold yellow]Dry run complete[/bold yellow] — no changes applied. ({result.from_version} -> {result.to_version} previewed)")
    else:
        console.print(f"[bold green]Upgrade complete![/bold green] {result.from_version} -> {result.to_version}")
        if auto_committed:
            console.print(f"[cyan]→ Auto-committed upgrade changes ({len(auto_commit_paths)} files)[/cyan]")
        elif left_uncommitted:
            console.print(_LEFT_UNCOMMITTED_MESSAGE)


# ---------------------------------------------------------------------------
# T037 — planner JSON helper (emits compat-planner.json contract)
# ---------------------------------------------------------------------------


def _real_pending_migrations_contract(project_path: Path, target_version: str) -> list[dict[str, object]]:
    """Return the contract-shaped pending-migration list the real run applies.

    Drives the preview through :meth:`VersionDetector.applicable_migrations`
    (→ :meth:`MigrationRegistry.get_applicable`) — the *same* selector the real
    ``upgrade`` run uses — so the reported pending set can never under-report
    the applied set (FR-009 / SC-004). The dict shape matches
    ``compat.messages.render_json``'s ``pending_migrations`` entries.

    Args:
        project_path: Root of the project directory.
        target_version: Version the real run would target.

    Returns:
        A list of ``{migration_id, target_schema_version, description,
        files_modified}`` dicts, in application order.
    """
    from specify_cli.compat.planner import _migration_step_from
    from specify_cli.upgrade.detector import VersionDetector

    steps = [_migration_step_from(m) for m in VersionDetector(project_path).applicable_migrations(target_version)]
    return [
        {
            "migration_id": step.migration_id,
            "target_schema_version": int(step.target_schema_version),
            "description": step.description,
            "files_modified": ([str(f) for f in step.files_modified] if step.files_modified is not None else None),
        }
        for step in steps
    ]


def _run_planner_json(
    *,
    dry_run: bool,
    no_nag: bool,
    project_path: Path,
    target_version: str,
    latest_version_provider: object = None,
) -> None:
    """Emit the compat-planner JSON contract to stdout and raise typer.Exit.

    Suppresses all human output.  Exit code follows R-08 unless ``dry_run``
    is True, except for a stronger refusal or incomplete supporting-repair preview.

    FR-009: the compat planner gates its own ``pending_migrations`` on a block
    decision, so a schema-compatible-but-stale project would preview ``[]``.
    Here we overwrite that field with the *real* applied set (the same
    ``MigrationRegistry.get_applicable`` selection the real run uses) so the
    preview never under-reports the migrations a real run would apply.

    The ``mission_type_activations`` provisioning seed (the second FR-009
    divergence) is surfaced on the human ``--dry-run`` preview
    (:func:`_print_dry_run_provisioning_notice`) rather than here: the
    ``compat-planner.json`` contract is externally frozen
    (``additionalProperties: false``) and owns no provisioning field, so the
    machine surface stays contract-clean.

    Args:
        dry_run: Preview without writes; incomplete repair assessment fails closed.
        no_nag: Suppress nag flag passed to the Invocation.
        project_path: Root of the project being previewed.
        target_version: Resolved target version for the pending-set computation.
        latest_version_provider: Optional override for tests.
    """
    from specify_cli.compat.planner import Invocation, is_ci_env, plan

    raw_args: tuple[str, ...] = ("--project",)
    if dry_run:
        raw_args = raw_args + ("--dry-run",)

    # Keep the real environment for output policy; JSON preview still queries
    # the version when stdout is piped or CI is set.
    invocation = Invocation(
        # Emit the compatibility plan for normal project-mutating commands.
        # ``upgrade`` itself is registered SAFE so users can remediate stale
        # schemas; using it here would hide project_migration_needed.
        command_path=_PROJECT_COMPAT_CHECK_COMMAND,
        raw_args=raw_args,
        is_help=False,
        is_version=False,
        flag_no_nag=no_nag,
        env_ci=is_ci_env(),
        stdout_is_tty=sys.stdout.isatty(),
    )

    kwargs: dict[str, object] = {}
    if latest_version_provider is not None:
        kwargs["latest_version_provider"] = latest_version_provider

    from specify_cli.upgrade.detector import VersionDetector
    from specify_cli.upgrade.runner import validate_upgrade_target

    current_version = VersionDetector(project_path).detect_version()
    validation_error = validate_upgrade_target(current_version, target_version)
    result = plan(invocation, read_only=True, query_latest=True, include_migrations=False, **kwargs)  # type: ignore[arg-type]

    payload = dict(result.rendered_json)
    semantic_code = result.exit_code
    if validation_error:
        payload["pending_migrations"] = []
        semantic_code = _legacy_target_refusal(payload, validation_error, semantic_code)
    else:
        payload["pending_migrations"] = _real_pending_migrations_contract(project_path, target_version)

    exit_code = 0 if dry_run and semantic_code != 5 else semantic_code
    if dry_run and not validation_error and semantic_code not in {2, 5, 6}:
        notice, incomplete = _supporting_repair_preview(project_path)
        if notice:
            # Keep the diagnostic prefix within the JSON text budget even if a
            # future notice grows; compatibility text keeps the remaining room.
            compatibility = str(payload["rendered_human"])
            notice = notice[:1023]
            payload["rendered_human"] = compatibility[: max(0, 1023 - len(notice))] + "\n" + notice
        if incomplete:
            exit_code = 1
            payload["exit_code"] = exit_code
    print(json.dumps(payload, indent=2))
    raise typer.Exit(exit_code)


def _legacy_target_refusal(payload: dict[str, object], reason: str, semantic_code: int) -> int:
    """Project target refusal without changing truthful schema compatibility."""
    stronger = {"BLOCK_PROJECT_CORRUPT", "BLOCK_CLI_UPGRADE", "BLOCK_PROJECT_MIGRATION"}
    if payload["decision"] in stronger:
        payload["rendered_human"] = str(payload["rendered_human"])[:512] + "\n" + reason[:511]
        return semantic_code
    payload.update(decision="BLOCK_INCOMPATIBLE_FLAGS", case="none", exit_code=2, rendered_human=reason)
    return 2


__all__ = ["upgrade"]
