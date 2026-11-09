"""A ``consolidate --resume`` reads ONE frozen anchor set (FR-015, NFR-002 (e)(f)(g), US4, WP18).

The fresh run freezes every lane's tip in ``state.json`` (``pre_interrupt_lane_tips``) before the first
branch moves. Before FR-015 the resume still anchored the closed world and the approved bound on the LIVE
dependency-lane branch names, so a dependency lane that gained a commit D after the interruption exempted D
on every lane that merged it. Every test here reaches a real interrupted state with the SIGKILL driver
(``resume_frozen_anchors_support``), checks the frozen record before resuming, and resumes in process.
"""

from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from rich.console import Console

from specify_cli.consolidation import claim_inputs as ci
from specify_cli.consolidation import executor, phase_claim, phase_gate
from specify_cli.consolidation import reconciliation_canceled as rc
from specify_cli.consolidation.claim_inputs import ClaimInputContext, ClaimInputSource, claim_inputs, frozen_dependency_tips
from specify_cli.consolidation.config import MergeStrategy
from specify_cli.consolidation.reconciliation import _closed_world_anchors
from specify_cli.consolidation.state import ConsolidationState
from specify_cli.lanes.compute import lane_created_branch
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from tests.consolidation import characterization_support as cs
from tests.consolidation import resume_frozen_anchors_support as rfa

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

#: Cleanup noise printed beside a passing landing, never part of a verdict (the corpus records it too).
_NOISE_CODES = frozenset({"WORKTREE_TIP_MOVED", "NOT_LANDED_ON_NAMED_REMOTE"})


def _verdict(result: cs.CellResult) -> tuple[int, str, tuple[str, ...]]:
    return result.exit_code, result.status, tuple(code for code in result.codes if code not in _NOISE_CODES)


def _fresh_verdict_on_copy(mission: cs.ShapeMission, dest: Path, *extra: str) -> cs.CellResult:
    """The fresh run's verdict on a copy of *mission* taken before any interruption."""
    with rfa.fixture_phase():
        copy = cs.copy_mission(mission, dest)
    return cs.run_in_process(copy, cs.consolidate_args(copy, "fresh", *extra))


# --------------------------------------------------------------------------- T091: the fixtures reach a frozen interrupted state


@pytest.mark.parametrize(
    ("build", "dependency_wp"),
    [
        pytest.param(rfa.build_mixed_lane_with_dependency, "WP03", id="e"),
        pytest.param(rfa.build_bound_lane_with_dependency, "WP01", id="f"),
        pytest.param(rfa.build_canceled_lane_on_approved_dependency, "WP01", id="g"),
    ],
)
def test_fixture_reaches_frozen_state(tmp_path: Path, build: rfa.Builder, dependency_wp: str) -> None:
    """The kill leaves a record that froze the dependency lane, and an undisturbed resume reaches the fresh verdict (US4-4)."""
    mission = build(tmp_path)
    fresh = _fresh_verdict_on_copy(mission, tmp_path / "fresh-copy")

    frozen = rfa.frozen_resume_state(mission, dependency_wp)
    assert frozen == cs._git(mission.repo, "rev-parse", mission.lane_branches[dependency_wp])
    resumed = rfa.resume(mission)

    assert _verdict(resumed) == _verdict(fresh), f"fresh:\n{fresh.output}\nresume:\n{resumed.output}"


def test_attested_fixture_reaches_frozen_state(tmp_path: Path) -> None:
    """The attestation fixture: the first run records the attestation, then is killed after the claim; the record froze lane-a."""
    mission = rfa.build_attested_bound_lane_with_dependency(tmp_path)
    log_before = rfa.attestation_count(mission, "WP02")

    rfa.frozen_resume_state(mission, "WP01", *rfa.attest_args("WP02", "first: read every line of lane-b"))

    assert rfa.attestation_count(mission, "WP02") == log_before + 1, "the interrupted run must have recorded the attestation"


# --------------------------------------------------------------------------- shared verdict observations


def _line_naming(output: str, marker: str) -> str:
    """The one output line that carries *marker* (a lane's refusal line), or ``""``."""
    return next((line for line in output.splitlines() if marker in line), "")


