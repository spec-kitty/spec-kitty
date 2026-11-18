"""SC-001 seam proof: the teardown writes a retarget run does not exercise end to end land on ``<b>`` (#7692, DRIFT-2).

The end-to-end arms (``tests/terminus/test_consolidate_retarget*.py``) produce no late gate-matrix
projection (#6791) and no tracked lane-context tombstone (#6450). Both writers commit on
``run.lanes_manifest.target_branch``, which the executor reseeds from the merge record's target.
These tests drive the REAL writers on a real coordination Mission whose record was rewritten to
``develop`` (``meta.json`` ``target_branch`` on the Mission branch and on ``develop``, the root
checkout on ``develop``), with the destination resolved from that record: both commits land on
``develop`` and the old target ``main`` does not move.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from specify_cli.consolidation import phase_teardown
from specify_cli.consolidation.bookkeeping_projection import project_late_gate_matrix_commits
from specify_cli.consolidation.resolve import _load_or_create_merge_state
from specify_cli.core.paths import resolve_merge_target_branch
from specify_cli.tasks.issue_matrix import IssueMatrixEntry, build_issue_matrix_document
from tests.terminus.conftest import CoordMission, blob_present_at, build_coord_mission

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_OLD, _NEW = "main", "develop"
_ISSUE = "#7692"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _coord_worktree(mission: CoordMission) -> Path:
    return mission.repo / ".worktrees" / f"{mission.slug}-coord"


def _commit_all(base: Path, message: str, *paths: Path) -> None:
    _git(base, "add", *(str(path.relative_to(base)) for path in paths))
    _git(base, "commit", "-qm", message)


def _rewrite_record(base: Path, mission: CoordMission) -> Path:
    """What ``_phase_retarget_record`` commits on each holder: ``meta.json`` naming ``develop``."""
    meta = base / "kitty-specs" / mission.slug / "meta.json"
    payload: dict[str, Any] = json.loads(meta.read_text(encoding="utf-8"))
    payload["target_branch"] = _NEW
    meta.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return meta


def _write_matrix(base: Path, mission: CoordMission, verdict: str, evidence_ref: str) -> Path:
    path = base / "kitty-specs" / mission.slug / "issue-matrix.json"
    rows = {_ISSUE: IssueMatrixEntry(verdict=verdict, evidence_ref=evidence_ref, title="retarget seam")}
    path.write_text(json.dumps(build_issue_matrix_document(rows), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def retargeted(tmp_path: Path) -> CoordMission:
    mission = build_coord_mission(tmp_path, wps=("WP01",), target_branch=_OLD, mid8="01M7692S")
    config = mission.repo / ".kittify" / "config.yaml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("protection:\n  protected_branches: []\n", encoding="utf-8")
    contexts = mission.repo / ".kittify" / "workspaces"
    contexts.mkdir(parents=True, exist_ok=True)
    tracked_context = contexts / f"{mission.slug}-lane-a.json"
    tracked_context.write_text("{}\n", encoding="utf-8")
    _git(mission.repo, "add", "-f", str(config.relative_to(mission.repo)), str(tracked_context.relative_to(mission.repo)))
    _git(mission.repo, "commit", "-qm", "chore(fixture): unprotect main, track a lane context")
    _git(mission.repo, "checkout", "-qb", _NEW, _OLD)
    for base in (mission.repo, _coord_worktree(mission)):
        _commit_all(base, "chore(fixture): retarget main -> develop", _rewrite_record(base, mission), _write_matrix(base, mission, "in-mission", "pending"))
    return mission


def _run(mission: CoordMission, monkeypatch: pytest.MonkeyPatch) -> Any:
    """The run the executor builds: its target is the merge record's, which a retarget record rewrites."""
    recorded, _source = resolve_merge_target_branch(mission.repo, mission.slug, None)
    assert recorded == _NEW, "the rewritten record names the new target"
    retarget = {"from": _OLD, "to": _NEW, "actor": "op", "at": "2026-11-17T09:00:00+00:00", "reason": "r", "committed": True}
    state, _is_resume = _load_or_create_merge_state(
        main_repo=mission.repo,
        mission_slug=mission.slug,
        canonical_id=mission.mission_id,
        target_branch=recorded,
        wp_order=["WP01"],
        push_requested=False,
        retarget=retarget,
    )
    assert state.target_branch == _NEW
    monkeypatch.setattr(phase_teardown, "_carry_pass_anchor_over_own_commit", lambda *_a, **_k: None)
    return SimpleNamespace(main_repo=mission.repo, mission_slug=mission.slug, lanes_manifest=SimpleNamespace(target_branch=state.target_branch), state=state)


def test_the_late_gate_matrix_projection_lands_on_the_new_target(retargeted: CoordMission, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = retargeted
    worktree = _coord_worktree(mission)
    checkpoint = _git(worktree, "rev-parse", "HEAD")
    _commit_all(worktree, "chore: late verdict", _write_matrix(worktree, mission, "fixed", "tests/consolidation/test_retarget_teardown_seams.py"))
    old_tip = _git(mission.repo, "rev-parse", _OLD)
    run = _run(mission, monkeypatch)

    projected = project_late_gate_matrix_commits(main_repo=mission.repo, mission_slug=mission.slug, coord_ref=mission.coord_branch, checkpoint_sha=checkpoint)
    assert projected == (mission.repo / "kitty-specs" / mission.slug / "issue-matrix.json",)
    phase_teardown._commit_projection_and_carry(run, list(projected), "chore: project late gate matrix")

    landed = json.loads(_git(mission.repo, "show", f"{_NEW}:kitty-specs/{mission.slug}/issue-matrix.json"))
    assert landed["rows"][_ISSUE]["verdict"] == "fixed"
    assert _git(mission.repo, "rev-parse", _OLD) == old_tip, "the old target receives nothing"
    assert not blob_present_at(mission.repo, _OLD, f"kitty-specs/{mission.slug}/issue-matrix.json")


def test_the_lane_context_tombstones_land_on_the_new_target(retargeted: CoordMission, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = retargeted
    context = mission.repo / ".kittify" / "workspaces" / f"{mission.slug}-lane-a.json"
    rel = context.relative_to(mission.repo).as_posix()
    old_tip = _git(mission.repo, "rev-parse", _OLD)
    run = _run(mission, monkeypatch)
    context.unlink()

    phase_teardown._commit_tombstoned_workspace_contexts(run, [context])

    assert not blob_present_at(mission.repo, _NEW, rel), "the tombstone is committed on the new target"
    assert _git(mission.repo, "log", "-1", "--format=%s", _NEW) == f"chore({mission.slug}): tombstone lane workspace contexts"
    assert _git(mission.repo, "rev-parse", _OLD) == old_tip and blob_present_at(mission.repo, _OLD, rel), "the old target keeps its copy"
