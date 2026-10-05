"""Implement command - allocate the lane worktree for a work package."""

from __future__ import annotations

import functools
import json
import subprocess
from collections.abc import Callable, Iterable
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, NoReturn

import typer
from pydantic import ValidationError
from specify_cli.cli.console import console
from rich.panel import Panel

from specify_cli.cli import StepTracker
from specify_cli.cli.selector_resolution import resolve_mission_handle
from specify_cli.core.context_validation import require_main_repo
from kernel.clock import now_utc_iso
from specify_cli.core.errors import PlacementResolutionRequired
from specify_cli.core.git_ops import get_current_branch
from specify_cli.core.vcs import VCSBackend
from specify_cli.mission_metadata import resolve_mission_identity, set_vcs_lock
from specify_cli.frontmatter import FrontmatterError
from specify_cli.git import safe_commit
from specify_cli.git.commit_helpers import (
    SafeCommitHeadMismatch,
    SafeCommitPathPolicyError,
)
from specify_cli.git.protection_policy import ProtectionPolicy
from mission_runtime import (
    MissionArtifactKind,
    placement_seam,
    resolve_topology,
    routes_through_coordination,
)
from specify_cli.coordination.coherence import (
    is_status_state_path,
)
from specify_cli.coordination.surface_resolver import is_under_worktrees_segment
from specify_cli.lanes import implement_support
from specify_cli.lanes.implement_support import create_lane_workspace
from specify_cli.lanes.persistence import require_lanes_json
from specify_cli.lanes.worktree_allocator import (
    DependencyLaneMergeConflictError,
    OrphanedPlanningCommitError,
    PlanningCommitMergeConflictError,
)
from specify_cli.status import TransitionError
from specify_cli.status import (
    WorkPackageClaimConflict,
    start_implementation_status,
)
from specify_cli.task_utils import TaskCliError, find_repo_root
from specify_cli.core import dependency_graph
from specify_cli.status import read_events, reduce as reduce_status_events
from specify_cli.workspace import context as workspace_context
from specify_cli.workspace.context import resolve_workspace_for_wp

# implement_cores.py houses the pure git-porcelain/diff and placement decision cores (git
# injected as a port). Production code here reads ``_resolve_placement_ref`` through the one name
# below; every other former shim re-export was deleted (implement-degod WP05) and callers import
# ``implement_cores`` directly.
from specify_cli.cli.commands import implement_planning_commit
from specify_cli.cli.commands.implement_cores import _resolve_placement_ref

if TYPE_CHECKING:
    # WP03 / T013: type-only -- ``_run_recover_mode`` and its extracted
    # helpers keep the real import lazy (inside the function body) to match
    # the module's existing deferred-import discipline; this gives mypy the
    # shapes without adding a runtime import edge to ``specify_cli.lanes``.
    from specify_cli.lanes.recovery import RecoveryReport, RecoveryState

# WP02 / T008 / S1192: the workspace-ready banner's rich-markup open/close
# tags, repeated ~8x in ``_print_workspace_ready_banner`` -- hoisted to
# constants rather than restated at each call site. The distinct
# ``title="[bold yellow]...[/]"`` uses elsewhere in this module (bulk-edit
# inference banners) use a different close tag and are left as-is.
_BANNER_OPEN = "[bold yellow]"
_BANNER_CLOSE = "[/bold yellow]"


def _protected_branch_status_commit_error(branch: str, repo_root: Path, mission_slug: str | None = None) -> str | None:
    # ProtectionPolicy.resolve_for_mission is the sole I/O boundary (FR-007/NFR-003):
    # config+hatch+meta reads happen once; is_protected() is I/O-free. A mission-scoped
    # write also honours that mission's ``commit_to_target`` for its own target (#5100 FR-008).
    if not ProtectionPolicy.resolve_for_mission(repo_root, mission_slug).is_protected(branch):
        return None
    return (
        f"Refusing to start implementation status on protected branch '{branch}' "
        "before mutating status files. Run this status commit from an allowed "
        "coordination/lane branch, or rerun with --no-auto-commit when you "
        "intentionally want to handle the status artifact commit manually."
    )


def _status_commit_destination_branch(repo_root: Path, fallback_branch: str) -> str:
    """Return the branch that the pre-lane status commit would target."""
    return get_current_branch(repo_root) or fallback_branch


