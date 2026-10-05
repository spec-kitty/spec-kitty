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
from typing import TYPE_CHECKING, Any

from specify_cli.core.atomic import atomic_write
from kernel.git_topology import GitTopologyError, git_toplevel
from specify_cli.lanes.branch_naming import worktree_dir_name, worktree_path as _seam_worktree_path
from mission_runtime import MissionArtifactKind, OwnedCheckout, placement_seam, resolve_single_branch_write_ref, routes_through_coordination
from specify_cli.ownership.inference import infer_execution_mode, score_execution_mode_signals
from specify_cli.ownership.models import WorkProductKind
from specify_cli.ownership.workspace_strategy import create_planning_workspace

# Deep import: status.emit imports this module during status/__init__ execution,
# so the status facade is not yet initialized here — importing from it would cycle.
from specify_cli.status.wp_metadata import WPMetadata, read_authored_wp_frontmatter

if TYPE_CHECKING:
    # WP01 campsite split: type-only -- the runtime import lives inside
    # ``_resolve_workspace_for_wp_impl`` (mirrors the module's existing
    # lazy-import style) to avoid a module-level cross-package import.
    from specify_cli.lanes.models import ExecutionLane


#: Operator recovery command named by workspace husk resolution errors
#: (NFR-003, #1833). Pinned by tests — keep in sync with the doctor command.
WORKSPACE_HUSK_RECOVERY_COMMAND = "spec-kitty doctor workspaces --fix"

#: ``ResolvedWorkspace.resolution_kind`` for an owned single_branch mission's
#: workspace (owned-checkout-lifecycle-authority WP05, FR-006/FR-011): the
#: owned checkout itself. This is a ``serialized_keys`` value (it surfaces as
#: ``resolution_kind`` in ``context resolve --json``) — name it once here and
#: never retype the literal (Sonar S1192).
_OWNED_CHECKOUT_KIND = "owned_checkout"

