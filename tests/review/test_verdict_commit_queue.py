"""Contract tests for the checkout-wide review verdict commit queue."""

from __future__ import annotations

import ast
import math
import multiprocessing
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from kernel.git_topology import clear_caches, git_common_dir
from specify_cli.review import verdict_commit_queue
from specify_cli.review.verdict_commit_queue import (
    DEFAULT_VERDICT_SAVE_TIMEOUT_SECONDS,
    VerdictSaveBusy,
    VerdictSaveReentrant,
    acquire_verdict_save_queue,
    verdict_save_queue_is_held,
    verdict_save_queue_path,
)
from tests._perf_helpers import assert_timing_budget

pytestmark = [pytest.mark.git_repo]  # exercises real repos, worktrees, and processes


def _git(repo: Path, *args: str) -> str:
    """Run Git in ``repo`` and return stripped stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _init_repo(path: Path) -> Path:
    """Create a committed repository suitable for linked worktrees and clones."""
    path.mkdir()
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "queue-tests@example.invalid")
    _git(path, "config", "user.name", "Queue Tests")
    (path / "README.md").write_text("queue test\n", encoding="utf-8")
    _git(path, "add", "README.md")
    _git(path, "commit", "-qm", "initial")
    clear_caches()
    return path


def _hold_queue_until_terminated(repository: str, ready: Any) -> None:
    """Spawn-safe worker that owns the queue until its process is terminated."""
    with acquire_verdict_save_queue(Path(repository), timeout_seconds=2.0):
        ready.send(True)
        while True:
            time.sleep(0.05)


def _hold_queue_until_released(repository: str, ready: Any, release: Any) -> None:
    """Spawn-safe owner that exits normally after the parent releases it."""
    with acquire_verdict_save_queue(Path(repository), timeout_seconds=2.0):
        ready.send(True)
        if not release.wait(10):
            raise TimeoutError("parent did not release queue owner")


def _wait_for_queue(repository: str, attempting: Any, acquired: Any) -> None:
    """Spawn-safe contender that reports before and after bounded acquisition."""
    attempting.set()
    with acquire_verdict_save_queue(Path(repository), timeout_seconds=3.0):
        acquired.send(True)


@pytest.fixture
def repository(tmp_path: Path) -> Iterator[Path]:
    """Yield a real repository and clear cached topology before and after use."""
    repo = _init_repo(tmp_path / "repo")
    try:
        yield repo
    finally:
        clear_caches()


def test_default_timeout_is_forwarded_and_lock_timeout_is_typed(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The exact ten-second default reaches ``kernel.locks`` without a retry loop.

    Migrated (mission cross-os-primitive-unification WP05/#4714) onto the
    canonical primitive's G6 test-double injection seam: ``machine_file_lock``
    resolves ``SyncMachineFileLock`` through ``kernel.locks``'s OWN namespace
    at call time, so the double is installed there -- not as an attribute of
    this module (there is no ``verdict_commit_queue.FileLock`` any more).
    """
    captured: dict[str, object] = {}

    class RefusingLock:
        def __init__(self, path: Path, *, blocking: bool, timeout_s: float | None, reentrant: bool = False) -> None:
            del reentrant
            captured["path"] = path
            captured["blocking"] = blocking
            captured["timeout_s"] = timeout_s

        def __enter__(self) -> object:
            raise verdict_commit_queue.LockAcquireTimeout(path=str(captured["path"]))

        def __exit__(self, *exc: object) -> None:
            pytest.fail("an unacquired lock must not be released")

    monkeypatch.setattr("kernel.locks.SyncMachineFileLock", RefusingLock)

    assert DEFAULT_VERDICT_SAVE_TIMEOUT_SECONDS == 10.0
    with (
        pytest.raises(VerdictSaveBusy) as raised,
        acquire_verdict_save_queue(repository),
    ):
        pytest.fail("timed-out acquisition must not enter")

    assert captured == {
        "path": verdict_save_queue_path(repository),
        "blocking": True,
        "timeout_s": 10.0,
    }
    assert raised.value.lock_path == verdict_save_queue_path(repository)
    assert raised.value.timeout_seconds == 10.0
    assert isinstance(raised.value.__cause__, verdict_commit_queue.LockAcquireTimeout)


