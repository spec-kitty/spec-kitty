#!/usr/bin/env python3
"""Acceptance workflow utilities for Spec Kitty missions."""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from kernel.clock import now_utc_stamp
from pathlib import Path
from typing import Any

from kernel.paths import to_posix
from specify_cli.core.agent_config import get_auto_commit_default
from specify_cli.core.owned_mission import effective_root_kwargs
from specify_cli.core.paths import load_meta_fail_closed, read_target_branch_from_meta
from specify_cli.decisions.models import DecisionStatus
from specify_cli.decisions.store import load_index
from specify_cli.mission import Mission, MissionError, get_mission_for_feature
from specify_cli.mission_metadata import record_acceptance, resolve_mission_identity, write_meta
from specify_cli.status import CanonicalStatusNotFoundError
from specify_cli.status import EVENTS_FILENAME, SNAPSHOT_FILENAME, StoreError

from specify_cli.task_utils import (
    LANES,
    WorkPackage,
    get_lane_from_frontmatter,
    git_status_lines,
    run_git,
    split_frontmatter,
)
from specify_cli.task_utils.support import TaskCliError
from specify_cli.runtime.resolver import resolve_configured_artifact_name
from specify_cli.upgrade.pre30_guard import check_pre30_layout
from specify_cli.validators.paths import normalize_path_token

# WP04 (coord-authority-trio-degod-01KX7094) split: pure lane-gate checks live
# in ``gates_core`` (T022), pure WP-summary/path-convention helpers live
# in ``summary_core`` (T021). Bare re-export shims, NOT added to ``__all__`` (T025) —
# ``accept.py`` and the WP01 characterization suite keep importing these names
# straight off ``specify_cli.acceptance``; only ``collect_feature_summary`` /
# ``perform_acceptance`` (the executor) and the already-public ``WorkPackageState``
# are load-bearing package exports.
from .gates_core import (
    AcceptanceCheckDiagnostic,
    _check_lane_gates,
    _find_unchecked_tasks,
    _normalized_unchecked_tasks,
)
from .summary_core import (
    WorkPackageState,
    _build_recommended_fix_order,
    build_canceled_wp_report,
    build_warnings,
    build_work_package_state,
    evaluate_path_conventions,
)
from specify_cli.status_lanes import has_operator_provenance, is_acceptable_ending

logger = logging.getLogger(__name__)

AcceptanceMode = str  # Expected values: "pr", "local", "checklist"

# FR-004 (#2709): canonical acceptance/VCS provenance field shapes reconciled by
# the ``meta.json`` squash merge driver. These are the target-authoritative scalar
# keys ``record_acceptance``/``set_vcs_lock`` (``mission_metadata``) stamp; the
# squash driver overlays the target-branch (accepted-newer) value for each, while
# ``ACCEPTANCE_HISTORY_FIELD`` is unioned (append-only) across both sides. Kept here
# as the single canonical field-shape source (DIRECTIVE_044) so the driver never
# re-hardcodes the key list.
ACCEPTANCE_HISTORY_FIELD = "acceptance_history"
ACCEPTANCE_PROVENANCE_FIELDS: tuple[str, ...] = (
    "accepted_at",
    "accepted_by",
    "accepted_from_commit",
    "acceptance_mode",
    "accept_commit",
    "vcs",
    "vcs_locked_at",
)

# FR-009/FR-010 (#3599): the accept triple is sourced from the per-type
# expected-artifacts.yaml path_pattern authority, not hardcoded literals --
# byte-compatible with the prior "spec.md"/"plan.md"/"tasks.md" literals for
# software-dev (NFR-003). See
# tests/specify_cli/runtime/test_configured_artifact_name.py.
#
# #3622: resolved lazily (call-time, not import-time) so a malformed built-in
# expected-artifacts.yaml raises at point-of-use rather than on
# `import specify_cli.acceptance`. ``SPEC_FILE``/``PLAN_FILE``/``TASKS_FILE``/
# ``PRIMARY_ARTIFACT_FILES`` stay readable as module attributes (module
# __getattr__ below) for the existing ``from specify_cli.acceptance import
# SPEC_FILE`` style API; in-module call sites use the ``_spec_file()`` etc.
# functions directly since bare-name global lookups don't route through
# module __getattr__.
QUICKSTART_FILE = "quickstart.md"
DATA_MODEL_FILE = "data-model.md"
RESEARCH_FILE = "research.md"


def _spec_file() -> str:
    value: str = resolve_configured_artifact_name("input.spec.main")
    return value


def _plan_file() -> str:
    value: str = resolve_configured_artifact_name("output.plan.main")
    return value


def _tasks_file() -> str:
    value: str = resolve_configured_artifact_name("output.tasks.list")
    return value


def _primary_artifact_files() -> tuple[str, str, str, str, str, str]:
    return (
        _spec_file(),
        _plan_file(),
        QUICKSTART_FILE,
        _tasks_file(),
        RESEARCH_FILE,
        DATA_MODEL_FILE,
    )


def __getattr__(name: str) -> str | tuple[str, str, str, str, str, str]:
    if name == "SPEC_FILE":
        return _spec_file()
    if name == "PLAN_FILE":
        return _plan_file()
    if name == "TASKS_FILE":
        return _tasks_file()
    if name == "PRIMARY_ARTIFACT_FILES":
        return _primary_artifact_files()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


_DECISION_ID_MARKER = "decision_id:"
# WP02 (mission-completion-terminal-state): the former ``_ACCEPTED_READY_LANES``
# module constant is retired onto the single acceptable-ending authority
# (``specify_cli.status_lanes.is_acceptable_ending``, FR-005 / directive 044).

_LEGACY_NOT_DONE_LANES = ("planned", "claimed", "doing", "in_progress", "for_review")
# The ``canceled`` hint (FR-003) names the WP and states that operator-authored
# cancellation provenance is required — a synthetic cancellation (``--force``
# with no operator ``--note``) cannot be used to skip work silently. The trailing
# "reopen or replace it … approved or done" guidance is retained so the message
# stays actionable for an operator who did not mean to cancel.
_ACTIONABLE_LANE_BLOCKER_HINTS = {
    "in_review": "review is still in progress; complete the review and move the work package to approved or done",
    "blocked": "work package is blocked; resolve the blocker and move the work package to approved or done",
    "canceled": (
        "work package is canceled; operator-authored cancellation provenance required "
        "— reopen or replace it, then move the work package to approved or done"
    ),
}


def _porcelain_dirty_path(line: str) -> str:
    """Return the path component from a git porcelain v1 status line."""
    path = line[3:].strip()
    if " -> " in path:
        path = path.split(" -> ", 1)[1].strip()
    return path


def _is_accept_pipeline_own_write(path: str, *, mission_slug: str) -> bool:
    """True when *path* is one of the accept pipeline's own convergence writes.

    Retires the former accept-owned-paths filename frozenset (IC-07g / R-014)
    onto the shared :func:`mission_runtime.kind_for_mission_file` owner
    classifier. The accept pipeline itself writes exactly two mission-artifact
    files — ``acceptance-matrix.json`` (the ``ACCEPTANCE_MATRIX`` kind, written
    by ``_check_lane_gates`` when ``mutate_matrix=True``) and ``status.json``
    (the daemon-materialized view) — and must ignore its own writes,
    UNCONDITIONALLY (every topology, not only under coordination), for the
    accept ∘ accept convergence guarantee to hold (#1883).

    ``status.json`` is deliberately matched by its OWN basename, not by the
    coarse ``STATUS_STATE`` kind: that kind also carries ``status.events.jsonl``
    (the append-only lane-state log, ``mission_runtime/artifacts.py``'s
    ``_MISSION_FILE_KIND_BY_BASENAME``). The accept pipeline only *reads*
    ``status.events.jsonl`` — it never appends to it (the writer is
    ``status/store.py`` via ``move-task`` / ``mark-status``) — so it is NOT an
    accept-pipeline own-write, and a dirty one is real, uncommitted lane-state
    the accept gate must still block (review-cycle-1 BLOCKER 1; the retired
    accept-owned-paths filename set never contained it either). Matching the
    coarse kind here would silently widen the exemption past what was ever
    excluded and reintroduce exactly the false pass this retirement must not
    make (C6).

    Also deliberately NOT the wider ``is_toolchain_generated_churn`` union:
    that union's coord-residue leg is hardcoded to project against
    ``MissionTopology.COORD``, so calling it unconditionally here would ALSO
    make ``issue-matrix.md`` (the third ``ACCEPTANCE_MATRIX``-adjacent
    placement kind, ``ISSUE_MATRIX``) benign on a FLAT mission — the same class
    of widening, one level up. The wider, topology-gated ``ISSUE_MATRIX``
    residue exclusion stays exactly where it was:
    :func:`_filter_coordination_residue` below. ``mission_slug`` scopes the
    match to the CURRENT mission only — another mission's ``status.json`` is
    not this pipeline's own write and must still block.
    """
    from mission_runtime import MissionArtifactKind, kind_for_mission_file

    kind = kind_for_mission_file(path, mission_slug=mission_slug)
    if kind is MissionArtifactKind.ACCEPTANCE_MATRIX:
        return True
    if kind is MissionArtifactKind.STATUS_STATE:
        basename = to_posix(path).rsplit("/", 1)[-1]
        # Explicit ``bool`` annotation re-narrows the comparison: under this
        # project's ``follow_imports = "skip"`` mypy config,
        # ``SNAPSHOT_FILENAME`` (imported from the cross-module status facade)
        # is seen as ``Any``, and ``str == Any`` types as ``Any`` rather than
        # ``bool`` — the same cross-module-boundary pattern documented on
        # ``mission_runtime.resolution.PlacementSeam.read_dir``.
        is_status_snapshot: bool = basename == SNAPSHOT_FILENAME
        return is_status_snapshot
    return False


