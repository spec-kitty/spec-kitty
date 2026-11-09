"""Intended-verdict pins: what the consolidation gate SHOULD decide where Phase 4 fixes it (FR-016, NFR-002).

The characterization corpus (``characterization/verdict_corpus.json``) records what the gate does
today, known-wrong verdicts included. This module records the verdict each Phase 4 work package
makes true, as a strict ``xfail(raises=AssertionError)`` test per NFR-002 cell. A fix removes the
marker of exactly the cell(s) it flips, in its fix commit, so "the golden diff is a subset of the
named cells" stays checkable.

========  =======================================================  ==========  ===================
Cell      Test                                                     FR          Flipped by
========  =======================================================  ==========  ===================
(a)       ``test_commit_between_two_approvals_is_refused``         FR-007      WP19
(a) mixed ``test_gap_then_recorded_stray_commit_is_refused``       FR-007      WP19
(b)       ``test_window_refusal_names_commit_and_preceding_wp``    FR-007      WP19
(c)       ``test_rewound_wp_window_opens_after_rewind[lanes]``     FR-021      WP19
(c)       ``test_rewound_wp_window_opens_after_rewind[single_..]`` FR-021      WP20
(d)       ``test_history_read_error_refuses_instead_of_deleting``  FR-014      WP16
(e)       ``test_resume_closed_world_reads_frozen_anchors``        FR-015      WP18
(f)       ``test_resume_approved_bound_reads_frozen_anchors``      FR-015      WP18
(g)       ``test_resume_fully_canceled_lane_reads_frozen_anchors`` FR-015      (unreachable, below)
(h)       ``test_forecast_uses_fresh_run_excluded_canceled_set``   FR-013      WP17
(h)       ``test_forecast_resolves_coordination_base_to_...``      FR-013      WP17
residual  ``test_parallel_claims_window_is_not_over_wide``         WW-6        stays ``xfail``
========  =======================================================  ==========  ===================

The precondition rule. A strict ``xfail(raises=AssertionError)`` turns ANY ``AssertionError`` into an
expected failure, a broken fixture included. So fixture work never asserts: :func:`require` raises
:class:`FixturePrecondition` (a ``RuntimeError``), and :func:`fixture_phase` re-raises the
``AssertionError`` of the shared corpus helpers (``ResumeUnreachableError`` is one) the same way. A
broken fixture therefore ERRORS the test instead of hiding behind the marker. Only the final
verdict assertions use ``assert``.

Cell (g) is the one cell that is not an ``xfail``: its flip is unreachable at verdict level, and the
test pins the reachable consequence instead (see its docstring).
"""

from __future__ import annotations

import contextlib
import inspect
import json
import re
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest

from specify_cli.consolidation import reconciliation
from specify_cli.consolidation.git_probes import GitProbeError
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
from tests.consolidation import characterization_support as cs
from tests.consolidation.reconciliation_family import setattr_reconciliation_family
from tests.terminus import rollback_harness
from tests.terminus.canceled_dependency_support import ACTOR, WP01_PATH, WP02_PATH, _approve, _commit_in
from tests.terminus.conftest import PlantedChange, build_coord_mission_mixed_lane_canceled
from tests.terminus.mixed_lane_support import transition

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

MOVED = "LANE_MOVED_AFTER_APPROVAL"
SINGLE_BRANCH_ABANDONED_PATH = "src/m2/abandoned.py"
_FROZEN_SHA = re.compile(r"[0-9a-f]{40}")


# --------------------------------------------------------------------------- the precondition rule


class FixturePrecondition(RuntimeError):
    """A fixture precondition failed: an error, never an ``AssertionError`` an ``xfail`` could absorb."""


def require(condition: bool, message: str) -> None:
    """Fixture precondition: raises :class:`FixturePrecondition` (never ``AssertionError``) when *condition* is false."""
    if not condition:
        raise FixturePrecondition(message)


@contextlib.contextmanager
def fixture_phase() -> Iterator[None]:
    """Fixture work whose ``AssertionError`` (the shared helpers raise them) must error the test, not xfail it."""
    try:
        yield
    except AssertionError as broken:
        raise FixturePrecondition(f"fixture helper failed: {broken}") from broken


