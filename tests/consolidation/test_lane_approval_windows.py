"""Lane missions adopt the work-package window model (Mission consolidation-window-provenance-01M6Y84D, WP19).

FR-007, FR-008, FR-009, FR-021, FR-022, FR-023, NFR-002 (a)(b)(c-lanes), NFR-010. Every verdict is
observed through ``spec-kitty consolidate`` (fresh run) or ``consolidate --dry-run --json`` (the
forecast), run in process on a real repository whose status events were written by the real status
pipeline (WP07's ``wp_window`` capture), never by hand. Fixture work never asserts: :func:`require`
raises a ``RuntimeError``, so a broken fixture ERRORS instead of reading as a verdict.

The red tests (T097) fail on WP18's tip because no refusal is raised; the over-refusal guards (T098)
pass before and after the window model.
"""

from __future__ import annotations

import functools
import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from kernel.clock import parse_iso, timedelta
from specify_cli.consolidation import forecast as forecast_module
from specify_cli.consolidation import reconciliation_bound
from specify_cli.consolidation.approved_bound import check_lane, render_refusals
from specify_cli.consolidation.claim_inputs import ClaimInputs
from specify_cli.consolidation.reconciliation import approved_bound_refusal
from specify_cli.consolidation.reconciliation_bound import _bound_approved_wp_ids, _bound_lanes, approval_stamp_anchors
from specify_cli.consolidation.reconciliation_claim_types import ApprovedWpCommitSet
from specify_cli.consolidation.reconciliation_kernel import _ClaimEventLog, _closed_world_anchors, _is_bookkeeping, _lane_branch_for, _planning_prefix
from specify_cli.lanes.models import LanesManifest
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
from specify_cli.status import materialize_snapshot
from specify_cli.status import WP_WINDOW_KEY
from specify_cli.status.models import ReviewResult
from tests.consolidation import characterization_support as cs
from tests.consolidation.resume_frozen_anchors_support import fixture_phase, require
from tests.terminus.canceled_dependency_support import ACTOR, REVIEWER, WP01_PATH, WP02_PATH, _approve, _commit_in
from tests.terminus.conftest import CoordMission
from tests.terminus.mixed_lane_support import transition
from tests.terminus.post_approval_support import add_post_approval_commit, rework_and_reapprove, strip_approval_stamps
from tests.terminus.rollback_harness import ref_shas

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

MOVED = "LANE_MOVED_AFTER_APPROVAL"
STAMP_MISSING = "APPROVAL_STAMP_MISSING"
FORECAST_REFUSED = "CLAIM_REFUSED_FORECAST"
REVIEW_FIX_PATH = "src/pkg/review_fix.py"
WP02_REWORK_PATH = "src/pkg/wp02_rework.py"

# --------------------------------------------------------------------------- builders

ReviewFlow = Callable[[CoordMission, Path], None]


def _approve_with_fix_during_review(mission: CoordMission, tree: Path) -> None:
    """WP02 goes to review; the reviewer's fix is committed while it is ``in_review``; then it is approved."""
    transition(mission, "WP02", "for_review", actor=ACTOR, subtasks_complete=True)
    transition(mission, "WP02", "in_review", actor=REVIEWER)
    _commit_in(tree, REVIEW_FIX_PATH, "FIXED = True\n", f"fix({mission.slug}): reviewer fix during review")
    reference = "review-WP02"
    transition(
        mission,
        "WP02",
        "approved",
        actor=REVIEWER,
        review_ref=reference,
        review_result=ReviewResult(reviewer=REVIEWER, verdict="approved", reference=reference),
    )


def _reject_rework_reapprove(to_lane: str) -> ReviewFlow:
    """WP02 is rejected from ``in_review`` to *to_lane* (a review rejection, never a rewind), reworked and approved again."""

    def _flow(mission: CoordMission, tree: Path) -> None:
        transition(mission, "WP02", "for_review", actor=ACTOR, subtasks_complete=True)
        transition(mission, "WP02", "in_review", actor=REVIEWER)
        rejected = "review-WP02-rejected"
        transition(
            mission,
            "WP02",
            to_lane,
            actor=REVIEWER,
            review_ref=rejected,
            reason="changes requested",
            review_result=ReviewResult(reviewer=REVIEWER, verdict="changes_requested", reference=rejected),
        )
        if to_lane == "planned":
            transition(mission, "WP02", "claimed", actor=ACTOR)
            transition(mission, "WP02", "in_progress", actor=ACTOR)
        _commit_in(tree, WP02_REWORK_PATH, "REWORKED = True\n", f"feat({mission.slug}): WP02 rework")
        _approve(mission, "WP02", reference="review-WP02-rework")

    return _flow


