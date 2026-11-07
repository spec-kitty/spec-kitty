"""Exclude the Mission status files from existing lane worktrees (S6, FR-044).

Mission ``lane-worktree-model-hardening-01M6QY1M`` WP10. ADR 2026-07-29-1
Amendment 2026-11-06 (restated ruling 3, decision 01M6QY3XQJ5NAYVF3GMZ7ZPPRE):
a lane checkout never shows the Mission's ``status.events.jsonl`` /
``status.json``, a lane never changes them and a reader never reads them. The
one lane-checkout helper applies that exclusion to every NEW lane checkout;
this migration brings the lane worktrees that already exist in a clone in line,
through the same one exclusion authority
(:func:`specify_cli.lanes.lane_checkout.exclude_lane_status_files`).

Lane worktrees are enumerated from the git worktree registry (a registered
checkout on a Mission's code-lane branch), never from the ``.worktrees/`` path
shape. Per worktree the outcome is exactly one of:

* ``excluded`` -- a clean copy; the exclusion is applied and the files leave the disk;
* ``flagged_redundant`` -- a dirty copy whose every event id is already on the
  resolved status surface; the exclusion is applied and git keeps the modified
  file on disk (it never discards a local change);
* ``refused_lane_only_events`` -- a dirty copy holding event ids found nowhere
  else; the worktree is left untouched and the ids are reported (C-009: an
  event is never dropped);
* ``skipped_mid_operation`` -- a merge, rebase or cherry-pick is in progress;
* ``refused_sparse_cone`` -- the worktree is a cone-mode sparse checkout, which
  cannot hold the exclusion; it is left untouched (#7276);
* ``failed`` -- applying the exclusion raised; the lane is reported and the run
  is not recorded as a success, so it runs again (#7276);
* ``already_excluded`` -- the exclusion is in place (a re-run is a no-op, NFR-005);
* ``skipped_legacy_mission`` -- the Mission is genuinely legacy (no coordination
  branch, no stored topology, not flattened): it keeps writing status into its
  lane checkout and ``safe_commit`` cannot stage a sparse-excluded path, so the
  lane is left untouched and is not reported as lacking the exclusion.

A worktree that is already a non-cone sparse checkout keeps its own patterns;
the two status negations are merged into them (#7276).

A run that would leave a lane ``refused_lane_only_events`` or
``skipped_mid_operation`` is refused by ``can_apply()``: the runner reports it
as a skip, records nothing and selects the migration again on the next
upgrade, so it never settles while a lane still lacks the exclusion. The
``doctor sparse-checkout`` finding ``LANE_STATUS_NOT_EXCLUDED`` names every such
lane with its remedy (:func:`lane_checkouts_lacking_exclusion`).

The effect lives in each worktree's own git directory (the per-worktree sparse
configuration), outside version control, so the migration is clone-local and
its ``apply()`` is idempotent. Only git's own commands and ``pathlib`` paths are
used (NFR-008).
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult, MigrationStateUnreadableError

if TYPE_CHECKING:
    from specify_cli.lanes.lane_checkout import MissionCodeLane

__all__ = [
    "LaneCheckoutStatusExclusionMigration",
    "lane_checkouts_lacking_exclusion",
    "lane_exclusion_remedy",
]

MIGRATION_ID = "4.0.0rc8_lane_checkout_status_exclusion"
TARGET_VERSION = "4.0.0rc8"

_EVENTS_FILENAME = "status.events.jsonl"
_MID_OPERATION_MARKERS = ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply")


class LaneCheckoutOutcome(StrEnum):
    """What the migration did with one lane worktree (data-model §4)."""

    EXCLUDED = "excluded"
    FLAGGED_REDUNDANT = "flagged_redundant"
    REFUSED_LANE_ONLY_EVENTS = "refused_lane_only_events"
    SKIPPED_MID_OPERATION = "skipped_mid_operation"
    ALREADY_EXCLUDED = "already_excluded"
    REFUSED_SPARSE_CONE = "refused_sparse_cone"
    FAILED = "failed"
    SKIPPED_LEGACY_MISSION = "skipped_legacy_mission"


_CHANGING_OUTCOMES = frozenset({LaneCheckoutOutcome.EXCLUDED, LaneCheckoutOutcome.FLAGGED_REDUNDANT})
_NOTHING_TO_EXCLUDE_OUTCOMES = frozenset({LaneCheckoutOutcome.ALREADY_EXCLUDED, LaneCheckoutOutcome.SKIPPED_LEGACY_MISSION})
_UNMIGRATED_OUTCOMES = frozenset(
    {
        LaneCheckoutOutcome.REFUSED_LANE_ONLY_EVENTS,
        LaneCheckoutOutcome.SKIPPED_MID_OPERATION,
        LaneCheckoutOutcome.REFUSED_SPARSE_CONE,
        LaneCheckoutOutcome.FAILED,
    }
)


@dataclass(frozen=True)
class LaneCheckoutMigrationItem:
    """One lane worktree's outcome (data-model §4 ``LaneCheckoutMigrationItem``)."""

    worktree: Path
    lane_id: str
    outcome: LaneCheckoutOutcome
    event_ids_only_in_lane: tuple[str, ...] = ()
    reason: str = ""

    def render(self) -> str:
        line = f"{self.worktree} ({self.lane_id}): {self.outcome.value}"
        return f"{line} - {self.reason}" if self.reason else line