def intended(cell: str, requirement: str, flipped_by: str) -> pytest.MarkDecorator:
    """The strict ``xfail`` of one NFR-002 cell: it names the cell, the FR and the work package that flips it."""
    return pytest.mark.xfail(strict=True, raises=AssertionError, reason=f"NFR-002 cell ({cell}), {requirement}; flipped by {flipped_by}")


# --------------------------------------------------------------------------- fixtures and observations


def _template(tmp_path: Path, name: str) -> cs.ShapeMission:
    """The corpus template *name*, built under *tmp_path* (a derived template builds its dependency first)."""
    dependency, builder = cs.TEMPLATES[name]
    with fixture_phase():
        base = cs.TEMPLATES[dependency][1](tmp_path / "base", None) if dependency else None
        return builder(tmp_path / "m", base)


def _git(mission: cs.ShapeMission, *args: str) -> str:
    with fixture_phase():
        return cs._git(mission.repo, *args)


def _tip(mission: cs.ShapeMission, ref: str) -> str:
    return cs._try_git(mission.repo, "rev-parse", "--verify", "-q", ref) or "<gone>"


def _branch_tips(mission: cs.ShapeMission) -> dict[str, str]:
    """Where the target, the Mission branch and every lane branch point: the 'no branch moved' observation."""
    refs = {"target": mission.target_branch, "mission": mission.mission_branch, **{f"lane:{wp}": branch for wp, branch in mission.lane_branches.items()}}
    return {name: _tip(mission, ref) for name, ref in refs.items()}


def _is_ancestor(mission: cs.ShapeMission, ancestor: str, descendant: str) -> bool:
    return cs._try_git(mission.repo, "merge-base", "--is-ancestor", ancestor, descendant) is not None


def _last_commit_touching(mission: cs.ShapeMission, branch: str, path: str) -> str:
    sha = _git(mission, "rev-list", "-1", branch, "--", path)
    require(bool(sha), f"no commit on {branch} touches {path}")
    return sha


def _openers(mission: cs.ShapeMission, wp_id: str) -> list[dict[str, Any]]:
    """The work package's non-migration openings (moves into claimed / in_progress), in log order."""
    with fixture_phase():
        return [event for event in cs._events(mission) if cs._is_opening(event, wp_id)]


def _open_sha(event: Mapping[str, Any]) -> str | None:
    window = (event.get("policy_metadata") or {}).get(cs.WP_WINDOW_KEY) or {}
    sha = window.get("open_sha")
    return str(sha) if sha else None


def _require_recorded(mission: cs.ShapeMission, wp_id: str) -> list[str]:
    """Every opener of *wp_id* carries a recorded ``open_sha`` (the window state under test); returns them in order."""
    shas = [_open_sha(event) for event in _openers(mission, wp_id)]
    require(bool(shas) and all(shas), f"{wp_id}: every opening event must carry wp_window.open_sha, got {shas}")
    return [str(sha) for sha in shas]


def _require_not_recorded(mission: cs.ShapeMission, wp_id: str) -> None:
    shas = [_open_sha(event) for event in _openers(mission, wp_id)]
    require(bool(shas) and not any(shas), f"{wp_id}: no opening event may carry wp_window.open_sha, got {shas}")


def _approval_stamp(mission: cs.ShapeMission, wp_id: str) -> str:
    """The ``lane_head`` stamped on the work package's newest ``approved`` event."""
    with fixture_phase():
        approvals = [event for event in cs._events(mission) if event.get("wp_id") == wp_id and event.get("to_lane") == "approved"]
    stamp = ((approvals[-1].get("policy_metadata") or {}).get("lane_head") if approvals else None) or ""
    require(bool(stamp), f"{wp_id} has no stamped approval")
    return str(stamp)


def _run(mission: cs.ShapeMission, mode: str, *extra: str) -> cs.CellResult:
    return cs.run_in_process(mission, cs.consolidate_args(mission, mode, *extra))


def _assert_refused_naming(result: cs.CellResult, *needles: str) -> None:
    """The refusal verdict: exit != 0, ``LANE_MOVED_AFTER_APPROVAL``, and every needle named in the output."""
    assert result.exit_code != 0, f"the run must refuse, it exited 0:\n{result.output}"
    assert MOVED in result.output, f"the refusal must carry {MOVED}:\n{result.output}"
    for needle in needles:
        assert needle in result.output, f"the refusal must name {needle!r}:\n{result.output}"