def _json_wrapper_resolve_wp_id(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
    """Resolve the ``wp_id`` used for JSON error payloads: the ``wp_id``
    kwarg first, else the first positional argument (the Typer commands
    wrapped by ``_json_safe_output`` all take ``wp_id`` as arg 0)."""
    wp_id = kwargs.get("wp_id")
    if wp_id is None and args:
        wp_id = args[0]
    return wp_id


def _json_wrapper_begin_capture(json_output: bool) -> tuple[bool, StringIO | None]:
    """Snapshot ``console.quiet`` and, in ``--json`` mode, redirect console
    output into an in-memory buffer so wrapped-function chatter never leaks
    onto stdout ahead of the machine-readable payload."""
    previous_quiet = console.quiet
    capture_buffer: StringIO | None = None
    if json_output:
        capture_buffer = StringIO()
        console.file = capture_buffer
        console.quiet = False
    return previous_quiet, capture_buffer


def _json_wrapper_summarize_capture(capture_buffer: StringIO | None) -> str:
    """Return the last 20 non-blank, rstripped lines captured from the
    console -- the JSON error-summary shape pinned by T010."""
    lines = [line.rstrip() for line in (capture_buffer.getvalue() if capture_buffer else "").splitlines() if line.strip()]
    return "\n".join(lines[-20:]).strip() if lines else "implement command failed"


def _json_wrapper_emit_error_payload(error: str, wp_id: Any) -> None:
    payload: dict[str, Any] = {"status": "error", "error": error}
    if wp_id:
        payload["wp_id"] = str(wp_id)
    print(json.dumps(payload))


def _json_wrapper_handle_typer_exit(exc: typer.Exit, json_output: bool, capture_buffer: StringIO | None, wp_id: Any) -> None:
    """Emit the JSON error payload for a ``typer.Exit`` failure -- unless
    ``exit_code`` is falsy (0), which is a success exit and never gets a
    payload. The caller re-raises ``exc`` verbatim afterwards; this helper
    never raises."""
    if json_output and getattr(exc, "exit_code", 1):
        summary = _json_wrapper_summarize_capture(capture_buffer)
        _json_wrapper_emit_error_payload(summary or "implement command failed", wp_id)


def _json_wrapper_end_capture(previous_quiet: bool) -> None:
    console.quiet = previous_quiet
    # Reset _file to None so the console uses sys.stdout dynamically.
    # Restoring previous_file can leave the console pointing at a closed
    # pytest capsys buffer when tests run in sequence.
    console._file = None


def _json_safe_output(func: Callable[..., Any]) -> Callable[..., Any]:
    """Ensure --json mode stays machine-readable on both success and failure."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        json_output = bool(kwargs.get("json_output", False))
        wp_id = _json_wrapper_resolve_wp_id(args, kwargs)
        previous_quiet, capture_buffer = _json_wrapper_begin_capture(json_output)

        try:
            return func(*args, **kwargs)
        except typer.Exit as exc:
            _json_wrapper_handle_typer_exit(exc, json_output, capture_buffer, wp_id)
            raise
        except Exception as exc:  # pragma: no cover - defensive
            if json_output:
                _json_wrapper_emit_error_payload(str(exc), wp_id)
            raise typer.Exit(1) from exc
        finally:
            _json_wrapper_end_capture(previous_quiet)

    return wrapper


def detect_feature_context(
    mission_flag: str | None = None,
    repo_root: Path | None = None,
    *,
    json_mode: bool = False,
) -> tuple[str | None, str]:
    """Require an explicit mission slug and return ``(mission_number, slug)``.

    Uses the canonical mission resolver (resolve_mission_handle) when
    repo_root is supplied, falling back to bare slug parsing otherwise.
    The repo_root is always available in the callers that matter.
    """
    import re as _re

    raw_handle = mission_flag
    if raw_handle is None:
        console.print("[red]Error:[/red] --mission <slug> is required")
        raise typer.Exit(1)

    if repo_root is not None:
        # Use canonical resolver — handles ambiguity, mid8, full ULID, etc.
        resolved = resolve_mission_handle(raw_handle, repo_root, json_mode=json_mode)
        slug = resolved.mission_slug
    else:
        # Bare-slug fallback for callers without a repo_root (e.g., unit tests).
        slug = raw_handle

    match = _re.match(r"^(\d{3})-", slug)
    return (match.group(1) if match else None), slug


_BASE_REF_UNRESOLVED_MSG = "[red]Error:[/red] Base ref '{base_ref}' does not resolve. Try 'git fetch' or 'git branch -a' to see available refs."


def _raise_base_ref_unresolved(base_ref: str) -> NoReturn:
    """Print the single canonical unresolved-base error and exit non-zero."""
    console.print(_BASE_REF_UNRESOLVED_MSG.format(base_ref=base_ref))
    raise typer.Exit(1)


def _rev_parse_ref(repo_root: Path, ref: str) -> str:
    """Return the full SHA *ref* resolves to, or ``""`` when it does not resolve.

    ``--end-of-options`` keeps a leading-dash ref (e.g. ``--git-dir``) from being
    consumed as a rev-parse option (#1917); ``--verify --quiet`` yields an empty
    stdout + non-zero exit on a missing ref, which :func:`implement_support.git_stdout` maps to
    ``""``.
    """
    return implement_support.git_stdout(repo_root, ["rev-parse", "--verify", "--quiet", "--end-of-options", ref])


def _is_ancestor(repo_root: Path, maybe_ancestor: str, descendant: str) -> bool:
    """Return whether *maybe_ancestor* is an ancestor of (or equal to) *descendant*."""
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", maybe_ancestor, descendant],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return result.returncode == 0


def _resolve_base_ref(repo_root: Path, base_ref: str) -> tuple[str, str] | None:
    """Resolve ``--base`` to ``(effective_ref, sha)``, preferring ``origin/<lane>`` (#4969).

    A teammate's pushed approved lane on ``origin/<base_ref>`` must NOT be
    shadowed by a fresh/stale local cut from ``main``: when ``origin/<base_ref>``
    resolves AND the local ``base_ref`` is either absent or strictly behind it (an
    ancestor of the origin tip), the origin ref wins. A local ref that is ahead of
    (or unrelated to) origin is kept, and a ref that resolves nowhere returns
    ``None`` so the caller can fail closed. The origin-aware base cutting itself
    (threading ``effective_ref`` into worktree allocation) is coordinated with
    WP04's ``workspace/context.py`` / ``lanes/compute.py``; this WP owns only the
    ``implement.py`` resolution site.
    """
    local_sha = _rev_parse_ref(repo_root, base_ref)
    origin_ref = f"origin/{base_ref}"
    origin_sha = _rev_parse_ref(repo_root, origin_ref)
    if origin_sha and (not local_sha or _is_ancestor(repo_root, local_sha, origin_sha)):
        return origin_ref, origin_sha
    if local_sha:
        return base_ref, local_sha
    return None


def _validate_base_ref(repo_root: Path, base_ref: str) -> str:
    """Validate ``--base`` and return the effective (origin-preferred) base SHA.

    #4969: consults ``origin/<base_ref>`` and prefers it over a local cut that is
    absent or behind it, so a teammate's pushed approved lane is not shadowed (see
    :func:`_resolve_base_ref`). Raises typer.Exit(1) with a clear error message
    when the ref resolves neither locally nor on ``origin``.
    """
    resolved = _resolve_base_ref(repo_root, base_ref)
    if resolved is None:
        _raise_base_ref_unresolved(base_ref)
    return resolved[1]


def _ensure_vcs_in_meta(feature_dir: Path, _repo_root: Path) -> VCSBackend:
    """Ensure VCS is selected and locked in meta.json."""
    # read-surface-ssot-closeout WP05 / FR-005: route the inline
    # ``json.loads`` read through the canonical ``load_meta`` authority. This
    # site HARD-FAILS on a missing or malformed meta.json (both branches below
    # raise ``typer.Exit(1)``) -- the post-#2091 contract for a hard-failing
    # site is ``allow_missing=False`` (never ``allow_missing=True``, which
    # would mask the guard by silently returning ``None`` instead of raising).
    from specify_cli.core.paths import MissionMetaReadError, load_meta_fail_closed

    try:
        meta = load_meta_fail_closed(feature_dir)
    except MissionMetaReadError as exc:
        console.print(f"[red]Error:[/red] Invalid JSON in meta.json: {exc}")
        raise typer.Exit(1) from exc
    # ``load_meta_fail_closed`` carries the ``allow_missing=True`` contract: a
    # MISSING meta.json is answered with ``None``, NOT an exception. This site
    # hard-fails on missing, so the guard is spelled explicitly here -- folding
    # it into ``meta or {}`` would mask it and let the command proceed on an
    # unspecified mission (the exact masking the comment above warns about).
    if meta is None:
        console.print(f"[red]Error:[/red] meta.json not found in {feature_dir}")
        console.print("Run /spec-kitty.specify inside your coding agent (Claude Code, Codex, Cursor) first to create the feature structure")
        raise typer.Exit(1)

    if "vcs" not in meta:
        now_iso = now_utc_iso()
        set_vcs_lock(feature_dir, vcs_type="git", locked_at=now_iso)
        console.print("[cyan]→ VCS locked to git in meta.json[/cyan]")

    return VCSBackend.GIT


def _recover_resolve_context(mission: str | None, json_output: bool) -> tuple[Path, str]:
    """Resolve ``(repo_root, mission_slug)`` for recovery.

    On failure, emits the JSON error payload (when requested) and exits 1 --
    matching the pre-extraction behavior byte-for-byte (T011 branch 1)."""
    try:
        repo_root = find_repo_root()
        _mission_number, mission_slug = detect_feature_context(mission, repo_root=repo_root)
    except (TaskCliError, typer.Exit) as exc:
        if json_output:
            print(json.dumps({"status": "error", "error": str(exc)}))
        raise typer.Exit(1) from None
    return repo_root, mission_slug


def _recover_emit_no_action_result(json_output: bool) -> None:
    """Report that the scan found nothing to recover (T011 branch 2)."""
    if json_output:
        print(
            json.dumps(
                {
                    "status": "ok",
                    "message": "No crashed implementation sessions found.",
                    "recovered_wps": [],
                    "worktrees_recreated": 0,
                    "transitions_emitted": 0,
                    "errors": [],
                }
            )
        )
    else:
        console.print("[green]No crashed implementation sessions found.[/green]")


def _recover_print_scan_table(needs_recovery: list[RecoveryState]) -> None:
    """Console-only rendering of the pre-recovery scan results table."""
    from rich.table import Table

    table = Table(title="Recovery Scan Results")
    table.add_column("WP", style="cyan")
    table.add_column("Lane", style="blue")
    table.add_column("Branch", style="dim")
    table.add_column("Worktree", style="green")
    table.add_column("Context", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Action", style="bold")

    for s in needs_recovery:
        table.add_row(
            s.wp_id,
            s.lane_id,
            s.branch_name,
            "yes" if s.worktree_exists else "[red]NO[/red]",
            "yes" if s.context_exists else "[red]NO[/red]",
            s.status_lane,
            s.recovery_action,
        )
    console.print(table)
    console.print()


def _recover_emit_report(report: RecoveryReport, json_output: bool) -> None:
    """Emit the final recovery report -- json payload (no
    ``contexts_recreated``) vs the console summary (which includes it),
    plus the console-only errors block (T011 branches 3+4)."""
    if json_output:
        print(
            json.dumps(
                {
                    "status": "ok",
                    "recovered_wps": report.recovered_wps,
                    "worktrees_recreated": report.worktrees_recreated,
                    "transitions_emitted": report.transitions_emitted,
                    "errors": report.errors,
                }
            )
        )
        return
    console.print("[bold green]Recovery complete[/bold green]")
    console.print(f"  WPs recovered: {', '.join(report.recovered_wps) or 'none'}")
    console.print(f"  Worktrees recreated: {report.worktrees_recreated}")
    console.print(f"  Contexts recreated: {report.contexts_recreated}")
    console.print(f"  Status transitions emitted: {report.transitions_emitted}")
    if report.errors:
        console.print("  [red]Errors:[/red]")
        for err in report.errors:
            console.print(f"    - {err}")


def _run_recover_mode(
    _wp_id: str,
    mission: str | None,
    json_output: bool,
) -> None:
    """Run crash recovery for the given mission.

    Orchestrates scan + worktree/context/status reconciliation + reporting.
    The _wp_id argument is accepted but ignored for recovery -- all WPs in
    the mission are scanned.
    """
    from specify_cli.lanes.recovery import run_recovery, scan_recovery_state

    repo_root, mission_slug = _recover_resolve_context(mission, json_output)

    # First, show what we found
    states = scan_recovery_state(repo_root, mission_slug)
    needs_recovery = [s for s in states if s.recovery_action != "no_action"]

    if not needs_recovery:
        _recover_emit_no_action_result(json_output)
        return

    if not json_output:
        _recover_print_scan_table(needs_recovery)

    # Run recovery
    report = run_recovery(repo_root, mission_slug)
    _recover_emit_report(report, json_output)


# ---------------------------------------------------------------------------
# T017: implement() decomposition helpers -- each owns one leaf decision or
# side effect so the Typer-shell function itself stays a thin orchestration
# sequence (S3776 <=15). None of these change externally-observed behavior;
# see the WP03 tracer for the extraction rationale.
# ---------------------------------------------------------------------------


def _detect_wp_context(
    mission: str,
    wp_id: str,
    repo_root: Path,
    auto_commit: bool | None,
    *,
    json_mode: bool = False,
) -> tuple[bool | None, str, Path, Path, Any]:
    """Resolve ``(auto_commit, mission_slug, feature_dir, wp_file,
    declared_deps)`` for the ``detect`` step. Exceptions propagate to the
    caller's tracker-aware ``except`` clause unchanged."""
    from specify_cli.core.agent_config import get_auto_commit_default
    from specify_cli.core.dependency_graph import parse_wp_dependencies

    if auto_commit is None:
        auto_commit = get_auto_commit_default(repo_root)
    _mission_number, mission_slug = detect_feature_context(mission, repo_root=repo_root, json_mode=json_mode)
    # read-surface-ssot-closeout WP05 / FR-001 / NFR-001: route through the
    # kind-aware placement seam instead of the kind-blind
    # ``resolve_feature_dir_for_mission`` (which could return the
    # coordination worktree's mission dir once materialized -- the #2453
    # coord-husk-shadows-primary defect NFR-001 closes). ``SPEC`` is a
    # PRIMARY-partition kind (mission_runtime.artifacts), so ``read_dir``
    # resolves the topology-blind primary directory directly: the SAME
    # directory every downstream read in this function needs (meta.json,
    # spec.md, tasks.md, the occurrence-map gate). This collapses the
    # former three-step meta.json-existence cascade (resolve -> candidate
    # fallback -> primary fallback), which existed ONLY to paper over the
    # kind-blind resolver's coord-husk shadowing -- the kind-correct seam
    # never returns a meta-less coord husk in the first place.
    feature_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.SPEC)
    wp_file = workspace_context.find_wp_file(repo_root, mission_slug, wp_id)
    declared_deps = parse_wp_dependencies(wp_file)
    return auto_commit, mission_slug, feature_dir, wp_file, declared_deps


def _raise_if_status_commit_protected(repo_root: Path, planning_branch: str, auto_commit: bool | None, mission_slug: str | None = None) -> None:
    """Raise ``ValueError`` when auto-commit is on and the pre-lane status
    commit would target a protected branch."""
    if not auto_commit:
        return
    status_destination = _status_commit_destination_branch(repo_root, fallback_branch=planning_branch)
    protected_error = _protected_branch_status_commit_error(status_destination, repo_root, mission_slug)
    if protected_error is not None:
        raise ValueError(protected_error)


def _run_bulk_edit_gate_and_inference(feature_dir: Path, wp_file: Path, mission_slug: str, wp_id: str, acknowledge_not_bulk_edit: bool) -> None:
    """Bulk-edit occurrence-classification gate (FR-006) + inference warning
    (FR-009). Raises ``typer.Exit(1)`` on a gate failure or an un-acknowledged
    triggered inference; a silent return means the claim may proceed."""
    from specify_cli.bulk_edit.gate import ensure_occurrence_classification_ready, render_gate_failure

    gate_result = ensure_occurrence_classification_ready(feature_dir)
    if not gate_result.passed:
        render_gate_failure(gate_result, console)
        raise typer.Exit(1)

    # FR-012 / NFR-001: key on the ONE canonical check (``== "bulk_edit"``), not
    # implicit presence. A legacy ``change_mode`` value must behave identically to
    # absence — both fall through to the inference scan below — so normalizing a
    # legacy value to absent stays behavior-preserving.
    if gate_result.change_mode == "bulk_edit":
        return

    from specify_cli.bulk_edit.inference import (
        scan_spec_file,
        wp_authors_bulk_edit_planning_artifact,
    )

    inference = scan_spec_file(feature_dir)
    planning_wp = wp_authors_bulk_edit_planning_artifact(wp_file, mission_slug)
    if inference.triggered and planning_wp:
        matched = ", ".join(f"'{p}' ({w}pt)" for p, w in inference.matched_phrases)
        console.print(
            Panel(
                f"This mission's spec contains language suggesting a bulk edit "
                f"(score: {inference.score}/{inference.threshold}), but {wp_id} owns "
                f"the occurrence-map planning artifact.\n"
                f"  Matched: {matched}\n\n"
                f"Continuing without --acknowledge-not-bulk-edit for this planning WP.",
                title="[bold yellow]Bulk Edit Inference Informational[/]",
                border_style="yellow",
            )
        )
        return
    if inference.triggered and not acknowledge_not_bulk_edit:
        matched = ", ".join(f"'{p}' ({w}pt)" for p, w in inference.matched_phrases)
        console.print(
            Panel(
                f"This mission's spec contains language suggesting a bulk edit "
                f"(score: {inference.score}/{inference.threshold}):\n"
                f"  Matched: {matched}\n\n"
                f"If this IS a bulk edit, set change_mode to 'bulk_edit' in meta.json.\n"
                f"If it is NOT, re-run with --acknowledge-not-bulk-edit to suppress.",
                title="[bold yellow]Bulk Edit Inference Warning[/]",
                border_style="yellow",
            )
        )
        raise typer.Exit(1)


def _resolve_execution_lane(resolved_workspace: Any, lanes_feature_dir: Path, wp_id: str, tracker: StepTracker) -> tuple[Any, Any]:
    """Resolve ``(lanes_manifest, lane)`` for a lane workspace, or ``(None,
    None)`` for a repository-root planning workspace. Completes the
    ``validate`` tracker step either way."""
    from specify_cli.lanes.compute import is_repo_root_lane

    if is_repo_root_lane(resolved_workspace):
        tracker.complete("validate", "Execution: repository root planning workspace")
        return None, None
    lanes_manifest = require_lanes_json(lanes_feature_dir)
    lane = lanes_manifest.lane_for_wp(wp_id)
    if lane is None:
        raise ValueError(f"{wp_id} is not assigned to any lane in lanes.json")
    tracker.complete("validate", f"Lane: {lane.lane_id}")
    return lanes_manifest, lane


def _resolve_active_lanes_manifest(repo_root: Path, base: str | None, resolved_workspace: Any, lanes_manifest: Any) -> tuple[str | None, Any]:
    """Validate ``--base`` (#1684) and resolve the effective base to thread
    through ``create_lane_workspace``.

    #3571 (P0): this NO LONGER smuggles the override through
    ``lanes_manifest.mission_branch`` (the coord-topology allocation path
    never read that field, silently discarding ``--base`` and printing a
    fabricated success line). ``base`` is now threaded as an explicit
    parameter all the way to the topology-aware allocator instead; this
    function's job is reduced to validating the ref and applying the
    planning-lane "ignored" warning (FR-007) — ``lanes_manifest`` is always
    returned UNCHANGED.

    Returns ``(effective_base, lanes_manifest)``. ``effective_base`` is
    ``None`` when ``--base`` was not supplied OR the resolved workspace is a
    repository-root planning lane (FR-007 — ``--base`` has no effect there).
    The success line has moved to the CLI layer, AFTER allocation actually
    succeeds (FR-005) — see the ``implement()`` call site."""
    from specify_cli.lanes.compute import is_planning_lane

    if base is None:
        return None, lanes_manifest
    if is_planning_lane(resolved_workspace):
        console.print("[yellow]Warning:[/yellow] --base is ignored for repository-root planning work")
        return None, lanes_manifest
    # #4969: resolve the effective base origin-first so a teammate's pushed
    # approved lane (``origin/<lane>``) is threaded into allocation instead of a
    # stale local cut. ``_resolve_base_ref`` returns the effective ref name (the
    # ``origin/<lane>`` ref when it wins), which is what ``create_lane_workspace``
    # cuts the lane from.
    resolved = _resolve_base_ref(repo_root, base)
    if resolved is None:
        _raise_base_ref_unresolved(base)
    effective_ref, _sha = resolved
    return effective_ref, lanes_manifest


def _primary_surface_status_paths(artifacts: Iterable[Path], *, routes_through_coord: bool) -> list[Path]:
    """Filter collected status artifacts for a PRIMARY-root claim-commit bundle.

    #2155 / #3784 invariant: NO ``.worktrees/``-nested path may enter a
    primary-root ``safe_commit`` bundle. On coord topology ``feature_dir`` is
    the coordination worktree, so every coord-owned artifact
    ``_collect_status_artifacts`` returns — ``status.events.jsonl``,
    ``status.json``, AND ``tasks.md`` — lives under ``.worktrees/``. The
    ``is_status_state_path`` check alone drops only the two STATUS_STATE files
    and lets the coord-worktree ``tasks.md`` (a ``TASKS_INDEX`` kind) survive,
    tripping the ``SafeCommitPathPolicyError`` guard (#3784). Excluding ANY
    ``is_under_worktrees_segment`` path keeps the invariant whole; dropping the
    coord ``tasks.md`` from the CLAIM commit is correct — at claim time it is
    unchanged and the primary copy was already committed at finalize. On
    flat/legacy missions these artifacts are canonical on PRIMARY and stay.
    """
    resolved = [path.resolve() for path in artifacts]
    if not routes_through_coord:
        return resolved
    return [path for path in resolved if not (is_status_state_path(path) or is_under_worktrees_segment(path))]


def _commit_wp_claim_status(
    *,
    repo_root: Path,
    feature_dir: Path,
    mission_slug: str,
    wp_id: str,
    wp_file: Path,
    auto_commit: bool | None,
    status_result: Any,
) -> None:
    """Auto-commit (or staged-only) side effect for a WP's claimed->'doing'
    transition. A no-op when *status_result* shows no lane change occurred.

    Split out of ``implement()`` so the outer try/except there keeps its
    exact ``SafeCommitPathPolicyError`` / ``PlacementResolutionRequired`` /
    soft-warning shape (D11 -- see
    ``test_implement_placement_routing.py::test_structured_error_is_not_swallowed_as_soft_warning``,
    which asserts on ``implement()``'s own source).
    """
    if status_result is None or not status_result.status_changed:
        return
    if not auto_commit:
        console.print(f"[cyan]→ {wp_id} moved to 'doing' (auto-commit disabled, changes staged only)[/cyan]")
        return

    from specify_cli.cli.commands.agent.tasks import _collect_status_artifacts

    commit_msg = f"chore: {wp_id} claimed for implementation"
    meta_file = feature_dir / "meta.json"
    config_file = repo_root / ".kittify" / "config.yaml"
    # #2155 (FR-002 / T011) + #3784: bundle ONLY primary-surface artifacts
    # into the primary-root claim commit. The status transition was already
    # committed to the coordination branch by ``start_implementation_status``
    # (the transactional emitter); under coord topology every coord-owned
    # artifact ``_collect_status_artifacts`` returns (events.jsonl /
    # status.json / the coord-worktree ``tasks.md``) lives UNDER
    # ``.worktrees/``, so staging it from the primary root trips the #1887
    # ``SafeCommitPathPolicyError`` guard. ``_primary_surface_status_paths``
    # drops ANY ``.worktrees/``-nested path on coord topology (the
    # ``is_status_state_path`` check alone let ``tasks.md`` — a TASKS_INDEX
    # kind — survive, the #3784 residual); on a flat/legacy mission these
    # artifacts ARE canonical on PRIMARY and stay in the bundle.
    status_paths = _primary_surface_status_paths(
        _collect_status_artifacts(feature_dir),
        routes_through_coord=routes_through_coordination(resolve_topology(repo_root, mission_slug)),
    )
    files_to_commit = [wp_file.resolve(), *status_paths]
    if meta_file.exists():
        files_to_commit.append(meta_file.resolve())
    if config_file.exists():
        files_to_commit.append(config_file.resolve())

    # #610: every file gathered above is, by construction, primary-surface
    # (the coord-owned status pair is filtered out above under coord
    # topology; nothing coord-residue is ever collected here). The claim
    # commit therefore always targets the PRIMARY write home -- resolved
    # through the canonical seam (``placement_seam(...).write_target(kind)``,
    # never a hand-built ``CommitTarget``, per contracts/seam-api.md) --
    # never the seam-resolved ``placement_ref`` this function used to route
    # through (which names the COORDINATION branch under coord topology).
    # Targeting ``placement_ref`` here was the latent bug behind this call
    # site's ``SafeCommitHeadMismatch``: ``repo_root`` (the primary checkout)
    # is on the mission's target branch, not the coordination branch, so
    # asserting HEAD against the coord ref always mismatched -- previously
    # masked by the very swallow this issue removes. ``WORK_PACKAGE_TASK`` is
    # a ``_PRIMARY_ARTIFACT_KINDS`` member (like every other kind bundled
    # above), so its write target is the primary target branch under every
    # topology.
    claim_commit_target = placement_seam(repo_root, mission_slug).write_target(MissionArtifactKind.WORK_PACKAGE_TASK)
    try:
        safe_commit(
            repo_root=repo_root,
            worktree_root=repo_root,
            target=claim_commit_target,
            message=commit_msg,
            paths=tuple(files_to_commit),
        )
        console.print(f"[cyan]→ {wp_id} moved to 'doing'[/cyan]")
    except SafeCommitPathPolicyError:
        # #2155 (FR-002 / T011): a wrong-surface guard refusal is a real
        # defect, not an "Auto-commit skipped" warning — re-raise so it
        # surfaces instead of leaving the branch silently dirty. The
        # partition above prevents this on a correct bundle; reaching here
        # means a coord-owned path leaked into the primary commit and the
        # C-006 guard MUST stay authoritative (never swallowed).
        raise
    except SafeCommitHeadMismatch:
        # #610: a genuine branch-name mismatch is a real defect, not an
        # "Auto-commit skipped" warning either. The status/lane files above
        # were already written to disk by the caller before this commit was
        # attempted, so swallowing this here left the worktree dirty with no
        # commit to cover it -- exactly what later trips ref_advance.py's
        # dirty-worktree gate at merge time. Re-raise so the mismatch
        # surfaces immediately instead of being discovered downstream.
        raise
    except Exception as _commit_exc:  # noqa: BLE001 — non-policy git failures stay soft
        console.print(f"[yellow]Warning:[/yellow] Could not auto-commit lane change: {_commit_exc}")


def _build_implement_json_payload(
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
    workspace_path: Path,
    branch_name: str | None,
    result: Any,
    resolved_workspace: Any,
) -> dict[str, Any]:
    """Assemble the ``--json`` success payload (FR-004/FR-005 #2186 identity
    anchor + FR-006 lane-test-env passthrough)."""
    result_execution_mode = result.execution_mode if isinstance(result.execution_mode, str) else resolved_workspace.execution_mode
    workspace_rel = str(workspace_path.relative_to(repo_root))
    # FR-004/FR-005 (#2186): the JSON ``mission_slug``/``mission_number``/
    # ``mission_type`` come from meta.json, which lives ONLY on the PRIMARY
    # checkout. ``feature_dir`` above may have landed on the coord husk (the
    # topology-aware resolve→candidate cascade); give the identity read its OWN
    # PRIMARY anchor rather than relying on the conditional meta-fallback above
    # (C-EXCL-FALLBACK — so that fallback can be retired later). NFR-004: no
    # primary-dir stub — this resolves the durable PRIMARY home for real.
    # read-side-seam-primary-primitive-closure-01KYKMMT WP05/FR-004: routed
    # through the kind-aware seam (PRIMARY_METADATA is a PRIMARY-partition
    # kind, so it never lands on the coord husk the topology-aware
    # resolve→candidate cascade above can).
    identity_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA)
    identity = resolve_mission_identity(identity_dir)
    return {
        "workspace": workspace_rel,
        "workspace_path": workspace_rel,
        "branch": branch_name,
        "mission_slug": identity.mission_slug,
        "mission_number": identity.mission_number,
        "mission_type": identity.mission_type,
        "wp_id": wp_id,
        "lane_id": result.lane_id,
        "execution_mode": result_execution_mode,
        "status": "created",
        # FR-006: surface the lane-suffixed test DB env so
        # downstream agents / test runners can `os.environ.update`
        # without re-deriving the helper. Empty dict for
        # planning-artifact workspaces (lane_id is None) or
        # when the result type doesn't carry a real dict
        # (e.g. a MagicMock in unit tests).
        "lane_test_env": (result.lane_test_env if isinstance(getattr(result, "lane_test_env", None), dict) else {}),
    }


