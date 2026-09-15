"""Mission-state audit / repair / teamspace-dry-run cluster for ``doctor`` (WP06, #2059).

Extracts Cluster H out of ``doctor.py``. The ``mission-state`` command is already
dispatch-thin (it delegates to ``_validate_modes`` / ``_run_*`` helpers); those
helpers move here so the command shell in ``doctor.py`` becomes a pure dispatch
shell well under the complexity ceiling — the ``# noqa: C901`` it used to carry
is dropped (NFR-003: no unnecessary suppressions).

Import discipline (one-way, I-2): imports shared infra from
:mod:`._doctor_shared`; never imports ``doctor.py``.
"""

from __future__ import annotations

import enum as _enum
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, cast

import typer
from rich.table import Table

from specify_cli.core.paths import locate_project_root

from ._doctor_shared import _emit_not_in_project, console

if TYPE_CHECKING:
    from specify_cli.audit import Severity

# ``__all__`` lists this sibling's single cross-module entrypoint. The dispatch
# helpers are intra-module (used here + by this module's own unit tests) and are
# deliberately NOT exported — listing them would register orphan public symbols
# under the dead-symbol gate (tests/architectural/test_no_dead_symbols).
__all__ = [
    "run_mission_state",
]


class _RootUnset:
    """Sentinel: caller omitted ``repo_root``, so resolve it here.

    ``None`` is a *valid* resolved root (fixtures-only run), so the
    "not passed" state needs a dedicated sentinel rather than ``None``.
    """


_ROOT_UNSET = _RootUnset()


def _print_rich_audit_report(report: object) -> None:
    """Print a Rich table summarising audit findings per mission."""
    from specify_cli.audit import RepoAuditReport

    assert isinstance(report, RepoAuditReport)

    missions_with_findings = [r for r in report.missions if r.findings]

    if not missions_with_findings:
        console.print("[green]No findings — all missions are clean.[/green]")
        return

    table = Table(box=None, padding=(0, 2), show_edge=False)
    table.add_column("Mission", style="cyan", min_width=28)
    table.add_column("Errors", justify="right", min_width=7)
    table.add_column("Warnings", justify="right", min_width=9)
    table.add_column("Info", justify="right", min_width=6)
    table.add_column("Codes")

    for result in missions_with_findings:
        from specify_cli.audit.models import Severity

        errors = sum(1 for f in result.findings if f.severity == Severity.ERROR)
        warnings = sum(1 for f in result.findings if f.severity == Severity.WARNING)
        infos = sum(1 for f in result.findings if f.severity == Severity.INFO)
        codes = ", ".join(sorted({f.code for f in result.findings}))

        err_str = f"[red]{errors}[/red]" if errors else str(errors)
        warn_str = f"[yellow]{warnings}[/yellow]" if warnings else str(warnings)
        table.add_row(result.mission_slug, err_str, warn_str, str(infos), codes)

    console.print(table)
    console.print()

    summary = report.repo_summary
    console.print(
        f"Total missions: {summary['total_missions']} | "
        f"With errors: {summary['missions_with_errors']} | "
        f"With warnings: {summary['missions_with_warnings']} | "
        f"TeamSpace blockers: {summary['teamspace_blockers']}"
    )


def _audit_fixture_root() -> Path:
    """Return the packaged mission-state audit fixture root."""
    return Path(__file__).resolve().parents[2] / "audit" / "fixtures"


class _MissionStateMode(_enum.Enum):
    """Dispatch mode for the mission-state command."""

    AUDIT = "audit"
    FIX = "fix"
    TEAMSPACE_DRY_RUN = "teamspace_dry_run"


def _validate_modes(audit: bool, fix: bool, teamspace_dry_run: bool) -> _MissionStateMode:
    """Validate mutually exclusive mode flags and return the active Mode.

    Raises typer.Exit(0) if no mode was selected (with usage hint).
    Raises typer.Exit(2) if more than one mode was selected.
    """
    selected_modes = sum(1 for selected in (audit, fix, teamspace_dry_run) if selected)
    if selected_modes == 0:
        typer.echo("Use --audit, --fix, or --teamspace-dry-run. See --help for options.")
        raise typer.Exit(0)
    if selected_modes > 1:
        typer.echo("Choose exactly one of --audit, --fix, or --teamspace-dry-run.", err=True)
        raise typer.Exit(2)
    if fix:
        return _MissionStateMode.FIX
    if teamspace_dry_run:
        return _MissionStateMode.TEAMSPACE_DRY_RUN
    return _MissionStateMode.AUDIT