# --------------------------------------------------------------------------- T024: commit between two approvals (a, b)


@pytest.fixture
def stray_mission(tmp_path: Path) -> tuple[cs.ShapeMission, str]:
    """A lane with WP01 approved, a stray commit X, WP02 opened (recorded window) and approved; no other lane reaches X."""
    mission = _template(tmp_path, "two_wp_lane_stray")
    with fixture_phase():
        cs.set_window_states(mission, "recorded")
    lane = mission.lane_branches["WP01"]
    stray = _last_commit_touching(mission, lane, cs.STRAY_PATH)
    first_stamp = _approval_stamp(mission, "WP01")
    require(_is_ancestor(mission, first_stamp, stray) and not _is_ancestor(mission, stray, first_stamp), "the stray commit must come after WP01's approval stamp")
    require(_is_ancestor(mission, stray, _approval_stamp(mission, "WP02")), "the stray commit must come before WP02's approval stamp")
    require(len(mission.lane_branches) == 2 and set(mission.lane_branches.values()) == {lane}, "both work packages share ONE lane, no other lane reaches X")
    _require_recorded(mission, "WP02")
    return mission, stray


def test_two_approvals_without_stray_commit_pass(tmp_path: Path) -> None:
    """Control (US2-2): the same fixture without X consolidates, so the pins below cannot hide an unrelated refusal."""
    mission = _template(tmp_path, "two_wp_lane")
    with fixture_phase():
        cs.set_window_states(mission, "recorded")
    require(cs._try_git(mission.repo, "cat-file", "-e", f"{mission.lane_branches['WP01']}:{cs.STRAY_PATH}") is None, "this control must hold no stray commit")
    _require_recorded(mission, "WP02")

    result = _run(mission, "fresh")

    assert result.exit_code == 0, result.output
    assert MOVED not in result.output, result.output


@intended("a", "FR-007", "WP19")
def test_commit_between_two_approvals_is_refused(stray_mission: tuple[cs.ShapeMission, str]) -> None:
    """US2-1: a commit between two approvals, with recorded windows, refuses ``LANE_MOVED_AFTER_APPROVAL`` and the target stays put."""
    mission, _stray = stray_mission
    before = _branch_tips(mission)

    result = _run(mission, "fresh")

    _assert_refused_naming(result)
    assert _branch_tips(mission) == before, "the refusal must not move any branch"


@intended("b", "FR-007", "WP19")
def test_window_refusal_names_commit_and_preceding_wp(stray_mission: tuple[cs.ShapeMission, str]) -> None:
    """FR-007: the refusal names the stray commit (short SHA as rendered) and WP01, the work package approved before it."""
    mission, stray = stray_mission

    result = _run(mission, "fresh")

    _assert_refused_naming(result, stray[:7], "WP01")


@intended("a mixed", "FR-007", "WP19")
def test_gap_then_recorded_stray_commit_is_refused(stray_mission: tuple[cs.ShapeMission, str]) -> None:
    """NFR-002 (a) mixed case, WW-7: WP01 has a window gap, X follows its approval, WP02 is recorded and approved after X.

    WP01 falls back to its approval-stamp bound (X is after it) and WP02's window opens after X, so X lies outside every window.
    """
    mission, _stray = stray_mission
    with fixture_phase():
        cs.set_window_state(mission, "WP01", "not_recorded")
    _require_not_recorded(mission, "WP01")
    _require_recorded(mission, "WP02")
    before = _branch_tips(mission)

    result = _run(mission, "fresh")

    _assert_refused_naming(result)
    assert _branch_tips(mission) == before, "the refusal must not move any branch"


# --------------------------------------------------------------------------- T025: rewound work package (c)


def _rewound_lanes(tmp_path: Path) -> tuple[cs.ShapeMission, str, str, str]:
    mission = _template(tmp_path, "two_wp_lane_rewound")
    with fixture_phase():
        cs.set_window_states(mission, "recorded")
    return mission, mission.lane_branches["WP02"], cs.ABANDONED_PATH, WP02_PATH