def _build_two_wp_lane_with_review(tmp_path: Path, *, mid8: str, review: ReviewFlow) -> cs.ShapeMission:
    """``cs.build_two_wp_lane`` (no stray) whose WP02 review runs *review* instead of a plain approval."""
    mission, manifest = cs._bootstrap_one_lane_coord(tmp_path, mid8=mid8, wps=("WP01", "WP02"))
    slug = mission.slug
    tree, branch = allocate_lane_worktree(mission.repo, slug, "WP01", manifest)
    for lane in ("planned", "claimed", "in_progress"):
        transition(mission, "WP01", lane, actor=ACTOR)
    _commit_in(tree, WP01_PATH, "def wp01() -> int:\n    return 1\n", f"feat({slug}): WP01 work")
    _approve(mission, "WP01", reference="review-WP01")
    transition(mission, "WP02", "planned", actor=ACTOR)
    transition(mission, "WP02", "claimed", actor=ACTOR)
    tree, branch = allocate_lane_worktree(mission.repo, slug, "WP02", manifest)
    transition(mission, "WP02", "in_progress", actor=ACTOR)
    _commit_in(tree, WP02_PATH, "def wp02() -> int:\n    return 2\n", f"feat({slug}): WP02 work")
    review(mission, tree)
    mission.lane_branches.update({"WP01": branch, "WP02": branch})
    return cs._from_coord(mission, "coord", subject_wp="WP02", window_wps=("WP01", "WP02"))


CANCELED_AFTER_APPROVAL_PATH = "src/pkg/canceled_late.py"


def _build_canceled_commit_after_approval(tmp_path: Path, *, mid8: str) -> cs.ShapeMission:
    """#5720 on a recorded-window lane: WP01 approved, then WP02 claimed, commits C (after WP01's stamp) and is canceled."""
    mission, manifest = cs._bootstrap_one_lane_coord(tmp_path, mid8=mid8, wps=("WP01", "WP02"))
    slug = mission.slug
    tree, branch = allocate_lane_worktree(mission.repo, slug, "WP01", manifest)
    for lane in ("planned", "claimed", "in_progress"):
        transition(mission, "WP01", lane, actor=ACTOR)
    _commit_in(tree, WP01_PATH, "def wp01() -> int:\n    return 1\n", f"feat({slug}): WP01 work")
    _approve(mission, "WP01", reference="review-WP01")
    for lane in ("planned", "claimed", "in_progress"):
        transition(mission, "WP02", lane, actor=ACTOR)
    _commit_in(tree, CANCELED_AFTER_APPROVAL_PATH, "LATE = True\n", f"feat({slug}): WP02 work after WP01's approval, later canceled")
    transition(mission, "WP02", "canceled", actor=ACTOR, reason_source="operator", reason="operator: scope removed from mission")
    mission.lane_branches.update({"WP01": branch, "WP02": branch})
    mission.canceled_wps.add("WP02")
    return cs._from_coord(mission, "coord", subject_wp="WP01", window_wps=("WP01",))


_TEMPLATES: dict[str, Callable[[Path], cs.ShapeMission]] = {
    "plain": lambda d: cs.build_two_wp_lane(d, mid8="01M6Y9A0"),
    "stray": lambda d: cs.build_two_wp_lane(d, mid8="01M6Y9A1", stray_between=True),
    "rewound": lambda d: cs.build_two_wp_lane(d, mid8="01M6Y9A2", rewound=True),
    "dependency_chain_stray": lambda d: cs.build_dependency_chain_with_stray(d, mid8="01M6Y9A3"),
    "single_lane": lambda d: cs.build_shape(d, "single_lane"),
    "review_fix": lambda d: _build_two_wp_lane_with_review(d, mid8="01M6Y9A4", review=_approve_with_fix_during_review),
    "rejected_in_progress": lambda d: _build_two_wp_lane_with_review(d, mid8="01M6Y9A5", review=_reject_rework_reapprove("in_progress")),
    "rejected_planned": lambda d: _build_two_wp_lane_with_review(d, mid8="01M6Y9A6", review=_reject_rework_reapprove("planned")),
    "canceled_superseded": lambda d: cs.build_mixed_lane_shell_shape(d, mid8="01M6Y9A7", supersede=True),
    "canceled_unsuperseded": lambda d: cs.build_mixed_lane_shell_shape(d, mid8="01M6Y9A8", supersede=False),
    "canceled_after_approval": lambda d: _build_canceled_commit_after_approval(d, mid8="01M6Y9A9"),
}


