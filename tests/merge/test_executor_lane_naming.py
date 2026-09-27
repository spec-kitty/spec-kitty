"""Executor lane-naming tests: guard every executor stage against re-deriving a
lane's branch/worktree name from Mission identity instead of the CREATED name.

FR-001/FR-004/FR-005/FR-006/FR-012: every executor stage that names a lane's
branch or worktree must go through the lane's CREATED name
(:func:`~specify_cli.merge.executor._created_lane_branch` /
:func:`~specify_cli.merge.executor._created_lane_worktree`) — a Mission
identity (``mission_id`` / ``canonical_mission_id``) is never a naming input.
These tests build every mission through the real-allocator divergent-shape
fixtures (:mod:`tests.merge._divergent_shapes`) so a lane branch/worktree is
never a hand-composed literal.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import typer

from specify_cli.git.destructive_guard import DestructiveOpRefused
from specify_cli.lanes.branch_naming import lane_branch_name
from specify_cli.lanes.models import ExecutionLane
from specify_cli.merge import executor as ex
from specify_cli.merge.config import MergeStrategy
from specify_cli.merge.state import MergeState

from tests.merge._divergent_shapes import (
    DivergentMission,
    DivergentShapeBuilder,
    all_wp_ids,
    identity_injected_lane_branch,
    shape_backfilled_legacy,
    shape_invalid_identity_long,
    shape_invalid_identity_short,
    shape_mismatched_mid8,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]


# ---------------------------------------------------------------------------
# Shared harness
# ---------------------------------------------------------------------------


# _identity_injected_lane_branch / _all_wp_ids moved to the shared
# tests/merge/_divergent_shapes.py home (identity_injected_lane_branch /
# all_wp_ids) — this module and test_merge_divergent_end_to_end.py both
# consumed byte-identical copies of each.
_identity_injected_lane_branch = identity_injected_lane_branch
_all_wp_ids = all_wp_ids


def _state(mission: DivergentMission, **overrides: object) -> MergeState:
    state = MergeState(
        mission_id=mission.mission_id,
        mission_slug=mission.slug,
        target_branch=mission.manifest.target_branch,
        wp_order=_all_wp_ids(mission),
    )
    for key, value in overrides.items():
        setattr(state, key, value)
    return state


def _run(
    mission: DivergentMission,
    state: MergeState,
    *,
    is_resume: bool = False,
    excluded_canceled_wp_ids: frozenset[str] = frozenset(),
) -> ex._MergeRunState:
    return ex._MergeRunState(
        main_repo=mission.repo_root,
        mission_slug=mission.slug,
        canonical_id=mission.mission_id,
        canonical_mission_id=mission.mission_id,
        feature_dir=mission.feature_dir,
        target_feature_dir=mission.feature_dir,
        lanes_manifest=mission.manifest,
        all_wp_ids=_all_wp_ids(mission),
        push=False,
        delete_branch=True,
        remove_worktree=True,
        strategy=MergeStrategy.SQUASH,
        assume_yes=True,
        planning_artifact_only=False,
        state=state,
        is_resume=is_resume,
        excluded_canceled_wp_ids=excluded_canceled_wp_ids,
    )


def _rev_parse(repo: Path, ref: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", ref],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _branch_exists(repo: Path, branch: str) -> bool:
    return (
        subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
            capture_output=True,
            text=True,
        ).returncode
        == 0
    )


# ---------------------------------------------------------------------------
# Created-name helpers
# ---------------------------------------------------------------------------


def test_created_lane_branch_never_the_identity_form(tmp_path: Path) -> None:
    """The created branch is keyed on the manifest slug alone (I-1): it must
    equal ``lane_branch_name`` called WITHOUT a ``mission_id``, and must NOT
    equal the identity-form branch."""
    mission = shape_mismatched_mid8(tmp_path)
    created = ex._created_lane_branch(mission.manifest, "lane-a")
    expected = lane_branch_name(mission.manifest.mission_slug, "lane-a", planning_base_branch=mission.manifest.target_branch)
    assert created == expected
    identity_form = _identity_injected_lane_branch(mission.manifest.mission_slug, "lane-a", mission.manifest.mission_id)
    assert created != identity_form
    # The created form is exactly the branch the real allocator produced.
    _wt_path, allocator_branch = mission.lanes["lane-a"]
    assert created == allocator_branch


def test_created_lane_branch_lane_planning_returns_target_branch(tmp_path: Path) -> None:
    mission = shape_backfilled_legacy(tmp_path, with_planning_lane=True)
    assert ex._created_lane_branch(mission.manifest, "lane-planning") == mission.manifest.target_branch


def test_created_lane_worktree_matches_real_allocator_output(tmp_path: Path) -> None:
    mission = shape_mismatched_mid8(tmp_path)
    allocator_path, _branch = mission.lanes["lane-a"]
    actual = ex._created_lane_worktree(mission.repo_root, mission.manifest.mission_slug, "lane-a")
    assert actual == allocator_path


# ---------------------------------------------------------------------------
# _lane_fully_canceled — the shared FR-004/FR-009 predicate
# ---------------------------------------------------------------------------


def _lane(wp_ids: list[str]) -> ExecutionLane:
    return ExecutionLane(
        lane_id="lane-x",
        wp_ids=tuple(wp_ids),
        write_scope=(),
        predicted_surfaces=(),
        depends_on_lanes=(),
        parallel_group=0,
    )


def test_lane_fully_canceled_true_when_every_wp_excluded() -> None:
    lane = _lane(["WP01", "WP02"])
    assert ex._lane_fully_canceled(lane, frozenset({"WP01", "WP02"})) is True


def test_lane_fully_canceled_false_when_a_wp_survives() -> None:
    """A mixed lane (a survivor + a canceled WP) still integrates its
    survivor — never fully canceled."""
    lane = _lane(["WP01", "WP02"])
    assert ex._lane_fully_canceled(lane, frozenset({"WP01"})) is False


def test_lane_fully_canceled_false_for_empty_wp_ids() -> None:
    """Mutation kill: replacing ``bool(lane.wp_ids) and all(...)`` with a bare
    ``all(...)`` would report a lane with NO WPs as fully canceled (``all()``
    over an empty iterable is vacuously ``True``). There is nothing to have
    canceled, so this must stay ``False`` even against a non-empty excluded
    set."""
    lane = _lane([])
    assert ex._lane_fully_canceled(lane, frozenset({"WP01"})) is False


# ---------------------------------------------------------------------------
# FR-004: pre-interrupt tips keyed by the created name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "shape_builder",
    [shape_backfilled_legacy, shape_mismatched_mid8, shape_invalid_identity_long],
)
def test_capture_pre_interrupt_lane_tips_keys_by_created_branch(tmp_path: Path, shape_builder: DivergentShapeBuilder) -> None:
    """Guards against reading the IDENTITY-form branch (never the branch the
    allocator created) — that would return ``{}`` for every divergent shape.
    The returned keys must equal the allocator-CREATED branch of every
    non-planning lane, and each value must equal that branch's real tip."""
    mission = shape_builder(tmp_path)
    run = _run(mission, _state(mission))

    tips = ex._capture_pre_interrupt_lane_tips(run)

    _wt_path, created_branch = mission.lanes["lane-a"]
    assert set(tips) == {created_branch}
    assert tips[created_branch] == _rev_parse(mission.repo_root, created_branch)