def _mission_routes_through_coordination(repo_root: Path, feature: str, *, effective_root: Path | None = None) -> bool:
    """True when ``feature`` routes through coordination under its STORED topology.

    FR-008 / FR-005: the accept dirty-tree gate is topology-aware. Read the WP02
    **stored** :class:`MissionTopology` via :func:`resolve_topology` and ask the
    ONE canonical :func:`routes_through_coordination` predicate — never the
    retired per-ref ``.kind`` arm (the predicate takes a ``MissionTopology``, not
    a ``CommitTarget``; passing a placement ref made it always-``False`` and
    silently disabled the residue filter). Under coordination topology the
    recognized coordination residue on the primary checkout is dropped from the
    dirty set; under a flat (``single_branch`` / ``lanes``) topology the predicate
    is ``False`` so the residue filter never runs and a flat mission's real
    primary artifacts STILL block.

    An unresolvable handle degrades to a non-coordination shape (fail-closed /
    conservative: the full dirty set is preserved, never widening the gate on a
    resolution edge case — NFR-003 / C-004), exactly as the canonical
    ``cli/commands/agent/mission.py`` routing site relies on.
    """
    from mission_runtime import (
        MissionArtifactKind,
        TopologySurface,
        resolve_topology,
        routes_through_coordination,
    )

    if effective_root is None:
        return routes_through_coordination(resolve_topology(repo_root, feature))

    from specify_cli.acceptance.execution_context import declared_home_surface

    return (
        declared_home_surface(
            repo_root,
            feature,
            MissionArtifactKind.ACCEPTANCE_MATRIX,
            effective_root=effective_root,
        )
        is TopologySurface.COORD
    )


def _accept_dirty_gate(
    git_dirty_raw: list[str],
    *,
    repo_root: Path,
    feature: str,
    effective_root: Path | None = None,
) -> list[str]:
    """Compute the accept dirty set: accept-owned exclusion + FR-008 coord residue.

    Three filters compose:

    1. **Accept-owned convergence (#1883):** the accept gate's own writes
       (``acceptance-matrix.json`` + ``status.json``) are excluded via
       :func:`_is_accept_pipeline_own_write`, the shared
       :func:`mission_runtime.kind_for_mission_file` owner classifier scoped to
       exactly those two kinds (IC-07g retired the former accept-owned-paths
       filename frozenset onto it) — unconditionally, every topology, so
       ``accept ∘ accept`` converges in every mode.
    2. **Self-bookkeeping exclusion (#2251):** spec-kitty's own bookkeeping
       files (``meta.json``, encoding-provenance JSONL, and ``kitty-ops/<ULID>.jsonl``
       Op-record orphans) are excluded via the SINGLE shared
       :func:`specify_cli.coordination.coherence.is_self_bookkeeping_churn`
       authority — no independent literal carried here (G-5 invariant / #1914
       framing; WP11 retired the former ``mission_runtime`` self-bookkeeping predicate
       onto this owner-module leg).
    3. **FR-008 topology-aware residue:** under coordination topology the
       recognized coordination residue (stale primary copies of artifacts owned
       by the coordination branch) is excluded via the SAME per-ref pattern the
       record-analysis preflight uses (:func:`routes_through_coordination` + the
       :func:`specify_cli.coordination.coherence.is_coord_residue_churn` residue
       leg -- WP12 retired the former ``mission_runtime`` predicate onto this
       owner leg). A flat mission routes through PRIMARY, so its real primary
       artifacts STILL block. The accept-owned exclusion (1) is NOT widened to
       this leg's ``ISSUE_MATRIX`` kind (see :func:`_is_accept_pipeline_own_write`).

    Non-accept-owned, non-self-bookkeeping, non-residue dirt is preserved verbatim
    (fail-closed, NFR-003).
    """
    from specify_cli.coordination.coherence import is_self_bookkeeping_churn

    git_dirty = [
        line
        for line in git_dirty_raw
        if not _is_accept_pipeline_own_write(_porcelain_dirty_path(line), mission_slug=feature) and not is_self_bookkeeping_churn(_porcelain_dirty_path(line))
    ]
    return _filter_coordination_residue(
        git_dirty, repo_root=repo_root, feature=feature,
        **effective_root_kwargs(effective_root),
    )


def _filter_coordination_residue(
    dirty_lines: list[str],
    *,
    repo_root: Path,
    feature: str,
    effective_root: Path | None = None,
) -> list[str]:
    """Drop coordination-residue dirty lines when the mission routes through coord.

    FR-008 convergence on the ``mission.py`` reference pattern: only when
    :func:`routes_through_coordination` holds does
    :func:`specify_cli.coordination.coherence.is_coord_residue_churn` (the
    stored-topology residue authority — flat→``False``; WP12 retired the former
    ``mission_runtime`` predicate onto this owner leg) get to exclude a path.
    The predicate is NOT a widening of the accept-owned exclusion
    (:func:`_is_accept_pipeline_own_write`): it is the per-ref
    coordination gate applied to recognized coordination-owned artifacts (spec /
    plan / tasks / lanes / status / matrices / checklists) left stale on the
    primary checkout. Real source edits, unknown mission scratch files, and
    another mission's artifacts are not recognized residue, so they still block.
    """
    from specify_cli.coordination.coherence import is_coord_residue_churn

    if not _mission_routes_through_coordination(
        repo_root, feature, **effective_root_kwargs(effective_root),
    ):
        return dirty_lines
    return [line for line in dirty_lines if not is_coord_residue_churn(_porcelain_dirty_path(line), mission_slug=feature)]


class AcceptanceError(TaskCliError):
    """Raised when acceptance cannot complete due to outstanding issues."""


class ArtifactEncodingError(AcceptanceError):
    """Raised when a project artifact cannot be decoded as UTF-8."""

    def __init__(self, path: Path, error: UnicodeDecodeError):
        byte = error.object[error.start : error.start + 1]
        byte_display = f"0x{byte[0]:02x}" if byte else "unknown"
        message = f"Invalid UTF-8 encoding in {path}: byte {byte_display} at offset {error.start}. Run with --normalize-encoding to fix automatically."
        super().__init__(message)
        self.path = path
        self.error = error


def _format_lane_blocker(lane: str, wp_id: str) -> str:
    hint = _ACTIONABLE_LANE_BLOCKER_HINTS.get(lane)
    if hint is None:
        hint = "move the work package to approved or done"
    return f"{wp_id}: canonical lane is '{lane}'; {hint}."