def _resolve_fail_on(fail_on: str | None) -> tuple[Severity | None, bool]:
    """Parse --fail-on into (severity, teamspace_blocker_flag).

    Returns (None, False) when fail_on is None.
    Raises typer.Exit(2) on invalid values.
    """
    from specify_cli.audit import Severity

    if fail_on is None:
        return None, False
    if fail_on == "teamspace-blocker":
        return None, True
    try:
        return Severity(fail_on), False
    except ValueError:
        valid = ", ".join([*(s.value for s in Severity), "teamspace-blocker"])
        typer.echo(
            f"Invalid --fail-on value: {fail_on!r}. Valid values: {valid}",
            err=True,
        )
        raise typer.Exit(2) from None


def _resolve_audit_root(
    fixture_dir: Path | None,
    include_fixtures: bool,
    repo_root: Path | None | _RootUnset = _ROOT_UNSET,
    *,
    json_output: bool = False,
) -> tuple[Path, Path | None]:
    """Resolve the effective (repo_root, fixture_dir) pair.

    Handles --include-fixtures / --fixture-dir interplay and project-root
    discovery. Returns (repo_root, fixture_dir).

    ``repo_root`` is the project root resolved by the ``doctor mission-state``
    command shell through its patchable ``locate_project_root`` seam (#2059
    decomposition keeps the seam in the shim — see ``run_workspaces``). It is
    sentinel-typed via ``_ROOT_UNSET`` so callers that pass an explicit
    ``None`` (no project found, fixtures-only) are honored, while direct
    callers that omit it fall back to discovering the root here.

    ``json_output`` defaults to ``False`` so direct callers (this module's own
    unit tests) that omit it keep the existing human-prose behavior; the
    ``doctor mission-state`` dispatch entrypoint (``run_mission_state``)
    threads its own ``json_output`` through so both terminal not-in-project
    branches honor ``--json`` (#4242 class-closing fold).

    Raises typer.Exit(1) if no repo root can be found.
    Raises typer.Exit(2) if --include-fixtures and --fixture-dir conflict,
    or the bundled fixture root is missing.
    """
    resolved_fixture_dir = fixture_dir
    if include_fixtures:
        if resolved_fixture_dir is not None:
            typer.echo("Use only one of --include-fixtures or --fixture-dir.", err=True)
            raise typer.Exit(2)
        resolved_fixture_dir = _audit_fixture_root()
        if not resolved_fixture_dir.is_dir():
            typer.echo(f"Bundled audit fixtures not found: {resolved_fixture_dir}", err=True)
            raise typer.Exit(2)

    if isinstance(repo_root, _RootUnset):
        try:
            resolved_repo_root = locate_project_root()
        except Exception as exc:
            _emit_not_in_project(json_output)
            raise typer.Exit(1) from exc
    else:
        resolved_repo_root = repo_root

    if resolved_repo_root is None:
        if resolved_fixture_dir is None:
            _emit_not_in_project(json_output)
            raise typer.Exit(1)
        resolved_repo_root = resolved_fixture_dir.parent

    return resolved_repo_root, resolved_fixture_dir


def _emit_mission_state(report: object, *, json_output: bool, pretty_renderer: Callable[[object], None]) -> None:
    """Emit a mission-state report as JSON or via a pretty renderer.

    Collapses the triplicated 'if json_output: dump JSON else: pretty-print'
    pattern across the three dispatch arms.
    """
    if json_output:
        sys.stdout.write(report.to_json())  # type: ignore[attr-defined]
        sys.stdout.flush()
    else:
        pretty_renderer(report)


