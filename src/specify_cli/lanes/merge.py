"""Lane-based merge operations.

Two-tier merge flow:
1. Lane → Mission: merge a lane branch into the mission integration branch.
2. Mission → Target: merge the mission branch into the target (e.g. main).

Both operations use temporary merge workspaces and the stale-lane
blocker to prevent overlapping file conflicts.

Strategy note (FR-006, FR-007):
- Lane→mission always uses merge commits (no-ff) regardless of strategy.
- Mission→target honors the ``strategy`` parameter (default: SQUASH).
"""

from __future__ import annotations

from mission_runtime import MissionArtifactKind, placement_seam
import os
import subprocess
import sys
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from specify_cli.coordination.coherence import is_toolchain_generated_churn
from specify_cli.git.ref_advance import advance_branch_ref
from specify_cli.lanes._git import branch_exists as _shared_branch_exists
from specify_cli.lanes.branch_naming import lane_branch_name, worktree_path as _worktree_path
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import read_lanes_json
from specify_cli.lanes.stale_check import StaleCheckResult, check_lane_staleness
from specify_cli.merge._constants import TARGET_BRANCH_CONTENT_CONFLICT
from specify_cli.merge.config import MergeStrategy


@dataclass(frozen=True)
class _MergeDriverSpec:
    """One custom git merge driver: config identity + ``.gitattributes`` mapping.

    ``config_key`` is the ``merge.<key>.*`` git-config namespace; ``pattern`` /
    ``target`` compose the ``<pattern> merge=<config_key>`` attributes line that
    routes matching paths to this driver (C-006).
    """

    config_key: str
    name: str
    command: str
    pattern: str

    @property
    def attributes_line(self) -> str:
        return f"{self.pattern} merge={self.config_key}"


# C-006: the canonical merge-driver registry. Every both-sides-divergent
# ``kitty-specs/**`` bookkeeping artifact that must reconcile (not clobber) under
# ``git merge --squash`` carries a driver here. Generalized from the
# single event-log driver (DIRECTIVE_044 — parametrized, not cloned).
_MERGE_DRIVERS: tuple[_MergeDriverSpec, ...] = (
    _MergeDriverSpec(
        config_key="spec-kitty-event-log",
        name="Spec Kitty event log union merge",
        command="spec-kitty merge-driver-event-log %O %A %B",
        pattern="kitty-specs/**/status.events.jsonl",
    ),
    # coord-write-placement-closure-01KYCF83 WP06 (out-of-owned-files leeway,
    # documented in the move-task note): decisions.events.jsonl
    # (events/decision_log.py's DecisionGitLog) is structurally identical to
    # status.events.jsonl -- an append-only JSONL log with an `event_id` +
    # `at` envelope (merge_event_payloads's only schema requirement) -- so it
    # reuses the SAME driver command/config, just a second pattern, rather
    # than a new dedicated driver. Surfaced by
    # test_merge_reconciliation_class_guard.py's completeness check once WP02
    # classified DECISION_LOG as a COORD-partition (both-sides-divergent) kind.
    _MergeDriverSpec(
        config_key="spec-kitty-event-log",
        name="Spec Kitty event log union merge",
        command="spec-kitty merge-driver-event-log %O %A %B",
        pattern="kitty-specs/**/decisions.events.jsonl",
    ),
    _MergeDriverSpec(
        config_key="spec-kitty-meta",
        name="Spec Kitty mission meta field merge",
        command="spec-kitty merge-driver-meta %O %A %B",
        pattern="kitty-specs/**/meta.json",
    ),
    _MergeDriverSpec(
        config_key="spec-kitty-traces",
        name="Spec Kitty mission traces union merge",
        command="spec-kitty merge-driver-traces %O %A %B",
        pattern="kitty-specs/**/traces/*.md",
    ),
    _MergeDriverSpec(
        config_key="spec-kitty-acceptance-matrix",
        name="Spec Kitty acceptance matrix filled-side merge",
        command="spec-kitty merge-driver-acceptance-matrix %O %A %B",
        pattern="kitty-specs/**/acceptance-matrix.json",
    ),
    _MergeDriverSpec(
        config_key="spec-kitty-issue-matrix",
        name="Spec Kitty issue matrix row-aware merge",
        command="spec-kitty merge-driver-issue-matrix %O %A %B",
        # WP11 (FR-008): repointed from issue-matrix.md -- WP05 migrated the
        # canonical artifact to structured JSON (C-008); no .md is written by
        # any canonical path any more, so the .md pattern would be inert.
        pattern="kitty-specs/**/issue-matrix.json",
    ),
    # review-cycle-verdict-seam-rebuild-01KZ2W7W WP18 (T017/T078): a
    # refuse-fail-closed driver, NOT a union/field-merge -- see
    # merge_driver.py::merge_driver_review_cycle's docstring for why this one
    # driver in the registry never reconciles a collision, only refuses it.
    # Filename-anchored pattern (never `tasks/*.md`) so genuinely
    # single-writer WP task files (`tasks/WP*.md`,
    # `tasks/<wp>/baseline-tests.json`) are unaffected.
    _MergeDriverSpec(
        config_key="spec-kitty-review-cycle",
        name="Spec Kitty review-cycle verdict collision refusal",
        command="spec-kitty merge-driver-review-cycle %O %A %B",
        pattern="kitty-specs/**/tasks/*/review-cycle-*.md",
    ),
)