@dataclass
class AcceptanceSummary:
    feature: str
    repo_root: Path
    feature_dir: Path
    tasks_dir: Path
    branch: str | None
    worktree_root: Path
    primary_repo_root: Path
    lanes: dict[str, list[str]]
    work_packages: list[WorkPackageState]
    metadata_issues: list[str]
    activity_issues: list[str]
    unchecked_tasks: list[str]
    needs_clarification: list[str]
    missing_artifacts: list[str]
    optional_missing: list[str]
    git_dirty: list[str]
    path_violations: list[str]
    warnings: list[str]
    skipped_checks: list[AcceptanceCheckDiagnostic] = field(default_factory=list)
    blocked_checks: list[AcceptanceCheckDiagnostic] = field(default_factory=list)
    recommended_fix_order: list[str] = field(default_factory=list)
    #: Accept-eligible cancellations (operator provenance) in the pinned NFR-003
    #: shape ``{wp_id, reason, actor, at}``. A synthetic cancellation is NOT here
    #: — it surfaces as a blocker via :meth:`outstanding` instead.
    canceled_wps: list[dict[str, str]] = field(default_factory=list)

    def _operator_provenance_by_wp(self) -> dict[str, bool]:
        """Per-WP operator-provenance lookup carried from the bucketing seam."""
        return {wp.work_package_id: wp.has_operator_provenance for wp in self.work_packages}

    @property
    def all_done(self) -> bool:
        """True when every WP is at an acceptable ending AND the mission delivered something.

        Decides the ``canceled`` case PER-WP (T009): the provenance-free lane
        bucket cannot tell an operator cancellation from a synthetic one, so
        acceptability is evaluated through the single
        :func:`~specify_cli.status_lanes.is_acceptable_ending` authority with the
        per-WP provenance carried onto :class:`WorkPackageState`. ``approved`` /
        ``done`` are always acceptable; ``canceled`` only with operator
        provenance; every other lane blocks.

        The vacuous guard is preserved: a mission with no tracked WPs is
        ``all_done`` (nothing outstanding). The spec "delivered nothing" guard is
        explicit and separate: a mission whose WPs are ALL canceled (none reached
        ``approved``/``done``) is NOT complete even though each cancellation is an
        acceptable ending on its own.
        """
        provenance = self._operator_provenance_by_wp()
        saw_wp = False
        delivered_something = False
        for lane, wp_ids in self.lanes.items():
            for wp_id in wp_ids:
                saw_wp = True
                if not is_acceptable_ending(lane, has_provenance=provenance.get(wp_id, False)):
                    return False
                # ``is_acceptable_ending(lane, has_provenance=False)`` is True
                # for exactly ``approved``/``done`` — the lanes that count as
                # delivered work (a canceled ending, even acceptable, delivered
                # nothing on its own).
                if is_acceptable_ending(lane, has_provenance=False):
                    delivered_something = True
        if not saw_wp:
            return True
        return delivered_something

    @property
    def ok(self) -> bool:
        return (
            self.all_done
            and not self.metadata_issues
            and not self.activity_issues
            and not self.unchecked_tasks
            and not self.needs_clarification
            and not self.missing_artifacts
            and not self.git_dirty
            and not self.path_violations
        )

    def _lane_blockers(self) -> list[str]:
        """Actionable lane blockers, with operator-canceled WPs excluded.

        A ``canceled`` WP with operator-authored provenance is an acceptable
        ending (reported under ``canceled_wps``), never a blocker (FR-001/FR-002);
        a synthetic cancellation stays a blocker naming the missing provenance
        (FR-003). Every other actionable lane (``in_review``/``blocked``) is a
        blocker as before (FR-006).
        """
        provenance = self._operator_provenance_by_wp()
        blockers: list[str] = []
        for lane in _ACTIONABLE_LANE_BLOCKER_HINTS:
            for wp_id in self.lanes.get(lane, []):
                if lane == "canceled" and provenance.get(wp_id, False):
                    continue
                blockers.append(_format_lane_blocker(lane, wp_id))
        return blockers

    def _delivered_nothing_blockers(self) -> list[str]:
        """Explicit "delivered nothing" guard (spec Edge Case).

        When every tracked WP is at an acceptable ending but NONE reached
        ``approved``/``done`` (i.e. all are canceled), the mission delivered
        nothing and must not be silently reported complete. This is an explicit
        check, not an accident of terminal-lane classification.
        """
        provenance = self._operator_provenance_by_wp()
        saw_wp = False
        delivered_something = False
        for lane, wp_ids in self.lanes.items():
            for wp_id in wp_ids:
                saw_wp = True
                if not is_acceptable_ending(lane, has_provenance=provenance.get(wp_id, False)):
                    return []  # a real blocker already fires elsewhere
                if is_acceptable_ending(lane, has_provenance=False):
                    delivered_something = True
        if saw_wp and not delivered_something:
            return ["mission delivered nothing: every work package is canceled; none reached approved or done"]
        return []

    def outstanding(self) -> dict[str, list[str]]:
        buckets = {
            "not_done": [
                *(wp_id for lane in _LEGACY_NOT_DONE_LANES for wp_id in self.lanes.get(lane, [])),
            ],
            "lane_blockers": self._lane_blockers(),
            "delivered_nothing": self._delivered_nothing_blockers(),
            "metadata": self.metadata_issues,
            "activity": self.activity_issues,
            "unchecked_tasks": self.unchecked_tasks,
            "needs_clarification": self.needs_clarification,
            "missing_artifacts": self.missing_artifacts,
            "git_dirty": self.git_dirty,
            "path_violations": self.path_violations,
        }
        return {key: value for key, value in buckets.items() if value}

    def failed_checks(self) -> list[AcceptanceCheckDiagnostic]:
        return [AcceptanceCheckDiagnostic(check=check, detail=detail) for check, details in self.outstanding().items() for detail in details]

    def to_dict(self) -> dict[str, object]:
        identity = resolve_mission_identity(self.feature_dir)
        return {
            "mission_slug": identity.mission_slug,
            "mission_number": identity.mission_number,
            "mission_type": identity.mission_type,
            "branch": self.branch,
            "repo_root": str(self.repo_root),
            "feature_dir": str(self.feature_dir),
            "tasks_dir": str(self.tasks_dir),
            "worktree_root": str(self.worktree_root),
            "primary_repo_root": str(self.primary_repo_root),
            "lanes": self.lanes,
            "work_packages": [
                {
                    "id": wp.work_package_id,
                    "lane": wp.lane,
                    "title": wp.title,
                    "path": wp.path,
                    "latest_lane": wp.latest_lane,
                    "has_lane_entry": wp.has_lane_entry,
                    "metadata": wp.metadata,
                }
                for wp in self.work_packages
            ],
            "metadata_issues": self.metadata_issues,
            "activity_issues": self.activity_issues,
            "unchecked_tasks": self.unchecked_tasks,
            "needs_clarification": self.needs_clarification,
            "missing_artifacts": self.missing_artifacts,
            "optional_missing": self.optional_missing,
            "git_dirty": self.git_dirty,
            "path_violations": self.path_violations,
            "warnings": self.warnings,
            "failed_checks": [item.to_dict() for item in self.failed_checks()],
            "skipped_checks": [item.to_dict() for item in self.skipped_checks],
            "blocked_checks": [item.to_dict() for item in self.blocked_checks],
            "recommended_fix_order": self.recommended_fix_order,
            "canceled_wps": self.canceled_wps,
            "all_done": self.all_done,
            "ok": self.ok,
        }


@dataclass
class AcceptanceResult:
    summary: AcceptanceSummary
    mode: AcceptanceMode
    accepted_at: str
    accepted_by: str
    parent_commit: str | None
    accept_commit: str | None
    commit_created: bool
    instructions: list[str]
    cleanup_instructions: list[str]
    notes: list[str] = field(default_factory=list)
    accepted_wps: list[str] = field(default_factory=list)
    approved_wps: list[str] = field(default_factory=list)
    done_wps: list[str] = field(default_factory=list)
    merge_pending_wps: list[str] = field(default_factory=list)
    #: NFR-003 ``accept --json`` field: accept-eligible cancellations in the
    #: pinned ``{wp_id, reason, actor, at}`` shape (schema
    #: ``contracts/accept-canceled-wps.schema.json``). Distinct from blockers.
    canceled_wps: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "accepted_at": self.accepted_at,
            "accepted_by": self.accepted_by,
            "mode": self.mode,
            "parent_commit": self.parent_commit,
            "accept_commit": self.accept_commit,
            "commit_created": self.commit_created,
            "instructions": self.instructions,
            "cleanup_instructions": self.cleanup_instructions,
            "notes": self.notes,
            "accepted_wps": self.accepted_wps,
            "approved_wps": self.approved_wps,
            "done_wps": self.done_wps,
            "merge_pending_wps": self.merge_pending_wps,
            "canceled_wps": self.canceled_wps,
            "summary": self.summary.to_dict(),
        }