_UPGRADE_REMEDY = "then run `spec-kitty upgrade`"


def lane_exclusion_remedy(item: LaneCheckoutMigrationItem) -> str:
    """What the operator does so the lane worktree of *item* gets the exclusion."""
    if item.outcome == LaneCheckoutOutcome.REFUSED_LANE_ONLY_EVENTS:
        return (
            "record each transition the lane copy holds on the status surface (spec-kitty agent tasks move-task), "
            f"discard the lane copy's change to the Mission's status.events.jsonl and status.json "
            f"(git -C {item.worktree} checkout -- <file>), {_UPGRADE_REMEDY}"
        )
    if item.outcome == LaneCheckoutOutcome.SKIPPED_MID_OPERATION:
        return f"finish or abort the merge, rebase or cherry-pick in {item.worktree}, {_UPGRADE_REMEDY}"
    if item.outcome == LaneCheckoutOutcome.REFUSED_SPARSE_CONE:
        return f"switch {item.worktree} to a non-cone sparse checkout (git sparse-checkout set --no-cone ...) or disable it, {_UPGRADE_REMEDY}"
    if item.outcome == LaneCheckoutOutcome.FAILED:
        return f"fix the git error reported for {item.worktree}, {_UPGRADE_REMEDY}"
    return "run `spec-kitty doctor sparse-checkout --fix` (or `spec-kitty upgrade`)"


def lane_checkouts_lacking_exclusion(project_path: Path, *, fix: bool) -> tuple[LaneCheckoutMigrationItem, ...]:
    """Every registered lane worktree that lacks the status-file exclusion (after applying it where safe when *fix*).

    With *fix*, the exclusion is applied to every lane the migration would
    change (``excluded`` / ``flagged_redundant``) and only the lanes it may not
    touch are returned. Without, nothing is written and every lane not yet
    excluded is returned.

    Raises:
        MigrationStateUnreadableError: the worktree registry cannot be read.
    """
    items = migrate_lane_checkouts(project_path, dry_run=not fix)
    if fix:
        return tuple(item for item in items if item.outcome in _UNMIGRATED_OUTCOMES)
    return tuple(item for item in items if item.outcome not in _NOTHING_TO_EXCLUDE_OUTCOMES)


def migrate_lane_checkouts(project_path: Path, *, dry_run: bool) -> tuple[LaneCheckoutMigrationItem, ...]:
    """Decide (and, unless *dry_run*, apply) the outcome of every existing lane worktree.

    Raises:
        MigrationStateUnreadableError: the project is in a git repository whose
            worktree registry cannot be read (fail closed).
    """
    from specify_cli.lanes.lane_checkout import mission_code_lanes

    if not _inside_git_repository(project_path):
        return ()
    checkouts = _registered_lane_checkouts(project_path)
    items: list[LaneCheckoutMigrationItem] = []
    for lane in mission_code_lanes(project_path):
        worktree = checkouts.get(lane.branch)
        if worktree is None or not worktree.is_dir():
            continue
        items.append(_migrate_one(project_path, worktree, lane, dry_run=dry_run))
    return tuple(items)


def _registered_lane_checkouts(project_path: Path) -> dict[str, Path]:
    from specify_cli.coordination.surface_resolver import WorktreeRegistryUnavailable
    from specify_cli.lanes.lane_checkout import read_registered_checkouts

    try:
        registered = read_registered_checkouts(project_path)
    except WorktreeRegistryUnavailable as exc:
        raise MigrationStateUnreadableError(str(exc)) from exc
    lanes: dict[str, Path] = {}
    for checkout in registered:
        if checkout.is_main:
            continue
        branch = checkout.branch or _rebasing_branch(checkout.path)
        if branch is not None:
            lanes[branch] = checkout.path
    return lanes


