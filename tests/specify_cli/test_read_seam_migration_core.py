"""WP07 (FR-002 / NFR-002) -- behaviour-preservation + fail-loud proofs for the
core/context/workspace/plan/misc read-side seam migration cluster.

Per ``docs/development/read-side-seam-classification.md`` (S:WP07), every
migrated call site in this cluster swaps the kind-blind
``resolve_planning_read_dir`` / ``candidate_feature_dir_for_mission`` for the
kind-aware ``mission_runtime.placement_seam(...).read_dir(kind)`` seam. For a
PRIMARY-partition kind (``WORK_PACKAGE_TASK``, ``LANE_STATE``,
``PRIMARY_METADATA``, ``SPEC``) this is a *behavior-neutral* swap: both
resolvers land on the identical topology-blind primary directory --
``LANE_STATE`` and ``WORK_PACKAGE_TASK`` are members of
``mission_runtime.artifacts._PRIMARY_ARTIFACT_KINDS``, so they NEVER trigger
the seam's coord-deleted fail-loud branch, regardless of topology. The ONE
observable behavior change in this cluster is for the single genuinely
COORD-partition kind migrated here -- ``STATUS_STATE``
(``charter_pack_synthesizer/apply.py``) -- whose declared ``coordination_branch``
may have been deleted from git with no coord worktree materialized: the old
lenient resolver silently substituted the PRIMARY checkout; the seam now
raises :class:`~specify_cli.coordination.surface_resolver
.CoordinationBranchDeleted` (NFR-002).

This module pins three classes of proof:

1. **Fail-loud proof** -- the seam raises on a deleted-coord mismatch for the
   one genuinely coord-partition site in this cluster:
   ``charter_pack_synthesizer.apply``'s STATUS_STATE feature-dir helper.
   Red-first: before WP07 this called the lenient
   ``resolve_planning_read_dir``, which never raises on a deleted coord
   branch -- it silently substitutes primary.
2. **Discriminating negative** -- a PRIMARY-partition-kind call site
   (``core.worktree_topology.materialize_worktree_topology``, LANE_STATE)
   does NOT raise on the same deleted-coord mission, proving the fail-loud
   behavior is correctly scoped to coord-partition kinds only.
3. **Healthy-path parity proofs** -- representative PRIMARY-partition-kind
   call sites across the cluster resolve the SAME primary directory as
   before the migration, for a plain (non-coord) mission. Reuses the shared
   ``flat_topology_mission`` fixture (``tests/integration
   /coord_topology_fixture.py``) rather than re-deriving mission-fixture
   shape.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted
from tests.integration.coord_topology_fixture import (
    FlatTopologyContext,
    _git,
    _make_git_repo,
    _status_event_line,
    _write_lanes_json,
    _write_meta,
    _write_wp_task,
)

# ``flat_topology_mission`` itself is injected via ``tests/specify_cli
# /conftest.py`` (parameter-name fixture resolution) -- not imported directly
# here, so a test parameter named ``flat_topology_mission`` does not shadow a
# module-level import (mirrors ``tests/acceptance/conftest.py``'s rationale).

pytestmark = [pytest.mark.fast, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Fail-loud fixture: a mission that declares a coordination_branch that was
# never created in git, and has no coord worktree materialized on disk.
# Mirrors tests/specify_cli/retrospective/test_load_traces_deleted_coord.py's
# proven-correct ``_build_coord_deleted_mission`` shape.
# ---------------------------------------------------------------------------

_DELETED_COORD_MISSION_ID = "01KW7SEAMDELETEDCOORD0WP07"[:26]
_DELETED_COORD_MID8 = _DELETED_COORD_MISSION_ID[:8]
_DELETED_COORD_HUMAN_SLUG = "seam-deleted-coord-wp07"
_DELETED_COORD_SLUG = f"{_DELETED_COORD_HUMAN_SLUG}-{_DELETED_COORD_MID8}"
_DELETED_COORD_BRANCH = f"kitty/mission-{_DELETED_COORD_SLUG}"


def _build_deleted_coord_mission(tmp_path: Path) -> Path:
    """Real git repo: mission declares a coord branch that was never created.

    ``meta.json`` records ``coordination_branch`` while the branch is absent
    from git and no coord worktree exists on disk -- the canonical
    coord-deleted (R3) shape shared with
    ``tests/status/test_aggregate_coord_deleted_contract.py`` and
    ``tests/specify_cli/retrospective/test_load_traces_deleted_coord.py``.
    """
    repo = _make_git_repo(tmp_path / "deleted-coord")
    feature_dir = repo / "kitty-specs" / _DELETED_COORD_SLUG
    feature_dir.mkdir(parents=True)
    _write_meta(
        feature_dir,
        slug=_DELETED_COORD_SLUG,
        mission_id=_DELETED_COORD_MISSION_ID,
        topology="coord",
        coordination_branch=_DELETED_COORD_BRANCH,
    )
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir()
    _write_wp_task(tasks_dir, "WP01")
    _write_lanes_json(feature_dir, slug=_DELETED_COORD_SLUG, mission_id=_DELETED_COORD_MISSION_ID)
    (feature_dir / "status.events.jsonl").write_text(
        _status_event_line(_DELETED_COORD_SLUG, "WP01", marker="PRIMARY_DECOY") + "\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "feat: mission with deleted coord branch")
    return repo


# ---------------------------------------------------------------------------
# 1. Fail-loud proofs (NFR-002)
# ---------------------------------------------------------------------------


def test_charter_pack_synthesizer_feature_dir_raises_on_deleted_coord(
    tmp_path: Path,
) -> None:
    """``charter_pack_synthesizer.apply._feature_dir`` (STATUS_STATE) fails loud.

    Before WP07 this helper called the lenient ``resolve_planning_read_dir``,
    which silently substituted the PRIMARY checkout when the declared
    ``coordination_branch`` no longer exists in git. Post-WP07 it routes
    through ``placement_seam(...).read_dir(STATUS_STATE)``, which raises
    ``CoordinationBranchDeleted`` instead (NFR-002 fail-loud read authority).
    """
    from specify_cli.charter_pack_synthesizer.apply import _feature_dir

    repo = _build_deleted_coord_mission(tmp_path)

    with pytest.raises(CoordinationBranchDeleted):
        _feature_dir(repo, _DELETED_COORD_SLUG)


def test_lane_state_reads_unaffected_by_deleted_coord(tmp_path: Path) -> None:
    """LANE_STATE stays PRIMARY-partition even on a deleted-coord mission.

    Unlike ``STATUS_STATE`` (genuinely COORD-partition), ``LANE_STATE`` is a
    member of ``mission_runtime.artifacts._PRIMARY_ARTIFACT_KINDS`` (lanes.json
    travels with tasks.md -- data-model.md), so the seam resolves it
    topology-blind to the primary checkout for EVERY topology shape,
    including a mission whose declared ``coordination_branch`` no longer
    exists in git. This is the discriminating negative to the STATUS_STATE
    fail-loud proof above: it pins that the WP07 migration's fail-loud
    behavior is correctly scoped to genuinely coord-partition kinds only --
    ``core.worktree_topology.materialize_worktree_topology`` (one of the
    LANE_STATE call sites migrated in this cluster) must NOT raise here.
    """
    from specify_cli.core.worktree_topology import materialize_worktree_topology

    repo = _build_deleted_coord_mission(tmp_path)

    topology = materialize_worktree_topology(repo, _DELETED_COORD_SLUG)

    assert topology.target_branch == "main"
    wp_ids = [entry.wp_id for entry in topology.entries]
    # Fixture (_build_deleted_coord_mission) writes exactly one WP01 task --
    # assert the exact resolved set, not mere membership (a topology that
    # picked up stray/duplicate entries from a wrong-leg read would still
    # satisfy "WP01" in wp_ids).
    assert wp_ids == ["WP01"]


# ---------------------------------------------------------------------------
# 2. Healthy-path parity proofs (behavior-neutral for PRIMARY-partition kinds)
# ---------------------------------------------------------------------------


def test_seam_parity_worktree_topology_materialize_resolves_primary(
    flat_topology_mission: FlatTopologyContext,
) -> None:
    """``core.worktree_topology.materialize_worktree_topology`` (LANE_STATE).

    A flat (non-coord) mission must still resolve its identity/lanes/tasks
    from the primary checkout after the WP07 seam swap -- unchanged from the
    pre-migration ``resolve_planning_read_dir`` behavior for a PRIMARY-
    partition kind.
    """
    from specify_cli.core.worktree_topology import materialize_worktree_topology

    ctx = flat_topology_mission
    topology = materialize_worktree_topology(ctx.repo, ctx.slug)

    assert topology.target_branch == "main"
    wp_ids = [entry.wp_id for entry in topology.entries]
    # flat_topology_mission fixture writes exactly one WP01 task -- assert the
    # exact resolved set, not mere membership (a topology that picked up
    # stray/duplicate entries from a wrong-leg read would still satisfy
    # "WP01" in wp_ids).
    assert wp_ids == ["WP01"]


def test_seam_parity_resolve_feature_worktree_resolves_lanes_on_flat_topology(
    flat_topology_mission: FlatTopologyContext,
) -> None:
    """``workspace.context.resolve_feature_worktree`` (LANE_STATE), flat mission.

    The fixture's ``lanes.json`` (written by ``_write_lanes_json``) declares a
    single ``lane-a`` lane. Materializing the on-disk lane worktree at the
    exact path ``lanes/branch_naming.worktree_path`` computes proves the
    LANE_STATE read resolved the PRIMARY ``lanes.json`` (not a stub/no-op)
    without raising (the migration's fail-loud branch is NOT triggered on a
    healthy, non-coord topology): a bare ``return None`` stub would fail this
    assertion, unlike the previous ``is None`` check it replaces.
    """
    from specify_cli.lanes.branch_naming import worktree_path as _seam_worktree_path
    from specify_cli.workspace.context import resolve_feature_worktree

    ctx = flat_topology_mission
    expected_lane_worktree = _seam_worktree_path(ctx.repo, ctx.slug, lane_id="lane-a")
    expected_lane_worktree.mkdir(parents=True)

    assert resolve_feature_worktree(ctx.repo, ctx.slug) == expected_lane_worktree


def test_seam_parity_task_utils_locate_work_package_resolves_primary(
    flat_topology_mission: FlatTopologyContext,
) -> None:
    """``task_utils.support.locate_work_package`` (WORK_PACKAGE_TASK)."""
    from specify_cli.task_utils.support import locate_work_package

    ctx = flat_topology_mission
    wp = locate_work_package(ctx.repo, ctx.slug, "WP01")

    assert wp.feature == ctx.slug
    assert wp.path == ctx.primary_feature_dir / "tasks" / "WP01.md"


def test_seam_parity_agent_tasks_ports_real_fs_reader_resolves_primary(
    flat_topology_mission: FlatTopologyContext,
) -> None:
    """``agent_tasks_ports.RealFsReader`` (WORK_PACKAGE_TASK, both methods)."""
    from mission_runtime import MissionArtifactKind
    from specify_cli.agent_tasks_ports import MissionHandle, RealFsReader

    ctx = flat_topology_mission
    handle = MissionHandle(repo_root=ctx.repo, mission_slug=ctx.slug)
    reader = RealFsReader()

    read_dir = reader.planning_read_dir(handle, kind=MissionArtifactKind.WORK_PACKAGE_TASK)
    assert read_dir == ctx.primary_feature_dir

    tasks_dir = reader.wp_tasks_dir(handle)
    assert tasks_dir == ctx.primary_feature_dir / "tasks"


def test_seam_parity_plan_interview_get_mission_id_resolves_primary(
    flat_topology_mission: FlatTopologyContext,
) -> None:
    """``missions.plan.plan_interview._get_mission_id`` (PRIMARY_METADATA)."""
    from specify_cli.missions.plan.plan_interview import (
        _get_mission_id as plan_get_mission_id,
    )

    ctx = flat_topology_mission
    assert plan_get_mission_id(ctx.repo, ctx.slug) == ctx.mission_id


def test_seam_parity_specify_interview_get_mission_id_resolves_primary(
    flat_topology_mission: FlatTopologyContext,
) -> None:
    """``missions.plan.specify_interview._get_mission_id`` (PRIMARY_METADATA).

    Near-duplicate module pair with ``plan_interview.py`` (same rationale,
    §WP07 of the ledger) -- pinned separately so a divergence between the two
    copies is caught.
    """
    from specify_cli.missions.plan.specify_interview import (
        _get_mission_id as specify_get_mission_id,
    )

    ctx = flat_topology_mission
    assert specify_get_mission_id(ctx.repo, ctx.slug) == ctx.mission_id


# ``test_seam_parity_sync_events_resolve_mission_id_for_slug_resolves_primary``
# retired with its module: ``sync.events._resolve_mission_id_for_slug`` died with
# the sync transport (issue #5). The surviving PRIMARY_METADATA readers stay pinned
# by the two ``_get_mission_id`` tests above.


def test_seam_parity_charter_pack_synthesizer_feature_dir_resolves_primary_on_flat_topology(
    flat_topology_mission: FlatTopologyContext,
) -> None:
    """``charter_pack_synthesizer.apply._feature_dir`` (STATUS_STATE), healthy leg.

    The discriminating sibling of the fail-loud proof above: a flat (non-
    coord) mission has no coordination_branch at all, so the STATUS_STATE
    read resolves the primary checkout without raising.
    """
    from specify_cli.charter_pack_synthesizer.apply import _feature_dir

    ctx = flat_topology_mission
    assert _feature_dir(ctx.repo, ctx.slug) == ctx.primary_feature_dir


def test_seam_parity_mission_record_analysis_write_feature_dir_resolves_primary(
    flat_topology_mission: FlatTopologyContext,
) -> None:
    """``cli.commands.agent.mission_record_analysis``'s SPEC-kind read leg.

    #2102 / FR-009 (gate-read-surface-completion WP04) originally routed this
    onto ``resolve_planning_read_dir(kind=_kind_for_artifact('spec'))``; WP07
    swaps that for ``placement_seam(...).read_dir(...)``. SPEC is PRIMARY-
    partition, so the resolved dir is unchanged for a flat mission -- pinned
    directly against the seam + the same ``_kind_for_artifact`` helper the
    production call site uses (behavior-neutral dedup, no bespoke duplicate
    kind mapping introduced here).
    """
    from mission_runtime import placement_seam
    from specify_cli.cli.commands.agent.mission_feature_resolution import (
        _kind_for_artifact,
    )

    ctx = flat_topology_mission
    write_feature_dir = placement_seam(ctx.repo, ctx.slug).read_dir(_kind_for_artifact("spec"))
    assert write_feature_dir == ctx.primary_feature_dir