def _iter_work_packages(repo_root: Path, feature: str, *, effective_root: Path | None = None) -> Iterable[WorkPackage]:
    """Iterate over work packages in flat tasks/ directory layout.

    Pre-3.0 missions (lane-directory layout) are hard-rejected with
    :class:`~specify_cli.upgrade.pre30_guard.Pre30LayoutError` — run
    ``spec-kitty upgrade`` to migrate before running the acceptance scan.
    """
    # WORK_PACKAGE_TASK is a PRIMARY-partition kind: route the WP-task read
    # through the kind-aware seam so a coord-topology mission reads its tasks off
    # the PRIMARY surface (where they live), not the materialized -coord husk
    # whose tasks/ dir is absent (closeout N+1 — debbie §3).
    feature_path = _wp_tasks_read_dir(
        repo_root, feature, **effective_root_kwargs(effective_root),
    )
    tasks_dir = feature_path / "tasks"
    if not tasks_dir.exists():
        raise AcceptanceError(f"Feature '{feature}' has no tasks directory at {tasks_dir}.")

    # Pre-3.0 layout: hard-reject (defense-in-depth — collect_feature_summary
    # also guards eagerly). The retirement of the legacy reader must NOT degrade
    # into a silent warn-and-skip: yielding zero work packages makes
    # AcceptanceSummary vacuously ``all_done`` and lets ``accept`` auto-commit an
    # unmigrated mission whose real (possibly un-done) WPs still sit in
    # ``tasks/planned/`` etc. (#1057 / squad Blocker 1). Fail closed with the
    # ``spec-kitty upgrade`` migration message, matching the task commands.
    check_pre30_layout(feature_path)

    # Flat-layout: tasks/ directory, lane from frontmatter.
    for path in sorted(tasks_dir.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        text = _read_text_strict(path)
        front, body, padding = split_frontmatter(text)
        try:
            lane = get_lane_from_frontmatter(path, warn_on_missing=False)
        except CanonicalStatusNotFoundError:
            lane = "uninitialized"
        relative = path.relative_to(tasks_dir)
        yield WorkPackage(
            feature=feature,
            path=path,
            current_lane=lane,
            relative_subpath=relative,
            frontmatter=front,
            body=body,
            padding=padding,
        )


def _read_text_strict(path: Path) -> str:
    """Read a file as UTF-8, raising ArtifactEncodingError on decode failure."""
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ArtifactEncodingError(path, exc) from exc


def _read_file(path: Path) -> str:
    return _read_text_strict(path) if path.exists() else ""


def _check_needs_clarification(files: Sequence[Path]) -> list[str]:
    results: list[str] = []
    for file_path in files:
        if file_path.exists():
            text = _read_text_strict(file_path)
            if _has_blocking_clarification_marker(file_path, text):
                results.append(str(file_path))
    return results


def _has_blocking_clarification_marker(file_path: Path, text: str) -> bool:
    markers = list(_iter_clarification_decision_ids(text))
    if not markers:
        return False

    index = load_index(file_path.parent)
    entries_by_id = {entry.decision_id: entry for entry in index.entries}
    for decision_id in markers:
        entry = entries_by_id.get(decision_id)
        if entry is None or entry.status in {DecisionStatus.OPEN, DecisionStatus.DEFERRED}:
            return True
    return False


def _iter_clarification_decision_ids(text: str) -> Iterable[str]:
    for line in text.splitlines():
        marker_start = line.find("[NEEDS CLARIFICATION:")
        if marker_start == -1:
            continue
        marker_end = line.find("]", marker_start)
        if marker_end == -1:
            continue
        comment_start = line.find("<!--", marker_end)
        if comment_start == -1:
            continue
        comment_end = line.find("-->", comment_start + 4)
        if comment_end == -1:
            continue
        comment_body = line[comment_start + 4 : comment_end]
        decision_id_index = comment_body.find(_DECISION_ID_MARKER)
        if decision_id_index == -1:
            continue
        decision_id_text = comment_body[decision_id_index + len(_DECISION_ID_MARKER) :].strip()
        if decision_id_text:
            yield decision_id_text.split(maxsplit=1)[0]


# Fallback optional-artifact tokens used when a mission is absent or its config
# carries no ``artifacts`` block (#3785). This mirrors the historical hardcoded
# list; it deliberately omits software-dev's ``checklists/`` — the mission's own
# ``artifacts.optional`` declaration is the SSOT when available (FR-006).
_FALLBACK_OPTIONAL_ARTIFACTS: tuple[str, ...] = (
    QUICKSTART_FILE,
    DATA_MODEL_FILE,
    RESEARCH_FILE,
    "contracts",
)


def _optional_artifact_tokens(mission: Mission | None) -> list[str]:
    """Optional-artifact tokens for a mission (#3785, FR-006).

    Prefers the mission's declared ``artifacts.optional`` (via the null-safe
    :meth:`Mission.get_optional_artifacts`) so the set stays the single source of
    truth — including software-dev's ``checklists/``. Falls back to
    :data:`_FALLBACK_OPTIONAL_ARTIFACTS` when there is no mission (``MissionError``)
    OR the mission config has no ``artifacts`` attribute. The ``getattr`` guard is
    load-bearing (C-009): the #3783 regression injects an artifacts-less
    ``SimpleNamespace`` config, on which ``get_optional_artifacts()`` would raise
    ``AttributeError`` (paths.py:160 uses the same guard).
    """
    if mission is not None and getattr(mission.config, "artifacts", None) is not None:
        return list(mission.get_optional_artifacts())
    return list(_FALLBACK_OPTIONAL_ARTIFACTS)


def _approved_lane_source_roots(
    repo_root: Path,
    feature_dir: Path,
    lanes: dict[str, list[str]],
) -> tuple[Path, ...]:
    """Worktrees of this mission's fully-approved execution lanes (#4254).

    Acceptance evaluates path conventions BEFORE the approved lane's source is
    integrated into the primary checkout, so a lane that introduces the first
    ``tests/`` or ``docs/`` has them only in its own worktree. Those trees are
    the genuine candidate source for this acceptance, and they are what the
    build-path check may additionally look in.

    Only lanes whose every work package is already ``approved``/``done`` are
    returned, so an unapproved lane — or any other checkout on disk — can
    never satisfy a declared path. A lane with no work packages contributes
    nothing. Missing or corrupt ``lanes.json`` yields no roots at all: the
    check then behaves exactly as it did before this change rather than
    guessing at a topology.
    """
    from specify_cli.lanes.branch_naming import worktree_path  # noqa: PLC0415
    from specify_cli.lanes.persistence import CorruptLanesError, read_lanes_json  # noqa: PLC0415

    accepted_wps = {*lanes.get("approved", []), *lanes.get("done", [])}
    if not accepted_wps:
        return ()
    try:
        manifest = read_lanes_json(feature_dir)
    except CorruptLanesError:
        return ()
    if manifest is None:
        return ()

    roots: list[Path] = []
    for lane in manifest.lanes:
        lane_wps = set(getattr(lane, "wp_ids", ()) or ())
        if not lane_wps or not lane_wps <= accepted_wps:
            continue
        candidate = worktree_path(
            repo_root,
            manifest.mission_slug,
            mission_id=manifest.mission_id,
            lane_id=lane.lane_id,
        )
        if candidate.is_dir():
            roots.append(candidate)
    return tuple(roots)


def _missing_artifacts(feature_dir: Path, mission: Mission | None) -> tuple[list[str], list[str]]:
    required = [feature_dir / _spec_file(), feature_dir / _plan_file(), feature_dir / _tasks_file()]
    # ``Path`` normalizes trailing slashes, so a ``contracts/`` token maps to the
    # same relative string ``contracts`` the ``normalize_path_token`` dedup expects
    # (C-003: severity for ``contracts/`` is decided downstream, unchanged here).
    optional = [feature_dir / token for token in _optional_artifact_tokens(mission)]
    missing_required = [str(p.relative_to(feature_dir)) for p in required if not p.exists()]
    missing_optional = [str(p.relative_to(feature_dir)) for p in optional if not p.exists()]
    return missing_required, missing_optional


# Unicode smart-punctuation -> ASCII equivalents, applied by
# :func:`_recover_normalized_text`.
_ENCODING_NORMALIZE_MAP = {
    "‘": "'",  # Left single quotation mark -> apostrophe
    "’": "'",  # Right single quotation mark -> apostrophe
    "‚": "'",  # Single low-9 quotation mark -> apostrophe
    "“": '"',  # Left double quotation mark -> straight quote
    "”": '"',  # Right double quotation mark -> straight quote
    "„": '"',  # Double low-9 quotation mark -> straight quote
    "—": "--",  # Em dash -> double hyphen
    "–": "-",  # En dash -> hyphen
    "…": "...",  # Horizontal ellipsis -> three dots
    " ": " ",  # Non-breaking space -> regular space
    "•": "*",  # Bullet -> asterisk
    "·": "*",  # Middle dot -> asterisk
}


def _gather_primary_encoding_candidates(feature_dir: Path) -> list[Path]:
    """Every artifact ``normalize_feature_encoding`` scans: the
    ``PRIMARY_ARTIFACT_FILES`` planning docs plus the ``tasks/``, ``research/``
    and ``checklists/`` markdown subtrees (all PRIMARY-partition kinds)."""
    candidates: list[Path] = [feature_dir / artifact_name for artifact_name in _primary_artifact_files()]
    result = [p for p in candidates if p.exists()]
    for subdir in (feature_dir / "tasks", feature_dir / "research", feature_dir / "checklists"):
        if subdir.exists():
            result.extend(subdir.rglob("*.md"))
    return result


def _recover_normalized_text(data: bytes) -> str | None:
    """Decode legacy-encoded bytes to UTF-8 text with ASCII character mapping.

    Returns ``None`` when ``data`` is already valid UTF-8 (nothing to rewrite);
    otherwise the recovered + normalized text. Tries cp1252 then latin-1, falls
    back to a lossy UTF-8 replace, strips a leading BOM, and maps Unicode
    smart-punctuation to ASCII via :data:`_ENCODING_NORMALIZE_MAP`.
    """
    try:
        data.decode("utf-8")
        return None
    except UnicodeDecodeError:
        pass

    text: str | None = None
    for encoding in ("cp1252", "latin-1"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = data.decode("utf-8", errors="replace")

    text = text.lstrip("﻿")  # strip UTF-8 BOM if present
    for unicode_char, ascii_replacement in _ENCODING_NORMALIZE_MAP.items():
        text = text.replace(unicode_char, ascii_replacement)
    return text


def normalize_feature_encoding(repo_root: Path, feature: str, *, effective_root: Path | None = None) -> list[Path]:
    """Normalize file encoding from Windows-1252 to UTF-8 with ASCII character mapping.

    Converts Windows-1252 encoded files to UTF-8, replacing Unicode smart quotes
    and special characters with ASCII equivalents for maximum compatibility.
    """
    # Every artifact this normalizer touches — the planning docs in
    # ``PRIMARY_ARTIFACT_FILES`` plus the ``tasks/`` (WORK_PACKAGE_TASK),
    # ``research/`` (RESEARCH) and ``checklists/`` (CHECKLIST) subtrees — is a
    # PRIMARY-partition kind, so the encoding-recovery scan must read the PRIMARY
    # surface, not the coord-aware husk. Pre-fix this used
    # ``resolve_feature_dir_for_mission`` (coord-aware); on a coord-topology
    # mission it scanned the materialized ``-coord`` worktree, missing the real
    # primary artifacts an encoding fault lives in (closeout N+1 sibling — debbie
    # §3). ``_planning_read_dir`` resolves the PRIMARY surface via the same
    # kind-aware seam; behavior-neutral for a FLATTENED mission.
    feature_dir = _planning_read_dir(
        repo_root, feature, **effective_root_kwargs(effective_root),
    )
    if not feature_dir.exists():
        return []

    rewritten: list[Path] = []
    seen: set[Path] = set()
    for path in _gather_primary_encoding_candidates(feature_dir):
        if path in seen or not path.exists():
            continue
        seen.add(path)
        text = _recover_normalized_text(path.read_bytes())
        if text is None:
            continue
        path.write_text(text, encoding="utf-8")
        rewritten.append(path)
    return rewritten


def _resolve_git_context(repo_root: Path) -> tuple[str | None, Path, Path, list[str]]:
    """Collect branch, worktree root, primary repo root, and dirty files."""
    branch: str | None = None
    try:
        branch_value = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root, check=True).stdout.strip()
        if branch_value and branch_value != "HEAD":
            branch = branch_value
    except TaskCliError:
        pass

    try:
        worktree_root = Path(run_git(["rev-parse", "--show-toplevel"], cwd=repo_root, check=True).stdout.strip()).resolve()
    except TaskCliError:
        worktree_root = repo_root

    try:
        git_common_dir = Path(run_git(["rev-parse", "--git-common-dir"], cwd=repo_root, check=True).stdout.strip()).resolve()
        primary_repo_root = git_common_dir.parent
    except TaskCliError:
        primary_repo_root = repo_root

    try:
        git_dirty = git_status_lines(repo_root)
    except TaskCliError:
        git_dirty = []

    return branch, worktree_root, primary_repo_root, git_dirty


def _collect_snapshot_wps(feature: str, feature_dir: Path, activity_issues: list[str]) -> dict[str, dict[str, Any]]:
    """Load canonical WP states from status.events.jsonl; append issues on failure."""
    events_path = feature_dir / EVENTS_FILENAME
    _missing_msg = (
        f"No canonical state found for feature '{feature}'. "
        "Cannot validate acceptance without status.events.jsonl. "
        f"Run 'spec-kitty agent mission finalize-tasks --mission {feature}' to bootstrap the event log."
    )
    if not events_path.exists():
        activity_issues.append(_missing_msg)
        return {}
    try:
        from specify_cli.status import reduce
        from specify_cli.status import read_event_stream

        event_stream = read_event_stream(feature_dir)
        snapshot = reduce(event_stream.transitions, event_stream.annotations)
    except StoreError as exc:
        raise AcceptanceError(f"Status event log is corrupted for feature '{feature}': {exc}") from exc
    if not snapshot.work_packages:
        activity_issues.append(_missing_msg)
    return snapshot.work_packages


def _status_read_feature_dir(
    repo_root: Path, feature: str, feature_dir: Path, *, effective_root: Path | None = None,
) -> Path:
    """Return canonical status read path for acceptance lane validation.

    Routes through the SINGLE guarded read-side seam
    (:func:`resolve_handle_to_read_path`, IC-01 / FR-001): the seam owns the
    primary-meta probe and the ONE sanctioned mid8 cascade
    (``meta.mid8`` → ``resolve_mid8(meta.mission_id)`` → ``mid8_from_slug``,
    NFR-005/#1868) internally, so this caller no longer derives the mid8 in
    parallel (WP01 reroute — byte-identical: the seam derives the same mid8 and
    forwards it to the existence-gated topology resolver with
    ``require_exists=False``).

    The acceptance-specific ``status_dir if status_dir.exists() else feature_dir``
    fallback is preserved verbatim: acceptance validation must stay LENIENT and
    degrade to the primary anchor dir rather than fail-close.
    """
    from specify_cli.missions._read_path_resolver import resolve_handle_to_read_path

    if effective_root is not None:
        from mission_runtime import MissionArtifactKind, placement_seam

        owned_status: Path = placement_seam(repo_root, feature, effective_root=effective_root).read_dir(MissionArtifactKind.STATUS_STATE)
        return owned_status
    status_dir = resolve_handle_to_read_path(repo_root, feature)
    return status_dir if status_dir.exists() else feature_dir


# Planning artifacts the accept gate inspects, mapped to their canonical
# ``MissionArtifactKind`` (FR-002 / data-model.md site map rows 2-9). Every entry
# is a PRIMARY-partition kind (``is_primary_artifact_kind`` True), so each resolves
# the SAME primary feature dir through the WP01 read seam. ``quickstart.md`` carries
# no dedicated kind; it is a planning checklist doc and is classified ``CHECKLIST``
# (a PRIMARY-partition kind) explicitly here — no silent default (DECISION 1 spirit).
def _accept_planning_artifact_kinds() -> dict[str, Any]:
    from mission_runtime import MissionArtifactKind

    return {
        _spec_file(): MissionArtifactKind.SPEC,
        _plan_file(): MissionArtifactKind.FINALIZED_EXECUTION_PLAN,
        _tasks_file(): MissionArtifactKind.TASKS_INDEX,
        RESEARCH_FILE: MissionArtifactKind.RESEARCH,
        DATA_MODEL_FILE: MissionArtifactKind.DATA_MODEL,
        QUICKSTART_FILE: MissionArtifactKind.CHECKLIST,
    }


def _planning_read_dir(repo_root: Path, feature: str, *, effective_root: Path | None = None) -> Path:
    """Return the PRIMARY mission dir the accept gate reads planning artifacts from.

    FR-002 (#2085): the accept gate's PLANNING reads (spec/plan/tasks/research/
    data-model/quickstart) are split off the coord-aware ``status_feature_dir`` and
    routed onto the SINGLE kind-aware read seam
    (:func:`~specify_cli.missions._read_path_resolver.resolve_planning_read_dir`,
    WP01). Because every planning artifact the gate reads is a PRIMARY-partition
    kind, they all resolve the same primary feature dir; we resolve once (keyed on
    ``SPEC``) and the per-artifact existence checks reuse it. This is NOT a parallel
    resolver (C-001 forbids a NEW resolver, not consuming the existing one): it is a
    thin caller of the shared chokepoint, mirroring ``mission.py::_planning_read_dir``.

    The STATUS/acceptance reads (``status.events.jsonl``, acceptance-matrix) keep
    using ``status_feature_dir`` with its leniency (C-002) — they are NOT routed here.

    coord-primary-partition-lock WP01 (T004): the final resolve routes through
    the placement seam's ``read_dir`` rather than ``resolve_planning_read_dir``
    directly — DRY-only consolidation (C-001), out-of-map edit (this file is not
    a WP01 owned file; the 4 duplicate ``_planning_read_dir`` wrapper copies
    collapse onto the seam's single read entry point).
    """
    from mission_runtime import is_primary_artifact_kind, placement_seam

    kinds = _accept_planning_artifact_kinds()
    # Guard the "resolve once and reuse" invariant: every planning artifact the gate
    # reads MUST be a PRIMARY-partition kind, so they all resolve the same primary
    # dir. If a future single-line reclassification in ``mission_runtime.artifacts``
    # moves one across the partition (NFR-004), fail LOUD here rather than silently
    # reading a stale coord surface for one artifact.
    non_primary = sorted(name for name, kind in kinds.items() if not is_primary_artifact_kind(kind))
    if non_primary:
        raise AcceptanceError(
            "Accept-gate planning split invariant violated: planning artifact(s) "
            f"{non_primary} are no longer PRIMARY-partition kinds; the per-artifact "
            "read dir must be resolved individually (FR-002 / data-model.md)."
        )
    # Explicit ``Path`` annotation: under the project's ``follow_imports = "skip"``
    # mypy config the cross-module ``PlacementSeam.read_dir`` return is seen as
    # ``Any``; the annotation re-narrows it (the method IS typed ``-> Path``) so the
    # chokepoint return is not an ``Any`` leak — matching ``mission.py::_planning_read_dir``.
    read_dir: Path = placement_seam(
        repo_root, feature, **effective_root_kwargs(effective_root),
    ).read_dir(kinds[_spec_file()])
    return read_dir


def _wp_tasks_read_dir(repo_root: Path, feature: str, *, effective_root: Path | None = None) -> Path:
    """Return the PRIMARY mission dir the accept gate reads WP tasks from.

    Closeout N+1 (debbie §3): the accept gate's WP-task iteration
    (:func:`_iter_work_packages`) reads ``tasks/WP*.md`` — a
    ``WORK_PACKAGE_TASK`` artifact, a PRIMARY-partition kind. Pre-fix it resolved
    the coord-aware :func:`resolve_feature_dir_for_mission`, landing on the
    materialized ``-coord`` worktree whose ``tasks/`` directory is ABSENT (WP
    tasks live on PRIMARY for both read and write — INV-5 symmetry). The REAL
    accept gate then raised ``AcceptanceError: ... has no tasks directory`` for a
    coord-topology mission whose WP tasks live (correctly) only on primary.

    This routes the WP-task read through the SAME kind-aware chokepoint the
    planning-doc reads use (:meth:`~mission_runtime.PlacementSeam.read_dir`),
    keyed on ``WORK_PACKAGE_TASK`` — mirroring the WP04 ``map-requirements``
    fix (tasks.py: ``resolve_planning_read_dir`` for the WP-task glob).
    Behavior-neutral for a FLATTENED mission (candidate == primary).
    The STATUS reads stay on ``status_feature_dir`` (C-002), unchanged.

    read-side-placement-seam-migration WP07: routed through
    :func:`~mission_runtime.placement_seam` (fail-loud on a deleted-coord
    mismatch, NFR-002) instead of the kind-blind
    ``resolve_planning_read_dir`` — mirrors ``_planning_read_dir`` above, the
    sibling accept-gate PRIMARY read. Behavior-neutral here: WORK_PACKAGE_TASK
    is PRIMARY-partition, so both resolve the identical primary dir.
    """
    from mission_runtime import MissionArtifactKind, is_primary_artifact_kind, placement_seam

    # Fail LOUD if a future reclassification moves WORK_PACKAGE_TASK off the
    # primary partition (NFR-004): the gate's WP-task read must stay on the same
    # single primary surface as the WP-task write, never silently a coord husk.
    if not is_primary_artifact_kind(MissionArtifactKind.WORK_PACKAGE_TASK):
        raise AcceptanceError(
            "Accept-gate WP-task read invariant violated: WORK_PACKAGE_TASK is no "
            "longer a PRIMARY-partition kind; the WP-task read dir must be resolved "
            "against its current partition (closeout N+1 / data-model.md)."
        )
    read_dir: Path = placement_seam(
        repo_root, feature, **effective_root_kwargs(effective_root),
    ).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)
    return read_dir


