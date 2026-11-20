"""#7497 (FR-011, US8): canceled content must not land through a re-approved dependency lane.

The shape: lane A (``lane-a``, WP01) is approved; lane C (``lane-b``, WP02) is cut from A and then FULLY
canceled with operator provenance; C is merged into A (``git merge --no-ff``); A is re-approved by an
unforced, independent review whose ``lane_head`` stamp descends from that merge; then a FRESH
``consolidate`` runs. The re-approval reviews WP01's own work; it cannot un-cancel WP02 (C-001), so the run
must refuse with ``CANCELED_REACHABLE_VIA_DEPENDENCY`` naming C's content.

Cross-reference: ``tests/consolidation/test_resume_frozen_anchors.py::test_resume_fully_canceled_lane_flip_is_unreachable``
(the (g) pin) covers the resume path WITHOUT the re-approval (``LANE_MOVED_AFTER_APPROVAL`` on lane-a); the control
test here pins the same verdict on a fresh run, and the main test covers the re-approved shape the (g) pin
calls "not an FR-015 verdict".

Every fixture precondition uses :func:`require` (never ``assert``), so a fixture that cannot express the
shape ERRORS instead of passing vacuously.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from specify_cli.consolidation import reconciliation_canceled as rc
from specify_cli.consolidation.approved_bound import approval_stamp
from specify_cli.consolidation.git_probes import GitProbeError
from specify_cli.lanes.branch_naming import lane_branch_name
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.compute import lane_fully_canceled
from specify_cli.lanes.persistence import read_lanes_json
from specify_cli.status.models import StatusEvent
from specify_cli.status.store import read_events_from_text
from tests.consolidation import characterization_support as cs
from tests.consolidation.resume_frozen_anchors_support import (
    build_canceled_lane_on_approved_dependency,
    committed_event_log,
    fixture_phase,
    require,
)
from tests.terminus.canceled_dependency_support import ACTOR, WP02_PATH, _approve
from tests.terminus.conftest import blob_present_at
from tests.terminus.mixed_lane_support import transition

pytestmark = [pytest.mark.git_repo]

CODE = "CANCELED_REACHABLE_VIA_DEPENDENCY"


def _merge_canceled_lane_into_dependency(mission: cs.ShapeMission) -> str:
    """Merge C (lane-b) into A (lane-a) with ``--no-ff``; return the merge commit."""
    with fixture_phase(), cs.lane_checkout(mission, mission.lane_branches["WP01"]) as lane_a:
        cs._git(lane_a, "merge", "-q", "--no-ff", "--no-edit", mission.lane_branches["WP02"])
        return cs._git(lane_a, "rev-parse", "HEAD").strip()


def _reapprove_wp01(mission: cs.ShapeMission) -> None:
    """Send WP01 back and re-approve it through the production shell: unforced, independent reviewer."""
    coord = mission.coord_mission()
    with fixture_phase():
        transition(coord, "WP01", "in_progress", actor=ACTOR, review_ref="review-WP01-rework")
        _approve(coord, "WP01", reference="review-WP01-reapproved")


def _wp01_events(mission: cs.ShapeMission) -> list[StatusEvent]:
    """WP01's lane transitions as committed on the coordination branch (the status surface)."""
    return [e for e in read_events_from_text(mission.feature_dir, committed_event_log(mission)) if e.wp_id == "WP01"]


def _is_approval(event: object) -> bool:
    return str(getattr(event, "to_lane", "")).lower().endswith("approved")


def _first_approval_stamp(mission: cs.ShapeMission) -> str:
    """The ``lane_head`` stamp of WP01's FIRST approval ("" when none): the content approved WP01 authored."""
    for event in _wp01_events(mission):
        if _is_approval(event):
            return str((event.policy_metadata or {}).get("lane_head") or "")
    return ""