#: Glob matching a mission's WP prompt files under ``tasks/`` (Sonar S1192).
_WP_FILE_GLOB = "WP*.md"


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
        super().__init__(f"Workspace resolution failed: {workspace_path} failed check '{failed_check}'. {detail} Recover with: {WORKSPACE_HUSK_RECOVERY_COMMAND}")


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
            detail=(f"git resolves the working tree toplevel to {actual_toplevel}, not the resolved workspace path {workspace_path}."),
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
    def runs_in_checkout_root(self) -> bool:
        """True when this workspace IS a checkout root, never a lane worktree.

        Both a ``repo_root`` resolution (the primary checkout) and an
        ``owned_checkout`` resolution (owned-checkout-lifecycle-authority WP05)
        point at a whole checkout, CWD-invariant and never a ``.worktrees/``
        entry. Downstream consumers that branch on ``resolution_kind ==
        "repo_root"`` to mean "a checkout root, not a lane worktree" should use
        this instead, so they treat the owned kind the same way.
        """
        return self.resolution_kind in ("repo_root", _OWNED_CHECKOUT_KIND)

    @property
    def status_execution_mode(self) -> str:
        """The status-event ``execution_mode`` stamp for this resolution (#5100 R-10).

        ``"direct_repo"`` when this workspace resolves to a checkout root
        (:attr:`runs_in_checkout_root` -- a ``repo_root`` planning-artifact /
        single_branch repo-root-lane WP, or an ``owned_checkout`` WP), else
        ``"worktree"``. This is
        the SINGLE derivation every status-emit call site uses; it replaces
        three previously copied ``"direct_repo" if ... else "worktree"``
        one-liners (``implement.py``, ``agent/workflow.py``,
        ``agent/workflow_executor.py``) and the hardcoded ``"worktree"``
        literals at the orchestrator-api and ``move-task`` call sites, so the
        stamp can never drift from ``resolution_kind`` at any of them.
        """
        return "direct_repo" if self.runs_in_checkout_root else "worktree"

    @property
    def exists(self) -> bool:
        """Return True when the resolved worktree is an actual git worktree on disk.

        A bare directory under ``.worktrees/`` with no ``.git`` entry (a
        "husk", #1833) is NOT a usable workspace: git commands run there fall
        through to the primary repository. Note git worktrees carry a ``.git``
        *file* (not directory), so this checks entry existence, not type.
        The ``.git``-marker requirement applies to lane workspaces only; a
        checkout-root resolution (``repo_root`` or ``owned_checkout``) points
        at a whole checkout and exists whenever the path exists.
        """
        if not self.worktree_path.exists():
            return False
        if self.runs_in_checkout_root:
            return True
        return (self.worktree_path / ".git").exists()

    @property
    def is_husk(self) -> bool:
        """Return True for a lane workspace path that exists but lacks ``.git``.

        Husks must be treated as absent-but-blocked: callers should surface a
        structured error (see :func:`husk_resolution_error`) instead of
        silently recreating a worktree on top — recreation hides the anomaly.
        An owned checkout is never a husk (it is not a git worktree of the
        repository root at all).
        """
        return self.resolution_kind == "lane_workspace" and self.worktree_path.exists() and not (self.worktree_path / ".git").exists()


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
    # compose it through the seam (emit-don't-guess, FR-005). Lane naming is
    # keyed on the creation input alone (WP07, FR-002/PD-1); no Mission
    # identity is passed here.
    workspace_name = worktree_dir_name(context.mission_slug, lane_id=context.lane_id)
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
    matching_contexts = [context for context in list_contexts(repo_root) if context.branch_name == branch_name]
    if not matching_contexts:
        return ActiveWPResolution(branch_name=branch_name, context_source="absent")

    if len(matching_contexts) > 1:
        lanes = ", ".join(sorted(context.lane_id for context in matching_contexts))
        return ActiveWPResolution(
            branch_name=branch_name,
            context_source="workspace_context",
            diagnostic_code="ACTIVE_WP_CONTEXT_AMBIGUOUS",
            diagnostic_message=(f"ACTIVE_WP_CONTEXT_AMBIGUOUS: Multiple workspace contexts match branch {branch_name}; lanes: {lanes}"),
        )

    context = matching_contexts[0]
    # STATUS leg (C-001): coord-aware — events may live in the coord husk.
    # WP09/FR-001 (kind-correct): route through the seam on ``STATUS_STATE``
    # rather than the kind-blind slug resolver (NFR-001) — same coord-aware
    # surface this comment already documents.
    feature_dir = placement_seam(repo_root, context.mission_slug).read_dir(MissionArtifactKind.STATUS_STATE)
    # PRIMARY leg (C-001): tasks/ WP-frontmatter always lives in the primary checkout.
    # read-side-placement-seam-migration WP07: names WORK_PACKAGE_TASK through
    # the seam authority instead of the kind-blind ``resolve_planning_read_dir``.
    # WORK_PACKAGE_TASK is PRIMARY-partition, so resolution is behavior-identical
    # to the prior resolver — the seam's fail-loud arm (NFR-002) is not reachable.
    planning_dir = placement_seam(repo_root, context.mission_slug).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)
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
        active_candidates = [wp_id for wp_id in lane_wp_ids if lanes_by_wp.get(wp_id) == Lane.IN_PROGRESS]
    except Exception as exc:
        return _active_wp_diagnostic(
            context,
            code="ACTIVE_WP_STATUS_UNAVAILABLE",
            message=f"Could not read canonical status for mission {context.mission_slug}: {exc}",
        )

    if len(active_candidates) != 1:
        candidates = ", ".join(active_candidates) if active_candidates else "none"
        lane_states = ", ".join(f"{wp_id}={lanes_by_wp.get(wp_id, Lane.UNINITIALIZED)}" for wp_id in lane_wp_ids)
        return _active_wp_diagnostic(
            context,
            code="ACTIVE_WP_CONTEXT_AMBIGUOUS",
            message=(f"Cannot prove active WP for branch {branch_name}; lane_id={context.lane_id}; active candidates: {candidates}; lane states: {lane_states}"),
        )

    active_wp_id = active_candidates[0]
    warnings: list[str] = []
    if context.current_wp and context.current_wp != active_wp_id:
        warnings.append(
            f"ACTIVE_WP_CONTEXT_STALE: workspace context current_wp={context.current_wp}, canonical active_wp={active_wp_id}; lane_id={context.lane_id}"
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


def _normalized_feature_cache_key(tasks_dir: Path, mission_slug: str) -> tuple[str, str]:
    """Cache key for the WP-metadata caches, keyed on the **resolved read
    tasks dir** (FR-019) — never on ``repo_root`` alone, or the same mission
    slug in two checkouts (the repository root and an owned checkout) would
    share one entry within a single process.
    """
    return (str(tasks_dir.resolve()), mission_slug)


def _wp_tasks_dir(
    repo_root: Path,
    mission_slug: str,
    *,
    owned: OwnedCheckout | None = None,
) -> Path:
    """The WP ``tasks/`` directory a WP-metadata lookup reads from.

    read-side-placement-seam-migration WP07: named via the seam authority
    instead of the kind-blind ``resolve_planning_read_dir``; behavior-
    identical since ``WORK_PACKAGE_TASK`` is PRIMARY-partition (no fail-loud
    arm reachable here). ``owned`` (owned-checkout-
    lifecycle-authority WP05) route the read through the owned checkout
    instead of the repository root.
    """
    seam = placement_seam(repo_root, mission_slug, owned=owned)
    return seam.read_dir(MissionArtifactKind.WORK_PACKAGE_TASK) / "tasks"


def _normalized_feature_snapshot(tasks_dir: Path) -> tuple[tuple[str, int], ...]:
    if not tasks_dir.is_dir():
        return ()
    snapshot: list[tuple[str, int]] = []
    for wp_file in sorted(tasks_dir.glob(_WP_FILE_GLOB)):
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
            diagnostic = f"Inferred execution_mode={execution_mode.value!r} for {metadata.work_package_id} from existing mission content."
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
    owned: OwnedCheckout | None = None,
) -> dict[str, NormalizedWorkPackage]:
    """Load and normalize mission WP metadata once per process.

    Normalization is intentionally read-only. Missing ``execution_mode`` values
    for supported historical missions are inferred in memory so downstream
    callers share one canonical classification result. ``owned``
    (owned-checkout-lifecycle-authority WP05, FR-019) routes
    the read through the owned checkout; every cache is keyed on the resolved
    ``tasks_dir``, not on ``repo_root``, so the same mission slug in two
    checkouts never shares one entry.
    """
    tasks_dir = _wp_tasks_dir(repo_root, mission_slug, owned=owned)
    cache_key = _normalized_feature_cache_key(tasks_dir, mission_slug)
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

    for wp_file in sorted(tasks_dir.glob(_WP_FILE_GLOB)):
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
    owned: OwnedCheckout | None = None,
) -> NormalizedWorkPackage:
    """Return the normalized metadata entry for a work package.

    ``owned`` (owned-checkout-lifecycle-authority WP05):
    forwarded to :func:`build_normalized_wp_index` so an owned checkout's
    tasks dir is read, never the repository root's.
    """
    entry = build_normalized_wp_index(repo_root, mission_slug, owned=owned).get(wp_id)
    if entry is not None:
        return entry
    tasks_dir = _wp_tasks_dir(repo_root, mission_slug, owned=owned)
    cache_key = _normalized_feature_cache_key(tasks_dir, mission_slug)
    error = _FEATURE_WP_METADATA_ERROR_CACHE.get(cache_key, {}).get(wp_id)
    if error is not None:
        raise error
    raise ValueError(f"Work package {wp_id} was not found under {tasks_dir}")