def _assert_nothing_moved(mission: cs.ShapeMission, tips: dict[str, str], logs: dict[str, list[str]]) -> None:
    assert rfa.branch_tips(mission) == tips, "a refused resume must move no branch"
    assert rfa.reflogs(mission) == logs, "nothing may have been moved and restored (a restore leaves a reflog entry)"


# --------------------------------------------------------------------------- T092: closed world (NFR-002 e, consumer 1)


def test_resume_closed_world_does_not_exempt_a_post_interrupt_dependency_commit(tmp_path: Path) -> None:
    """US4-3, FR-015: the mixed-lane closed world reads the FROZEN dependency-lane tip on a resume.

    Mixed lane-b (approved WP01 + canceled WP02) depends on lane-a (WP03). After the interruption lane-b gains D and
    lane-a merges lane-b, so lane-a's LIVE tip reaches D while the tip the interrupted run froze does not. D sits on
    lane-b's first-parent spine as a non-merge commit outside every WP window: with the frozen anchor the closed world
    refuses it (``commit_outside_windows``). With the live lane-a branch as an anchor D was exempt.
    """
    mission = rfa.build_mixed_lane_with_dependency(tmp_path)
    rfa.frozen_resume_state(mission, "WP03")
    advanced = rfa.advance_lane_into_dependency(mission, "WP01", dependency_wp="WP03")
    tips, logs = rfa.branch_tips(mission), rfa.reflogs(mission)

    result = rfa.resume(mission)

    assert result.exit_code == 1, result.output
    closed_world = _line_naming(result.output, "mixed lane lane-b: canceled WP02 cannot be attributed")
    assert "outside every WP's recorded work window" in closed_world, f"the closed world must refuse lane-b:\n{result.output}"
    assert advanced[:10] in closed_world, f"the closed-world refusal must name D ({advanced[:10]}):\n{result.output}"
    assert rfa.ADVANCED_PATH in closed_world
    _assert_nothing_moved(mission, tips, logs)


# --------------------------------------------------------------------------- T093: approved bound (NFR-002 f, consumer 2)


def test_resume_approved_bound_refuses_a_post_interrupt_dependency_commit(tmp_path: Path) -> None:
    """US4-5, FR-015: the approved bound reads the FROZEN dependency-lane tip on a resume.

    lane-b (approved WP02, not mixed) depends on lane-a (WP01). After the interruption lane-a gains D and lane-b merges
    it. The merge commit is dropped by the bound (``content_commits``), so D is the commit lane-b holds beyond its
    approval stamp: ``LANE_MOVED_AFTER_APPROVAL`` names lane-b / WP02 and D. With the live lane-a branch as an anchor D
    was exempt on lane-b and only lane-a was refused.
    """
    mission = rfa.build_bound_lane_with_dependency(tmp_path)
    rfa.frozen_resume_state(mission, "WP01")
    advanced = rfa.advance_dependency_lane(mission, "WP01", merge_into="WP02")
    tips, logs = rfa.branch_tips(mission), rfa.reflogs(mission)

    result = rfa.resume(mission)

    assert result.exit_code == 1, result.output
    assert "LANE_MOVED_AFTER_APPROVAL" in result.output, result.output
    lane_b = _line_naming(result.output, "(lane-b carries WP02)")
    assert advanced[:7] in lane_b, f"lane-b must be refused naming D ({advanced[:7]}):\n{result.output}"
    _assert_nothing_moved(mission, tips, logs)


def test_fresh_run_on_the_same_fixture_keeps_its_verdict(tmp_path: Path) -> None:
    """Control: a fresh run on the (f) fixture, before any kill and without the advance, keeps the golden fresh verdict."""
    mission = rfa.build_bound_lane_with_dependency(tmp_path)
    golden = cs.load_golden()[cs.cell_key("fresh", "dependency_chain", "present", "recorded")]

    fresh = _fresh_verdict_on_copy(mission, tmp_path / "fresh-copy")

    assert (fresh.exit_code, fresh.status) == (golden["exit_code"], golden["status"]), fresh.output
    assert [code for code in fresh.codes if code not in _NOISE_CODES] == [code for code in golden["codes"] if code not in _NOISE_CODES]


# --------------------------------------------------------------------------- T094: fully-canceled lane (NFR-002 g, consumer 3)