def _require_shape(mission: cs.ShapeMission, merge_commit: str, *, reapproved: bool) -> None:
    """The four vacuity routes (renata HIGH on FR-011), each a FixturePrecondition, never an assertion."""
    manifest = read_lanes_json(mission.feature_dir)
    require(manifest is not None, "lanes.json must be readable")
    assert manifest is not None
    lane_b = next(lane for lane in manifest.lanes if "WP02" in lane.wp_ids)
    require(mission.canceled_wps == frozenset({"WP02"}), "WP02 must be canceled with operator provenance")
    require(lane_fully_canceled(lane_b, frozenset(mission.canceled_wps)), "lane-b (C) must be fully canceled")

    lane_a, lane_c = mission.lane_branches["WP01"], mission.lane_branches["WP02"]
    require(blob_present_at(mission.repo, lane_a, WP02_PATH), "C's canceled blob must be reachable from lane-a's tip (the merge happened)")
    canceled_blob = cs._git(mission.repo, "rev-parse", f"{lane_c}:{WP02_PATH}").strip()
    first_stamp = _first_approval_stamp(mission)
    require(bool(first_stamp), "WP01's first approval must carry a lane_head stamp")
    approved_blob = cs._try_git(mission.repo, "rev-parse", "-q", "--verify", f"{first_stamp}:{WP02_PATH}") or ""
    require(approved_blob.strip() != canceled_blob, "C's canceled blob must differ from any blob approved WP01 authored")

    events = _wp01_events(mission)
    stamp = approval_stamp(events, "WP01")
    require(stamp is not None, "WP01's newest approval must be a stamped review approval")
    assert stamp is not None
    newest = [e for e in events if _is_approval(e)][-1]
    require(not newest.force, "WP01's newest approval must be unforced")
    descends = cs._try_git(mission.repo, "merge-base", "--is-ancestor", merge_commit, stamp) is not None
    if reapproved:
        require(descends, "WP01's re-approval stamp must descend from the merge of C into A")
    else:
        require(not descends, "control: WP01's approval stamp must predate the merge of C into A")
    require(cs._state_json(mission) is None, "no consolidate record may exist: this is a fresh run")


def _build(tmp_path: Path, *, reapprove: bool) -> tuple[cs.ShapeMission, str]:
    mission = build_canceled_lane_on_approved_dependency(tmp_path)
    merge_commit = _merge_canceled_lane_into_dependency(mission)
    if reapprove:
        _reapprove_wp01(mission)
    _require_shape(mission, merge_commit, reapproved=reapprove)
    return mission, merge_commit


def _fresh_run(mission: cs.ShapeMission) -> cs.CellResult:
    return cs.run_in_process(mission, cs.consolidate_args(mission, "fresh"))


@pytest.mark.slow
def test_canceled_content_via_reapproved_dependency_lane_is_refused(tmp_path: Path) -> None:
    """FR-011: A re-approved over C's merge must not carry C's canceled content onto the target."""
    mission, _merge = _build(tmp_path, reapprove=True)

    result = _fresh_run(mission)

    assert result.exception is None, result.output
    assert result.exit_code != 0, result.output
    assert CODE in result.output, f"{result.codes} {result.divergence_fields}\n{result.output}"
    assert "WP02" in result.output and "lane-b" in result.output, result.output
    assert WP02_PATH in result.output, result.output
    assert not blob_present_at(mission.repo, mission.target_branch, WP02_PATH), "C's canceled blob must not be on the target"


@pytest.mark.slow
def test_control_without_reapproval_keeps_lane_moved_after_approval(tmp_path: Path) -> None:
    """Control: A NOT re-approved over C's merge keeps today's verdict (the (g) pin's verdict, on a fresh run)."""
    mission, _merge = _build(tmp_path, reapprove=False)

    result = _fresh_run(mission)

    assert result.exception is None, result.output
    assert result.exit_code == 1, result.output
    assert "LANE_MOVED_AFTER_APPROVAL" in result.output, result.output
    assert "(lane-a carries WP01)" in result.output, result.output
    assert not blob_present_at(mission.repo, mission.target_branch, WP02_PATH)


# --------------------------------------------------------------------------- T043: the protection is load-bearing


@pytest.mark.slow
@pytest.mark.parametrize(
    ("name", "disabled"),
    [
        ("_dependency_anchor_before_incorporating", lambda _repo, _base, tip, _canceled: tip),
        ("_with_merged_in_canceled", lambda _repo, _base, _branch, spine, _canceled: spine),
    ],
    ids=["anchor_at_live_tip", "first_parent_carriers_only"],
)
def test_protection_is_load_bearing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, disabled: object) -> None:
    """Mutation check: with either half of the #7497 fix switched back to the old behaviour, the code is not produced."""
    mission, _merge = _build(tmp_path, reapprove=True)
    monkeypatch.setattr(rc, name, disabled)

    result = _fresh_run(mission)

    assert result.exception is None, result.output
    assert CODE not in result.output, result.output


