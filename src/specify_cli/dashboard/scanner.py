"""Feature scanning helpers for the Spec Kitty dashboard."""

from __future__ import annotations

from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.paths import assert_safe_path_segment
import contextlib
import logging
import os
from kernel.clock import UTC, parse_iso
from kernel._safe_re import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from specify_cli.status.wp_view import WPView

from specify_cli.dashboard.charter_path import resolve_project_charter_presence
from specify_cli.lanes.branch_naming import resolve_mid8
from specify_cli.mission_metadata import load_meta
from specify_cli.missions._read_path_resolver import (
    MissionSelectorAmbiguous,
    resolve_planning_read_dir,
)
from specify_cli.upgrade.legacy_detector import is_legacy_format
from specify_cli.status import wp_state_for
from specify_cli.status import Lane
from specify_cli.status import NON_DISPLAY_LANES
from specify_cli.text_sanitization import sanitize_file


# Dashboard kanban column mapping, driven by WPState.lane (Lane enum).
# The dashboard renders 5 fixed columns; all 9 canonical lanes must map
# into one of them.  ``approved`` gets its own column because the dashboard
# distinguishes it from ``for_review`` (both have display_category "Review").
_KANBAN_COLUMN_FOR_LANE: dict[Lane, str] = {
    Lane.PLANNED: "planned",
    Lane.CLAIMED: "doing",
    Lane.IN_PROGRESS: "doing",
    Lane.FOR_REVIEW: "for_review",
    Lane.IN_REVIEW: "for_review",
    Lane.APPROVED: "approved",
    Lane.DONE: "done",
    Lane.BLOCKED: "planned",
    Lane.CANCELED: "done",
}

logger = logging.getLogger(__name__)

__all__ = [
    "build_mission_registry",
    "format_path_for_display",
    # gather_feature_paths: demoted — no cross-module src/ from-import callers
    # (WP01 harden-dead-symbol-gate-01KW0RJR).
    "get_feature_artifacts",
    "get_workflow_status",
    # read_file_resilient: demoted — no cross-module src/ from-import callers
    # (WP01 harden-dead-symbol-gate-01KW0RJR).
    "read_only_weighted_percentage",
    "resolve_feature_dir",
    "resolve_feature_planning_dir",
    "resolve_active_feature",
    "scan_all_features",
    "scan_feature_kanban",
    "sort_missions_for_display",
]


def read_file_resilient(file_path: Path, *, auto_fix: bool = True) -> tuple[str | None, str | None]:
    """Read a file with resilience to encoding errors.

    This function attempts to read a file as UTF-8, and if that fails:
    1. Tries alternative encodings (cp1252, latin-1)
    2. Optionally auto-fixes the file by sanitizing and re-saving as UTF-8
    3. Returns clear error messages for the dashboard to display

    Args:
        file_path: Path to the file to read
        auto_fix: If True, automatically sanitize and fix encoding errors

    Returns:
        Tuple of (content, error_message)
        - content: File content if successful, None if failed
        - error_message: None if successful, error description if failed

    Examples:
        >>> from pathlib import Path
        >>> content, error = read_file_resilient(Path("good-file.md"))
        >>> content is not None
        True
        >>> error is None
        True
    """
    if not file_path.exists():
        return None, f"File not found: {file_path.name}"

    try:
        # Try strict UTF-8 first
        content = file_path.read_text(encoding="utf-8-sig")
        return content, None
    except UnicodeDecodeError as exc:
        # Log the encoding error
        logger.warning(f"UTF-8 decoding failed for {file_path.name} at byte {exc.start}: {exc.reason}")

        if not auto_fix:
            return None, (
                f"Encoding error in {file_path.name} at byte {exc.start}. "
                f"File contains non-UTF-8 characters (possibly Windows-1252 smart quotes). "
                f"Run 'spec-kitty validate-encoding --fix' to repair."
            )

        # Attempt auto-fix
        try:
            logger.info(f"Attempting to auto-fix encoding for {file_path.name}")
            was_modified, error = sanitize_file(file_path, backup=True, dry_run=False)

            if error:
                return None, error

            if was_modified:
                # Read the fixed file
                content = file_path.read_text(encoding="utf-8-sig")
                logger.info(f"Successfully fixed encoding for {file_path.name}")
                return content, None
            else:
                # Shouldn't happen, but handle it
                return None, f"Auto-fix failed for {file_path.name}: no changes made"

        except Exception as fix_exc:
            logger.error(f"Auto-fix failed for {file_path.name}: {fix_exc}")
            return None, (
                f"Encoding error in {file_path.name} and auto-fix failed: {fix_exc}. Manually repair the file or run 'spec-kitty validate-encoding --fix'."
            )
    except Exception as exc:
        logger.error(f"Unexpected error reading {file_path.name}: {exc}")
        return None, f"Error reading {file_path.name}: {exc}"


def format_path_for_display(path_str: str | None) -> str | None:
    """Return a human-readable path that shortens the user's home directory."""
    if not path_str:
        return path_str

    try:
        path = Path(path_str).expanduser()
    except (TypeError, ValueError):
        return path_str

    try:
        resolved = path.resolve()
    except Exception:
        resolved = path

    try:
        home = Path.home().resolve()
    except Exception:
        home = Path.home()

    try:
        relative = resolved.relative_to(home)
    except ValueError:
        return str(resolved)

    relative_str = str(relative)
    if relative_str in {"", "."}:
        return "~"
    return f"~{os.sep}{relative_str}"


def format_feature_display_name(feature_id: str, friendly_name: str) -> str:
    """Return a dashboard label that preserves the numeric feature prefix."""
    label = friendly_name.strip() or feature_id
    number_match = re.match(r"^(\d+)", feature_id)
    if not number_match:
        return label

    feature_number = number_match.group(1)
    if re.match(rf"^{re.escape(feature_number)}(?:\b|[-:_\s])", label):
        return label

    return f"{feature_number} - {label}"


