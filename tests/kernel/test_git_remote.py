"""Behaviour of :mod:`kernel.git.remote` against a REAL bare remote (FR-013, FR-017, NFR-001, NFR-002)."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any

import pytest

from kernel.git import remote as git_remote
from kernel.git.remote import (
    FETCH_TIMEOUT,
    LS_REMOTE_TIMEOUT,
    Divergence,
    RemoteUnreachable,
    divergence,
    fetch_branches,
    no_prompt_env,
    remote_heads,
    resolve_remote,
    tracking_ref,
)
from kernel.git.runner import GitCommandError, GitResult
from tests._support.two_clone import (
    attach_and_push,
    clone_from,
    isolated_git_env,
    make_bare_remote,
    unreachable_remote,
)

pytestmark = [pytest.mark.git_repo]


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _commit(repo: Path, name: str, content: str = "x", message: str | None = None) -> str:
    target = repo / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message or f"add {name}")
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Return ``(bare, work)``: a bare origin and a working clone with ``main`` pushed."""
    isolated_git_env(monkeypatch, tmp_path)
    bare = make_bare_remote(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    _git(work, "config", "user.name", "T")
    _git(work, "config", "user.email", "t@example.com")
    _commit(work, "README.md")
    attach_and_push(work, bare, ["main"])
    _git(work, "fetch", "-q", "origin")
    _git(work, "branch", "-q", "--set-upstream-to=origin/main", "main")
    return bare, work


# --- resolve_remote / tracking_ref -------------------------------------------------


def test_resolve_remote_prefers_branch_config(world: tuple[Path, Path]) -> None:
    _, work = world
    _git(work, "remote", "add", "up", str(work))
    _git(work, "config", "branch.feat.remote", "up")
    assert resolve_remote(work, "feat") == "up"


def test_resolve_remote_single_remote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    isolated_git_env(monkeypatch, tmp_path)
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "remote", "add", "fork", "/nonexistent")
    assert resolve_remote(repo, "main") == "fork"


def test_resolve_remote_origin_among_several(world: tuple[Path, Path]) -> None:
    _, work = world
    _git(work, "remote", "add", "other", "/nonexistent")
    assert resolve_remote(work, "unconfigured") == "origin"


def test_resolve_remote_ambiguous_is_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    isolated_git_env(monkeypatch, tmp_path)
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "remote", "add", "a", "/x")
    _git(repo, "remote", "add", "b", "/y")
    assert resolve_remote(repo, "main") is None


def test_resolve_remote_no_remotes_is_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    isolated_git_env(monkeypatch, tmp_path)
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    assert resolve_remote(repo, "main") is None


def test_resolve_remote_dot_is_treated_as_unset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    isolated_git_env(monkeypatch, tmp_path)
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "remote", "add", "fork", "/nonexistent")
    _git(repo, "config", "branch.main.remote", ".")
    assert resolve_remote(repo, "main") == "fork"


def test_tracking_ref() -> None:
    assert tracking_ref("origin", "kitty/mission-x-lane-a") == "refs/remotes/origin/kitty/mission-x-lane-a"


# --- remote_heads ------------------------------------------------------------------


def test_remote_heads_lists_present_omits_absent(world: tuple[Path, Path]) -> None:
    _, work = world
    main_sha = _git(work, "rev-parse", "main")
    assert remote_heads(work, "origin", ["main", "absent"]) == {"main": main_sha}


def test_remote_heads_exact_ref_match_only(world: tuple[Path, Path]) -> None:
    _, work = world
    _git(work, "push", "-q", "origin", "main:refs/heads/team/main")
    assert set(remote_heads(work, "origin", ["main"])) == {"main"}


def test_remote_heads_empty_branches_does_not_contact(world: tuple[Path, Path]) -> None:
    _, work = world
    unreachable_remote(work)
    assert remote_heads(work, "origin", []) == {}


def test_remote_heads_unreachable_raises_not_empty(world: tuple[Path, Path]) -> None:
    _, work = world
    unreachable_remote(work)
    with pytest.raises(RemoteUnreachable) as excinfo:
        remote_heads(work, "origin", ["main"])
    assert excinfo.value.remote == "origin"
    assert isinstance(excinfo.value, GitCommandError)
    assert str(excinfo.value).startswith("remote origin unreachable:")