def resolve_workspace_for_wp(
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
    *,
    write_intent: bool = False,
    current_cwd: Path | None = None,
    owned: OwnedCheckout | None = None,
) -> ResolvedWorkspace:
    """Resolve the real workspace/branch contract for a work package.

    Resolution order:
    0. An owned single_branch mission (``owned`` set, non-coordination
       topology) -> the owned checkout itself (owned-checkout-lifecycle-
       authority WP05, FR-006/FR-011)
    1. Normalize WP metadata and execution mode once per process
    2. planning_artifact -> repository root
    3. `lanes.json` repo-root lane (single_branch, #5100 M8) -- BEFORE the
       persisted context lookup, so a stale context record can never shadow it
    4. Existing lane workspace context for code_change
    5. `lanes.json` lane mapping for code_change

    The returned path may not exist yet; callers can inspect `.exists`.

    A fact whose ``mission_slug`` differs from the ``mission_slug`` argument
    raises ``ValueError`` naming both. Only a validated fact produces the
    ``owned_checkout`` kind (no fact means no validated topology or target
    proof).

    Seam-B checkout-identity (write-path-integrity WP03, #3128 / FR-005). This is
    the single WP-mutation chokepoint that ``implement`` and ``review`` both
    funnel through. It is invoked ~20 times as a pure read vehicle, so the
    checkout-identity refusal keys on **explicit write-intent, never action-name**
    (C-007): only the true ``implement`` / ``review`` WP-write call sites pass
    ``write_intent=True``. When set, and the resolved workspace is a real lane
    worktree (or, for an owned mission, the owned checkout itself) the invoking
    checkout does not own, this raises
    :class:`~mission_runtime.checkout_identity.CheckoutIdentityError` (a distinct
    exception NOT subclassing ``ActionContextError``). Reads (``write_intent``
    left ``False``), planning writes resolving to the primary checkout, and the
    mission's own worktrees are never refused. The comparison is pure-path — no
    git subprocess is invoked (NFR-004). For an owned call the identity gate's
    ``primary_root`` is the fact's own ``repository_root`` (never
    ``get_main_repo_root``, so the owned arm makes no git call at all).
    ``current_cwd`` defaults to the process CWD; it is injectable for tests.
    """
    if owned is not None and owned.mission_slug != mission_slug:
        raise ValueError(f"owned fact is for mission {owned.mission_slug!r} but resolve_workspace_for_wp was called with mission_slug {mission_slug!r}")
    resolved = _resolve_workspace_for_wp_impl(repo_root, mission_slug, wp_id, owned=owned)
    if write_intent:
        from mission_runtime import enforce_checkout_identity

        if owned is not None:
            primary_root = owned.repository_root
        else:
            from specify_cli.core.paths import get_main_repo_root

            primary_root = get_main_repo_root(repo_root)

        enforce_checkout_identity(
            current_cwd=current_cwd if current_cwd is not None else Path.cwd(),
            workspace_path=resolved.worktree_path,
            primary_root=primary_root,
            resolution_kind=resolved.resolution_kind,
            mission_slug=mission_slug,
            wp_id=wp_id,
        )
    return resolved


