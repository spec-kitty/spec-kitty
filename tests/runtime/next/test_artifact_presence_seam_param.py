"""Characterisation: guard-failure paths and artifact presence per caller shape (WP05 T023).

Mission ``runtime-status-read-door-01M73HHB`` (FR-010). The presence API used to receive a status
directory and map it back to a placement seam; WP05 hands it the seam instead. This file pins,
before that move, what each production caller shape reports today, so the move is provably
behaviour-preserving:

* non-owned ``single_branch`` and non-owned ``coord`` (materialized), the directory passed being
  the Mission's status home (what bootstrap hands the guards);
* owned ``single_branch`` and owned ``coord`` (materialized), the repository root checkout R plus
  the validated fact, as ``decide_next`` calls them.

Each case asks for spec.md, plan.md, tasks.md, a coordination-kind artifact (issue-matrix.md) and
an unclassified custom filename. After the move the calls pass the seam the production callers
build (:func:`runtime_bridge_io.presence_seam`); the expected answers are unchanged except the
owned coordination case, re-pinned red-first to resolve PRIMARY kinds in P. ``spec.md`` is written only to the PRIMARY home and ``plan.md``
only to the status home, so a resolution that picks the wrong home changes the answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from mission_runtime import MissionTopology, OwnedCheckout, PlacementSeam
from runtime.next import runtime_bridge_io as io_seam
from tests._owned_fixtures import mint_test_fact
from tests.runtime.test_artifact_presence_placement import MISSION_SLUG, _git, _mission

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

NAMES = ("spec.md", "plan.md", "tasks.md", "issue-matrix.md", "custom-notes.txt")
GUARD_FAILURES = (
    "Required artifact missing: spec.md",
    "Required artifact missing: plan.md",
    "Required artifact missing: tasks.md",
    "WP01 is not in a reviewable lane",
)


@dataclass(frozen=True)
class Case:
    repo: Path
    feature_dir: Path
    owned: OwnedCheckout | None
    tokens: dict[Path, str]


def _owned(tmp_path: Path, repo: Path, topology: MissionTopology) -> tuple[Path, OwnedCheckout]:
    owned_root = tmp_path / "owned"
    _git(repo, "worktree", "add", "-q", "-b", "codex/owned", str(owned_root))
    owned_mission = owned_root / "kitty-specs" / MISSION_SLUG
    fact = mint_test_fact(
        repository_root=repo,
        owned_root=owned_root,
        mission_dir=owned_mission,
        mission_slug=MISSION_SLUG,
        write_branch="codex/owned",
        topology=topology,
    )
    return owned_mission, fact


def _case(tmp_path: Path, shape: str) -> Case:
    topology = "single_branch" if shape.endswith("single_branch") else "coord"
    repo, primary, status = _mission(tmp_path, topology)
    tokens = {primary: "R_PRIMARY", status: "STATUS"} if status != primary else {primary: "R_PRIMARY"}
    if shape.startswith("owned"):
        owned_mission, fact = _owned(tmp_path, repo, MissionTopology(topology))
        tokens[owned_mission] = "P"
        # Bootstrap hands the owned guards the status home: P for single_branch, the
        # coordination worktree under R for a materialized coordination Mission.
        feature_dir = owned_mission if topology == "single_branch" else status
        planning_home = owned_mission
    else:
        fact = None
        feature_dir = status
        planning_home = primary
    (planning_home / "spec.md").write_text("# Spec\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    return Case(repo=repo, feature_dir=feature_dir, owned=fact, tokens=tokens)


def _token(case: Case, raw: str) -> str:
    path = Path(raw)
    if not path.is_absolute():
        path = case.repo / path
    for home, token in sorted(case.tokens.items(), key=lambda item: -len(str(item[0]))):
        if path.parent == home:
            return f"{token}/{path.name}"
    return f"?{raw}"


def _seam(case: Case) -> PlacementSeam | None:
    """The seam a production caller hands over (WP05): the Mission's own, owned when owned."""
    return io_seam.presence_seam(case.repo, MISSION_SLUG, owned=case.owned)


def _search_paths(case: Case) -> dict[str, str]:
    raw = io_seam.artifact_search_paths(case.feature_dir, mission_family="software-dev", repo_root=case.repo, names=NAMES, owned=case.owned, seam=_seam(case))
    return {name: _token(case, path) for name, path in raw.items()}


def _guard_paths(case: Case) -> dict[str, str]:
    raw = io_seam.guard_failure_artifact_paths(
        case.feature_dir,
        mission_family="software-dev",
        repo_root=case.repo,
        guard_failures=GUARD_FAILURES,
        owned=case.owned,
        seam=_seam(case),
    )
    return {name: _token(case, path) for name, path in raw.items()}


def _present(case: Case, step_id: str) -> set[str]:
    snapshot = io_seam.gather_artifact_presence(case.feature_dir, mission_family="software-dev", step_id=step_id, repo_root=case.repo, seam=_seam(case))
    return set(snapshot.present_artifacts) & {"spec.md", "plan.md", "tasks.md"}


_PLAN_AND_SPEC = {"spec.md", "plan.md"}
_TASK_TRIO = ("plan.md", "spec.md", "tasks.md")

#: shape -> (artifact_search_paths, guard_failure_artifact_paths, present planning artifacts).
_EXPECTED: dict[str, tuple[dict[str, str], dict[str, str], set[str]]] = {
    "nonowned-single_branch": (
        {name: f"R_PRIMARY/{name}" for name in NAMES},
        {name: f"R_PRIMARY/{name}" for name in _TASK_TRIO},
        _PLAN_AND_SPEC,
    ),
    # PRIMARY kinds resolve to the root checkout's primary dir; the coordination kind and the
    # unclassified filename keep the supplied status home.
    "nonowned-coord": (
        {
            "spec.md": "R_PRIMARY/spec.md",
            "plan.md": "R_PRIMARY/plan.md",
            "tasks.md": "R_PRIMARY/tasks.md",
            "issue-matrix.md": "STATUS/issue-matrix.md",
            "custom-notes.txt": "STATUS/custom-notes.txt",
        },
        {name: f"R_PRIMARY/{name}" for name in _TASK_TRIO},
        {"spec.md"},
    ),
    "owned-single_branch": (
        {name: f"P/{name}" for name in NAMES},
        {name: f"P/{name}" for name in _TASK_TRIO},
        _PLAN_AND_SPEC,
    ),
    # Owned coord resolves PRIMARY kinds in the owned checkout P, like owned single_branch
    # (root discipline, WP11). Before WP05 the reverse map tried the non-owned seam first; its
    # status home IS the coordination worktree, so PRIMARY kinds resolved in R, where an owned
    # Mission's planning does not live. The coordination kind and the unclassified filename keep
    # the coordination worktree.
    "owned-coord": (
        {
            "spec.md": "P/spec.md",
            "plan.md": "P/plan.md",
            "tasks.md": "P/tasks.md",
            "issue-matrix.md": "STATUS/issue-matrix.md",
            "custom-notes.txt": "STATUS/custom-notes.txt",
        },
        {name: f"P/{name}" for name in _TASK_TRIO},
        {"spec.md"},
    ),
}


@pytest.mark.parametrize("shape", sorted(_EXPECTED))
def test_presence_answers_are_pinned(tmp_path: Path, shape: str) -> None:
    case = _case(tmp_path, shape)
    search, guard, present = _EXPECTED[shape]

    assert _search_paths(case) == search
    assert _guard_paths(case) == guard
    assert _present(case, "plan") == present
