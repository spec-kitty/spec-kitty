"""Implement command - allocate the lane worktree for a work package."""

from __future__ import annotations

import functools
import json
import re
import subprocess
from collections.abc import Callable, Iterable
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, NamedTuple

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
from specify_cli.core.constants import WORKTREES_DIR
from mission_runtime import (
    CommitTarget,
    MissionArtifactKind,
    placement_seam,
    resolve_topology,
    routes_through_coordination,
)
from specify_cli.coordination.coherence import (
    is_coord_residue_churn,
    is_self_bookkeeping_churn,
    is_status_state_path,
)
from specify_cli.coordination.surface_resolver import is_under_worktrees_segment
from specify_cli.lanes.implement_support import create_lane_workspace
from specify_cli.lanes.persistence import require_lanes_json
from specify_cli.lanes.worktree_allocator import (
    DependencyLaneMergeConflictError,
    PlanningCommitMergeConflictError,
)
from specify_cli.status import TransitionError
from specify_cli.status import Lane
from specify_cli.status import (
    WorkPackageClaimConflict,
    WorkPackageStartRejected,
    start_implementation_status,
)
from specify_cli.task_utils import TaskCliError, find_repo_root
from specify_cli.workspace.context import resolve_workspace_for_wp

# WP03 / T019: re-export shim -- bare import (NOT added to __all__, see the
# bottom of this file). implement_cores.py houses the pure git-porcelain/diff
# and placement decision cores (git injected as a port); this module keeps
# them importable at their historical `specify_cli.cli.commands.implement.*`
# location for external callers/tests and is the "git executor" for the one
# staging-decision core (_ensure_planning_artifacts_committed_git, T016).
from specify_cli.cli.commands.implement_cores import (  # noqa: F401 -- shim re-export
    _committed_meta_mapping,
    _drop_if,
    _feature_dir_status_entries,
    detect_structural_planning_changes,
    _files_changed_vs_ref,
    _is_runtime_frontmatter_only_wp_diff,
    _is_self_write_only_diff,
    _parse_wp_frontmatter,
    _placement_coord_filter,
    _PorcelainEntry,
    _commit_target_ref_for,
    _resolve_claim_commit_target,
    _resolve_placement_ref,
    _status_paths_for_commit,
    resolve_planning_artifact_staging,
)

if TYPE_CHECKING:
    # WP03 / T013: type-only -- ``_run_recover_mode`` and its extracted
    # helpers keep the real import lazy (inside the function body) to match
    # the module's existing deferred-import discipline; this gives mypy the
    # shapes without adding a runtime import edge to ``specify_cli.lanes``.
    from specify_cli.lanes.recovery import RecoveryReport, RecoveryState

_WP_ID_RE = re.compile(r"^WP\d{2}$", re.IGNORECASE)
# WP03 / S1192: the rich-markup error prefix, repeated across the
# planning-artifact commit helper this WP touches -- hoisted to one constant
# rather than restated at each ``console.print`` call site.
_RED_ERROR_PREFIX = "[red]Error:[/red] "
# WP02 / T008 / S1192: the workspace-ready banner's rich-markup open/close
# tags, repeated ~8x in ``_print_workspace_ready_banner`` -- hoisted to
# constants rather than restated at each call site. The distinct
# ``title="[bold yellow]...[/]"`` uses elsewhere in this module (bulk-edit
# inference banners) use a different close tag and are left as-is.
_BANNER_OPEN = "[bold yellow]"
_BANNER_CLOSE = "[/bold yellow]"


def _protected_branch_status_commit_error(branch: str, repo_root: Path) -> str | None:
    # ProtectionPolicy.resolve is the sole I/O boundary (FR-007/NFR-003):
    # config+hatch reads happen once; is_protected() is I/O-free.
    if not ProtectionPolicy.resolve(repo_root).is_protected(branch):
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


def find_wp_file(repo_root: Path, mission_slug: str, wp_id: str) -> Path:
    """Find the markdown file for a work package.

    WP05 / FR-003 (coord-topology regression fix): WP prompt files under
    ``tasks/`` are authored on the PRIMARY checkout (``mission_creation`` writes
    the mission dir there and the ``tasks`` step appends beside it). On a
    coordination-topology mission finalize-tasks commits a COPY of those files
    onto the coordination branch, but a freshly-resolved ``find_wp_file`` runs
    before the lane worktree is allocated and must locate the authored prompt on
    the surface that always carries it. The topology-aware
    ``resolve_feature_dir_for_mission`` selects the coordination worktree once
    one exists, which need not carry every authored prompt — so anchor the
    WP-file read on the primary surface, consistent with finalize-tasks and
    ``mission_runtime.resolve_placement_only``.

    read-side-seam-primary-primitive-closure-01KYKMMT WP05/FR-004: routed
    through the kind-aware seam (WORK_PACKAGE_TASK is a PRIMARY-partition
    kind, so it short-circuits to PRIMARY before any coord probe and -- unlike
    the kind-blind resolver above -- never lands on the coordination
    worktree).
    """
    tasks_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK) / "tasks"
    if not tasks_dir.exists():
        raise FileNotFoundError(f"Tasks directory not found: {tasks_dir}")

    normalized_wp_id = wp_id.strip().upper()
    if not _WP_ID_RE.fullmatch(normalized_wp_id):
        raise FileNotFoundError(f"Invalid work package ID: {wp_id}. Expected format WP## (for example, WP01).")

    wp_name_re = re.compile(rf"^{re.escape(normalized_wp_id)}(?:[-_.].+)?\.md$", re.IGNORECASE)
    wp_files = sorted(path for path in tasks_dir.glob("WP*.md") if wp_name_re.match(path.name))
    if not wp_files:
        raise FileNotFoundError(f"WP file not found for {normalized_wp_id} in {tasks_dir}")
    return wp_files[0]


def resolve_feature_target_branch(mission_slug: str, repo_root: Path) -> str:
    """Resolve the feature's configured target branch from metadata."""
    from specify_cli.core.git_ops import resolve_target_branch

    resolution = resolve_target_branch(
        mission_slug=mission_slug,
        repo_path=repo_root,
        respect_current=True,
    )
    return resolution.target