def _lane_worktree_anchor(repo_root: Path, owned: OwnedCheckout | None) -> Path:
    """The repository root that lane / coordination worktree paths compose under.

    Lane and coordination worktrees live under the repository root checkout,
    never under an owned checkout ``P`` (owned-checkout-lifecycle-authority
    WP05, review cycle 1, HIGH-1). For an owned coordination-topology mission
    this is ``owned.repository_root``, regardless of whatever ``repo_root``
    the caller happened to pass (``next`` passes ``P``); for a non-owned
    mission it is the caller's ``repo_root`` unchanged.
    """
    return owned.repository_root if owned is not None else repo_root


def _planning_surface_root(repo_root: Path, owned: OwnedCheckout | None) -> Path:
    """The checkout a planning-lane / ``planning_artifact`` WP resolves to.

    The mission's planning surface IS the owned checkout for an owned
    mission (owned-checkout-lifecycle-authority WP05, review cycle 1,
    HIGH-1) — never the repository root, and never whatever ``repo_root``
    the caller happened to pass.
    """
    return owned.owned_root if owned is not None else repo_root


def _resolve_planning_artifact_arm(
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
    normalized_wp: NormalizedWorkPackage,
    execution_mode: WorkProductKind,
    *,
    owned: OwnedCheckout | None = None,
) -> ResolvedWorkspace | None:
    """Resolve a ``planning_artifact`` WP to the repo-root ``lane-planning`` lane.

    Returns ``None`` when ``execution_mode`` is not ``PLANNING_ARTIFACT``, so
    the caller falls through to the next arm. WP01 campsite split (behaviour-
    preserving) out of ``_resolve_workspace_for_wp_impl``.
    """
    if execution_mode != WorkProductKind.PLANNING_ARTIFACT:
        return None

    # planning_artifact WPs are first-class lane-owned entities assigned to
    # "lane-planning".  That lane resolves to the main repository checkout
    # (or, for an owned coordination-topology mission, the owned checkout
    # itself — the mission's planning surface, review cycle 1 HIGH-1).
    # We still call create_planning_workspace() for the path, but we now
    # populate lane_id so the ResolvedWorkspace contract is uniform.
    from specify_cli.lanes.compute import PLANNING_LANE_ID
    from specify_cli.lanes.persistence import read_lanes_json

    planning_workspace = create_planning_workspace(
        mission_slug=mission_slug,
        wp_code=wp_id,
        owned_files=list(normalized_wp.metadata.owned_files),
        repo_root=_planning_surface_root(repo_root, owned),
    )
    # Try to populate lane_wp_ids from lanes.json if available.
    # lanes.json is a PRIMARY-partition artifact (LANE_STATE kind).
    # read-side-placement-seam-migration WP07: named via the seam
    # authority instead of the kind-blind ``resolve_planning_read_dir``;
    # behavior-identical since LANE_STATE is PRIMARY-partition (no
    # fail-loud arm reachable here).
    lane_wp_ids: list[str] = []
    lanes_read_dir = placement_seam(repo_root, mission_slug, owned=owned).read_dir(MissionArtifactKind.LANE_STATE)
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