def _primary_anchor_feature_dir(
    repo_root: Path, feature: str, read_dir: Path, *, effective_root: Path | None = None,
) -> Path:
    """Return the primary-checkout mission dir anchoring ``AcceptanceSummary``.

    ``resolve_feature_dir_for_mission`` hands back the coord-aware READ
    directory — the coordination worktree once one is materialized. The
    summary's identity anchor (``AcceptanceSummary.feature_dir``) must stay on
    the primary checkout (status source of truth is feature metadata on main:
    ``_commit_acceptance_meta`` records acceptance into the primary
    ``meta.json``), while artifact/status reads stay coord-aware through
    ``_status_read_feature_dir``.

    The primary dir name can differ from the read dir name — backfilled legacy
    missions carry no ``-<mid8>`` suffix on the primary side while their coord
    mission dir does — so the anchor is derived from the mission *handle*,
    never recomposed from the read dir's name:

    1. literal handle → primary composition (covers canonical ``<slug>-<mid8>``
       names AND backfilled legacy names);
    2. handle resolver (mid8 / ULID / numeric prefix / human slug) → the
       primary directory it indexed;
    3. fall back to the resolved read dir rather than fail when no
       primary-side directory exists (identity/existence was already validated
       by the read resolution).

    read-side-seam-primary-primitive-closure-01KYKMMT WP05/FR-004/FR-015:
    step 1's composition is routed through the kind-aware seam
    (``PRIMARY_METADATA`` is a PRIMARY-partition kind, so it resolves the
    topology-blind primary dir directly -- it never consults the coord husk
    the *kind-blind* ``resolve_feature_dir_for_mission`` handed the caller's
    ``read_dir`` argument can land on, which is exactly why this function
    exists as a separate anchor).
    """
    from mission_runtime import MissionArtifactKind, placement_seam

    primary_candidate: Path = placement_seam(
        repo_root, feature, **effective_root_kwargs(effective_root),
    ).read_dir(MissionArtifactKind.PRIMARY_METADATA)
    if primary_candidate.exists():
        return primary_candidate

    from specify_cli.context.mission_resolver import (
        AmbiguousHandleError,
        MissionNotFoundError,
        resolve_mission,
    )

    try:
        resolved = resolve_mission(feature, effective_root or repo_root)
    except (AmbiguousHandleError, MissionNotFoundError):
        return read_dir
    resolved_primary: Path = resolved.feature_dir
    if resolved_primary.exists():
        return resolved_primary
    return read_dir