def _heal_duplicate_key_artifacts(
    repo_root: Path,
    fixture_dir: Path | None,
    allow_dirty: bool,
    json_output: bool,
) -> None:
    """Opt-in FR-008 heal: repair legacy dual-key ``review_feedback`` artifacts.

    Runs as part of ``--fix`` (``doctor`` itself is unconditionally SAFE), before
    the mission-state canonicalization, so a project is healed *before* an
    upgrade trips over the invalid YAML. Batch-atomic + non-destructive; an
    un-repairable artifact aborts with a non-zero exit and leaves the corpus
    untouched.
    """
    from specify_cli.migration.mission_state import (
        MissionStateRepairError,
        repair_duplicate_key_artifacts,
    )
    from specify_cli.status import DuplicateKeyRepairError

    try:
        report = repair_duplicate_key_artifacts(
            repo_root, scan_root=fixture_dir, allow_dirty=allow_dirty
        )
    except (DuplicateKeyRepairError, MissionStateRepairError) as exc:
        if json_output:
            _emit_json_error("DUPLICATE_KEY_REPAIR_FAILED", message=str(exc))
        else:
            typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc

    healed = sum(len(result.file_changes) for result in report.missions)
    if healed and not json_output:
        console.print(
            f"[green]Healed {healed} duplicate-key artifact(s)[/green] "
            f"(keep-last-non-empty). Manifest: {report.manifest_path}"
        )


def _run_mission_repair(
    repo_root: Path,
    fixture_dir: Path | None,
    mission: str | None,
    manifest_path: Path | None,
    allow_dirty: bool,
    json_output: bool,
) -> None:
    """Execute the --fix dispatch arm: repair repo and emit the manifest."""
    from specify_cli.migration.mission_state import MissionStateRepairError, repair_repo

    # FR-008: heal legacy dual-key artifacts before mission-state canonicalization.
    _heal_duplicate_key_artifacts(repo_root, fixture_dir, allow_dirty, json_output)

    try:
        report = repair_repo(
            repo_root,
            scan_root=fixture_dir,
            mission=mission,
            manifest_path=manifest_path,
            allow_dirty=allow_dirty,
        )
    except MissionStateRepairError as exc:
        if json_output:
            sys.stdout.write(json.dumps({"error": "MISSION_STATE_REPAIR_FAILED", "message": str(exc)}) + "\n")
            sys.stdout.flush()
        else:
            typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc

    def _pretty_repair(r: object) -> None:
        summary = r.to_dict()["summary"]  # type: ignore[attr-defined]
        assert isinstance(summary, dict)
        console.print(
            "[green]Mission-state repair complete[/green] "
            f"(updated={summary['missions_updated']}, "
            f"unchanged={summary['missions_unchanged']}, "
            f"errors={summary['missions_error']})."
        )
        console.print(f"Manifest: {r.manifest_path}")  # type: ignore[attr-defined]

    _emit_mission_state(report, json_output=json_output, pretty_renderer=_pretty_repair)
    if any(result.status == "error" for result in report.missions):
        raise typer.Exit(1)


def _run_teamspace_dry_run_mode(
    repo_root: Path,
    fixture_dir: Path | None,
    mission: str | None,
    json_output: bool,
) -> None:
    """Execute the --teamspace-dry-run dispatch arm: synthesize and validate envelopes."""
    from specify_cli.migration.mission_state import (
        MissionStateDryRunError,
        TeamspaceDryRunReport,
    )
    from specify_cli.migration.mission_state import teamspace_dry_run as run_teamspace_dry_run

    try:
        dry_run_report = run_teamspace_dry_run(
            repo_root,
            scan_root=fixture_dir,
            mission=mission,
        )
    except MissionStateDryRunError as exc:
        if json_output:
            sys.stdout.write(json.dumps({"error": "TEAMSPACE_DRY_RUN_FAILED", "message": str(exc)}) + "\n")
            sys.stdout.flush()
        else:
            typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc

    def _pretty_dry_run(r: object) -> None:
        # pretty_renderer is typed Callable[[object], None] so one shape serves both
        # the repair and dry-run reports; narrow to the concrete dry-run report here
        # so attribute access type-checks without per-line suppressions.
        report = cast(TeamspaceDryRunReport, r)
        if report.valid:
            console.print(
                "[green]TeamSpace dry-run valid[/green] "
                f"({report.envelope_count} envelopes, "
                f"spec-kitty-events {report.events_package_version})."
            )
        else:
            console.print(
                "[red]TeamSpace dry-run failed[/red] "
                f"({len(report.errors)} validation errors)."
            )

    _emit_mission_state(dry_run_report, json_output=json_output, pretty_renderer=_pretty_dry_run)
    if not dry_run_report.valid:
        raise typer.Exit(1)