def test_capture_pre_interrupt_lane_tips_short_identity_keys_by_created_branch(tmp_path: Path) -> None:
    """Guards against lane-tip capture consulting the Mission identity at all:
    a mission whose ``mission_id`` is too short to derive a mid8 must not
    raise, and the captured tip is keyed by the lane's CREATED branch name
    (never a ``mission_id``-injected form the naming seam no longer
    composes)."""
    mission = shape_invalid_identity_short(tmp_path)
    run = _run(mission, _state(mission))

    tips = ex._capture_pre_interrupt_lane_tips(run)

    _wt_path, created_branch = mission.lanes["lane-a"]
    assert set(tips) == {created_branch}


def test_capture_pre_interrupt_lane_tips_skips_fully_canceled_lane(tmp_path: Path) -> None:
    """A lane whose WPs are ALL in ``excluded_canceled_wp_ids`` contributes no
    key, even though its branch exists (FR-004/FR-009)."""
    mission = shape_backfilled_legacy(tmp_path, with_canceled_lane=True, canceled_lane_status="approved")
    # lane-b is the second lane the fixture builds -> WP02 (see `_build_shape`).
    run = _run(mission, _state(mission), excluded_canceled_wp_ids=frozenset({"WP02"}))

    tips = ex._capture_pre_interrupt_lane_tips(run)

    _wt_a, branch_a = mission.lanes["lane-a"]
    _wt_b, branch_b = mission.lanes["lane-b"]
    assert branch_a in tips
    assert branch_b not in tips
    assert _branch_exists(mission.repo_root, branch_b), "fixture invalid: lane-b's branch must still exist"