def _rewound_single_branch(tmp_path: Path) -> tuple[cs.ShapeMission, str, str, str]:
    mission = _template(tmp_path, "single_branch_rewound")
    with fixture_phase():
        cs._single_branch_recorded(mission)
    return mission, mission.mission_branch, SINGLE_BRANCH_ABANDONED_PATH, "src/m2/real.py"


@pytest.mark.parametrize(
    ("build", "flipped_by"),
    [(_rewound_lanes, "WP19"), (_rewound_single_branch, "WP20")],
    ids=["lanes", "single_branch"],
)
def test_rewound_wp_window_opens_after_rewind(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    build: Callable[[Path], tuple[cs.ShapeMission, str, str, str]],
    flipped_by: str,
) -> None:
    """FR-021, data-model section 3 cycle rule: a rewound work package's window is ``(S1, stamp]``, S1 being the first opener after the rewind.

    The abandoned attempt C1 was committed before the rewind: it lies in the abandoned cycle, outside every window and every
    exemption anchor, so it is refused. The work after the restart (C2) lies inside the window and is not named.
    """
    request.applymarker(intended("c", "FR-021", flipped_by))
    mission, branch, abandoned_path, work_path = build(tmp_path)
    abandoned = _last_commit_touching(mission, branch, abandoned_path)
    work = _last_commit_touching(mission, branch, work_path)
    openers = _require_recorded(mission, "WP02")
    require(len(openers) >= 2, f"WP02 must have been claimed again after the rewind, openers: {openers}")
    require(not _is_ancestor(mission, abandoned, openers[0]), "the first cycle must open before the abandoned commit")
    require(_is_ancestor(mission, abandoned, openers[-1]), "the cycle after the rewind must open after the abandoned commit")
    require(not _is_ancestor(mission, work, openers[-1]), "the restarted cycle must open before its own work")
    before = _branch_tips(mission)

    result = _run(mission, "fresh")

    _assert_refused_naming(result, abandoned[:7])
    assert work[:7] not in result.output, f"C2 lies inside the restarted window and must not be named:\n{result.output}"
    assert _branch_tips(mission) == before, "the refusal must not move any branch"


# --------------------------------------------------------------------------- T026: a history-read error is never a deletion (d)


def _failing_probe_for(path: str, touch_sha: str, real: Callable[[Path, str, str], str]) -> Callable[[Path, str, str], str]:
    """A ``blob_id_at`` that raises ``GitProbeError`` for exactly ``(touch_sha, path)`` and delegates everywhere else.

    Scoped to that one pair on purpose: the verifier also reads ``blob_id_at(target_ref, path)`` at gate time, and a fake that
    raised for the path at any ref would refuse at the GATE and roll back, which satisfies loose assertions and XPASSes the pin.
    Retarget this helper when the fix replaces the probe (WP16 moves the read to ``path_state_at``).
    """

    def _probe(repo_root: Path, ref: str, probed_path: str) -> str:
        if ref == touch_sha and probed_path == path:
            raise GitProbeError(f"injected history-read error for {probed_path} at {ref}")
        return real(repo_root, ref, probed_path)

    return _probe