def test_resume_fully_canceled_lane_flip_is_unreachable(tmp_path: Path) -> None:
    """NFR-002 (g), FR-015: UNREACHABLE at verdict level; this pins the reachable consequence, identical before and after FR-015.

    Consumer 3, ``_fully_canceled_lane_own_commits``, computes a fully-canceled lane C's own commits through
    ``lane_own_commits(..., _closed_world_anchors(C))``, whose anchors are C's approved dependency lane A plus the target
    base. A post-interruption advance can shrink C's own commits only when A's tip comes to reach them, i.e. when A
    merges C. But then C's commits and A's new commit D lie on A after A's approval stamp, and a fully-canceled lane
    contributes neither an approval-stamp anchor nor a closed-world anchor, so the approved bound refuses lane A at claim
    time (``LANE_MOVED_AFTER_APPROVAL`` naming C's commit and D), with live and frozen anchors alike: A's own anchors
    did not move. That refusal stops the claim before the gate-time canceled-dependency content check, the only reader of
    C's own commits a frozen anchor would change. The only true flip needs A re-approved over C's merged commits, which a
    fresh run on the same final state lets through as well: not an FR-015 verdict (WP05's (g) pin, operator ruling).
    """
    mission = rfa.build_canceled_lane_on_approved_dependency(tmp_path)
    canceled_commit = cs._git(mission.repo, "rev-list", "-1", mission.lane_branches["WP02"], "--", "src/pkg/wp02.py")
    rfa.frozen_resume_state(mission, "WP01")
    advanced = rfa.advance_dependency_lane(mission, "WP01", merge_into=None)
    with rfa.fixture_phase(), cs.lane_checkout(mission, mission.lane_branches["WP01"]) as lane_a:
        cs._git(lane_a, "merge", "-q", "--no-ff", "--no-edit", mission.lane_branches["WP02"])
    tips, logs = rfa.branch_tips(mission), rfa.reflogs(mission)

    result = rfa.resume(mission)

    assert result.exit_code == 1, result.output
    assert "LANE_MOVED_AFTER_APPROVAL" in result.output, result.output
    lane_a_line = _line_naming(result.output, "(lane-a carries WP01)")
    assert advanced[:7] in lane_a_line and canceled_commit[:7] in lane_a_line, f"lane-a must be refused naming D and C's commit:\n{result.output}"
    assert "(lane-b carries" not in result.output, "the fully-canceled lane C is never a bounded lane"
    _assert_nothing_moved(mission, tips, logs)


# --------------------------------------------------------------------------- T094: approved-reviewed attestation (consumer 4)


def test_resume_attestation_check_reads_the_frozen_dependency_tip(tmp_path: Path) -> None:
    """FR-015, CI-5: a repeated ``--attest-approved-reviewed`` on a resume reads the frozen dependency-lane tip.

    lane-b (WP02, depends on lane-a) is attested on the interrupted first run. After the kill lane-a gains D and lane-b
    merges it, so lane-b moved past that attestation by D. The repeat must be refused (``cannot be repeated for WP02``)
    with nothing recorded. With lane-a's live branch as an anchor D was exempt and the repeat was accepted, re-bounding
    lane-b over D.
    """
    mission = rfa.build_attested_bound_lane_with_dependency(tmp_path)
    rfa.frozen_resume_state(mission, "WP01", *rfa.attest_args("WP02", "first: read every line of lane-b"))
    advanced = rfa.advance_dependency_lane(mission, "WP01", merge_into="WP02")
    log_before = rfa.committed_event_log(mission)
    tips = rfa.branch_tips(mission)

    result = rfa.resume(mission, *rfa.attest_args("WP02", "again"))

    assert result.exit_code == 1, result.output
    assert "cannot be repeated for WP02" in result.output, f"the repeat attestation must be refused (D={advanced[:7]}):\n{result.output}"
    assert rfa.committed_event_log(mission) == log_before, "a refused attestation records nothing"
    assert rfa.branch_tips(mission) == tips


# --------------------------------------------------------------------------- T095: the one frozen anchor set, unit level

_REPO = Path("/nonexistent/repo")
_TARGET = "a" * 40
_FROZEN_A = "1" * 40
_FROZEN_B = "2" * 40


