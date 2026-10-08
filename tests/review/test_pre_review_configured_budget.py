"""Configured head-gate budgets preserve scope authority and validation execution."""

from __future__ import annotations

from collections.abc import Sequence
import json
import math
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from typing import Any
import warnings

import pytest

from specify_cli.cli.commands.agent import tasks_move_task_gates as gates
from specify_cli.review import baseline
from specify_cli.review import pre_review_gate as engine
from specify_cli.review.gate_registry import TransitionGateContext
from specify_cli.status.models import Lane

pytestmark = pytest.mark.fast


def config(root: Path, value: object, *, present: bool = True) -> None:
    (root / ".kittify").mkdir(parents=True)
    encoded = (".nan" if math.isnan(value) else (".inf" if value > 0 else "-.inf")) if isinstance(value, float) and not math.isfinite(value) else json.dumps(value)
    timeout = f"  pre_review_timeout_seconds: {encoded}\n" if present else ""
    command = f'{sys.executable} -c "print(123)"'
    (root / ".kittify/config.yaml").write_text(f"review:\n  test_command: {command!r}\n{timeout}")


def run_transition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, route: str, owned: bool, value: object, present: bool = True
) -> tuple[list[engine.GateVerdict], list[float], list[tuple[str, ...]]]:
    primary, write = tmp_path / "primary", tmp_path / "owned"
    config(primary, 17)
    config(write, value, present=present)
    selected = write if owned else primary
    state = SimpleNamespace(
        repo_root=write,
        main_repo_root=primary,
        owned=object() if owned else None,
        json_output=True,
        wp=SimpleNamespace(frontmatter=""),
        review_base_ref=None,
        target_branch="landing",
        old_lane=Lane.IN_PROGRESS,
        target_lane=Lane.FOR_REVIEW,
        force=False,
    )
    monkeypatch.setattr(gates, "_mt_resolve_pre_review_workspace", lambda _: write)
    monkeypatch.setattr(gates, "_mt_pre_review_dirty_paths", lambda _: ())
    monkeypatch.setattr(gates, "_mt_pre_review_changed_files", lambda *_: ("src/example.py",))
    monkeypatch.setattr(gates, "_mt_resolve_gate_baseline", lambda _: None)
    monkeypatch.setattr(gates, "_mt_pre_review_scope_override", lambda *_: ("tests/selected",) if route == "override" else None)
    monkeypatch.setattr(
        gates, "_mt_resolve_active_gate_bindings", lambda _: SimpleNamespace(active=(SimpleNamespace(handler="spec-kitty-pre-review"),), reason="active")
    )
    budgets: list[float] = []
    commands: list[tuple[str, ...]] = []
    observe = engine._observe_process
    launch = engine._launch_scoped_process
    expected_env = engine._gate_run_env()

    def recording_observe(process: subprocess.Popen[str], **kwargs: Any) -> Any:
        budgets.append(kwargs["timeout"])
        return observe(process, **kwargs)

    def recording_launch(command: Sequence[str], **kwargs: Any) -> subprocess.Popen[str]:
        assert kwargs["env"] == expected_env
        assert kwargs["repo_root"] == write
        assert baseline.CAPTURE_BASELINE_TIMEOUT_SECONDS == 300
        commands.append(tuple(command))
        if route == "override":
            junit = next(atom.split("=", 1)[1] for atom in command if atom.startswith("--junitxml="))
            script = f'from pathlib import Path; Path({junit!r}).write_text(\'<testsuite tests="1" failures="0" errors="0" skipped="0"/>\')'
            return launch([sys.executable, "-c", script], **kwargs)
        return launch(command, **kwargs)

    monkeypatch.setattr(engine, "_observe_process", recording_observe)
    monkeypatch.setattr(engine, "_launch_scoped_process", recording_launch)
    inputs, _ = gates._mt_resolve_transition_gate_inputs(state)
    assert inputs.scope_source_root == selected
    return gates._mt_collect_transition_gate_verdicts(state, inputs, SimpleNamespace()), budgets, commands