def _claim_policy_metadata(shell_pid: int, agent: str) -> dict[str, Any]:
    """Best-effort ``policy_metadata`` triple for the claim transition (WP07/T026).

    Mirrors ``cli.commands.agent.workflow_executor._claim_policy_metadata``
    (duplicated rather than imported to avoid a lower-layer -> agent-package
    dependency): routes ``(shell_pid, shell_pid_created_at, agent)`` onto the
    ``planned -> claimed`` transition's ``policy_metadata`` sidecar (FR-004)
    using WP01's exact reducer-fold key names, omitting
    ``shell_pid_created_at`` (never fabricating a value) when
    :func:`~specify_cli.core.process_liveness.capture_creation_time_baseline`
    cannot capture a baseline (C-007 best-effort, D3a legacy-claim semantics).
    """
    from specify_cli.core.process_liveness import capture_creation_time_baseline
    from specify_cli.status import build_claim_policy_metadata

    baseline = capture_creation_time_baseline(shell_pid)
    if baseline is None:
        return {"shell_pid": shell_pid, "agent": agent}
    return build_claim_policy_metadata(shell_pid=shell_pid, shell_pid_created_at=baseline, agent=agent)


def _start_wp_implementation_status(
    *,
    feature_dir: Path,
    mission_slug: str,
    wp_id: str,
    effective_actor: str,
    workspace_path: Path,
    status_execution_mode: str,
    repo_root: Path,
) -> Any:
    """Call ``start_implementation_status``, translating claim-conflict /
    transition failures into a printed error + ``typer.Exit(1)``."""
    import os as _os

    try:
        return start_implementation_status(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            actor=effective_actor,
            workspace_context=f"{status_execution_mode}:{workspace_path}",
            execution_mode=status_execution_mode,
            repo_root=repo_root,
            # WP07/T026 (FR-004/FR-014): the claim triple rides the
            # planned -> claimed transition's policy_metadata sidecar; the
            # frontmatter pre-write mirror was removed in the #2816 cutover.
            policy_metadata=_claim_policy_metadata(_os.getppid(), effective_actor),
        )
    except WorkPackageClaimConflict as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    except TransitionError as exc:
        console.print(f"[red]Error:[/red] Could not start implementation status: {exc}")
        raise typer.Exit(1) from exc