def _resolve_context_arm(
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
    normalized_wp: NormalizedWorkPackage,
    execution_mode: WorkProductKind,
    *,
    owned: OwnedCheckout | None = None,
) -> ResolvedWorkspace | None:
    """Resolve a WP to its already-persisted lane :class:`WorkspaceContext`.

    Returns ``None`` when no context is persisted yet, so the caller falls
    through to the ``lanes.json`` arms. WP01 campsite split (behaviour-
    preserving) out of ``_resolve_workspace_for_wp_impl``. The context
    registry lives under the repository root, never the owned checkout, and
    the context's relative ``worktree_path`` is joined under
    :func:`_lane_worktree_anchor` (review cycle 1, HIGH-1).
    """
    lane_anchor = _lane_worktree_anchor(repo_root, owned)
    context = find_context_for_wp(lane_anchor, mission_slug, wp_id)
    if context is None:
        return None
    worktree_path = lane_anchor / context.worktree_path
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


def _resolve_repo_root_lane_arm(
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
    normalized_wp: NormalizedWorkPackage,
    execution_mode: WorkProductKind,
    *,
    owned: OwnedCheckout | None = None,
) -> ResolvedWorkspace | None:
    """Resolve a WP whose ``lanes.json`` lane is a repo-root lane (#5100 M8).

    Checked BEFORE the persisted :class:`WorkspaceContext` arm (plan fold M8):
    a single_branch repo-root lane can hold CODE work packages (unlike the
    planning-only ``lane-planning`` lane every other topology carries), and a
    stale context record left over from before the mission adopted
    single_branch -- or from an unrelated prior run -- must never shadow this
    routing. Returns ``None`` when ``lanes.json`` is absent, the WP has no
    lane, or its lane is not a repo-root lane, so the caller falls through to
    the existing context / code-lane arms unchanged.

    The resolved ``branch_name`` follows the contract's resolve table
    (``contracts/single-branch-execution.md``): the mission's recorded
    ``meta.mission_branch`` when its STORED topology is ``single_branch`` (a
    protected-target mint, IC-05), else the manifest's ``target_branch`` --
    via :func:`mission_runtime.resolve_single_branch_write_ref`. ``worktree_path`` is the
    mission's planning surface (:func:`_planning_surface_root`): the repository
    root checkout, or the owned checkout for an owned coordination-topology
    mission (an owned single_branch mission never reaches this arm -- it is
    dispatched to :func:`_owned_checkout_workspace` first). For an owned
    mission the write branch is the validated fact's own ``target_branch``
    (already the #5100 write branch -- see ``owned_mission.expected_write_branch``).
    """
    from specify_cli.lanes.compute import PLANNING_LANE_ID, is_repo_root_lane
    from specify_cli.lanes.persistence import read_lanes_json

    lanes_read_dir = placement_seam(repo_root, mission_slug, owned=owned).read_dir(MissionArtifactKind.LANE_STATE)
    lanes_manifest = read_lanes_json(lanes_read_dir)
    if lanes_manifest is None:
        return None
    lane = lanes_manifest.lane_for_wp(wp_id)
    if lane is None or not is_repo_root_lane(lane):
        return None

    worktree_path = _planning_surface_root(repo_root, owned)
    # The write branch comes from the ONE mission_runtime rule over meta.json
    # (stored single_branch + meta.mission_branch, else the target branch) --
    # never from ``lanes.json.mission_branch``, which is a stale copy after a
    # protected landing clears the meta field, and which names the
    # integration branch (not the write branch) for a lanes/coord mission
    # whose code WP happens to sit in ``lane-planning``.
    branch_name = owned.write_branch if owned is not None else resolve_single_branch_write_ref(repo_root, mission_slug, lanes_manifest.target_branch)
    return ResolvedWorkspace(
        mission_slug=mission_slug,
        wp_id=wp_id,
        execution_mode=execution_mode.value,
        mode_source=normalized_wp.mode_source,
        resolution_kind="repo_root",
        workspace_name=f"{mission_slug}-{PLANNING_LANE_ID}",
        worktree_path=worktree_path,
        branch_name=branch_name,
        lane_id=PLANNING_LANE_ID,
        lane_wp_ids=list(lane.wp_ids),
        context=None,
    )