# --------------------------------------------------------------------------- T041: the helpers, on a small real repository

_SLUG = "reapproved-dep"
_TARGET = "main"


def _sh(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _commit(repo: Path, path: str, text: str) -> str:
    (repo / path).parent.mkdir(parents=True, exist_ok=True)
    (repo / path).write_text(text, encoding="utf-8")
    _sh(repo, "add", path)
    _sh(repo, "commit", "-qm", f"edit {path}")
    return _sh(repo, "rev-parse", "HEAD")


def _branch(lane_id: str) -> str:
    branch: str = lane_branch_name(_SLUG, lane_id, target_branch=_TARGET)
    return branch


def _lane(lane_id: str, wp_id: str, deps: tuple[str, ...] = ()) -> ExecutionLane:
    return ExecutionLane(lane_id=lane_id, wp_ids=(wp_id,), write_scope=("src",), predicted_surfaces=("code",), depends_on_lanes=deps, parallel_group=0)


_MANIFEST = LanesManifest(
    version=1,
    mission_slug=_SLUG,
    mission_id="01REAPPROVEDDEP000000000000",
    mission_branch=f"kitty/mission-{_SLUG}",
    target_branch=_TARGET,
    lanes=[_lane("lane-a", "WP01"), _lane("lane-b", "WP02", ("lane-a",))],
    computed_at="2026-11-20T00:00:00+00:00",
    computed_from="test-canceled-via-reapproved-dependency",
)


@dataclass(frozen=True)
class Shape:
    """``base`` -> lane-a ``a1``; lane-b (canceled) cut from ``a1`` with ``c1``; lane-a merges lane-b (``merge``), then ``a2``."""

    repo: Path
    base: str
    a1: str
    c1: str
    merge: str
    a2: str


@pytest.fixture
def shape(tmp_path: Path) -> Shape:
    repo = tmp_path / "repo"
    repo.mkdir()
    _sh(repo, "init", "-q", "-b", _TARGET)
    for key, value in (("user.email", "t@example.invalid"), ("user.name", "Test"), ("commit.gpgsign", "false")):
        _sh(repo, "config", key, value)
    base = _commit(repo, "README.md", "init\n")
    _sh(repo, "checkout", "-q", "-b", _branch("lane-a"), base)
    a1 = _commit(repo, "src/a.py", "A = 1\n")
    _sh(repo, "checkout", "-q", "-b", _branch("lane-b"), a1)
    c1 = _commit(repo, "src/c.py", "C = 'canceled'\n")
    _sh(repo, "checkout", "-q", _branch("lane-a"))
    _sh(repo, "merge", "-q", "--no-ff", "--no-edit", _branch("lane-b"))
    merge = _sh(repo, "rev-parse", "HEAD")
    a2 = _commit(repo, "src/a.py", "A = 2\n")
    return Shape(repo=repo, base=base, a1=a1, c1=c1, merge=merge, a2=a2)


def _canceled_tip(shape: Shape) -> frozenset[str]:
    return frozenset({shape.a1, shape.c1})  # lane-b's commits since the base: A's a1 (fast-forwarded at the cut) and c1


def test_anchor_is_the_first_parent_of_the_merge_that_incorporated_c(shape: Shape) -> None:
    got = rc._dependency_anchor_before_incorporating(shape.repo, shape.base, _branch("lane-a"), _canceled_tip(shape))
    assert got == shape.a1


def test_anchor_is_unchanged_when_the_dependency_never_merged_c(shape: Shape) -> None:
    assert rc._dependency_anchor_before_incorporating(shape.repo, shape.base, shape.a1, _canceled_tip(shape)) == shape.a1


def test_an_unrelated_merge_keeps_the_live_anchor(shape: Shape) -> None:
    _sh(shape.repo, "checkout", "-q", "-b", "side", shape.base)
    _commit(shape.repo, "src/side.py", "SIDE = 1\n")
    _sh(shape.repo, "checkout", "-q", "-b", "a-only", shape.a1)
    _sh(shape.repo, "merge", "-q", "--no-ff", "--no-edit", "side")
    tip = _sh(shape.repo, "rev-parse", "HEAD")
    assert rc._dependency_anchor_before_incorporating(shape.repo, shape.base, tip, _canceled_tip(shape)) == tip


def test_the_earliest_incorporation_decides(shape: Shape) -> None:
    _sh(shape.repo, "checkout", "-q", _branch("lane-b"))
    c2 = _commit(shape.repo, "src/c.py", "C = 'canceled again'\n")
    _sh(shape.repo, "checkout", "-q", _branch("lane-a"))
    _sh(shape.repo, "merge", "-q", "--no-ff", "--no-edit", _branch("lane-b"))
    canceled = _canceled_tip(shape) | {c2}
    assert rc._dependency_anchor_before_incorporating(shape.repo, shape.base, _branch("lane-a"), canceled) == shape.a1


def test_an_unreadable_dependency_anchors_nothing_and_keeps_the_target_base(shape: Shape) -> None:
    with pytest.raises(GitProbeError):
        rc._dependency_anchor_before_incorporating(shape.repo, shape.base, "no-such-ref", _canceled_tip(shape))
    got = rc._canceled_lane_anchors(shape.repo, shape.base, ["no-such-ref", shape.base], shape.base, _canceled_tip(shape))
    assert got == [shape.base]


def test_canceled_lane_own_commits_live_and_frozen(shape: Shape) -> None:
    """C owns c1 again: on the live read (A merged C) and on a resume's frozen pre-merge tip (FR-015)."""
    excluded = frozenset({"WP02"})
    live = rc._fully_canceled_lane_own_commits(shape.repo, _MANIFEST, excluded, shape.base, None, frozen_tips=None)
    frozen = rc._fully_canceled_lane_own_commits(shape.repo, _MANIFEST, excluded, shape.base, None, frozen_tips={_branch("lane-a"): shape.a1})
    assert live == {"lane-b": frozenset({shape.c1})}
    assert frozen == {"lane-b": frozenset({shape.c1})}


def test_merged_in_canceled_commits_follow_their_merge_on_the_spine(shape: Shape) -> None:
    spine = [shape.a2, shape.merge, shape.a1]
    assert rc._with_merged_in_canceled(shape.repo, shape.base, _branch("lane-a"), spine, frozenset({shape.c1})) == [shape.a2, shape.merge, shape.c1, shape.a1]
    assert rc._with_merged_in_canceled(shape.repo, shape.base, _branch("lane-a"), spine, frozenset({shape.a1})) == spine


def _query(shape: Shape) -> rc._CanceledLaneQuery:
    return rc._CanceledLaneQuery(
        shape.repo, shape.repo / "kitty-specs" / _SLUG, _MANIFEST, {"WP01": {"lane": "approved"}, "WP02": {"lane": "canceled"}},
        frozenset({"WP02"}), shape.base, None, None, None, frozen_tips=None,
    )  # fmt: skip


def test_a_lane_that_merged_c_is_its_carrier(shape: Shape) -> None:
    carriers = rc._carrier_spines(_query(shape), frozenset({shape.c1}))
    assert carriers.spines == {"lane-a": [shape.a2, shape.merge, shape.c1, shape.a1]}
    assert carriers.unreadable == {}


def test_an_unreadable_merged_in_history_refuses_spine_unreadable(shape: Shape, monkeypatch: pytest.MonkeyPatch) -> None:
    def _broken(*_args: object) -> list[str]:
        raise GitProbeError("broken history")

    monkeypatch.setattr(rc, "_with_merged_in_canceled", _broken)
    query = _query(shape)
    carriers = rc._carrier_spines(query, frozenset({shape.c1}))
    assert set(carriers.unreadable) == {"lane-a"} and shape.c1 in carriers.spines["lane-a"]
    own_by_lane = {"lane-b": frozenset({shape.c1})}
    _superseded, content, refusal = rc._carried_dependency_content(query, own_by_lane, carriers.spines, frozenset({shape.c1}), carriers.unreadable)
    assert content == frozenset()
    assert refusal is not None and "spine_unreadable" in refusal and "broken history" in refusal
