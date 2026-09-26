"""Repro #5021 residual 1 -- resume mid-teardown false-FAILs a completed squash.

WP02 (terminus-reconciliation-attribution-integrity-01M3D4RW). Mechanism
(research.md Decision 3 / contract R1): a default-squash ``spec-kitty merge``
that already advanced the target and PASSed reconciliation, then crashed
DURING coordination teardown (e.g. the lane branch was already deleted),
re-runs the full squash content axis on ``--resume``. ``_capture_reconciliation_
claim`` rebuilds ``ApprovedWpCommitSet.authored_blobs`` from each approved
lane's first-parent spine (``_lane_first_parent_spine``); once the lane branch
is gone, that spine is unresolvable and the (tolerant) rebuild collapses to an
EMPTY authored set. ``MergeOutcomeVerifier._unattributable_content_squash``
then REFUSEs an empty authored-blob set against resolved approved WPs --
false-FAILing a legitimately-completed, already-verified merge.

Contract R1: after ``--resume``, the merge must complete teardown (exit 0),
the already-PASSed target tip must remain an ancestor of the final target (no
CAS-revert), and the approved commit's content must still be present on the
target. The fixture retains coordination during the REAL first (setup) merge
(``--keep-worktree``, so only lane branches are torn down) precisely to model
"reconciliation already PASSed, teardown partially done" -- the coordination
teardown's own retrospective-persist-before-destroy step therefore legitimately
lands ONE further commit on ``--resume`` (it never ran during setup), so the
target tip is expected to ADVANCE past the pre-resume SHA, not stay
byte-identical to it; what must never happen is a REVERT (the pre-resume SHA
ceasing to be an ancestor).

Contract R2 (guard): a GENUINELY incomplete merge (target never advanced /
reconciliation never recorded as PASSed) must still run the full gate on
``--resume`` -- no tolerance leak (``test_5021_r2_genuinely_incomplete_merge_
still_runs_full_gate``).

RED-first: driven through the REAL ``spec-kitty merge --resume`` CLI (no
``_run_git`` / subprocess mocking). The interrupted mid-teardown git state
(target already carrying the squashed lane content, lane branch already
deleted) + resume state are built with real git and ``save_state`` -- fixture
setup, not a mock. Verified RED against pre-fix ``executor.py``/``state.py``
(the REFUSE fired on resume); GREEN after T008's persisted
``reconciliation_passed_target_sha`` CAS short-circuit + the
``_lane_completed_but_branch_gone`` resume tolerance in ``_phase_merge_lanes``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.terminus.conftest import (
    CoordMission,
    blob_present_at,
    build_coord_mission,
    run_terminus,
    sha_reachable,
)
from tests.terminus.conftest import _git as git
from tests.terminus.conftest import _git_out as git_out

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]


def _coord_worktree(mission: CoordMission) -> Path:
    for line in git_out(mission.repo, "worktree", "list").splitlines():
        path = line.split()[0]
        if "coord" in path:
            return Path(path)
    raise AssertionError("coordination worktree not found")


def _complete_squash_then_recreate_mid_teardown_state(mission: CoordMission, wp_id: str, wp_order: list[str]) -> str:
    """Drive a REAL, fully successful squash merge with ``--keep-worktree`` (so
    lane branches ARE deleted but the coordination branch/worktree/marker are
    NOT -- one coupled decision, ``teardown_coordination = delete_branch AND
    remove_worktree``), then re-persist a resume-pending ``state.json`` on top
    of that real, fully-landed git state -- the exact #5021 r1 window
    (research.md Decision 3): target already advanced + reconciliation already
    PASSed, teardown partially done (lane branch gone, coordination retained).

    Driving the FIRST merge for real (rather than hand-simulating the squash)
    is deliberate: several phases between lane consolidation and the
    mission->target squash (baseline/bake, pre-target ``done`` marking) also
    write to the coordination branch, so only a REAL run produces the exact
    coordination tree a resumed ``_phase_mission_to_target`` tree-equality
    check will recognize as "already applied" (no spurious second squash
    commit on resume).

    Persists the SAME pre-mutation anchors real post-fix attempt-1 durably
    writes BEFORE it consolidates any lane (mirroring the #4982/#4997 sibling
    fixtures) so the resume is not fail-closed by the H4 baseless-consolidation
    guard, PLUS ``mission_number_baked=True`` (the real first run already baked
    it for real) so a resumed bake phase treats it as already done rather than
    attempting a second bake against a coordination branch that no longer
    exists to receive it.

    Returns the target branch tip SHA at the moment reconciliation PASSed --
    also injected into the persisted state.json as
    ``reconciliation_passed_target_sha`` so a POST-FIX resume can recognize
    the completed-but-mid-teardown state. Written as a raw JSON key (not via
    the ``MergeState`` constructor) so this SAME fixture is inert pre-fix
    (``MergeState.from_dict``'s known-fields filter silently drops an
    unrecognised key) and load-bearing post-fix -- no fixture edit needed
    between T007 (RED) and T008 (GREEN).
    """
    from mission_runtime import MissionArtifactKind, resolve_placement_only
    from specify_cli.merge.reconciliation import write_post_fix_marker
    from specify_cli.merge.state import MergeState, get_state_path, save_state

    # --- pre-mutation anchors, captured BEFORE the REAL merge runs -----------
    pre_mutation_coord_sha = mission.rev(mission.coord_branch)
    pre_mutation_coord_ref = resolve_placement_only(mission.repo, mission.slug, kind=MissionArtifactKind.STATUS_STATE).ref
    pre_mutation_target_sha = mission.rev(mission.target_branch)
    pre_interrupt_lane_tips = {mission.lane_branch(wp): mission.rev(mission.lane_branch(wp)) for wp in wp_order}

    # -- drive a REAL, fully successful squash merge; retain ONLY coordination
    #    (lane branches still get deleted -- ``delete_branch`` defaults True and
    #    is independent of ``--keep-worktree``'s ``remove_worktree=False``,
    #    which couples with ``delete_branch`` into ``teardown_coordination``). -
    setup_result = run_terminus(mission, ["merge", "--mission", mission.slug, "--keep-worktree", "--yes"])
    assert setup_result.returncode == 0, (
        "fixture precondition: the REAL first squash merge must succeed so the "
        f"resumed state models a genuinely-completed merge. "
        f"stdout={setup_result.stdout}\nstderr={setup_result.stderr}"
    )
    target_sha_at_pass = mission.rev(mission.target_branch)

    state = MergeState(
        mission_id=mission.mission_id,
        mission_slug=mission.slug,
        target_branch=mission.target_branch,
        wp_order=list(wp_order),
    )
    state.completed_wps = list(wp_order)
    state.current_wp = None
    state.strategy = "squash"
    state.mission_number_baked = True
    state.pre_mutation_coord_sha = pre_mutation_coord_sha
    state.pre_mutation_coord_ref = pre_mutation_coord_ref
    state.pre_mutation_target_sha = pre_mutation_target_sha
    state.pre_interrupt_lane_tips = pre_interrupt_lane_tips
    save_state(state, mission.repo)

    # Inject the completed-state marker directly into the persisted JSON (see
    # docstring) -- forward-compatible with the not-yet-existing dataclass field.
    state_path = get_state_path(mission.repo, mission.mission_id)
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    payload["reconciliation_passed_target_sha"] = target_sha_at_pass
    state_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    write_post_fix_marker(mission.repo, mission.mission_id)
    git(mission.repo, "checkout", "-q", mission.target_branch)
    return target_sha_at_pass


def test_5021_r1_resume_completes_teardown_without_rerunning_content_axis(
    tmp_path: Path,
) -> None:
    mission = build_coord_mission(tmp_path, wps=("WP01",), mid8="01M5021A")
    target_sha_before_resume = _complete_squash_then_recreate_mid_teardown_state(mission, "WP01", ["WP01"])

    result = run_terminus(mission, ["merge", "--resume", "--yes"])

    assert result.returncode == 0, (
        f"#5021 r1: --resume over a completed-but-mid-teardown squash must "
        f"complete (exit 0), not re-run the content axis and REFUSE. "
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    assert sha_reachable(mission.repo, target_sha_before_resume, mission.target_branch), (
        "#5021 r1: the already-PASSed target tip must remain an ancestor of the "
        "final target -- a resume that re-runs the content axis and REFUSEs "
        "CAS-reverts the target, which would drop this SHA"
    )
    assert blob_present_at(mission.repo, mission.target_branch, "src/pkg/wp01.py"), (
        "#5021 r1: the approved WP01 content must remain on the target after --resume completes teardown"
    )


def test_5021_r2_genuinely_incomplete_merge_still_runs_full_gate(tmp_path: Path) -> None:
    """Guard (R2): a genuinely incomplete resume (target never advanced, no PASS
    recorded) must still run the full reconciliation gate -- no tolerance leak.

    Mirrors #4982's clean interrupt-after-first-lane window (mission consolidated
    onto coord, but the mission never reached the target), with NO
    ``reconciliation_passed_target_sha`` marker persisted. The short-circuit must
    NOT fire: this is not a real repro of a fix (the merge legitimately proceeds
    through the full gate and PASSes on its own merits, since nothing is actually
    unattributable here) -- it only proves the short-circuit is not vacuously
    true, i.e. it distinguishes "genuinely incomplete" from "completed but
    mid-teardown".
    """
    from mission_runtime import MissionArtifactKind, resolve_placement_only
    from specify_cli.merge.reconciliation import write_post_fix_marker
    from specify_cli.merge.state import MergeState, save_state

    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M5021B")

    pre_mutation_coord_sha = mission.rev(mission.coord_branch)
    pre_mutation_coord_ref = resolve_placement_only(mission.repo, mission.slug, kind=MissionArtifactKind.STATUS_STATE).ref
    pre_interrupt_lane_tips = {mission.lane_branch(wp): mission.rev(mission.lane_branch(wp)) for wp in ("WP01", "WP02")}

    coord_wt = _coord_worktree(mission)
    git(coord_wt, "merge", "-q", "--no-edit", mission.lane_branch("WP01"))

    state = MergeState(
        mission_id=mission.mission_id,
        mission_slug=mission.slug,
        target_branch=mission.target_branch,
        wp_order=["WP01", "WP02"],
    )
    state.completed_wps = ["WP01"]
    state.current_wp = "WP02"
    state.strategy = "squash"
    state.pre_mutation_coord_sha = pre_mutation_coord_sha
    state.pre_mutation_coord_ref = pre_mutation_coord_ref
    state.pre_interrupt_lane_tips = pre_interrupt_lane_tips
    # Deliberately NO ``reconciliation_passed_target_sha`` -- this attempt never
    # reached the reconciliation gate, so nothing must be recorded as PASSed.
    save_state(state, mission.repo)
    write_post_fix_marker(mission.repo, mission.mission_id)
    git(mission.repo, "checkout", "-q", mission.target_branch)

    result = run_terminus(mission, ["merge", "--resume", "--yes"])

    assert result.returncode == 0, (
        f"R2 guard: a genuinely incomplete merge must still complete via the full gate on --resume. stdout={result.stdout}\nstderr={result.stderr}"
    )
    for wp_id in ("WP01", "WP02"):
        for sha in mission.approved_shas_from_lane_tips([wp_id])[wp_id]:
            assert sha_reachable(mission.repo, sha, mission.target_branch) or blob_present_at(mission.repo, mission.target_branch, f"src/pkg/{wp_id.lower()}.py"), (
                f"R2 guard: approved {wp_id} content must land via the full gate"
            )