def _emit_json_error(error_code: str, **extra: object) -> None:
    """Write a JSON error envelope to stdout and flush."""
    payload = {"error": error_code, **extra}
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def _audit_fail_gate(
    report: object,
    fail_on_severity: Severity | None,
    fail_on_teamspace_blocker: bool,
) -> None:
    """Raise typer.Exit(1) if any finding meets the --fail-on gate."""
    from specify_cli.audit.models import is_teamspace_blocker

    if fail_on_severity is not None and any(
        f.severity <= fail_on_severity
        for result in report.missions  # type: ignore[attr-defined]
        for f in result.findings
    ):
        raise typer.Exit(1)
    if fail_on_teamspace_blocker and any(
        is_teamspace_blocker(f)
        for result in report.missions  # type: ignore[attr-defined]
        for f in result.findings
    ):
        raise typer.Exit(1)


def _run_audit_mode(
    repo_root: Path,
    fixture_dir: Path | None,
    mission: str | None,
    fail_on_severity: Severity | None,
    fail_on_teamspace_blocker: bool,
    json_output: bool,
) -> None:
    """Execute the --audit dispatch arm: run the audit engine and emit findings."""
    from specify_cli.audit import AuditOptions, build_report_json, run_audit
    from specify_cli.context.mission_resolver import AmbiguousHandleError, MissionNotFoundError

    options = AuditOptions(
        repo_root=repo_root,
        scan_root=fixture_dir,
        mission_filter=mission,
        fail_on=fail_on_severity,
        invoking_cwd=Path.cwd(),
    )
    try:
        report = run_audit(options)
    except MissionNotFoundError as exc:
        if json_output:
            _emit_json_error("MISSION_NOT_FOUND", handle=mission)
        else:
            typer.echo(f"Error: Mission not found: {mission!r}", err=True)
        raise typer.Exit(1) from exc
    except AmbiguousHandleError as exc:
        if json_output:
            _emit_json_error("AMBIGUOUS_HANDLE", handle=mission)
        else:
            typer.echo(f"Error: Ambiguous handle: {mission!r}", err=True)
        raise typer.Exit(1) from exc

    if json_output:
        sys.stdout.write(build_report_json(report))
        sys.stdout.flush()
    else:
        _print_rich_audit_report(report)

    _audit_fail_gate(report, fail_on_severity, fail_on_teamspace_blocker)


def _refuse_foreign_lane_fix(resolved_root: Path) -> None:
    """Fail closed when a foreign-lane ``--fix`` would canonicalize the primary.

    Preserves the deliberate #2320 primary status-home (``resolved_root`` is the
    already-re-anchored primary) but refuses to write it *silently* from a lane
    worktree that does not own it. Owner / explicit-root invocations are a no-op
    (the guard returns no refusal). #3051/#3541.
    """
    from specify_cli.migration.mission_state import (
        MissionStateWriteRefused,
        enforce_primary_write_ownership,
    )

    try:
        enforce_primary_write_ownership(Path.cwd(), resolved_root)
    except MissionStateWriteRefused as exc:
        console.print(f"[red]Refusing --fix:[/red] {exc}")
        raise typer.Exit(1) from exc