def _parse_created_at(value: object) -> float | None:
    """Return a comparable timestamp for ISO-8601 meta.json created_at values."""
    if not isinstance(value, str):
        return None

    raw = value.strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"

    try:
        parsed = parse_iso(raw)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.timestamp()


def _coerce_sort_mission_number(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


# Higher priority = sorted first (list uses reverse=True).
_MISSION_STATUS_PRIORITY: dict[str, int] = {"active": 3, "planned": 2, "done": 1, "draft": 0, "discarded": -1}


def _derive_mission_status(kanban_stats: dict[str, Any], meta_data: dict[str, Any] | None = None) -> str:
    """Derive mission lifecycle status from WP lane counts and lifecycle markers.

    Returns one of ``"active"``, ``"planned"``, ``"done"``, ``"draft"``, or
    ``"discarded"``.

    - ``"discarded"`` — ``discarded_at`` is set: the mission was abandoned via
      ``mission close --discard`` (#704). Checked first, because an abandoned
      mission's WP lane counts describe work that was thrown away, not work
      still active or done, so status must never be re-derived from them once
      the mission is marked discarded.
    - ``"active"``  — WPs in flight, OR all WPs terminal but mission not yet accepted
    - ``"planned"`` — no WP is active and planned work remains
    - ``"done"``    — all WPs terminal AND ``accepted_at`` is set in meta.json
    - ``"draft"``   — no WPs yet, or the event log is unreadable
    """
    if meta_data and meta_data.get("discarded_at"):
        return "discarded"
    if kanban_stats.get("error") or not kanban_stats.get("total", 0):
        return "draft"
    if kanban_stats.get("doing", 0) or kanban_stats.get("for_review", 0) or kanban_stats.get("approved", 0):
        return "active"
    if kanban_stats.get("planned", 0):
        return "planned"
    # All WPs terminal — only "done" once the operator has accepted the mission
    if meta_data and not meta_data.get("accepted_at"):
        return "active"
    return "done"


def _derive_next_action(meta_data: dict[str, Any], kanban_stats: dict[str, Any]) -> str | None:
    """Derive the next operator action from mission lifecycle markers in meta.json.

    spec-kitty merge writes ``baseline_merge_commit``; spec-kitty accept writes
    ``accepted_at``.  Together they let the dashboard surface what's still needed
    without calling the decision engine.
    """
    if not isinstance(meta_data, dict):
        return None
    if meta_data.get("accepted_at"):
        return None
    slug = meta_data.get("mission_slug") or meta_data.get("slug")
    if not isinstance(slug, str):
        return None
    try:
        slug = assert_safe_path_segment(slug)
    except ValueError:
        return None
    if meta_data.get("baseline_merge_commit"):
        return f"Run /spec-kitty.review, then: spec-kitty accept --mission {slug}"
    if not kanban_stats.get("error") and kanban_stats.get("total", 0) > 0:
        in_flight = kanban_stats.get("doing", 0) + kanban_stats.get("for_review", 0) + kanban_stats.get("approved", 0) + kanban_stats.get("planned", 0)
        if in_flight == 0 and kanban_stats.get("done", 0) > 0:
            return f"Run: spec-kitty merge --mission {slug}"
    return None


def _feature_recency_sort_key(feature: dict[str, Any]) -> tuple[int, bool, float, bool, str, bool, int, str]:
    """Sort selector rows: active first, then planned, then done/draft; newest-first within each bucket."""
    status = feature.get("mission_status", "draft")
    status_priority = _MISSION_STATUS_PRIORITY.get(status, 0)


    meta = feature.get("meta")
    if not isinstance(meta, dict):
        meta = {}

    created_at = _parse_created_at(meta.get("created_at"))
    mission_id = meta.get("mission_id")
    mission_id_key = mission_id.strip() if isinstance(mission_id, str) else ""
    mission_number = _coerce_sort_mission_number(meta.get("mission_number"))

    return (
        status_priority,
        created_at is not None,
        created_at if created_at is not None else float("-inf"),
        bool(mission_id_key),
        mission_id_key,
        mission_number is not None,
        mission_number if mission_number is not None else -1,
        str(feature.get("id", "")),
    )


def work_package_sort_key(task: dict[str, Any]) -> tuple:
    """Provide a natural sort key for work package identifiers."""
    work_id = str(task.get("id", "")).strip()
    if not work_id:
        return ((), "")

    number_parts = [int(part.lstrip("0") or "0") for part in re.findall(r"\d+", work_id)]
    return (tuple(number_parts), work_id.lower())


def _get_artifact_info(path: Path) -> dict[str, any]:
    """Get artifact information including existence, mtime, and size."""
    if not path.exists():
        return {"exists": False, "mtime": None, "size": None}

    stat = path.stat()
    return {
        "exists": True,
        "mtime": stat.st_mtime,
        "size": stat.st_size if path.is_file() else None,
    }


def get_feature_artifacts(
    feature_dir: Path,
    project_dir: Path | None = None,
) -> dict[str, dict[str, any]]:
    """Return which artifacts exist for a feature with modification info.

    Charter status is project-level. If project_dir is omitted, we fall back
    to feature_dir.parent.parent for compatibility with older call sites.

    FR-003 (#3150): the "charter" artifact's presence/mtime/size signal is
    keyed on ``resolve_project_charter_presence``, which prefers
    ``charter.yaml`` (the C-001 resolving authority) so the dashboard's "no
    charter" UI signal survives ``charter.md`` deletion, and falls back to
    ``charter.md`` when ``charter.yaml`` has not been compiled yet -- so a
    ``charter.md``-only project that never ran ``charter sync``/compile still
    reports a charter (landing-fold fix; do not narrow this back to a
    yaml-only signal). This is a presence probe only -- the prose body itself
    is served elsewhere (``dashboard/handlers/api.py`` ``handle_charter``) via
    the md-keyed ``resolve_project_charter_path``.
    """
    project_root = project_dir if project_dir is not None else feature_dir.parent.parent
    charter_path = resolve_project_charter_presence(project_root)

    charter_info = _get_artifact_info(charter_path) if charter_path is not None else {"exists": False, "mtime": None, "size": None}

    return {
        "charter": charter_info,
        "spec": _get_artifact_info(feature_dir / "spec.md"),
        "plan": _get_artifact_info(feature_dir / "plan.md"),
        "tasks": _get_artifact_info(feature_dir / "tasks.md"),
        "research": _get_artifact_info(feature_dir / "research.md"),
        "quickstart": _get_artifact_info(feature_dir / "quickstart.md"),
        "data_model": _get_artifact_info(feature_dir / "data-model.md"),
        "contracts": _get_artifact_info(feature_dir / "contracts"),
        "checklists": _get_artifact_info(feature_dir / "checklists"),
        "kanban": _get_artifact_info(feature_dir / "tasks"),
    }


def get_workflow_status(artifacts: dict[str, dict[str, any]]) -> dict[str, str]:
    """Determine workflow progression status."""
    has_spec = artifacts.get("spec", {}).get("exists", False)
    has_plan = artifacts.get("plan", {}).get("exists", False)
    has_tasks = artifacts.get("tasks", {}).get("exists", False)
    has_kanban = artifacts.get("kanban", {}).get("exists", False)

    workflow: dict[str, str] = {}

    if not has_spec:
        workflow.update({"specify": "pending", "plan": "pending", "tasks": "pending", "implement": "pending"})
        return workflow
    workflow["specify"] = "complete"

    if not has_plan:
        workflow.update({"plan": "pending", "tasks": "pending", "implement": "pending"})
        return workflow
    workflow["plan"] = "complete"

    if not has_tasks:
        workflow.update({"tasks": "pending", "implement": "pending"})
        return workflow
    workflow["tasks"] = "complete"

    workflow["implement"] = "in_progress" if has_kanban else "pending"
    return workflow


def gather_feature_paths(project_dir: Path) -> dict[str, Path]:
    """Collect candidate feature directories from root and worktrees.

    Resolution priority:
      1. Coordination worktree copies, when present, because they hold the
         authoritative live mission state during active coordination-topology
         missions.
      2. Main repo copies under ``kitty-specs/``.
      3. Lane worktree copies, which may be stale and should never outrank the
         coordination worktree or main checkout.
    """
    from specify_cli.coordination.surface_resolver import (
        WorktreeRegistryUnavailable,
        WorktreeTopology,
        classify_worktree_topology,
        read_worktree_registry,
    )

    feature_paths: dict[str, Path] = {}
    coord_paths: dict[str, Path] = {}

    # First scan worktrees. Lane worktrees stay low priority, while the
    # coordination worktree for a mission is remembered and applied last.
    worktrees_root = project_dir / ".worktrees"
    if worktrees_root.exists():
        # Read the git worktree registry once for the whole scan pass (name
        # proposes coord-ness; the registry disposes). A husk ``-coord`` dir
        # (suffix present, not registered) must NOT shadow the primary surface.
        try:
            registry = read_worktree_registry(project_dir)
        except WorktreeRegistryUnavailable:
            # No readable registry (e.g. project_dir is not a git repo in tests):
            # degrade to scanning all dirs as non-coord rather than failing the
            # whole dashboard scan. Coord copies simply do not outrank here.
            registry = None
        for worktree_dir in worktrees_root.iterdir():
            if not worktree_dir.is_dir():
                continue
            wt_specs = worktree_dir / KITTY_SPECS_DIR
            if not wt_specs.exists():
                continue
            is_coord_worktree = (
                registry is not None
                and classify_worktree_topology(
                    worktree_dir, repo_root=project_dir, registry=registry
                )
                is WorktreeTopology.COORD_WORKTREE
            )
            for feature_dir in wt_specs.iterdir():
                if feature_dir.is_dir():
                    if is_coord_worktree:
                        coord_paths[feature_dir.name] = feature_dir
                        continue
                    feature_paths[feature_dir.name] = feature_dir

    # Main checkout beats lane worktrees.
    root_specs = project_dir / KITTY_SPECS_DIR
    if root_specs.exists():
        for feature_dir in root_specs.iterdir():
            if feature_dir.is_dir():
                feature_paths[feature_dir.name] = feature_dir

    # Coordination worktrees beat everything else.
    feature_paths.update(coord_paths)

    return feature_paths


def _read_mission_identity(feature_dir: Path) -> tuple[str | None, int | None]:
    """Return (mission_id, mission_number) from meta.json, or (None, None) if unreadable.

    Returns empty strings coerced to None for mission_id.
    """
    raw = load_meta(feature_dir, on_malformed="none", encoding="utf-8-sig")
    if raw is None:
        return None, None
    mission_id: str | None = raw.get("mission_id") or None  # "" -> None
    raw_number = raw.get("mission_number")
    mission_number: int | None = None
    if isinstance(raw_number, int):
        mission_number = raw_number
    elif isinstance(raw_number, str) and raw_number.isdigit():
        with contextlib.suppress(ValueError):
            mission_number = int(raw_number)
    return mission_id, mission_number


def _resolve_identity_primary_first(
    project_dir: Path, feature_dir: Path
) -> tuple[str | None, int | None]:
    """Resolve ``(mission_id, mission_number)`` from the PRIMARY surface (#2331).

    Mission identity (``meta.json``) is a PRIMARY-partition artifact: it lives on
    the primary checkout, never the coordination worktree. But
    :func:`gather_feature_paths` prefers the coord worktree copy (it holds live
    *status*), and that copy has no ``meta.json`` mid-orchestration — so reading
    identity off the scanned ``feature_dir`` orphaned a valid in-flight mission.

    Read identity through the kind-aware read seam
    (:func:`resolve_planning_read_dir` with ``PRIMARY_METADATA``, the same seam the
    coord-read fixes use to anchor primary artifacts), and only fall back to the
    scanned ``feature_dir`` when the primary copy is absent/identity-less (e.g.
    lane-only or pre-3.1 layouts) so no merged/idle mission regresses.
    """
    from mission_runtime import MissionArtifactKind  # noqa: PLC0415 — late import, cold-start cost

    slug = feature_dir.name
    try:
        primary_dir = resolve_planning_read_dir(
            project_dir, slug, kind=MissionArtifactKind.PRIMARY_METADATA
        )
    except (ValueError, MissionSelectorAmbiguous):
        # Unsafe slug segment (traversal guard) or an ambiguous handle — the
        # dashboard scan must never crash, so keep the scanned dir.
        return _read_mission_identity(feature_dir)

    mission_id, mission_number = _read_mission_identity(primary_dir)
    if mission_id is None and mission_number is None and primary_dir != feature_dir:
        return _read_mission_identity(feature_dir)
    return mission_id, mission_number


def _resolve_planning_dir_primary_first(project_dir: Path, feature_dir: Path) -> Path:
    """Resolve the *planning* surface for one scanned feature dir (#2430).

    :func:`gather_feature_paths` returns ONE dir per feature, coord-first —
    the right priority for live *status* (the append-only event log lives on
    the coordination branch for coord-topology missions, C-001), but wrong for
    *planning* artifacts: ``spec-commit`` lands ``spec.md`` / ``plan.md`` /
    ``tasks.md`` / ``tasks/`` / ``meta.json`` on the PRIMARY surface for every
    topology (write-surface-coherence). A scanned ``-coord`` dir therefore
    holds only status writes mid-mission, and reading planning artifacts off
    it made a PR-bound feature-branch mission invisible (#2430) — the same
    coord-shadows-primary class as #2331.

    Resolve the planning surface primary-first through the kind-aware read
    seam (:func:`resolve_planning_read_dir` with ``TASKS_INDEX``, the same
    seam #2331 uses for identity). Fall back to the scanned dir when the
    resolver declines (unsafe segment, ambiguous handle) or the resolved dir
    does not exist, so legacy / lane-only / test layouts keep their existing
    behavior. The scanned ``feature_dir`` itself remains the status surface —
    gather's registry-classified coord preference already encodes that.
    """
    from mission_runtime import MissionArtifactKind  # noqa: PLC0415 — late import, cold-start cost

    try:
        candidate = resolve_planning_read_dir(
            project_dir, feature_dir.name, kind=MissionArtifactKind.TASKS_INDEX
        )
    except (ValueError, MissionSelectorAmbiguous):
        return feature_dir
    if candidate.exists():
        return candidate
    return feature_dir


def _mission_record_key(feature_dir: Path, mission_id: str | None, mission_number: int | None) -> str:
    """Compute the canonical registry key for a mission.

    - Assigned (mission_id present, mission_number present): use mission_id
    - Pending (mission_id present, mission_number absent): use mission_id
    - Legacy (mission_id absent, mission_number present): use ``legacy:<slug>``
    - Orphan (both absent): use ``orphan:<path.name>``
    """
    if mission_id is not None:
        return mission_id
    slug = feature_dir.name
    if mission_number is not None:
        return f"legacy:{slug}"
    return f"orphan:{slug}"


def build_mission_registry(project_dir: Path) -> dict[str, dict[str, Any]]:
    """Return a dict keyed by ``mission_id`` (or pseudo-key) mapping to mission records.

    Each record is a minimal dict with at least:
    - ``mission_id``: str — the ULID (or the pseudo-key for legacy/orphan)
    - ``mission_slug``: str — the directory name
    - ``display_number``: int | None — the numeric prefix for display sorting
    - ``mid8``: str | None — first 8 chars of mission_id (None for pseudo-keys)

    Duplicate numeric prefixes produce DISTINCT records because each gets its own
    ``mission_id`` key.  The three ``080-*`` missions on a real repo each appear
    as a separate entry.

    Args:
        project_dir: Repository root containing ``kitty-specs/``.

    Returns:
        ``{mission_id_or_pseudo_key: record}`` dict.
    """
    registry: dict[str, dict[str, Any]] = {}
    feature_paths = gather_feature_paths(project_dir)

    for _feature_id, feature_dir in feature_paths.items():
        # Identity is PRIMARY-anchored (#2331); status/display keep the scanned
        # (possibly coord) feature_dir below.
        mission_id, mission_number = _resolve_identity_primary_first(project_dir, feature_dir)
        key = _mission_record_key(feature_dir, mission_id, mission_number)

        # mid8 is meaningful only when key is an actual mission_id (ULID).
        # Route through the authoritative resolver (WP03 / FR-009); ``or None``
        # preserves the registry's ``mid8 is None`` contract for pseudo keys and
        # missing identities (resolve_mid8 declines to ``""``, never ``None``).
        is_pseudo = key.startswith(("legacy:", "orphan:"))
        mid8: str | None = (
            None
            if is_pseudo
            else (resolve_mid8(feature_dir.name, mission_id=mission_id) or None)
        )

        registry[key] = {
            "mission_id": key,  # canonical key, may be pseudo
            "mission_slug": feature_dir.name,
            "display_number": mission_number,
            "mid8": mid8,
            "feature_dir": str(feature_dir),
        }

    return registry


def sort_missions_for_display(registry: dict[str, dict[str, Any]]) -> list[str]:
    """Return an ordered list of registry keys suitable for display.

    Sort order:
    1. ``display_number`` ascending (missions with a numeric prefix come first)
    2. ``None`` display_number last (pre-merge / pending missions)
    3. Secondary: ``mission_slug`` ascending (stable tie-break among same-prefix missions)

    Args:
        registry: Output of :func:`build_mission_registry`.

    Returns:
        Ordered list of mission_id strings (or pseudo-keys).
    """

    def _sort_key(key: str) -> tuple[int, int, str]:
        record = registry[key]
        number = record.get("display_number")
        slug = record.get("mission_slug", key)
        # None sorts last: use (1, 0, slug) vs (0, number, slug)
        if number is None:
            return (1, 0, slug)
        return (0, number, slug)

    return sorted(registry.keys(), key=_sort_key)


def resolve_feature_dir(project_dir: Path, feature_id: str) -> Path | None:
    """Resolve the on-disk directory for the requested feature."""
    feature_paths = gather_feature_paths(project_dir)
    return feature_paths.get(feature_id)


def resolve_feature_planning_dir(project_dir: Path, feature_id: str) -> Path | None:
    """Resolve the PLANNING surface for the requested feature (#2502).

    :func:`resolve_feature_dir` is coord-first — correct for live *status*
    (the event log lives on the coordination branch), wrong for *planning*
    artifacts (``spec.md`` / ``plan.md`` / ``research*`` / ``contracts/`` /
    ``checklists/`` live on the primary surface for every topology). An
    in-flight coordination mission's coord copy is a status-only husk, so an
    artifact viewer reading it renders empty (#2502) — the same
    coord-shadows-primary class as #2331/#2430.

    Compose the coord-first resolver with the primary-first planning
    re-anchor so viewer endpoints read the surface that actually holds the
    content. For non-coordination missions both resolve to the same dir.
    """
    feature_dir = resolve_feature_dir(project_dir, feature_id)
    if feature_dir is None:
        return None
    return _resolve_planning_dir_primary_first(project_dir, feature_dir)


def resolve_active_feature(
    project_dir: Path,  # noqa: ARG001
) -> dict[str, Any] | None:
    """Return None — active feature cannot be auto-detected; requires explicit --mission.

    This function is retained for backward-compatible call sites. Without
    auto-detection, we cannot determine the active feature without an explicit
    feature slug from the caller.
    """
    return None


def _count_wps_by_lane(tasks_dir: Path, status_dir: Path | None = None) -> dict[str, int]:
    """Count work packages by lane from the canonical event log.

    Raises ``CanonicalStatusNotFoundError`` when the event log is absent.
    WPs not present in the event log are treated as ``genesis`` and excluded
    from display counts until finalize-tasks seeds them.

    ``status_dir`` names the surface holding the canonical event log; under
    coordination topology it differs from the planning surface that holds
    ``tasks/`` (#2430). ``None`` derives it from ``tasks_dir`` as before.

    Lane-to-column mapping is driven by :meth:`WPState.display_category`
    via :data:`_KANBAN_COLUMN_MAP`.
    """
    counts = {"planned": 0, "doing": 0, "for_review": 0, "approved": 0, "done": 0}

    if not tasks_dir.exists():
        return counts

    # Default: the event log lives beside tasks/ (single-surface layouts).
    feature_dir = status_dir if status_dir is not None else tasks_dir.parent

    from specify_cli.status import get_all_wp_lanes

    event_lanes = get_all_wp_lanes(feature_dir)

    for wp_file in tasks_dir.glob("WP*.md"):
        stem = wp_file.stem
        wp_id_match = re.match(r"^(WP\d+)", stem, re.IGNORECASE)
        wp_id = wp_id_match.group(1).upper() if wp_id_match else stem

        lane = event_lanes.get(wp_id, Lane.GENESIS)

        # Genesis/uninitialized WPs are non-display and must not inflate planned.
        # NON_DISPLAY_LANES is the single canonical authority (models.py); Lane
        # is a StrEnum so membership works whether ``lane`` is a Lane or a
        # plain str (both hash/compare equal to the same string value).
        if lane in NON_DISPLAY_LANES:
            continue
        state = wp_state_for(lane)
        column = _KANBAN_COLUMN_FOR_LANE.get(state.lane, "planned")
        if column in counts:
            counts[column] += 1

    return counts


def _read_dashboard_feature_meta(feature_dir: Path) -> tuple[str, dict[str, Any] | None]:
    """Return the display name and sanitized meta.json fields for a dashboard row."""
    friendly_name = feature_dir.name
    meta_data = load_meta(feature_dir, on_malformed="none", encoding="utf-8-sig")
    if meta_data is None:
        return friendly_name, None

    potential_name = meta_data.get("friendly_name")
    if isinstance(potential_name, str) and potential_name.strip():
        friendly_name = potential_name.strip()

    # Keep purpose summary data inside meta so the dashboard can render it
    # without widening the typed feature payload.
    for key in ("purpose_tldr", "purpose_context"):
        value = meta_data.get(key)
        if isinstance(value, str) and value.strip():
            meta_data[key] = " ".join(value.split())

    return friendly_name, meta_data


def _resolve_feature_worktree_info(project_dir: Path, feature_dir: Path) -> dict[str, Any]:
    """Return dashboard worktree metadata for a selected feature directory."""
    worktrees_root = project_dir / ".worktrees"
    if feature_dir.is_relative_to(worktrees_root):
        worktree_root = feature_dir.parents[1]
        return {
            "path": format_path_for_display(str(worktree_root)),
            "exists": True,
        }

    worktree_path = worktrees_root / feature_dir.name
    return {
        "path": format_path_for_display(str(worktree_path)),
        "exists": worktree_path.exists(),
    }


def _build_legacy_kanban_stats(tasks_dir: Path) -> dict[str, int]:
    kanban_stats = {"total": 0, "planned": 0, "doing": 0, "for_review": 0, "approved": 0, "done": 0}
    for lane in ["planned", "doing", "for_review", "done"]:
        lane_dir = tasks_dir / lane
        if lane_dir.exists():
            count = len(list(lane_dir.rglob("WP*.md")))
            kanban_stats[lane] = count
            kanban_stats["total"] += count
    return kanban_stats


def read_only_weighted_percentage(feature_dir: Path) -> float | None:
    """Return the weighted-progress percentage for ``feature_dir`` read-only.

    WP11 / FR-014(a) / IC-12: the dashboard is a *viewer*. Computing progress
    for a kanban request MUST NOT write tracked status (``status.json``) as a
    side-effect — the writing ``materialize()`` clobbers tracked status during
    git operations (#1789, the dashboard half). This helper reduces the event
    log via the read-only ``materialize_snapshot`` and never writes.

    The dashboard shares WP07's single git-op detection source
    (``git_operation_in_progress``) rather than duplicating it (C-005): during
    an active git op this path is *guaranteed* write-free, so the helper short-
    circuits early with the same detection WP07's runtime writers consult. The
    snapshot returns the exact reduced view ``materialize()`` would have written
    (C-004 — rendered data is unchanged), only without the write.

    Returns the rounded percentage, or ``None`` when progress is unavailable.
    """
    from specify_cli.status import compute_weighted_progress
    from specify_cli.status import git_operation_in_progress
    from specify_cli.status import materialize_snapshot

    # Single-source git-op detection (C-005): the dashboard consumes WP07's
    # shared helper rather than re-implementing marker probing. Reads here are
    # always write-free (materialize_snapshot), so a git op never forces a
    # different code path; we surface it for observability and to make the
    # write-free-during-git-op contract explicit and testable (SC-6a).
    repo_root = _resolve_checkout_root(feature_dir)
    if repo_root is not None and git_operation_in_progress(repo_root):
        logger.debug(
            "Git operation in progress at '%s'; serving kanban for '%s' "
            "read-only (no tracked status write).",
            repo_root,
            feature_dir.name,
        )

    snapshot = materialize_snapshot(feature_dir)
    progress = compute_weighted_progress(snapshot)
    return round(progress.percentage, 1)


def _resolve_checkout_root(feature_dir: Path) -> Path | None:
    """Return the checkout root (the dir holding ``.git``) for ``feature_dir``.

    WP07's :func:`git_operation_in_progress` expects the checkout root (where
    ``.git`` lives, file or directory), then internally resolves both the
    per-worktree and shared common gitdirs. The dashboard receives a mission
    ``feature_dir`` (``<root>/kitty-specs/<slug>``), so we walk up to the
    nearest ancestor that owns a ``.git`` entry. Returns ``None`` when no
    enclosing checkout is found (conservative: callers then skip the probe).
    """
    for candidate in (feature_dir, *feature_dir.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _build_event_log_kanban_stats(feature_dir: Path, tasks_dir: Path) -> dict[str, Any]:
    """Count WP lanes: ``tasks_dir`` lists the WPs (planning surface),
    ``feature_dir`` holds the canonical event log (status surface, #2430)."""
    from specify_cli.status import CanonicalStatusNotFoundError
    from specify_cli.status import StoreError

    kanban_stats: dict[str, Any] = {"total": 0, "planned": 0, "doing": 0, "for_review": 0, "approved": 0, "done": 0}
    try:
        lane_counts = _count_wps_by_lane(tasks_dir, status_dir=feature_dir)
        for lane, count in lane_counts.items():
            kanban_stats[lane] = count
            kanban_stats["total"] += count

        try:
            weighted = read_only_weighted_percentage(feature_dir)
            if weighted is not None:
                kanban_stats["weighted_percentage"] = weighted
        except Exception:
            logger.debug(
                "Could not compute weighted progress for '%s'",
                feature_dir.name,
            )
    except CanonicalStatusNotFoundError:
        logger.warning(
            "No event log for feature '%s' — skipping kanban counts",
            feature_dir.name,
        )
        kanban_stats["error"] = f"Event log not found. Run: spec-kitty agent mission finalize-tasks --mission {feature_dir.name}"
    except StoreError as exc:
        logger.warning(
            "Unreadable event log for feature '%s' — dashboard counts unavailable: %s",
            feature_dir.name,
            exc,
        )
        kanban_stats["error"] = f"Event log unreadable. Run: spec-kitty upgrade (feature {feature_dir.name})"

    return kanban_stats


def _build_kanban_stats(
    planning_dir: Path,
    artifacts: dict[str, dict[str, Any]],
    status_dir: Path | None = None,
) -> dict[str, Any]:
    """Build kanban lane counts.

    ``planning_dir`` supplies the WP task files (planning surface);
    ``status_dir`` supplies the canonical event log — under coordination
    topology the two live on different surfaces (#2430). ``None`` keeps the
    single-surface behavior for legacy call sites.
    """
    kanban_stats: dict[str, Any] = {"total": 0, "planned": 0, "doing": 0, "for_review": 0, "approved": 0, "done": 0}
    if not artifacts["kanban"]:
        return kanban_stats

    tasks_dir = planning_dir / "tasks"
    if is_legacy_format(planning_dir):
        return _build_legacy_kanban_stats(tasks_dir)
    return _build_event_log_kanban_stats(status_dir or planning_dir, tasks_dir)


def scan_all_features(project_dir: Path) -> list[dict[str, Any]]:
    """Scan all features and return metadata."""
    features: list[dict[str, Any]] = []
    feature_paths = gather_feature_paths(project_dir)

    for feature_id, feature_dir in feature_paths.items():
        # Planning artifacts read primary-first (#2430); the scanned dir stays
        # the live-status surface (gather is coord-first by construction).
        planning_dir = _resolve_planning_dir_primary_first(project_dir, feature_dir)

        # A coord-topology mission's scanned (coord) dir holds only status
        # writes — its ``tasks/`` lives on the planning surface, so the
        # existence filter must consult that surface too or a live in-flight
        # mission with a post-083 (non-numeric) slug vanishes (#2430).
        if not (
            re.match(r"^\d+", feature_dir.name)
            or (planning_dir / "tasks").exists()
            or (feature_dir / "tasks").exists()
        ):
            continue

        meta_dir = planning_dir if (planning_dir / "meta.json").exists() else feature_dir
        friendly_name, meta_data = _read_dashboard_feature_meta(meta_dir)
        artifacts = get_feature_artifacts(planning_dir, project_dir)
        workflow = get_workflow_status(artifacts)
        kanban_stats = _build_kanban_stats(planning_dir, artifacts, status_dir=feature_dir)

        worktree = _resolve_feature_worktree_info(project_dir, feature_dir)
        display_name = format_feature_display_name(feature_id, friendly_name)

        features.append(
            {
                "id": feature_id,
                "name": friendly_name,
                "display_name": display_name,
                # Artifact viewers read planning content — point them at the
                # planning surface, not a status-only coord husk (#2430).
                "path": str(planning_dir.relative_to(project_dir)),
                "artifacts": artifacts,
                "workflow": workflow,
                "kanban_stats": kanban_stats,
                "mission_status": _derive_mission_status(kanban_stats, meta_data),
                "next_action": _derive_next_action(meta_data or {}, kanban_stats),
                "meta": meta_data or {},
                "worktree": worktree,
            }
        )

    features.sort(key=_feature_recency_sort_key, reverse=True)
    return features


def _canonical_wp_id(stem: str) -> str:
    """Uppercase canonical ``WP<n>`` id from a file stem (``WP04-slug`` -> ``WP04``)."""
    match = re.match(r"^(WP\d+)", stem, re.IGNORECASE)
    return match.group(1).upper() if match else stem


def _resolve_wp_title(content: str, wp_meta: Any, prompt_file: Path) -> str:
    """Presentation title -- a dashboard-CONSUMER concern the reconstruction reader
    deliberately does NOT produce: the ``# Work Package Prompt:`` header, else the
    frontmatter ``title``, else the file stem."""
    title_match = re.search(r"^#\s+Work Package Prompt:\s+(.+)$", content, re.MULTILINE)
    if title_match:
        return title_match.group(1)
    if wp_meta.title is not None:
        return str(wp_meta.title).strip()
    return prompt_file.stem


def _resolve_wp_lane_and_dir(
    prompt_file: Path,
    canonical_wp_id: str,
    default_lane: str,
    status_dir: Path | None,
) -> tuple[Any, Path]:
    """Resolve ``(lane, event_log_dir)``.

    ``lane`` stays event-sourced through ``reconstruct_wp_view``. ``event_log_dir`` is the
    surface that carries the live event log -- the status surface (coord worktree)
    when present, else the WP's feature dir (#2430) -- and is what the
    reconstruction reader reads resolved runtime state from. A legacy feature
    falls back to ``default_lane`` and the (log-less) feature dir; a non-legacy
    feature with no canonical log raises the finalize hint.
    """
    from specify_cli.status import (
        CanonicalStatusNotFoundError,
        has_event_log,
        reconstruct_wp_view,
    )

    candidate = prompt_file.parent.parent
    if status_dir is not None and has_event_log(status_dir):
        event_log_dir = status_dir
    elif has_event_log(candidate):
        event_log_dir = candidate
    elif has_event_log(candidate.parent):
        event_log_dir = candidate.parent
    else:
        event_log_dir = None
    if event_log_dir is not None:
        lane = reconstruct_wp_view(event_log_dir, canonical_wp_id).resolved.lane
        return lane or default_lane, event_log_dir
    feature_candidate = candidate if candidate.name != "tasks" else candidate.parent
    if is_legacy_format(feature_candidate):
        return default_lane, candidate
    raise CanonicalStatusNotFoundError(
        f"Canonical status not found for feature "
        f"'{feature_candidate.name}'. Run 'spec-kitty agent mission "
        f"finalize-tasks --mission {feature_candidate.name}' to "
        f"bootstrap the event log."
    )


def _wp_runtime_view(event_log_dir: Path, canonical_wp_id: str, wp_meta: Any) -> WPView:
    """Reconstruct the WP view through the ONE canonical reader (T044 / SC-007).

    ``metadata`` is threaded so the authored group is sourced from the (possibly
    planning-surface) prompt file already parsed here -- the reader does not
    re-read it -- while resolved runtime state comes from ``event_log_dir``.
    """
    from specify_cli.status import reconstruct_wp_view

    return reconstruct_wp_view(event_log_dir, canonical_wp_id, metadata=wp_meta)


def _wp_identity_fields(view: WPView) -> dict[str, str]:
    """Return separately labelled resolved-actual and authored identity fields.

    Empty resolved slots remain empty: authored recommendations never
    masquerade as runtime facts at the dashboard API boundary (INV-7).
    """
    resolved = view.resolved
    return {
        "agent": resolved.agent or "",
        "model": resolved.model or "",
        "agent_profile": resolved.agent_profile or "",
        "agent_profile_version": resolved.agent_profile_version or "",
        "role": resolved.role or "",
        "provider": resolved.provider or "",
        "assignee": resolved.assignee or "",
        "authored_model": view.authored.model or "",
        "authored_agent_profile": view.authored.agent_profile or "",
        "authored_role": view.authored.role or "",
    }


def _wp_subtask_progress(view: WPView) -> tuple[int, int]:
    """Return progress from the authored roster plus resolved completion state.

    Membership is static design intent from ``view.authored.subtasks``; status
    is the event-sourced ``view.resolved.subtasks`` mapping. Missing resolved
    entries are unfinished, so marking one item in a two-item roster reports
    ``1/2`` rather than the false-complete ``1/1``. No markdown checkbox state
    participates in either side of the calculation.
    """
    resolved_subtasks = view.resolved.subtasks
    done = sum(
        1
        for task_id in view.authored.subtasks
        if resolved_subtasks.get(task_id) == str(Lane.DONE)
    )
    return done, len(view.authored.subtasks)


def _process_wp_file(
    prompt_file: Path,
    project_dir: Path,
    default_lane: str,
    status_dir: Path | None = None,
) -> dict[str, Any] | None:
    """Process a single WP file and return task data or None on error.

    Runtime identity (agent/model/agent_profile/role/assignee + subtask progress)
    is reconstructed through the ONE canonical ``reconstruct_wp_view`` reader
    (T044/T045); the presentation fields (``title`` / ``prompt_markdown`` /
    ``prompt_path``) stay consumer-side -- the reader never produces them.
    """
    content, error = read_file_resilient(prompt_file, auto_fix=True)

    if content is None:
        logger.error(f"Failed to read {prompt_file.name}: {error}")
        return {
            "id": prompt_file.stem,
            "title": f"⚠️ Encoding Error: {prompt_file.name}",
            "lane": default_lane,
            "subtasks": [],
            "subtasks_done": 0,
            "subtasks_total": 0,
            "agent": "",
            "model": "",
            "assignee": "",
            "phase": "",
            "prompt_markdown": f"**Encoding Error**\n\n{error}",
            "prompt_path": str(prompt_file.relative_to(project_dir)) if prompt_file.is_relative_to(project_dir) else str(prompt_file),
            "encoding_error": True,
        }

    from specify_cli.status import read_wp_frontmatter

    try:
        wp_meta, prompt_body = read_wp_frontmatter(prompt_file)
    except Exception:
        return None

    canonical_wp_id = _canonical_wp_id(prompt_file.stem)
    lane, event_log_dir = _resolve_wp_lane_and_dir(prompt_file, canonical_wp_id, default_lane, status_dir)

    view = _wp_runtime_view(event_log_dir, canonical_wp_id, wp_meta)
    identity = _wp_identity_fields(view)
    subtasks_done, subtasks_total = _wp_subtask_progress(view)

    prompt_path = str(prompt_file.relative_to(project_dir)) if prompt_file.is_relative_to(project_dir) else str(prompt_file)
    return {
        "id": wp_meta.work_package_id,
        "title": _resolve_wp_title(content, wp_meta, prompt_file),
        "lane": lane,
        "subtasks": list(view.authored.subtasks),
        "subtasks_done": subtasks_done,
        "subtasks_total": subtasks_total,
        "agent": identity["agent"],
        "model": identity["model"],
        "agent_profile": identity["agent_profile"],
        "agent_profile_version": identity["agent_profile_version"],
        "role": identity["role"],
        "provider": identity["provider"],
        "assignee": identity["assignee"],
        "authored_model": identity["authored_model"],
        "authored_agent_profile": identity["authored_agent_profile"],
        "authored_role": identity["authored_role"],
        "phase": wp_meta.phase or "",
        "prompt_markdown": prompt_body.strip(),
        "prompt_path": prompt_path,
    }


def scan_feature_kanban(project_dir: Path, feature_id: str) -> dict[str, list[dict[str, Any]]]:
    """Scan kanban board for a specific feature.

    Supports both legacy (directory-based) and new (event-log-based) lane formats.
    """
    feature_dir = resolve_feature_dir(project_dir, feature_id)
    lanes: dict[str, list[dict[str, Any]]] = {
        "planned": [],
        "doing": [],
        "for_review": [],
        "approved": [],
        "done": [],
    }

    if feature_dir is None or not feature_dir.exists():
        return lanes

    # WP task files live on the planning surface, the live event log on the
    # status surface (the gather-resolved, coord-first ``feature_dir``) —
    # split the read per partition (#2430).
    planning_dir = _resolve_planning_dir_primary_first(project_dir, feature_dir)
    status_dir = feature_dir

    tasks_dir = planning_dir / "tasks"
    if not tasks_dir.exists():
        return lanes

    # Legacy detection uses the planning surface by design: legacy lane
    # directories are a planning artifact, and coord-topology missions are
    # never legacy (they always carry an event log).
    if is_legacy_format(planning_dir):
        # Pre-3.0 layout: the boundary guard blocks mutation commands from
        # reaching this path; the dashboard read-only scan annotates the feature
        # as legacy without iterating lane subdirectories.
        return lanes

    # New format: scan flat tasks/ directory, lane from event log
    from specify_cli.status import CanonicalStatusNotFoundError

    for prompt_file in tasks_dir.glob("WP*.md"):
        try:
            task_data = _process_wp_file(
                prompt_file,
                project_dir,
                "planned",
                status_dir=status_dir,
            )
            if task_data is not None:
                raw_lane = task_data.get("lane", "planned")
                state = wp_state_for(raw_lane)
                column = _KANBAN_COLUMN_FOR_LANE.get(state.lane, "planned")
                lanes[column].append(task_data)
        except CanonicalStatusNotFoundError:
            logger.warning(
                "No event log for feature '%s' — cannot render kanban",
                feature_dir.name,
            )
            return lanes  # Return empty kanban — feature not finalized
        except Exception as exc:
            logger.error(f"Unexpected error processing {prompt_file.name}: {exc}")
            continue

    # Sort all lanes
    for lane in lanes:
        lanes[lane].sort(key=work_package_sort_key)

    return lanes
