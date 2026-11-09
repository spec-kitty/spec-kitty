"""SIGKILL resume fixtures for the frozen resume anchors (FR-015, NFR-002 (e)(f)(g), WP18).

A resume test is meaningful only when it reaches a REAL interrupted state that holds frozen tips.
An exception exit does not: a pre-mutation exit clears a fresh record and a full-restore rollback
re-baselines it (#6770), so the "resume" would be a fresh run and a red test a vacuous one. Every
fixture here therefore interrupts with the corpus's SIGKILL driver
(:func:`~tests.consolidation.characterization_support.interrupt_after_claim`): the child is killed in
place of ``executor._phase_merge_lanes``, right after ``_capture_reconciliation_claim`` persisted
``pre_mutation_coord_sha`` and ``pre_interrupt_lane_tips`` and before the first branch moves.

Only the coordination topology freezes tips (``phase_claim._resolve_pre_mutation_coord_sha`` persists
them only when the status surface ref resolves to a coordination checkpoint), so every builder here is
a coordination Mission.

The precondition rule (shared with the intended-verdict pins): fixture work never asserts.
:func:`require` raises :class:`FixturePrecondition` (a ``RuntimeError``) and :func:`fixture_phase`
re-raises the ``AssertionError`` of a shared corpus helper the same way, so a broken fixture ERRORS a
strict ``xfail(raises=AssertionError)`` test instead of hiding behind it. ``state.json`` is only read
here, never written (NFR-010).
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any

from specify_cli.consolidation.approved_bound import APPROVED_REVIEWED, ATTEST_APPROVED_FLAG
from specify_cli.consolidation.canceled_attestation import ATTESTATION_KEY
from specify_cli.consolidation.state import lane_tip_cas_ok
from tests.consolidation import characterization_support as cs
from tests.terminus.canceled_dependency_support import ACTOR, build_canceled_dependency_mission
from tests.terminus.mixed_lane_support import transition

__all__ = [
    "ADVANCED_PATH",
    "FixturePrecondition",
    "Builder",
    "advance_dependency_lane",
    "advance_lane_into_dependency",
    "attest_args",
    "attestation_count",
    "committed_event_log",
    "branch_tips",
    "build_attested_bound_lane_with_dependency",
    "build_bound_lane_with_dependency",
    "build_canceled_lane_on_approved_dependency",
    "build_mixed_lane_with_dependency",
    "fixture_phase",
    "frozen_resume_state",
    "reflogs",
    "require",
    "resume",
]

#: The non-bookkeeping path no work package owns that the post-interrupt commit D touches.
ADVANCED_PATH = "src/advanced/after_interrupt.py"

#: A fixture builder: the destination directory in, the built coordination Mission out.
Builder = Callable[[Path], cs.ShapeMission]


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


# --------------------------------------------------------------------------- observations


def _tip(mission: cs.ShapeMission, ref: str) -> str:
    return cs._try_git(mission.repo, "rev-parse", "--verify", "-q", ref) or "<gone>"


def _watched(mission: cs.ShapeMission) -> dict[str, str]:
    return {"target": mission.target_branch, "mission": mission.mission_branch, **{f"lane:{wp}": branch for wp, branch in sorted(mission.lane_branches.items())}}


def branch_tips(mission: cs.ShapeMission) -> dict[str, str]:
    """Where the target, the Mission branch and every lane branch point: the 'no branch moved' observation."""
    return {name: _tip(mission, ref) for name, ref in _watched(mission).items()}


def _unmovable_tips(mission: cs.ShapeMission) -> dict[str, str]:
    """The target and lane tips: what no step before the first lane merge may move (an attestation moves only the Mission branch)."""
    return {name: tip for name, tip in branch_tips(mission).items() if name != "mission"}


def reflogs(mission: cs.ShapeMission) -> dict[str, list[str]]:
    """The reflog of the target and the Mission branch: a moved-and-restored branch leaves an entry here."""
    out: dict[str, list[str]] = {}
    for branch in (mission.target_branch, mission.mission_branch):
        listed = cs._try_git(mission.repo, "reflog", "show", "--format=%H", f"refs/heads/{branch}") or ""
        out[branch] = listed.split()
    return out


def committed_event_log(mission: cs.ShapeMission) -> str:
    """The status event log as committed on the Mission (coordination) branch: an unrecorded attestation leaves it byte-identical."""
    return cs._try_git(mission.repo, "show", f"{mission.mission_branch}:kitty-specs/{mission.slug}/status.events.jsonl") or ""


def attestation_count(mission: cs.ShapeMission, wp_id: str) -> int:
    """How many ``approved_reviewed`` attestations the committed event log holds for *wp_id*."""
    events = (json.loads(line) for line in committed_event_log(mission).splitlines() if line.strip())
    return sum(1 for event in events if event.get("wp_id") == wp_id and (event.get("policy_metadata") or {}).get(ATTESTATION_KEY) == APPROVED_REVIEWED)


# --------------------------------------------------------------------------- builders (coordination topology: tips are frozen)


def _template(tmp_path: Path, name: str) -> cs.ShapeMission:
    _dependency, builder = cs.TEMPLATES[name]
    with fixture_phase():
        mission = builder(tmp_path / "m", None)
        cs.set_window_states(mission, "recorded")
    return mission


def build_mixed_lane_with_dependency(tmp_path: Path) -> cs.ShapeMission:
    """(e): mixed lane-b (approved WP01 + WP02 canceled with operator provenance) depends on approved lane-a (WP03)."""
    mission = _template(tmp_path, "mixed_lane_with_dependency")
    require(bool(mission.canceled_wps), "the dependent lane must be mixed: a canceled work package shares it")
    require(mission.lane_branches["WP01"] == mission.lane_branches["WP02"] != mission.lane_branches["WP03"], "lane-b (WP01+WP02) must depend on lane-a (WP03)")
    return mission


def build_bound_lane_with_dependency(tmp_path: Path) -> cs.ShapeMission:
    """(f): lane-b (approved WP02, not mixed) depends on approved lane-a (WP01)."""
    mission = _template(tmp_path, "dependency_chain")
    require(not mission.canceled_wps, "the dependent lane must not be mixed")
    require(mission.lane_branches["WP01"] != mission.lane_branches["WP02"], "WP02 must sit on its own lane, depending on lane-a")
    return mission


def build_canceled_lane_on_approved_dependency(tmp_path: Path) -> cs.ShapeMission:
    """(g): fully-canceled lane C (lane-b, WP02 canceled with operator provenance) whose own dependency lane A (lane-a, WP01) is approved.

    C's closed-world anchors are A's tip plus the target base (``_fully_canceled_lane_own_commits``), so A is the one
    dependency lane whose frozen tip touches C at all.
    """
    with fixture_phase():
        built = build_canceled_dependency_mission(tmp_path / "m", wp01_final="approved", depends=True, approve_wp02=False, mid8="01M6Y8G1")
        transition(built.mission, "WP02", "canceled", actor=ACTOR, reason_source="operator", reason="operator: scope removed from mission")
        built.mission.canceled_wps.add("WP02")
        mission = cs._from_coord(built.mission, "coord", subject_wp="WP01", window_wps=("WP01",))
        cs.set_window_states(mission, "recorded")
    require(mission.canceled_wps == frozenset({"WP02"}), "WP02 (lane-b) must be the only canceled work package")
    return mission


def build_attested_bound_lane_with_dependency(tmp_path: Path) -> cs.ShapeMission:
    """Consumer 4: lane-b (WP02, depends on approved lane-a) whose approval carries no stamp, so the first run attests it.

    The stamp is stripped with the corpus's stamp axis (``apply_stamp(..., "missing")``), the production shape of an
    approval recorded before the stamp existed; the operator then attests WP02 (``--attest-approved-reviewed``).
    """
    mission = build_bound_lane_with_dependency(tmp_path)
    with fixture_phase():
        cs.apply_stamp(mission, "missing")
    return mission


def attest_args(wp_id: str, reason: str) -> tuple[str, ...]:
    return (ATTEST_APPROVED_FLAG, wp_id, "--attest-reason", reason)


# --------------------------------------------------------------------------- the interrupted state


def _record(mission: cs.ShapeMission) -> dict[str, Any]:
    path = cs._state_json(mission)
    if path is None:
        raise FixturePrecondition("the killed run left no state.json")
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return payload


def frozen_resume_state(mission: cs.ShapeMission, dependency_wp: str, *extra: str) -> str:
    """SIGKILL a fresh ``consolidate`` right after the claim anchors were saved; return the dependency lane's frozen tip.

    Preconditions checked on the record the killed run left (read only): ``pre_interrupt_lane_tips`` holds the
    dependency lane's created branch at the tip it had before the kill, ``pre_mutation_coord_sha`` is set, no work
    package was consolidated, and neither the target (tip and reflog) nor a lane branch moved. The Mission
    (coordination) branch is not checked: an operator attestation the run records commits to it, legitimately. The
    stale global merge lock is removed by the driver, as the operator is told to.
    """
    branch = mission.lane_branches[dependency_wp]
    before_tip = _tip(mission, branch)
    before_tips = _unmovable_tips(mission)
    before_target_reflog = reflogs(mission)[mission.target_branch]
    with fixture_phase():
        cs.interrupt_after_claim(mission, *extra)
    record = _record(mission)
    tips = record.get("pre_interrupt_lane_tips") or {}
    require(isinstance(tips, dict) and tips.get(branch) == before_tip, f"state.json must freeze {branch} at {before_tip}: {tips}")
    require(bool(record.get("pre_mutation_coord_sha")), "state.json must hold pre_mutation_coord_sha")
    require(record.get("completed_wps") == [], f"no work package may be consolidated before the kill: {record.get('completed_wps')}")
    require(_unmovable_tips(mission) == before_tips, "the killed run must not have moved the target or a lane branch")
    require(reflogs(mission)[mission.target_branch] == before_target_reflog, "the killed run must not have moved and restored the target")
    return before_tip


def _commit_and_merge(mission: cs.ShapeMission, lane_wp: str, merge_into: str | None, message: str) -> str:
    """Commit D on *lane_wp*'s lane, then the allocator-shaped ``--no-ff`` merge of that lane into *merge_into*'s lane.

    Afterwards every frozen lane tip must still pass the H3 compare-and-swap (``lane_tip_cas_ok``: an advanced lane is
    a descendant), so the resume reaches the claim instead of refusing on divergence. Returns D.
    """
    with fixture_phase():
        advanced = cs._advance_lane(mission, lane_wp, ADVANCED_PATH, message)
        if merge_into is not None:
            with cs.lane_checkout(mission, mission.lane_branches[merge_into]) as receiving:
                cs._git(receiving, "merge", "-q", "--no-ff", "--no-edit", mission.lane_branches[lane_wp])
    tips: Mapping[str, str] = _record(mission).get("pre_interrupt_lane_tips") or {}
    for branch, sha in tips.items():
        require(lane_tip_cas_ok(mission.repo, branch, sha), f"H3 would refuse the resume: {branch} is no descendant of its frozen tip {sha}")
    return advanced


def advance_dependency_lane(mission: cs.ShapeMission, dependency_wp: str, *, merge_into: str | None) -> str:
    """Commit D on the dependency lane (a path no work package owns); merge it into *merge_into*'s lane when given. Returns D."""
    return _commit_and_merge(mission, dependency_wp, merge_into, "feat: dependency lane advanced after the interruption")


def advance_lane_into_dependency(mission: cs.ShapeMission, lane_wp: str, *, dependency_wp: str) -> str:
    """Commit D on *lane_wp*'s own lane, then merge that lane into its dependency lane: the dependency lane gains D. Returns D.

    The shape that puts D on the dependent lane's FIRST-PARENT spine as a non-merge commit, the only commits the
    mixed-lane closed world walks (a dependency-lane commit merged in with ``--no-ff`` sits behind the merge commit,
    which the walk skips). The dependency lane's live tip reaches D; its frozen tip does not.
    """
    return _commit_and_merge(mission, lane_wp, dependency_wp, "feat: dependent lane advanced after the interruption")


def resume(mission: cs.ShapeMission, *extra: str) -> cs.CellResult:
    """``consolidate --resume --yes`` in process (patches and seeded mutations reach it)."""
    return cs.run_in_process(mission, cs.consolidate_args(mission, "resume", *extra))
