"""Workspace context management for runtime visibility.

This module manages persistent workspace context files stored in .kittify/workspaces/.
These files provide runtime visibility into workspace state for LLM agents and CLI tools.

Context files are:
- Created during `spec-kitty implement` command
- Stored in main repo's .kittify/workspaces/ directory
- Readable from both main repo and worktrees (via relative path)
- Cleaned up during merge or explicit workspace deletion

Execution topology is determined by work-package execution mode:
- code_change WPs resolve to a lane worktree
- planning_artifact WPs resolve to the main repository root
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from specify_cli.core.atomic import atomic_write
from kernel.git_topology import GitTopologyError, git_toplevel
from specify_cli.lanes.branch_naming import worktree_dir_name, worktree_path as _seam_worktree_path
from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.ownership.inference import infer_execution_mode, score_execution_mode_signals
from specify_cli.ownership.models import WorkProductKind
from specify_cli.ownership.workspace_strategy import create_planning_workspace
# Deep import: status.emit imports this module during status/__init__ execution,
# so the status facade is not yet initialized here — importing from it would cycle.
from specify_cli.status.wp_metadata import WPMetadata, read_authored_wp_frontmatter


#: Operator recovery command named by workspace husk resolution errors
#: (NFR-003, #1833). Pinned by tests — keep in sync with the doctor command.
WORKSPACE_HUSK_RECOVERY_COMMAND = "spec-kitty doctor workspaces --fix"


class WorkspaceResolutionError(RuntimeError):
    """Structured workspace resolution failure (#1833 — fall-through is failure).

    Raised (or rendered) when a resolved lane workspace path is not an actual
    git worktree, so git commands invoked there would silently walk up and
    operate on the primary repository.
    """

    def __init__(self, *, workspace_path: Path, failed_check: str, detail: str) -> None:
        self.workspace_path = workspace_path
        self.failed_check = failed_check
        self.detail = detail
        super().__init__(
            f"Workspace resolution failed: {workspace_path} failed check '{failed_check}'. "
            f"{detail} "
            f"Recover with: {WORKSPACE_HUSK_RECOVERY_COMMAND}"
        )


def husk_resolution_error(workspace_path: Path) -> WorkspaceResolutionError:
    """Build the structured error for a husk directory (exists, no ``.git`` entry)."""
    return WorkspaceResolutionError(
        workspace_path=workspace_path,
        failed_check="git-worktree-marker (.git entry)",
        detail=(
            "The directory exists but contains no .git entry (a stale 'husk'); "
            "git commands run there would fall through to the primary repository "
            "and produce misattributed verdicts."
        ),
    )


def verify_workspace_toplevel(workspace_path: Path) -> WorkspaceResolutionError | None:
    """Assert ``git -C <path> rev-parse --show-toplevel`` resolves to the path itself.

    Last-line defense for workspace paths arriving from other resolver
    lineages (#1833 R4). Returns a structured error on mismatch or git
    failure, ``None`` when the path is the toplevel of its own working tree.

    The toplevel probe is delegated to the unified
    :func:`~kernel.git_topology.git_toplevel` primitive (mission
    write-path-integrity-01KZZD69 WP01, #3373); the primitive's typed failure is
    mapped to this site's ``git-toplevel`` structured error, preserving the
    is-worktree assertion contract.
    """
    try:
        actual_toplevel = git_toplevel(workspace_path)
    except GitTopologyError as exc:
        return WorkspaceResolutionError(
            workspace_path=workspace_path,
            failed_check="git-toplevel",
            detail=f"git rev-parse --show-toplevel failed: {exc}.",
        )
    if actual_toplevel != workspace_path.resolve():
        return WorkspaceResolutionError(
            workspace_path=workspace_path,
            failed_check="git-toplevel",
            detail=(
                f"git resolves the working tree toplevel to {actual_toplevel}, "
                f"not the resolved workspace path {workspace_path}."
            ),
        )
    return None


_FEATURE_CONTEXT_INDEX_CACHE: dict[tuple[str, str], dict[str, WorkspaceContext]] = {}
_FEATURE_WP_METADATA_CACHE: dict[tuple[str, str], dict[str, NormalizedWorkPackage]] = {}
_FEATURE_WP_METADATA_ERROR_CACHE: dict[tuple[str, str], dict[str, ValueError]] = {}
_FEATURE_WP_METADATA_SNAPSHOT_CACHE: dict[tuple[str, str], tuple[tuple[str, int], ...]] = {}


@dataclass(frozen=True)
class NormalizedWorkPackage:
    """Mission-scoped in-memory normalized WP metadata.

    A legacy WP may be missing ``execution_mode`` on disk. This structure keeps
    the normalized typed metadata in memory so every caller sees the same
    classification result for the lifetime of the process.
    """

    wp_id: str
    path: Path
    metadata: WPMetadata
    mode_source: str
    diagnostic: str | None = None


def clear_workspace_resolution_caches() -> None:
    """Invalidate all process-local workspace resolution caches."""
    _FEATURE_CONTEXT_INDEX_CACHE.clear()
    _FEATURE_WP_METADATA_CACHE.clear()
    _FEATURE_WP_METADATA_ERROR_CACHE.clear()
    _FEATURE_WP_METADATA_SNAPSHOT_CACHE.clear()


def _clear_feature_context_index_cache() -> None:
    """Invalidate the process-local feature context index cache."""
    _FEATURE_CONTEXT_INDEX_CACHE.clear()


@dataclass
class WorkspaceContext:
    """
    Runtime context for a work package workspace.

    Provides all information an agent needs to understand workspace state.
    Stored as JSON in .kittify/workspaces/###-feature-lane-x.json
    """

    # Identity
    wp_id: str  # e.g., "WP02"
    mission_slug: str  # e.g., "010-lane-only-runtime"

    # Paths
    worktree_path: str  # Relative path from repo root (e.g., ".worktrees/010-feature-lane-a")
    branch_name: str  # Git branch name (e.g., "kitty/mission-010-feature-lane-a")

    # Base tracking
    base_branch: str  # Branch this was created from (e.g., "kitty/mission-010-feature-lane-a" or "main")
    base_commit: str | None  # Git SHA this was created from; None when unavailable

    # Dependencies
    dependencies: list[str]  # List of WP IDs this depends on (e.g., ["WP01"])

    # Metadata
    created_at: str  # ISO timestamp when workspace was created
    created_by: str  # Command that created this (e.g., "implement-command")
    vcs_backend: str  # "git" or "jj"

    # Lane fields
    lane_id: str  # e.g., "lane-a"
    lane_wp_ids: list[str]  # All WPs assigned to this lane
    current_wp: str | None = None  # Which WP is currently active in the lane

    # Lane-specific test database isolation env vars (FR-006).
    # Empty dict for repo-root planning workspaces (no parallel-lane DB risk).
    # Populated by `lane_test_env(mission_slug, lane_id)` so two parallel
    # SaaS / Django lanes cannot collide on a single shared test DB.
    lane_test_env: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkspaceContext:
        """Create from dictionary (JSON deserialization)."""
        import dataclasses

        field_names = {f.name for f in dataclasses.fields(cls)}
        filtered = {k: v for k, v in data.items() if k in field_names}
        if not filtered.get("lane_id"):
            raise ValueError("Workspace context is missing required lane_id")
        if not isinstance(filtered.get("lane_wp_ids"), list):
            raise ValueError("Workspace context is missing required lane_wp_ids")
        if filtered.get("base_commit") == "unknown":
            filtered["base_commit"] = None
        return cls(**filtered)


@dataclass(frozen=True)
class ResolvedWorkspace:
    """Resolved workspace contract for a work package.

    This describes the execution workspace that owns a work package.
    """

    mission_slug: str
    wp_id: str
    execution_mode: str
    mode_source: str
    resolution_kind: str
    workspace_name: str
    worktree_path: Path
    branch_name: str | None
    lane_id: str | None
    lane_wp_ids: list[str]
    context: WorkspaceContext | None = None

    @property
    def exists(self) -> bool:
        """Return True when the resolved worktree is an actual git worktree on disk.

        A bare directory under ``.worktrees/`` with no ``.git`` entry (a
        "husk", #1833) is NOT a usable workspace: git commands run there fall
        through to the primary repository. Note git worktrees carry a ``.git``
        *file* (not directory), so this checks entry existence, not type.
        The ``.git``-marker requirement applies to lane workspaces only; a
        ``repo_root`` resolution points at the primary checkout itself.
        """
        if not self.worktree_path.exists():
            return False
        if self.resolution_kind != "lane_workspace":
            return True
        return (self.worktree_path / ".git").exists()

    @property
    def is_husk(self) -> bool:
        """Return True for a lane workspace path that exists but lacks ``.git``.

        Husks must be treated as absent-but-blocked: callers should surface a
        structured error (see :func:`husk_resolution_error`) instead of
        silently recreating a worktree on top — recreation hides the anomaly.
        """
        return (
            self.resolution_kind == "lane_workspace"
            and self.worktree_path.exists()
            and not (self.worktree_path / ".git").exists()
        )


@dataclass(frozen=True)
class ActiveWPResolution:
    """Active WP ownership resolved for a lane branch at guard time."""

    mission_slug: str | None = None
    wp_id: str | None = None
    owned_files: list[str] = field(default_factory=list)
    lane_id: str | None = None
    branch_name: str | None = None
    context_source: str = "absent"
    diagnostic_code: str | None = None
    diagnostic_message: str | None = None
    warnings: list[str] = field(default_factory=list)


def get_workspaces_dir(repo_root: Path) -> Path:
    """Get or create the workspaces context directory.

    Args:
        repo_root: Repository root path

    Returns:
        Path to .kittify/workspaces/ directory
    """
    workspaces_dir = repo_root / ".kittify" / "workspaces"
    workspaces_dir.mkdir(parents=True, exist_ok=True)
    return workspaces_dir


def get_context_path(repo_root: Path, workspace_name: str) -> Path:
    """Get path to workspace context file.

    Args:
        repo_root: Repository root path
        workspace_name: Workspace name (e.g., "010-feature-lane-a")

    Returns:
        Path to context JSON file
    """
    workspaces_dir = get_workspaces_dir(repo_root)
    return workspaces_dir / f"{workspace_name}.json"


def save_context(repo_root: Path, context: WorkspaceContext) -> Path:
    """Save workspace context to JSON file.

    Args:
        repo_root: Repository root path
        context: Workspace context to save

    Returns:
        Path to saved context file
    """
    # The context-JSON filename is keyed to the on-disk lane-worktree dir name;
    # compose it through the seam (emit-don't-guess, FR-005). Legacy grammar
    # ({slug}-{lane}, no mid8) ⇒ mission_id=None reproduces it byte-identically.
    workspace_name = worktree_dir_name(
        context.mission_slug, mission_id=None, lane_id=context.lane_id
    )
    context_path = get_context_path(repo_root, workspace_name)

    # Write JSON with pretty formatting
    content = json.dumps(context.to_dict(), indent=2) + "\n"
    atomic_write(context_path, content)
    _clear_feature_context_index_cache()

    return context_path


def load_context(repo_root: Path, workspace_name: str) -> WorkspaceContext | None:
    """Load workspace context from JSON file.

    Args:
        repo_root: Repository root path
        workspace_name: Workspace name (e.g., "010-feature-lane-a")

    Returns:
        WorkspaceContext if file exists, None otherwise
    """
    context_path = get_context_path(repo_root, workspace_name)

    if not context_path.exists():
        return None

    try:
        data = json.loads(context_path.read_text(encoding="utf-8"))
        return WorkspaceContext.from_dict(data)
    except (json.JSONDecodeError, TypeError, KeyError, ValueError):
        # Malformed context file
        return None


def delete_context(repo_root: Path, workspace_name: str) -> bool:
    """Delete workspace context file.

    Args:
        repo_root: Repository root path
        workspace_name: Workspace name (e.g., "010-feature-lane-a")

    Returns:
        True if deleted, False if didn't exist
    """
    context_path = get_context_path(repo_root, workspace_name)

    if context_path.exists():
        context_path.unlink()
        _clear_feature_context_index_cache()
        return True

    return False


def list_contexts(repo_root: Path) -> list[WorkspaceContext]:
    """List all workspace contexts.

    Args:
        repo_root: Repository root path

    Returns:
        List of all workspace contexts (empty if none exist)
    """
    workspaces_dir = get_workspaces_dir(repo_root)

    if not workspaces_dir.exists():
        return []

    contexts = []
    for context_file in sorted(workspaces_dir.glob("*.json"), key=lambda path: path.name):
        workspace_name = context_file.stem
        context = load_context(repo_root, workspace_name)
        if context:
            contexts.append(context)

    return contexts


def build_feature_context_index(
    repo_root: Path,
    mission_slug: str,
) -> dict[str, WorkspaceContext]:
    """Index feature contexts by WP ID, expanding lane contexts to all WPs.

    Lane-mode contexts are stored one-per-lane and retain `lane_wp_ids`, so a
    caller asking for WP01 should still find the lane context even after the
    active WP in that lane has advanced to WP02.
    """
    cache_key = (str(repo_root.resolve()), mission_slug)
    cached = _FEATURE_CONTEXT_INDEX_CACHE.get(cache_key)
    if cached is not None:
        return dict(cached)

    index: dict[str, WorkspaceContext] = {}

    for context in list_contexts(repo_root):
        if context.mission_slug != mission_slug:
            continue

        if context.lane_wp_ids:
            for lane_wp_id in context.lane_wp_ids:
                index.setdefault(lane_wp_id, context)

        if context.current_wp:
            index[context.current_wp] = context
        if context.wp_id:
            index.setdefault(context.wp_id, context)

    _FEATURE_CONTEXT_INDEX_CACHE[cache_key] = dict(index)
    return index


def find_context_for_wp(
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
) -> WorkspaceContext | None:
    """Return the lane workspace context for a work package."""
    return build_feature_context_index(repo_root, mission_slug).get(wp_id)


def resolve_active_wp_for_branch(
    repo_root: Path,
    branch_name: str,
) -> ActiveWPResolution:
    """Resolve the active WP for a lane branch from canonical status state.

    Shared lane worktrees are reused across sequential WPs. The workspace
    context can therefore identify the lane while its ``current_wp`` field may
    lag behind the canonical task board. This resolver treats canonical status
    as authoritative for the active WP and returns diagnostics instead of
    falling back to stale ownership when the active WP cannot be proven.
    """
    matching_contexts = [
        context
        for context in list_contexts(repo_root)
        if context.branch_name == branch_name
    ]
    if not matching_contexts:
        return ActiveWPResolution(branch_name=branch_name, context_source="absent")

    if len(matching_contexts) > 1:
        lanes = ", ".join(sorted(context.lane_id for context in matching_contexts))
        return ActiveWPResolution(
            branch_name=branch_name,
            context_source="workspace_context",
            diagnostic_code="ACTIVE_WP_CONTEXT_AMBIGUOUS",
            diagnostic_message=(
                "ACTIVE_WP_CONTEXT_AMBIGUOUS: Multiple workspace contexts match "
                f"branch {branch_name}; lanes: {lanes}"
            ),
        )

    context = matching_contexts[0]
    # STATUS leg (C-001): coord-aware — events may live in the coord husk.
    # WP09/FR-001 (kind-correct): route through the seam on ``STATUS_STATE``
    # rather than the kind-blind slug resolver (NFR-001) — same coord-aware
    # surface this comment already documents.
    feature_dir = placement_seam(repo_root, context.mission_slug).read_dir(
        MissionArtifactKind.STATUS_STATE
    )
    # PRIMARY leg (C-001): tasks/ WP-frontmatter always lives in the primary checkout.
    # read-side-placement-seam-migration WP07: names WORK_PACKAGE_TASK through
    # the seam authority instead of the kind-blind ``resolve_planning_read_dir``.
    # WORK_PACKAGE_TASK is PRIMARY-partition, so resolution is behavior-identical
    # to the prior resolver — the seam's fail-loud arm (NFR-002) is not reachable.
    planning_dir = placement_seam(repo_root, context.mission_slug).read_dir(
        MissionArtifactKind.WORK_PACKAGE_TASK
    )
    lane_wp_ids = _context_lane_wp_ids(context)

    if not feature_dir.is_dir():
        return _active_wp_diagnostic(
            context,
            code="ACTIVE_WP_CONTEXT_MISSING",
            message=f"Mission directory not found: {feature_dir}",
        )

    try:
        from specify_cli.status import get_all_wp_lanes
        from specify_cli.status import Lane

        lanes_by_wp = get_all_wp_lanes(feature_dir)
        active_candidates = [
            wp_id
            for wp_id in lane_wp_ids
            if lanes_by_wp.get(wp_id) == Lane.IN_PROGRESS
        ]
    except Exception as exc:
        return _active_wp_diagnostic(
            context,
            code="ACTIVE_WP_STATUS_UNAVAILABLE",
            message=f"Could not read canonical status for mission {context.mission_slug}: {exc}",
        )

    if len(active_candidates) != 1:
        candidates = ", ".join(active_candidates) if active_candidates else "none"
        lane_states = ", ".join(
            f"{wp_id}={lanes_by_wp.get(wp_id, Lane.UNINITIALIZED)}"
            for wp_id in lane_wp_ids
        )
        return _active_wp_diagnostic(
            context,
            code="ACTIVE_WP_CONTEXT_AMBIGUOUS",
            message=(
                f"Cannot prove active WP for branch {branch_name}; "
                f"lane_id={context.lane_id}; active candidates: {candidates}; "
                f"lane states: {lane_states}"
            ),
        )

    active_wp_id = active_candidates[0]
    warnings: list[str] = []
    if context.current_wp and context.current_wp != active_wp_id:
        warnings.append(
            "ACTIVE_WP_CONTEXT_STALE: "
            f"workspace context current_wp={context.current_wp}, "
            f"canonical active_wp={active_wp_id}; lane_id={context.lane_id}"
        )

    wp_path = _find_wp_file(planning_dir / "tasks", active_wp_id)
    if wp_path is None:
        return _active_wp_diagnostic(
            context,
            code="ACTIVE_WP_METADATA_MISSING",
            message=f"Could not find task file for active_wp={active_wp_id}",
            wp_id=active_wp_id,
        )

    try:
        metadata, _body = read_authored_wp_frontmatter(wp_path)
    except Exception as exc:
        return _active_wp_diagnostic(
            context,
            code="ACTIVE_WP_METADATA_INVALID",
            message=f"Could not read task frontmatter for active_wp={active_wp_id}: {exc}",
            wp_id=active_wp_id,
        )

    return ActiveWPResolution(
        mission_slug=context.mission_slug,
        wp_id=active_wp_id,
        owned_files=list(metadata.owned_files),
        lane_id=context.lane_id,
        branch_name=branch_name,
        context_source="canonical_status",
        warnings=warnings,
    )


def _context_lane_wp_ids(context: WorkspaceContext) -> list[str]:
    lane_wp_ids = list(context.lane_wp_ids)
    if not lane_wp_ids:
        lane_wp_ids = [wp_id for wp_id in (context.current_wp, context.wp_id) if wp_id]
    return lane_wp_ids


def _active_wp_diagnostic(
    context: WorkspaceContext,
    *,
    code: str,
    message: str,
    wp_id: str | None = None,
) -> ActiveWPResolution:
    return ActiveWPResolution(
        mission_slug=context.mission_slug,
        wp_id=wp_id,
        lane_id=context.lane_id,
        branch_name=context.branch_name,
        context_source="canonical_status",
        diagnostic_code=code,
        diagnostic_message=f"{code}: {message}",
    )


def _find_wp_file(tasks_dir: Path, wp_id: str) -> Path | None:
    if not tasks_dir.is_dir():
        return None
    return next(iter(sorted(tasks_dir.glob(f"{wp_id}*.md"))), None)


def _normalized_feature_cache_key(repo_root: Path, mission_slug: str, *, effective_root: Path | None = None) -> tuple[str, str]:
    from specify_cli.core.paths import get_main_repo_root

    read_root = effective_root if effective_root is not None else get_main_repo_root(repo_root)
    return (str(read_root.resolve()), mission_slug)


def _normalized_feature_snapshot(tasks_dir: Path) -> tuple[tuple[str, int], ...]:
    if not tasks_dir.is_dir():
        return ()
    snapshot: list[tuple[str, int]] = []
    for wp_file in sorted(tasks_dir.glob("WP*.md")):
        snapshot.append((wp_file.name, wp_file.stat().st_mtime_ns))
    return tuple(snapshot)


def _wp_id_from_path(wp_file: Path) -> str:
    match = re.match(r"^(WP\d{2,})(?:[-_.]|$)", wp_file.name)
    if match:
        return match.group(1)
    return wp_file.stem


def _normalize_wp_file(wp_file: Path, mission_slug: str) -> NormalizedWorkPackage:
    metadata, _body = read_authored_wp_frontmatter(wp_file)
    normalized_meta = metadata
    mode_source = "frontmatter"
    diagnostic: str | None = None

    raw_mode = metadata.execution_mode
    if raw_mode is None:
        raw_content = wp_file.read_text(encoding="utf-8")
        planning_score, code_score = score_execution_mode_signals(raw_content, list(metadata.owned_files))
        try:
            inferred_mode = infer_execution_mode(raw_content, list(metadata.owned_files))
            execution_mode = WorkProductKind(inferred_mode)
        except Exception as exc:  # pragma: no cover - defensive; covered by tests via monkeypatch
            raise ValueError(
                "Could not classify execution_mode for legacy work package "
                f"{metadata.work_package_id} in mission {mission_slug}. "
                "Add execution_mode to the WP frontmatter or rerun "
                f"`spec-kitty agent tasks finalize-tasks --mission {mission_slug}`."
            ) from exc

        normalized_meta = normalized_meta.update(execution_mode=str(execution_mode))
        mode_source = "inferred_legacy"
        if planning_score == 0 and code_score == 0:
            diagnostic = (
                f"Inferred execution_mode={execution_mode.value!r} for {metadata.work_package_id} "
                "by default — neither planning nor code signals were present in the WP body. "
                "Add an explicit execution_mode in the WP frontmatter to silence this default."
            )
        else:
            diagnostic = (
                f"Inferred execution_mode={execution_mode.value!r} for {metadata.work_package_id} from existing mission content."
            )
    else:
        try:
            execution_mode = WorkProductKind(raw_mode)
        except ValueError as exc:
            raise ValueError(f"Invalid execution_mode {raw_mode!r} for {metadata.work_package_id} in mission {mission_slug}.") from exc
        normalized_meta = normalized_meta.update(execution_mode=str(execution_mode))

    if normalized_meta.feature_slug != mission_slug:
        normalized_meta = normalized_meta.update(feature_slug=mission_slug)

    return NormalizedWorkPackage(
        wp_id=normalized_meta.work_package_id,
        path=wp_file,
        metadata=normalized_meta,
        mode_source=mode_source,
        diagnostic=diagnostic,
    )


def build_normalized_wp_index(
    repo_root: Path,
    mission_slug: str,
    *,
    effective_root: Path | None = None,
) -> dict[str, NormalizedWorkPackage]:
    """Load and normalize mission WP metadata once per process.

    Normalization is intentionally read-only. Missing ``execution_mode`` values
    for supported historical missions are inferred in memory so downstream
    callers share one canonical classification result.
    """
    cache_key = _normalized_feature_cache_key(repo_root, mission_slug, effective_root=effective_root)
    # read-side-placement-seam-migration WP07: names WORK_PACKAGE_TASK through
    # the seam authority instead of the kind-blind ``resolve_planning_read_dir``.
    # WORK_PACKAGE_TASK is PRIMARY-partition, so this is behavior-identical to
    # the prior resolver — no fail-loud arm is reachable here.
    tasks_dir = placement_seam(repo_root, mission_slug, effective_root=effective_root).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK) / "tasks"
    snapshot = _normalized_feature_snapshot(tasks_dir)
    cached = _FEATURE_WP_METADATA_CACHE.get(cache_key)
    if cached is not None and _FEATURE_WP_METADATA_SNAPSHOT_CACHE.get(cache_key) == snapshot:
        return dict(cached)

    index: dict[str, NormalizedWorkPackage] = {}
    errors: dict[str, ValueError] = {}

    if not tasks_dir.is_dir():
        _FEATURE_WP_METADATA_CACHE[cache_key] = {}
        _FEATURE_WP_METADATA_ERROR_CACHE[cache_key] = {}
        _FEATURE_WP_METADATA_SNAPSHOT_CACHE[cache_key] = snapshot
        return {}

    for wp_file in sorted(tasks_dir.glob("WP*.md")):
        try:
            normalized_wp = _normalize_wp_file(wp_file, mission_slug)
        except Exception as exc:
            if isinstance(exc, ValueError):
                error = exc
            else:
                error = ValueError(
                    f"Could not read work package metadata for {_wp_id_from_path(wp_file)} in mission {mission_slug}. Fix malformed frontmatter in {wp_file}."
                )
            errors[_wp_id_from_path(wp_file)] = error
            continue
        index[normalized_wp.wp_id] = normalized_wp

    _FEATURE_WP_METADATA_CACHE[cache_key] = dict(index)
    _FEATURE_WP_METADATA_ERROR_CACHE[cache_key] = dict(errors)
    _FEATURE_WP_METADATA_SNAPSHOT_CACHE[cache_key] = snapshot
    return dict(index)


def get_normalized_wp(
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
    *,
    effective_root: Path | None = None,
) -> NormalizedWorkPackage:
    """Return the normalized metadata entry for a work package."""
    cache_key = _normalized_feature_cache_key(repo_root, mission_slug, effective_root=effective_root)
    entry = build_normalized_wp_index(repo_root, mission_slug, effective_root=effective_root).get(wp_id)
    if entry is None:
        error = _FEATURE_WP_METADATA_ERROR_CACHE.get(cache_key, {}).get(wp_id)
        if error is not None:
            raise error
        raise ValueError(
            f"Work package {wp_id} was not found under "
            # read-side-placement-seam-migration WP07: named via the seam
            # authority (WORK_PACKAGE_TASK, PRIMARY-partition — no fail-loud
            # arm reachable) instead of ``resolve_planning_read_dir``.
            f"{placement_seam(repo_root, mission_slug, effective_root=effective_root).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK) / 'tasks'}"
        )
    return entry


def resolve_workspace_for_wp(
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
    *,
    write_intent: bool = False,
    current_cwd: Path | None = None,
    effective_root: Path | None = None,
) -> ResolvedWorkspace:
    """Resolve the real workspace/branch contract for a work package.

    Resolution order:
    1. Normalize WP metadata and execution mode once per process
    2. planning_artifact -> repository root
    3. Existing lane workspace context for code_change
    4. `lanes.json` lane mapping for code_change

    The returned path may not exist yet; callers can inspect `.exists`.

    Seam-B checkout-identity (write-path-integrity WP03, #3128 / FR-005). This is
    the single WP-mutation chokepoint that ``implement`` and ``review`` both
    funnel through. It is invoked ~20 times as a pure read vehicle, so the
    checkout-identity refusal keys on **explicit write-intent, never action-name**
    (C-007): only the true ``implement`` / ``review`` WP-write call sites pass
    ``write_intent=True``. When set, and the resolved workspace is a real lane
    worktree the invoking checkout does not own, this raises
    :class:`~mission_runtime.checkout_identity.CheckoutIdentityError` (a distinct
    exception NOT subclassing ``ActionContextError``). Reads (``write_intent``
    left ``False``), planning writes resolving to the primary checkout, and the
    mission's own worktrees are never refused. The comparison is pure-path — no
    git subprocess is invoked (NFR-004). ``current_cwd`` defaults to the process
    CWD; it is injectable for tests.
    """
    resolved = _resolve_workspace_for_wp_impl(repo_root, mission_slug, wp_id, effective_root=effective_root)
    if write_intent:
        from mission_runtime import enforce_checkout_identity
        from specify_cli.core.paths import get_main_repo_root

        enforce_checkout_identity(
            current_cwd=current_cwd if current_cwd is not None else Path.cwd(),
            workspace_path=resolved.worktree_path,
            primary_root=get_main_repo_root(repo_root),
            resolution_kind=resolved.resolution_kind,
            mission_slug=mission_slug,
            wp_id=wp_id,
        )
    return resolved


def _resolve_workspace_for_wp_impl(
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
    *,
    effective_root: Path | None = None,
) -> ResolvedWorkspace:
    """Resolve the ResolvedWorkspace for a WP (pure resolution, no identity gate).

    The Seam-B checkout-identity refusal is layered on by the public
    :func:`resolve_workspace_for_wp` wrapper so every one of this function's
    early-return arms is gated identically without duplicating the check.
    """
    normalized_wp = get_normalized_wp(repo_root, mission_slug, wp_id, effective_root=effective_root)
    execution_mode = WorkProductKind(normalized_wp.metadata.execution_mode or WorkProductKind.CODE_CHANGE)

    if effective_root is not None:
        # Owned mode supports single-branch missions only. Read lane membership
        # through the validated placement seam, but execute in that checkout;
        # never infer a new lane worktree or consult primary workspace caches.
        from specify_cli.lanes.persistence import require_lanes_json

        seam = placement_seam(repo_root, mission_slug, effective_root=effective_root)
        manifest = require_lanes_json(seam.read_dir(MissionArtifactKind.LANE_STATE))
        lane = manifest.lane_for_wp(wp_id)
        if lane is None:
            raise ValueError(f"{wp_id} is not assigned to a lane in the owned mission")
        return ResolvedWorkspace(
            mission_slug=mission_slug,
            wp_id=wp_id,
            execution_mode=execution_mode.value,
            mode_source=normalized_wp.mode_source,
            resolution_kind="repo_root",
            workspace_name=effective_root.name,
            worktree_path=effective_root,
            branch_name=manifest.target_branch,
            lane_id=lane.lane_id,
            lane_wp_ids=list(lane.wp_ids),
            context=None,
        )

    if execution_mode == WorkProductKind.PLANNING_ARTIFACT:
        # planning_artifact WPs are first-class lane-owned entities assigned to
        # "lane-planning".  That lane resolves to the main repository checkout.
        # We still call create_planning_workspace() for the path, but we now
        # populate lane_id so the ResolvedWorkspace contract is uniform.
        from specify_cli.lanes.compute import PLANNING_LANE_ID
        from specify_cli.lanes.persistence import read_lanes_json

        planning_workspace = create_planning_workspace(
            mission_slug=mission_slug,
            wp_code=wp_id,
            owned_files=list(normalized_wp.metadata.owned_files),
            repo_root=repo_root,
        )
        # Try to populate lane_wp_ids from lanes.json if available.
        # lanes.json is a PRIMARY-partition artifact (LANE_STATE kind).
        # read-side-placement-seam-migration WP07: named via the seam
        # authority instead of the kind-blind ``resolve_planning_read_dir``;
        # behavior-identical since LANE_STATE is PRIMARY-partition (no
        # fail-loud arm reachable here).
        lane_wp_ids: list[str] = []
        lanes_read_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.LANE_STATE)
        lanes_manifest = read_lanes_json(lanes_read_dir)
        if lanes_manifest is not None:
            planning_lane = lanes_manifest.lane_for_wp(wp_id)
            if planning_lane is not None:
                lane_wp_ids = list(planning_lane.wp_ids)

        return ResolvedWorkspace(
            mission_slug=mission_slug,
            wp_id=wp_id,
            execution_mode=execution_mode.value,
            mode_source=normalized_wp.mode_source,
            resolution_kind="repo_root",
            workspace_name=f"{mission_slug}-{PLANNING_LANE_ID}",
            worktree_path=planning_workspace,
            branch_name=None,
            lane_id=PLANNING_LANE_ID,
            lane_wp_ids=lane_wp_ids,
            context=None,
        )

    context = find_context_for_wp(repo_root, mission_slug, wp_id)
    if context is not None:
        worktree_path = repo_root / context.worktree_path
        return ResolvedWorkspace(
            mission_slug=mission_slug,
            wp_id=wp_id,
            execution_mode=execution_mode.value,
            mode_source=normalized_wp.mode_source,
            resolution_kind="lane_workspace",
            workspace_name=worktree_path.name,
            worktree_path=worktree_path,
            branch_name=context.branch_name,
            lane_id=context.lane_id,
            lane_wp_ids=list(context.lane_wp_ids),
            context=context,
        )

    # lanes.json is a PRIMARY-partition artifact (LANE_STATE kind).
    # read-side-placement-seam-migration WP07: named via the seam authority
    # instead of the kind-blind ``resolve_planning_read_dir``; behavior-
    # identical since LANE_STATE is PRIMARY-partition (no fail-loud arm
    # reachable here).
    lanes_read_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.LANE_STATE)
    from specify_cli.lanes.branch_naming import lane_branch_name
    from specify_cli.lanes.compute import PLANNING_LANE_ID, is_planning_lane
    from specify_cli.lanes.persistence import require_lanes_json, resolve_lanes_dir

    lanes_manifest = require_lanes_json(lanes_read_dir)
    lane = lanes_manifest.lane_for_wp(wp_id)
    if lane is None:
        raise ValueError(f"{wp_id} resolved to execution_mode={execution_mode.value!r} but is not assigned to any lane in {resolve_lanes_dir(lanes_read_dir)}")

    # lane-planning resolves to the main repository checkout, not a .worktrees/ path.
    if is_planning_lane(lane):
        target_branch = lanes_manifest.target_branch
        return ResolvedWorkspace(
            mission_slug=mission_slug,
            wp_id=wp_id,
            execution_mode=execution_mode.value,
            mode_source=normalized_wp.mode_source,
            resolution_kind="repo_root",
            workspace_name=f"{mission_slug}-{PLANNING_LANE_ID}",
            worktree_path=repo_root,
            branch_name=lane_branch_name(mission_slug, PLANNING_LANE_ID, planning_base_branch=target_branch),
            lane_id=PLANNING_LANE_ID,
            lane_wp_ids=list(lane.wp_ids),
            context=None,
        )

    # Route the COMPOSE (not just the .worktrees join) through the seam so no
    # name-guess survives the assign-then-join indirection (FR-005, WP09 ratchet).
    # Legacy worktree grammar ({slug}-{lane}, no mid8) ⇒ mission_id=None.
    workspace_name = worktree_dir_name(mission_slug, mission_id=None, lane_id=lane.lane_id)
    return ResolvedWorkspace(
        mission_slug=mission_slug,
        wp_id=wp_id,
        execution_mode=execution_mode.value,
        mode_source=normalized_wp.mode_source,
        resolution_kind="lane_workspace",
        workspace_name=workspace_name,
        worktree_path=_seam_worktree_path(repo_root, mission_slug, mission_id=None, lane_id=lane.lane_id),
        branch_name=lane_branch_name(mission_slug, lane.lane_id),
        lane_id=lane.lane_id,
        lane_wp_ids=list(lane.wp_ids),
        context=None,
    )


def resolve_lane_base_ref(
    repo_root: Path,
    lane_branch: str,
    *,
    fallback_base: str,
) -> str:
    """Return the base ref a lane worktree should be cut/attached from (#4969).

    When a teammate's approved lane has been pushed and fetched, it exists as
    ``refs/remotes/origin/<lane_branch>``. Cutting a fresh branch from local
    ``main`` in that case *shadows* the pushed work; this resolver prefers the
    origin ref so the lane is rooted on the teammate's tip instead.

    When no such origin ref exists (offline, no remote configured, or the lane
    was never pushed) it falls back to ``fallback_base`` — the existing
    local-cut behavior. This is **base resolution, not a terminus write**, so it
    must not fail closed on a missing origin ref.

    The origin-ref probe mirrors the ``git rev-parse --verify`` ref-resolution
    semantics of ``implement._validate_base_ref`` (WP03) via the canonical
    :func:`specify_cli.lanes._git.ref_exists` helper, so the two base-resolution
    sites agree on what "the origin lane exists" means. The returned value is the
    fully-qualified ``refs/remotes/origin/<lane_branch>`` ref, unambiguous
    against a same-named tag.
    """
    from specify_cli.lanes._git import ref_exists

    origin_ref = f"refs/remotes/origin/{lane_branch}"
    if ref_exists(repo_root, origin_ref):
        return origin_ref
    return fallback_base


def resolve_feature_worktree(repo_root: Path, mission_slug: str) -> Path | None:
    """Find a deterministic worktree to operate on for a feature.

    Prefer active lane workspace contexts first, then lane paths inferred from
    `lanes.json`.
    """
    for context in list_contexts(repo_root):
        if context.mission_slug != mission_slug:
            continue
        candidate = repo_root / context.worktree_path
        if candidate.is_dir():
            return candidate

    # lanes.json is a PRIMARY-partition artifact (LANE_STATE kind).
    # read-side-placement-seam-migration WP07: named via the seam authority
    # instead of the kind-blind ``resolve_planning_read_dir``; behavior-
    # identical since LANE_STATE is PRIMARY-partition (no fail-loud arm
    # reachable here).
    lanes_read_dir = placement_seam(repo_root, mission_slug).read_dir(
        MissionArtifactKind.LANE_STATE
    )
    from specify_cli.lanes.persistence import read_lanes_json

    lanes_manifest = read_lanes_json(lanes_read_dir)

    if lanes_manifest is not None:
        for lane in lanes_manifest.lanes:
            lane_candidate: Path = _seam_worktree_path(
                repo_root, mission_slug, mission_id=None, lane_id=lane.lane_id
            )
            if lane_candidate.is_dir():
                return lane_candidate
    return None


def find_orphaned_contexts(repo_root: Path) -> list[tuple[str, WorkspaceContext]]:
    """Find context files for workspaces that no longer exist.

    Args:
        repo_root: Repository root path

    Returns:
        List of (workspace_name, context) tuples for orphaned contexts
    """
    orphaned = []

    for context in list_contexts(repo_root):
        workspace_path = repo_root / context.worktree_path
        if not workspace_path.exists():
            workspace_name = worktree_dir_name(
                context.mission_slug, mission_id=None, lane_id=context.lane_id
            )
            orphaned.append((workspace_name, context))

    return orphaned


def cleanup_orphaned_contexts(repo_root: Path) -> int:
    """Remove context files for deleted workspaces.

    Args:
        repo_root: Repository root path

    Returns:
        Number of orphaned contexts cleaned up
    """
    orphaned = find_orphaned_contexts(repo_root)

    for workspace_name, _ in orphaned:
        delete_context(repo_root, workspace_name)

    return len(orphaned)


__all__ = [
    # ActiveWPResolution: demoted — no cross-module src/ from-import callers
    # (WP01 harden-dead-symbol-gate-01KW0RJR).
    "NormalizedWorkPackage",
    "ResolvedWorkspace",
    # WORKSPACE_HUSK_RECOVERY_COMMAND: demoted — no cross-module src/
    # from-import callers (WP01 harden-dead-symbol-gate-01KW0RJR).
    "WorkspaceContext",
    # WorkspaceResolutionError: demoted — no cross-module src/ from-import
    # callers (WP01 harden-dead-symbol-gate-01KW0RJR).
    # Resolution error raised and caught within this module; tests access
    # it via explicit import, which works regardless of __all__.
    "husk_resolution_error",
    "verify_workspace_toplevel",
    "build_normalized_wp_index",
    "build_feature_context_index",
    "clear_workspace_resolution_caches",
    "get_normalized_wp",
    "get_workspaces_dir",
    "get_context_path",
    "save_context",
    "load_context",
    "resolve_active_wp_for_branch",
    "resolve_lane_base_ref",
    "delete_context",
    "list_contexts",
    "find_context_for_wp",
    "resolve_workspace_for_wp",
    "resolve_feature_worktree",
    "find_orphaned_contexts",
    "cleanup_orphaned_contexts",
]
