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

from specify_cli.lanes.lane_tip import LANE_TIP_REF_PREFIX
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


def test_rendered_hook_writes_the_ref_under_the_lane_tip_prefix(tmp_path: Path) -> None:
    """The hook script and ``lane_tip.tip_ref`` share ONE prefix constant, rendered verbatim."""
    repo = tmp_path / "repo"
    _init_repo(repo)

    install_lane_tip_recorder(repo)

    for name in ("post-commit", "post-rewrite"):
        text = (repo / ".git" / "hooks" / name).read_text(encoding="utf-8")
        assert f'git update-ref "{LANE_TIP_REF_PREFIX}${{b#refs/heads/}}" HEAD >/dev/null 2>&1\n' in text


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
    custom_hooks = tmp_path / "outside-hooks"
    custom_hooks.mkdir()
    _git(repo, "config", "core.hooksPath", str(custom_hooks))

    installed = install_lane_tip_recorder(repo)

    assert installed and all(p.is_relative_to(custom_hooks) for p in installed)
    assert not (repo / ".git" / "hooks" / "post-commit").exists()


def _status(repo: Path) -> str:
    return _git(repo, "status", "--porcelain").stdout


def test_dev_null_hooks_path_is_skipped_without_raising(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    _git(repo, "config", "core.hooksPath", "/dev/null")

    assert install_lane_tip_recorder(repo) == []
    assert pending_hook_names(repo) == []


def test_in_tree_hooks_path_is_never_written(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    husky = repo / ".husky"
    husky.mkdir()
    (husky / "pre-commit").write_text("#!/bin/sh\n", encoding="utf-8")
    _git(repo, "add", ".husky")
    _git(repo, "commit", "-q", "-m", "husky")
    _git(repo, "config", "core.hooksPath", ".husky")

    assert install_lane_tip_recorder(repo) == []
    assert not (husky / "post-commit").exists()
    assert not (husky / "post-rewrite").exists()
    assert _status(repo) == ""
    assert pending_hook_names(repo) == []


def _isolate_git_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point HOME / global / system git config at empty files under ``tmp_path``."""
    home = tmp_path / "home"
    home.mkdir()
    global_cfg = home / ".gitconfig"
    global_cfg.write_text("", encoding="utf-8")
    system_cfg = tmp_path / "system-gitconfig"
    system_cfg.write_text("", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_cfg))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(system_cfg))
    monkeypatch.delenv("GIT_CONFIG_NOSYSTEM", raising=False)
    return global_cfg


def test_global_hooks_path_is_never_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A user-global ``core.hooksPath`` outside the repo is shared by EVERY repository.

    Writing the recorder there would run it in all of the user's repositories, so
    the installer must skip it rather than follow the path.
    """
    global_cfg = _isolate_git_config(monkeypatch, tmp_path)
    global_hooks = tmp_path / "home" / "globalhooks"
    global_hooks.mkdir()
    subprocess.run(["git", "config", "--file", str(global_cfg), "core.hooksPath", str(global_hooks)], check=True)
    repo = tmp_path / "repo"
    _init_repo(repo)

    assert install_lane_tip_recorder(repo) == []
    assert list(global_hooks.iterdir()) == []
    assert pending_hook_names(repo) == []


def test_system_hooks_path_is_never_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _isolate_git_config(monkeypatch, tmp_path)
    system_hooks = tmp_path / "systemhooks"
    system_hooks.mkdir()
    subprocess.run(
        ["git", "config", "--file", str(tmp_path / "system-gitconfig"), "core.hooksPath", str(system_hooks)],
        check=True,
    )
    repo = tmp_path / "repo"
    _init_repo(repo)

    assert install_lane_tip_recorder(repo) == []
    assert list(system_hooks.iterdir()) == []


def test_command_scope_hooks_path_is_never_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _isolate_git_config(monkeypatch, tmp_path)
    command_hooks = tmp_path / "commandhooks"
    command_hooks.mkdir()
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.hooksPath")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", str(command_hooks))
    repo = tmp_path / "repo"
    _init_repo(repo)

    assert install_lane_tip_recorder(repo) == []
    assert list(command_hooks.iterdir()) == []


def test_local_hooks_path_still_installs_when_global_config_is_isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _isolate_git_config(monkeypatch, tmp_path)
    repo = tmp_path / "repo"
    _init_repo(repo)
    custom_hooks = tmp_path / "outside-hooks"
    custom_hooks.mkdir()
    _git(repo, "config", "core.hooksPath", str(custom_hooks))

    installed = install_lane_tip_recorder(repo)

    assert sorted(p.name for p in installed) == ["post-commit", "post-rewrite"]


def test_nonexistent_configured_hooks_path_is_not_created(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    missing = tmp_path / "no-such-hooks"
    _git(repo, "config", "core.hooksPath", str(missing))

    assert install_lane_tip_recorder(repo) == []
    assert not missing.exists()
    assert pending_hook_names(repo) == []


def test_default_git_hooks_dir_still_installs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)

    installed = install_lane_tip_recorder(repo)

    assert sorted(p.name for p in installed) == ["post-commit", "post-rewrite"]
    assert _status(repo) == ""


def test_os_error_during_install_warns_and_continues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)

    def _boom(*_a: object, **_k: object) -> None:
        raise OSError("read-only")

    monkeypatch.setattr("specify_cli.policy.lane_tip_recorder.tempfile.mkstemp", _boom)

    assert install_lane_tip_recorder(repo) == []


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