@dataclass
class LaneMergeResult:
    """Outcome of a lane merge operation."""

    success: bool
    lane_id: str
    merged_into: str
    errors: list[str] = field(default_factory=list)
    stale_check: StaleCheckResult | None = None


@dataclass
class MissionMergeResult:
    """Outcome of a mission-to-target merge."""

    success: bool
    mission_branch: str
    target_branch: str
    commit: str | None = None
    already_applied: bool = False
    errors: list[str] = field(default_factory=list)
    # #4892: when the squash left unresolved content conflicts, carry the paths
    # and diagnostic code as STRUCTURED data — never fold them into ``errors``
    # prose alone. The executor's ``--resume`` "already merged" tolerance is a
    # substring match on ``errors``; a conflicting path such as
    # ``tests/test_already_applied.py`` would otherwise read as "already merged"
    # and let a real conflict slip through resume. Callers gate on this field,
    # not on the message text.
    conflicting_paths: tuple[str, ...] = ()
    diagnostic_code: str | None = None


@dataclass(frozen=True)
class MissionIntegrationPreview:
    """Read-only readiness result for mission-to-target branch integration."""

    conflicting_paths: tuple[str, ...] = ()


class _SquashMergeConflict(RuntimeError):
    """Normal squash integration left paths that no policy may auto-resolve."""

    def __init__(
        self,
        source_branch: str,
        target_branch: str,
        conflicting_paths: tuple[str, ...],
    ) -> None:
        self.conflicting_paths = conflicting_paths
        paths = ", ".join(conflicting_paths)
        super().__init__(f"Squash merge of {source_branch} into {target_branch} failed: unresolved content conflict(s): {paths}")


def _resolve_lane_manifest(
    repo_root: Path,
    mission_slug: str,
    lanes_manifest: LanesManifest | None,
) -> LanesManifest | None:
    """Return the provided manifest or load it from disk."""
    if lanes_manifest is not None:
        return lanes_manifest
    # FR-001 (#2185): ``lanes.json`` is LANE_STATE (PRIMARY-partition) — it lives
    # ONLY on the PRIMARY checkout post-#2106. The coord-aware resolver lands on
    # the STATUS-only ``-coord`` husk (no lanes.json), so route by kind.
    feature_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.LANE_STATE)
    return read_lanes_json(feature_dir)


def _try_auto_rebase_if_stale(
    stale: StaleCheckResult,
    lane: ExecutionLane,
    branch: str,
    mission_branch: str,
    mission_slug: str,
    repo_root: Path,
) -> StaleCheckResult:
    """If the lane is stale and a worktree exists, attempt auto-rebase and recheck."""
    if not stale.is_stale:
        return stale
    worktree_path = _worktree_path(repo_root, mission_slug, mission_id=None, lane_id=lane.lane_id)
    if not worktree_path.exists():
        return stale
    from specify_cli.lanes.auto_rebase import attempt_auto_rebase

    report = attempt_auto_rebase(lane, branch, mission_branch, repo_root, worktree_path)
    if report.succeeded:
        return check_lane_staleness(lane, branch, mission_branch, repo_root)
    return stale


def consolidate_lane_into_mission(
    repo_root: Path,
    mission_slug: str,
    lane_id: str,
    lanes_manifest: LanesManifest | None = None,
) -> LaneMergeResult:
    """Consolidate a lane branch into the mission integration branch.

    This is the *lane-consolidation* merge (one of a mission's several lane
    branches folded into the single mission branch) -- distinct from
    :func:`integrate_mission_into_target`, which performs the later
    *branch-integration* merge of the whole mission branch into the target
    (Primary) branch. Naming these two merge steps apart removes the
    overloaded bare "merge" ambiguity (FR-003/FR-008).

    Performs stale-lane check before merging. If the lane is stale
    (overlapping files changed in mission), the merge is blocked.

    Args:
        repo_root: Repository root.
        mission_slug: Feature slug.
        lane_id: Lane to merge (e.g., "lane-a").
        lanes_manifest: Pre-loaded manifest (loaded from disk if None).

    Returns:
        LaneMergeResult with success/error status.
    """
    lanes_manifest = _resolve_lane_manifest(repo_root, mission_slug, lanes_manifest)
    if lanes_manifest is None:
        return LaneMergeResult(
            success=False,
            lane_id=lane_id,
            merged_into="",
            errors=["No lanes.json found for this feature"],
        )

    lane = next(
        (c for c in lanes_manifest.lanes if c.lane_id == lane_id),
        None,
    )
    if lane is None:
        return LaneMergeResult(
            success=False,
            lane_id=lane_id,
            merged_into="",
            errors=[f"Lane {lane_id} not found in lanes.json"],
        )

    branch = lane_branch_name(
        mission_slug,
        lane_id,
        planning_base_branch=lanes_manifest.target_branch,
    )
    mission_branch = lanes_manifest.mission_branch

    if not _branch_exists(repo_root, branch):
        return LaneMergeResult(
            success=False,
            lane_id=lane_id,
            merged_into=mission_branch,
            errors=[f"Lane branch {branch} does not exist"],
        )

    stale = check_lane_staleness(lane, branch, mission_branch, repo_root)
    stale = _try_auto_rebase_if_stale(
        stale,
        lane,
        branch,
        mission_branch,
        mission_slug,
        repo_root,
    )
    if stale.is_stale:
        return LaneMergeResult(
            success=False,
            lane_id=lane_id,
            merged_into=mission_branch,
            errors=[f"Lane {lane_id} is stale: overlapping files {stale.stale_files}. {stale.remediation}"],
            stale_check=stale,
        )

    try:
        _merge_branch_into(repo_root, branch, mission_branch)
    except RuntimeError as e:
        return LaneMergeResult(
            success=False,
            lane_id=lane_id,
            merged_into=mission_branch,
            errors=[str(e)],
        )

    return LaneMergeResult(
        success=True,
        lane_id=lane_id,
        merged_into=mission_branch,
    )


