"""Tests for the per-run pytest temp root (#63).

Pure-logic limbs are ``fast``; the one subprocess probe that proves the wiring
end-to-end (an actual pytest invocation lands under the private root and leaves
it reaped at exit) carries ``integration``, matching its real cost.
"""

from __future__ import annotations

import atexit
import os
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests._support import run_basetemp as run_basetemp_module
from tests._support.run_basetemp import (
    RUN_TMP_ROOT_NAME,
    STALE_RUN_MAX_AGE_S,
    _validate_existing_root,
    install_run_basetemp,
    mark_session_outcome,
    remove_run_dirs,
    run_basetemp_dir,
    run_tmp_root,
    stale_run_dirs,
    temproot,
)
from tests.utils import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_PROBE_ENV = "SPEC_KITTY_RUN_BASETEMP_PROBE"


def _fake_config(basetemp: str | None = None, *, worker: bool = False) -> SimpleNamespace:
    """Just what :func:`install_run_basetemp` touches: the option and workerinput."""
    config = SimpleNamespace(option=SimpleNamespace(basetemp=basetemp))
    if worker:
        config.workerinput = {"workerid": "gw3"}
    return config


# ---------------------------------------------------------------------------
# Naming / resolution
# ---------------------------------------------------------------------------


def test_run_basetemp_dir_is_unique_per_controller_process() -> None:
    assert run_basetemp_dir(pid=100) != run_basetemp_dir(pid=200)
    # Deterministic per controller PID: two calls with the same pid agree.
    same_pid_first = run_basetemp_dir(pid=100)
    same_pid_second = run_basetemp_dir(pid=100)
    assert same_pid_first == same_pid_second
    assert run_basetemp_dir(pid=100).parent == run_tmp_root()


def test_temproot_honors_pytest_debug_temproot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYTEST_DEBUG_TEMPROOT", raising=False)
    default = temproot()
    monkeypatch.setenv("PYTEST_DEBUG_TEMPROOT", "/opt/alt-root")
    assert temproot() == Path("/opt/alt-root")
    assert run_tmp_root() == Path("/opt/alt-root") / RUN_TMP_ROOT_NAME
    monkeypatch.delenv("PYTEST_DEBUG_TEMPROOT", raising=False)
    assert temproot() == default


# ---------------------------------------------------------------------------
# Stale sweep
# ---------------------------------------------------------------------------


def _make_dir(root: Path, name: str, *, mtime: float) -> Path:
    path = root / name
    path.mkdir()
    os.utime(path, (mtime, mtime))
    return path


def test_stale_run_dirs_selects_only_entries_past_the_age_bound(tmp_path: Path) -> None:
    now = 2_000_000.0
    _make_dir(tmp_path, "run-1", mtime=now - STALE_RUN_MAX_AGE_S - 10)
    live = _make_dir(tmp_path, "run-2", mtime=now - STALE_RUN_MAX_AGE_S + 10)
    edge = _make_dir(tmp_path, "run-3", mtime=now - STALE_RUN_MAX_AGE_S)

    assert [path.name for path in stale_run_dirs(tmp_path, now=now)] == ["run-1"]
    assert live.is_dir() and edge.is_dir()


def test_stale_run_dirs_returns_empty_for_missing_root(tmp_path: Path) -> None:
    assert stale_run_dirs(tmp_path / "absent", now=10**9) == []


def test_remove_run_dirs_handles_dirs_files_and_repeats(tmp_path: Path) -> None:
    victim_dir = tmp_path / "run-9"
    (victim_dir / "nested").mkdir(parents=True)
    (victim_dir / "nested" / "f.txt").write_text("x")
    victim_file = tmp_path / "stray"
    victim_file.write_text("y")

    removed = remove_run_dirs([victim_dir, victim_file, victim_dir])
    assert removed == [victim_dir, victim_file]
    assert not victim_dir.exists() and not victim_file.exists()
    assert remove_run_dirs([victim_dir, victim_file]) == []


# ---------------------------------------------------------------------------
# Pre-existing-root validation (#77: pytest-parity owner/mode/symlink checks)
# ---------------------------------------------------------------------------


def test_validate_existing_root_repairs_world_readable_mode(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir(mode=0o755)
    os.chmod(root, 0o755)  # mkdir's mode is umask-filtered; force the bits we're testing

    _validate_existing_root(root)

    assert stat.S_IMODE(root.stat().st_mode) & 0o077 == 0


def test_validate_existing_root_rejects_a_symlinked_root(tmp_path: Path) -> None:
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real_dir)

    with pytest.raises(OSError, match="symbolic link"):
        _validate_existing_root(link)