def _rebasing_branch(worktree: Path) -> str | None:
    """The branch a detached checkout is rebasing (git records it as ``head-name``), or ``None``."""
    for state_dir in ("rebase-merge", "rebase-apply"):
        head_name = _git_path(worktree, f"{state_dir}/head-name")
        if head_name is not None and head_name.is_file():
            ref = head_name.read_text(encoding="utf-8").strip()
            return ref.removeprefix("refs/heads/") if ref.startswith("refs/heads/") else None
    return None


def _migrate_one(project_path: Path, worktree: Path, lane: MissionCodeLane, *, dry_run: bool) -> LaneCheckoutMigrationItem:
    lane_id, mission, mission_dir_name = lane.lane_id, lane.mission, lane.mission_dir_name
    if lane.legacy:
        reason = "a genuinely-legacy Mission writes its status into the lane checkout; worktree left untouched"
        return LaneCheckoutMigrationItem(worktree, lane_id, LaneCheckoutOutcome.SKIPPED_LEGACY_MISSION, reason=reason)
    if _already_excluded(worktree, mission_dir_name):
        return LaneCheckoutMigrationItem(worktree, lane_id, LaneCheckoutOutcome.ALREADY_EXCLUDED)
    if _mid_operation(worktree):
        return LaneCheckoutMigrationItem(worktree, lane_id, LaneCheckoutOutcome.SKIPPED_MID_OPERATION, reason="a merge, rebase or cherry-pick is in progress")
    if _cone_mode(worktree):
        reason = "a cone-mode sparse checkout cannot exclude the status files; worktree left untouched"
        return LaneCheckoutMigrationItem(worktree, lane_id, LaneCheckoutOutcome.REFUSED_SPARSE_CONE, reason=reason)
    item = _classify_copy(project_path, worktree, lane_id, mission, mission_dir_name)
    if item.outcome in _CHANGING_OUTCOMES and not dry_run:
        from specify_cli.lanes import lane_checkout

        try:
            lane_checkout.exclude_lane_status_files(worktree, mission_dir_name)
        except lane_checkout.LaneCheckoutError as exc:
            return LaneCheckoutMigrationItem(worktree, lane_id, LaneCheckoutOutcome.FAILED, reason=f"the exclusion could not be applied ({exc})")
    return item


def _cone_mode(worktree: Path) -> bool:
    return _config_true(worktree, "core.sparseCheckout") and _config_true(worktree, "core.sparseCheckoutCone")


def _config_true(worktree: Path, key: str) -> bool:
    return _git(worktree, "config", "--get", key).strip().lower() == "true"


def _classify_copy(project_path: Path, worktree: Path, lane_id: str, mission: str, mission_dir_name: str) -> LaneCheckoutMigrationItem:
    """``excluded`` / ``flagged_redundant`` / ``refused_lane_only_events`` for a worktree not yet excluded."""
    from specify_cli.missions._read_path_resolver import StatusReadPathNotFound

    status_paths = (f"kitty-specs/{mission_dir_name}/{_EVENTS_FILENAME}", f"kitty-specs/{mission_dir_name}/status.json")
    if not _dirty(worktree, status_paths):
        return LaneCheckoutMigrationItem(worktree, lane_id, LaneCheckoutOutcome.EXCLUDED)
    lane_keys = _event_keys(_read_text(worktree / status_paths[0]))
    try:
        surface_keys = set(_event_keys(_surface_text(project_path, mission)))
    except (StatusReadPathNotFound, OSError, RuntimeError, ValueError) as exc:
        return LaneCheckoutMigrationItem(
            worktree,
            lane_id,
            LaneCheckoutOutcome.REFUSED_LANE_ONLY_EVENTS,
            tuple(lane_keys),
            reason=f"the resolved status surface could not be read ({exc}); worktree left untouched",
        )
    only_in_lane = tuple(key for key in lane_keys if key not in surface_keys)
    if only_in_lane:
        return LaneCheckoutMigrationItem(
            worktree,
            lane_id,
            LaneCheckoutOutcome.REFUSED_LANE_ONLY_EVENTS,
            only_in_lane,
            reason=f"event ids found only in this lane copy: {', '.join(only_in_lane)}; worktree left untouched",
        )
    reason = "dirty copy; every event id is on the resolved status surface"
    return LaneCheckoutMigrationItem(worktree, lane_id, LaneCheckoutOutcome.FLAGGED_REDUNDANT, reason=reason)


def _already_excluded(worktree: Path, mission_dir_name: str) -> bool:
    from specify_cli.lanes.lane_checkout import status_exclusion_in_place

    if not _config_true(worktree, "core.sparseCheckout") or _config_true(worktree, "core.sparseCheckoutCone"):
        return False
    sparse_file = _git_path(worktree, "info/sparse-checkout")
    if sparse_file is None or not sparse_file.is_file():
        return False
    return status_exclusion_in_place(sparse_file.read_text(encoding="utf-8").splitlines(), mission_dir_name)