def integrate_mission_into_target(
    repo_root: Path,
    mission_slug: str,
    lanes_manifest: LanesManifest | None = None,
    *,
    strategy: MergeStrategy = MergeStrategy.SQUASH,
    allow_already_applied: bool = False,
) -> MissionMergeResult:
    """Integrate the mission branch into the target (Primary) branch.

    This is the *branch-integration* merge -- the final step of a mission,
    folding the single mission integration branch into the repository's
    target/Primary branch (e.g. ``main``). It is distinct from
    :func:`consolidate_lane_into_mission`, the earlier *lane-consolidation*
    merge that folds individual lane branches into the mission branch; keeping
    the two named apart removes the overloaded bare "merge" ambiguity
    (FR-003/FR-008).

    Only the mission branch may integrate into the target branch.

    Args:
        repo_root: Repository root.
        mission_slug: Feature slug.
        lanes_manifest: Pre-loaded manifest (loaded from disk if None).
        strategy: Merge strategy for the mission→target step (FR-006/T010).
            Defaults to SQUASH. Lane→mission is NOT affected by this parameter.

    Returns:
        MissionMergeResult with success/error status.
    """
    if lanes_manifest is None:
        # FR-001 (#2185): LANE_STATE read — PRIMARY-partition (see above).
        feature_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.LANE_STATE)
        lanes_manifest = read_lanes_json(feature_dir)
        if lanes_manifest is None:
            return MissionMergeResult(
                success=False,
                mission_branch="",
                target_branch="",
                errors=["No lanes.json found for this feature"],
            )

    mission_branch = lanes_manifest.mission_branch
    target_branch = lanes_manifest.target_branch

    if not _branch_exists(repo_root, mission_branch):
        return MissionMergeResult(
            success=False,
            mission_branch=mission_branch,
            target_branch=target_branch,
            errors=[f"Mission branch {mission_branch} does not exist"],
        )

    try:
        # T010: honor strategy for mission→target only; lane→mission is not touched
        changed = _merge_branch_into(
            repo_root,
            mission_branch,
            target_branch,
            strategy=strategy,
            allow_noop_squash=allow_already_applied,
        )
    except _SquashMergeConflict as exc:
        # #4892: a genuine target-content conflict. Surface the paths as
        # structured data (never only as ``errors`` prose) and tag the shared
        # diagnostic code so the real merge reports exactly what ``--dry-run``
        # reports — and so the resume tolerance can never mistake it for
        # "already merged".
        return MissionMergeResult(
            success=False,
            mission_branch=mission_branch,
            target_branch=target_branch,
            errors=[str(exc)],
            conflicting_paths=exc.conflicting_paths,
            diagnostic_code=TARGET_BRANCH_CONTENT_CONFLICT,
        )
    except RuntimeError as e:
        return MissionMergeResult(
            success=False,
            mission_branch=mission_branch,
            target_branch=target_branch,
            errors=[str(e)],
        )

    # Get the merge commit.
    commit = _rev_parse(repo_root, target_branch) if changed else None

    return MissionMergeResult(
        success=True,
        mission_branch=mission_branch,
        target_branch=target_branch,
        commit=commit,
        already_applied=not changed,
    )


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _branch_exists(repo_root: Path, branch: str) -> bool:
    # Routes the existence check through the shared lanes/_git helper while
    # preserving the merge pipeline's single env authority (_make_merge_env);
    # the env composes through rather than forking the helper (#1904).
    return bool(_shared_branch_exists(repo_root, branch, env=_make_merge_env()))


def _git_config_get(repo_root: Path, key: str) -> str | None:
    """Return a local git config value or ``None`` when unset/unreadable."""
    result = subprocess.run(
        ["git", "config", "--local", "--get", key],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env=_make_merge_env(),
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _git_common_dir(repo_root: Path) -> Path | None:
    """Return the repository's shared git common dir (worktree-safe)."""
    result = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env=_make_merge_env(),
    )
    if result.returncode != 0:
        return None
    raw = Path(result.stdout.strip())
    return raw if raw.is_absolute() else (repo_root / raw)


def _set_local_git_config(repo_root: Path, key: str, value: str) -> None:
    """Set a local git-config *key* to *value* when it is not already current."""
    if _git_config_get(repo_root, key) == value:
        return
    subprocess.run(
        ["git", "config", "--local", key, value],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
        env=_make_merge_env(),
    )