def test_validate_existing_root_rejects_a_root_owned_by_another_uid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    monkeypatch.setattr(run_basetemp_module, "get_user_id", lambda: root.stat().st_uid + 1)

    with pytest.raises(OSError, match="not owned by the current user"):
        _validate_existing_root(root)


def test_validate_existing_root_is_a_noop_when_uid_is_undeterminable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows' ``get_user_id`` returns ``None`` — matches pytest's own
    rootdir check, which skips owner/mode enforcement in that case too."""
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real_dir)
    monkeypatch.setattr(run_basetemp_module, "get_user_id", lambda: None)

    _validate_existing_root(link)  # must not raise despite the symlink


def test_install_run_basetemp_rejects_a_preexisting_symlinked_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    temp_root = tmp_path / "temproot"
    temp_root.mkdir()
    monkeypatch.setenv("PYTEST_DEBUG_TEMPROOT", str(temp_root))
    real_dir = tmp_path / "real-root"
    real_dir.mkdir()
    (temp_root / RUN_TMP_ROOT_NAME).symlink_to(real_dir)

    with pytest.raises(OSError, match="symbolic link"):
        install_run_basetemp(_fake_config(), now=10**9)


# ---------------------------------------------------------------------------
# install_run_basetemp
# ---------------------------------------------------------------------------


def test_install_points_config_at_a_fresh_private_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYTEST_DEBUG_TEMPROOT", str(tmp_path))
    config = _fake_config()

    install_run_basetemp(config, now=10**9)

    chosen = Path(config.option.basetemp)
    assert chosen.parent == tmp_path / RUN_TMP_ROOT_NAME
    assert chosen.name.startswith("run-")
    assert chosen.parent.is_dir(), "root pre-created: pytest mkdirs the basetemp without parents"


def test_install_reaps_crash_leftovers_but_leaves_concurrent_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYTEST_DEBUG_TEMPROOT", str(tmp_path))
    now = 5_000_000.0
    root = tmp_path / RUN_TMP_ROOT_NAME
    root.mkdir()
    crashed = _make_dir(root, "run-111", mtime=now - STALE_RUN_MAX_AGE_S - 60)
    concurrent = _make_dir(root, "run-222", mtime=now - 30)

    install_run_basetemp(config := _fake_config(), now=now)

    assert not crashed.exists()
    assert concurrent.is_dir()
    assert Path(config.option.basetemp) not in (crashed, concurrent)


def test_install_respects_an_explicit_basetemp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYTEST_DEBUG_TEMPROOT", str(tmp_path))
    explicit = str(tmp_path / "user-owned")
    registered: list[object] = []
    monkeypatch.setattr(atexit, "register", registered.append)

    config = _fake_config(basetemp=explicit)
    install_run_basetemp(config, now=10**9)

    assert config.option.basetemp == explicit
    assert registered == [], "whoever passes --basetemp owns its lifecycle"


def test_install_never_touches_an_xdist_worker_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYTEST_DEBUG_TEMPROOT", str(tmp_path))
    registered: list[object] = []
    monkeypatch.setattr(atexit, "register", registered.append)

    config = _fake_config(worker=True)
    install_run_basetemp(config, now=10**9)

    assert config.option.basetemp is None
    assert registered == []
    assert not (tmp_path / RUN_TMP_ROOT_NAME).exists()


def test_install_registers_an_atexit_reaper_for_this_run_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYTEST_DEBUG_TEMPROOT", str(tmp_path))
    handlers: list = []

    def _capture(function) -> None:
        handlers.append(function)

    monkeypatch.setattr(atexit, "register", _capture)
    config = _fake_config()
    install_run_basetemp(config, now=10**9)
    assert len(handlers) == 1  # exactly one reaper, never two

    # Simulate a successful session — pytest_sessionfinish marks this BEFORE
    # atexit callbacks run (#76: reap only follows a recorded success).
    mark_session_outcome(config, succeeded=True)

    # Simulate interpreter exit with residue left under the run dir.
    residue = Path(config.option.basetemp) / "popen-gw0"
    residue.mkdir(parents=True)
    (residue / "leftover").write_text("x")
    handlers[0]()
    assert not Path(config.option.basetemp).exists()
    assert (tmp_path / RUN_TMP_ROOT_NAME).is_dir(), "the shared root itself stays"


def test_install_retains_the_run_dir_when_the_session_did_not_succeed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#76: a failed/errored/interrupted session keeps its tmp tree — the
    reap is gated on a recorded success, never unconditional."""
    monkeypatch.setenv("PYTEST_DEBUG_TEMPROOT", str(tmp_path))
    handlers: list = []
    monkeypatch.setattr(atexit, "register", handlers.append)

    config = _fake_config()
    install_run_basetemp(config, now=10**9)

    basetemp = Path(config.option.basetemp)
    basetemp.mkdir(parents=True)
    forensic_evidence = basetemp / "leftover.txt"
    forensic_evidence.write_text("post-mortem state")

    # No mark_session_outcome(succeeded=True) call — the default is "not
    # succeeded", matching a run that crashed before sessionfinish too.
    handlers[0]()

    assert basetemp.is_dir()
    assert forensic_evidence.read_text() == "post-mortem state"


