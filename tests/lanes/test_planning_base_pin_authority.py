"""#7793 / #7297: the pin branch line and the patch-id follow (``lanes.planning_base``), over real git."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from specify_cli.lanes.planning_base import PatchIdFollow, follow_pin_by_patch_id, pin_branch_line

pytestmark = pytest.mark.git_repo


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _commit(repo: Path, rel: str, content: str, message: str) -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "--allow-empty", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "commit.gpgsign", "false")
    _commit(root, "README.md", "init\n", "init")
    return root


def _mission_branch_with_planning(repo: Path) -> tuple[str, str]:
    """``topic`` off main: a planning commit (the pin), then an implementation commit."""
    _git(repo, "checkout", "-q", "-b", "topic")
    pin = _commit(repo, "kitty-specs/m/tasks/WP01-a.md", "wp01\n", "planning")
    _commit(repo, "src/a.py", "X = 1\n", "implementation")
    return pin, _git(repo, "rev-parse", "HEAD")


def _rebase_onto_new_main(repo: Path) -> None:
    _git(repo, "checkout", "-q", "main")
    _commit(repo, "upstream.txt", "upstream\n", "main moves on")
    _git(repo, "checkout", "-q", "topic")
    _git(repo, "rebase", "-q", "main")


def test_follow_finds_the_rebased_copy_of_the_planning_commit(repo: Path) -> None:
    pin, _ = _mission_branch_with_planning(repo)
    _rebase_onto_new_main(repo)

    follow = follow_pin_by_patch_id(repo, pin, "topic")

    assert follow.miss is None
    assert follow.sha == _git(repo, "rev-parse", "topic~1")
    assert follow.sha != pin
    assert _git(repo, "log", "-1", "--format=%s", follow.sha) == "planning"


def test_follow_reports_no_match_when_the_rebase_rewrote_the_change(repo: Path) -> None:
    pin, _ = _mission_branch_with_planning(repo)
    _git(repo, "checkout", "-q", "main")
    _commit(repo, "upstream.txt", "upstream\n", "main moves on")
    _git(repo, "checkout", "-q", "-B", "topic", "main")
    _commit(repo, "kitty-specs/m/tasks/WP01-a.md", "a different planning change\n", "planning, rewritten")

    assert follow_pin_by_patch_id(repo, pin, "topic") == PatchIdFollow(sha=None, miss="no_match")


def test_follow_refuses_to_guess_between_two_copies(repo: Path) -> None:
    pin, _ = _mission_branch_with_planning(repo)
    _rebase_onto_new_main(repo)
    copy = _git(repo, "rev-parse", "topic~1")
    _git(repo, "checkout", "-q", "main")
    _commit(repo, "noise.txt", "noise\n", "noise")
    _git(repo, "cherry-pick", copy)
    _git(repo, "checkout", "-q", "topic")
    _git(repo, "merge", "-q", "--no-edit", "main")

    follow = follow_pin_by_patch_id(repo, pin, "topic")

    assert follow.sha is None
    assert follow.miss == "ambiguous"
    assert len(follow.candidates) == 2


def test_an_empty_diff_pin_has_no_patch_id_to_follow(repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "topic")
    pin = _commit(repo, "README.md", "init\n", "empty planning commit")
    _rebase_onto_new_main(repo)

    assert follow_pin_by_patch_id(repo, pin, "topic") == PatchIdFollow(sha=None, miss="no_patch_id")


def test_follow_scans_all_history_when_the_pin_shares_no_commit_with_the_tip(repo: Path) -> None:
    _git(repo, "checkout", "-q", "--orphan", "island")
    _git(repo, "rm", "-rq", "--cached", ".")
    pin = _commit(repo, "island.txt", "island\n", "island planning")
    _git(repo, "checkout", "-q", "-f", "main")

    assert follow_pin_by_patch_id(repo, pin, "main").miss == "no_match"


@pytest.mark.parametrize(
    ("meta", "expected"),
    [
        ({"topology": "single_branch", "mission_branch": "kitty/mission-x-01ABCDEF"}, "kitty/mission-x-01ABCDEF"),
        ({"topology": "single_branch", "mission_branch": None}, "main"),
        ({"topology": "single_branch", "mission_branch": "  "}, "main"),
        ({"topology": "lanes", "mission_branch": "kitty/mission-x-01ABCDEF"}, "main"),
        ({"topology": "lanes_with_coord", "mission_branch": "kitty/mission-x-01ABCDEF"}, "main"),
    ],
)
def test_pin_branch_line_is_the_mission_branch_only_for_single_branch(meta: dict[str, object], expected: str) -> None:
    assert pin_branch_line(meta, "main") == expected


def _planning_also_landed_upstream(repo: Path) -> str:
    """The planning commit is cherry-picked onto main (with later main work), then ``topic`` is rebased.

    ``git rebase`` drops the Mission's copy as already applied: the only patch-id match left on
    ``topic`` is main's own copy (#7793 review B2).
    """
    pin, _ = _mission_branch_with_planning(repo)
    _git(repo, "checkout", "-q", "main")
    _git(repo, "-c", "user.name=Other", "cherry-pick", pin)
    _commit(repo, "src/b.py", "Y = 1\n", "later main work")
    _git(repo, "checkout", "-q", "topic")
    _git(repo, "rebase", "-q", "main")
    return pin


def test_follow_never_takes_the_upstream_copy_of_the_planning_commit(repo: Path) -> None:
    pin = _planning_also_landed_upstream(repo)

    assert follow_pin_by_patch_id(repo, pin, "topic", upstream_refs=("main",)) == PatchIdFollow(sha=None, miss="upstream_only")


def test_a_missing_upstream_ref_reaches_nothing(repo: Path) -> None:
    pin, _ = _mission_branch_with_planning(repo)
    _rebase_onto_new_main(repo)

    follow = follow_pin_by_patch_id(repo, pin, "topic", upstream_refs=("no-such-branch", "main"))

    assert follow.sha == _git(repo, "rev-parse", "topic~1")


def test_any_work_package_left_planned_reads_history_and_ignores_migrations() -> None:
    """#7793 / squad F3: the one predicate finalize and the doctor share."""
    from types import SimpleNamespace

    from specify_cli.lanes.persistence import any_work_package_left_planned

    def event(to_lane: str, actor: str = "claude") -> SimpleNamespace:
        return SimpleNamespace(to_lane=to_lane, actor=actor)

    assert any_work_package_left_planned([event("planned"), event("claimed"), event("planned")])
    assert not any_work_package_left_planned([event("planned"), event("claimed", actor="migration:backfill")])
    assert not any_work_package_left_planned([])