def _ensure_info_attributes(repo_root: Path) -> list[str]:
    """Map the driver patterns in the shared ``.git/info/attributes``.

    The ephemeral merge worktree (``_merge_branch_into``) checks out the target
    branch tip, which need not carry a committed ``.gitattributes`` (fresh repos,
    test fixtures). ``$GIT_COMMON_DIR/info/attributes`` applies to every linked
    worktree, so seeding the driver patterns there makes the custom drivers fire
    under ``git merge --squash`` regardless of what a branch committed.
    Additive and idempotent: operator lines are preserved; missing lines appended.

    Returns the attribute lines it newly appended (``[]`` when everything was
    already present), so the caller can tear down *exactly* its own seeding —
    see :func:`_remove_info_attributes` / :func:`_ephemeral_merge_driver_activation`.
    """
    common_dir = _git_common_dir(repo_root)
    if common_dir is None:
        return []
    info_dir = common_dir / "info"
    attributes_path = info_dir / "attributes"
    existing = attributes_path.read_text(encoding="utf-8").splitlines() if attributes_path.exists() else []
    missing = [spec.attributes_line for spec in _MERGE_DRIVERS if spec.attributes_line not in existing]
    if not missing:
        return []
    info_dir.mkdir(parents=True, exist_ok=True)
    attributes_path.write_text("\n".join([*existing, *missing]).rstrip("\n") + "\n", encoding="utf-8")
    return missing


def _remove_info_attributes(repo_root: Path, added_lines: list[str]) -> None:
    """Tear down the driver attribute lines :func:`_ensure_info_attributes` seeded.

    Removes *only* ``added_lines`` from ``$GIT_COMMON_DIR/info/attributes``,
    leaving any pre-existing operator lines untouched. If the file is left empty
    (we seeded it into an otherwise-absent file), it is unlinked so the repo is
    restored to its prior state. Idempotent: an empty ``added_lines`` or a
    missing file is a no-op.

    This is the load-bearing half of the #2709/#2711 split: the git-config driver
    *definitions* persist (intended, inert without an attribute mapping), but the
    ``info/attributes`` *activation* is repo-global across worktrees and MUST NOT
    outlive the ephemeral squash merge — otherwise a later ``auto_rebase`` in the
    same repo finds the git driver pre-activated and resolves
    ``status.events.jsonl`` via ``spec-kitty merge-driver-event-log`` on PATH
    before its in-process ``R-STATUS-EVENTS-JSONL-UNION`` classifier can run.
    """
    if not added_lines:
        return
    common_dir = _git_common_dir(repo_root)
    if common_dir is None:
        return
    attributes_path = common_dir / "info" / "attributes"
    if not attributes_path.exists():
        return
    remaining = [line for line in attributes_path.read_text(encoding="utf-8").splitlines() if line not in added_lines]
    if remaining:
        attributes_path.write_text("\n".join(remaining).rstrip("\n") + "\n", encoding="utf-8")
    else:
        attributes_path.unlink()


def _ensure_merge_driver_git_config(repo_root: Path) -> None:
    """Ensure every custom merge driver's git-*config* is present (no attributes).

    Sets the ``merge.<key>.name`` / ``merge.<key>.driver`` git-config for the
    whole :data:`_MERGE_DRIVERS` registry (event-log union, ``meta.json`` field
    merge, ``traces/*.md`` union) so the drivers are *defined*. ``spec-kitty
    init`` calls this directly (#4146), so a fresh init inside an existing git
    repository gets both halves of the driver wiring; when the project is not
    a git repository yet at init time, this helper's own ``.git`` guard makes
    it a no-op and the merge path self-heals that gap later (C-006 /
    DIRECTIVE_044).

    It deliberately does **not** seed ``.git/info/attributes``: defining a driver
    is inert until an attribute maps a path to it. This is the entry point the
    stale-lane auto-rebase pipeline uses. Auto-rebase owns its own in-process
    event-log union classifier (``R-STATUS-EVENTS-JSONL-UNION``) as the fallback
    for repos that have not committed a ``.gitattributes`` mapping; pre-seeding
    ``.git/info/attributes`` here would pre-activate the git driver and silently
    pre-empt that fallback (the #2709/#2711 regression), coupling auto-rebase to
    the external ``spec-kitty merge-driver-*`` subcommands being on PATH.
    """
    if not (repo_root / ".git").exists():
        return

    for spec in _MERGE_DRIVERS:
        _set_local_git_config(repo_root, f"merge.{spec.config_key}.name", spec.name)
        _set_local_git_config(repo_root, f"merge.{spec.config_key}.driver", spec.command)


def _merge_driver_config_snapshot(repo_root: Path) -> dict[str, str | None]:
    """Capture the config keys self-healed by merge-driver activation."""
    keys = {
        key
        for spec in _MERGE_DRIVERS
        for key in (
            f"merge.{spec.config_key}.name",
            f"merge.{spec.config_key}.driver",
        )
    }
    return {key: _git_config_get(repo_root, key) for key in keys}


def _restore_merge_driver_config(
    repo_root: Path,
    snapshot: dict[str, str | None],
) -> None:
    """Restore merge-driver config after a read-only preview."""
    for key, value in snapshot.items():
        if value is not None:
            _set_local_git_config(repo_root, key, value)
            continue
        subprocess.run(
            ["git", "config", "--local", "--unset-all", key],
            cwd=str(repo_root),
            capture_output=True,
            env=_make_merge_env(),
        )