def _validate_wp_readiness(
    expected_wp_ids: list[str],
    snapshot_wps: dict[str, dict[str, Any]],
    events_path: Path,
    activity_issues: list[str],
) -> None:
    """WPs must be at an acceptable ending for acceptance (FR-005).

    Routed through the single :func:`~specify_cli.status_lanes.is_acceptable_ending`
    authority: ``approved``/``done`` unconditionally, plus a ``canceled`` WP that
    carries operator-authored provenance (read from this same coord-surface
    snapshot via the shared :func:`~specify_cli.status_lanes.has_operator_provenance`
    accessor). A synthetic cancellation or any non-terminal lane still produces
    an activity issue here (FR-003/FR-006); its FR-003-specific "operator-authored
    cancellation provenance required" diagnostic is surfaced by
    :meth:`AcceptanceSummary.outstanding`'s lane blockers.
    """
    if not (events_path.exists() and snapshot_wps):
        return
    for wp_id in expected_wp_ids:
        wp_snapshot = snapshot_wps.get(wp_id)
        if wp_snapshot is None:
            activity_issues.append(f"{wp_id}: no canonical state found in status.events.jsonl")
            continue
        lane = wp_snapshot.get("lane")
        if not is_acceptable_ending(str(lane), has_provenance=has_operator_provenance(wp_snapshot)):
            activity_issues.append(f"{wp_id}: canonical lane is '{lane}', expected 'approved' or 'done'")


def _target_branch_for_feature(feature_dir: Path) -> str | None:
    """Thin adapter over the single ``target_branch`` read authority (FR-008 / #2139)."""
    # str(...) narrows the cross-module Any mypy sees under this repo's
    # `follow_imports = "skip"` override for specify_cli.* (pyproject.toml);
    # value is already str | None here (the authority's real contract),
    # mirroring the same cast pattern in core/paths.py:723.
    value = read_target_branch_from_meta(feature_dir)
    return str(value) if value is not None else None


