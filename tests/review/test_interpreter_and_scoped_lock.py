"""Direct-callable coverage for ``resolve_pytest_command`` (#2570.3) and the
scoped subprocess contention lock ``_scoped_run_lock`` (#2493).

Split out of ``test_pre_review_gate_interpreter.py`` (#592): that file's
branch-matrix tests for ``resolve_pytest_command`` exercised the resolver
only through ``GateCoverageScopeSource.test_command()``, so when #551
retired ``GateCoverageScopeSource`` outright the whole file went with it —
even though ``resolve_pytest_command`` and ``_scoped_run_lock`` are still
live production code, called directly from
``specify_cli.review.pre_review_gate.run_scoped_tests_at_head``. These tests
call both directly, with no dependency on ``GateCoverageScopeSource``, so a
future retirement of that class cannot take this coverage down with it.

The lock tests are real subprocess/thread integration cases, not
mock-only proofs — the docstrings on each explain why a mock would not
catch the regression it guards against.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

import pytest

from specify_cli.review import _interpreter, pre_review_gate
from specify_cli.review._interpreter import resolve_pytest_command
from tests._perf_helpers import assert_timing_budget

pytestmark = [pytest.mark.integration]

_PASSING_TEST_BODY = "def test_pass():\n    assert True\n"


def _write_tiny_pytest_project(base: Path) -> None:
    (base / "test_sample.py").write_text(_PASSING_TEST_BODY, encoding="utf-8")


# ---------------------------------------------------------------------------
# resolve_pytest_command branch coverage, called directly (no
# GateCoverageScopeSource dependency)
# ---------------------------------------------------------------------------


@pytest.mark.fast
def test_uv_present_and_pyproject_present_resolves_to_uv_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Branch (i): both legs of the AND hold -> route through ``uv run``."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    monkeypatch.setattr(_interpreter.shutil, "which", lambda name: "/usr/bin/uv" if name == "uv" else None)

    command = resolve_pytest_command(["--junitxml=out.xml", "-q"], repo_root=tmp_path)

    assert command[:5] == ["uv", "run", "--frozen", "--project", str(tmp_path)]
    assert command[5:8] == ["python", "-m", "pytest"]
    assert command[-2:] == ["--junitxml=out.xml", "-q"]


@pytest.mark.fast
def test_uv_present_but_no_pyproject_falls_back_to_sys_executable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Branch (ii) — G2, the AND's second leg: no ``pyproject.toml`` at
    ``repo_root`` even though ``uv`` is on PATH -> fall back."""
    monkeypatch.setattr(_interpreter.shutil, "which", lambda name: "/usr/bin/uv" if name == "uv" else None)
    assert not (tmp_path / "pyproject.toml").exists()

    command = resolve_pytest_command(["--junitxml=out.xml", "-q"], repo_root=tmp_path)

    assert command == [sys.executable, "-m", "pytest", "--junitxml=out.xml", "-q"]


@pytest.mark.fast
def test_uv_absent_falls_back_to_sys_executable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Branch (iii): no ``uv`` on PATH at all -> fall back regardless of pyproject.toml."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    monkeypatch.setattr(_interpreter.shutil, "which", lambda _name: None)

    command = resolve_pytest_command(["--junitxml=out.xml", "-q"], repo_root=tmp_path)

    assert command == [sys.executable, "-m", "pytest", "--junitxml=out.xml", "-q"]


# ---------------------------------------------------------------------------
# T010 red-first — unmask #2570.3: a pytest-lacking sys.executable must not
# force a spurious no_coverage when uv can run the suite instead. Proven
# through the real production call site, pre_review_gate.run_scoped_tests_at_head.
# ---------------------------------------------------------------------------


def _write_fake_uv(bin_dir: Path) -> None:
    """A stand-in ``uv`` on PATH: ignores its args except ``--junitxml=``,
    to which it writes a single passing ``<testcase>`` and exits 0."""
    fake_uv = bin_dir / "uv"
    fake_uv.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "args = sys.argv[1:]\n"
        "junit_path = next(a.split('=', 1)[1] for a in args if a.startswith('--junitxml='))\n"
        "with open(junit_path, 'w', encoding='utf-8') as fh:\n"
        '    fh.write(\'<testsuite><testcase classname="t" name="test_pass" /></testsuite>\')\n'
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)


def _write_broken_python(bin_dir: Path) -> Path:
    """A stand-in for a ``sys.executable`` that lacks the ``pytest`` module:
    it always errors and never writes a JUnit file, mirroring the real
    ``No module named pytest`` failure mode (#2570.3)."""
    broken_python = bin_dir / "broken-python"
    broken_python.write_text(
        "#!/usr/bin/env python3\nimport sys\nsys.stderr.write(\"ModuleNotFoundError: No module named 'pytest'\\n\")\nsys.exit(1)\n",
        encoding="utf-8",
    )
    broken_python.chmod(0o755)
    return broken_python