def _resolve_planning_lane_arm(
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
    normalized_wp: NormalizedWorkPackage,
    execution_mode: WorkProductKind,
    lane: ExecutionLane,
    target_branch: str,
    *,
    owned: OwnedCheckout | None = None,
) -> ResolvedWorkspace | None:
    """Resolve a WP whose ``lanes.json`` lane is ``lane-planning``.

    Returns ``None`` when ``lane`` is not the planning lane, so the caller
    falls through to the code-lane arm. WP01 campsite split (behaviour-
    preserving) out of ``_resolve_workspace_for_wp_impl``.
    """
    from specify_cli.lanes.branch_naming import lane_branch_name
    from specify_cli.lanes.compute import PLANNING_LANE_ID, is_planning_lane

    # lane-planning resolves to the mission's planning surface: the primary
    # checkout for a non-owned mission, or the owned checkout itself for an
    # owned coordination-topology mission (review cycle 1, HIGH-1) — never a
    # .worktrees/ path.
    if not is_planning_lane(lane):
        return None
    return ResolvedWorkspace(
        mission_slug=mission_slug,
        wp_id=wp_id,
        execution_mode=execution_mode.value,
        mode_source=normalized_wp.mode_source,
        resolution_kind="repo_root",
        workspace_name=f"{mission_slug}-{PLANNING_LANE_ID}",
        worktree_path=_planning_surface_root(repo_root, owned),
        branch_name=lane_branch_name(mission_slug, PLANNING_LANE_ID, target_branch=target_branch),
        lane_id=PLANNING_LANE_ID,
        lane_wp_ids=list(lane.wp_ids),
        context=None,
    )


def _resolve_code_lane_arm(
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
    normalized_wp: NormalizedWorkPackage,
    execution_mode: WorkProductKind,
    lane: ExecutionLane,
    *,
    owned: OwnedCheckout | None = None,
) -> ResolvedWorkspace:
    """Resolve a WP to its ``lanes.json`` code-change lane worktree.

    The final, always-non-``None`` arm: every WP that reaches this point has
    a code lane assigned. WP01 campsite split (behaviour-preserving) out of
    ``_resolve_workspace_for_wp_impl``.
    """
    from specify_cli.lanes.branch_naming import code_lane_branch_name

    # Route the COMPOSE (not just the .worktrees join) through the seam so no
    # name-guess survives the assign-then-join indirection (FR-005, WP09 ratchet).
    # Lane naming is keyed on the creation input alone (WP07, FR-002/PD-1).
    # The anchor is the repository root, never a caller-supplied ``repo_root``
    # that may name the owned checkout (review cycle 1, HIGH-1).
    lane_anchor = _lane_worktree_anchor(repo_root, owned)
    workspace_name = worktree_dir_name(mission_slug, lane_id=lane.lane_id)
    return ResolvedWorkspace(
        mission_slug=mission_slug,
        wp_id=wp_id,
        execution_mode=execution_mode.value,
        mode_source=normalized_wp.mode_source,
        resolution_kind="lane_workspace",
        workspace_name=workspace_name,
        worktree_path=_seam_worktree_path(lane_anchor, mission_slug, lane_id=lane.lane_id),
        branch_name=code_lane_branch_name(mission_slug, lane.lane_id),
        lane_id=lane.lane_id,
        lane_wp_ids=list(lane.wp_ids),
        context=None,
    )