@pytest.mark.parametrize(
    "invalid_timeout",
    [math.nan, math.inf, -math.inf, 0.0, -0.25],
    ids=["nan", "positive-infinity", "negative-infinity", "zero", "negative"],
)
def test_queue_rejects_non_finite_or_non_positive_timeout_before_acquisition(
    repository: Path,
    invalid_timeout: float,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every invalid budget fails before lock construction or acquisition."""
    lock_constructed = False

    class UnexpectedLock:
        def __init__(self, path: Path, **_kwargs: object) -> None:
            del path
            nonlocal lock_constructed
            lock_constructed = True

    monkeypatch.setattr("kernel.locks.SyncMachineFileLock", UnexpectedLock)

    with (
        pytest.raises(ValueError, match="finite and positive"),
        acquire_verdict_save_queue(repository, timeout_seconds=invalid_timeout),
    ):
        pytest.fail("invalid timeout must not enter")

    assert not lock_constructed


def test_queue_releases_after_normal_and_exceptional_exit(repository: Path) -> None:
    """Both context-manager exit paths release ownership immediately."""
    with acquire_verdict_save_queue(repository, timeout_seconds=0.5):
        assert verdict_save_queue_is_held(repository)
    assert not verdict_save_queue_is_held(repository)

    with (
        pytest.raises(LookupError, match="body failed"),
        acquire_verdict_save_queue(repository, timeout_seconds=0.5),
    ):
        raise LookupError("body failed")

    with acquire_verdict_save_queue(repository, timeout_seconds=0.5):
        assert verdict_save_queue_is_held(repository)


def test_nested_acquisition_is_explicitly_refused_without_waiting(repository: Path) -> None:
    """Same-context nesting never relies on a hidden recursive lock contract.

    Functional half of the #4015 split; the wall-clock ceiling now lives in
    ``test_nested_acquisition_refusal_stays_fast`` (nightly-only).
    """
    with (
        acquire_verdict_save_queue(repository, timeout_seconds=0.5),
        pytest.raises(VerdictSaveReentrant) as raised,
        acquire_verdict_save_queue(repository),
    ):
        pytest.fail("nested acquisition must not enter")

    assert raised.value.lock_path == verdict_save_queue_path(repository)


@pytest.mark.performance
def test_nested_acquisition_refusal_stays_fast(repository: Path) -> None:
    """Nested acquisition is refused promptly, without waiting (nightly).

    Split from ``test_nested_acquisition_is_explicitly_refused_without_waiting``
    (#4015); budget preserved.
    """
    with acquire_verdict_save_queue(repository, timeout_seconds=0.5):
        started = time.perf_counter()
        with (
            pytest.raises(VerdictSaveReentrant),
            acquire_verdict_save_queue(repository),
        ):
            pytest.fail("nested acquisition must not enter")
        elapsed = time.perf_counter() - started

    assert_timing_budget(elapsed, 0.5, name="nested_acquisition_refusal")


def test_process_death_releases_queue_ownership(repository: Path) -> None:
    """OS lock cleanup permits acquisition after a spawned owner is terminated."""
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(
        target=_hold_queue_until_terminated,
        args=(str(repository), child),
    )
    process.start()
    child.close()
    try:
        assert parent.poll(10), "spawned owner never acquired the queue"
        assert parent.recv() is True
        process.terminate()
        process.join(timeout=10)
        assert not process.is_alive()

        with acquire_verdict_save_queue(repository, timeout_seconds=2.0):
            assert verdict_save_queue_is_held(repository)
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=10)
        parent.close()


def test_live_holder_causes_real_bounded_busy_refusal(repository: Path) -> None:
    """A live owner excludes a real contender until its finite budget expires.

    Functional half of the #4015 split; the wall-clock window now lives in
    ``test_live_holder_busy_refusal_stays_bounded`` (nightly-only).
    """
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    release = context.Event()
    owner = context.Process(
        target=_hold_queue_until_released,
        args=(str(repository), child, release),
    )
    owner.start()
    child.close()
    try:
        assert parent.poll(10), "spawned owner never acquired the queue"
        assert parent.recv() is True

        with (
            pytest.raises(VerdictSaveBusy) as raised,
            acquire_verdict_save_queue(repository, timeout_seconds=0.2),
        ):
            pytest.fail("live owner must exclude the contender")

        assert raised.value.timeout_seconds == 0.2
        assert owner.is_alive()
        release.set()
        owner.join(timeout=10)
        assert not owner.is_alive()
        assert owner.exitcode == 0
    finally:
        release.set()
        if owner.is_alive():
            owner.terminate()
            owner.join(timeout=10)
        parent.close()


@pytest.mark.performance
def test_live_holder_busy_refusal_stays_bounded(repository: Path) -> None:
    """A live owner's busy refusal happens within its finite budget window (nightly).

    Split from ``test_live_holder_causes_real_bounded_busy_refusal`` (#4015);
    budget preserved (the original two-sided ``0.15 <= elapsed < 2.0`` window:
    long enough to prove the contender genuinely waited, short enough to
    prove it never blocked past its own timeout).
    """
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    release = context.Event()
    owner = context.Process(
        target=_hold_queue_until_released,
        args=(str(repository), child, release),
    )
    owner.start()
    child.close()
    try:
        parent.poll(10)
        parent.recv()

        started = time.perf_counter()
        with (
            pytest.raises(VerdictSaveBusy),
            acquire_verdict_save_queue(repository, timeout_seconds=0.2),
        ):
            pytest.fail("live owner must exclude the contender")
        elapsed = time.perf_counter() - started

        assert 0.15 <= elapsed < 2.0
        release.set()
        owner.join(timeout=10)
    finally:
        release.set()
        if owner.is_alive():
            owner.terminate()
            owner.join(timeout=10)
        parent.close()


def test_waiting_contender_acquires_after_live_owner_releases_normally(
    repository: Path,
) -> None:
    """A queued contender waits behind a live owner and wins after release."""
    context = multiprocessing.get_context("spawn")
    owner_ready_parent, owner_ready_child = context.Pipe(duplex=False)
    acquired_parent, acquired_child = context.Pipe(duplex=False)
    release = context.Event()
    attempting = context.Event()
    owner = context.Process(
        target=_hold_queue_until_released,
        args=(str(repository), owner_ready_child, release),
    )
    contender = context.Process(
        target=_wait_for_queue,
        args=(str(repository), attempting, acquired_child),
    )
    owner.start()
    owner_ready_child.close()
    try:
        assert owner_ready_parent.poll(10), "spawned owner never acquired the queue"
        assert owner_ready_parent.recv() is True
        contender.start()
        acquired_child.close()
        assert attempting.wait(10), "contender never attempted queue acquisition"
        assert not acquired_parent.poll(0.25), "contender bypassed the live owner"

        release.set()
        assert acquired_parent.poll(10), "waiting contender did not acquire after release"
        assert acquired_parent.recv() is True
        owner.join(timeout=10)
        contender.join(timeout=10)

        assert not owner.is_alive()
        assert not contender.is_alive()
        assert owner.exitcode == 0
        assert contender.exitcode == 0
    finally:
        release.set()
        for process in (owner, contender):
            if process.is_alive():
                process.terminate()
                process.join(timeout=10)
        owner_ready_parent.close()
        acquired_parent.close()


def test_queue_path_converges_for_linked_worktrees_and_missions(
    repository: Path,
    tmp_path: Path,
) -> None:
    """All worktrees and missions sharing one common dir share one queue path."""
    linked = tmp_path / "linked"
    coordination = tmp_path / "coordination"
    _git(repository, "worktree", "add", "-q", "--detach", str(linked), "HEAD")
    _git(repository, "worktree", "add", "-q", "--detach", str(coordination), "HEAD")
    clear_caches()

    primary_path_for_mission_a = verdict_save_queue_path(repository)
    primary_path_for_mission_b = verdict_save_queue_path(repository / ".")

    assert primary_path_for_mission_a == primary_path_for_mission_b
    assert verdict_save_queue_path(linked) == primary_path_for_mission_a
    assert verdict_save_queue_path(coordination) == primary_path_for_mission_a
    assert primary_path_for_mission_a.parent.parent == git_common_dir(repository)


def test_independent_clones_have_different_queue_paths(
    repository: Path,
    tmp_path: Path,
) -> None:
    """Checkout-wide serialization does not become a machine-global lock."""
    clone_a = tmp_path / "clone-a"
    clone_b = tmp_path / "clone-b"
    subprocess.run(
        ["git", "clone", "-q", str(repository), str(clone_a)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "clone", "-q", str(repository), str(clone_b)],
        check=True,
        capture_output=True,
    )
    clear_caches()

    assert verdict_save_queue_path(clone_a) != verdict_save_queue_path(clone_b)


def test_queue_path_uses_portable_components(repository: Path) -> None:
    """Lock naming has no branch, mission, process, or platform path encoding."""
    lock_path = verdict_save_queue_path(repository)

    assert lock_path.name == "review-verdict-save.lock"
    assert lock_path.parent.name == "spec-kitty-locks"
    assert ":" not in lock_path.name
    assert "/" not in lock_path.name
    assert "\\" not in lock_path.name


def test_module_has_no_daemon_or_status_event_dependencies() -> None:
    """The primitive remains synchronous and independent of status mutation."""
    source_path = Path(verdict_commit_queue.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module is not None}
    imported_modules.update(alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names)
    forbidden_calls = {
        node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Attribute, ast.Name))
    } & {"Thread", "Process", "Popen"}

    assert not forbidden_calls
    assert not any(name.startswith("specify_cli.status") for name in imported_modules)
    assert not any(name.startswith("specify_cli.cli") for name in imported_modules)
    assert imported_modules <= {
        "__future__",
        "collections.abc",
        "contextlib",
        "contextvars",
        "kernel.git_topology",
        # WP05/#4714: migrated off filelock onto the canonical, stdlib-only
        # kernel.locks primitive (see kernel.locks's own zero-third-party-dep
        # module docstring).
        "kernel.locks",
        "math",
        "pathlib",
        # #3773 item 4: the enter/translate sequence shared with
        # specify_cli.status.locking now lives in one place. It carries no
        # status/cli coupling of its own (see that module's docstring), so it
        # does not violate the intent this allowlist guards.
        "specify_cli.core.checkout_file_lock",
    }