def _lane(lane_id: str, wp_ids: tuple[str, ...], depends: tuple[str, ...] = ()) -> ExecutionLane:
    return ExecutionLane(lane_id=lane_id, wp_ids=wp_ids, write_scope=("src/**",), predicted_surfaces=(), depends_on_lanes=depends, parallel_group=len(depends))


def _manifest() -> LanesManifest:
    """lane-c depends on lane-b, lane-b on lane-a (transitive), and on the planning lane."""
    return LanesManifest(
        version=1,
        mission_slug="m-01ABCDEF",
        mission_id="01ABCDEF" + "0" * 18,
        mission_branch="kitty/mission-m-01ABCDEF",
        target_branch="main",
        lanes=[
            _lane("lane-planning", ("WP00",)),
            _lane("lane-a", ("WP01",)),
            _lane("lane-b", ("WP02",), ("lane-a",)),
            _lane("lane-c", ("WP03",), ("lane-b", "lane-planning")),
        ],
        computed_at="2026-11-09T00:00:00+00:00",
        computed_from="test",
    )


_MANIFEST = _manifest()
_BRANCH_A = lane_created_branch(_MANIFEST, "lane-a")
_BRANCH_B = lane_created_branch(_MANIFEST, "lane-b")
_LANE_C = _MANIFEST.lanes[3]


def test_closed_world_anchors_substitute_frozen_tips() -> None:
    anchors = _closed_world_anchors(_MANIFEST, _LANE_C, _TARGET, excluded_canceled_wp_ids=frozenset(), frozen_tips={_BRANCH_A: _FROZEN_A, _BRANCH_B: _FROZEN_B})

    assert anchors == [_FROZEN_A, _FROZEN_B, _TARGET], "every dependency lane (transitive) reads its frozen tip; the planning lane stays out"


def test_closed_world_anchors_keep_live_name_without_a_frozen_tip() -> None:
    """A degraded anchor: a dependency lane the record froze no tip for keeps the live branch name."""
    anchors = _closed_world_anchors(_MANIFEST, _LANE_C, _TARGET, excluded_canceled_wp_ids=frozenset(), frozen_tips={_BRANCH_B: _FROZEN_B})

    assert anchors == [_BRANCH_A, _FROZEN_B, _TARGET]


def test_closed_world_anchors_without_frozen_tips_are_unchanged() -> None:
    live = _closed_world_anchors(_MANIFEST, _LANE_C, _TARGET, excluded_canceled_wp_ids=frozenset())

    assert live == [_BRANCH_A, _BRANCH_B, _TARGET]
    assert _closed_world_anchors(_MANIFEST, _LANE_C, _TARGET, excluded_canceled_wp_ids=frozenset(), frozen_tips={}) == live


def test_closed_world_anchors_keep_the_fully_canceled_exclusion_with_frozen_tips() -> None:
    frozen = {_BRANCH_A: _FROZEN_A, _BRANCH_B: _FROZEN_B}
    anchors = _closed_world_anchors(_MANIFEST, _LANE_C, None, excluded_canceled_wp_ids=frozenset({"WP01"}), frozen_tips=frozen)

    assert anchors == [_FROZEN_B], "a fully-canceled dependency lane is no anchor, frozen tip or not"


def _state(tips: dict[str, str]) -> ConsolidationState:
    state = ConsolidationState(mission_id="m", mission_slug="m", target_branch="main", wp_order=[])
    state.pre_mutation_target_sha = _TARGET
    state.pre_mutation_coord_sha = "c" * 40
    state.pre_interrupt_lane_tips = dict(tips)
    return state


def _saved(tips: dict[str, str], excluded: frozenset[str] = frozenset()) -> ci.ClaimInputs:
    context = ClaimInputContext(
        repo_root=_REPO,
        manifest=_MANIFEST,
        status_dir=_REPO / "status",
        strategy="squash",
        resolved_target_base=_TARGET,
        state=_state(tips),
        excluded_canceled_wp_ids=excluded,
    )
    return claim_inputs(ClaimInputSource.SAVED, context)


def test_saved_dependency_anchors_are_the_frozen_tips(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ci, "capture_branch_tip", lambda *_a: pytest.fail("a frozen dependency lane must not be read live (CI-3)"))

    inputs = _saved({_BRANCH_A: _FROZEN_A, _BRANCH_B: _FROZEN_B})

    assert dict(inputs.dependency_anchors) == {_BRANCH_A: _FROZEN_A, _BRANCH_B: _FROZEN_B}
    assert inputs.degraded_dependency_anchors == ()
    assert frozen_dependency_tips(inputs) == inputs.dependency_anchors