class _Templates:
    """Each template is built once per module, on first use, and copied for every test (the original is never run)."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._built: dict[str, cs.ShapeMission] = {}

    def copy(self, name: str, dest: Path) -> cs.ShapeMission:
        if name not in self._built:
            with fixture_phase():
                self._built[name] = _TEMPLATES[name](self._root / name)
        return cs.copy_mission(self._built[name], dest / name)


@pytest.fixture(scope="module")
def templates(tmp_path_factory: pytest.TempPathFactory) -> Iterator[_Templates]:
    yield _Templates(tmp_path_factory.mktemp("lane-window-templates"))


# --------------------------------------------------------------------------- observations


def _git(mission: cs.ShapeMission, *args: str) -> str:
    with fixture_phase():
        return cs._git(mission.repo, *args)


def _is_ancestor(mission: cs.ShapeMission, ancestor: str, descendant: str) -> bool:
    return cs._try_git(mission.repo, "merge-base", "--is-ancestor", ancestor, descendant) is not None


def _last_commit_touching(mission: cs.ShapeMission, branch: str, path: str) -> str:
    sha = _git(mission, "rev-list", "-1", branch, "--", path)
    require(bool(sha), f"no commit on {branch} touches {path}")
    return sha


def _events(mission: cs.ShapeMission) -> list[dict[str, Any]]:
    with fixture_phase():
        return cs._events(mission)


def _approval_stamp(mission: cs.ShapeMission, wp_id: str) -> str:
    approvals = [event for event in _events(mission) if event.get("wp_id") == wp_id and event.get("to_lane") == "approved"]
    stamp = ((approvals[-1].get("policy_metadata") or {}).get("lane_head") if approvals else None) or ""
    require(bool(stamp), f"{wp_id} has no stamped approval")
    return str(stamp)


def _open_shas(mission: cs.ShapeMission, wp_id: str) -> list[str | None]:
    openers = [event for event in _events(mission) if cs._is_opening(event, wp_id)]
    return [((event.get("policy_metadata") or {}).get(WP_WINDOW_KEY) or {}).get("open_sha") for event in openers]


def _set_windows(mission: cs.ShapeMission, **states: str) -> None:
    with fixture_phase():
        for wp_id, state in states.items():
            cs.set_window_state(mission, wp_id, state)


def _fresh(mission: cs.ShapeMission, *extra: str) -> cs.CellResult:
    return cs.run_in_process(mission, cs.consolidate_args(mission, "fresh", *extra))


def _forecast(mission: cs.ShapeMission) -> tuple[cs.CellResult, dict[str, Any]]:
    result = cs.run_in_process(mission, cs.consolidate_args(mission, "forecast"))
    start, end = result.output.find("{"), result.output.rfind("}")
    require(start >= 0 and end > start, f"the forecast printed no JSON payload:\n{result.output}")
    payload: dict[str, Any] = json.loads(result.output[start : end + 1])
    return result, payload


def _refs(mission: cs.ShapeMission) -> dict[str, str]:
    return ref_shas(mission.coord_mission())


def _naming_line(output: str, short_sha: str) -> str:
    lines = [line for line in output.splitlines() if short_sha in line]
    return lines[0] if lines else ""


def _assert_refusal_names(output: str, sha: str, wp_id: str) -> None:
    """``LANE_MOVED_AFTER_APPROVAL`` is in *output*, and the line naming *sha*'s short form names *wp_id*."""
    assert MOVED in output, f"the run must refuse with {MOVED}:\n{output}"
    line = _naming_line(output, sha[:7])
    assert line, f"no output line names the commit {sha[:7]}:\n{output}"
    assert wp_id in line, f"the line naming {sha[:7]} must name {wp_id}:\n{line}"


def _stray_fixture(templates: _Templates, tmp_path: Path, *, wp01: str = "recorded") -> tuple[cs.ShapeMission, str]:
    """The US2 lane: WP01 approved (S1), stray X, WP02 opened after X and approved (S2); both share ONE lane."""
    mission = templates.copy("stray", tmp_path)
    _set_windows(mission, WP01=wp01, WP02="recorded")
    lane = mission.lane_branches["WP01"]
    stray = _last_commit_touching(mission, lane, cs.STRAY_PATH)
    require(_is_ancestor(mission, _approval_stamp(mission, "WP01"), stray), "X must come after WP01's approval stamp")
    require(_is_ancestor(mission, stray, _approval_stamp(mission, "WP02")), "X must be an ancestor of S2 (the own-lane stamp)")
    wp02_open = _open_shas(mission, "WP02")
    require(bool(wp02_open) and all(wp02_open), f"WP02's openers must carry wp_window.open_sha, got {wp02_open}")
    require(all(_is_ancestor(mission, stray, str(sha)) for sha in wp02_open), "WP02's recorded open_sha must reach X")
    require(set(mission.lane_branches.values()) == {lane}, "both work packages share ONE lane")
    return mission, stray


# --------------------------------------------------------------------------- T097: red-first


def test_stray_commit_between_two_approvals_refuses(templates: _Templates, tmp_path: Path) -> None:
    """US2-1: X, committed between WP01's approval and WP02's window, refuses naming X and WP01; no branch moves."""
    mission, stray = _stray_fixture(templates, tmp_path)
    before = _refs(mission)

    result = _fresh(mission)

    assert result.exit_code == 1, result.output
    _assert_refusal_names(result.output, stray, "WP01")
    assert _refs(mission) == before