def test_capture_pre_interrupt_lane_tips_skips_planning_lane(tmp_path: Path) -> None:
    mission = shape_backfilled_legacy(tmp_path, with_planning_lane=True)
    run = _run(mission, _state(mission))

    tips = ex._capture_pre_interrupt_lane_tips(run)

    assert mission.manifest.target_branch not in tips


# ---------------------------------------------------------------------------
# FR-005: H5 unanchored-record refusal
# ---------------------------------------------------------------------------


def _h5_run(mission: DivergentMission, *, pre_interrupt_lane_tips: dict[str, str]) -> ex._MergeRunState:
    state = _state(
        mission,
        pre_mutation_coord_sha="COORDSHA",
        pre_interrupt_lane_tips=pre_interrupt_lane_tips,
    )
    return _run(mission, state, is_resume=True)


def _assert_h5_refusal_names_abort(capsys: pytest.CaptureFixture[str], *branches: str) -> None:
    """The H5 refusal message must name ``spec-kitty merge --abort`` (the
    ``_MERGE_ABORT_COMMAND`` constant) and every missing branch by name.
    Mutation-proof: dropping ``_MERGE_ABORT_AND_RESTART_HINT`` from the H5
    message, or the missing-branch listing, fails this assertion."""
    output = capsys.readouterr().out
    assert ex._MERGE_ABORT_COMMAND in output
    for branch in branches:
        assert branch in output