def test_saved_dependency_lane_missing_from_the_record_is_a_named_degraded_anchor(monkeypatch: pytest.MonkeyPatch) -> None:
    """WP09 review (b): a dependency lane with no frozen tip is never dropped: it is read live and named."""
    monkeypatch.setattr(ci, "capture_branch_tip", lambda _repo, branch: f"live-{branch}")

    inputs = _saved({_BRANCH_B: _FROZEN_B})

    assert dict(inputs.dependency_anchors) == {_BRANCH_A: f"live-{_BRANCH_A}", _BRANCH_B: _FROZEN_B}
    assert inputs.degraded_dependency_anchors == (_BRANCH_A,)


def test_saved_degraded_anchor_that_does_not_resolve_is_left_to_the_live_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ci, "capture_branch_tip", lambda *_a: None)

    inputs = _saved({})

    assert dict(inputs.dependency_anchors) == {}, "no SHA: the closed world then reads the branch name, as a fresh run would"
    assert inputs.degraded_dependency_anchors == (_BRANCH_A, _BRANCH_B)


def test_saved_drops_a_dependency_lane_canceled_since_the_capture(monkeypatch: pytest.MonkeyPatch) -> None:
    """WP09 review (c): the current excluded set filters a lane that became fully canceled after its tip was frozen."""
    monkeypatch.setattr(ci, "capture_branch_tip", lambda *_a: pytest.fail("no live read is needed"))

    inputs = _saved({_BRANCH_A: _FROZEN_A, _BRANCH_B: _FROZEN_B}, excluded=frozenset({"WP01"}))

    assert dict(inputs.dependency_anchors) == {_BRANCH_B: _FROZEN_B}
    assert inputs.degraded_dependency_anchors == ()


@pytest.mark.parametrize("source", [ClaimInputSource.LIVE, ClaimInputSource.LIVE_THEN_SAVED])
def test_fresh_run_and_forecast_pass_no_frozen_set(monkeypatch: pytest.MonkeyPatch, source: ClaimInputSource) -> None:
    monkeypatch.setattr(ci, "capture_branch_tip", lambda _repo, branch: f"live-{branch}")
    monkeypatch.setattr(ci, "acceptably_canceled_wp_ids", lambda *_a: set())
    monkeypatch.setattr(ci, "_live_coord_base", lambda _context: "c" * 40)
    context = ClaimInputContext(repo_root=_REPO, manifest=_MANIFEST, status_dir=_REPO / "status", strategy="squash", resolved_target_base=_TARGET)

    inputs = claim_inputs(source, context)

    assert frozen_dependency_tips(inputs) is None
    assert inputs.degraded_dependency_anchors == ()
    assert dict(inputs.dependency_anchors) == {_BRANCH_A: f"live-{_BRANCH_A}", _BRANCH_B: f"live-{_BRANCH_B}"}


def _captured_console(monkeypatch: pytest.MonkeyPatch, module: object) -> io.StringIO:
    sink = io.StringIO()
    monkeypatch.setattr(module, "console", Console(file=sink, width=400, color_system=None))
    return sink


def test_degraded_anchor_notice_names_each_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    sink = _captured_console(monkeypatch, phase_claim)

    phase_claim._print_degraded_dependency_anchors((_BRANCH_A, _BRANCH_B))

    text = sink.getvalue()
    assert repr(_BRANCH_A) in text and repr(_BRANCH_B) in text and "degraded anchor" in text


def test_no_degraded_anchor_prints_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    sink = _captured_console(monkeypatch, phase_claim)

    phase_claim._print_degraded_dependency_anchors(())

    assert sink.getvalue() == ""


def _resume_tips(monkeypatch: pytest.MonkeyPatch, state: ConsolidationState | None, requested: tuple[str, ...]) -> Any:
    monkeypatch.setattr(executor, "load_state", lambda _repo, _id: state)
    monkeypatch.setattr(ci, "capture_branch_tip", lambda _repo, branch: f"live-{branch}")
    return executor._resume_frozen_dependency_tips(_REPO, "m", _REPO / "status", _MANIFEST, frozenset(), requested=requested)