def test_following_the_printed_window_recovery_leads_to_a_passing_run(templates: _Templates, tmp_path: Path) -> None:
    """M8: the recovery the refusal prints (send WP01 back, approve it again) clears it; it never advises a revert."""
    mission, _stray = _stray_fixture(templates, tmp_path)
    refused = _fresh(mission)
    assert refused.exit_code == 1, refused.output
    flat = " ".join(refused.output.split())
    assert "revert" not in flat, flat
    assert f"spec-kitty agent tasks move-task WP01 --to in_progress --mission {mission.slug}" in flat, flat

    coord = mission.coord_mission()
    transition(coord, "WP01", "in_progress", actor=ACTOR, review_ref="review-WP01-window-recovery")
    _approve(coord, "WP01", reference="review-WP01-window-recovery-approved")

    _assert_passes(_fresh(mission))


def test_stray_commit_between_two_approvals_forecast_refuses(templates: _Templates, tmp_path: Path) -> None:
    """US2-5: the ``--dry-run`` forecast refuses the same claim, with ``CLAIM_REFUSED_FORECAST``."""
    mission, stray = _stray_fixture(templates, tmp_path)
    before = _refs(mission)

    result, payload = _forecast(mission)

    assert result.exit_code == 1, result.output
    assert payload.get("error_code") == FORECAST_REFUSED, payload
    _assert_refusal_names(str(payload.get("error", "")), stray, "WP01")
    assert _refs(mission) == before


def test_own_lane_approval_stamp_does_not_exempt(templates: _Templates, tmp_path: Path) -> None:
    """US2-7, WW-2a: X is an ancestor of S2, the lane's OWN approval stamp; that stamp exempts nothing."""
    mission, stray = _stray_fixture(templates, tmp_path)
    require(_is_ancestor(mission, stray, _approval_stamp(mission, "WP02")), "X must be reachable from the own-lane stamp S2")
    before = _refs(mission)

    result = _fresh(mission)

    assert result.exit_code == 1, result.output
    _assert_refusal_names(result.output, stray, "WP01")
    assert _refs(mission) == before


def test_gap_then_recorded_stray_commit_refuses(templates: _Templates, tmp_path: Path) -> None:
    """NFR-002 (a) mixed, WW-7: WP01 has a gap (degraded to its stamp), WP02 is recorded after X; X lies in no window."""
    mission, stray = _stray_fixture(templates, tmp_path, wp01="not_recorded")
    require(not any(_open_shas(mission, "WP01")), "WP01 must carry no recorded open_sha")
    before = _refs(mission)

    fresh = _fresh(mission)
    forecast, payload = _forecast(mission)

    assert fresh.exit_code == 1, fresh.output
    _assert_refusal_names(fresh.output, stray, "WP01")
    assert forecast.exit_code == 1, forecast.output
    assert payload.get("error_code") == FORECAST_REFUSED, payload
    _assert_refusal_names(str(payload.get("error", "")), stray, "WP01")
    assert _refs(mission) == before


def test_rewound_wp_commit_from_abandoned_cycle_refuses(templates: _Templates, tmp_path: Path) -> None:
    """NFR-002 (c) lanes, FR-021: WP02 commits C1, is rewound to ``planned``, restarts and commits C2; C1 is refused, C2 is not named."""
    mission = templates.copy("rewound", tmp_path)
    _set_windows(mission, WP01="recorded", WP02="recorded")
    lane = mission.lane_branches["WP02"]
    abandoned = _last_commit_touching(mission, lane, cs.ABANDONED_PATH)
    work = _last_commit_touching(mission, lane, WP02_PATH)
    openers = [str(sha) for sha in _open_shas(mission, "WP02") if sha]
    require(len(openers) >= 4, f"WP02 must have two recorded cycles (claimed + in_progress twice), got {openers}")
    require(_is_ancestor(mission, abandoned, openers[-1]), "the cycle after the rewind opens after C1")
    require(not _is_ancestor(mission, work, openers[-1]), "the restarted cycle opens before C2")
    before = _refs(mission)

    result = _fresh(mission)

    assert result.exit_code == 1, result.output
    _assert_refusal_names(result.output, abandoned, "WP01")
    assert work[:7] not in result.output, f"C2 lies inside the restarted window and must not be named:\n{result.output}"
    assert _refs(mission) == before


# --------------------------------------------------------------------------- T098: over-refusal guards


def _assert_passes(result: cs.CellResult) -> None:
    assert result.exit_code == 0, result.output
    assert MOVED not in result.output, result.output


def test_same_fixture_without_stray_passes(templates: _Templates, tmp_path: Path) -> None:
    """US2-2: the same two approvals without X consolidate."""
    mission = templates.copy("plain", tmp_path)
    _set_windows(mission, WP01="recorded", WP02="recorded")

    _assert_passes(_fresh(mission))


def test_reviewer_fix_during_review_passes(templates: _Templates, tmp_path: Path) -> None:
    """US2-3: a fix committed while WP02 is ``in_review`` lies inside WP02's window (before its approval stamp)."""
    mission = templates.copy("review_fix", tmp_path)
    _set_windows(mission, WP01="recorded", WP02="recorded")
    fix = _last_commit_touching(mission, mission.lane_branches["WP02"], REVIEW_FIX_PATH)
    require(_is_ancestor(mission, fix, _approval_stamp(mission, "WP02")), "the review fix must precede WP02's approval stamp")

    _assert_passes(_fresh(mission))