@pytest.mark.parametrize("route", ["registry", "override"])
@pytest.mark.parametrize("value,present,expected", [(None, False, 300), (8, True, 8), (0.25, True, 0.25)])
def test_budget_forwarded_without_changing_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, route: str, value: object, present: bool, expected: float
) -> None:
    verdicts, budgets, commands = run_transition(tmp_path, monkeypatch, route=route, owned=True, value=value, present=present)
    assert budgets == [expected]
    assert verdicts[0].outcome is not engine.GateOutcome.NO_COVERAGE
    assert len(commands) == 1
    if route == "registry":
        assert commands[0] == ("sh", "-c", f'{sys.executable} -c "print(123)"')
    else:
        assert "tests/selected" in commands[0]
        assert commands[0][-1] == "-q"


@pytest.mark.parametrize("route", ["registry", "override"])
@pytest.mark.parametrize("owned", [False, True])
def test_budget_uses_same_resolved_scope_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, route: str, owned: bool) -> None:
    _, budgets, _ = run_transition(tmp_path, monkeypatch, route=route, owned=owned, value=0.5)
    assert budgets == [0.5 if owned else 17]


@pytest.mark.parametrize("route", ["registry", "override"])
@pytest.mark.parametrize("value", [None, True, False, "45", 0, -1, float("inf"), float("-inf"), float("nan")])
def test_invalid_budget_warns_and_runs_under_warning_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], route: str, value: object
) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        verdicts, budgets, commands = run_transition(tmp_path, monkeypatch, route=route, owned=True, value=value)
    assert budgets == [300]
    assert len(commands) == 1
    assert verdicts[0].outcome is not engine.GateOutcome.NO_COVERAGE
    assert "pre_review_timeout_seconds" in capsys.readouterr().err


@pytest.mark.parametrize("route", ["registry", "override"])
def test_huge_integer_conversion_overflow_still_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], route: str) -> None:
    original = gates._mt_review_config_section
    monkeypatch.setattr(
        gates,
        "_mt_review_config_section",
        lambda root: {
            **original(root),
            "pre_review_timeout_seconds": 10**10000,
        },
    )
    verdicts, budgets, commands = run_transition(tmp_path, monkeypatch, route=route, owned=True, value=1)
    assert budgets == [300]
    assert len(commands) == 1
    assert verdicts[0].outcome is not engine.GateOutcome.NO_COVERAGE
    assert "pre_review_timeout_seconds" in capsys.readouterr().err


def test_context_positional_observer_compatibility() -> None:
    def observer(_: engine.GateStatusEvent) -> None:
        return None

    context = TransitionGateContext((), SimpleNamespace(), None, Path("."), False, Lane.IN_PROGRESS, Lane.FOR_REVIEW, observer)
    assert context.status_observer is observer
    assert context.timeout == 300


def test_candidate_source_is_loaded() -> None:
    root = Path(__file__).resolve().parents[2]
    assert Path(gates.__file__).resolve() == root / "src/specify_cli/cli/commands/agent/tasks_move_task_gates.py"
    assert Path(engine.__file__).resolve() == root / "src/specify_cli/review/pre_review_gate.py"


@pytest.mark.parametrize("mode", ["completed", "timed_out", "cancelled"])
def test_fractional_real_child_is_reaped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    import time

    launched: list[subprocess.Popen[str]] = []
    launch = engine._launch_scoped_process

    def recording_launch(command: Sequence[str], **kwargs: Any) -> subprocess.Popen[str]:
        process = launch(command, **kwargs)
        launched.append(process)
        return process

    interrupted = False

    def wait(process: subprocess.Popen[str], timeout: float) -> tuple[str, str]:
        nonlocal interrupted
        if mode == "cancelled" and not interrupted:
            interrupted = True
            raise KeyboardInterrupt
        return process.communicate(timeout=timeout)

    monkeypatch.setattr(engine, "_launch_scoped_process", recording_launch)
    command = [sys.executable, "-c", "print(123)" if mode == "completed" else "import time; time.sleep(30)"]
    state, raw, error = engine._run_raw_command(command, repo_root=tmp_path, timeout=0.15, progress_callback=None, monotonic=time.monotonic, wait=wait)
    assert state.value == mode
    assert len(launched) == 1
    assert launched[0].poll() is not None
    if mode == "completed":
        assert raw is not None and raw.stdout.strip() == "123"
        assert error is None
    else:
        assert raw is None
        assert error and mode.replace("_", " ") in error
