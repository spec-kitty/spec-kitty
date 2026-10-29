"""The run-wide charter synthesis lock (#6453, WP02): placement, mechanics, restamp wiring."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

import charter.activation.synthesizer.synthesis_lock as lock_module
from charter.activation.bundle_restamp import restamp_bundle_hash
from charter.activation.synthesizer.manifest import MANIFEST_PATH
from charter.activation.synthesizer.synthesis_lock import (
    NON_GIT_LOCK_PATH,
    SYNTHESIS_LOCK_SUBDIRECTORY,
    SynthesisLockHeldError,
    SynthesisLockUnavailableError,
    synthesis_lock,
    synthesis_lock_path,
    synthesis_lock_unless,
)
from kernel.git_topology import GitTopologyUnavailableError, NotAGitRepositoryError
from tests.charter.test_activate_restamps_bundle_hash import _project

pytestmark = pytest.mark.unit

_SHORT_WAIT_S = 0.2


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    return path.resolve()


@contextmanager
def hold_from_other_thread(repo_root: Path) -> Iterator[None]:
    """Hold the synthesis lock on another thread (same-thread re-entry would be vacuous)."""
    acquired = threading.Event()
    release = threading.Event()

    def _holder() -> None:
        with synthesis_lock(repo_root):
            acquired.set()
            release.wait(timeout=30)

    thread = threading.Thread(target=_holder, daemon=True)
    thread.start()
    assert acquired.wait(timeout=10), "holder thread never acquired the lock"
    try:
        yield
    finally:
        release.set()
        thread.join(timeout=10)


@pytest.fixture
def short_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lock_module, "SYNTHESIS_LOCK_TIMEOUT_S", _SHORT_WAIT_S)


def test_lock_path_in_git_repo_is_under_common_dir(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")

    path = synthesis_lock_path(repo)

    assert path.parent == repo / ".git" / "spec-kitty-locks" / SYNTHESIS_LOCK_SUBDIRECTORY
    assert path.suffix == ".lock"
    assert len(path.stem) == 32
    assert synthesis_lock_path(repo) == path


def test_symlinked_root_resolves_to_same_lock_path(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    link = tmp_path / "link"
    link.symlink_to(repo, target_is_directory=True)

    assert synthesis_lock_path(link) == synthesis_lock_path(repo)


def test_two_worktrees_of_one_repository_get_different_lock_paths(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "--allow-empty", "-m", "init")
    other = tmp_path / "other"
    _git(repo, "worktree", "add", "-q", str(other), "-b", "wt")

    main_path = synthesis_lock_path(repo)
    other_path = synthesis_lock_path(other)

    assert main_path != other_path
    assert main_path.parent == other_path.parent


def test_non_git_root_uses_kittify_runtime_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The pytest tmp tree may itself sit inside a git repository, so make the probe say "not git".
    def _not_git(path: Path) -> Path:
        raise NotAGitRepositoryError(path)

    monkeypatch.setattr(lock_module, "git_common_dir", _not_git)
    root = tmp_path / "plain"
    root.mkdir()

    assert synthesis_lock_path(root) == root.resolve() / NON_GIT_LOCK_PATH
    with synthesis_lock(root) as path:
        assert path.is_file()


def test_git_unusable_raises_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(path: Path) -> Path:
        raise GitTopologyUnavailableError(path, "git missing")

    monkeypatch.setattr(lock_module, "git_common_dir", _boom)

    with pytest.raises(SynthesisLockUnavailableError) as excinfo, synthesis_lock(tmp_path):
        pytest.fail("the body must not run")
    assert excinfo.value.code == "CHARTER_SYNTHESIS_LOCK_UNAVAILABLE"
    assert "git could not be invoked" in excinfo.value.body


def test_acquires_with_blocking_bounded_reentrant_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init_repo(tmp_path / "repo")
    calls: list[dict[str, Any]] = []
    real = lock_module.machine_file_lock

    def _spy(path: Path, **kwargs: Any) -> Any:
        calls.append(kwargs)
        return real(path, **kwargs)

    monkeypatch.setattr(lock_module, "machine_file_lock", _spy)

    with synthesis_lock(repo):
        pass

    assert calls == [{"blocking": True, "timeout_s": 10.0, "reentrant": True}]


@pytest.mark.windows_ci
def test_same_thread_reentry_does_not_deadlock(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")

    with synthesis_lock(repo) as outer, synthesis_lock(repo) as inner:
        assert inner == outer


@pytest.mark.windows_ci
def test_other_thread_holding_lock_raises_held(tmp_path: Path, short_wait: None) -> None:
    repo = _init_repo(tmp_path / "repo")

    with hold_from_other_thread(repo), pytest.raises(SynthesisLockHeldError) as excinfo, synthesis_lock(repo):
        pytest.fail("the body must not run")

    assert excinfo.value.code == "CHARTER_SYNTHESIS_LOCK_HELD"
    assert str(synthesis_lock_path(repo)) in excinfo.value.body
    assert "Nothing was written" in excinfo.value.body
    # Positive control: once the holder is gone the same fixture acquires.
    with synthesis_lock(repo):
        pass


def test_crashed_holder_does_not_leave_lock_held(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    code = (
        "import os, sys\n"
        "from pathlib import Path\n"
        "from charter.activation.synthesizer.synthesis_lock import synthesis_lock\n"
        "cm = synthesis_lock(Path(sys.argv[1]))\n"
        "cm.__enter__()\n"
        "os._exit(0)\n"
    )
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)}
    subprocess.run([sys.executable, "-c", code, str(repo)], check=True, env=env, timeout=60)

    with synthesis_lock(repo, timeout_s=_SHORT_WAIT_S):
        pass


def _drift(repo: Path) -> bytes:
    """Make ``charter.yaml`` drift from the stamped manifest; return the manifest bytes before the restamp."""
    charter_yaml = repo / ".kittify" / "charter" / "charter.yaml"
    charter_yaml.write_text(charter_yaml.read_text(encoding="utf-8") + "# drift\n", encoding="utf-8")
    before: bytes = (repo / MANIFEST_PATH).read_bytes()
    return before


def test_restamp_warns_and_skips_while_another_thread_holds_lock(tmp_path: Path, short_wait: None, capsys: pytest.CaptureFixture[str]) -> None:
    """Re-pinned (operator decision 2026-10-27): was ``..._refuses_...`` and expected a raise.

    A non-synthesis caller has already saved its change, so a held lock must not abort it with a
    false "Nothing was written": the restamp is skipped (``False``) with one stderr warning.
    """
    repo = _project(_init_repo(tmp_path / "repo"))
    manifest_before = _drift(repo)

    with hold_from_other_thread(repo):
        assert restamp_bundle_hash(repo) is False
    captured = capsys.readouterr()
    assert (repo / MANIFEST_PATH).read_bytes() == manifest_before
    assert captured.out == ""
    assert len(captured.err.splitlines()) == 1
    assert captured.err.startswith("Warning: ")
    assert "bundle hash was not refreshed" in captured.err
    assert str(synthesis_lock_path(repo)) in captured.err
    assert "next activation change or synthesis run will restamp" in captured.err

    # Positive control on the same fixture, lock free: the restamp lands.
    assert restamp_bundle_hash(repo) is True
    assert (repo / MANIFEST_PATH).read_bytes() != manifest_before
    assert capsys.readouterr().err == ""


def test_restamp_warns_and_skips_when_git_is_unusable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    repo = _project(_init_repo(tmp_path / "repo"))
    manifest_before = _drift(repo)

    def _boom(path: Path) -> Path:
        raise GitTopologyUnavailableError(path, "git missing")

    monkeypatch.setattr(lock_module, "git_common_dir", _boom)

    assert restamp_bundle_hash(repo) is False
    captured = capsys.readouterr()
    assert (repo / MANIFEST_PATH).read_bytes() == manifest_before
    assert len(captured.err.splitlines()) == 1
    assert "bundle hash was not refreshed" in captured.err
    assert "git could not be invoked" in captured.err
    assert "next activation change or synthesis run will restamp" in captured.err

    # Positive control: git usable again, the restamp lands.
    monkeypatch.undo()
    assert restamp_bundle_hash(repo) is True


def test_restamp_nests_inside_a_held_lock_on_same_thread(tmp_path: Path) -> None:
    repo = _project(_init_repo(tmp_path / "repo"))
    charter_yaml = repo / ".kittify" / "charter" / "charter.yaml"
    charter_yaml.write_text(charter_yaml.read_text(encoding="utf-8") + "# drift\n", encoding="utf-8")

    with synthesis_lock(repo):
        assert restamp_bundle_hash(repo) is True


def test_synthesis_lock_unless_read_only_takes_no_lock(tmp_path: Path, short_wait: None) -> None:
    repo = _init_repo(tmp_path / "repo")

    with hold_from_other_thread(repo), synthesis_lock_unless(True, repo) as held:
        assert held is None  # a no-op context: the lock held elsewhere does not block it


def test_synthesis_lock_unless_writing_takes_the_lock(tmp_path: Path, short_wait: None) -> None:
    repo = _init_repo(tmp_path / "repo")

    with synthesis_lock_unless(False, repo) as held:
        assert held == synthesis_lock_path(repo)
    with hold_from_other_thread(repo), pytest.raises(SynthesisLockHeldError), synthesis_lock_unless(False, repo):
        pytest.fail("the body must not run")