@pytest.mark.parametrize("to_lane", ["in_progress", "planned"])
def test_rejected_and_reapproved_wp_passes(templates: _Templates, tmp_path: Path, to_lane: str) -> None:
    """US2-4, R-16: a review rejection (to ``in_progress`` or ``planned``) keeps the window; the rework lies inside it."""
    mission = templates.copy(f"rejected_{to_lane}", tmp_path)
    _set_windows(mission, WP01="recorded", WP02="recorded")
    require(len(_open_shas(mission, "WP02")) >= (4 if to_lane == "planned" else 2), "WP02 must have re-opened after the rejection")

    _assert_passes(_fresh(mission))


def test_dependency_chain_stray_is_exempt(templates: _Templates, tmp_path: Path) -> None:
    """US2-6, FR-007 exception: lane B merged lane A's tip (with X) and was approved; another lane's stamp exempts X."""
    mission = templates.copy("dependency_chain_stray", tmp_path)
    _set_windows(mission, WP01="recorded", WP02="recorded")
    stray = _last_commit_touching(mission, mission.lane_branches["WP01"], cs.STRAY_PATH)
    require(_is_ancestor(mission, stray, _approval_stamp(mission, "WP02")), "lane B's approval stamp must reach X")
    require(mission.lane_branches["WP01"] != mission.lane_branches["WP02"], "WP01 and WP02 must be on different lanes")

    _assert_passes(_fresh(mission))


def test_all_gap_lane_passes(templates: _Templates, tmp_path: Path) -> None:
    """US3-1: every work package has a gap and nothing late landed; the lane consolidates."""
    mission = templates.copy("plain", tmp_path)
    _set_windows(mission, WP01="not_recorded", WP02="not_recorded")

    _assert_passes(_fresh(mission))


def test_gap_wp_covers_stray_before_recorded_wp(templates: _Templates, tmp_path: Path) -> None:
    """US3-4, WW-7 weaker check: WP02's gap degrades its window to ``(claim base, S2]``, which covers X."""
    mission = templates.copy("stray", tmp_path)
    _set_windows(mission, WP01="recorded", WP02="not_recorded")

    _assert_passes(_fresh(mission))


def test_attested_approval_window_runs_to_attested_stamp(templates: _Templates, tmp_path: Path) -> None:
    """WW-4: a stripped stamp refuses ``APPROVAL_STAMP_MISSING`` unchanged; the attested stamp then closes WP02's window."""
    mission = templates.copy("plain", tmp_path)
    _set_windows(mission, WP01="recorded", WP02="recorded")
    with fixture_phase(), cs.deterministic_commit_dates(mission.repo):
        strip_approval_stamps(mission.coord_mission(), "WP02")

    refused = _fresh(mission)
    attested = _fresh(mission, "--attest-approved-reviewed", "WP02", "--attest-reason", "checked")

    assert refused.exit_code == 1, refused.output
    assert STAMP_MISSING in refused.output, refused.output
    _assert_passes(attested)


def test_skewed_clock_rework_does_not_narrow_window(templates: _Templates, tmp_path: Path) -> None:
    """FR-021, D-3: WP01's rework opener carries a clock 1 s before its claim; the topological first SHA still opens the window."""
    mission = templates.copy("single_lane", tmp_path)
    with fixture_phase():
        rework_and_reapprove(mission.coord_mission(), "WP01")
    claims = [e for e in _events(mission) if e.get("wp_id") == "WP01" and e.get("to_lane") == "claimed"]
    require(bool(claims), "WP01 must have a claim event")
    skewed = _shift_seconds(str(claims[0]["at"]), -1)

    def _skew(event: dict[str, Any]) -> dict[str, Any] | None:
        if event.get("wp_id") == "WP01" and event.get("to_lane") == "in_progress" and event.get("from_lane") == "approved":
            return {**event, "at": skewed}
        return None

    with fixture_phase():
        cs.rewrite_events(mission, _skew, "test: skew WP01's rework opener 1 s before its claim")
    require(any(e.get("at") == skewed for e in _events(mission)), "the rework opener must carry the skewed clock")
    _set_windows(mission, WP01="recorded", WP02="recorded")

    _assert_passes(_fresh(mission))


def test_leading_branch_missing_opener_is_skipped(templates: _Templates, tmp_path: Path) -> None:
    """US1-5: WP02's first opener recorded ``lane_branch_missing``; it is skipped and the next recorded opener opens the window."""
    mission = templates.copy("plain", tmp_path)
    _set_windows(mission, WP01="recorded", WP02="recorded")
    with fixture_phase():
        cs.set_window_state(mission, "WP02", "lane_branch_missing", openers=(0,))
    require(_open_shas(mission, "WP02")[0] is None and all(_open_shas(mission, "WP02")[1:]), "only WP02's first opener is a gap")

    _assert_passes(_fresh(mission))