def test_attestation_reads_the_resume_records_frozen_tips(monkeypatch: pytest.MonkeyPatch) -> None:
    """WP09 review (d): the attestation check gets the SAVED claim inputs' anchor set, built before the claim phase."""
    tips = _resume_tips(monkeypatch, _state({_BRANCH_A: _FROZEN_A, _BRANCH_B: _FROZEN_B}), ("WP02",))

    assert dict(tips) == {_BRANCH_A: _FROZEN_A, _BRANCH_B: _FROZEN_B}


def test_attestation_reads_live_without_a_record_or_a_request(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _resume_tips(monkeypatch, None, ("WP02",)) is None, "a fresh run: its live tips are what the claim then freezes (CI-5)"
    assert _resume_tips(monkeypatch, _state({_BRANCH_A: _FROZEN_A}), ()) is None, "no --attest-approved-reviewed: nothing to read"


def test_gate_rebuild_reuses_the_claim_phase_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    """WP09 review (a): the gate's defensive rebuild reuses ``run.claim_inputs`` instead of resolving its inputs again."""
    monkeypatch.setattr(ci, "capture_branch_tip", lambda *_a: pytest.fail("the claim phase's inputs are reused, nothing is read"))
    claimed = _saved({_BRANCH_A: _FROZEN_A, _BRANCH_B: _FROZEN_B})
    seen: list[ci.ClaimInputs] = []

    def _build(_repo: Path, _manifest: LanesManifest, inputs: ci.ClaimInputs) -> str:
        seen.append(inputs)
        return "rebuilt"

    monkeypatch.setattr(phase_gate, "build_claim", _build)
    monkeypatch.setattr(phase_gate, "_gate_rebuild_inputs", lambda _run: pytest.fail("the gate must not resolve its own inputs"))
    run = SimpleNamespace(
        main_repo=_REPO, lanes_manifest=_MANIFEST, approved_wp_set=None, claim_inputs=claimed, dependency_ref_pins={}, strategy=MergeStrategy.MERGE
    )

    assert phase_gate._reconciliation_claim_for_gate(cast(Any, run)) == "rebuilt"
    assert seen == [claimed]


def _record_own_commit_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Replace ``_fully_canceled_lane_own_commits`` with a recorder that reports no canceled lane."""
    calls: list[dict[str, Any]] = []

    def _recorder(*_args: Any, **kwargs: Any) -> dict[str, frozenset[str]]:
        calls.append(kwargs)
        return {}

    monkeypatch.setattr(rc, "_fully_canceled_lane_own_commits", _recorder)
    return calls


def test_resume_fully_canceled_lane_commits_receive_the_frozen_tips(monkeypatch: pytest.MonkeyPatch) -> None:
    """Consumer 3 (FR-015): ``_fully_canceled_lane_commits`` hands a resume's frozen tips to the per-lane walk."""
    calls = _record_own_commit_calls(monkeypatch)
    frozen = {_BRANCH_A: _FROZEN_A}

    assert rc._fully_canceled_lane_commits(_REPO, _MANIFEST, frozenset(), "c" * 40, _TARGET, frozen_tips=frozen) == frozenset()

    assert calls == [{"frozen_tips": frozen}]


def test_resume_canceled_dependency_resolution_receives_the_frozen_tips(monkeypatch: pytest.MonkeyPatch) -> None:
    """The dependency-lane resolution forwards the query's frozen tips to the same per-lane walk."""
    calls = _record_own_commit_calls(monkeypatch)
    frozen = {_BRANCH_A: _FROZEN_A}
    query = rc._CanceledLaneQuery(
        repo_root=_REPO,
        feature_dir=_REPO / "kitty-specs" / "m",
        lanes_manifest=_MANIFEST,
        work_packages={},
        excluded_ids=frozenset(),
        coord_base_ref="c" * 40,
        planning_prefix=None,
        target_base=_TARGET,
        sb_window=None,
        frozen_tips=frozen,
    )

    resolution = rc._resolve_canceled_dependency_lanes(query)

    assert resolution.unapproved_commits == frozenset()
    assert calls == [{"frozen_tips": frozen}]