@contextmanager
def _ephemeral_merge_driver_activation(
    repo_root: Path,
    *,
    restore_config: bool = False,
) -> Iterator[None]:
    """Activate the custom drivers for ONE ephemeral merge, then tear the seeding down.

    Used by the squash mission→target merge (``_merge_branch_into``): its
    ephemeral merge worktree checks out the target-branch tip, which need not
    carry a committed ``.gitattributes`` (fresh repos, test fixtures), so the
    driver patterns must be seeded into ``$GIT_COMMON_DIR/info/attributes`` for
    the custom drivers to fire under ``git merge --squash`` (C-006 /
    DIRECTIVE_044).

    Seeding happens *before* the merge (so the drivers fire during it) and is
    torn down *after* (so it does not persist). Only the ``info/attributes``
    activation is ephemeral — the git-config driver *definitions*
    (:func:`_ensure_merge_driver_git_config`) and the committed ``.gitattributes``
    remain, since they are the intended persistent surface and are inert without
    an active attribute mapping. Distinct from :func:`_ensure_merge_driver_git_config`,
    which only *defines* the drivers without activating them — see that docstring
    for why auto-rebase must not seed attributes, and :func:`_remove_info_attributes`
    for why leaving this seeding in place re-couples auto-rebase to the external
    ``spec-kitty merge-driver-*`` subcommands (the #2709/#2711 regression).
    """
    if not (repo_root / ".git").exists():
        yield
        return

    config_snapshot = _merge_driver_config_snapshot(repo_root) if restore_config else None
    added: list[str] = []
    try:
        _ensure_merge_driver_git_config(repo_root)
        added = _ensure_info_attributes(repo_root)
        yield
    finally:
        _remove_info_attributes(repo_root, added)
        if config_snapshot is not None:
            _restore_merge_driver_config(repo_root, config_snapshot)


def _make_merge_env() -> dict[str, str]:
    """Single environment authority for the lane-merge pipeline (AC-F1).

    Prepends the current venv's bin directory to PATH so that git's merge
    driver invocation of ``spec-kitty merge-driver-event-log`` resolves to the
    same spec-kitty binary that is currently running, not a stale global one.

    Every subprocess invocation in this module routes its ``env`` through
    this helper — no inline ``os.environ`` copies with ad-hoc PATH/GIT_*
    mutations (FR-008b; ratchet in
    ``tests/architectural/test_merge_pipeline_ratchets.py``).
    """
    venv_bin = str(Path(sys.executable).parent)
    env = os.environ.copy()
    env["PATH"] = venv_bin + os.pathsep + env.get("PATH", "")
    return env


def _rev_parse(repo_root: Path, ref: str) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", ref],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env=_make_merge_env(),
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _blob_at(repo_root: Path, ref: str, rel: str, env: dict[str, str]) -> bytes | None:
    """Return the bytes of ``rel`` at ``ref``, or None when the path is absent there."""
    result = subprocess.run(
        ["git", "show", f"{ref}:{rel}"],
        cwd=str(repo_root),
        capture_output=True,
        env=env,
    )
    return result.stdout if result.returncode == 0 else None


def _three_way_merge_favouring_target(
    repo_root: Path,
    merge_base: str,
    target_branch: str,
    source_branch: str,
    rel: str,
    env: dict[str, str],
) -> bytes | None:
    """3-way merge base/target/lane for ``rel``, resolving conflicts toward TARGET.

    Returns the merged bytes, or None when the target has no blob for ``rel`` (a
    delete — leave the squash result untouched). Uses ``git merge-file --ours`` so
    the lane's *disjoint* edits are unioned in losslessly and only genuinely
    *overlapping* hunks resolve to the target copy. This is the #3942 fix done
    without the data loss a wholesale target-blob overwrite would cause in the
    both-sides-advanced case (a lane edit to a different section must survive).

    Caveat — no common ancestor: when ``rel`` is add/add (absent at the merge-base
    and independently created on both sides), there is no base to anchor a disjoint
    union, so ``merge-file`` treats the whole file as one conflicting region and the
    target wins wholesale (favour-target policy). This is deliberately confined
    to paths selected by the PRIMARY planning-artifact authority.
    """
    import tempfile

    target_blob = _blob_at(repo_root, target_branch, rel, env)
    if target_blob is None:
        return None
    lane_blob = _blob_at(repo_root, source_branch, rel, env)
    if lane_blob is None:
        # Lane never had / deleted the path — no lane edits to union; target stands.
        return target_blob
    base_blob = _blob_at(repo_root, merge_base, rel, env) or b""
    with tempfile.TemporaryDirectory(prefix="kitty-3way-") as td:
        tp = Path(td) / "target"
        bp = Path(td) / "base"
        lp = Path(td) / "lane"
        tp.write_bytes(target_blob)
        bp.write_bytes(base_blob)
        lp.write_bytes(lane_blob)
        # --ours resolves every conflicting hunk toward `tp` (target) and still
        # applies lane's non-conflicting hunks; the merge is written into `tp`.
        # Return code is intentionally ignored: for a text merge it is the
        # (auto-resolved) conflict count, and for a binary blob it is 255 with the
        # target copy left in place — a fail-safe toward target, never corruption.
        # All eligible kinds are text (markdown) planning artifacts.
        subprocess.run(
            ["git", "merge-file", "-q", "--ours", str(tp), str(bp), str(lp)],
            cwd=str(repo_root),
            capture_output=True,
            env=env,
        )
        return tp.read_bytes()