def test_all_gap_lane_post_approval_refusal_keeps_todays_code(templates: _Templates, tmp_path: Path) -> None:
    """US3-2, FR-023: an all-gap lane with a commit after its approval refuses exactly as before (tier-1 code, one refusal)."""
    mission = templates.copy("single_lane", tmp_path)
    _set_windows(mission, WP01="not_recorded", WP02="not_recorded")
    with fixture_phase():
        late = add_post_approval_commit(mission.coord_mission())

    result = _fresh(mission)

    assert result.exit_code == 1, result.output
    assert MOVED in result.output and late[:7] in result.output, result.output


# --------------------------------------------------------------------------- R1: a canceled work package's own commits (operator ruling 2026-11-09)

CANCELED_CONTENT_FAIL = "carries canceled WP02's change"

#: The verdict on the parent of the window model (``eca56240cd^``, where WP01's own approval stamp
#: exempted C and the mixed-lane / canceled-content rules judged it), observed on this very fixture:
#: ``(fresh exit, fresh status, forecast exit, forecast status)``. The ruling keeps it.
_PRE_WINDOW_VERDICT = {
    "superseded": (0, "pass", 0, "pass"),
    "unsuperseded": (1, "fail", 0, "pass"),
}


def _first_commit_touching(mission: cs.ShapeMission, branch: str, path: str) -> str:
    commits = _git(mission, "rev-list", "--reverse", branch, "--", path).split()
    require(bool(commits), f"no commit on {branch} touches {path}")
    return commits[0]


def _canceled_commit_fixture(templates: _Templates, dest: Path, outcome: str) -> tuple[cs.ShapeMission, str]:
    """The probe lane: canceled WP02's commit C, then WP01 claimed (its recorded window opens after C), committed and approved."""
    mission = templates.copy(f"canceled_{outcome}", dest)
    lane = mission.lane_branches["WP01"]
    canceled = _first_commit_touching(mission, lane, cs.SHELL_CANCELED_PATH)
    wp01_open = _open_shas(mission, "WP01")
    require(bool(wp01_open) and all(wp01_open), f"WP01's openers must carry wp_window.open_sha, got {wp01_open}")
    require(all(_is_ancestor(mission, canceled, str(sha)) for sha in wp01_open), "C must predate WP01's recorded window")
    require(any(e.get("wp_id") == "WP02" and e.get("to_lane") == "canceled" for e in _events(mission)), "WP02 must be canceled")
    require(set(mission.lane_branches.values()) == {lane}, "both work packages share ONE lane")
    return mission, canceled


@pytest.mark.parametrize("outcome", ["superseded", "unsuperseded"])
def test_canceled_wp_commit_before_window_is_judged_by_the_canceled_rules(templates: _Templates, tmp_path: Path, outcome: str) -> None:
    """Operator ruling 2026-11-09: canceled WP02's own commit C, before WP01's window, is exempt from the window check (tier 2).

    The mixed-lane / canceled-content rules stay its sole judge, so the verdict is the one before the
    window model: superseded C consolidates; surviving C fails the canceled-content axis (rolled back),
    never ``LANE_MOVED_AFTER_APPROVAL`` (which named C "committed after WP01's approval", although C
    predates WP01's claim, and which no re-approval of WP01 could clear).
    """
    mission, canceled = _canceled_commit_fixture(templates, tmp_path / "fresh", outcome)
    twin, _ = _canceled_commit_fixture(templates, tmp_path / "forecast", outcome)
    before, twin_before = _refs(mission), _refs(twin)

    fresh = _fresh(mission)
    forecast, payload = _forecast(twin)

    assert MOVED not in fresh.output, fresh.output
    assert MOVED not in forecast.output, forecast.output
    assert payload.get("error_code") != FORECAST_REFUSED, payload
    assert (fresh.exit_code, fresh.status, forecast.exit_code, forecast.status) == _PRE_WINDOW_VERDICT[outcome], fresh.output
    if outcome == "unsuperseded":
        assert CANCELED_CONTENT_FAIL in fresh.output, fresh.output
        assert _refs(mission) == before
    assert _refs(twin) == twin_before
    assert canceled[:7] not in forecast.output


TIER_ONE_MARKER = "holds content committed after its approval stamp"


def test_canceled_wp_commit_after_approval_still_refuses_in_tier_one(templates: _Templates, tmp_path: Path) -> None:
    """#5720 pin: the ruling exempts canceled commits from tier 2 only; C after WP01's approval stamp still refuses in tier 1."""
    mission = templates.copy("canceled_after_approval", tmp_path)
    late = _first_commit_touching(mission, mission.lane_branches["WP01"], CANCELED_AFTER_APPROVAL_PATH)
    require(_is_ancestor(mission, _approval_stamp(mission, "WP01"), late), "C must come after WP01's approval stamp")
    require(all(_open_shas(mission, "WP01")), "WP01's window must be recorded (the lane reaches the window check)")
    before = _refs(mission)

    result = _fresh(mission)

    assert result.exit_code == 1, result.output
    assert MOVED in result.output and TIER_ONE_MARKER in result.output, result.output
    assert late[:7] in result.output, result.output
    assert _refs(mission) == before


