"""Which checkout a coordination-less status commit runs in (#7633, slice 2 of #7594's Mission).

The coordination-less arm of ``BookkeepingTransaction.acquire`` takes its checkout from the
placement seam (``write_dir(STATUS_STATE).surface_root``), the checkout the status read door
reads. When that checkout does not hold the destination ref (the write branch is held by some
other checkout, or by no usable one), the arm refuses before any write with
``STATUS_WRITE_CHECKOUT_NOT_ON_WRITE_BRANCH`` (operator ruling Q8, option a): a status commit
never lands in a checkout the read door does not read.

Every Mission is built with the real ``agent mission create`` core in a real git repository
(the characterization matrix of #7633, 11 rows). Each row records three answers:

* **write:** the checkout ``acquire`` picks, or ``refused`` with the named code;
* **seam:** ``write_dir(STATUS_STATE).surface_root``;
* **read door:** what ``resolve_status_read`` reads (a checkout, or ``ref:<ref>``).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from kernel.git_anchor import checkout_root_in_spelling
from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.coordination.transaction import BookkeepingPolicyRefused, BookkeepingTransaction
from specify_cli.coordination.types import STATUS_WRITE_CHECKOUT_NOT_ON_WRITE_BRANCH
from specify_cli.status.read_surface import resolve_status_read
from tests.specify_cli.cli.commands.agent.test_finalize_topology_settlement import (
    DefaultMission,
    _quiet_status_fanout,
    _write_wps,
    git,
    init_repo,
    make_default_mission,
    run_finalize,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]
__all__ = ["_quiet_status_fanout"]

_STATUS = MissionArtifactKind.STATUS_STATE
_UNPROTECTED = "develop"
_TWO_WPS = ("src/one.py", "src/two.py")
_REFUSED = f"refused:{STATUS_WRITE_CHECKOUT_NOT_ON_WRITE_BRANCH}"

Checkouts = dict[str, Path]


@dataclass(frozen=True)
class Answers:
    write: str
    seam: str
    read_door: str


def _label(path: Path | None, mission: DefaultMission, extra: Checkouts) -> str:
    if path is None:
        return "none"
    resolved = path.resolve()
    if resolved == mission.root.resolve():
        return "root"
    for name, candidate in extra.items():
        if resolved == candidate.resolve():
            return name
    return str(path)


def _meta(mission: DefaultMission) -> dict[str, object]:
    data: dict[str, object] = json.loads((mission.root_mission_dir / "meta.json").read_text(encoding="utf-8"))
    return data


def _write_answer(mission: DefaultMission, checkouts: Checkouts, ref: str) -> str:
    meta = _meta(mission)
    mission_id = str(meta["mission_id"])
    try:
        with BookkeepingTransaction.acquire(
            repo_root=mission.root,
            mission_id=mission_id,
            mission_slug=mission.slug,
            mid8=mission_id[:8],
            destination_ref=ref,
            operation="characterization",
        ) as txn:
            assert txn._legacy_mode is True
            return _label(txn.worktree_root, mission, checkouts)
    except BookkeepingPolicyRefused as refused:
        return f"refused:{refused.verdict.error_code}"


def _answers(mission: DefaultMission, checkouts: Checkouts) -> Answers:
    seam = placement_seam(mission.root, mission.slug)
    write = _write_answer(mission, checkouts, seam.write_target(_STATUS).ref)
    surface = resolve_status_read(mission.root, mission.slug)
    read_door = f"ref:{surface.ref}" if surface.path is None else _label(checkout_root_in_spelling(surface.path), mission, checkouts)
    return Answers(write, _label(seam.write_dir(_STATUS).surface_root, mission, checkouts), read_door)


# ---------------------------------------------------------------------------
# Shapes
# ---------------------------------------------------------------------------


def _move_branch_to(mission: DefaultMission, branch: str, holder: Path) -> None:
    git(mission.root, "checkout", "-q", "--detach")
    git(mission.root, "worktree", "add", "-q", str(holder), branch)


def _commit_to_target_mission(tmp_path: Path) -> DefaultMission:
    from mission_runtime import MissionTopology
    from specify_cli.core.mission_creation import create_mission_core
    from specify_cli.meta_keys import TopologySource

    root = init_repo(tmp_path, standing_on=_UNPROTECTED)
    result = create_mission_core(
        root,
        "probe",
        allow_worktree_context=True,
        friendly_name="Probe",
        purpose_tldr="Deliver the probe for the characterization.",
        purpose_context="This mission pins which checkout a coordination-less status commit runs in.",
        topology=MissionTopology.SINGLE_BRANCH,
        topology_source=TopologySource.EXPLICIT,
        commit_to_target=True,
    )
    _write_wps(result.feature_dir, _TWO_WPS)
    git(root, "add", "kitty-specs")
    git(root, "commit", "-qm", "tasks")
    return DefaultMission(root=root, slug=result.mission_slug, topic="", return_branch=_UNPROTECTED, root_mission_dir=result.feature_dir)


def _explicit_single_branch(tmp_path: Path) -> tuple[DefaultMission, Checkouts]:
    return make_default_mission(tmp_path, _TWO_WPS, standing_on=_UNPROTECTED, explicit="single_branch"), {}


def _explicit_commit_to_target(tmp_path: Path) -> tuple[DefaultMission, Checkouts]:
    return _commit_to_target_mission(tmp_path), {}


def _explicit_lanes(tmp_path: Path) -> tuple[DefaultMission, Checkouts]:
    return make_default_mission(tmp_path, _TWO_WPS, standing_on=_UNPROTECTED, explicit="lanes"), {}


def _default_unsettled(tmp_path: Path) -> tuple[DefaultMission, Checkouts]:
    return make_default_mission(tmp_path, _TWO_WPS), {}


def _default_settled_single_branch(tmp_path: Path) -> tuple[DefaultMission, Checkouts]:
    mission = make_default_mission(tmp_path, _TWO_WPS)
    code, payload = run_finalize(mission)
    assert code == 0, payload
    return mission, {}


def _default_topic_held_elsewhere(tmp_path: Path) -> tuple[DefaultMission, Checkouts]:
    mission = make_default_mission(tmp_path, _TWO_WPS)
    holder = tmp_path / "operator"
    _move_branch_to(mission, mission.topic, holder)
    return mission, {"other": holder}


def _landed(tmp_path: Path) -> tuple[DefaultMission, Checkouts]:
    mission = make_default_mission(tmp_path, _TWO_WPS, standing_on=_UNPROTECTED)
    code, payload = run_finalize(mission)
    assert code == 0, payload
    git(mission.root, "checkout", "-q", _UNPROTECTED)
    git(mission.root, "merge", "-q", "--ff-only", mission.topic)
    meta = _meta(mission)
    meta.pop("mission_branch", None)
    meta["merged_at"] = "2026-11-14T00:00:00+00:00"
    (mission.root_mission_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    git(mission.root, "commit", "-qam", "land")
    return mission, {}


def _lane_worktree_holds_topic(tmp_path: Path) -> tuple[DefaultMission, Checkouts]:
    mission = make_default_mission(tmp_path, _TWO_WPS)
    lane = mission.root / ".worktrees" / f"{mission.slug}-lane-a"
    _move_branch_to(mission, mission.topic, lane)
    return mission, {"lane": lane}


def _write_ref_held_elsewhere(mission: DefaultMission, tmp_path: Path) -> Checkouts:
    holder = tmp_path / "operator"
    _move_branch_to(mission, placement_seam(mission.root, mission.slug).write_target(_STATUS).ref, holder)
    return {"other": holder}


def _commit_to_target_held_elsewhere(tmp_path: Path) -> tuple[DefaultMission, Checkouts]:  # shape (a)
    mission = _commit_to_target_mission(tmp_path)
    return mission, _write_ref_held_elsewhere(mission, tmp_path)


def _explicit_mission_branch_held_elsewhere(tmp_path: Path) -> tuple[DefaultMission, Checkouts]:  # shape (a), minted
    mission = make_default_mission(tmp_path, _TWO_WPS, standing_on=_UNPROTECTED, explicit="single_branch")
    return mission, _write_ref_held_elsewhere(mission, tmp_path)


def _default_topic_holder_without_mission_dir(tmp_path: Path) -> tuple[DefaultMission, Checkouts]:  # shape (b)
    mission = make_default_mission(tmp_path, _TWO_WPS)
    holder = tmp_path / "operator"
    _move_branch_to(mission, mission.topic, holder)
    git(holder, "rm", "-rq", f"kitty-specs/{mission.slug}")
    return mission, {"other": holder}


Builder = Callable[[Path], tuple[DefaultMission, Checkouts]]

#: shape -> (builder, expected answers). ``{topic}`` in ``read_door`` is the Mission topic branch.
MATRIX: dict[str, tuple[Builder, Answers]] = {
    "explicit-single-branch-unprotected": (_explicit_single_branch, Answers("root", "root", "root")),
    "explicit-commit-to-target": (_explicit_commit_to_target, Answers("root", "root", "root")),
    "explicit-lanes": (_explicit_lanes, Answers("root", "root", "root")),
    "default-unsettled-root-holds-topic": (_default_unsettled, Answers("root", "root", "root")),
    "default-settled-single-branch": (_default_settled_single_branch, Answers("root", "root", "root")),
    "default-topic-held-by-other-checkout": (_default_topic_held_elsewhere, Answers("other", "other", "other")),
    "landed": (_landed, Answers("root", "root", "root")),
    "lane-worktree-holds-topic": (_lane_worktree_holds_topic, Answers(_REFUSED, "root", "ref:refs/heads/{topic}")),
    "a-commit-to-target-held-by-other-checkout": (_commit_to_target_held_elsewhere, Answers(_REFUSED, "root", "root")),
    "a-explicit-mission-branch-held-by-other-checkout": (_explicit_mission_branch_held_elsewhere, Answers(_REFUSED, "root", "root")),
    "b-default-topic-holder-without-mission-dir": (_default_topic_holder_without_mission_dir, Answers(_REFUSED, "root", "ref:refs/heads/{topic}")),
}


@pytest.mark.parametrize("shape_id", list(MATRIX))
def test_coordless_status_commit_checkout_matrix(tmp_path: Path, shape_id: str) -> None:
    build, expected = MATRIX[shape_id]
    mission, checkouts = build(tmp_path)
    assert _answers(mission, checkouts) == replace(expected, read_door=expected.read_door.format(topic=mission.topic))


def _status_bytes(mission: DefaultMission, checkouts: Checkouts) -> dict[str, bytes]:
    roots = [mission.root, *checkouts.values()]
    return {str(path): path.read_bytes() for root in roots if root.is_dir() for path in sorted(root.rglob("status*.json*")) if ".git" not in path.parts}


@pytest.mark.parametrize("shape_id", [shape for shape, (_build, answers) in MATRIX.items() if answers.write == _REFUSED])
def test_refused_status_commit_writes_nothing(tmp_path: Path, shape_id: str) -> None:
    """NFR-001: the refusal comes before any write, in every checkout."""
    build, _expected = MATRIX[shape_id]
    mission, checkouts = build(tmp_path)
    before = _status_bytes(mission, checkouts)
    ref = placement_seam(mission.root, mission.slug).write_target(_STATUS).ref
    assert _write_answer(mission, checkouts, ref) == _REFUSED
    assert _status_bytes(mission, checkouts) == before


@pytest.mark.parametrize("shape_id", ["a-commit-to-target-held-by-other-checkout", "b-default-topic-holder-without-mission-dir"])
def test_refusal_names_the_holder_and_the_remedy(tmp_path: Path, shape_id: str) -> None:
    """Operator ruling on shape (a): the refusal names the checkout holding the write branch."""
    build, _expected = MATRIX[shape_id]
    mission, checkouts = build(tmp_path)
    ref = placement_seam(mission.root, mission.slug).write_target(_STATUS).ref
    verdict = BookkeepingTransaction.preflight_refusal(
        repo_root=mission.root, mission_slug=mission.slug, mid8=str(_meta(mission)["mission_id"])[:8], destination_ref=ref, operation="probe"
    )
    assert verdict is not None and verdict.error_code == STATUS_WRITE_CHECKOUT_NOT_ON_WRITE_BRANCH
    assert str(checkouts["other"].resolve()) in verdict.message or str(checkouts["other"]) in verdict.message
    assert f"checkout {ref}" in verdict.next_step