def _surface_audit_disagreement(
    resolved_root: Path, mission: str | None, json_output: bool
) -> bool:
    """Report an honest invoking-checkout-vs-primary disagreement for ``--audit``.

    Returns ``True`` when a disagreement was found (the caller then fails closed
    so the false-green — reading the redirected primary at both ends — cannot be
    reported as agreement). ``False`` when the invocation owns the primary (the
    common case) or targets an explicit/fixture root. #3051/#3541.
    """
    from specify_cli.migration.mission_state import (
        CheckoutDisagreement,
        audit_invocation_disagreement,
    )

    disagreements: list[CheckoutDisagreement] = audit_invocation_disagreement(
        Path.cwd(), resolved_root, mission=mission
    )
    if not disagreements:
        return False
    if json_output:
        sys.stderr.write(
            json.dumps(
                {
                    "warning": "CHECKOUT_STATE_DISAGREEMENT",
                    "primary_root": str(resolved_root),
                    "disagreements": [d.to_dict() for d in disagreements],
                }
            )
            + "\n"
        )
        sys.stderr.flush()
    else:
        console.print(
            "[red]Audit disagreement:[/red] this checkout's mission state "
            "differs from the canonical primary. Reporting the honest mismatch "
            "(NOT a false-green from reading the primary at both ends):"
        )
        for item in disagreements:
            console.print(
                f"  - {item.mission_slug}/{item.artifact}: invoking != primary"
            )
    return True


def run_mission_state(
    *,
    audit: bool,
    fix: bool,
    teamspace_dry_run: bool,
    json_output: bool,
    mission: str | None,
    fail_on: str | None,
    fixture_dir: Path | None,
    include_fixtures: bool,
    manifest_path: Path | None,
    allow_dirty: bool,
    repo_root: Path | None | _RootUnset = _ROOT_UNSET,
) -> None:
    """Dispatch entry point for ``doctor mission-state`` (mode-exclusive contract).

    ``repo_root`` is forwarded by the ``doctor mission-state`` command shell,
    which resolves it through the shim's patchable ``locate_project_root`` seam
    (#2059 — mirrors ``run_workspaces``). Omitting it makes this helper discover
    the root itself, preserving the standalone entrypoint contract.
    """
    mode = _validate_modes(audit, fix, teamspace_dry_run)
    fail_on_severity, fail_on_teamspace_blocker = _resolve_fail_on(fail_on)
    resolved_root, resolved_fixture_dir = _resolve_audit_root(
        fixture_dir, include_fixtures, repo_root, json_output=json_output
    )

    # Unify audit + fix on ONE canonical-root authority (#2320 follow-up). The
    # ``--fix`` path already re-anchors to the primary main-checkout inside
    # ``repair_repo`` (``_anchor_repair_root`` → ``resolve_canonical_root``), but
    # ``--audit`` read the root as-resolved by ``locate_project_root`` (a
    # *conditional* anchor that stops at the CWD's worktree). From a non-primary
    # cwd the two modes therefore diverged: audit could read a stale worktree
    # while fix wrote the primary. Re-anchor the shared root through the same
    # helper so every mode resolves identically from any cwd. Fixture-dir
    # (``scan_root``) and non-git shapes are honored verbatim by the helper.
    from specify_cli.migration.mission_state import _anchor_repair_root

    resolved_root = _anchor_repair_root(resolved_root, scan_root=resolved_fixture_dir)

    # Checkout-identity reconciliation (WP04, #3051/#3541). The re-anchor above
    # deliberately keeps the #2320 primary status-home; here we make a foreign
    # lane invocation of that re-anchor *honest* rather than silent. Skipped in
    # fixture mode, where the write/read target is the fixture tree, not a
    # primary this invocation could fail to own.
    if mode == _MissionStateMode.FIX:
        if resolved_fixture_dir is None:
            _refuse_foreign_lane_fix(resolved_root)
        _run_mission_repair(
            resolved_root, resolved_fixture_dir, mission, manifest_path, allow_dirty, json_output
        )
        return
    if mode == _MissionStateMode.TEAMSPACE_DRY_RUN:
        _run_teamspace_dry_run_mode(resolved_root, resolved_fixture_dir, mission, json_output)
        return
    disagreement = (
        _surface_audit_disagreement(resolved_root, mission, json_output)
        if resolved_fixture_dir is None
        else False
    )
    _run_audit_mode(
        resolved_root,
        resolved_fixture_dir,
        mission,
        fail_on_severity,
        fail_on_teamspace_blocker,
        json_output,
    )
    if disagreement:
        raise typer.Exit(1)