def _report_workspace_created(tracker: StepTracker, result: Any, workspace_path: Path, repo_root: Path) -> None:
    """Complete the ``create`` tracker step and print the workspace/branch
    summary lines shared by the repo-root and lane-worktree cases."""
    if result.lane_id is None:
        tracker.complete("create", f"Repository root: {workspace_path.relative_to(repo_root)}")
    elif result.is_reuse:
        tracker.complete("create", f"Reused lane {result.lane_id}: {workspace_path.relative_to(repo_root)}")
    else:
        tracker.complete("create", f"Lane {result.lane_id}: {workspace_path.relative_to(repo_root)}")
    console.print(tracker.render())
    if result.mission_branch:
        console.print(f"[cyan]→ Mission branch: {result.mission_branch}[/cyan]")
    if result.branch_name:
        console.print(f"[cyan]→ Lane branch: {result.branch_name}[/cyan]")
    else:
        console.print("[cyan]→ Workspace contract: repository root planning workspace[/cyan]")


def _refuse_repo_root_checkout_if_unavailable(
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
    resolved_workspace: Any,
) -> bool:
    """Run the repo-root write-checkout refusals early (no side effects).

    Returns ``True`` when the occupancy scan ran, so ``implement`` threads it
    into ``create_lane_workspace`` and the full-repo scan runs once per call.
    """
    from specify_cli.lanes.compute import is_repo_root_lane
    from specify_cli.lanes.implement_support import _ensure_repo_root_checkout_available

    if is_repo_root_lane(resolved_workspace):
        return _ensure_repo_root_checkout_available(repo_root, mission_slug, wp_id, resolved_workspace)
    return False


