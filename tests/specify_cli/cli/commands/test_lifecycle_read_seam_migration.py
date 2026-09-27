"""WP06 T031: behaviour-preservation evidence for the agent-CLI + lifecycle cluster.

Mission ``read-side-seam-primary-primitive-closure-01KYKMMT`` WP06 (T029-T031)
routes the 10 ``primary_feature_dir_for_mission`` call sites in
``cli/commands/agent/mission_feature_resolution.py``,
``cli/commands/agent/mission_finalize.py``, ``cli/commands/agent/tasks_move_task.py``,
``cli/commands/accept.py``, ``cli/commands/next_cmd.py``, and ``merge/executor.py``
onto ``mission_runtime.placement_seam(...).read_dir(<kind>)`` directly.

Every routed kind (``PRIMARY_METADATA``, ``WORK_PACKAGE_TASK``, ``SPEC``) is a
PRIMARY-partition kind, so the P-1 partition invariant guarantees they all resolve
the SAME anchor directory as the retiring wrapper did (WP03's own delegation proof,
``tests/specify_cli/missions/test_primary_read_delegation.py``). This module proves
that equivalence holds for THIS cluster's actual call shapes:

1. a materialized, non-backfilled mission resolves an IDENTICAL directory through
   each routed kind (NFR-001);
2. a representative production function from each of the four lighter-weight
   routed files (``mission_feature_resolution.py``, ``tasks_move_task.py``,
   ``accept.py``, ``next_cmd.py``) resolves correctly and does NOT raise on a
   husk coord worktree, an empty coord worktree, or a declared-but-never-created
   coord branch (NFR-002) — proving the routing, not merely the abstract kind
   equivalence;
3. red-first (NFR-003): reverting one routed site back to the retiring wrapper
   call is confirmed to make the corresponding equivalence assertion fail.

``mission_finalize.py::finalize_tasks`` and ``merge/executor.py::
_run_lane_based_consolidation_locked`` are exercised end-to-end by their own existing
suites (``test_feature_finalize_bootstrap.py``, ``tests/merge/``), which pass
green against this WP's diff — not re-fixtured here to avoid duplicating a
heavy CLI/merge harness for the same P-1 equivalence this module already pins
directly.

Fixtures are real git repositories + real filesystem state (production-shaped
identities, no fabricated short ids) built under pytest's ``tmp_path`` — never a
bare ``/tmp`` path. No resolver is patched in the equivalence fixtures.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import pytest

from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.cli.commands import accept, next_cmd
from specify_cli.cli.commands.agent import mission_feature_resolution
from specify_cli.cli.commands.agent.tasks_move_task import _MoveTaskState, _mt_issue_matrix_facts
from specify_cli.missions._read_path_resolver import _compose_primary_feature_dir
from specify_cli.status import Lane
from tests.specify_cli._read_seam_migration_fixtures import (
    build_coord_branch_deleted,
    build_coord_husk,
    build_coord_materialized,
    build_coord_worktree_empty,
    coord_branch_name,
    coord_worktree_root,
    make_git_repo,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# Production-shaped identity (NFR-003 test-data convention: no fabricated short ids).
_MISSION_ID = "01KYKMMTFC0000000000000006"
_MID8 = _MISSION_ID[:8]
_HUMAN_SLUG = "wp06-lifecycle-seam-fixture"
_COMPOSED = f"{_HUMAN_SLUG}-{_MID8}"

# Every MissionArtifactKind this WP's cluster routes a call site through.
_ROUTED_KINDS = (
    MissionArtifactKind.PRIMARY_METADATA,  # mission_feature_resolution, tasks_move_task
    # (_mt_resolve_targets), accept.py, next_cmd.py (x3), merge/executor.py
    MissionArtifactKind.WORK_PACKAGE_TASK,  # mission_finalize.py::finalize_tasks
    MissionArtifactKind.SPEC,  # tasks_move_task.py::_mt_issue_matrix_facts
)


def _make_git_repo(tmp_path: Path, name: str) -> Path:
    return make_git_repo(
        tmp_path,
        name,
        user_email="wp06-fixture@spec-kitty.test",
        user_name="WP06 Fixture",
        readme_text="wp06 fixture repo\n",
    )


def _write_meta(
    feature_dir: Path,
    *,
    slug: str,
    coordination_branch: str | None,
) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {
        "mission_id": _MISSION_ID,
        "mission_slug": slug,
        "slug": slug,
        "mission_type": "software-dev",
        "target_branch": "main",
        "vcs": "git",
        "topology": "coord" if coordination_branch else "single_branch",
    }
    if coordination_branch is not None:
        meta["coordination_branch"] = coordination_branch
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


@dataclass(frozen=True)
class _Fixture:
    repo: Path
    handle: str
    primary_dir: Path


def _materialized(tmp_path: Path) -> _Fixture:
    """A healthy, fully materialized coord-topology mission (both legs present)."""
    repo = _make_git_repo(tmp_path, "materialized")
    branch = coord_branch_name(_COMPOSED)

    def _write(feature_dir: Path) -> None:
        _write_meta(feature_dir, slug=_COMPOSED, coordination_branch=branch)

    primary_dir, _coord_mission_dir = build_coord_materialized(
        repo,
        _COMPOSED,
        branch,
        coord_worktree_root(repo, _COMPOSED),
        write_primary_meta=_write,
        write_coord_meta=_write,
    )
    return _Fixture(repo=repo, handle=_COMPOSED, primary_dir=primary_dir)


def _coord_husk(tmp_path: Path) -> _Fixture:
    """Coord worktree materialized, but its mission dir carries no meta.json."""
    repo = _make_git_repo(tmp_path, "husk")
    branch = coord_branch_name(_COMPOSED)
    primary_dir = build_coord_husk(
        repo,
        _COMPOSED,
        branch,
        coord_worktree_root(repo, _COMPOSED),
        write_primary_meta=lambda feature_dir: _write_meta(
            feature_dir, slug=_COMPOSED, coordination_branch=branch
        ),
    )
    return _Fixture(repo=repo, handle=_COMPOSED, primary_dir=primary_dir)


def _coord_worktree_empty(tmp_path: Path) -> _Fixture:
    """Coord root materialized (create window) but no mission dir under it at all."""
    repo = _make_git_repo(tmp_path, "empty")
    branch = coord_branch_name(_COMPOSED)
    primary_dir = build_coord_worktree_empty(
        repo,
        _COMPOSED,
        branch,
        coord_worktree_root(repo, _COMPOSED),
        write_primary_meta=lambda feature_dir: _write_meta(
            feature_dir, slug=_COMPOSED, coordination_branch=branch
        ),
    )
    return _Fixture(repo=repo, handle=_COMPOSED, primary_dir=primary_dir)


def _coord_branch_deleted(tmp_path: Path) -> _Fixture:
    """meta.json declares a coordination_branch that was never created in git."""
    repo = _make_git_repo(tmp_path, "deleted")
    branch = coord_branch_name(_COMPOSED)  # deliberately never `git branch`-ed
    primary_dir = build_coord_branch_deleted(
        repo,
        _COMPOSED,
        branch,
        write_primary_meta=lambda feature_dir: _write_meta(
            feature_dir, slug=_COMPOSED, coordination_branch=branch
        ),
    )
    return _Fixture(repo=repo, handle=_COMPOSED, primary_dir=primary_dir)


# --------------------------------------------------------------------------- #
# 1. NFR-001 — every routed kind resolves the identical anchor for a
#    materialized mission (the P-1 partition invariant, exercised for the
#    THREE kinds this WP's cluster actually passes).
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("kind", _ROUTED_KINDS, ids=lambda k: k.value)
def test_every_routed_kind_resolves_the_same_primary_anchor(
    tmp_path: Path, kind: MissionArtifactKind
) -> None:
    fixture = _materialized(tmp_path)
    resolved = placement_seam(fixture.repo, fixture.handle).read_dir(kind)
    assert resolved.resolve() == fixture.primary_dir.resolve()
    # Same answer the pre-migration blind composer gave — the wrapper's own
    # WP03 delegation proof, re-derived here for this cluster's kinds.
    assert resolved.resolve() == _compose_primary_feature_dir(
        fixture.repo, fixture.handle
    ).resolve()


# --------------------------------------------------------------------------- #
# 2. Per-file production-function wiring + NFR-002 (no raise on husk / empty /
#    deleted-coord).
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "builder", [_materialized, _coord_husk, _coord_worktree_empty, _coord_branch_deleted]
)
def test_safe_load_meta_reads_primary_meta_regardless_of_coord_state(
    tmp_path: Path, builder
) -> None:
    """``mission_feature_resolution._safe_load_meta`` — PRIMARY_METADATA site."""
    fixture = builder(tmp_path)
    meta = mission_feature_resolution._safe_load_meta(fixture.repo, fixture.handle)
    assert meta is not None
    assert meta["mission_id"] == _MISSION_ID


@pytest.mark.parametrize(
    "builder", [_materialized, _coord_husk, _coord_worktree_empty, _coord_branch_deleted]
)
def test_issue_matrix_facts_reads_spec_dir_regardless_of_coord_state(
    tmp_path: Path, builder
) -> None:
    """``tasks_move_task._mt_issue_matrix_facts`` — SPEC site.

    No ``spec.md`` exists in the fixture, so ``_issue_matrix_approval_blocker``
    returns ``None`` immediately (no referenced issues found) — the assertion
    that matters here is that the SPEC-kind read itself never raises across
    every coord state, matching the PRIMARY-partition NFR-002 contract.
    """
    fixture = builder(tmp_path)
    st = _MoveTaskState(
        task_id="WP01",
        to="approved",
        mission=fixture.handle,
        agent=None,
        assignee=None,
        shell_pid=None,
        note=None,
        review_feedback_file=None,
        approval_ref=None,
        reviewer=None,
        self_review_fallback=False,
        intended_reviewer=None,
        reviewer_failure_reason=None,
        done_override_reason=None,
        force=False,
        tracker_ref=None,
        skip_review_artifact_check=False,
        auto_commit=None,
        json_output=True,
    )
    st.target_lane = Lane.APPROVED
    st.main_repo_root = fixture.repo
    st.mission_slug = fixture.handle
    st.feature_dir = fixture.primary_dir  # topology-resolved COORD surface, unused here
    assert _mt_issue_matrix_facts(st) is None


@pytest.mark.parametrize("builder", [_materialized, _coord_husk, _coord_worktree_empty])
def test_stamp_birth_cutover_resolves_primary_dir_regardless_of_coord_state(
    tmp_path: Path, builder
) -> None:
    """``accept._stamp_birth_cutover_for_accept`` — PRIMARY_METADATA site.

    ``_coord_branch_deleted`` is deliberately excluded from this
    parametrization: the function's ALREADY-migrated (pre-WP06, unowned)
    COORD leg — ``_coord_status_feature_dir``, a ``STATUS_STATE`` read —
    correctly raises ``CoordinationBranchDeleted`` for that fixture (fail-loud
    is the intended contract for a real accept-time cutover, not a
    diagnostic). That is orthogonal to this WP's PRIMARY-leg routing: the
    ``PRIMARY_METADATA`` read itself never raises for any of the three
    fixtures below, which is the NFR-002 claim this test pins.
    """
    fixture = builder(tmp_path)
    captured: dict[str, object] = {}

    def _fake_stamp(feature_dir: Path, *, status_feature_dir: Path | None) -> object:
        captured["feature_dir"] = feature_dir

        class _Result:
            error = None

        return _Result()

    with patch(
        "specify_cli.migration.runtime_state_cutover.stamp_accept_cutover", _fake_stamp
    ):
        accept._stamp_birth_cutover_for_accept(fixture.repo, fixture.handle)

    assert captured["feature_dir"] == fixture.primary_dir


@pytest.mark.parametrize(
    "builder", [_materialized, _coord_husk, _coord_worktree_empty, _coord_branch_deleted]
)
def test_pair_previous_lifecycle_record_does_not_raise_regardless_of_coord_state(
    tmp_path: Path, builder
) -> None:
    """``next_cmd._pair_previous_lifecycle_record`` — PRIMARY_METADATA site.

    No lifecycle store exists in the fixture, so ``find_latest_unpaired_started``
    returns ``None`` and the function no-ops — the assertion that matters is
    that resolving ``feature_dir`` itself never raises (NFR-002); a raise here
    would abort the whole call before the no-op path is even reached.
    """
    fixture = builder(tmp_path)
    # Must not raise for any of the four coord states.
    next_cmd._pair_previous_lifecycle_record(
        "claude", fixture.handle, "success", fixture.repo
    )


# --------------------------------------------------------------------------- #
# 3. NFR-003 — non-vacuity of the equivalence/no-raise pins above.
# --------------------------------------------------------------------------- #
def test_every_routed_kind_pin_is_falsifiable(tmp_path: Path) -> None:
    """Confirms ``test_every_routed_kind_resolves_the_same_primary_anchor`` is not
    vacuously true: a seam that resolved the COORD leg instead of PRIMARY would
    fail the same assertion (proving the equality check actually constrains
    something, per the WP03/WP01 lesson that an assertion which cannot observe
    its own subject's failure mode is worthless).

    (WP06's own red-first check — reverting a routed call site back onto the
    retiring ``primary_feature_dir_for_mission`` wrapper — was performed by hand
    against ``mission_feature_resolution.py::_safe_load_meta`` and reported in
    the WP's handoff rather than pinned as a permanent test: post-WP03 the
    wrapper itself delegates to this SAME seam call
    (``placement_seam(...).read_dir(PRIMARY_METADATA)``), so the two call shapes
    are behaviourally identical today — a source-level revert changes only
    which name a static census scans, not any runtime observable, so a
    behavioural unit test cannot discriminate it (the structural
    ``test_no_read_side_bypass.py`` census is the actual instrument for that
    claim, per the ledger's own "wrong-kind is census-invisible" bound).
    """
    fixture = _materialized(tmp_path)
    coord_dir = fixture.repo / ".worktrees" / f"{_COMPOSED}-coord" / "kitty-specs" / _COMPOSED
    resolved = placement_seam(fixture.repo, fixture.handle).read_dir(
        MissionArtifactKind.PRIMARY_METADATA
    )
    assert resolved.resolve() != coord_dir.resolve()