def _preserve_target_newer_planning_artifacts(
    repo_root: Path,
    worktree: Path,
    source_branch: str,
    target_branch: str,
    env: dict[str, str],
) -> list[str]:
    """Restore target-newer PRIMARY-partition planning files into the squash commit (#3942).

    PRIMARY-partition planning artifacts (``spec.md`` / ``tasks/WP*.md`` and the
    rest of the partition) are authored on the primary/target surface and can
    legitimately carry a *newer* target copy than the mission branch. A merge
    driver cannot detect that — it sees only three blobs, no history — so the
    pure three-way rule in
    :func:`planning_recency.target_newer_primary_artifacts` names the paths the
    target owns. Each is re-resolved by a base/target/lane 3-way merge that
    favours the target on *overlapping* conflicts while preserving the lane's
    *disjoint* edits (never a wholesale target overwrite — that would drop a lane
    edit to a different section), and the squash commit is amended so the
    reconciled content lands in the SINGLE merge commit ``advance_branch_ref``
    fast-forwards to. Only paths whose reconciled content actually differs from
    the squash result are rewritten. Returns those repo-relative paths (operator
    report / FR-002).
    """
    from specify_cli.merge.planning_recency import target_newer_primary_artifacts

    target_newer = target_newer_primary_artifacts(repo_root, target_branch, source_branch)
    if not target_newer:
        return []
    merge_base = subprocess.run(
        ["git", "merge-base", target_branch, source_branch],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env=env,
    )
    if merge_base.returncode != 0 or not merge_base.stdout.strip():
        return []
    merge_base_ref = merge_base.stdout.strip()
    restored: list[str] = []
    for rel in target_newer:
        rel_str = str(rel)
        reconciled = _three_way_merge_favouring_target(repo_root, merge_base_ref, target_branch, source_branch, rel_str, env)
        if reconciled is None:
            # Target deleted (or cannot read) the path — leave the squash result
            # untouched; the #3942 clobber is a content modify, not a delete.
            continue
        dest = worktree / rel_str
        # Rewrite only when the 3-way result actually differs from the squash
        # result: when git already merged losslessly there is nothing to preserve.
        current = dest.read_bytes() if dest.exists() else None
        if current == reconciled:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(reconciled)
        add = subprocess.run(
            ["git", "add", "--", rel_str],
            cwd=str(worktree),
            capture_output=True,
            text=True,
            env=env,
        )
        if add.returncode != 0:
            raise RuntimeError(f"Failed to stage restored planning artifact {rel_str}: {add.stderr.strip()}")
        restored.append(rel_str)
    if restored:
        # ``--allow-empty``: when the mission's ONLY diffs were the older
        # planning copies we just restored to the target's version, the amended
        # tree equals the parent (target tip) — there is genuinely nothing to
        # integrate, but we keep the (empty) squash commit as the merge record
        # so the ref-advance + downstream bookkeeping stay uniform.
        amend = subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "commit", "--amend", "--no-edit", "--allow-empty"],
            cwd=str(worktree),
            capture_output=True,
            text=True,
            env=env,
        )
        if amend.returncode != 0:
            raise RuntimeError(f"Failed to amend squash commit with preserved planning artifacts: {amend.stderr.strip() or amend.stdout.strip()}")
        # FR-002 divergence report: surface the preservation to the operator
        # (never silent) — the target carried a newer copy than the mission
        # branch for these PRIMARY-partition planning artifacts (#3942).
        print(
            f"Notice (#3942): preserved target-newer planning artifact(s) the squash would otherwise have clobbered: {', '.join(restored)}",
            file=sys.stderr,
        )
    return restored