def _validate_base_ref(repo_root: Path, base_ref: str) -> str:
    """Validate that a base ref resolves locally and return its full SHA.

    Raises typer.Exit(1) with a clear error message if the ref is unknown.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--end-of-options", base_ref],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        console.print(f"[red]Error:[/red] Base ref '{base_ref}' does not resolve. Try 'git fetch' or 'git branch -a' to see available refs.")
        raise typer.Exit(1)
    return result.stdout.strip()


def _git_stdout(repo_root: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _feature_dir_status_paths(repo_root: Path, feature_dir: Path) -> list[str]:
    """Repo-relative paths of *writable* (non-structural) feature-dir changes."""
    return [e.path for e in _feature_dir_status_entries(repo_root, feature_dir) if not e.is_structural]


def _resolve_lanes_dir(repo_root: Path, mission_slug: str) -> Path:
    """Return the directory containing ``lanes.json`` for *mission_slug*.

    ``lanes.json`` is the ``LANE_STATE`` artifact, a member of
    :data:`mission_runtime.artifacts._PRIMARY_ARTIFACT_KINDS` — it "travels
    with tasks.md → PRIMARY" and carries **INV-5 full read/write symmetry**
    (FR-004 / NFR-004): PRIMARY on both sides, for every topology. So this
    reader resolves it through the kind-aware placement seam
    (``placement_seam(...).read_dir(LANE_STATE)`` → the PRIMARY surface),
    exactly as the other canonical ``lanes.json`` readers already do
    (``merge/executor.py``, ``lanes/lifecycle_sync.py``). The coord-aware
    STATUS surface — the ``-coord`` husk — does NOT carry ``lanes.json``, so
    resolving it there (the pre-symmetry C-LANES-1 read) was the write-path
    -integrity regression: the write side commits ``lanes.json`` to the
    PRIMARY target branch while this read looked on coord (#3371 e2e break).

    Distinct from :func:`lanes.persistence.resolve_lanes_dir`, which is a
    path-join helper (``feature_dir / lanes.json``); this function resolves
    the *feature_dir* itself from the artifact's canonical partition.
    """
    return placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.LANE_STATE)


def _print_uncommitted_planning_artifacts(files_to_commit: list[str]) -> None:
    console.print("\n[cyan]Planning artifacts not committed:[/cyan]")
    for file_path in files_to_commit:
        console.print(f"  {file_path}")


def _print_planning_artifact_commit_instructions(
    current_branch: str,
    planning_branch: str,
    auto_commit: bool,
    feature_dir: Path,
    mission_slug: str,
) -> None:
    if current_branch != planning_branch:
        console.print(f"\n[red]Error:[/red] Planning artifacts must be committed on {planning_branch}.")
        console.print(f"Current branch: {current_branch}")
        raise typer.Exit(1)

    if auto_commit:
        return

    console.print("\n[yellow]Auto-commit disabled.[/yellow] Commit planning artifacts first:")
    console.print(f"  git add -f {feature_dir}")
    console.print(f'  git commit -m "chore: planning artifacts for {mission_slug}"')
    raise typer.Exit(1)


def _load_primary_anchored_mission_meta(repo_root: Path | None, mission_slug: str) -> dict[str, Any] | None:
    """FR-003 cascade layer 1: read the PRIMARY-checkout ``meta.json``.

    ``coordination_branch`` / ``mission_id`` / ``mid8`` live ONLY in the
    PRIMARY-checkout meta.json; the coord worktree's mission dir has none.
    ``feature_dir`` (the caller's fallback, see
    :func:`_load_fallback_mission_meta`) is topology-aware and prefers the
    coord worktree once materialized — reading meta there returns empty, so
    every identifier silently fell back to the slug (``mid8`` ->
    ``<slug>0000``), which then names a non-existent coord branch/worktree at
    claim time ("Failed to resolve coordination worktree for
    <slug>-<slug-fallback>"). Anchor the config read on the canonical primary
    dir first (the caller threads the true main ``repo_root``), so config is
    read before topology is resolved.

    Returns ``None`` when *repo_root* is not supplied or the primary meta is
    missing/corrupt (legacy). Does NOT catch an ambiguous-handle raise from
    the seam's handle canonicalization — that must propagate (no silent
    pick, C-009).

    read-side-seam-primary-primitive-closure-01KYKMMT WP05/FR-004: routed
    through the kind-aware seam (PRIMARY_METADATA is a PRIMARY-partition
    kind, so it resolves PRIMARY for every topology). The seam's internal
    handle canonicalization propagates ``MissionSelectorAmbiguous`` exactly
    like the drained ``_canonicalize_primary_read_handle`` call did, so it is
    deliberately called OUTSIDE the ``try`` below -- only the meta.json
    read itself is soft-caught.
    """
    if repo_root is None:
        return None

    from specify_cli.core.paths import MissionMetaReadError
    from specify_cli.core.paths import load_meta_fail_closed as _load_meta

    primary_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA)
    try:
        return _load_meta(primary_dir)
    except (OSError, MissionMetaReadError):  # corrupt/unreadable primary meta -> fall through to layer 2
        return None


def _load_fallback_mission_meta(feature_dir: Path) -> dict[str, Any] | None:
    """FR-003 cascade layer 2: read ``meta.json`` off the passed *feature_dir*.

    Only consulted when :func:`_load_primary_anchored_mission_meta` yields
    ``None`` (no ``repo_root``, or the primary meta is missing/corrupt).
    """
    from specify_cli.core.paths import MissionMetaReadError
    from specify_cli.core.paths import load_meta_fail_closed as _load_meta

    try:
        return _load_meta(feature_dir)
    except (OSError, MissionMetaReadError):  # corrupt/unreadable meta.json is legacy-tolerated here
        return None


def _extract_mission_identifiers_from_meta(mission_meta: dict[str, Any] | None, mission_slug: str) -> tuple[str | None, str | None, str | None]:
    """Pull ``(coord_branch, mission_id, mid8)`` out of a resolved meta dict.

    mid8 precedence: the stored ``meta["mid8"]`` value wins; otherwise the
    fallback routes through the authoritative :func:`resolve_mid8` resolver
    (WP03 / FR-009). ``or None`` preserves the prior ``None`` contract
    (``resolve_mid8`` declines to ``""``).
    """
    if not isinstance(mission_meta, dict):
        return None, None, None

    coord_branch: str | None = mission_meta.get("coordination_branch") or None
    mission_id: str | None = mission_meta.get("mission_id") or None

    from specify_cli.lanes.branch_naming import resolve_mid8

    mid8: str | None = mission_meta.get("mid8") or (
        resolve_mid8(
            mission_slug,
            mission_id=mission_id if isinstance(mission_id, str) else None,
        )
        or None
    )
    return coord_branch, mission_id, mid8


def _compute_effective_bookkeeping_ids(
    mission_slug: str,
    mission_id: str | None,
    mid8: str | None,
    coord_branch: str | None,
) -> tuple[str, str]:
    """Derive ``(effective_mission_id, effective_mid8)`` from the resolved triple.

    ``effective_mission_id`` falls back to ``legacy-<slug>`` when no declared
    ``mission_id`` is available. ``effective_mid8`` routes through the
    canonical fail-closed authority (FR-007) rather than fabricating a
    zero-padded mid8 from the slug — that idiom named a non-existent coord
    branch/worktree at claim time.
    """
    effective_mission_id = str(mission_id) if mission_id else f"legacy-{mission_slug}"

    from specify_cli.lanes.branch_naming import resolve_transaction_mid8

    effective_mid8 = resolve_transaction_mid8(
        mission_slug,
        mission_id=str(mission_id) if mission_id else None,
        mid8=str(mid8) if mid8 else None,
        coordination_branch=coord_branch,
    )
    return effective_mission_id, effective_mid8


class _BookkeepingTransactionIdentifiers(NamedTuple):
    """The identifiers :func:`_resolve_bookkeeping_transaction_identifiers` returns.

    A ``NamedTuple`` (PR #2662 squad LOW-3 hardening): it IS a 5-tuple, so the
    frozen C-006 contract holds by construction — ``tasks_move_task.py`` reads
    ``[0]`` cross-lane and the in-module caller unpacks all five, both unchanged
    — while the fields are now named/structural instead of a bare positional
    pin. Arity and order MUST NOT change (C-006).
    """

    coord_branch: str | None
    mission_id: str | None
    mid8: str | None
    effective_mission_id: str
    effective_mid8: str


def _resolve_bookkeeping_transaction_identifiers(
    feature_dir: Path,
    mission_slug: str,
    repo_root: Path | None = None,
) -> _BookkeepingTransactionIdentifiers:
    """Resolve the ``(coord_branch, mission_id, mid8, effective_mission_id,
    effective_mid8)`` bookkeeping identifiers as a 5-field NamedTuple.

    C-006 (frozen contract, #2649): ``tasks_move_task.py`` imports this
    symbol and reads only element ``[0]`` cross-lane, while the in-module
    caller (``_ensure_planning_artifacts_committed_git``) unpacks all five —
    the 5-tuple arity and order MUST NOT change (a NamedTuple keeps both the
    positional and the new named access working).
    """
    mission_meta = _load_primary_anchored_mission_meta(repo_root, mission_slug)
    if mission_meta is None:
        mission_meta = _load_fallback_mission_meta(feature_dir)

    coord_branch, mission_id, mid8 = _extract_mission_identifiers_from_meta(mission_meta, mission_slug)
    effective_mission_id, effective_mid8 = _compute_effective_bookkeeping_ids(mission_slug, mission_id, mid8, coord_branch)
    return _BookkeepingTransactionIdentifiers(coord_branch, mission_id, mid8, effective_mission_id, effective_mid8)


def _feature_dir_file_paths(repo_root: Path, feature_dir: Path) -> list[str]:
    # FR-005 / Issue #1887: reject calls where feature_dir resolves under
    # .worktrees/.  Relativizing a coord-worktree path against the primary repo
    # root produces paths like ".worktrees/<slug>/..." which safe_commit then
    # stages into the primary index, leaking coord internals into origin/main.
    # The caller must pass the correct coordination-branch-relative path instead.
    feature_dir_resolved = feature_dir.resolve()
    repo_root_resolved = repo_root.resolve()
    try:
        rel = feature_dir_resolved.relative_to(repo_root_resolved)
    except ValueError:
        rel = None
    if rel is not None and rel.parts and rel.parts[0] == WORKTREES_DIR:
        raise SafeCommitPathPolicyError(
            offending_path=rel.as_posix(),
            worktree_root=repo_root_resolved,
        )

    paths: list[str] = []
    for path in sorted(feature_dir.rglob("*")):
        if not path.is_file():
            continue
        try:
            rel_path = path.resolve().relative_to(repo_root_resolved).as_posix()
        except ValueError:
            continue
        # Secondary guard: individual files must not land under .worktrees/.
        if Path(rel_path).parts and Path(rel_path).parts[0] == WORKTREES_DIR:
            raise SafeCommitPathPolicyError(
                offending_path=rel_path,
                worktree_root=repo_root_resolved,
            )
        paths.append(rel_path)
    return paths


def _planning_artifact_source_dir(repo_root: Path, feature_dir: Path, mission_slug: str) -> Path:
    """Return the primary-checkout mission dir for planning-artifact discovery."""
    repo_root_resolved = repo_root.resolve()
    try:
        rel = feature_dir.resolve().relative_to(repo_root_resolved)
    except ValueError:
        return feature_dir
    if rel.parts and rel.parts[0] == WORKTREES_DIR:
        # read-side-seam-primary-primitive-closure-01KYKMMT WP05/FR-004: routed
        # through the kind-aware seam. PRIMARY_METADATA is a PRIMARY-partition
        # kind -- it resolves the SAME topology-blind primary mission dir every
        # other PRIMARY-partition kind does (mirroring the established
        # slug-canonicalization idiom: "resolve a handle to its canonical
        # on-disk directory name" always migrates onto PRIMARY_METADATA,
        # never a specific artifact's content -- this call discards content,
        # it only needs the directory).
        primary_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA)
        if primary_dir.exists():
            return primary_dir
    return feature_dir


def _print_structural_planning_refusal(structural: list[_PorcelainEntry]) -> None:
    """Print the #1598 fail-closed refusal for structural planning-artifact
    changes (deletions/renames/copies) that cannot be auto-committed to the
    coordination branch.

    ``BookkeepingTransaction.write_artifact`` is a write-only API that cannot
    remove an old path from the coordination branch, so silently committing only
    the additions would leave the branch incoherent (stale deleted/renamed-from
    artifacts). The claim must refuse; the operator commits the structural change
    to the coordination branch out-of-band, then re-runs the claim.
    """
    console.print(f"\n{_RED_ERROR_PREFIX}Uncommitted structural planning-artifact changes (deletions/renames) cannot be auto-committed to the coordination branch:")
    for entry in structural:
        console.print(f"  {entry.xy.strip() or entry.xy} {entry.path}")
    console.print("\nCommit these structural changes to the coordination branch yourself (e.g. `git rm`/`git mv` + commit), then re-run the claim.")


def _ensure_planning_artifacts_committed_git(
    repo_root: Path,
    feature_dir: Path,
    mission_slug: str,
    wp_id: str,
    planning_branch: str,
    *,
    auto_commit: bool,
    placement_ref: CommitTarget | None = None,
) -> None:
    """Ensure planning artifacts are committed on the feature planning branch.

    ``placement_ref`` (WP06 / T019) is the context's resolved
    :class:`CommitTarget` — the ONE ref planning artifacts AND status events
    resolve to (C-PLACE-1). When supplied it drives the coord/flattened/primary
    placement decision so implement-claim never reconciles a primary↔coord
    split (#1816). When ``None`` (callers not yet threading the context, C-004
    strangler) the legacy meta-derived path is used unchanged.
    """
    current_branch = _git_stdout(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    artifact_source_dir = _planning_artifact_source_dir(repo_root, feature_dir, mission_slug)

    # Squad-B1 (#2464): fail closed on structural planning-artifact changes
    # BEFORE resolving the coordination-branch filter below (which can raise on
    # a broken topology). This restores the pre-degod ordering so a topology
    # fault never preempts the tailored structural-refusal message under a
    # double fault (structural change present AND topology resolution raising).
    structural = detect_structural_planning_changes(repo_root, artifact_source_dir)
    if structural:
        _print_structural_planning_refusal(structural)
        raise typer.Exit(1)

    # WP06 / T019 / C-PLACE-1: when the context supplies a placement ref, the
    # coord/flattened/primary decision comes from that single CommitTarget — no
    # independent meta-derived coord logic (C-005). Otherwise fall back to the
    # legacy meta-derived coord branch (C-004 strangler).
    if placement_ref is not None:
        coord_branch_for_filter = _placement_coord_filter(repo_root, mission_slug, placement_ref)
    else:
        coord_branch_for_filter = _resolve_bookkeeping_transaction_identifiers(feature_dir, mission_slug, repo_root)[0]

    # T016: the staging DECISION (structural fail-closed check, #2222
    # vcs-lock exclusion, dedup, idempotency filtering) is a pure core in
    # implement_cores.py; this function is the git EXECUTOR -- it turns a
    # non-empty ``plan.structural`` into the fail-closed print+exit below and
    # an empty ``plan.files_to_commit`` into a silent no-op return, then does
    # the actual BookkeepingTransaction I/O.
    extra_file_paths = _feature_dir_file_paths(repo_root, artifact_source_dir) if coord_branch_for_filter else []
    # FIX-M2-08: no longer thread ``placement_ref.ref`` in as ``verbatim_ref``.
    # The "PR #2662 squad fix" this parameter implemented compared EVERY
    # candidate (PRIMARY and COORD-residue alike) against the coordination
    # ref -- but ``_commit_planning_artifacts_transaction`` below was later
    # made partition-aware (write-path-integrity WP02/T008/FR-001, closing
    # #3371: PRIMARY files commit to ``planning_branch``, only COORD-residue
    # files commit to the coordination ref). Leaving ``verbatim_ref`` wired
    # here left the STAGING check comparing PRIMARY planning artifacts
    # (spec.md/plan.md/tasks.md/lanes.json/the D1-excluded dossier snapshot)
    # against the coordination branch even though the COMMIT never lands them
    # there -- exactly the read=HEAD/write=coord divergence #2653 already
    # named, just reintroduced on the read side. A coordination branch that
    # has not yet received a mission's planning-artifact history (the normal
    # case: coord is materialised early, planning artifacts land on primary)
    # then makes every already-committed primary file look "changed",
    # inflating ``files_to_commit`` with files that need no commit at all —
    # confirmed via ``tests/e2e/test_cli_smoke.py::test_full_workflow_sequence``
    # (spec.md/plan.md/tasks.md/lanes.json all reported "not committed" while
    # ``git status`` on the primary checkout showed them clean). Passing no
    # ``verbatim_ref`` restores the partition-aware comparison
    # (:func:`resolve_precondition_ref`: PRIMARY vs ``HEAD``, COORD-residue vs
    # the coordination ref) the pinned staging-core tests already assert as
    # canonical (``test_meta_json_on_coord_mission_resolves_to_head``,
    # ``test_dirty_spec_md_still_staged_against_head_on_coord_mission``,
    # INV-5 / #2533 / BLOCKER-2).
    plan = resolve_planning_artifact_staging(
        repo_root,
        artifact_source_dir,
        coord_branch_for_filter,
        extra_file_paths,
        auto_commit=auto_commit,
    )

    files_to_commit = plan.files_to_commit
    if not files_to_commit:
        return

    if plan.status_paths_to_commit:
        _print_uncommitted_planning_artifacts(files_to_commit)
        _print_planning_artifact_commit_instructions(
            current_branch,
            planning_branch,
            auto_commit,
            artifact_source_dir,
            mission_slug,
        )

    commit_msg = f"chore: planning artifacts for {mission_slug}\n\nAuto-committed by spec-kitty before creating the lane worktree for {wp_id}"

    _commit_planning_artifacts_transaction(
        repo_root=repo_root,
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        planning_branch=planning_branch,
        files_to_commit=files_to_commit,
        commit_msg=commit_msg,
        placement_ref=placement_ref,
    )


def _partition_files_for_commit(files_to_commit: list[str]) -> tuple[list[str], list[str]]:
    """Split *files_to_commit* into PRIMARY and COORD-residue groups (T007).

    Mirrors ``commit_router._group_files_by_partition``: classifies each
    repo-relative path with the same
    :func:`~specify_cli.coordination.coherence.is_coord_residue_churn`
    predicate WP01 wired into the read-side ``resolve_precondition_ref`` --
    one authority (NFR-004), no new partition literal (WP12 retired the
    former ``mission_runtime`` predicate onto this owner leg). Everything NOT
    explicitly COORD-residue (PRIMARY kinds, ``meta.json``, unrecognized paths)
    defaults to the PRIMARY group -- the same fail-safe-toward-primary
    direction as the read side.
    """
    primary_files: list[str] = []
    coord_files: list[str] = []
    for path_str in files_to_commit:
        if is_coord_residue_churn(path_str):
            coord_files.append(path_str)
        else:
            primary_files.append(path_str)
    return primary_files, coord_files


def _guard_planning_commit_partition(files: list[str], *, destination_is_coord: bool) -> None:
    """Seam-A guard for the kind-agnostic ``BookkeepingTransaction`` commit (T011).

    write-path-integrity WP02 / FR-002 / C-008: the ``commit_for_mission``
    classifier already refuses a PRIMARY kind reaching coord staging
    (:class:`~specify_cli.coordination.commit_router.PrimaryKindReachedCoordStagingError`),
    but the P0 planning path commits through the kind-AGNOSTIC
    :class:`BookkeepingTransaction` seam, which never consulted a kind. This is
    the mirror guard on THAT seam: it classifies each staged path and raises the
    SAME exception on a partition mis-route, so a future edit that mixes
    partitions fails loud instead of silently landing a PRIMARY ``lanes.json`` on
    the coordination branch (the #3371 class).

    Exemption ORDER matters (C-008): spec-kitty's OWN bookkeeping
    (:func:`~specify_cli.coordination.coherence.is_self_bookkeeping_churn` --
    ``meta.json``, encoding-provenance, ``kitty-ops`` Op records) is exempted
    BEFORE kind classification, so a legitimate coordination commit co-travelling
    ``meta.json`` (a COORD-partition status commit that also carries mission
    identity metadata) does NOT trip the ``PRIMARY_METADATA``→coord guard. Only
    then is each remaining path checked: under a COORD destination a PRIMARY
    (non-residue) kind is the forbidden PRIMARY→coord route; under a PRIMARY
    destination a coord-residue kind is the forbidden COORD→primary/lane route.

    This guard is only applied under coordination topology (the caller passes
    ``enforce_partition=True`` for the coord-topology partition commits and
    ``False`` for the flat/legacy single-branch collapse, where every kind
    legitimately shares one branch and there is no partition to violate).
    """
    from specify_cli.coordination.commit_router import PrimaryKindReachedCoordStagingError

    for path_str in files:
        if is_self_bookkeeping_churn(path_str):
            # meta.json / encoding-provenance / kitty-ops co-travel — exempt
            # BEFORE kind classification (C-008).
            continue
        file_is_coord = is_coord_residue_churn(path_str)
        if file_is_coord == destination_is_coord:
            continue
        if destination_is_coord:
            raise PrimaryKindReachedCoordStagingError(
                f"PRIMARY-partition planning artifact {path_str!r} reached the "
                f"coordination-branch commit seam; PRIMARY kinds must commit to "
                f"the primary target branch and never transit the coordination "
                f"branch (write-path-integrity FR-002)."
            )
        raise PrimaryKindReachedCoordStagingError(
            f"COORD-partition artifact {path_str!r} reached a PRIMARY/lane commit "
            f"seam; coordination-partition kinds must commit to the coordination "
            f"branch, never a primary or lane branch (write-path-integrity FR-002/#2549)."
        )


def _run_planning_artifact_commit(
    *,
    repo_root: Path,
    mission_id: str,
    mission_slug: str,
    mid8: str,
    destination_ref: str,
    files: list[str],
    commit_msg: str,
    commit_to_primary_target: bool = False,
    enforce_partition: bool = False,
) -> None:
    """Execute ONE ``BookkeepingTransaction`` commit of *files* to *destination_ref*.

    Extracted from :func:`_commit_planning_artifacts_transaction` (T007) so
    the partition-aware caller below can run this once per PRIMARY/COORD-
    residue group without duplicating the transaction I/O + exception
    handling.

    ``commit_to_primary_target`` (WP02 / FR-001): threaded to
    :meth:`BookkeepingTransaction.acquire` so a PRIMARY-partition commit lands on
    the mission's own ``destination_ref`` (primary target branch) instead of
    being redirected onto the coordination branch. See ``acquire``'s docstring.

    ``enforce_partition`` (WP02 / FR-002 / T011): apply the Seam-A guard. Set for
    the coordination-topology partition commits (PRIMARY and COORD groups) and
    left ``False`` for the flat/legacy single-branch collapse where a mixed batch
    legitimately shares one branch.

    ``commit_idempotent`` (WP02 / FR-001 / T009): crash-recovery re-drive. If the
    process dies between the PRIMARY and COORD commits, re-invoking ``implement``
    re-runs BOTH groups; the group that already committed finds its staged paths
    byte-identical to HEAD and no-ops instead of hard-failing on an empty
    changeset. Recovery is per-partition idempotent re-drive, NOT cross-ref
    atomicity.
    """
    from specify_cli.coordination.transaction import BookkeepingTransaction

    if enforce_partition:
        _guard_planning_commit_partition(files, destination_is_coord=not commit_to_primary_target)

    with BookkeepingTransaction.acquire(
        repo_root=repo_root,
        mission_id=mission_id,
        mission_slug=mission_slug,
        mid8=mid8,
        destination_ref=destination_ref,
        operation=f"planning artifacts for {mission_slug}",
        commit_to_primary_target=commit_to_primary_target,
    ) as txn:
        for path_str in files:
            repo_path = Path(path_str)
            source_path = (repo_root / repo_path).resolve()
            if not source_path.exists():
                continue
            txn.write_artifact(repo_path, source_path.read_bytes())
        try:
            txn.commit_idempotent(commit_msg)
        except Exception as exc:  # noqa: BLE001 — surface as exit-1
            console.print(f"{_RED_ERROR_PREFIX}Failed to commit planning artifacts to {destination_ref}: {exc}")
            raise typer.Exit(1) from exc


def _commit_planning_artifacts_transaction(
    *,
    repo_root: Path,
    feature_dir: Path,
    mission_slug: str,
    planning_branch: str,
    files_to_commit: list[str],
    commit_msg: str,
    placement_ref: CommitTarget | None,
) -> None:
    """T016 git-executor tail: run the BookkeepingTransaction commit(s).

    Split out of :func:`_ensure_planning_artifacts_committed_git` so that
    function's own complexity stays scoped to the staging decision it drives;
    this helper owns only the transaction I/O (identifier resolution,
    destination-ref selection, ``BookkeepingTransaction`` write+commit,
    legacy-vs-coordination status prints).

    WP06 T026: route planning-artifact commits through BookkeepingTransaction
    so the commit lands on the mission's coordination branch (FR-005) and any
    write of status events is atomically reversible (FR-010). Legacy missions
    (created pre-WP03) have no ``coordination_branch`` in meta.json; the
    transaction's built-in legacy fallback (``_is_legacy_mission`` +
    ``_resolve_legacy_lane_destination`` in ``coordination/transaction.py``)
    overrides ``destination_ref`` with the actual checked-out lane branch, so
    the pre-flight policy gate, surgical rollback, and feature-status lock
    apply uniformly to coordination-branch and legacy missions alike (FR-027).

    WP03 / T011 / D11: no inline ``coord_branch if coord_branch else
    planning_branch`` grammar (the forbidden pattern named in
    contracts/seam-api.md's consumer table). When a ``placement_ref`` was
    threaded (modern, non-legacy missions), it is already the ONE
    seam-resolved :class:`CommitTarget` planning artifacts AND status events
    resolve to (C-PLACE-1) -- use its ``.ref`` directly instead of
    reconstructing the coord/primary choice a second time from
    ``coord_branch``. Genuinely-legacy missions (no ``placement_ref``) keep
    the existing meta-derived placeholder -- out of this WP's scope (#2453;
    the value is never persisted).

    WP02 / T007 / FR-003 / INV-1: pre-fix, the ``elif coord_branch:`` (meta-
    derived) branch below committed EVERY file in ``files_to_commit`` through
    ONE transaction to the coordination branch, so a genuinely-dirty PRIMARY
    artifact would land on coordination, never the primary/target branch.
    Post-fix, THAT branch partitions ``files_to_commit``
    (:func:`_partition_files_for_commit`) into a PRIMARY group (committed to
    ``planning_branch``, the mission's target branch) and a COORD-residue
    group (committed to the coordination branch) -- two transactions when
    both groups are non-empty, mirroring
    ``commit_router._group_files_by_partition``'s own two-group split.

    write-path-integrity WP02 / T008 / FR-001 (SANCTIONED C-004 reversal):
    the ``if placement_ref is not None:`` branch is NO LONGER a verbatim
    whole-batch commit. It now partitions ``files_to_commit`` exactly like the
    meta-derived ``else`` arm -- the PRIMARY group commits to the mission's
    target branch (honoured via ``commit_to_primary_target=True`` so the
    transaction does not redirect it onto coord) and the COORD-residue group
    commits to ``placement_ref.ref`` (the coordination ref). This closes the
    #3371 P0 where a PRIMARY ``lanes.json`` was committed onto the coordination
    branch and add/add-conflicted at lane allocation. The prior "one ref for
    everything" contract (and its pinned test
    ``test_effective_destination_ref_is_placement_ref_verbatim``) is rewritten
    (not deleted) to assert BOTH partition refs receive their group (T010).

    #2648 (WP01) narrow-triple fail-close: this function has exactly FOUR
    ``placement_ref``/``coord_branch``/protection outcomes, and only ONE of
    them raises --

    - ``placement_ref is not None`` -- partition-aware commit: PRIMARY group to
      the target branch, COORD-residue group to ``placement_ref.ref`` (T008).
    - ``placement_ref is None`` and ``not coord_branch`` -- flat/legacy
      mission, single transaction to ``planning_branch`` (C-004 strangler,
      unchanged).
    - ``placement_ref is None`` and ``coord_branch`` truthy and
      ``is_protected(planning_branch)`` -- the NARROW TRIPLE: raises
      :class:`PlacementResolutionRequired` with the SAME operator message as
      the status-commit half (``_resolve_claim_commit_target``,
      implement_cores.py). A real mission's ``planning_branch`` is never
      main/master (it is the mission's dedicated feature branch), so this
      only fires for a degenerate fixture/edge case or a torn-down topology;
      pre-fix, this arm silently diverted the WHOLE dirty-PRIMARY batch to
      the coordination branch instead of raising -- a genuinely-dirty
      PRIMARY artifact would never reach ``planning_branch`` and the operator
      would get no signal that the write placement is undecidable. Loud
      fail-close beats a silent wrong-branch commit here (D11).
    - ``placement_ref is None`` and ``coord_branch`` truthy and
      ``planning_branch`` is NOT protected -- meta-derived coordination
      mission, partition-aware split (unchanged: see ``T007`` below).

    Only the narrow triple raises; the other three outcomes still commit.
    """
    (
        coord_branch,
        mission_id,
        mid8,
        effective_mission_id,
        effective_mid8,
    ) = _resolve_bookkeeping_transaction_identifiers(feature_dir, mission_slug, repo_root)

    # WP06 / T019 / C-PLACE-1: the placement destination is the context's single
    # ``placement_ref`` when threaded — one ref for planning artifacts AND status
    # events. Under a flattened/primary topology there is no coord branch
    # (``CommitTarget`` is ref-only; the retired ``.kind``/FLATTENED arm is gone),
    # so ``coord_branch`` collapses to ``None`` and the commit lands on
    # ``planning_branch`` (== target == coordination); under coordination
    # topology it is the coord ref. Identity (``mission_id`` / ``mid8``) is
    # unaffected — only the placement decision moves to the context (C-005).
    if placement_ref is not None:
        coord_branch = _placement_coord_filter(repo_root, mission_slug, placement_ref)

    is_legacy = not (coord_branch and mission_id and mid8)
    if is_legacy:
        console.print(
            f"\n[cyan]Auto-committing planning artifacts to {planning_branch}...[/cyan] "
            f"[dim](legacy path -- mission has no coordination_branch; "
            f"routed through BookkeepingTransaction for FR-020/FR-027 atomicity)[/dim]"
        )

    if placement_ref is not None:
        # write-path-integrity WP02 / T008 / FR-001 (SANCTIONED C-004 reversal):
        # the seam-resolved ``placement_ref.ref`` is the COORD ref under
        # coordination topology. Pre-fix this arm committed the WHOLE batch
        # (PRIMARY ``lanes.json`` / ``spec.md`` included) VERBATIM to that coord
        # ref -- the #3371 P0 that landed PRIMARY ``lanes.json`` on the
        # coordination branch and add/add-conflicted at lane allocation. Post-fix
        # this arm partitions the batch exactly like the meta-derived ``else`` arm
        # below: the PRIMARY group commits to the mission's target branch
        # (``_commit_target_ref_for(planning_branch)``, honoured by
        # ``commit_to_primary_target=True`` so the transaction does not redirect
        # it to coord), and the COORD-residue group commits to the coordination
        # ref (``placement_ref.ref``). Only the non-empty group(s) run
        # (skip-empty caller guard, mirroring the ``else`` arm -- no empty
        # transaction). The Seam-A guard (``enforce_partition=True``) fails loud on
        # any partition mis-route on either leg (FR-002 / T011).
        primary_files, coord_files = _partition_files_for_commit(files_to_commit)
        if primary_files:
            _run_planning_artifact_commit(
                repo_root=repo_root,
                mission_id=effective_mission_id,
                mission_slug=mission_slug,
                mid8=effective_mid8,
                destination_ref=_commit_target_ref_for(planning_branch),
                files=primary_files,
                commit_msg=commit_msg,
                commit_to_primary_target=True,
                enforce_partition=True,
            )
        if coord_files:
            _run_planning_artifact_commit(
                repo_root=repo_root,
                mission_id=effective_mission_id,
                mission_slug=mission_slug,
                mid8=effective_mid8,
                destination_ref=placement_ref.ref,
                files=coord_files,
                commit_msg=commit_msg,
                enforce_partition=True,
            )
    elif not coord_branch:
        # Flattened/legacy mission: no coordination branch at all -- the
        # historical single transaction to ``planning_branch``, routed
        # through the shared ``_commit_target_ref_for`` expression (FR-005 ref
        # half) so this write-side destination and the read-side idempotency
        # compare cannot silently diverge (#2650 / WP04).
        _run_planning_artifact_commit(
            repo_root=repo_root,
            mission_id=effective_mission_id,
            mission_slug=mission_slug,
            mid8=effective_mid8,
            destination_ref=_commit_target_ref_for(planning_branch),
            files=files_to_commit,
            commit_msg=commit_msg,
        )
    elif ProtectionPolicy.resolve(repo_root).is_protected(planning_branch):
        # #2648 (WP01) narrow-triple fail-close: ``placement_ref is None`` AND
        # the meta-derived ``coord_branch`` is truthy AND
        # ``is_protected(planning_branch)`` -- EXACTLY the precondition where
        # the status-commit half (``_resolve_claim_commit_target``,
        # implement_cores.py) already raises ``PlacementResolutionRequired``.
        # Pre-fix, this arm silently diverted the WHOLE dirty-PRIMARY batch to
        # the coordination branch instead of the (protected) target branch --
        # a genuinely-dirty PRIMARY artifact would never reach
        # ``planning_branch``. Raising here (rather than falling back to a
        # coord-only commit) makes both halves of the claim agree: neither
        # commits partially or silently when the canonical write placement
        # cannot be resolved for a protected planning branch.
        raise PlacementResolutionRequired(
            "Cannot resolve the canonical write placement for this mission's "
            "WP status claim commit -- refusing to commit to the currently "
            "checked-out branch (D11 fail-closed). This usually means the "
            "mission's stored topology could not be resolved (e.g. a "
            "coordination branch declared in meta.json is missing/torn down "
            "in git). Run `spec-kitty doctor workspaces --fix`, or flatten "
            "the mission by removing `coordination_branch` from meta.json if "
            "the coordination topology was never used, then retry."
        )
    else:
        # T007: meta-derived coordination mission -- partition-aware commit.
        # A genuinely-dirty PRIMARY artifact lands on ``planning_branch``
        # (never coordination); COORD-residue artifacts still land on the
        # coordination branch. Only the group(s) that are non-empty run.
        primary_files, coord_files = _partition_files_for_commit(files_to_commit)
        if primary_files:
            # FR-005 ref half (#2650 / WP04): the PRIMARY-group destination
            # is derived from the SAME ``_commit_target_ref_for`` expression the
            # read-side idempotency compare uses -- one source of the
            # cli-side PRIMARY ref, not two independently-written literals.
            # WP02 / FR-001: ``commit_to_primary_target=True`` so the transaction
            # commits this group to the target branch from the primary checkout
            # instead of redirecting it onto the coordination branch.
            _run_planning_artifact_commit(
                repo_root=repo_root,
                mission_id=effective_mission_id,
                mission_slug=mission_slug,
                mid8=effective_mid8,
                destination_ref=_commit_target_ref_for(planning_branch),
                files=primary_files,
                commit_msg=commit_msg,
                commit_to_primary_target=True,
                enforce_partition=True,
            )
        if coord_files:
            _run_planning_artifact_commit(
                repo_root=repo_root,
                mission_id=effective_mission_id,
                mission_slug=mission_slug,
                mid8=effective_mid8,
                destination_ref=str(coord_branch),
                files=coord_files,
                commit_msg=commit_msg,
                enforce_partition=True,
            )

    if is_legacy:
        console.print(f"[green]✓[/green] Planning artifacts committed to {planning_branch}")
    else:
        console.print(f"[green]✓[/green] Planning artifacts committed to coordination branch {coord_branch}")


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
        console.print("Run /spec-kitty.specify first to create feature structure")
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
    wp_file = find_wp_file(repo_root, mission_slug, wp_id)
    declared_deps = parse_wp_dependencies(wp_file)
    return auto_commit, mission_slug, feature_dir, wp_file, declared_deps


def _raise_if_status_commit_protected(repo_root: Path, planning_branch: str, auto_commit: bool | None) -> None:
    """Raise ``ValueError`` when auto-commit is on and the pre-lane status
    commit would target a protected branch."""
    if not auto_commit:
        return
    status_destination = _status_commit_destination_branch(repo_root, fallback_branch=planning_branch)
    protected_error = _protected_branch_status_commit_error(status_destination, repo_root)
    if protected_error is not None:
        raise ValueError(protected_error)


def _execution_mode_for_workspace(resolved_workspace: Any) -> str:
    """``"direct_repo"`` for a repository-root planning workspace, else
    ``"worktree"``."""
    return "direct_repo" if resolved_workspace.resolution_kind == "repo_root" else "worktree"


def _ensure_wp_claim_preconditions(status_feature_dir: Path, wp_id: str, declared_deps: Any) -> None:
    """Raise if *wp_id* is unseeded (T012 / Contract 3) or a declared
    dependency is not yet ``approved``/``done``."""
    from specify_cli.core.dependency_graph import dependency_readiness_for_wp
    from specify_cli.status import reduce as _reduce_events
    from specify_cli.status import read_events as _read_events

    _snapshot = _reduce_events(_read_events(status_feature_dir))
    wp_lanes = {_wp_id: _state.get("lane", Lane.GENESIS) for _wp_id, _state in _snapshot.work_packages.items()}
    # T012 / Contract 3: reject unseeded WPs BEFORE any workspace
    # allocation. A genesis WP has not been through finalize-tasks; the
    # user must run it first to seed the genesis→planned bootstrap event.
    current_wp_lane = wp_lanes.get(wp_id, Lane.GENESIS)
    if current_wp_lane == Lane.GENESIS:
        # FR-009: same rejection (and exception type) as the lifecycle layer,
        # so programmatic callers catching WorkPackageStartRejected see this
        # path too (review M5).
        raise WorkPackageStartRejected(f"WP {wp_id} is not finalized; run `spec-kitty agent mission finalize-tasks`")
    # Thread per-dependency provenance so a canceled-with-operator-provenance
    # dependency counts as resolved (FR-009). `spec-kitty implement WP##` is the
    # primary claim command (CLAUDE.md: "the only supported way to prepare a
    # workspace"); collapsing to a lane-only map here would leave the #2945
    # strand trap open on the main claim path (review REJECT), mirroring the
    # workflow_executor gate fix.
    # Pre-flight UX only (FR-014, fsm-write-path-integrity WP04). The authoritative
    # dependency gate is `GuardContext.dependency_ready`, resolved in-lock by the emit shells.
    dependency_readiness = dependency_readiness_for_wp(wp_id, declared_deps, wp_lanes, provenance=_snapshot.work_packages)
    if not dependency_readiness.satisfied:
        blocked = ", ".join(dependency_readiness.unsatisfied)
        raise ValueError(f"dependencies_not_satisfied: {wp_id} depends on {blocked}; all dependencies must be approved or done before implementation can start")


def _run_bulk_edit_gate_and_inference(feature_dir: Path, wp_file: Path, mission_slug: str, wp_id: str, acknowledge_not_bulk_edit: bool) -> None:
    """Bulk-edit occurrence-classification gate (FR-006) + inference warning
    (FR-009). Raises ``typer.Exit(1)`` on a gate failure or an un-acknowledged
    triggered inference; a silent return means the claim may proceed."""
    from specify_cli.bulk_edit.gate import ensure_occurrence_classification_ready, render_gate_failure

    gate_result = ensure_occurrence_classification_ready(feature_dir)
    if not gate_result.passed:
        render_gate_failure(gate_result, console)
        raise typer.Exit(1)

    if gate_result.change_mode is not None:
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
    from specify_cli.lanes.compute import is_planning_lane

    if is_planning_lane(resolved_workspace):
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
    _validate_base_ref(repo_root, base)
    return base, lanes_manifest


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
        planning_branch = resolve_feature_target_branch(mission_slug, repo_root)
        _raise_if_status_commit_protected(repo_root, planning_branch, auto_commit)

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
        # implement (#3371). See :func:`_resolve_lanes_dir`.
        _lanes_feature_dir: Path = _resolve_lanes_dir(repo_root, mission_slug)

        # T012 / Contract 3 + dependency gate: reject unseeded WPs and
        # not-yet-ready dependencies BEFORE any workspace allocation.
        _ensure_wp_claim_preconditions(_status_feature_dir, wp_id, declared_deps)

        # WP06 / T019 / C-PLACE-1: resolve the single artifact-placement ref from
        # the canonical context so implement-claim never reconciles a
        # primary↔coord planning-artifact split (#1816). The placement ref is the
        # SAME CommitTarget status events resolve to. Resolution is best-effort:
        # on a context-resolution error we pass ``None`` and the helper keeps the
        # legacy meta-derived path (C-004 strangler — never break the lifecycle).
        _placement_ref = _resolve_placement_ref(repo_root, mission_slug=mission_slug, wp_id=wp_id)

        _ensure_planning_artifacts_committed_git(
            repo_root=repo_root,
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            planning_branch=planning_branch,
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
    status_execution_mode = _execution_mode_for_workspace(resolved_workspace)
    try:
        # WP04/T015 (FR-004/NFR-003/SC-004): the pre-write claim triple rides
        # the planned -> claimed transition's policy_metadata sidecar (see
        # _start_wp_implementation_status below). The former frontmatter
        # dual-write mirror was removed in the #2816 unconditional cutover, so
        # `spec-kitty implement` writes 0 runtime bytes to the WP file.
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
        )
        workspace_path = result.workspace_path
        branch_name = result.branch_name

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
        console.print(f"\n[red]Error:[/red] Workspace allocation failed: {exc}")
        # F-50 (#3937): a tooling/allocation failure emits NO lifecycle
        # transition. ``create_lane_workspace`` runs BEFORE the claim, so the WP
        # is still ``planned``, and the allocator self-cleans (abort +
        # ``reset --hard``, no ``lanes.json`` write). The former
        # ``_emit_blocked_on_alloc_failure`` manufactured ``planned -> blocked``,
        # an unrecoverable state (``blocked -> planned`` is illegal). Leaving the
        # WP ``planned`` is recoverable and reentrant — at parity with the
        # orchestrator-api path, which never emits ``blocked``. Surface the
        # exception's actionable ``next_step`` for the conflict types that carry
        # one, so the operator gets the concrete resolution rather than a
        # generic "re-run".
        if isinstance(exc, (DependencyLaneMergeConflictError, PlanningCommitMergeConflictError)):
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


__all__ = ["_ensure_vcs_in_meta", "find_wp_file", "implement"]