@intended("d", "FR-014", "WP16")
def test_history_read_error_refuses_instead_of_deleting(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-014, US4-1: the failed history read refuses the claim, naming the path, before anything moves.

    Today ``_final_authored_walk`` records the unreadable path as a deletion, the claim builds, and the run continues past claim
    time (the gate then FAILs it as an unattributable blob and rolls back). Intended: exit 1 with the claim-time probe message,
    no branch moved, NO move-and-restore (a gate rollback leaves a reflog entry, a claim-time refusal leaves none), and no
    pre-mutation snapshot left behind.
    """
    mission = _template(tmp_path, "single_lane")
    lane = mission.lane_branches["WP01"]
    touch_sha = _git(mission, "rev-list", "--first-parent", "-1", f"{mission.mission_branch}..{lane}", "--", WP01_PATH)
    require(bool(touch_sha), f"no first-parent lane commit touches {WP01_PATH}")
    tip_has_path = cs._try_git(mission.repo, "cat-file", "-e", f"{lane}:{WP01_PATH}") is not None
    require(tip_has_path, f"{WP01_PATH} must exist at the lane tip: the spine modifies it, it is no deletion")
    coordinated = mission.coord_mission()
    watched = (mission.target_branch, mission.mission_branch)
    refs_before = rollback_harness.ref_shas(coordinated)
    reflogs_before = {branch: rollback_harness.reflog_shas(coordinated, branch) for branch in watched}
    require(rollback_harness.state_path(coordinated) is None, "no consolidation record may exist before the run")
    setattr_reconciliation_family(monkeypatch, "blob_id_at", _failing_probe_for(WP01_PATH, touch_sha, reconciliation.blob_id_at))

    result = _run(mission, "fresh")

    assert result.exit_code == 1, result.output
    assert "a git probe failed while building the approved-WP claim" in result.output, result.output
    assert WP01_PATH in result.output, f"the refusal must name the path:\n{result.output}"
    assert rollback_harness.ref_shas(coordinated) == refs_before, "no branch may have moved"
    reflogs_after = {branch: rollback_harness.reflog_shas(coordinated, branch) for branch in watched}
    assert reflogs_after == reflogs_before, "nothing may have been moved and rolled back (a restore leaves a reflog entry)"
    record = rollback_harness.state_path(coordinated)
    assert record is None or not json.loads(record.read_text(encoding="utf-8")).get("pre_mutation_refs"), "no pre-mutation snapshot may remain"


# --------------------------------------------------------------------------- T027: resume reads frozen anchors (e, f, g)


def _advance_dependency_and_merge(dependency_wp: str, dependent_wp: str) -> Callable[[cs.ShapeMission], str]:
    """After the interruption: the dependency lane gains a commit D, then the dependent lane merges it. Returns D."""

    def _between(mission: cs.ShapeMission) -> str:
        advanced = cs._advance_lane(mission, dependency_wp, "src/advanced/after_interrupt.py", "feat: dependency lane advanced after the interruption")
        with cs.lane_checkout(mission, mission.lane_branches[dependent_wp]) as dependent:
            cs._git(dependent, "merge", "-q", "--no-ff", "--no-edit", mission.lane_branches[dependency_wp])
        return advanced

    return _between


def _advance_without_merge(wp_id: str) -> Callable[[cs.ShapeMission], str]:
    def _between(mission: cs.ShapeMission) -> str:
        return cs._advance_lane(mission, wp_id, "src/advanced/after_interrupt.py", "feat: canceled dependency lane advanced after the interruption")

    return _between


def _resume_after_interruption(
    mission: cs.ShapeMission,
    between: Callable[[cs.ShapeMission], str] | None,
    dependency_wp: str,
    *,
    frozen_wps: tuple[str, ...],
) -> tuple[cs.CellResult, str]:
    """Interrupt right after the claim anchors were saved, move the dependency lane (D), then ``consolidate --resume``.

    Preconditions: the record holds ``pre_interrupt_lane_tips`` for every lane of *frozen_wps* (never hand-written), and D is
    not reachable from the dependency lane's tip as the interrupted run left it. *between* ``None`` leaves the lane alone (the
    control; D is then empty). Returns the resume result and D.
    """
    with fixture_phase():
        record = cs.interrupt_after_claim(mission)
        tips = record.get("pre_interrupt_lane_tips")
        for wp_id in frozen_wps:
            lane_branch = mission.lane_branches[wp_id]
            require(isinstance(tips, dict) and lane_branch in tips, f"state.json must freeze {lane_branch} in pre_interrupt_lane_tips: {tips}")
        interrupted_tip = _tip(mission, mission.lane_branches[dependency_wp])
        advanced = between(mission) if between is not None else ""
        require(between is None or not _is_ancestor(mission, advanced, interrupted_tip), "D must lie beyond the dependency-lane tip the interrupted run saw")
    return _run(mission, "resume"), advanced


@intended("e", "FR-015", "WP18")
def test_resume_closed_world_reads_frozen_anchors(tmp_path: Path) -> None:
    """US4-3, FR-015: on a mixed lane (lane-b: approved WP01 + canceled WP02) a dependency-lane advance after the interruption exempts nothing.

    lane-a (WP03) gains D after the interruption and the mixed lane merges it. With the anchors frozen at claim capture D is
    not reachable from them, so the mixed lane refuses it as well (lane-b / WP01), not only lane-a. Today the live
    dependency-lane tip is an anchor, D is exempt on lane-b, and only lane-a is refused.

    The observable is the dependent lane's refusal line: on this fixture (the allocator-shaped ``--no-ff`` merge) the
    closed-world scan reads the first-parent spine, where D is the merge commit, so the closed-world and approved-bound anchors
    flip together (WP18 flips (e) and (f) in one commit).
    """
    mission = _template(tmp_path, "mixed_lane_with_dependency")
    with fixture_phase():
        cs.set_window_states(mission, "recorded")
    require(bool(mission.canceled_wps), "the dependent lane must be mixed: a canceled work package shares it")
    require(mission.lane_branches["WP01"] == mission.lane_branches["WP02"] != mission.lane_branches["WP03"], "lane-b (WP01+WP02) must depend on lane-a (WP03)")

    result, advanced = _resume_after_interruption(mission, _advance_dependency_and_merge("WP03", "WP01"), "WP03", frozen_wps=("WP03",))

    _assert_refused_naming(result, advanced[:7], "lane-b carries WP01")


@intended("f", "FR-015", "WP18")
def test_resume_approved_bound_reads_frozen_anchors(tmp_path: Path) -> None:
    """US4-5, FR-015: a lane that is not mixed, whose dependency lane gained D after the interruption and then merged it, refuses D.

    lane-a (WP01) gains D and lane-b (WP02) merges it. With frozen anchors D is not exempt on lane-b, so ``LANE_MOVED_AFTER_APPROVAL``
    names lane-b / WP02. Today the live lane-a tip exempts D on lane-b and only lane-a (WP01) is refused.
    """
    mission = _template(tmp_path, "dependency_chain")
    with fixture_phase():
        cs.set_window_states(mission, "recorded")
    require(not mission.canceled_wps, "the dependent lane must not be mixed")
    require(mission.lane_branches["WP01"] != mission.lane_branches["WP02"], "WP02 must sit on its own lane, depending on lane-a")

    result, advanced = _resume_after_interruption(mission, _advance_dependency_and_merge("WP01", "WP02"), "WP01", frozen_wps=("WP01",))

    _assert_refused_naming(result, advanced[:7], "lane-b carries WP02")


#: Codes that are cleanup noise printed beside a passing landing, not part of any verdict (the corpus records them too).
_NOISE_CODES = frozenset({"WORKTREE_TIP_MOVED", "NOT_LANDED_ON_NAMED_REMOTE"})


def _verdict(result: cs.CellResult) -> tuple[int, str, tuple[str, ...]]:
    return result.exit_code, result.status, tuple(code for code in result.codes if code not in _NOISE_CODES)


def test_resume_fully_canceled_lane_reads_frozen_anchors(tmp_path: Path) -> None:
    """NFR-002 (g), FR-015: the flip is UNREACHABLE at verdict level, so this pins the reachable consequence (no ``xfail``).

    What the fully-canceled-lane content check reads from the live dependency lane is the canceled lane's own commits
    (``_fully_canceled_lane_own_commits``), subtracted from the approved claim. A canceled lane's advance can change a verdict
    only through a lane that CARRIES the new commit D, and an interrupted run's claim is taken after every approval, so D
    reaches a carrier after that carrier's approval stamp. A fully-canceled lane is never an anchor, so the approved bound
    refuses D on the carrier with or without frozen anchors, before the canceled-lane check could differ. The one remaining
    route, re-approving the carrier after D, would make the frozen set LESS strict (D counted as the carrier's own authorship)
    and is not an intended behaviour: it needs an operator ruling, not a pin.

    There is also no frozen tip to read for the canceled lane itself: ``_capture_pre_interrupt_lane_tips`` skips a fully-canceled
    lane, so ``pre_interrupt_lane_tips`` holds only the dependent lane (lane-b); the canceled lane keeps the live read FR-015
    names a degraded anchor.

    So the reachable consequence, true today and after FR-015:

    - an advance of the canceled lane the dependent lane never merged leaves the resume verdict equal to the resume of the same
      Mission without the advance;
    - when the dependent lane merged D, the resume refuses ``LANE_MOVED_AFTER_APPROVAL`` naming lane-b / WP02.
    """
    template = "fully_canceled_dependency"

    unmoved = _template(tmp_path / "unmoved", template)
    advanced = _template(tmp_path / "advanced", template)
    merged = _template(tmp_path / "merged", template)
    for mission in (unmoved, advanced, merged):
        with fixture_phase():
            cs.set_window_states(mission, "recorded")
    separate_lanes = unmoved.lane_branches["WP01"] != unmoved.lane_branches["WP02"]
    require(set(unmoved.canceled_wps) == {"WP01"} and separate_lanes, "WP01 must be a fully-canceled dependency lane of WP02")

    baseline, _ = _resume_after_interruption(unmoved, None, "WP01", frozen_wps=("WP02",))
    moved, _ = _resume_after_interruption(advanced, _advance_without_merge("WP01"), "WP01", frozen_wps=("WP02",))
    carried, carried_sha = _resume_after_interruption(merged, _advance_dependency_and_merge("WP01", "WP02"), "WP01", frozen_wps=("WP02",))

    assert baseline.exit_code == 0, f"the control resume must pass:\n{baseline.output}"
    assert _verdict(moved) == _verdict(baseline), f"an unmerged canceled-lane advance must not change the verdict:\n{moved.output}"
    _assert_refused_naming(carried, carried_sha[:7], "lane-b carries WP02")


# --------------------------------------------------------------------------- T028: forecast inputs (h)


def _canceled_wp_without_attribution(tmp_path: Path) -> cs.ShapeMission:
    """A mixed lane (approved WP01 + canceled WP02) whose canceled WP has no commit attribution: the fresh run refuses at claim time."""
    with fixture_phase():
        built = build_coord_mission_mixed_lane_canceled(
            tmp_path / "m",
            canceled_changes=(PlantedChange("src/canceled/c.py", "CANCELED = True\n"),),
            survivor_before=(PlantedChange(WP01_PATH, "def wp01() -> int:\n    return 1\n"),),
            stamp_attribution=False,
            mid8="01M6Y2Z1",
        )
        return cs._from_coord(built, "coord", subject_wp="WP01", window_wps=("WP01",))


@intended("h", "FR-013", "WP17")
def test_forecast_uses_fresh_run_excluded_canceled_set(tmp_path: Path) -> None:
    """US5-3, FR-013: on an unmutated Mission the forecast reports the fresh run's claim-time refusal of the excluded canceled work package.

    The fresh run builds the claim with WP02 as an excluded canceled work package and refuses it at claim time
    (``canceled WP02 cannot be attributed``). Today the forecast passes no excluded set, so WP02 is invisible to it: it refuses
    only on the approval stamp and never names the canceled work package.
    """
    template = _canceled_wp_without_attribution(tmp_path)
    fresh = cs.copy_mission(template, tmp_path / "fresh")
    forecast = cs.copy_mission(template, tmp_path / "forecast")
    refusal = "canceled WP02 cannot be attributed"

    fresh_result = _run(fresh, "fresh")
    require(fresh_result.exit_code != 0 and refusal in fresh_result.output, f"the fresh run must refuse WP02's attribution at claim time:\n{fresh_result.output}")
    forecast_result = _run(forecast, "forecast")

    assert forecast_result.exit_code != 0, forecast_result.output
    assert refusal in forecast_result.output, f"the forecast must report the fresh run's claim-time refusal:\n{forecast_result.output}"


@intended("h", "FR-013", "WP17")
def test_forecast_resolves_coordination_base_to_fresh_run_sha(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-013: the forecast resolves its coordination base to a SHA, the one the fresh run resolves.

    A forecast and a fresh run on one unmutated Mission cannot be told apart by verdict here: both see the same tip. The divergence
    is in the claim input itself, so this observes the ``coord_base_ref`` each passes to ``build_approved_wp_set``. The fresh run
    passes the pre-mutation coordination SHA; today the forecast passes the live branch NAME.
    """
    template = _template(tmp_path, "single_lane")
    fresh = cs.copy_mission(template, tmp_path / "fresh")
    forecast = cs.copy_mission(template, tmp_path / "forecast")
    real = reconciliation.build_approved_wp_set
    signature = inspect.signature(real)
    seen: list[str] = []

    def _spy(*args: Any, **kwargs: Any) -> Any:
        seen.append(str(signature.bind(*args, **kwargs).arguments["coord_base_ref"]))
        return real(*args, **kwargs)

    setattr_reconciliation_family(monkeypatch, "build_approved_wp_set", _spy)

    _run(fresh, "fresh")
    require(bool(seen) and bool(_FROZEN_SHA.fullmatch(seen[0])), f"the fresh run must build its claim from a coordination SHA, saw {seen}")
    fresh_base = seen[0]
    seen.clear()
    _run(forecast, "forecast")
    require(bool(seen), "the forecast must build a claim")

    assert _FROZEN_SHA.fullmatch(seen[0]), f"the forecast must resolve its coordination base to a SHA, it passed {seen[0]!r}"
    assert seen[0] == fresh_base, "the forecast's coordination base must equal the SHA the fresh run resolves"


# --------------------------------------------------------------------------- T029: parallel claims, a named residual (WW-6)


def _build_parallel_claims(tmp_path: Path) -> tuple[cs.ShapeMission, str]:
    """WP01 and WP02 on ONE lane, WP02 claimed (and parked, never returned to ``planned``) before WP01 commits; a stray commit between their work."""
    with fixture_phase():
        mission, manifest = cs._bootstrap_one_lane_coord(tmp_path, mid8="01M6Y2W3", wps=("WP01", "WP02"))
        slug = mission.slug
        tree, branch = allocate_lane_worktree(mission.repo, slug, "WP01", manifest)
        for lane in ("planned", "claimed", "in_progress"):
            transition(mission, "WP01", lane, actor=ACTOR)
        transition(mission, "WP02", "planned", actor=ACTOR)
        transition(mission, "WP02", "claimed", actor=ACTOR)
        _commit_in(tree, WP01_PATH, "def wp01() -> int:\n    return 1\n", f"feat({slug}): WP01 work")
        _approve(mission, "WP01", reference="review-WP01")
        stray = _commit_in(tree, cs.STRAY_PATH, "STRAY = True\n", f"feat({slug}): unreviewed change between the two work packages")
        tree, branch = allocate_lane_worktree(mission.repo, slug, "WP02", manifest)
        transition(mission, "WP02", "in_progress", actor=ACTOR)
        _commit_in(tree, WP02_PATH, "def wp02() -> int:\n    return 2\n", f"feat({slug}): WP02 work")
        _approve(mission, "WP02", reference="review-WP02")
        mission.lane_branches.update({"WP01": branch, "WP02": branch})
        shaped = cs._from_coord(mission, "coord", subject_wp="WP02", window_wps=("WP01", "WP02"))
        cs.set_window_states(shaped, "recorded")
    return shaped, str(stray)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "named residual WW-6 (ADR 2026-11-08-2-work-package-windows-are-recorded-at-the-opening-transition): "
        "a work package claimed early and parked has an over-wide window that covers a stray commit between two work packages; "
        "not removed by this Mission"
    ),
)
def test_parallel_claims_window_is_not_over_wide(tmp_path: Path) -> None:
    """Ideal verdict: the stray commit between WP01's and WP02's work is refused although WP02 claimed before WP01 committed.

    WP02's window opens at its first opener, before WP01's work, so it covers the stray commit. The window model keeps that
    commit covered (WW-6): this is a named residual, kept visible here and never flipped by this Mission.
    """
    mission, stray = _build_parallel_claims(tmp_path)
    claimed, in_progress = (_require_recorded(mission, "WP02")[i] for i in (0, -1))
    require(claimed != in_progress, "WP02 must have claimed before WP01 committed and started work after the stray commit")
    require(_is_ancestor(mission, claimed, stray) and not _is_ancestor(mission, stray, claimed), "WP02's window must open before the stray commit")
    before = _branch_tips(mission)

    result = _run(mission, "fresh")

    _assert_refused_naming(result, stray[:7])
    assert _branch_tips(mission) == before, "the refusal must not move any branch"