def _print_workspace_ready_banner(result: Any, workspace_path: Path) -> None:
    """Human-readable "workspace ready" banner (repo-root planning vs lane
    worktree), plus the FR-006 lane-test-env export block."""
    if result.lane_id is None:
        console.print("\n[bold green]✓ Repository-root workspace ready[/bold green]")
        console.print()
        console.print(_BANNER_OPEN + "=" * 72 + _BANNER_CLOSE)
        console.print(_BANNER_OPEN + "Planning-artifact work for this WP happens in the repository root" + _BANNER_CLOSE)
        console.print(_BANNER_OPEN + "=" * 72 + _BANNER_CLOSE)
        console.print()
        console.print(f"  [bold]cd {workspace_path}[/bold]")
        console.print()
        console.print("[dim]This WP does not get a lane worktree or workspace context file.[/dim]")
        console.print("[dim]Make planning-artifact changes directly in the repository root.[/dim]")
        return

    if getattr(result, "resolution_kind", None) == "repo_root" and result.branch_name:
        # single_branch code WP: executes in the write checkout, no lane worktree.
        console.print("\n[bold green]✓ Repository-root workspace ready[/bold green]")
        console.print()
        console.print(f"  Work in the repository root checkout on branch [bold]{result.branch_name}[/bold]")
        console.print(f"  [bold]cd {workspace_path}[/bold]")
        console.print()
        console.print("[dim]This WP runs directly in the repository root; commit your work on this branch yourself.[/dim]")
        return

    console.print("\n[bold green]✓ Lane worktree ready[/bold green]")
    console.print()
    console.print(_BANNER_OPEN + "=" * 72 + _BANNER_CLOSE)
    console.print(_BANNER_OPEN + "CRITICAL: Change to the lane worktree before editing files" + _BANNER_CLOSE)
    console.print(_BANNER_OPEN + "=" * 72 + _BANNER_CLOSE)
    console.print()
    console.print(f"  [bold]cd {workspace_path}[/bold]")
    console.print()
    console.print("[dim]All file edits, writes, and commits MUST happen in this directory.[/dim]")
    console.print("[dim]Writing to the main repository instead of the lane worktree is a critical error.[/dim]")

    # FR-006: surface the lane-suffixed test DB env so the agent can
    # export it before running the project's test suite. Persisted to
    # WorkspaceContext for resurrection by later commands; printed here
    # so a human operator can copy/paste in their shell.
    lane_env = getattr(result, "lane_test_env", None)
    if isinstance(lane_env, dict) and lane_env:
        console.print()
        console.print("[bold cyan]Lane-specific test environment (FR-006):[/bold cyan]")
        for key, value in sorted(lane_env.items()):
            console.print(f"  export {key}={value}")
        console.print("[dim]Two parallel SaaS / Django lanes will collide on a single shared test DB unless these are exported in the lane's test process.[/dim]")


