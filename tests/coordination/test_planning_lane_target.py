"""#7860: the planning lane's write branch and the checkout that holds it (``planning_lane_target``).

Real git. A default Mission that has not landed writes its planning work on its Mission branch,
in the checkout holding it (the coordination worktree once settled). A missing checkout refuses
with ``PLANNING_CHECKOUT_MISSING``; it never falls back to the repository root checkout (NFR-002).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mission_runtime import PlanningWriteRefUnavailable
from specify_cli.coordination import planning_commit
from specify_cli.coordination.planning_commit import PlanningCheckoutMissing, planning_lane_target, planning_lane_write_ref
from tests._support.git_cli import git_out

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_SLUG = "fx-01M8AAAA"
_MISSION_BRANCH = f"kitty/mission-{_SLUG}"
_TARGET = "main"
_META_REL = f"kitty-specs/{_SLUG}/meta.json"


def _init(repo: Path) -> None:
    repo.mkdir()
    git_out(repo, "init", "-q", "-b", _TARGET)
    git_out(repo, "config", "user.email", "t@example.com")
    git_out(repo, "config", "user.name", "Test")
    git_out(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    git_out(repo, "add", "-A")
    git_out(repo, "commit", "-q", "-m", "init")


def _commit_meta(checkout: Path, payload: dict[str, object]) -> None:
    path = checkout / _META_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    git_out(checkout, "add", "-A")
    git_out(checkout, "commit", "-q", "-m", "meta")


def _default_meta() -> dict[str, object]:
    return {
        "mission_slug": _SLUG,
        "mission_id": "01M8AAAAAAAAAAAAAAAAAAAAAA",
        "target_branch": _TARGET,
        "topology": "lanes_with_coord",
        "topology_source": "default",
        "mission_branch": _MISSION_BRANCH,
        "coordination_branch": _MISSION_BRANCH,
    }


def _settled_default_mission(tmp_path: Path) -> tuple[Path, Path]:
    """The settled shape: the root checkout on the target, the Mission branch in the coordination worktree."""
    repo = tmp_path / "repo"
    _init(repo)
    holder = repo / ".worktrees" / f"{_SLUG}-coord"
    git_out(repo, "worktree", "add", "-q", "-b", _MISSION_BRANCH, str(holder))
    _commit_meta(holder, _default_meta())
    return repo, holder


def test_a_settled_default_mission_writes_in_the_coordination_worktree(tmp_path: Path) -> None:
    repo, holder = _settled_default_mission(tmp_path)

    target = planning_lane_target(repo, _SLUG, _TARGET)

    assert target.branch == _MISSION_BRANCH
    assert target.checkout.resolve() == holder.resolve()
    assert target.on_mission_branch is True


def test_an_unsettled_default_mission_writes_in_the_root_checkout_holding_its_mission_branch(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init(repo)
    git_out(repo, "checkout", "-q", "-b", _MISSION_BRANCH)
    meta = _default_meta() | {"topology": "single_branch", "coordination_branch": None}
    _commit_meta(repo, meta)

    target = planning_lane_target(repo, _SLUG, _TARGET)

    assert (target.branch, target.checkout.resolve(), target.on_mission_branch) == (_MISSION_BRANCH, repo.resolve(), True)


def test_an_explicit_topology_keeps_the_repository_root_and_the_target(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init(repo)
    _commit_meta(repo, {k: v for k, v in _default_meta().items() if k != "topology_source"})

    target = planning_lane_target(repo, _SLUG, _TARGET)

    assert (target.branch, target.checkout.resolve(), target.on_mission_branch) == (_TARGET, repo.resolve(), False)


def test_a_removed_coordination_worktree_refuses_and_names_the_mission_branch(tmp_path: Path) -> None:
    repo, holder = _settled_default_mission(tmp_path)
    git_out(repo, "worktree", "remove", "--force", str(holder))

    with pytest.raises(PlanningCheckoutMissing) as refused:
        planning_lane_target(repo, _SLUG, _TARGET)

    assert refused.value.error_code == "PLANNING_CHECKOUT_MISSING"
    assert _MISSION_BRANCH in str(refused.value)
    assert f"spec-kitty doctor coordination --mission {_SLUG} --fix" in str(refused.value)


def test_a_legacy_mission_with_no_meta_anywhere_keeps_the_target(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init(repo)

    ref = planning_lane_write_ref(repo, _SLUG, _TARGET)

    assert (ref.branch, ref.on_mission_branch, ref.meta_found) == (_TARGET, False, False)


def test_a_default_mission_whose_branch_no_checkout_holds_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The meta was found but no checkout holds the Mission branch (the root is on the target): refuse, never the root."""
    repo, _holder = _settled_default_mission(tmp_path)
    monkeypatch.setattr(planning_commit, "primary_partition_checkout", lambda *_a: None)

    with pytest.raises(PlanningCheckoutMissing):
        planning_lane_target(repo, _SLUG, _TARGET)


def test_a_git_failure_while_probing_the_mission_branch_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from kernel.git import GitCommandError

    repo, holder = _settled_default_mission(tmp_path)
    git_out(repo, "worktree", "remove", "--force", str(holder))

    def _broken(*_a: object, **_k: object) -> object:
        raise GitCommandError(argv=("ls-tree",), cwd=repo, returncode=128, stderr="boom")

    import kernel.git

    monkeypatch.setattr(kernel.git, "tree_entry", _broken)

    with pytest.raises(PlanningWriteRefUnavailable):
        planning_lane_write_ref(repo, _SLUG, _TARGET)