def _fake_ssh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, sleep: float = 0.0) -> Path:
    """Install a fake ssh as ``GIT_SSH_COMMAND``; it records argv + env, optionally sleeps, then fails."""
    log = tmp_path / "ssh.log"
    script = tmp_path / "bin" / "ssh"  # ssh-like basename, so BatchMode is appended to it
    script.parent.mkdir(exist_ok=True)
    script.write_text(
        f'#!/bin/sh\necho "ARGV: $*" >> "{log}"\necho "PROMPT: ${{GIT_TERMINAL_PROMPT-unset}}" >> "{log}"\nsleep {sleep}\nexit 255\n',
        encoding="utf-8",
    )
    script.chmod(0o755)
    monkeypatch.setenv("GIT_SSH_COMMAND", str(script))
    monkeypatch.delenv("GIT_TERMINAL_PROMPT", raising=False)
    return log


def _ssh_remote(work: Path) -> None:
    _git(work, "remote", "set-url", "origin", "ssh://git@example.invalid/nonexistent.git")


def test_remote_heads_passes_non_prompting_env_to_transport(world: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-002: the transport sees BatchMode=yes and GIT_TERMINAL_PROMPT=0, set by the code, not the test."""
    _, work = world
    log = _fake_ssh(tmp_path, monkeypatch)
    _ssh_remote(work)
    with pytest.raises(RemoteUnreachable):
        remote_heads(work, "origin", ["main"])
    recorded = log.read_text(encoding="utf-8")
    assert "BatchMode=yes" in recorded
    assert "PROMPT: 0" in recorded


def test_fetch_branches_passes_non_prompting_env_to_transport(world: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, work = world
    log = _fake_ssh(tmp_path, monkeypatch)
    _ssh_remote(work)
    with pytest.raises(RemoteUnreachable):
        fetch_branches(work, "origin", ["main"])
    recorded = log.read_text(encoding="utf-8")
    assert "BatchMode=yes" in recorded
    assert "PROMPT: 0" in recorded


def test_describe_remote_head_passes_non_prompting_env_to_transport(world: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, work = world
    log = _fake_ssh(tmp_path, monkeypatch)
    _ssh_remote(work)
    assert git_remote.describe_remote_head(work, "origin") is None
    recorded = log.read_text(encoding="utf-8")
    assert "BatchMode=yes" in recorded
    assert "PROMPT: 0" in recorded


def test_fetch_branches_never_recurses_into_submodules(world: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """A submodule fetch would contact further remotes outside the one bounded contact."""
    _, work = world
    seen: list[tuple[str, ...]] = []
    real_run_git = git_remote.run_git

    def recording(cwd: Path, *args: str, **kwargs: Any) -> GitResult:
        seen.append(args)
        return real_run_git(cwd, *args, **kwargs)

    monkeypatch.setattr(git_remote, "run_git", recording)
    fetch_branches(work, "origin", ["main"])

    (fetch_argv,) = [argv for argv in seen if argv[:1] == ("fetch",)]
    assert "--no-recurse-submodules" in fetch_argv
    assert fetch_argv.index("--no-recurse-submodules") < fetch_argv.index("origin")


@pytest.mark.parametrize("call", ["remote_heads", "fetch_branches"])
def test_contact_is_bounded_by_timeout(world: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, call: str) -> None:
    """NFR-001: a hanging transport is cut off at the timeout and classified RemoteUnreachable(timed_out)."""
    _, work = world
    _fake_ssh(tmp_path, monkeypatch, sleep=30.0)
    _ssh_remote(work)
    started = time.monotonic()
    contact = (
        (lambda: remote_heads(work, "origin", ["main"], timeout=1.0)) if call == "remote_heads" else (lambda: fetch_branches(work, "origin", ["main"], timeout=1.0))
    )
    with pytest.raises(RemoteUnreachable) as excinfo:
        contact()
    assert excinfo.value.timed_out
    assert time.monotonic() - started < 2.0


def test_describe_remote_head_is_bounded_by_timeout(world: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, work = world
    _fake_ssh(tmp_path, monkeypatch, sleep=30.0)
    _ssh_remote(work)
    started = time.monotonic()
    assert git_remote.describe_remote_head(work, "origin", timeout=1.0) is None
    assert time.monotonic() - started < 2.0


def test_clone_repository_resolves_relative_paths_against_cwd(world: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Relative url/dest resolve against the process cwd, exactly as the doctrine git source's inherited cwd does."""
    bare, _ = world
    launch = tmp_path / "launch"
    (launch / "packs").mkdir(parents=True)
    monkeypatch.chdir(launch)
    rel_bare = Path("..") / bare.name
    result = git_remote.clone_repository(str(rel_bare), Path("packs") / "p")
    assert result.returncode == 0
    assert (launch / "packs" / "p" / "README.md").exists()
    assert not (launch / "packs" / "packs").exists()


# --- fetch_branches ----------------------------------------------------------------


def test_fetch_branches_writes_tracking_ref_only(world: tuple[Path, Path], tmp_path: Path) -> None:
    bare, work = world
    other = clone_from(bare, tmp_path / "other")
    _git(other, "checkout", "-q", "-b", "feature")
    pushed = _commit(other, "f.txt")
    _git(other, "push", "-q", "origin", "feature")

    fetch_branches(work, "origin", ["feature"])

    assert _git(work, "rev-parse", "refs/remotes/origin/feature") == pushed
    absent = subprocess.run(["git", "-C", str(work), "rev-parse", "--verify", "--quiet", "refs/heads/feature"], capture_output=True, check=False)
    assert absent.returncode != 0


def test_fetch_branches_empty_does_not_contact(world: tuple[Path, Path]) -> None:
    _, work = world
    unreachable_remote(work)
    fetch_branches(work, "origin", [])


def test_fetch_branches_unreachable_raises(world: tuple[Path, Path]) -> None:
    _, work = world
    unreachable_remote(work)
    with pytest.raises(RemoteUnreachable):
        fetch_branches(work, "origin", ["main"])


# --- divergence --------------------------------------------------------------------


def test_divergence_equal(world: tuple[Path, Path]) -> None:
    _, work = world
    assert divergence(work, "main", "refs/remotes/origin/main") == Divergence(ahead=0, behind=0)


def test_divergence_local_ahead(world: tuple[Path, Path]) -> None:
    _, work = world
    _commit(work, "l.txt")
    result = divergence(work, "main", "refs/remotes/origin/main")
    assert (result.ahead, result.behind, result.diverged) == (1, 0, False)


def test_divergence_behind_two(world: tuple[Path, Path], tmp_path: Path) -> None:
    bare, work = world
    other = clone_from(bare, tmp_path / "other")
    _commit(other, "a.txt")
    _commit(other, "b.txt")
    _git(other, "push", "-q", "origin", "main")
    fetch_branches(work, "origin", ["main"])
    result = divergence(work, "main", "refs/remotes/origin/main")
    assert (result.ahead, result.behind, result.diverged) == (0, 2, False)


def test_divergence_diverged(world: tuple[Path, Path], tmp_path: Path) -> None:
    bare, work = world
    other = clone_from(bare, tmp_path / "other")
    _commit(other, "a.txt")
    _commit(other, "b.txt")
    _git(other, "push", "-q", "origin", "main")
    _commit(work, "l.txt")
    fetch_branches(work, "origin", ["main"])
    result = divergence(work, "main", "refs/remotes/origin/main")
    assert (result.ahead, result.behind, result.diverged) == (1, 2, True)


def test_divergence_path_scoped_ignores_unrelated_remote_commits(world: tuple[Path, Path], tmp_path: Path) -> None:
    bare, work = world
    other = clone_from(bare, tmp_path / "other")
    _commit(other, "b.txt")
    _git(other, "push", "-q", "origin", "main")
    fetch_branches(work, "origin", ["main"])
    scoped = divergence(work, "main", "refs/remotes/origin/main", paths=["a/status.events.jsonl"])
    assert scoped.behind == 0

    _commit(other, "a/status.events.jsonl", "{}")
    _git(other, "push", "-q", "origin", "main")
    fetch_branches(work, "origin", ["main"])
    assert divergence(work, "main", "refs/remotes/origin/main", paths=["a/status.events.jsonl"]).behind == 1


# --- no_prompt_env -----------------------------------------------------------------


def _clean_ssh_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GIT_SSH_COMMAND", raising=False)
    monkeypatch.delenv("GIT_SSH", raising=False)


def test_no_prompt_env_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    isolated_git_env(monkeypatch, tmp_path)
    _clean_ssh_env(monkeypatch)
    env = no_prompt_env(cwd=tmp_path)
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GIT_SSH_COMMAND"] == "ssh -o BatchMode=yes"


def test_no_prompt_env_preserves_existing_ssh_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    isolated_git_env(monkeypatch, tmp_path)
    monkeypatch.setenv("GIT_SSH_COMMAND", "ssh -i /k")
    assert no_prompt_env(cwd=tmp_path)["GIT_SSH_COMMAND"] == "ssh -i /k -o BatchMode=yes"


def test_no_prompt_env_honours_core_ssh_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A repository's ``core.sshCommand`` is carried over, not overridden by the bare default."""
    isolated_git_env(monkeypatch, tmp_path)
    _clean_ssh_env(monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "core.sshCommand", "ssh -i /work/key")
    assert no_prompt_env(cwd=repo)["GIT_SSH_COMMAND"] == "ssh -i /work/key -o BatchMode=yes"


def test_no_prompt_env_for_clone_ignores_the_cwd_repository_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A clone reads no repository's local config, so the project's key must not leak into it."""
    isolated_git_env(monkeypatch, tmp_path)
    _clean_ssh_env(monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "core.sshCommand", "ssh -i /work/key")
    monkeypatch.chdir(repo)
    assert no_prompt_env(clone=True)["GIT_SSH_COMMAND"] == "ssh -o BatchMode=yes"


def test_no_prompt_env_for_clone_honours_global_ssh_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    isolated_git_env(monkeypatch, tmp_path)
    _clean_ssh_env(monkeypatch)
    _git(tmp_path, "config", "--global", "core.sshCommand", "ssh -i /global/key")
    monkeypatch.chdir(tmp_path)
    assert no_prompt_env(clone=True)["GIT_SSH_COMMAND"] == "ssh -i /global/key -o BatchMode=yes"


def test_no_prompt_env_env_command_beats_core_ssh_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    isolated_git_env(monkeypatch, tmp_path)
    monkeypatch.setenv("GIT_SSH_COMMAND", "ssh -i /env")
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "core.sshCommand", "ssh -i /cfg")
    assert no_prompt_env(cwd=repo)["GIT_SSH_COMMAND"] == "ssh -i /env -o BatchMode=yes"


def test_no_prompt_env_non_ssh_command_is_left_alone(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    isolated_git_env(monkeypatch, tmp_path)
    _clean_ssh_env(monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "core.sshCommand", "/opt/wrap/ssh-agentless --flag")
    assert no_prompt_env(cwd=repo)["GIT_SSH_COMMAND"] == "/opt/wrap/ssh-agentless --flag"


def test_no_prompt_env_existing_batchmode_not_duplicated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    isolated_git_env(monkeypatch, tmp_path)
    monkeypatch.setenv("GIT_SSH_COMMAND", "/usr/bin/ssh -o BatchMode=no")
    assert no_prompt_env(cwd=tmp_path)["GIT_SSH_COMMAND"] == "/usr/bin/ssh -o BatchMode=no"


def test_no_prompt_env_git_ssh_set_leaves_ssh_command_unset(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``GIT_SSH`` is only honoured by git while ``GIT_SSH_COMMAND`` is absent."""
    isolated_git_env(monkeypatch, tmp_path)
    monkeypatch.delenv("GIT_SSH_COMMAND", raising=False)
    monkeypatch.setenv("GIT_SSH", "/opt/wrap/ssh")
    env = no_prompt_env(cwd=tmp_path)
    assert "GIT_SSH_COMMAND" not in env
    assert env["GIT_SSH"] == "/opt/wrap/ssh"
    assert env["GIT_TERMINAL_PROMPT"] == "0"


def test_no_prompt_env_accepts_base_mapping() -> None:
    env = no_prompt_env({"FOO": "bar"})
    assert env["FOO"] == "bar"
    assert env["GIT_TERMINAL_PROMPT"] == "0"


def test_timeouts_are_bounded() -> None:
    assert LS_REMOTE_TIMEOUT == 5.0
    assert FETCH_TIMEOUT == 15.0
    assert git_remote.CLONE_TIMEOUT > FETCH_TIMEOUT


# --- describe_remote_head / doctrine wrappers --------------------------------------


def test_describe_remote_head_reads_default_branch(world: tuple[Path, Path]) -> None:
    _, work = world
    assert git_remote.describe_remote_head(work, "origin") == "main"


def test_describe_remote_head_unreachable_is_none(world: tuple[Path, Path]) -> None:
    _, work = world
    unreachable_remote(work)
    assert git_remote.describe_remote_head(work, "origin") is None


def test_clone_repository_and_fetch_tags(world: tuple[Path, Path], tmp_path: Path) -> None:
    bare, work = world
    dest = tmp_path / "cloned"
    assert git_remote.clone_repository(str(bare), dest).returncode == 0
    assert (dest / "README.md").exists()
    _git(work, "tag", "v1")
    _git(work, "push", "-q", "origin", "v1")
    assert git_remote.fetch_tags(dest, "origin").returncode == 0
    assert _git(dest, "tag", "--list", "v1") == "v1"


# --- shared two-clone helper smoke --------------------------------------------------


def test_two_clone_helper_smoke(world: tuple[Path, Path], tmp_path: Path) -> None:
    bare, work = world
    second = clone_from(bare, tmp_path / "second")
    assert _git(second, "config", "user.email")
    pushed = _commit(second, "s.txt")
    _git(second, "push", "-q", "origin", "main")
    assert remote_heads(work, "origin", ["main"]) == {"main": pushed}