@pytest.mark.integration
def test_pytest_lacking_sys_executable_still_yields_real_verdict_via_uv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Red-first proof of #2570.3: bug-present code hardcodes ``sys.executable``
    unconditionally, so it would call ``broken-python -m pytest ...`` here,
    produce no JUnit output, and degrade to ``HeadRunResult(ran=False)`` (the
    caller then reports ``GateOutcome.NO_COVERAGE``). Fixed code detects
    ``uv`` + ``pyproject.toml`` and routes through the (working) fake ``uv``
    instead, never touching the broken interpreter at all."""
    project_dir = tmp_path
    (project_dir / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    _write_tiny_pytest_project(project_dir)

    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    broken_python = _write_broken_python(bin_dir)
    _write_fake_uv(bin_dir)

    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    # WP04: pre_review_gate no longer imports `sys` itself (its own `sys`
    # usage was migrated onto kernel.locks/kernel.paths), so patch the real
    # `sys` module directly -- `pre_review_gate.sys` was always just a proxy
    # for this same module object, never a module-local copy.
    monkeypatch.setattr(sys, "executable", str(broken_python))

    result = pre_review_gate.run_scoped_tests_at_head(["test_sample.py"], repo_root=project_dir)

    assert result.ran is True
    assert result.current_failures == ()


# ---------------------------------------------------------------------------
# T011 — contention lock: serialization + decoupled timeout
# ---------------------------------------------------------------------------


@pytest.mark.fast
def test_scoped_run_lock_serializes_two_overlapping_holders() -> None:
    """Two overlapping ``_scoped_run_lock`` holders never run their critical
    section concurrently — whichever thread enters first must also exit
    before the second thread's entry is recorded."""
    events: list[str] = []
    lock_guard = threading.Lock()
    barrier = threading.Barrier(2)

    def hold(tag: str) -> None:
        barrier.wait(timeout=5)
        with pre_review_gate._scoped_run_lock(acquire_timeout=2.0):
            with lock_guard:
                events.append(f"{tag}-enter")
            time.sleep(0.05)
            with lock_guard:
                events.append(f"{tag}-exit")

    threads = [threading.Thread(target=hold, args=(tag,)) for tag in ("a", "b")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert len(events) == 4
    first_tag = events[0].split("-")[0]
    assert events[1] == f"{first_tag}-exit", f"interleaved holders: {events}"


def _run_lock_acquire_timeout_scenario(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[object, list[float], float]:
    """Shared K-9 scenario: permanent lock contention, then a scoped run.

    Returns ``(result, captured_timeouts, elapsed)`` so both the functional
    and the (nightly-only) timing-budget test can share one setup without
    duplicating the mocking (#4015 split).

    WP04 (cross-os-primitive-unification): ``_scoped_run_lock`` no longer
    calls ``fcntl.flock`` at all (migrated onto
    ``kernel.locks.machine_file_lock``), so "permanent contention" is
    simulated by genuinely holding the SAME lock path open from this test
    process for the scenario's duration -- OS-level ``flock`` contends
    across independent open file descriptions even within one process, so
    this reproduces real contention rather than mocking an internal call.
    """
    monkeypatch.setattr(pre_review_gate, "_LOCK_ACQUIRE_TIMEOUT_DEFAULT", 0.05)

    from kernel.locks import machine_file_lock

    lock_path = pre_review_gate.get_runtime_root().base / "gate-locks" / pre_review_gate._SCOPED_RUN_LOCK_FILENAME
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    contender = machine_file_lock(lock_path, blocking=True)
    contender.__enter__()

    captured_command: list[str] = []
    captured_timeouts: list[float] = []

    class _FakeProcess:
        returncode = 0

    def _fake_launch(command: list[str], **_kwargs: object) -> _FakeProcess:
        captured_command.extend(command)
        return _FakeProcess()

    def _fake_wait(_process: object, timeout: float) -> tuple[str, str]:
        captured_timeouts.append(timeout)
        junit_arg = next(arg for arg in captured_command if arg.startswith("--junitxml="))
        junit_path = Path(junit_arg.split("=", 1)[1])
        junit_path.write_text(
            '<testsuite><testcase classname="t" name="ok" /></testsuite>',
            encoding="utf-8",
        )
        return "", ""

    monkeypatch.setattr(pre_review_gate, "_HEAD_RUN_HEARTBEAT_INTERVAL", 300.0)
    monkeypatch.setattr(pre_review_gate, "_launch_scoped_process", _fake_launch)
    observation_clock = iter((100.0, 100.0))

    try:
        start = time.monotonic()
        result = pre_review_gate.run_scoped_tests_at_head(
            ["tests/status"],
            repo_root=tmp_path,
            timeout=300,
            monotonic=lambda: next(observation_clock),
            wait=_fake_wait,
        )
        elapsed = time.monotonic() - start
    finally:
        contender.__exit__(None, None, None)

    return result, captured_timeouts, elapsed


@pytest.mark.fast
def test_lock_acquire_timeout_falls_back_without_charging_run_timeout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """K-9: under permanent lock contention the acquire loop gives up after
    its OWN short bound and the run proceeds anyway — the process observation
    ``timeout`` budget must reflect only the full run budget, never the
    (much smaller) lock-acquire bound.

    Functional half of the #4015 split; the wall-clock ceiling now lives in
    ``test_lock_acquire_timeout_stays_bounded`` (nightly-only).
    """
    result, captured_timeouts, _elapsed = _run_lock_acquire_timeout_scenario(monkeypatch, tmp_path)

    assert result.ran is True
    assert captured_timeouts == [300]  # process observation receives the full run budget


@pytest.mark.performance
def test_lock_acquire_timeout_stays_bounded(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """K-9 (nightly): wall-clock spent stays bounded by the SHORT lock-acquire
    timeout, never the (much larger) run timeout.

    Split from ``test_lock_acquire_timeout_falls_back_without_charging_run_timeout``
    (#4015); budget preserved.
    """
    _result, _captured_timeouts, elapsed = _run_lock_acquire_timeout_scenario(monkeypatch, tmp_path)

    assert_timing_budget(elapsed, 2.0, name="lock_acquire_timeout_fallback")