def collect_feature_summary(
    repo_root: Path,
    feature: str,
    *,
    strict_metadata: bool = True,
    mutate_matrix: bool = True,
    effective_root: Path | None = None,
) -> AcceptanceSummary:
    # WP09/FR-001 (kind-correct): ``_primary_anchor_feature_dir`` only needs
    # the coord-aware existence/identity read described in its own docstring
    # ("identity/existence was already validated by the read resolution") —
    # the ``PRIMARY_METADATA`` home, not a specific artifact's content.
    from mission_runtime import MissionArtifactKind, placement_seam

    scope = effective_root_kwargs(effective_root)
    read_feature_dir = placement_seam(repo_root, feature, **scope).read_dir(MissionArtifactKind.PRIMARY_METADATA)
    feature_dir = _primary_anchor_feature_dir(repo_root, feature, read_feature_dir, **scope)
    tasks_dir = feature_dir / "tasks"
    if not feature_dir.exists():
        raise AcceptanceError(f"Mission directory not found: {feature_dir}")

    # #1057 / squad Blocker 1: hard-reject a pre-3.0 lane-directory mission BEFORE
    # building the summary. WP tasks are a PRIMARY-partition kind, so they live on
    # the primary anchor dir; the legacy detector reads ``tasks/{lane}/`` there.
    # Without this guard the retired legacy reader degraded into an empty WP set →
    # vacuously ``all_done`` → ``accept`` auto-committed an unmigrated mission. The
    # raised ``Pre30LayoutError`` carries the ``spec-kitty upgrade`` instruction and
    # is surfaced as exit 1 by every acceptance/verify entrypoint.
    check_pre30_layout(feature_dir)

    branch, worktree_root, primary_repo_root, git_dirty_raw = _resolve_git_context(repo_root)

    status_feature_dir = _status_read_feature_dir(repo_root, feature, feature_dir, **scope)
    git_dirty = _accept_dirty_gate(
        git_dirty_raw,
        repo_root=repo_root,
        feature=feature,
        **scope,
    )

    lanes: dict[str, list[str]] = {lane: [] for lane in LANES}
    work_packages: list[WorkPackageState] = []
    metadata_issues: list[str] = []
    activity_issues: list[str] = []
    skipped_checks: list[AcceptanceCheckDiagnostic] = []
    blocked_checks: list[AcceptanceCheckDiagnostic] = []

    snapshot_wps = _collect_snapshot_wps(feature, status_feature_dir, activity_issues)

    # #2122: PRIMARY-partition reads (WP tasks/, planning artifacts) must key on
    # the canonical PRIMARY slug, not the raw handle. A mid8/ULID/numeric handle
    # passed straight to the kind-aware seam composes a nonexistent
    # `kitty-specs/<handle>` dir. `feature_dir` is the already-resolved primary
    # anchor, so its name is the canonical primary slug (which can legitimately
    # differ from the coord read-dir name for backfilled legacy missions).
    # STATUS reads above/below stay coord-aware on the raw `feature` (C-002).
    primary_slug = feature_dir.name

    expected_wp_ids: list[str] = []
    canceled_wps: list[dict[str, str]] = []
    for wp in _iter_work_packages(repo_root, primary_slug, **scope):
        wp_id = wp.work_package_id or wp.path.stem
        expected_wp_ids.append(wp_id)

        wp_snapshot = snapshot_wps.get(wp_id)
        state, wp_metadata_issues = build_work_package_state(
            wp,
            wp_id,
            wp_snapshot,
            repo_root=repo_root,
            strict_metadata=strict_metadata,
        )
        bucket_lane = state.lane
        if bucket_lane in lanes:
            lanes[bucket_lane].append(wp_id)
        else:
            lanes["planned"].append(wp_id)
        metadata_issues.extend(wp_metadata_issues)
        work_packages.append(state)

        # FR-002/NFR-003: an operator-canceled WP is reported separately (the
        # provenance/reason/actor/at read from the coord-surface snapshot that
        # ``status_feature_dir`` already resolves), decided per-WP at the
        # bucketing seam — the provenance-free lane bucket cannot carry it.
        canceled_entry = build_canceled_wp_report(wp_id, wp_snapshot)
        if canceled_entry is not None:
            canceled_wps.append(canceled_entry)

    _validate_wp_readiness(expected_wp_ids, snapshot_wps, status_feature_dir / EVENTS_FILENAME, activity_issues)

    # Provenance-aware terminality for the FR-009 unchecked-task normalization
    # (T007): the lane-only view cannot see whether a ``canceled`` WP is
    # operator-authored, so decide it here from the per-WP data and thread the
    # authoritative flag into ``_normalized_unchecked_tasks``. Mirrors the
    # ``_all_work_packages_terminal`` "no tracked WP → not terminal" guard.
    all_packages_acceptable = bool(work_packages) and all(
        is_acceptable_ending(state.lane, has_provenance=state.has_operator_provenance)
        for state in work_packages
    )

    # FR-002 (#2085): PLANNING reads (spec/plan/tasks/research/data-model/quickstart)
    # resolve the PRIMARY surface via the WP01 kind-aware seam; the STATUS reads above
    # (status.events.jsonl) and below (acceptance-matrix via _check_lane_gates) stay on
    # the coord-aware status_feature_dir (C-002). The single status_feature_dir variable
    # is split per-partition WITHOUT renaming it (additive: a new planning_read_dir).
    planning_read_dir = _planning_read_dir(repo_root, primary_slug, **scope)

    unchecked_tasks = _find_unchecked_tasks(planning_read_dir / _tasks_file())
    needs_clarification = _check_needs_clarification(
        [
            planning_read_dir / "spec.md",
            planning_read_dir / "plan.md",
            planning_read_dir / "quickstart.md",
            planning_read_dir / _tasks_file(),
            planning_read_dir / "research.md",
            planning_read_dir / "data-model.md",
        ]
    )
    try:
        mission = get_mission_for_feature(feature_dir)
    except MissionError:
        mission = None

    # #3785 T012: the mission is fetched BEFORE _missing_artifacts so the optional
    # set is derived from the mission's declared artifacts.optional (SSOT, FR-006)
    # instead of a drifted hardcoded list. Nothing between depended on the old order.
    missing_required, missing_optional = _missing_artifacts(planning_read_dir, mission)

    path_violations, path_convention_warning, dedup_tokens = evaluate_path_conventions(
        mission,
        repo_root,
        feature_dir,
        planning_read_dir,
        strict_metadata=strict_metadata,
        candidate_source_roots=_approved_lane_source_roots(repo_root, feature_dir, lanes),
    )
    if dedup_tokens:
        # FR-002: apply the dedup query result explicitly — evaluate_path_conventions
        # is a pure query and never mutates our list itself (summary_core.py).
        missing_optional = [entry for entry in missing_optional if normalize_path_token(entry) not in dedup_tokens]

    warnings = build_warnings(
        missing_optional=missing_optional,
        path_violations=path_violations,
        path_convention_warning=path_convention_warning,
    )

    # read-side-seam-primary-primitive-closure-01KYKMMT WP05/FR-015 (#2824
    # residual — the functional defect was already fixed in 6923d1d40; only
    # this comment was stale): ``read_feature_dir`` is the PRIMARY_METADATA
    # seam read (line 923 above) — it resolves the topology-blind PRIMARY dir
    # for EVERY topology, never the coordination worktree. ``lanes.json``
    # (``LANE_STATE``) is itself a PRIMARY-partition kind (C-001 — it travels
    # with tasks.md), so reading it off this PRIMARY anchor is correct, not a
    # husk risk. ``acceptance-matrix.json`` (``ACCEPTANCE_MATRIX``) is a
    # COORD-partition kind and is NOT read from this ``feature_dir`` argument
    # at all: ``_check_lane_gates`` -> ``_evaluate_acceptance_matrix`` resolves
    # its own coord-aware surface internally (``_acceptance_matrix_read_dir``,
    # gates_core.py), independent of the PRIMARY dir passed here.
    _check_lane_gates(
        repo_root,
        read_feature_dir,
        branch,
        activity_issues,
        skipped_checks,
        blocked_checks,
        mutate_matrix=mutate_matrix,
        **scope,
    )
    normalized_unchecked_tasks = _normalized_unchecked_tasks(
        unchecked_tasks, lanes, all_packages_acceptable=all_packages_acceptable
    )
    recommended_fix_order = _build_recommended_fix_order(
        lanes=lanes,
        metadata_issues=metadata_issues,
        activity_issues=activity_issues,
        unchecked_tasks=normalized_unchecked_tasks,
        needs_clarification=needs_clarification,
        missing_artifacts=missing_required,
        git_dirty=git_dirty,
        path_violations=path_violations,
        blocked_checks=blocked_checks,
    )

    return AcceptanceSummary(
        feature=feature,
        repo_root=repo_root,
        feature_dir=feature_dir,
        tasks_dir=tasks_dir,
        branch=branch,
        worktree_root=worktree_root,
        primary_repo_root=primary_repo_root,
        lanes=lanes,
        work_packages=work_packages,
        metadata_issues=metadata_issues,
        activity_issues=activity_issues,
        unchecked_tasks=normalized_unchecked_tasks,
        needs_clarification=needs_clarification,
        missing_artifacts=missing_required,
        optional_missing=missing_optional,
        git_dirty=git_dirty,
        path_violations=path_violations,
        warnings=warnings,
        skipped_checks=skipped_checks,
        blocked_checks=blocked_checks,
        recommended_fix_order=recommended_fix_order,
        canceled_wps=canceled_wps,
    )


def choose_mode(preference: str | None, repo_root: Path) -> AcceptanceMode:
    if preference in {"pr", "local", "checklist"}:
        return preference
    try:
        remotes = run_git(["remote"], cwd=repo_root, check=False).stdout.strip().splitlines()
        if remotes:
            return "pr"
    except TaskCliError:
        pass
    return "local"


def resolve_acceptance_actor(actor: str | None) -> str:
    return (actor or os.getenv("USER") or os.getenv("USERNAME") or "system").strip()


def acceptance_lane_derivations(summary: AcceptanceSummary) -> dict[str, list[str]]:
    approved_wps = list(summary.lanes.get("approved", []))
    done_wps = list(summary.lanes.get("done", []))
    return {
        "accepted_wps": [*approved_wps, *done_wps],
        "approved_wps": approved_wps,
        "done_wps": done_wps,
        "merge_pending_wps": approved_wps,
    }


_WELL_KNOWN_INTEGRATION_BRANCHES = frozenset({"main", "master", "develop", "development", "2.x", "3.x"})