def _shift_seconds(stamp: str, seconds: int) -> str:
    parsed = parse_iso(stamp.replace("Z", "+00:00"))
    return (parsed + timedelta(seconds=seconds)).isoformat()


# --------------------------------------------------------------------------- T101 / T102: the claim the run builds


@dataclass(frozen=True)
class _Built:
    """The claim a ``--dry-run`` built, with the exact inputs it was built from."""

    manifest: LanesManifest
    inputs: ClaimInputs
    claim: ApprovedWpCommitSet
    predicate_tips: tuple[str, ...]


def _forecast_claim(mission: cs.ShapeMission, monkeypatch: pytest.MonkeyPatch) -> _Built:
    """Run ``consolidate --dry-run --json`` and capture its claim, its inputs and every tip the window predicates were bound to."""
    captured: list[tuple[LanesManifest, ClaimInputs, ApprovedWpCommitSet]] = []
    tips: list[str] = []
    real_build, real_bind = forecast_module.build_claim, reconciliation_bound.bind_lane_predicates

    def _build(repo_root: Path, manifest: LanesManifest, inputs: ClaimInputs) -> ApprovedWpCommitSet:
        claim = real_build(repo_root, manifest, inputs)
        captured.append((manifest, inputs, claim))
        return claim

    def _bind(repo_root: Path, tip: str) -> Any:
        tips.append(tip)
        return real_bind(repo_root, tip)

    monkeypatch.setattr(forecast_module, "build_claim", _build)
    monkeypatch.setattr(reconciliation_bound, "bind_lane_predicates", _bind)
    _forecast(mission)
    require(len(captured) == 1, f"the forecast must build exactly one claim, built {len(captured)}")
    manifest, inputs, claim = captured[0]
    return _Built(manifest, inputs, claim, tuple(tips))


def _gaps(claim: ApprovedWpCommitSet) -> list[tuple[str, str]]:
    return [(gap.wp_id, gap.reason) for gap in claim.window_gaps]


