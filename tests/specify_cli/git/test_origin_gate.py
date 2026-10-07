"""The shared evidence-gate adapter over ``origin_freshness`` (FR-003/FR-004)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.git.origin_freshness import (
    FreshnessState,
    FreshnessVerdict,
    OriginCheckMode,
    OriginCheckSetting,
    OriginFreshnessRefused,
)
from specify_cli.git import origin_gate
from specify_cli.git.origin_gate import run_origin_gate, verdict_payload, verdict_payloads
from specify_cli.git.ref_advance import RefAdvanceError
from tests.terminus.conftest import build_coord_mission
from tests.terminus.lanes_fixture import build_lanes_mission
from tests.terminus.two_clone_support import attach_and_push, isolated_git_env, make_bare_remote, unreachable_remote

pytestmark = [pytest.mark.git_repo]

_ENFORCE = OriginCheckSetting(OriginCheckMode.ENFORCE, "default")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def test_verdict_payload_carries_the_additive_row_fields() -> None:
    verdict = FreshnessVerdict("kitty/x", "origin", FreshnessState.BEHIND, behind=2, ahead=1, scope="kitty-specs/m/status.events.jsonl")
    unreachable = FreshnessVerdict("kitty/y", "origin", FreshnessState.UNREACHABLE, detail="ssh: connect failed")

    assert verdict_payload(unreachable)["detail"] == "ssh: connect failed"
    assert verdict_payload(verdict) == {
        "branch": "kitty/x",
        "remote": "origin",
        "state": "behind",
        "behind": 2,
        "ahead": 1,
        "scope": "kitty-specs/m/status.events.jsonl",
        "detail": None,
    }
    assert verdict_payloads([verdict, verdict]) == [verdict_payload(verdict)] * 2


def test_coordination_evidence_missing_locally_is_passed_through_not_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    isolated_git_env(monkeypatch, tmp_path)
    coord = build_coord_mission(tmp_path / "c", wps=("WP01",))
    bare = make_bare_remote(tmp_path)
    attach_and_push(coord.repo, bare, [coord.target_branch, coord.coord_branch])
    for line in _git(coord.repo, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree ") and Path(line.split(" ", 1)[1]) != coord.repo:
            _git(coord.repo, "worktree", "remove", "--force", line.split(" ", 1)[1])
    _git(coord.repo, "branch", "-D", coord.coord_branch)

    assert run_origin_gate(coord.repo, coord.slug, setting=_ENFORCE) == []


def test_lanes_evidence_and_lane_verdicts_refuse_in_enforce_and_warn_otherwise(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    isolated_git_env(monkeypatch, tmp_path)
    mission = build_lanes_mission(tmp_path / "m", wps=("WP01",))
    attach_and_push(mission.repo, make_bare_remote(tmp_path), [mission.target_branch])
    unreachable_remote(mission.repo)
    lanes = list(mission.lane_branches.values())

    with pytest.raises(OriginFreshnessRefused) as refused:
        run_origin_gate(mission.repo, mission.slug, setting=_ENFORCE, lane_branches=lanes)
    assert refused.value.error_codes == ["ORIGIN_UNREACHABLE"]

    warnings = run_origin_gate(mission.repo, mission.slug, setting=OriginCheckSetting(OriginCheckMode.WARN, "flag"), lane_branches=lanes)
    assert warnings and all("continuing" in warning for warning in warnings)


def test_evidence_checkout_is_none_without_a_holder_or_when_worktrees_cannot_be_listed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(origin_gate, "worktrees_with_branch_checked_out", lambda repo, branch: [])
    assert origin_gate._evidence_checkout(tmp_path, "kitty/x") is None

    def boom(repo: Path, branch: str) -> list[Path]:
        raise RefAdvanceError("cannot list")

    monkeypatch.setattr(origin_gate, "worktrees_with_branch_checked_out", boom)
    assert origin_gate._evidence_checkout(tmp_path, "kitty/x") is None

    holder = tmp_path / "wt"
    monkeypatch.setattr(origin_gate, "worktrees_with_branch_checked_out", lambda repo, branch: [holder])
    assert origin_gate._evidence_checkout(tmp_path, "kitty/x") == holder