def test_mark_session_outcome_is_a_noop_without_an_installed_reaper() -> None:
    """A config install_run_basetemp never ran against (xdist worker, or an
    explicit --basetemp) has nothing for mark_session_outcome to update."""
    config = _fake_config()
    mark_session_outcome(config, succeeded=True)  # must not raise


# ---------------------------------------------------------------------------
# End-to-end wiring: a real nested pytest run
# ---------------------------------------------------------------------------


@pytest.mark.fast
def test_inner_tmp_path_lands_under_the_private_run_root(tmp_path: Path) -> None:
    """Runs only as the inner probe spawned by the integration test below."""
    if not os.environ.get(_PROBE_ENV):
        pytest.skip("inner probe of test_subprocess_run_uses_the_private_root")
    expected_root = Path(os.environ["PYTEST_DEBUG_TEMPROOT"]) / RUN_TMP_ROOT_NAME
    assert tmp_path.is_relative_to(expected_root)


@pytest.mark.integration
def test_subprocess_run_uses_the_private_root_and_reaps_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole mechanism, observed from outside a real pytest invocation."""
    if os.environ.get(_PROBE_ENV):
        pytest.skip("the inner probe must not recurse")
    scratch = tmp_path / "temproot"
    scratch.mkdir()
    monkeypatch.setenv("PYTEST_DEBUG_TEMPROOT", str(scratch))
    monkeypatch.setenv(_PROBE_ENV, "1")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(Path(__file__).resolve()),
            "-k",
            "inner",
            "-p",
            "no:cacheprovider",
            "--tb=short",
            "-q",
        ],
        cwd=REPO_ROOT,
        env=dict(os.environ),
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, output

    private_root = scratch / RUN_TMP_ROOT_NAME
    assert private_root.is_dir(), f"the run never created its private root:\n{output}"
    assert not any(private_root.iterdir()), "the run's own dir survived its own exit"


_PROBE_FAIL_ENV = "SPEC_KITTY_RUN_BASETEMP_PROBE_FAIL"


@pytest.mark.fast
def test_probe_failure_leaves_a_marker_under_tmp_path(tmp_path: Path) -> None:
    """Runs only as the inner probe spawned by
    ``test_subprocess_failed_run_retains_the_private_root``; deliberately
    fails after writing a marker so the outer test can check it survives."""
    if not os.environ.get(_PROBE_FAIL_ENV):
        pytest.skip("inner probe of test_subprocess_failed_run_retains_the_private_root")
    (tmp_path / "marker.txt").write_text("post-mortem evidence")
    pytest.fail("intentional failure to exercise outcome-gated retention (#76)")


@pytest.mark.integration
def test_subprocess_failed_run_retains_the_private_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#76 end-to-end: a session with a failing test keeps its private root.

    Exercises the real ``pytest_sessionfinish`` wiring in ``tests/conftest.py``
    (:func:`mark_session_outcome` called there), not just the isolated
    unit-level calls in the ``install_run_basetemp`` tests above.
    """
    if os.environ.get(_PROBE_ENV) or os.environ.get(_PROBE_FAIL_ENV):
        pytest.skip("the inner probe must not recurse")
    scratch = tmp_path / "temproot"
    scratch.mkdir()
    monkeypatch.setenv("PYTEST_DEBUG_TEMPROOT", str(scratch))
    monkeypatch.setenv(_PROBE_FAIL_ENV, "1")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(Path(__file__).resolve()),
            "-k",
            "probe_failure_leaves_a_marker",
            "-p",
            "no:cacheprovider",
            "--tb=short",
            "-q",
        ],
        cwd=REPO_ROOT,
        env=dict(os.environ),
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    output = result.stdout + result.stderr
    assert result.returncode != 0, f"the inner probe was supposed to fail:\n{output}"

    private_root = scratch / RUN_TMP_ROOT_NAME
    run_dirs = list(private_root.iterdir())
    assert len(run_dirs) == 1, f"expected exactly the retained run dir:\n{output}"
    markers = list(run_dirs[0].rglob("marker.txt"))
    assert markers, f"forensic marker did not survive the failed session:\n{output}"
    assert markers[0].read_text() == "post-mortem evidence"