def _unmerged_paths(
    worktree: Path,
    env: dict[str, str],
) -> tuple[str, ...]:
    """Return deterministic repo-relative paths still unresolved in the index."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=U", "-z"],
        cwd=str(worktree),
        capture_output=True,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Could not inspect squash merge conflicts: {result.stderr.decode(errors='replace').strip()}")
    return tuple(sorted(os.fsdecode(raw_path) for raw_path in result.stdout.split(b"\0") if raw_path))


def _resolve_planning_conflicts(
    repo_root: Path,
    worktree: Path,
    source_branch: str,
    target_branch: str,
    conflicting_paths: tuple[str, ...],
    env: dict[str, str],
) -> None:
    """Resolve only conflicts owned by the existing PRIMARY planning policy."""
    from specify_cli.merge.planning_recency import target_newer_primary_artifacts

    target_wins = target_newer_primary_artifacts(
        repo_root,
        target_branch,
        source_branch,
        changed_paths=conflicting_paths,
    )
    target_paths = {str(path) for path in target_wins}
    source_wins = target_newer_primary_artifacts(
        repo_root,
        source_branch,
        target_branch,
        changed_paths=(path for path in conflicting_paths if path not in target_paths),
    )
    resolutions = [(path, target_branch, source_branch) for path in target_wins] + [(path, source_branch, target_branch) for path in source_wins]
    if not resolutions:
        return
    merge_base = subprocess.run(
        ["git", "merge-base", target_branch, source_branch],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env=env,
    )
    if merge_base.returncode != 0 or not merge_base.stdout.strip():
        return
    merge_base_ref = merge_base.stdout.strip()
    for path, preferred_branch, other_branch in resolutions:
        rel = str(path)
        reconciled = _three_way_merge_favouring_target(
            repo_root,
            merge_base_ref,
            preferred_branch,
            other_branch,
            rel,
            env,
        )
        if reconciled is None:
            # Preserve the historical #3942 scope: content reconciliation only.
            # A delete/modify ambiguity remains an explicit blocker.
            continue
        destination = worktree / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(reconciled)
        staged = subprocess.run(
            ["git", "add", "--", rel],
            cwd=str(worktree),
            capture_output=True,
            text=True,
            env=env,
        )
        if staged.returncode != 0:
            raise RuntimeError(f"Failed to stage reconciled planning artifact {rel}: {staged.stderr.strip()}")


def _run_squash_merge(
    repo_root: Path,
    worktree: Path,
    source_branch: str,
    target_branch: str,
    env: dict[str, str],
) -> bool:
    """Stage a squash merge; return whether planning reconciliation was needed."""
    result = subprocess.run(
        ["git", "merge", "--squash", source_branch],
        cwd=str(worktree),
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode == 0:
        return False

    conflicts = _unmerged_paths(worktree, env)
    if conflicts:
        _resolve_planning_conflicts(
            repo_root,
            worktree,
            source_branch,
            target_branch,
            conflicts,
            env,
        )
        conflicts = _unmerged_paths(worktree, env)
        if conflicts:
            raise _SquashMergeConflict(
                source_branch,
                target_branch,
                conflicts,
            )
        return True

    # A non-zero merge with no unresolved index paths is an operational error
    # (for example, a failed hook/driver), not a successful simulation.
    diagnostic = result.stderr.strip() or result.stdout.strip()
    raise RuntimeError(f"Squash merge of {source_branch} into {target_branch} failed: {diagnostic}")


def preview_mission_target_integration(
    repo_root: Path,
    source_branch: str,
    target_branch: str,
    *,
    strategy: MergeStrategy,
) -> MissionIntegrationPreview:
    """Simulate squash branch integration without committing or advancing refs.

    Scope: this previews ``source_branch`` (the current mission-branch tip)
    against ``target_branch``. It does NOT first consolidate the lane branches
    the way the real merge does (``_phase_merge_lanes``), so a conflict that
    lives only in an un-consolidated lane commit is invisible here — the real
    merge still fails closed on it. The forecast is a readiness signal, not a
    completeness guarantee.

    Missing refs retain the historical dry-run behavior: other preflights may
    still preview lifecycle/retention state before implementation has created a
    local mission branch.
    """
    if strategy != MergeStrategy.SQUASH or not _branch_exists(repo_root, source_branch) or not _branch_exists(repo_root, target_branch):
        return MissionIntegrationPreview()

    import tempfile

    tmp_path = Path(tempfile.mkdtemp(prefix="kitty-merge-preview-"))
    env = _make_merge_env()
    with ExitStack() as stack:
        stack.enter_context(_ephemeral_merge_driver_activation(repo_root, restore_config=True))
        stack.callback(
            lambda: subprocess.run(
                ["git", "worktree", "remove", str(tmp_path), "--force"],
                cwd=str(repo_root),
                capture_output=True,
                env=env,
            )
        )
        created = subprocess.run(
            ["git", "worktree", "add", "--detach", str(tmp_path), target_branch],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            env=env,
        )
        if created.returncode != 0:
            raise RuntimeError(f"Failed to create merge preview worktree: {created.stderr.strip()}")
        try:
            _run_squash_merge(
                repo_root,
                tmp_path,
                source_branch,
                target_branch,
                env,
            )
        except _SquashMergeConflict as exc:
            return MissionIntegrationPreview(exc.conflicting_paths)
    return MissionIntegrationPreview()


def _merge_branch_into(
    repo_root: Path,
    source_branch: str,
    target_branch: str,
    *,
    strategy: MergeStrategy = MergeStrategy.MERGE,
    allow_noop_squash: bool = False,
) -> bool:
    """Merge source_branch into target_branch using a temporary worktree.

    Creates a detached worktree at the target branch tip, merges source
    into it using the specified strategy, then fast-forwards the target branch
    ref to the result. The main repo's checkout is never changed.

    Uses --detach to avoid "branch already checked out" errors when
    target_branch is the currently checked-out branch.

    Strategy behavior:
    - MERGE (default for lane→mission): ``git merge --no-ff``  — preserves structure
    - SQUASH: ``git merge --squash`` + explicit commit
    - REBASE: ``git rebase`` then fast-forward

    Raises RuntimeError on merge failure (including conflicts).
    """
    import tempfile

    tmp_dir = tempfile.mkdtemp(prefix="kitty-merge-")
    tmp_path = Path(tmp_dir)

    # Single environment authority for the lane-merge pipeline (AC-F1).
    _env = _make_merge_env()

    # Seed the custom-driver ``info/attributes`` activation for the duration of
    # this ephemeral merge only, and remove the merge worktree on exit. The
    # activation is torn down when the ``with`` block closes (LIFO: worktree
    # removed first, then ``info/attributes`` restored) so it never persists into
    # a later ``auto_rebase`` (#2709/#2711 — see _ephemeral_merge_driver_activation).
    with ExitStack() as _stack:
        _stack.enter_context(_ephemeral_merge_driver_activation(repo_root))
        _stack.callback(
            lambda: subprocess.run(
                ["git", "worktree", "remove", str(tmp_path), "--force"],
                cwd=str(repo_root),
                capture_output=True,
                env=_env,
            )
        )

        # Create detached worktree at target branch tip.
        result = subprocess.run(
            ["git", "worktree", "add", "--detach", str(tmp_path), target_branch],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            env=_env,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to create merge worktree: {result.stderr.strip()}")

        if strategy == MergeStrategy.SQUASH:
            # #4892: ordinary source conflicts must remain visible. Registered
            # artifact drivers and the history-aware planning policy are the
            # only allowed auto-resolution authorities.
            try:
                planning_conflict_resolved = _run_squash_merge(
                    repo_root,
                    tmp_path,
                    source_branch,
                    target_branch,
                    _env,
                )
            except RuntimeError:
                subprocess.run(
                    ["git", "merge", "--abort"],
                    cwd=str(tmp_path),
                    capture_output=True,
                    env=_env,
                )
                raise
            # Squash merges do not record ancestry. On retry after a previous
            # successful squash, Git reports a clean index and a plain commit
            # would fail in this detached worktree with "Not currently on any
            # branch." Only explicit resume callers may treat that as
            # idempotent success; ordinary callers need a real merge result.
            staged = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=str(tmp_path),
                capture_output=True,
                text=True,
                env=_env,
            )
            if staged.returncode == 0:
                # Nothing staged. #4892 review: when a planning conflict resolves
                # entirely to the target copy, the target already contains the
                # mission's tree — a genuine no-op. NEVER force it through with an
                # ``--allow-empty`` commit (that fabricated an empty squash commit
                # and bypassed the FR-037 no-op check). Report the no-op so the
                # executor's zero-diff guard can adjudicate it.
                if planning_conflict_resolved or allow_noop_squash:
                    return False
                raise RuntimeError(
                    f"Squash merge of {source_branch} into {target_branch} "
                    "produced no changes; target may already contain this tree. "
                    "Retry with merge resume if recovering an interrupted merge."
                )
            if staged.returncode not in (0, 1):
                raise RuntimeError(f"Could not inspect squash merge result for {source_branch} into {target_branch}: {staged.stderr.strip()}")
            # Commit the squashed result. There is guaranteed staged content here
            # (returncode == 1), so no ``--allow-empty`` is ever needed.
            result = subprocess.run(
                [
                    "git",
                    "-c",
                    "commit.gpgsign=false",
                    "commit",
                    "-m",
                    f"feat({source_branch}): squash merge of mission",
                ],
                cwd=str(tmp_path),
                capture_output=True,
                text=True,
                env=_env,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Squash commit into {target_branch} failed: {result.stderr.strip() or result.stdout.strip()}")
        elif strategy == MergeStrategy.REBASE:
            # Rebase source onto target in the isolated worktree, then
            # fast-forward target to the rebased detached HEAD. Do not check
            # out or rewrite source_branch in the user's main checkout.
            result = subprocess.run(
                ["git", "checkout", "--detach", source_branch],
                cwd=str(tmp_path),
                capture_output=True,
                text=True,
                env=_env,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Failed to check out {source_branch} in merge worktree: {result.stderr.strip() or result.stdout.strip()}")
            # Rebase source on top of target.
            result = subprocess.run(
                ["git", "rebase", target_branch],
                cwd=str(tmp_path),
                capture_output=True,
                text=True,
                env=_env,
            )
            if result.returncode != 0:
                subprocess.run(
                    ["git", "rebase", "--abort"],
                    cwd=str(tmp_path),
                    capture_output=True,
                    env=_env,
                )
                raise RuntimeError(f"Rebase of {source_branch} onto {target_branch} failed: {result.stderr.strip() or result.stdout.strip()}")
            # Get the rebased HEAD SHA.
            rebased_sha = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(tmp_path),
                capture_output=True,
                text=True,
                check=True,
                env=_env,
            ).stdout.strip()
            # Fast-forward the target branch to the rebased tip, resyncing any
            # worktree that has target_branch checked out (#1826 / AC-B2).
            # Coordination status residue is excluded from the dirty gate via
            # the single residue authority (FR-012 / #1878).
            advance_branch_ref(
                repo_root,
                target_branch,
                rebased_sha,
                env=_env,
                is_residue=is_toolchain_generated_churn,
            )
            return True  # early return — ref already updated
        else:
            # MERGE strategy (default for lane→mission): no-ff merge commit.
            result = subprocess.run(
                ["git", "merge", source_branch, "--no-edit", "-m", f"Merge {source_branch} into {target_branch}"],
                cwd=str(tmp_path),
                capture_output=True,
                text=True,
                env=_env,
            )
            if result.returncode != 0:
                subprocess.run(
                    ["git", "merge", "--abort"],
                    cwd=str(tmp_path),
                    capture_output=True,
                    env=_env,
                )
                raise RuntimeError(f"Merge of {source_branch} into {target_branch} failed: {result.stderr.strip() or result.stdout.strip()}")

        # #3942: after the squash (never for merge/rebase), preserve any
        # target-newer PRIMARY-partition planning artifact not already handled
        # during conflict resolution, amending it before the ref advances.
        if strategy == MergeStrategy.SQUASH:
            _preserve_target_newer_planning_artifacts(repo_root, tmp_path, source_branch, target_branch, _env)

        # Get the resulting commit SHA.
        merge_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            check=True,
            env=_env,
        ).stdout.strip()

        # Update the target branch ref to point to the merge commit, resyncing
        # any worktree that has target_branch checked out (#1826 / AC-B2).
        # Coordination status residue is excluded from the dirty gate via the
        # single residue authority (FR-012 / #1878).
        advance_branch_ref(
            repo_root,
            target_branch,
            merge_commit,
            env=_env,
            is_residue=is_toolchain_generated_churn,
        )
        return True