def _owned_checkout_workspace(repo_root: Path, owned: OwnedCheckout, wp_id: str) -> ResolvedWorkspace:
    """The owned single_branch arm (owned-checkout-lifecycle-authority WP05, FR-006/FR-011).

    Applies to BOTH ``code_change`` and ``planning_artifact`` WPs: the
    mission's planning surface *is* the owned checkout, so there is no
    separate planning-lane sub-arm here (unlike the non-owned/coordination
    arms). Does not consult ``find_context_for_wp`` — that reads the
    repository root's ``.kittify/workspaces`` contexts, which describe lane
    worktrees, not the owned checkout. No git subprocess (NFR-002): every
    input is already a resolved path on the fact or read from disk via the
    placement seam.
    """
    normalized_wp = get_normalized_wp(repo_root, owned.mission_slug, wp_id, owned=owned)
    execution_mode = WorkProductKind(normalized_wp.metadata.execution_mode or WorkProductKind.CODE_CHANGE)
    return ResolvedWorkspace(
        mission_slug=owned.mission_slug,
        wp_id=wp_id,
        execution_mode=execution_mode.value,
        mode_source=normalized_wp.mode_source,
        resolution_kind=_OWNED_CHECKOUT_KIND,
        workspace_name=owned.owned_root.name,
        worktree_path=owned.owned_root,
        branch_name=owned.write_branch,
        lane_id=None,
        lane_wp_ids=[],
        context=None,
    )


def _resolve_workspace_for_wp_impl(
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
    *,
    owned: OwnedCheckout | None = None,
) -> ResolvedWorkspace:
    """Resolve the ResolvedWorkspace for a WP (pure resolution, no identity gate).

    The Seam-B checkout-identity refusal is layered on by the public
    :func:`resolve_workspace_for_wp` wrapper so every one of this function's
    early-return arms is gated identically without duplicating the check.

    Dispatch: an owned single_branch mission (``owned`` set and the fact's
    topology does not route through coordination — LANES cannot be minted
    owned) resolves through :func:`_owned_checkout_workspace` and never
    reaches the other arms. Everything else (non-owned, or an owned
    coordination-topology mission reachable only through ``next``) reads as a
    short dispatch over the per-arm helpers (WP01 campsite split), in today's
    precedence order: planning_artifact kind -> lanes.json repo-root lane
    (#5100 M8) -> persisted context -> lanes.json planning lane -> code lane.
    The repo-root-lane arm runs BEFORE the persisted context lookup so a stale
    context record can never shadow it. ``owned`` is threaded into every arm's
    WP-index and ``lanes.json`` reads so a coordination-topology owned mission
    reads from the owned checkout; the lane/context arms additionally anchor
    every filesystem path they compose on the fact (``owned.repository_root``
    for lane/coordination worktrees, ``owned.owned_root`` for the planning
    surface) rather than the caller-supplied ``repo_root`` (review cycle 1,
    HIGH-1 — ``next`` passes ``P``, which must never become the lane-worktree
    anchor). The arm order is behaviour — do not reorder.
    """
    if owned is not None and not routes_through_coordination(owned.topology):
        return _owned_checkout_workspace(repo_root, owned, wp_id)

    normalized_wp = get_normalized_wp(repo_root, mission_slug, wp_id, owned=owned)
    execution_mode = WorkProductKind(normalized_wp.metadata.execution_mode or WorkProductKind.CODE_CHANGE)

    planning_artifact_workspace = _resolve_planning_artifact_arm(repo_root, mission_slug, wp_id, normalized_wp, execution_mode, owned=owned)
    if planning_artifact_workspace is not None:
        return planning_artifact_workspace

    repo_root_lane_workspace = _resolve_repo_root_lane_arm(repo_root, mission_slug, wp_id, normalized_wp, execution_mode, owned=owned)
    if repo_root_lane_workspace is not None:
        return repo_root_lane_workspace

    context_workspace = _resolve_context_arm(repo_root, mission_slug, wp_id, normalized_wp, execution_mode, owned=owned)
    if context_workspace is not None:
        return context_workspace

    # lanes.json is a PRIMARY-partition artifact (LANE_STATE kind).
    # read-side-placement-seam-migration WP07: named via the seam authority
    # instead of the kind-blind ``resolve_planning_read_dir``; behavior-
    # identical since LANE_STATE is PRIMARY-partition (no fail-loud arm
    # reachable here).
    lanes_read_dir = placement_seam(repo_root, mission_slug, owned=owned).read_dir(MissionArtifactKind.LANE_STATE)
    from specify_cli.lanes.persistence import require_lanes_json, resolve_lanes_dir

    lanes_manifest = require_lanes_json(lanes_read_dir)
    lane = lanes_manifest.lane_for_wp(wp_id)
    if lane is None:
        raise ValueError(f"{wp_id} resolved to execution_mode={execution_mode.value!r} but is not assigned to any lane in {resolve_lanes_dir(lanes_read_dir)}")

    planning_lane_workspace = _resolve_planning_lane_arm(
        repo_root,
        mission_slug,
        wp_id,
        normalized_wp,
        execution_mode,
        lane,
        lanes_manifest.target_branch,
        owned=owned,
    )
    if planning_lane_workspace is not None:
        return planning_lane_workspace

    return _resolve_code_lane_arm(repo_root, mission_slug, wp_id, normalized_wp, execution_mode, lane, owned=owned)


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
    semantics of ``lanes.implement_support.resolve_base_ref`` (WP03) via the canonical
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
    lanes_read_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.LANE_STATE)
    from specify_cli.lanes.persistence import read_lanes_json

    lanes_manifest = read_lanes_json(lanes_read_dir)

    if lanes_manifest is not None:
        for lane in lanes_manifest.lanes:
            lane_candidate: Path = _seam_worktree_path(repo_root, mission_slug, lane_id=lane.lane_id)
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
            workspace_name = worktree_dir_name(context.mission_slug, lane_id=context.lane_id)
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