@pytest.mark.parametrize("failing", ["merge-base", "rev-list"])
def test_a_git_failure_is_never_read_as_a_miss(repo: Path, monkeypatch: pytest.MonkeyPatch, failing: str) -> None:
    """Squad T4: merge-base / rev-list failing for a real reason raises GitProbeError, never "no_match"."""
    from kernel.git import GitCommandError
    from specify_cli.consolidation.git_probes import GitProbeError
    from specify_cli.lanes import planning_base

    pin, _ = _mission_branch_with_planning(repo)
    real = planning_base.run_git

    def flaky(cwd: Path, *args: str, **kwargs: Any) -> Any:
        if args and args[0] == failing and "--is-ancestor" not in args:
            raise GitCommandError(argv=args, cwd=cwd, returncode=128, stderr="fatal: bad object")
        return real(cwd, *args, **kwargs)

    monkeypatch.setattr(planning_base, "run_git", flaky)
    if failing == "rev-list":
        # Unrelated histories force the full rev-list scan.
        monkeypatch.setattr(planning_base, "commits_in_range", lambda *_a: [])
        _git(repo, "checkout", "-q", "--orphan", "island")
        _git(repo, "rm", "-rq", "--cached", ".")
        _commit(repo, "island.txt", "island\n", "island")
        with pytest.raises(GitProbeError):
            follow_pin_by_patch_id(repo, pin, "island")
        return
    with pytest.raises(GitProbeError):
        follow_pin_by_patch_id(repo, pin, "topic")


def test_an_is_ancestor_failure_for_a_real_reason_raises(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from kernel.git import GitCommandError
    from specify_cli.consolidation.git_probes import GitProbeError
    from specify_cli.lanes import planning_base

    real = planning_base.run_git

    def flaky(cwd: Path, *args: str, **kwargs: Any) -> Any:
        if "--is-ancestor" in args:
            raise GitCommandError(argv=args, cwd=cwd, returncode=128, stderr="fatal: corrupt")
        return real(cwd, *args, **kwargs)

    monkeypatch.setattr(planning_base, "run_git", flaky)
    with pytest.raises(GitProbeError):
        planning_base._on_any_upstream(repo, _git(repo, "rev-parse", "HEAD"), ("main",))
