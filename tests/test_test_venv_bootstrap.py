from __future__ import annotations

import json
import multiprocessing
import os
import sys
import time
from pathlib import Path
from queue import Empty
from typing import Any

import pytest

from kernel.clock import now_epoch
from tests import conftest as root_conftest


pytestmark = pytest.mark.fast

_SOURCE_VERSION = "9.9.9"


def _fake_python_path(venv_dir: Path) -> Path:
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _fake_build(venv_dir: Path, source_version: str) -> None:
    del source_version
    count_path = venv_dir.parent / "build-count.txt"
    count_path.parent.mkdir(parents=True, exist_ok=True)
    with count_path.open("a", encoding="utf-8") as stream:
        stream.write(f"{os.getpid()}\n")
    time.sleep(0.35)
    python = _fake_python_path(venv_dir)
    python.parent.mkdir(parents=True)
    python.write_text("fake", encoding="utf-8")


def _blocking_build(venv_dir: Path, source_version: str) -> None:
    del source_version
    started = venv_dir.parent / "builder-started"
    # Publish atomically: a plain write_text makes the file visible (and thus
    # _wait_for-observable) before its content lands, so a reader racing the
    # write observes "" — which Path("") turns into ".", a path that always
    # exists and fails the reclaim assertion for the wrong reason.
    staged = started.with_name(f"{started.name}.tmp-{os.getpid()}")
    staged.write_text(str(venv_dir), encoding="utf-8")
    os.replace(staged, started)
    time.sleep(30)


def _fake_valid(venv_dir: Path, source_version: str) -> bool:
    marker = venv_dir / "VERSION"
    return (
        _fake_python_path(venv_dir).is_file()
        and marker.is_file()
        and marker.read_text(encoding="utf-8").strip() == source_version
    )