_WP_ID_RE = re.compile(r"^WP\d{2}$", re.IGNORECASE)


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

    Distinct from the private :func:`_find_wp_file` below, which globs an
    already-resolved ``tasks_dir`` for ``<wp_id>*.md`` and returns ``None`` when
    nothing matches; this public reader resolves the tasks dir itself through
    the seam, validates the ``WP##`` shape and raises ``FileNotFoundError``.
    """
    tasks_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK) / "tasks"
    if not tasks_dir.exists():
        raise FileNotFoundError(f"Tasks directory not found: {tasks_dir}")

    normalized_wp_id = wp_id.strip().upper()
    if not _WP_ID_RE.fullmatch(normalized_wp_id):
        raise FileNotFoundError(f"Invalid work package ID: {wp_id}. Expected format WP## (for example, WP01).")

    wp_name_re = re.compile(rf"^{re.escape(normalized_wp_id)}(?:[-_.].+)?\.md$", re.IGNORECASE)
    wp_files = sorted(path for path in tasks_dir.glob(_WP_FILE_GLOB) if wp_name_re.match(path.name))
    if not wp_files:
        raise FileNotFoundError(f"WP file not found for {normalized_wp_id} in {tasks_dir}")
    return wp_files[0]


def resolve_mission_target_branch(mission_slug: str, repo_root: Path) -> str:
    """Resolve the mission's configured target branch from metadata."""
    from specify_cli.core.git_ops import resolve_target_branch

    resolution = resolve_target_branch(
        mission_slug=mission_slug,
        repo_path=repo_root,
        respect_current=True,
    )
    target: str = resolution.target
    return target


def resolve_lane_state_dir(repo_root: Path, mission_slug: str) -> Path:
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

    Distinct from :func:`specify_cli.lanes.persistence.resolve_lanes_dir`
    (hence the name), which is a path-join helper (``feature_dir / lanes.json``);
    this function resolves the *feature_dir* itself from the artifact's
    canonical partition.
    """
    return placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.LANE_STATE)


__all__ = [
    "find_wp_file",
    "resolve_lane_state_dir",
    "resolve_mission_target_branch",
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