@_json_safe_output
@require_main_repo
def implement(
    wp_id: str = typer.Argument(..., help="Work package ID (for example, WP01)"),
    mission: Annotated[str | None, typer.Option("--mission", help="Mission slug (for example, 001-my-feature)")] = None,
    auto_commit: Annotated[
        bool | None,
        typer.Option("--auto-commit/--no-auto-commit", help="Auto-commit status and planning changes (default: from project config)"),
    ] = None,
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
    recover: bool = typer.Option(False, "--recover", help="Recover from crashed implementation session"),
    base: Annotated[
        str | None,
        typer.Option(
            "--base",
            help=(
                "Explicit base ref for the lane workspace (default: auto-detect). "
                "Use this when upstream dependency branches have been merged-and-deleted "
                "and you want to start from the current target branch tip, e.g. --base main."
            ),
        ),
    ] = None,
    acknowledge_not_bulk_edit: Annotated[
        bool,
        typer.Option(
            "--acknowledge-not-bulk-edit",
            help="Suppress the bulk-edit inference warning when spec language resembles a bulk edit but the mission is not one.",
        ),
    ] = False,
    actor: Annotated[str | None, typer.Option("--actor", hidden=True, help="Actor identity for programmatic callers")] = None,
) -> None:
    """Internal — allocate or reuse the lane worktree for a work package.

    This command is internal infrastructure, used by ``spec-kitty agent action implement``
    for workspace creation. It is not the canonical user-facing implementation path for
    spec-kitty 3.1.1.

    Canonical user workflow::

      spec-kitty next --agent <name> --mission <slug>   (loop entry)
      spec-kitty agent action implement <WP> --agent <name>  (per-WP verb)

    This command remains available as a compatibility surface for direct callers.
    See FR-503 and D-4 in the 3.1.1 spec.
    """
    # SC-003 no-selector guard: exit 2 when --mission is omitted (mirrors
    # all other commands and aligns with the no-selector-error-contract).
    # Guard runs BEFORE --recover so that `implement --recover` with no
    # --mission also exits 2, not 1 via detect_feature_context.
    if mission is None:
        console.print("[red]Error:[/red] --mission <slug> is required")
        raise typer.Exit(2)

    if recover:
        _run_recover_mode(wp_id, mission, json_output)
        return

    tracker = StepTracker(f"Implement {wp_id}")
    tracker.add("detect", "Detect feature context")
    tracker.add("validate", "Validate planning state")
    tracker.add("create", "Resolve execution workspace")
    console.print()

    tracker.start("detect")
    try:
        repo_root = find_repo_root()
        # FR-006 caller contract (T024): charter preflight runs BEFORE
        # any worktree allocation or .kittify/ modification. On failure
        # we exit 1 with the blocked_reason — no state mutation.
        from specify_cli.charter_runtime.preflight.hook import run_preflight_or_abort

        run_preflight_or_abort(repo_root, consumer="implement")
        auto_commit, mission_slug, feature_dir, wp_file, declared_deps = _detect_wp_context(mission, wp_id, repo_root, auto_commit, json_mode=json_output)
        tracker.complete("detect", f"Feature: {mission_slug}")
    except (TaskCliError, FileNotFoundError, FrontmatterError, ValidationError, typer.Exit) as exc:
        tracker.error("detect", str(exc))
        console.print(tracker.render())
        raise typer.Exit(1) from exc

    tracker.start("validate")
    try:
        planning_branch = workspace_context.resolve_mission_target_branch(mission_slug, repo_root)
        _raise_if_status_commit_protected(repo_root, planning_branch, auto_commit, mission_slug)

        from specify_cli.coordination.surface_resolver import (
            resolve_status_surface_with_anchor as _resolve_status_surface,
        )

        # FR-003 layer 4: read WP-lane status through the SAME canonical,
        # config-determined surface authority the status WRITE path
        # (coordination/status_transition) uses, never a second ad-hoc
        # resolution. resolve_mission_read_path derived its own coord
        # preference from a slug-derived mid8 (empty for bare slugs), so in the
        # planning→implement window the read landed on a different surface than
        # the write and saw genesis ("WP not finalized"). The anchor authority
        # derives mid8 from meta and carries the fail-closed coord semantics
        # (StatusReadPathNotFound) — one authority, C-STAT-1.
        _status_feature_dir = _resolve_status_surface(repo_root, mission_slug).read_dir
        # ``lanes.json`` (LANE_STATE) is a PRIMARY-partition artifact with INV-5
        # read/write symmetry, so its dir resolves through the kind-aware
        # placement seam (PRIMARY surface) — a DIFFERENT surface than the coord
        # STATUS read above. Resolving it on the coord surface (the pre-symmetry
        # C-LANES-1 read) mismatched the PRIMARY write and broke coord-mission
        # implement (#3371). See :func:`specify_cli.workspace.context.resolve_lane_state_dir`.
        _lanes_feature_dir: Path = workspace_context.resolve_lane_state_dir(repo_root, mission_slug)

        # T012 / Contract 3 + dependency gate: reject unseeded WPs and
        # not-yet-ready dependencies BEFORE any workspace allocation.
        _claim_snapshot = reduce_status_events(read_events(_status_feature_dir))
        dependency_graph.ensure_wp_claim_preconditions(wp_id, declared_deps, _claim_snapshot.work_packages)

        # WP06 / T019 / C-PLACE-1: resolve the single artifact-placement ref from
        # the canonical context so implement-claim never reconciles a
        # primary↔coord planning-artifact split (#1816). The placement ref is the
        # SAME CommitTarget status events resolve to. Resolution is best-effort:
        # on a context-resolution error we pass ``None`` and the helper keeps the
        # legacy meta-derived path (C-004 strangler — never break the lifecycle).
        _placement_ref = _resolve_placement_ref(repo_root, mission_slug=mission_slug, wp_id=wp_id)

        implement_planning_commit._ensure_planning_artifacts_committed_git(
            repo_root=repo_root,
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            planning_branch=implement_planning_commit._planning_commit_branch(repo_root, mission_slug, planning_branch),
            auto_commit=bool(auto_commit),
            placement_ref=_placement_ref,
        )

        # Bulk edit occurrence classification gate (FR-006) + inference
        # warning for potentially unmarked bulk edits (FR-009).
        _run_bulk_edit_gate_and_inference(feature_dir, wp_file, mission_slug, wp_id, acknowledge_not_bulk_edit)

        # FR-017 / NFR-004: build and validate the runtime OperationalContext
        # BEFORE any worktree allocation. The shared claim builder is read-only
        # (no worktree, no status event); calling its guards here means a
        # missing-context precondition failure aborts before create_lane_workspace
        # runs, so a failed claim leaves zero new worktree paths and zero new
        # status events.
        from runtime.next.runtime_bridge import build_operational_context_for_claim

        operational_context = build_operational_context_for_claim(
            repo_root=repo_root,
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            actor=actor or "implement-command",
            active_model=actor,
            active_role=actor or "implement-command",
            current_activity="implement",
        )
        operational_context.require_active_role()

        # Seam-B (WP03, #3128 / FR-005): true WP-execution write site. Refuse a
        # claim invoked from a checkout the mission does not own (canonically
        # another mission's lane worktree in the same registry). write_intent
        # gates the checkout-identity refusal; the ~20 pure read vehicles leave
        # it False, so reads/planning are never falsely refused.
        resolved_workspace = resolve_workspace_for_wp(repo_root, mission_slug, wp_id, write_intent=True)

        lanes_manifest, _lane = _resolve_execution_lane(resolved_workspace, _lanes_feature_dir, wp_id, tracker)
    except Exception as exc:
        # Catches (among others) CorruptLanesError, MissingLanesError,
        # WorkPackageStartRejected, ValueError, typer.Exit -- every failure
        # in this block maps to the same "report + exit 1" outcome, so one
        # generic handler (Exception is a strict superset) replaces the
        # former specific-tuple + generic-fallback pair without changing
        # behavior for any of them.
        tracker.error("validate", str(exc))
        console.print(tracker.render())
        raise typer.Exit(1) from exc

    tracker.start("create")
    effective_actor = actor or "implement-command"
    status_result = None
    status_execution_mode = resolved_workspace.status_execution_mode
    # #4888/T025: distinguishes a failure that occurred BEFORE the workspace
    # existed (create_lane_workspace itself failed -- the WP is still
    # `planned`, matching the comment below) from a failure that occurred
    # AFTER it (inside _start_wp_implementation_status, e.g. a
    # SafeCommitRecoveryFailed surfacing after the status commit already
    # landed) -- so the printed message never contradicts a WP that is
    # already `in_progress`/committed.
    workspace_created = False
    try:
        # WP04/T015 (FR-004/NFR-003/SC-004): the pre-write claim triple rides
        # the planned -> claimed transition's policy_metadata sidecar (see
        # _start_wp_implementation_status below). The former frontmatter
        # dual-write mirror was removed in the #2816 unconditional cutover, so
        # `spec-kitty implement` writes 0 runtime bytes to the WP file.
        # #5100 A3: refusals (wrong branch / occupied / dirty) run BEFORE the VCS
        # lock is written into meta.json, so a refused implement leaves nothing
        # behind (the read-only check is repeated, idempotently, at allocation).
        occupancy_verified = _refuse_repo_root_checkout_if_unavailable(repo_root, mission_slug, wp_id, resolved_workspace)
        vcs_backend = _ensure_vcs_in_meta(feature_dir, repo_root)

        # #3571: when --base is provided, validate the ref (planning-lane
        # "ignored" warning applied here, FR-007) and thread the EFFECTIVE
        # base as an explicit parameter into create_lane_workspace, which
        # forwards it to the topology-aware allocator (never smuggled
        # through lanes_manifest.mission_branch — the coord path never read
        # that field).
        effective_base, active_lanes_manifest = _resolve_active_lanes_manifest(repo_root, base, resolved_workspace, lanes_manifest)

        result = create_lane_workspace(
            repo_root=repo_root,
            mission_slug=mission_slug,
            wp_id=wp_id,
            wp_file=wp_file,
            resolved_workspace=resolved_workspace,
            lanes_manifest=active_lanes_manifest,
            declared_deps=declared_deps,
            vcs_backend_value=vcs_backend.value,
            base=effective_base,
            occupancy_verified=occupancy_verified,
        )
        workspace_path = result.workspace_path
        branch_name = result.branch_name
        workspace_created = True

        status_result = _start_wp_implementation_status(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            effective_actor=effective_actor,
            workspace_path=workspace_path,
            status_execution_mode=status_execution_mode,
            repo_root=repo_root,
        )

        _report_workspace_created(tracker, result, workspace_path, repo_root)

        # #3571 (FR-005): the success line prints ONLY here — AFTER
        # create_lane_workspace has actually returned successfully — so it
        # can never fabricate success. Guarded so it fires only when a base
        # was supplied AND actually applies (not on a repository-root
        # planning lane, where --base is a no-op warned about above); it is
        # therefore unreachable on base=None, on the planning-lane branch,
        # on the orchestrator-api path (a different call site entirely), and
        # on any fail-loud raise (control never reaches this line).
        from specify_cli.lanes.compute import is_planning_lane

        if effective_base is not None and not is_planning_lane(resolved_workspace):
            console.print(f"[cyan]→ Using explicit base ref: {effective_base}[/cyan]")
    except typer.Exit:
        console.print(tracker.render())
        raise
    except Exception as exc:
        tracker.error("create", f"workspace allocation failed: {exc}")
        console.print(tracker.render())
        if workspace_created:
            # #4888/T025: the workspace was already created (`create_lane_workspace`
            # returned) and the failure happened inside `_start_wp_implementation_status`
            # -- possibly AFTER its status commit already landed (e.g. a
            # `SafeCommitRecoveryFailed` whose `commit_sha` is set). Printing
            # the generic "Workspace allocation failed" line here would
            # contradict a WP that is already `claimed`/`in_progress` and
            # committed, so name the actual failure point instead.
            commit_sha = getattr(exc, "commit_sha", None)
            landed_note = (
                f" A status commit (sha={commit_sha}) may have already landed on the lane branch."
                if commit_sha
                else " The WP status transition may have already landed on the lane branch."
            )
            console.print(
                f"\n[red]Error:[/red] Workspace was created but starting the WP status failed: {exc}.{landed_note} "
                "Run `spec-kitty agent tasks status` to check the WP's actual lane before retrying."
            )
        else:
            console.print(f"\n[red]Error:[/red] Workspace allocation failed: {exc}")
        # F-50 (#3937): a tooling/allocation failure that happens BEFORE the
        # workspace exists emits NO lifecycle transition. ``create_lane_workspace``
        # runs BEFORE the claim, so the WP is still ``planned`` in that case,
        # and the allocator self-cleans (abort + ``reset --hard``, no
        # ``lanes.json`` write). The former ``_emit_blocked_on_alloc_failure``
        # manufactured ``planned -> blocked``, an unrecoverable state
        # (``blocked -> planned`` is illegal). Leaving the WP ``planned`` is
        # recoverable and reentrant — at parity with the orchestrator-api
        # path, which never emits ``blocked``. When the failure happens AFTER
        # workspace creation (``workspace_created`` above), the WP may
        # instead already be ``claimed``/``in_progress`` with a landed commit
        # — the message above says so instead of implying ``planned``.
        # Surface the exception's actionable ``next_step`` for the
        # conflict/orphan types that carry one, so the operator gets the
        # concrete resolution rather than a generic "re-run".
        if isinstance(
            exc,
            (DependencyLaneMergeConflictError, PlanningCommitMergeConflictError, OrphanedPlanningCommitError),
        ):
            console.print(f"[yellow]Next step:[/yellow] {exc.next_step}")
        raise typer.Exit(1) from exc

    try:
        _commit_wp_claim_status(
            repo_root=repo_root,
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            wp_file=wp_file,
            auto_commit=auto_commit,
            status_result=status_result,
        )
    except SafeCommitPathPolicyError:
        # #2155 (FR-002 / T011): a wrong-surface guard refusal must NOT be folded
        # into the soft "Could not update WP status" warning — let it propagate so
        # the defect surfaces (the inner handler already re-raised it on purpose).
        raise
    except SafeCommitHeadMismatch:
        # #610: mirrors the SafeCommitPathPolicyError clause above — a genuine
        # branch-name mismatch must NOT be folded into the soft "Could not
        # update WP status" warning either (the inner handler already
        # re-raised it on purpose).
        raise
    except PlacementResolutionRequired:
        # WP03 / D11: a fail-closed placement-resolution refusal must NOT be
        # folded into the soft "Could not update WP status" warning either —
        # that would silently resurrect the checkout-derived fallback this
        # error exists to forbid. Let it propagate so the operator sees and
        # acts on the structured, actionable message.
        raise
    except Exception as exc:
        console.print(f"[yellow]Warning:[/yellow] Could not update WP status: {exc}")

    if json_output:
        print(json.dumps(_build_implement_json_payload(repo_root, mission_slug, wp_id, workspace_path, branch_name, result, resolved_workspace)))
        return

    _print_workspace_ready_banner(result, workspace_path)


__all__ = ["_ensure_vcs_in_meta", "implement"]