def test_existing_executables_win_over_spoofed_platform(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Platform-spoof tests must not redirect a published POSIX venv."""
    python = tmp_path / "bin" / "python"
    pip = tmp_path / "bin" / "pip"
    python.parent.mkdir(parents=True)
    python.write_text("python", encoding="utf-8")
    pip.write_text("pip", encoding="utf-8")

    monkeypatch.setattr(root_conftest.sys, "platform", "win32")

    assert root_conftest._venv_python(tmp_path) == python
    assert root_conftest._venv_pip(tmp_path) == pip


def _bootstrap_worker(
    project_root: str,
    start: Any,
    results: Any,
    *,
    blocking: bool = False,
) -> None:
    start.wait()
    build = _blocking_build if blocking else _fake_build
    try:
        path = root_conftest._ensure_test_venv(
            Path(project_root),
            _SOURCE_VERSION,
            _build=build,
            _validate=_fake_valid,
            _heartbeat_interval=0.05,
            _lease_seconds=0.2,
            _wait_timeout=5.0,
            _poll_interval=0.02,
        )
    except BaseException as exc:  # pragma: no cover - surfaced in parent
        results.put(("error", repr(exc)))
    else:
        results.put(("ok", str(path)))


def _spawn_context() -> Any:
    return multiprocessing.get_context("spawn")


def _start_worker(
    context: Any,
    project_root: Path,
    start: Any,
    results: Any,
    *,
    blocking: bool = False,
) -> multiprocessing.Process:
    process: multiprocessing.Process = context.Process(
        target=_bootstrap_worker,
        args=(str(project_root), start, results),
        kwargs={"blocking": blocking},
    )
    process.start()
    return process


def _wait_for(path: Path, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return
        time.sleep(0.01)
    raise AssertionError(f"Timed out waiting for {path}")


def _wait_for_removal(path: Path, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not path.exists():
            return
        time.sleep(0.01)
    raise AssertionError(f"Timed out waiting for removal of {path}")


def _drain_worker_outcomes(results: Any, count: int) -> list[tuple[str, str]]:
    """Collect every child outcome before any assertion runs.

    A child that exits without queueing a result must not discard its
    siblings' payloads: record a ("missing", ...) marker instead of letting
    queue.Empty escape the drain, so the combined exit-code/outcome
    assertion that follows prints every child's status and payload
    (spec-kitty#4486's diagnostic acceptance bullet).
    """
    outcomes: list[tuple[str, str]] = []
    for _ in range(count):
        try:
            outcomes.append(results.get(timeout=1))
        except Empty:
            outcomes.append(("missing", "no result queued"))
    return outcomes


class _FakeResultsQueue:
    """Minimal results.get() stand-in for the drain-path unit tests."""

    def __init__(self, items: list[tuple[str, str]]) -> None:
        self._items = list(items)

    def get(self, timeout: float = 1) -> tuple[str, str]:
        del timeout
        if not self._items:
            raise Empty
        return self._items.pop(0)


def test_drain_worker_outcomes_preserves_error_payloads() -> None:
    results = _FakeResultsQueue([("error", "RuntimeError('boom')"), ("ok", "/venv")])
    assert _drain_worker_outcomes(results, 2) == [
        ("error", "RuntimeError('boom')"),
        ("ok", "/venv"),
    ]


def test_drain_worker_outcomes_marks_missing_results_instead_of_raising() -> None:
    # A child that exits without queueing a result must not cost its sibling
    # the payload report: queue.Empty becomes a ("missing", ...) marker.
    results = _FakeResultsQueue([("ok", "/venv")])
    assert _drain_worker_outcomes(results, 2) == [
        ("ok", "/venv"),
        ("missing", "no result queued"),
    ]


def test_two_spawned_processes_publish_one_shared_venv(tmp_path: Path) -> None:
    context = _spawn_context()
    start = context.Event()
    results = context.Queue()
    processes = [
        _start_worker(context, tmp_path, start, results),
        _start_worker(context, tmp_path, start, results),
    ]

    start.set()
    for process in processes:
        process.join(timeout=10)

    outcomes = _drain_worker_outcomes(results, len(processes))
    expected = str(tmp_path / root_conftest._VENV_CACHE_PATH)
    assert ([process.exitcode for process in processes], sorted(outcomes)) == (
        [0, 0],
        [("ok", expected), ("ok", expected)],
    )
    count_path = tmp_path / ".pytest_cache" / "build-count.txt"
    assert len(count_path.read_text(encoding="utf-8").splitlines()) == 1


def test_slow_live_builder_is_not_stolen_and_final_is_hidden(tmp_path: Path) -> None:
    context = _spawn_context()
    start = context.Event()
    results = context.Queue()
    first = _start_worker(context, tmp_path, start, results)
    start.set()
    count_path = tmp_path / ".pytest_cache" / "build-count.txt"
    _wait_for(count_path)

    final_path = tmp_path / root_conftest._VENV_CACHE_PATH
    assert not final_path.exists()
    second = _start_worker(context, tmp_path, start, results)
    first.join(timeout=10)
    second.join(timeout=10)

    assert first.exitcode == second.exitcode == 0
    assert all(results.get(timeout=1)[0] == "ok" for _ in range(2))
    assert len(count_path.read_text(encoding="utf-8").splitlines()) == 1
    assert _fake_valid(final_path, _SOURCE_VERSION)


def test_killed_builder_is_reclaimed_without_touching_other_siblings(tmp_path: Path) -> None:
    context = _spawn_context()
    start = context.Event()
    results = context.Queue()
    sentinel = tmp_path / ".pytest_cache" / "unrelated-sibling"
    sentinel.mkdir(parents=True)
    (sentinel / "keep").write_text("safe", encoding="utf-8")

    builder = _start_worker(context, tmp_path, start, results, blocking=True)
    start.set()
    started_path = tmp_path / ".pytest_cache" / "builder-started"
    _wait_for(started_path)
    abandoned_temp = Path(started_path.read_text(encoding="utf-8"))
    # Fail loudly on a torn read instead of silently testing ".", which always
    # exists and would fail the reclaim wait below for the wrong reason.
    assert abandoned_temp.is_absolute(), f"empty or torn read of {started_path}"
    builder.terminate()
    builder.join(timeout=5)

    recovered = root_conftest._ensure_test_venv(
        tmp_path,
        _SOURCE_VERSION,
        _build=_fake_build,
        _validate=_fake_valid,
        _heartbeat_interval=0.05,
        _lease_seconds=0.2,
        _wait_timeout=5.0,
        _poll_interval=0.02,
    )

    assert _fake_valid(recovered, _SOURCE_VERSION)
    _wait_for_removal(abandoned_temp)
    assert (sentinel / "keep").read_text(encoding="utf-8") == "safe"


@pytest.mark.parametrize("state", ["BUILDING", "VALIDATED"])
def test_pid_reuse_or_crash_state_is_rebuilt(tmp_path: Path, state: str) -> None:
    cache = tmp_path / ".pytest_cache"
    abandoned = cache / "spec-kitty-test-venv.build-abandoned"
    _fake_build(abandoned, _SOURCE_VERSION)
    (abandoned / "VERSION").write_text(_SOURCE_VERSION, encoding="utf-8")
    state_path = tmp_path / root_conftest._VENV_STATE_PATH
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "state": state,
                "owner_pid": os.getpid(),
                "process_start_token": "reused-pid-token",
                "heartbeat_at": now_epoch(),
                "lease_seconds": 30.0,
                "temp_path": str(abandoned),
                "source_version": _SOURCE_VERSION,
                "environment_hash": root_conftest._test_venv_environment_hash(
                    tmp_path, _SOURCE_VERSION
                ),
            }
        ),
        encoding="utf-8",
    )

    final = root_conftest._ensure_test_venv(
        tmp_path,
        _SOURCE_VERSION,
        _build=_fake_build,
        _validate=_fake_valid,
        _wait_timeout=5.0,
    )

    assert _fake_valid(final, _SOURCE_VERSION)
    assert not abandoned.exists()


def test_expired_heartbeat_is_reclaimed_even_when_pid_is_live(tmp_path: Path) -> None:
    cache = tmp_path / ".pytest_cache"
    abandoned = cache / "spec-kitty-test-venv.build-expired"
    _fake_build(abandoned, _SOURCE_VERSION)
    state_path = tmp_path / root_conftest._VENV_STATE_PATH
    state_path.write_text(
        json.dumps(
            {
                "state": "BUILDING",
                "owner_pid": os.getpid(),
                "process_start_token": root_conftest._process_start_token(os.getpid()),
                "heartbeat_at": now_epoch() - 60,
                "lease_seconds": 0.1,
                "temp_path": str(abandoned),
                "source_version": _SOURCE_VERSION,
                "environment_hash": root_conftest._test_venv_environment_hash(
                    tmp_path, _SOURCE_VERSION
                ),
            }
        ),
        encoding="utf-8",
    )

    final = root_conftest._ensure_test_venv(
        tmp_path,
        _SOURCE_VERSION,
        _build=_fake_build,
        _validate=_fake_valid,
        _wait_timeout=5.0,
    )

    assert _fake_valid(final, _SOURCE_VERSION)
    assert not abandoned.exists()


def test_live_owner_with_stale_heartbeat_is_not_stolen_within_grace(tmp_path: Path) -> None:
    """A live owner survives a transient heartbeat gap (spec-kitty#4486).

    Mirror of ``test_expired_heartbeat_is_reclaimed_even_when_pid_is_live``:
    staleness beyond the lease window alone must not abandon a token-verified
    live owner — a loaded Windows runner stalls a healthy heartbeat far past
    a compressed lease — only staleness that also outlives the grace floor
    does. Deterministic: fixed heartbeat offset, no timing race.
    """
    cache = tmp_path / ".pytest_cache"
    building = cache / "spec-kitty-test-venv.build-live"
    _fake_build(building, _SOURCE_VERSION)
    state_path = tmp_path / root_conftest._VENV_STATE_PATH
    state_path.write_text(
        json.dumps(
            {
                "state": "BUILDING",
                "owner_pid": os.getpid(),
                "process_start_token": root_conftest._process_start_token(os.getpid()),
                "heartbeat_at": now_epoch() - 1.0,
                "lease_seconds": 0.1,
                "temp_path": str(building),
                "source_version": _SOURCE_VERSION,
                "environment_hash": root_conftest._test_venv_environment_hash(
                    tmp_path, _SOURCE_VERSION
                ),
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="Timed out waiting"):
        root_conftest._ensure_test_venv(
            tmp_path,
            _SOURCE_VERSION,
            _build=_fake_build,
            _validate=_fake_valid,
            _wait_timeout=0.5,
        )

    assert building.exists()


@pytest.mark.parametrize("entry_kind", ["directory", "file", "symlink"])
def test_invalid_published_venv_is_rebuilt_once(tmp_path: Path, entry_kind: str) -> None:
    final = tmp_path / root_conftest._VENV_CACHE_PATH
    final.parent.mkdir(parents=True)
    symlink_target = tmp_path / "symlink-target"
    if entry_kind == "directory":
        final.mkdir()
        (final / "VERSION").write_text("old", encoding="utf-8")
    elif entry_kind == "file":
        final.write_text("not a venv", encoding="utf-8")
    else:
        symlink_target.mkdir()
        (symlink_target / "keep").write_text("safe", encoding="utf-8")
        try:
            final.symlink_to(symlink_target, target_is_directory=True)
        except OSError as exc:
            pytest.skip(f"directory symlinks unavailable: {exc}")

    result = root_conftest._ensure_test_venv(
        tmp_path,
        _SOURCE_VERSION,
        _build=_fake_build,
        _validate=_fake_valid,
        _wait_timeout=5.0,
    )

    assert _fake_valid(result, _SOURCE_VERSION)
    assert len((tmp_path / ".pytest_cache" / "build-count.txt").read_text(encoding="utf-8").splitlines()) == 1
    if entry_kind == "symlink":
        assert (symlink_target / "keep").read_text(encoding="utf-8") == "safe"


def test_stale_lease_recovers_past_invalid_final_symlink_without_following_target(
    tmp_path: Path,
) -> None:
    cache = tmp_path / ".pytest_cache"
    cache.mkdir()
    abandoned = cache / "spec-kitty-test-venv.build-abandoned"
    _fake_build(abandoned, _SOURCE_VERSION)
    outside_target = tmp_path / "outside-target"
    outside_target.mkdir()
    (outside_target / "keep").write_text("safe", encoding="utf-8")
    final = tmp_path / root_conftest._VENV_CACHE_PATH
    try:
        final.symlink_to(outside_target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks unavailable: {exc}")

    state_path = tmp_path / root_conftest._VENV_STATE_PATH
    state_path.write_text(
        json.dumps(
            {
                "state": "BUILDING",
                "owner_pid": 99999999,
                "process_start_token": "dead",
                "heartbeat_at": 0.0,
                "lease_seconds": 0.1,
                "temp_path": str(abandoned),
                "source_version": _SOURCE_VERSION,
                "environment_hash": root_conftest._test_venv_environment_hash(
                    tmp_path, _SOURCE_VERSION
                ),
            }
        ),
        encoding="utf-8",
    )

    result = root_conftest._ensure_test_venv(
        tmp_path,
        _SOURCE_VERSION,
        _build=_fake_build,
        _validate=_fake_valid,
        _wait_timeout=5.0,
    )

    assert _fake_valid(result, _SOURCE_VERSION)
    assert not result.is_symlink()
    assert not abandoned.exists()
    assert (outside_target / "keep").read_text(encoding="utf-8") == "safe"


def test_corrupt_state_cannot_delete_untrusted_temp_path(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep").write_text("safe", encoding="utf-8")
    state_path = tmp_path / root_conftest._VENV_STATE_PATH
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "state": "BUILDING",
                "owner_pid": 99999999,
                "process_start_token": "dead",
                "heartbeat_at": 0.0,
                "lease_seconds": 0.1,
                "temp_path": str(outside),
                "source_version": _SOURCE_VERSION,
                "environment_hash": "untrusted",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="unsafe temp_path"):
        root_conftest._ensure_test_venv(
            tmp_path,
            _SOURCE_VERSION,
            _build=_fake_build,
            _validate=_fake_valid,
            _wait_timeout=1.0,
        )

    assert (outside / "keep").read_text(encoding="utf-8") == "safe"


def test_malformed_lease_state_fails_closed(tmp_path: Path) -> None:
    state_path = tmp_path / root_conftest._VENV_STATE_PATH
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text("not-json", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Malformed test-venv lease state"):
        root_conftest._ensure_test_venv(
            tmp_path,
            _SOURCE_VERSION,
            _build=_fake_build,
            _validate=_fake_valid,
            _wait_timeout=1.0,
        )


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX layout assertion")
def test_venv_python_uses_posix_layout_on_posix(tmp_path: Path) -> None:
    assert root_conftest._venv_python(tmp_path) == tmp_path / "bin" / "python"


@pytest.mark.windows_ci
def test_venv_python_uses_scripts_layout_on_windows(tmp_path: Path) -> None:
    assert sys.platform == "win32"
    assert root_conftest._venv_python(tmp_path) == tmp_path / "Scripts" / "python.exe"


@pytest.mark.windows_ci
def test_two_spawned_windows_processes_publish_one_shared_venv(tmp_path: Path) -> None:
    assert sys.platform == "win32"
    context = _spawn_context()
    start = context.Event()
    results = context.Queue()
    processes = [
        _start_worker(context, tmp_path, start, results),
        _start_worker(context, tmp_path, start, results),
    ]

    start.set()
    # windows-latest spawn + conftest import alone measured ~8.6s of the old
    # 10s budget on the spec-kitty#4486 run; the join headroom is not the
    # assertion under test, so keep it generous.
    for process in processes:
        process.join(timeout=20)

    outcomes = _drain_worker_outcomes(results, len(processes))
    expected = str(tmp_path / root_conftest._VENV_CACHE_PATH)
    assert ([process.exitcode for process in processes], sorted(outcomes)) == (
        [0, 0],
        [("ok", expected), ("ok", expected)],
    )
    count_path = tmp_path / ".pytest_cache" / "build-count.txt"
    assert len(count_path.read_text(encoding="utf-8").splitlines()) == 1