def _mid_operation(worktree: Path) -> bool:
    for marker in _MID_OPERATION_MARKERS:
        path = _git_path(worktree, marker)
        if path is not None and path.exists():
            return True
    return False


def _dirty(worktree: Path, status_paths: tuple[str, str]) -> bool:
    from kernel.git import GitCommandError, status_entries

    try:
        return bool(status_entries(worktree, pathspecs=status_paths, untracked="all"))
    except GitCommandError:
        return False  # an unreadable checkout reads clean, as the porcelain probe did


def _event_keys(text: str) -> list[str]:
    """Event ids in log order; a line with no readable id is keyed by its own bytes."""
    keys: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        key = _event_id(stripped) or f"unparsed line: {stripped}"
        if key not in keys:
            keys.append(key)
    return keys


def _event_id(line: str) -> str | None:
    try:
        row = json.loads(line)
    except ValueError:
        return None
    event_id = row.get("event_id") if isinstance(row, dict) else None
    return event_id if isinstance(event_id, str) and event_id else None


def _surface_text(project_path: Path, mission: str) -> str:
    """The resolved status surface's event log (WP05's door), from its path or its ref."""
    from specify_cli.coordination.status_service import read_status_ref
    from specify_cli.status import resolve_status_read

    surface = resolve_status_read(project_path, mission)
    if surface.path is not None:
        return _read_text(surface.path / _EVENTS_FILENAME)
    assert surface.ref is not None  # the surface invariant: exactly one of path and ref
    read = surface.prefetched or read_status_ref(surface.repo_root, surface.ref, f"kitty-specs/{surface.mission_dir_name}/{_EVENTS_FILENAME}")
    return "" if read.data is None else read.data.decode("utf-8", errors="replace")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def _inside_git_repository(directory: Path) -> bool:
    if not directory.is_dir():
        return False
    probe = subprocess.run(["git", "-C", str(directory), "rev-parse", "--git-common-dir"], capture_output=True, text=True, check=False)
    return probe.returncode == 0


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=False)
    return result.stdout if result.returncode == 0 else ""


def _git_path(worktree: Path, name: str) -> Path | None:
    raw = _git(worktree, "rev-parse", "--git-path", name).strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_absolute() else worktree / path


@MigrationRegistry.register
class LaneCheckoutStatusExclusionMigration(BaseMigration):
    """Apply the lane status-file exclusion to existing lane worktrees; report lane-only events."""

    migration_id = MIGRATION_ID
    description = "Exclude the Mission status files from existing lane worktrees; report event ids held only by a lane copy (FR-044)."
    target_version = TARGET_VERSION
    runs_on_worktrees = False
    clone_local_effect = True  # per-worktree sparse configuration in the git dir, outside version control

    def detect(self, project_path: Path) -> bool:
        """True when some existing lane worktree lacks the exclusion."""
        return bool(lane_checkouts_lacking_exclusion(project_path, fix=False))

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Refuse while any lane would be left unexcluded, so the run never settles the migration.

        The runner reports the refusal as a skip, records nothing and selects
        the migration again on the next upgrade: the upgrade does not fail, and
        no lane waits unreported (``doctor sparse-checkout`` names it too).
        """
        lacking = lane_checkouts_lacking_exclusion(project_path, fix=False)
        blocked = [item for item in lacking if item.outcome in _UNMIGRATED_OUTCOMES]
        if blocked:
            lanes = "; ".join(f"{item.render()}. Remedy: {lane_exclusion_remedy(item)}" for item in blocked)
            return False, f"{lanes}. No lane worktree is excluded until every one can be; this migration runs again on the next upgrade"
        if lacking:
            return True, ""
        return False, "every lane worktree already excludes the Mission status files (or there is none)"

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        items = migrate_lane_checkouts(project_path, dry_run=dry_run)
        prefix = "would apply" if dry_run else "applied"
        changes = [f"{prefix} lane status exclusion: {item.render()}" for item in items if item.outcome in _CHANGING_OUTCOMES]
        warnings = [f"lane worktree not migrated: {item.render()}" for item in items if item.outcome in _UNMIGRATED_OUTCOMES]
        # can_apply() already blocks every refusal it can foresee; a lane whose exclusion
        # failed while applying keeps the run from being recorded as a success (#7276).
        errors = [f"lane worktree exclusion failed: {item.render()}" for item in items if item.outcome == LaneCheckoutOutcome.FAILED]
        return MigrationResult(success=not errors, changes_made=changes, errors=errors, warnings=warnings)