def test_all_gap_lane_claim_lists_every_wp(templates: _Templates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """US3-1, FR-009: the passing claim names every work package of the all-gap lane, reason ``not recorded``."""
    mission = templates.copy("plain", tmp_path)
    _set_windows(mission, WP01="not_recorded", WP02="not_recorded")

    built = _forecast_claim(mission, monkeypatch)

    assert built.claim.refusal is None, built.claim.refusal
    assert _gaps(built.claim) == [("WP01", "not recorded"), ("WP02", "not recorded")]
    assert {gap.lane_id for gap in built.claim.window_gaps} == {"lane-a"}


def test_gap_wp_covering_stray_is_the_only_gap(templates: _Templates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """US3-4: WP01 recorded, WP02 a gap whose degraded window covers X; the claim passes and lists WP02 only."""
    mission = templates.copy("stray", tmp_path)
    _set_windows(mission, WP01="recorded", WP02="not_recorded")

    built = _forecast_claim(mission, monkeypatch)

    assert built.claim.refusal is None, built.claim.refusal
    assert _gaps(built.claim) == [("WP02", "not recorded")]


def test_leading_branch_missing_opener_leaves_no_gap(templates: _Templates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """US1-5: a skipped leading ``lane_branch_missing`` opener is not a gap when a later opener recorded a SHA."""
    mission = templates.copy("plain", tmp_path)
    _set_windows(mission, WP01="recorded", WP02="recorded")
    with fixture_phase():
        cs.set_window_state(mission, "WP02", "lane_branch_missing", openers=(0,))

    built = _forecast_claim(mission, monkeypatch)

    assert built.claim.refusal is None, built.claim.refusal
    assert built.claim.window_gaps == ()


def test_refused_claim_carries_the_window_gaps(templates: _Templates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T102: a claim the bound refused still carries its gaps (WP01's, in the gap-then-recorded stray lane)."""
    mission, _stray = _stray_fixture(templates, tmp_path, wp01="not_recorded")

    built = _forecast_claim(mission, monkeypatch)

    assert built.claim.refusal is not None and MOVED in built.claim.refusal
    assert _gaps(built.claim) == [("WP01", "not recorded")]


def test_approved_bound_refusal_matches_claim_refusal(templates: _Templates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-022: the ``orchestrator-api`` door yields the claim's refusal text byte for byte (same inputs, same tip)."""
    mission, stray = _stray_fixture(templates, tmp_path)
    built = _forecast_claim(mission, monkeypatch)
    require(built.claim.refusal is not None, "the US2-1 claim must refuse")

    door = _door_refusal(mission, built)

    assert door == built.claim.refusal
    _assert_refusal_names(door or "", stray, "WP01")


def _door_refusal(mission: cs.ShapeMission, built: _Built) -> str | None:
    with cs.mission_environment(mission):
        return approved_bound_refusal(
            mission.repo,
            built.inputs.status_dir,
            built.manifest,
            coord_base_ref=built.inputs.coord_base,
            excluded_canceled_wp_ids=built.inputs.excluded_canceled_wp_ids,
            excluded_window_base=built.inputs.target_base,
        )


@pytest.mark.parametrize("template", ["canceled_superseded", "canceled_unsuperseded", "canceled_after_approval"])
def test_approved_bound_refusal_matches_claim_on_canceled_commits(templates: _Templates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, template: str) -> None:
    """FR-022 with the ruling: the ``orchestrator-api`` door exempts the same canceled commits from tier 2 as the claim (and no more)."""
    mission = templates.copy(template, tmp_path)

    built = _forecast_claim(mission, monkeypatch)
    door = _door_refusal(mission, built)

    assert door == built.claim.refusal
    if template == "canceled_after_approval":
        assert door is not None and TIER_ONE_MARKER in door, door
    else:
        assert door is None, door


def test_classifier_reads_the_tip_the_bound_resolved(templates: _Templates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-022: the window predicates are bound to the very lane tip the bound validated and records on the claim."""
    mission = templates.copy("plain", tmp_path)
    _set_windows(mission, WP01="recorded", WP02="recorded")

    built = _forecast_claim(mission, monkeypatch)

    assert built.claim.refusal is None, built.claim.refusal
    recorded = {tip for _branch, tip in built.claim.bound_lane_tips}
    assert built.predicate_tips, "the bound must bind the window predicates"
    assert set(built.predicate_tips) == recorded
    assert len(built.predicate_tips) == len(built.claim.bound_lane_tips)


def test_not_on_lane_open_sha_is_a_gap_not_a_probe_error(templates: _Templates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """R-4: a recorded SHA the lane tip does not reach is a ``not on lane`` gap; the run passes like the all-gap lane."""
    not_on_lane = templates.copy("plain", tmp_path / "off")
    _set_windows(not_on_lane, WP01="not_on_lane", WP02="not_on_lane")
    all_gap = templates.copy("plain", tmp_path / "gap")
    _set_windows(all_gap, WP01="not_recorded", WP02="not_recorded")

    built = _forecast_claim(not_on_lane, monkeypatch)
    off_result, gap_result = _fresh(not_on_lane), _fresh(all_gap)

    assert built.claim.refusal is None, built.claim.refusal
    assert _gaps(built.claim) == [("WP01", "not on lane"), ("WP02", "not on lane")]
    assert (off_result.exit_code, off_result.status, off_result.codes) == (gap_result.exit_code, gap_result.status, gap_result.codes)
    _assert_passes(off_result)


def _todays_bound_text(mission: cs.ShapeMission, built: _Built) -> str | None:
    """The approved bound's refusal text as computed before the window model: ``check_lane`` with every bounded lane's stamps."""
    repo, feature_dir, manifest = mission.repo, built.inputs.status_dir, built.manifest
    work_packages = materialize_snapshot(feature_dir).work_packages or {}
    excluded = frozenset(built.inputs.excluded_canceled_wp_ids)
    events = _ClaimEventLog(feature_dir).read()
    require(events is not None, "the status log must be readable")
    lanes = _bound_lanes(manifest, work_packages, excluded)
    stamps = approval_stamp_anchors(events or [], lanes, work_packages, excluded)
    is_bookkeeping = functools.partial(_is_bookkeeping, mission_slug=manifest.mission_slug, planning_prefix=_planning_prefix(repo, feature_dir))
    base = built.inputs.target_base
    refusals = []
    for lane in lanes:
        branch = _lane_branch_for(manifest, lane.lane_id)
        found = check_lane(
            repo,
            events=events or [],
            lane_id=lane.lane_id,
            branch=branch,
            approved_wp_ids=_bound_approved_wp_ids(lane, work_packages, excluded),
            claim_base=base,
            anchors=[*_closed_world_anchors(manifest, lane, base, excluded_canceled_wp_ids=excluded, frozen_tips=None), *stamps],
            is_bookkeeping=is_bookkeeping,
            tip=_git(mission, "rev-parse", branch),
        )
        if found is not None:
            refusals.append(found)
    return render_refusals(refusals, manifest.mission_slug) if refusals else None


def test_all_gap_lane_post_approval_refusal_text_is_todays(templates: _Templates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """US3-2, US3-5, FR-023: every work package a gap plus a late commit; the claim text equals today's ``check_lane`` text, byte for byte."""
    mission = templates.copy("single_lane", tmp_path)
    _set_windows(mission, WP01="not_recorded", WP02="not_recorded")
    with fixture_phase():
        late = add_post_approval_commit(mission.coord_mission())

    built = _forecast_claim(mission, monkeypatch)
    with cs.mission_environment(mission):
        expected = _todays_bound_text(mission, built)

    assert expected is not None and late[:7] in expected
    assert built.claim.refusal == expected