def _commit_acceptance_meta(
    summary: AcceptanceSummary,
    actor_name: str,
    mode: AcceptanceMode,
) -> tuple[str | None, str | None, bool]:
    """Record acceptance in meta.json and commit; return (parent_commit, accept_commit, commit_created).

    T016 / WP04 / FR-001 / FR-003 / FR-009: the former
    ``assert_not_protected_branch → raise`` deadlock is removed.  Protection
    provenance flows through ``ProtectionPolicy.resolve`` (FR-007 / SF-2).

    When HEAD is on an UNPROTECTED branch (the normal mission-lane path):
    commits go directly to that branch, preserving existing behaviour.

    When HEAD is on a PROTECTED branch (e.g. ``main``, direct-repo solo-fork
    operator): commits are routed through ``commit_for_mission`` which
    materialises the coordination worktree on demand (C-001 / FR-003).
    """
    from specify_cli.core.git_ops import get_current_branch
    from specify_cli.git.protection_policy import ProtectionPolicy

    repo_root = summary.repo_root
    mission_slug = summary.feature
    policy = ProtectionPolicy.resolve(repo_root)
    current_branch = get_current_branch(repo_root)
    on_protected_primary = current_branch is not None and policy.is_protected(current_branch)

    try:
        parent_commit: str | None = run_git(["rev-parse", "HEAD"], cwd=repo_root, check=False).stdout.strip() or None
    except TaskCliError:
        parent_commit = None

    record_acceptance(summary.feature_dir, accepted_by=actor_name, mode=mode, from_commit=parent_commit, accept_commit=None)

    meta_path = summary.feature_dir / "meta.json"
    meta_rel = str(meta_path.relative_to(repo_root))

    if on_protected_primary:
        # Protected primary: route through commit_for_mission so the coord
        # worktree is materialised on demand (C-001 / FR-003).
        return _commit_acceptance_meta_via_router(
            repo_root=repo_root,
            mission_slug=mission_slug,
            meta_path=meta_path,
            policy=policy,
            parent_commit=parent_commit,
        )

    # Unprotected path (mission-lane branch): commit directly to current branch.
    run_git(["add", meta_rel], cwd=repo_root, check=True)

    # Scope the staged-check and commit to meta.json. A bare ``git commit`` would
    # sweep in any unrelated files the operator had pre-staged before running
    # ``accept``; the explicit ``-- <meta>`` pathspec commits only the
    # acceptance metadata and leaves the operator's staged work untouched.
    status = run_git(["diff", "--cached", "--name-only", "--", meta_rel], cwd=repo_root, check=True)
    staged_files = [line.strip() for line in status.stdout.splitlines() if line.strip()]
    if not staged_files:
        return parent_commit, None, False

    run_git(["commit", "-m", f"Accept {mission_slug}", "--", meta_rel], cwd=repo_root, check=True)
    try:
        accept_commit: str | None = run_git(["rev-parse", "HEAD"], cwd=repo_root, check=True).stdout.strip()
    except TaskCliError:
        accept_commit = None

    if accept_commit:
        # FR-007 route: ``route-unwrapped`` census site -- corruption surfaces
        # as the typed ``MissionMetaReadError`` and PROPAGATES (swallowing it
        # would silently skip stamping ``accept_commit`` into meta.json).
        _meta = load_meta_fail_closed(summary.feature_dir)
        if _meta is not None:
            _meta["accept_commit"] = accept_commit
            _history = _meta.get("acceptance_history", [])
            if _history:
                _history[-1]["accept_commit"] = accept_commit
            write_meta(summary.feature_dir, _meta)
            run_git(["add", meta_rel], cwd=repo_root, check=True)
            commit_status = run_git(["diff", "--cached", "--name-only", "--", meta_rel], cwd=repo_root, check=True)
            commit_staged_files = [line.strip() for line in commit_status.stdout.splitlines() if line.strip()]
            if commit_staged_files:
                run_git(
                    ["commit", "-m", f"Record acceptance commit for {mission_slug}", "--", meta_rel],
                    cwd=repo_root,
                    check=True,
                )

    return parent_commit, accept_commit, True


def _commit_acceptance_meta_via_router(
    *,
    repo_root: Path,
    mission_slug: str,
    meta_path: Path,
    policy: Any,
    parent_commit: str | None,
) -> tuple[str | None, str | None, bool]:
    """Route acceptance commit through ``commit_for_mission`` on a protected primary.

    Called by :func:`_commit_acceptance_meta` when HEAD is on a protected branch.
    ``commit_for_mission`` handles coord-worktree materialisation (C-001).
    Extracted to keep ``_commit_acceptance_meta`` complexity within the C901 ceiling.

    ``policy`` accepts any object satisfying the ``_ProtectionPolicyProtocol``
    structural protocol in ``commit_router`` (duck-typed; always a ``ProtectionPolicy``
    instance at runtime — using ``Any`` avoids a cross-module Protocol import).
    """
    from mission_runtime import MissionArtifactKind
    from specify_cli.coordination.commit_router import commit_for_mission

    router_result = commit_for_mission(
        repo_root=repo_root,
        mission_slug=mission_slug,
        files=(meta_path,),
        message=f"Accept {mission_slug}",
        policy=policy,
        # meta.json is PRIMARY_METADATA (write-surface-coherence WP02 / T009):
        # acceptance meta moves to the primary surface on the WRITE side too,
        # realizing the INV-5 read↔write symmetry. Primary kind → primary target.
        kind=MissionArtifactKind.PRIMARY_METADATA,
    )

    if router_result.status == "unchanged":
        return parent_commit, None, False

    if router_result.status not in ("committed",):
        raise AcceptanceError(f"Acceptance commit failed ({router_result.status}): " + (router_result.diagnostic or "no diagnostic available"))

    accept_commit: str | None = router_result.commit_hash

    if accept_commit:
        # FR-007 route: ``route-unwrapped`` census site -- see the sibling
        # ``_commit_acceptance_meta``; the typed error PROPAGATES.
        _meta = load_meta_fail_closed(meta_path.parent)
        if _meta is not None:
            _meta["accept_commit"] = accept_commit
            _history = _meta.get("acceptance_history", [])
            if _history:
                _history[-1]["accept_commit"] = accept_commit
            write_meta(meta_path.parent, _meta)
            # Second commit: record the accept_commit SHA back into meta.json.
            commit_for_mission(
                repo_root=repo_root,
                mission_slug=mission_slug,
                files=(meta_path,),
                message=f"Record acceptance commit for {mission_slug}",
                policy=policy,
                # meta.json → PRIMARY_METADATA (write-surface-coherence WP02 / T009).
                kind=MissionArtifactKind.PRIMARY_METADATA,
            )

    return parent_commit, accept_commit, True


def _build_acceptance_instructions(
    summary: AcceptanceSummary,
    mode: AcceptanceMode,
    branch: str,
    is_integration_branch: bool,
) -> tuple[list[str], list[str]]:
    """Build human-readable next-step and cleanup instruction lists."""
    instructions: list[str] = []
    cleanup_instructions: list[str] = []

    if mode == "pr":
        if is_integration_branch:
            instructions.append(f"Acceptance recorded on integration branch `{branch}`. Push and open a pull request if needed.")
        else:
            instructions.extend(
                [
                    f"Review the acceptance commit on branch `{branch}`.",
                    f"Run the mission merge when ready: `spec-kitty merge --mission {summary.feature}`",
                    "After merge, run /spec-kitty-mission-review and the retrospective workflow.",
                ]
            )
    elif mode == "local":
        if is_integration_branch:
            instructions.append(f"Acceptance recorded directly on `{branch}`. No merge needed.")
        else:
            instructions.extend(
                [
                    f"Acceptance passed. Run the mission merge: `spec-kitty merge --mission {summary.feature}`",
                    "After merge, run /spec-kitty-mission-review and the retrospective workflow.",
                ]
            )
    else:  # checklist
        instructions.append(f"All checks passed. Recommended next step: `spec-kitty merge --mission {summary.feature}`.")

    if summary.worktree_root != summary.primary_repo_root:
        cleanup_instructions.append(f"After merging, remove the worktree: `git worktree remove {summary.worktree_root}`")
    if not is_integration_branch:
        cleanup_instructions.append(f"Delete the feature branch when done: `git branch -d {branch}`")

    return instructions, cleanup_instructions


def perform_acceptance(
    summary: AcceptanceSummary,
    *,
    mode: AcceptanceMode,
    actor: str | None,
    tests: Sequence[str] | None = None,
    auto_commit: bool | None = None,
) -> AcceptanceResult:
    if auto_commit is None:
        auto_commit = get_auto_commit_default(summary.repo_root)

    if mode != "checklist" and not summary.ok:
        raise AcceptanceError("Acceptance checks failed; run verify to see outstanding issues.")

    actor_name = resolve_acceptance_actor(actor)
    timestamp = now_utc_stamp()

    parent_commit: str | None = None
    accept_commit: str | None = None
    commit_created = False

    if auto_commit and mode != "checklist":
        parent_commit, accept_commit, commit_created = _commit_acceptance_meta(summary, actor_name, mode)

    branch = summary.branch or summary.feature
    # FR-008 / #2139: delegate to the single target_branch read authority
    # (via the local thin adapter) instead of re-embedding a raw
    # ``load_meta(...).get("target_branch")`` extraction here.
    _target_branch = _target_branch_for_feature(summary.feature_dir)
    is_integration_branch = branch == _target_branch or (_target_branch is None and branch in _WELL_KNOWN_INTEGRATION_BRANCHES)

    instructions, cleanup_instructions = _build_acceptance_instructions(summary, mode, branch, is_integration_branch)

    notes: list[str] = []
    if accept_commit:
        notes.append(f"Acceptance commit: {accept_commit}")
    if parent_commit:
        notes.append(f"Accepted from parent commit: {parent_commit}")
    if tests:
        notes.append("Validation commands:")
        notes.extend(f"  - {cmd}" for cmd in tests)

    lane_derivations = acceptance_lane_derivations(summary)

    return AcceptanceResult(
        summary=summary,
        mode=mode,
        accepted_at=timestamp,
        accepted_by=actor_name,
        parent_commit=parent_commit,
        accept_commit=accept_commit,
        commit_created=commit_created,
        instructions=instructions,
        cleanup_instructions=cleanup_instructions,
        notes=notes,
        accepted_wps=lane_derivations["accepted_wps"],
        approved_wps=lane_derivations["approved_wps"],
        done_wps=lane_derivations["done_wps"],
        merge_pending_wps=lane_derivations["merge_pending_wps"],
        canceled_wps=summary.canceled_wps,
    )


__all__ = [
    "ACCEPTANCE_HISTORY_FIELD",
    "ACCEPTANCE_PROVENANCE_FIELDS",
    "AcceptanceError",
    "AcceptanceMode",
    "AcceptanceResult",
    "AcceptanceSummary",
    "acceptance_lane_derivations",
    "ArtifactEncodingError",
    "WorkPackageState",
    "choose_mode",
    "collect_feature_summary",
    "normalize_feature_encoding",
    "perform_acceptance",
    "resolve_acceptance_actor",
]