def test_h5_refuses_on_empty_record(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    mission = shape_mismatched_mid8(tmp_path)
    _wt_a, branch_a = mission.lanes["lane-a"]
    run = _h5_run(mission, pre_interrupt_lane_tips={})
    with pytest.raises(typer.Exit) as exc:
        ex._enforce_resume_anchor_integrity(run, coord_topology=True)
    assert exc.value.exit_code == 1
    _assert_h5_refusal_names_abort(capsys, branch_a)


def test_h5_refuses_on_partial_record(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    mission = shape_mismatched_mid8(tmp_path, with_canceled_lane=True, canceled_lane_status="approved")
    _wt_a, branch_a = mission.lanes["lane-a"]
    _wt_b, branch_b = mission.lanes["lane-b"]
    # Only lane-a is anchored; lane-b (a genuinely survivor lane, not excluded
    # as canceled here) is missing.
    run = _h5_run(mission, pre_interrupt_lane_tips={branch_a: _rev_parse(mission.repo_root, branch_a)})
    with pytest.raises(typer.Exit) as exc:
        ex._enforce_resume_anchor_integrity(run, coord_topology=True)
    assert exc.value.exit_code == 1
    _assert_h5_refusal_names_abort(capsys, branch_b)


def test_h5_refuses_on_old_form_identity_keyed_record(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """An old-form record keyed under the IDENTITY-form branch name — a
    literal never produced by post-fix naming code — must refuse (US2 AS2),
    and specifically via **H5**, never H3.

    The persisted value MUST be a real, resolvable commit object (here: the
    created lane branch's own tip) — never an unresolvable literal like
    ``"deadbeef"``. An unresolvable SHA makes H3's
    :func:`~specify_cli.merge.state.lane_tip_cas_ok` refuse FIRST (a missing
    commit object is treated as a corrupt/absent required base), which would
    pass this test for the wrong reason — proving nothing about H5. With a
    real SHA keyed under a branch name that does not exist in git, H3's CAS
    check is tolerant (a gone branch ref is fine when its persisted commit
    still resolves) and returns True, so only H5 -- which requires the
    CREATED branch name as the dict key, not the identity form -- can refuse
    here."""
    mission = shape_mismatched_mid8(tmp_path)
    _wt_a, created_branch = mission.lanes["lane-a"]
    real_sha = _rev_parse(mission.repo_root, created_branch)
    identity_form = _identity_injected_lane_branch(mission.manifest.mission_slug, "lane-a", mission.manifest.mission_id)
    assert identity_form != created_branch, "fixture invalid: identity and created forms must differ"
    run = _h5_run(mission, pre_interrupt_lane_tips={identity_form: real_sha})
    with pytest.raises(typer.Exit) as exc:
        ex._enforce_resume_anchor_integrity(run, coord_topology=True)
    assert exc.value.exit_code == 1
    _assert_h5_refusal_names_abort(capsys, created_branch)


def test_h5_refuses_when_survivor_lane_branch_gone_before_capture(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Guards against the capture-skip -> H5 gap: a non-canceled ("survivor")
    lane whose CREATED branch is already gone at tip-capture time (deleted
    outside a normal merge, never provenance-canceled) gets no entry from
    :func:`_capture_pre_interrupt_lane_tips` (the "branch that does not
    resolve... contributes no entry" tolerance) -- and a subsequent resume
    must still refuse via H5 rather than silently treating the missing key as
    an anchored, already-integrated lane."""
    mission = shape_mismatched_mid8(tmp_path, delete_created_branch_of="lane-a")
    _wt_a, branch_a = mission.lanes["lane-a"]
    assert not _branch_exists(mission.repo_root, branch_a)

    capture_run = _run(mission, _state(mission))
    tips = ex._capture_pre_interrupt_lane_tips(capture_run)
    assert branch_a not in tips, "a gone, non-canceled lane branch must be skipped, not anchored"

    run = _h5_run(mission, pre_interrupt_lane_tips=tips)
    with pytest.raises(typer.Exit) as exc:
        ex._enforce_resume_anchor_integrity(run, coord_topology=True)
    assert exc.value.exit_code == 1
    _assert_h5_refusal_names_abort(capsys, branch_a)


def test_h5_noop_on_canceled_only_manifest(tmp_path: Path) -> None:
    """A manifest whose only WP-bearing lane is fully canceled (US2 AS3) never
    requires an anchor — there is nothing to have captured."""
    mission = shape_backfilled_legacy(tmp_path)
    run = _h5_run(mission, pre_interrupt_lane_tips={})
    run.excluded_canceled_wp_ids = frozenset({"WP01"})
    ex._enforce_resume_anchor_integrity(run, coord_topology=True)  # no raise


def test_h5_noop_on_planning_only_manifest(tmp_path: Path) -> None:
    """A pure planning-artifact manifest (only ``lane-planning``) is exempt."""
    mission = shape_backfilled_legacy(tmp_path, with_planning_lane=True)
    mission.manifest.lanes = [lane for lane in mission.manifest.lanes if lane.lane_id == "lane-planning"]
    run = _h5_run(mission, pre_interrupt_lane_tips={})
    ex._enforce_resume_anchor_integrity(run, coord_topology=True)  # no raise


def test_h5_noop_when_coord_topology_false(tmp_path: Path) -> None:
    mission = shape_mismatched_mid8(tmp_path)
    run = _h5_run(mission, pre_interrupt_lane_tips={})
    ex._enforce_resume_anchor_integrity(run, coord_topology=False)  # no raise


def test_h5_not_evaluated_when_pre_mutation_coord_sha_none(tmp_path: Path) -> None:
    mission = shape_mismatched_mid8(tmp_path)
    state = _state(mission, pre_mutation_coord_sha=None, pre_interrupt_lane_tips={})
    run = _run(mission, state, is_resume=True)
    ex._enforce_resume_anchor_integrity(run, coord_topology=True)  # no raise (H4 path, unchanged)


def test_h5_noop_on_complete_record_keyed_by_created_names(tmp_path: Path) -> None:
    """A record captured by :func:`_capture_pre_interrupt_lane_tips` itself
    must never trip its own H5 guard (the capture/H5 predicates agree)."""
    mission = shape_mismatched_mid8(tmp_path)
    capture_run = _run(mission, _state(mission))
    tips = ex._capture_pre_interrupt_lane_tips(capture_run)

    run = _h5_run(mission, pre_interrupt_lane_tips=tips)
    ex._enforce_resume_anchor_integrity(run, coord_topology=True)  # no raise


# ---------------------------------------------------------------------------
# FR-006: safety preflight inspects the CREATED worktree
# ---------------------------------------------------------------------------


def test_preflight_refuses_dirty_created_lane_worktree(tmp_path: Path) -> None:
    mission = shape_mismatched_mid8(tmp_path)
    wt_path, _branch = mission.lanes["lane-a"]
    (wt_path / "scratch.txt").write_text("uncommitted operator scratch\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(mission.repo_root), "checkout", "-q", mission.manifest.target_branch], check=True)

    with pytest.raises(DestructiveOpRefused):
        ex._pre_mutation_safety_preflight(
            mission.repo_root,
            mission.manifest.mission_slug,
            mission.manifest.target_branch,
            mission.manifest,
            mission.feature_dir,
            remove_worktree=True,
            teardown_coordination=False,
        )


def test_preflight_clean_created_lane_worktree_passes(tmp_path: Path) -> None:
    mission = shape_mismatched_mid8(tmp_path)
    subprocess.run(["git", "-C", str(mission.repo_root), "checkout", "-q", mission.manifest.target_branch], check=True)

    ex._pre_mutation_safety_preflight(
        mission.repo_root,
        mission.manifest.mission_slug,
        mission.manifest.target_branch,
        mission.manifest,
        mission.feature_dir,
        remove_worktree=True,
        teardown_coordination=False,
    )  # no raise


# ---------------------------------------------------------------------------
# FR-006 cleanup of the CREATED resources
# ---------------------------------------------------------------------------


def test_remove_lane_worktrees_removes_created_worktree_and_tombstones_context(tmp_path: Path) -> None:
    from specify_cli.workspace.context import get_context_path

    mission = shape_mismatched_mid8(tmp_path)
    wt_path, _branch = mission.lanes["lane-a"]
    subprocess.run(["git", "-C", str(mission.repo_root), "checkout", "-q", mission.manifest.target_branch], check=True)
    assert wt_path.exists()

    # The tombstone filename MUST equal ``_created_lane_worktree(...).name``
    # (the ``{slug}-{lane}`` form ``save_context`` writes) — seed it directly so
    # the assertion below proves the SAME name the removal loop computed, never
    # a name this test guessed independently.
    workspace_name = ex._created_lane_worktree(mission.repo_root, mission.manifest.mission_slug, "lane-a").name
    context_path = get_context_path(mission.repo_root, workspace_name)
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.write_text("{}", encoding="utf-8")

    run = _run(mission, _state(mission))
    ex._remove_lane_worktrees(run)

    assert not wt_path.exists(), "the allocator-CREATED worktree must be removed"
    assert not context_path.exists(), "the lane's workspace-context JSON must be tombstoned"


def test_delete_lane_branches_deletes_created_branch(tmp_path: Path) -> None:
    mission = shape_mismatched_mid8(tmp_path)
    wt_path, branch = mission.lanes["lane-a"]
    subprocess.run(["git", "-C", str(mission.repo_root), "worktree", "remove", "--force", str(wt_path)], check=True)
    assert _branch_exists(mission.repo_root, branch)

    run = _run(mission, _state(mission))
    ex._delete_lane_branches(run)

    assert not _branch_exists(mission.repo_root, branch), "the allocator-CREATED branch must be deleted"


def test_delete_lane_branches_skips_planning_lane(tmp_path: Path) -> None:
    mission = shape_backfilled_legacy(tmp_path, with_planning_lane=True)
    run = _run(mission, _state(mission))
    ex._delete_lane_branches(run)  # no raise; target branch ("main") is untouched
    assert _branch_exists(mission.repo_root, mission.manifest.target_branch)


def test_cleanup_full_run_removes_no_orphans(tmp_path: Path) -> None:
    """Guards against the worktree-removal loop keying on
    ``run.baseline_mission_id`` (a divergent-identity mission's baseline
    differs from the CREATED name) — that would orphan the real worktree even
    though ``remove_worktree=True``. No allocator-created worktree or branch
    may survive a full cleanup (US1 AS5, SC-002)."""
    mission = shape_mismatched_mid8(tmp_path)
    wt_path, branch = mission.lanes["lane-a"]
    subprocess.run(["git", "-C", str(mission.repo_root), "checkout", "-q", mission.manifest.target_branch], check=True)

    run = _run(mission, _state(mission))
    run.baseline_mission_id = mission.mission_id  # the pre-fix orphaning input
    ex._remove_lane_worktrees(run)
    ex._delete_lane_branches(run)

    assert not wt_path.exists()
    assert not _branch_exists(mission.repo_root, branch)


def test_phase_cleanup_retention_keeps_created_worktree_and_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Retention (``remove_worktree=False``/``delete_branch=False``, mapped
    from ``--keep-worktree``/``--keep-branch``) drives the REAL phase body
    (:func:`~specify_cli.merge.executor._phase_cleanup_worktrees_and_branches`,
    never a test-local ``if`` re-implementing its gates) — the CREATED
    worktree and branch survive. The mission/coordination leg is patched out
    (out of scope for this WP; covered by its own suite)."""
    mission = shape_mismatched_mid8(tmp_path)
    wt_path, branch = mission.lanes["lane-a"]
    subprocess.run(["git", "-C", str(mission.repo_root), "checkout", "-q", mission.manifest.target_branch], check=True)
    monkeypatch.setattr(ex, "_cleanup_mission_branch_and_coordination", lambda _run: None)

    run = _run(mission, _state(mission))
    run.remove_worktree = False
    run.delete_branch = False

    ex._phase_cleanup_worktrees_and_branches(run)

    assert wt_path.exists(), "retention (remove_worktree=False) must not remove the created worktree"
    assert _branch_exists(mission.repo_root, branch), "retention (delete_branch=False) must not delete the created branch"


def test_phase_cleanup_removes_created_worktree_and_branch_when_requested(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The counterpart of the retention case above, through the SAME real
    phase body: ``remove_worktree=True``/``delete_branch=True`` removes both
    (US1 AS5, SC-002)."""
    mission = shape_mismatched_mid8(tmp_path)
    wt_path, branch = mission.lanes["lane-a"]
    subprocess.run(["git", "-C", str(mission.repo_root), "checkout", "-q", mission.manifest.target_branch], check=True)
    monkeypatch.setattr(ex, "_cleanup_mission_branch_and_coordination", lambda _run: None)

    run = _run(mission, _state(mission))
    run.remove_worktree = True
    run.delete_branch = True

    ex._phase_cleanup_worktrees_and_branches(run)

    assert not wt_path.exists()
    assert not _branch_exists(mission.repo_root, branch)


def test_phase_cleanup_keep_branch_only_retains_branch_removes_worktree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Proves the ``delete_branch`` gate specifically (mutation kill for
    replacing ``if run.delete_branch: _delete_lane_branches(run)`` with an
    unconditional call): ``remove_worktree=True``/``delete_branch=False``
    (``--keep-branch`` alone) removes the created worktree but leaves the
    created branch alone. The worktree must come down FIRST so the branch is
    no longer checked out anywhere -- otherwise a git worktree lock would
    make a real ``git branch -D`` fail regardless of the gate, masking a
    dropped gate as a false green (the surviving mutant this closes)."""
    mission = shape_mismatched_mid8(tmp_path)
    wt_path, branch = mission.lanes["lane-a"]
    subprocess.run(["git", "-C", str(mission.repo_root), "checkout", "-q", mission.manifest.target_branch], check=True)
    monkeypatch.setattr(ex, "_cleanup_mission_branch_and_coordination", lambda _run: None)

    run = _run(mission, _state(mission))
    run.remove_worktree = True
    run.delete_branch = False

    ex._phase_cleanup_worktrees_and_branches(run)

    assert not wt_path.exists(), "remove_worktree=True must remove the created worktree"
    assert _branch_exists(mission.repo_root, branch), "delete_branch=False (--keep-branch) must retain the created branch"
