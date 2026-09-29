"""Tests for the lane work-tip recorder hook installer (#5115, T030).

Real tmp git repos throughout; every commit-firing scenario drives the
INSTALLED hook via a real ``git commit``/``git rebase``/``git cherry-pick``/
``git commit --amend`` subprocess -- never a hand-invoked hook script.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

from specify_cli.policy.lane_tip_recorder import (
    LANE_TIP_HOOK_SIGNATURE,
    install_lane_tip_recorder,
    pending_hook_names,
)

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_LANE_BRANCH = "kitty/mission-foo-01ABCDEF-lane-a"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-q", "-m", "seed")


def _rev(repo: Path, ref: str) -> str:
    return _git(repo, "rev-parse", ref).stdout.strip()


def _tip(repo: Path, branch: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f"refs/spec-kitty/lane-tip/{branch}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _commit_file(repo: Path, name: str, content: str, message: str) -> None:
    (repo / name).write_text(content, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", message)


def test_install_into_an_empty_slot(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)

    installed = install_lane_tip_recorder(repo)

    assert {p.name for p in installed} == {"post-commit", "post-rewrite"}
    for name in ("post-commit", "post-rewrite"):
        hook_path = repo / ".git" / "hooks" / name
        assert hook_path.exists()
        assert LANE_TIP_HOOK_SIGNATURE in hook_path.read_text(encoding="utf-8")
        assert (hook_path.stat().st_mode & 0o777) == 0o755


def test_skips_a_foreign_hook_and_leaves_its_bytes_unchanged(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    hooks_dir = repo / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    foreign = hooks_dir / "post-commit"
    foreign.write_text("#!/bin/sh\necho custom-hook\n", encoding="utf-8")
    foreign.chmod(0o755)
    original_bytes = foreign.read_bytes()

    installed = install_lane_tip_recorder(repo)

    assert {p.name for p in installed} == {"post-rewrite"}
    assert foreign.read_bytes() == original_bytes


def test_pending_hook_names_excludes_a_foreign_slot(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    hooks_dir = repo / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    (hooks_dir / "post-commit").write_text("#!/bin/sh\necho custom\n", encoding="utf-8")

    assert pending_hook_names(repo) == ["post-rewrite"]


def test_reinstall_is_idempotent(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    install_lane_tip_recorder(repo)
    first = (repo / ".git" / "hooks" / "post-commit").read_bytes()

    install_lane_tip_recorder(repo)
    second = (repo / ".git" / "hooks" / "post-commit").read_bytes()

    assert first == second


def test_honours_core_hooks_path(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    custom_hooks = repo / "myhooks"
    custom_hooks.mkdir()
    _git(repo, "config", "core.hooksPath", "myhooks")

    installed = install_lane_tip_recorder(repo)

    assert all(p.is_relative_to(custom_hooks) for p in installed)
    assert not (repo / ".git" / "hooks" / "post-commit").exists()


def test_records_on_a_lane_commit_from_a_linked_worktree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    install_lane_tip_recorder(repo)
    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", "-q", str(wt), "-b", _LANE_BRANCH, "main")

    _commit_file(wt, "w.txt", "linked\n", "linked worktree commit")
    head = _rev(wt, "HEAD")

    assert _tip(repo, _LANE_BRANCH) == head


def test_does_not_match_a_slug_containing_lane_with_a_non_lane_suffix(tmp_path: Path) -> None:
    """M4: ``${b##*-lane-}`` strips to the LAST ``-lane-`` occurrence."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    install_lane_tip_recorder(repo)
    branch = "kitty/mission-foo-lane-recut-01ABC"
    _git(repo, "checkout", "-q", "-b", branch)

    _commit_file(repo, "r.txt", "recut\n", "recut branch commit")

    assert _tip(repo, branch) is None


def test_does_not_match_a_non_lane_branch(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    install_lane_tip_recorder(repo)
    _git(repo, "checkout", "-q", "-b", "feature/unrelated")

    _commit_file(repo, "o.txt", "other\n", "unrelated branch commit")

    assert _tip(repo, "feature/unrelated") is None


def test_records_after_amend(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    install_lane_tip_recorder(repo)
    _git(repo, "checkout", "-q", "-b", _LANE_BRANCH)
    _commit_file(repo, "a.txt", "a\n", "first")

    (repo / "a.txt").write_text("a-amended\n", encoding="utf-8")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-q", "--amend", "-m", "amended")
    head = _rev(repo, "HEAD")

    assert _tip(repo, _LANE_BRANCH) == head


def test_records_after_no_verify_commit(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    install_lane_tip_recorder(repo)
    _git(repo, "checkout", "-q", "-b", _LANE_BRANCH)

    (repo / "nv.txt").write_text("no-verify\n", encoding="utf-8")
    _git(repo, "add", "nv.txt")
    _git(repo, "commit", "-q", "-m", "no-verify commit", "--no-verify")
    head = _rev(repo, "HEAD")

    assert _tip(repo, _LANE_BRANCH) == head


def test_records_after_rebase(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    install_lane_tip_recorder(repo)
    _git(repo, "checkout", "-q", "-b", _LANE_BRANCH)
    _commit_file(repo, "lane.txt", "lane\n", "lane work")
    _git(repo, "checkout", "-q", "main")
    _commit_file(repo, "main.txt", "main\n", "main work")
    _git(repo, "checkout", "-q", _LANE_BRANCH)

    _git(repo, "rebase", "-q", "main")
    head = _rev(repo, "HEAD")

    assert _tip(repo, _LANE_BRANCH) == head


def test_records_after_cherry_pick(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    install_lane_tip_recorder(repo)
    _git(repo, "checkout", "-q", "-b", "source")
    _commit_file(repo, "s.txt", "s\n", "source commit")
    source_sha = _rev(repo, "HEAD")
    _git(repo, "checkout", "-q", "-b", _LANE_BRANCH, "main")

    _git(repo, "cherry-pick", source_sha)
    head = _rev(repo, "HEAD")

    assert _tip(repo, _LANE_BRANCH) == head


def test_hook_exits_zero_even_when_update_ref_fails(tmp_path: Path) -> None:
    """NFR-001: the recorder never changes a commit's exit status."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    install_lane_tip_recorder(repo)
    _git(repo, "checkout", "-q", "-b", _LANE_BRANCH)
    # Collide the ref NAMESPACE with a plain file so ``git update-ref
    # refs/spec-kitty/lane-tip/<branch>`` cannot create the intermediate
    # directory -- forces the hook's own ``update-ref`` call to fail.
    refs_dir = repo / ".git" / "refs" / "spec-kitty"
    refs_dir.mkdir(parents=True, exist_ok=True)
    (refs_dir / "lane-tip").write_text("not a directory\n", encoding="utf-8")

    (repo / "f.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "f.txt")
    proc = subprocess.run(
        ["git", "-C", str(repo), "commit", "-q", "-m", "work despite broken ref namespace"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, f"commit must succeed regardless of the hook's own update-ref failure: {proc.stderr}"


def test_single_sample_commit_overhead_stays_under_150ms(tmp_path: Path) -> None:
    """Fast sanity bound (NOT the NFR-001 evidence -- see the ``timing``-marked p95 test)."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    install_lane_tip_recorder(repo)
    _git(repo, "checkout", "-q", "-b", _LANE_BRANCH)
    (repo / "f.txt").write_text("0\n", encoding="utf-8")
    _git(repo, "add", "f.txt")

    start = time.perf_counter()
    _git(repo, "commit", "-q", "-m", "timed commit")
    elapsed = time.perf_counter() - start

    assert elapsed < 0.150, f"single-sample commit overhead too high: {elapsed * 1000:.1f}ms"


@pytest.mark.timing
def test_p95_commit_overhead_with_hook_stays_under_50ms(tmp_path: Path) -> None:
    """NFR-001 evidence: p95 added-per-commit overhead <= 50ms across 20 commits.

    Compares WITH the hook installed against a bare repo with no hook, so the
    measured delta is the hook's own overhead, not ambient ``git commit`` cost.
    Not selected by any per-PR-blocking job (mission orchestrator runs it at
    mission end per the operator rule -- see the WP07 handoff report).
    """

    def _commit_times(repo: Path, branch: str, count: int) -> list[float]:
        _git(repo, "checkout", "-q", "-b", branch)
        times: list[float] = []
        for i in range(count):
            (repo / f"f{i}.txt").write_text(str(i), encoding="utf-8")
            _git(repo, "add", f"f{i}.txt")
            start = time.perf_counter()
            _git(repo, "commit", "-q", "-m", f"c{i}")
            times.append(time.perf_counter() - start)
        return times

    without_repo = tmp_path / "without"
    _init_repo(without_repo)
    without_times = sorted(_commit_times(without_repo, _LANE_BRANCH, 20))

    with_repo = tmp_path / "with"
    _init_repo(with_repo)
    install_lane_tip_recorder(with_repo)
    with_times = sorted(_commit_times(with_repo, _LANE_BRANCH, 20))

    p95_index = int(len(with_times) * 0.95) - 1
    delta_p95 = with_times[p95_index] - without_times[p95_index]

    assert delta_p95 <= 0.050, f"hook added {delta_p95 * 1000:.1f}ms at p95 (budget: 50ms)"
