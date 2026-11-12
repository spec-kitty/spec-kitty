"""The pre-review gate runs in the environment the hook hands it (WP03, #7547).

Mission ``lane-code-verification-01M76AC0`` WP03 (FR-006, FR-011, C-003, C-008):

1. the declared-command path (``evaluate_pre_review_gate`` ->
   ``_run_raw_command``) runs with the given ``run_env`` (plus the forced
   ``PWHEADLESS=1``) instead of the inherited environment, and ``run_env=None``
   keeps today's inherited environment (back-compat positive control);
2. the override tier (``evaluate_with_scope(scope_source=None)`` ->
   ``run_scoped_tests_at_head``) runs its ``sys.executable`` fallback in the
   given ``run_env`` (#5985 item 2);
3. the baseline run applies the same recipe as the head, rooted at the
   baseline worktree: the interpreter-redirect variables are removed and
   ``PYTHONPATH=<cwd>/src`` is set when the worktree has tracked source
   packages and no ``.venv`` of its own.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from specify_cli.lanes.lane_invocation import INTERPRETER_REDIRECT_KEYS
from specify_cli.review import _interpreter, baseline, pre_review_gate
from specify_cli.review.pre_review_gate import (
    GateOutcome,
    HeadRunState,
    ScopeResult,
    evaluate_pre_review_gate,
    evaluate_with_scope,
)
from specify_cli.review.scope_source import RawRunResult

if TYPE_CHECKING:
    from specify_cli.review.baseline import BaselineFailure

pytestmark = [pytest.mark.fast]

_ENV_DUMP = "env.json"
_INHERITED = "/primary/checkout"
_DUMP_ENV_SCRIPT = f"import json, os; json.dump(dict(os.environ), open({_ENV_DUMP!r}, 'w'))"


@dataclass(frozen=True)
class _EnvDumpingScopeSource:
    """A non-narrowing ``ScopeSource`` whose command records its own environment."""

    def test_command(self) -> list[str] | None:
        return [sys.executable, "-c", _DUMP_ENV_SCRIPT]

    def file_to_scope(self, path: str) -> tuple[str, ...]:
        del path
        return ()

    def parse_results(self, raw: RawRunResult) -> tuple[BaselineFailure, ...]:
        del raw
        return ()

    def parse_mode(self, raw: RawRunResult) -> str:
        del raw
        return "text"


def _inherit_redirect_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in INTERPRETER_REDIRECT_KEYS:
        monkeypatch.setenv(key, _INHERITED)


def _lane_run_env() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key not in INTERPRETER_REDIRECT_KEYS}
    env["MARK"] = "1"
    return env


def _recorded_env(root: Path) -> dict[str, str]:
    recorded: dict[str, str] = json.loads((root / _ENV_DUMP).read_text(encoding="utf-8"))
    return recorded


# ---------------------------------------------------------------------------
# 1. Declared-command path
# ---------------------------------------------------------------------------


def test_declared_path_runs_in_the_given_run_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _inherit_redirect_keys(monkeypatch)

    verdict = evaluate_pre_review_gate(
        ("src/pkg/mod.py",),
        repo_root=tmp_path,
        baseline=None,
        scope_source=_EnvDumpingScopeSource(),
        run_env=_lane_run_env(),
    )

    assert verdict.outcome is GateOutcome.UNVERIFIED_BASELINE
    recorded = _recorded_env(tmp_path)
    assert recorded["MARK"] == "1"
    assert recorded["PWHEADLESS"] == "1"
    assert not set(INTERPRETER_REDIRECT_KEYS) & recorded.keys()


def test_declared_path_without_run_env_inherits_the_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Positive control: ``run_env=None`` is today's inherited environment."""
    _inherit_redirect_keys(monkeypatch)

    evaluate_pre_review_gate(
        ("src/pkg/mod.py",),
        repo_root=tmp_path,
        baseline=None,
        scope_source=_EnvDumpingScopeSource(),
    )

    recorded = _recorded_env(tmp_path)
    assert {key: recorded.get(key) for key in INTERPRETER_REDIRECT_KEYS} == dict.fromkeys(INTERPRETER_REDIRECT_KEYS, _INHERITED)
    assert recorded["PWHEADLESS"] == "1"
    assert "MARK" not in recorded


# ---------------------------------------------------------------------------
# 2. Override tier (sys.executable fallback)
# ---------------------------------------------------------------------------


def _capture_launch_env(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, str]]:
    """Spy on the launcher: record ``env`` and refuse the launch (no real pytest)."""
    seen: list[dict[str, str]] = []

    def _spy(command: Sequence[str], *, repo_root: Path, env: Mapping[str, str], platform: str | None = None) -> object:
        del command, repo_root, platform
        seen.append(dict(env))
        raise OSError("launch refused by the test spy")

    monkeypatch.setattr(pre_review_gate, "_launch_scoped_process", _spy)
    monkeypatch.setattr(_interpreter.shutil, "which", lambda _name, path=None: None)
    return seen


def test_override_tier_fallback_runs_in_the_given_run_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _inherit_redirect_keys(monkeypatch)
    seen = _capture_launch_env(monkeypatch)
    run_env = _lane_run_env()
    run_env["PYTHONPATH"] = str(tmp_path / "src")

    verdict = evaluate_with_scope(
        ScopeResult.from_override(("tests/test_x.py",)),
        repo_root=tmp_path,
        baseline=None,
        scope_source=None,
        run_env=run_env,
    )

    assert verdict.outcome is GateOutcome.NO_COVERAGE
    assert seen == [{**run_env, "PWHEADLESS": "1"}]


def test_override_tier_fallback_without_run_env_inherits_the_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Positive control: the fallback keeps today's inherited ``PYTHONPATH`` and interpreter (a lane ``.venv`` is not consulted)."""
    _inherit_redirect_keys(monkeypatch)
    seen = _capture_launch_env(monkeypatch)
    commands: list[Sequence[str]] = []
    launch_spy = pre_review_gate._launch_scoped_process

    def _record(command: Sequence[str], **kwargs: object) -> object:
        commands.append(list(command))
        return launch_spy(command, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(pre_review_gate, "_launch_scoped_process", _record)
    lane_python = tmp_path / ".venv" / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
    lane_python.parent.mkdir(parents=True)
    lane_python.write_text("", encoding="utf-8")

    evaluate_with_scope(
        ScopeResult.from_override(("tests/test_x.py",)),
        repo_root=tmp_path,
        baseline=None,
        scope_source=None,
    )

    assert [command[0] for command in commands] == [sys.executable]
    assert len(seen) == 1
    assert {key: seen[0].get(key) for key in INTERPRETER_REDIRECT_KEYS} == dict.fromkeys(INTERPRETER_REDIRECT_KEYS, _INHERITED)
    assert seen[0]["PWHEADLESS"] == "1"


def test_override_tier_fallback_runs_the_interpreter_the_lane_probe_checked(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A lane with its own ``.venv`` and no ``uv`` on the run's PATH runs pytest in that venv, not in the CLI interpreter."""
    commands: list[list[str]] = []

    def _spy(command: Sequence[str], *, repo_root: Path, env: Mapping[str, str], platform: str | None = None) -> object:
        del repo_root, env, platform
        commands.append(list(command))
        raise OSError("launch refused by the test spy")

    monkeypatch.setattr(pre_review_gate, "_launch_scoped_process", _spy)
    monkeypatch.setattr(_interpreter.shutil, "which", lambda _name, path=None: None)
    lane_python = tmp_path / ".venv" / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
    lane_python.parent.mkdir(parents=True)
    lane_python.write_text("", encoding="utf-8")

    evaluate_with_scope(
        ScopeResult.from_override(("tests/test_x.py",)),
        repo_root=tmp_path,
        baseline=None,
        scope_source=None,
        run_env=_lane_run_env(),
    )

    assert [command[:3] for command in commands] == [[str(lane_python), "-m", "pytest"]]


def test_override_tier_uv_path_strips_redirects_from_the_given_run_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """On the ``uv run --project <lane>`` path the redirect variables never reach the run, run_env or not."""
    _inherit_redirect_keys(monkeypatch)
    seen = _capture_launch_env(monkeypatch)
    monkeypatch.setattr(_interpreter.shutil, "which", lambda _name, path=None: "/usr/bin/uv")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    (tmp_path / "uv.lock").write_text("", encoding="utf-8")
    run_env = _lane_run_env()
    run_env["PYTHONPATH"] = str(tmp_path / "src")

    evaluate_with_scope(
        ScopeResult.from_override(("tests/test_x.py",)),
        repo_root=tmp_path,
        baseline=None,
        scope_source=None,
        run_env=run_env,
    )

    assert len(seen) == 1
    assert seen[0]["MARK"] == "1"
    assert seen[0]["PWHEADLESS"] == "1"
    assert not set(INTERPRETER_REDIRECT_KEYS) & set(seen[0])


# ---------------------------------------------------------------------------
# 3. Baseline symmetry
# ---------------------------------------------------------------------------


def _git_tracked_tree(root: Path, files: Sequence[str]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    for relative in files:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "--", *files], check=True)


def _capture_baseline_env(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, str] | None]:
    seen: list[dict[str, str] | None] = []

    def _spy(command: Sequence[str], *, repo_root: Path, env: Mapping[str, str] | None = None, **_: object) -> tuple[HeadRunState, RawRunResult, None]:
        del command, repo_root
        seen.append(None if env is None else dict(env))
        return HeadRunState.COMPLETED, RawRunResult(returncode=0, stdout="", stderr="", output_artifact_path=None), None

    monkeypatch.setattr(pre_review_gate, "_run_raw_command", _spy)
    return seen


def test_baseline_run_applies_the_lane_recipe_at_its_worktree(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _inherit_redirect_keys(monkeypatch)
    worktree = tmp_path / "base"
    _git_tracked_tree(worktree, ["src/pkg/__init__.py"])
    seen = _capture_baseline_env(monkeypatch)

    baseline._run_command_for_baseline(["true"], cwd=worktree)

    assert len(seen) == 1
    env = seen[0]
    assert env is not None
    assert env["PYTHONPATH"] == str(worktree / "src")
    assert "VIRTUAL_ENV" not in env
    assert "UV_PROJECT_ENVIRONMENT" not in env
    assert env["PWHEADLESS"] == "1"


def test_baseline_run_without_source_packages_sets_no_pythonpath(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _inherit_redirect_keys(monkeypatch)
    worktree = tmp_path / "base"
    _git_tracked_tree(worktree, ["README.md"])
    seen = _capture_baseline_env(monkeypatch)

    baseline._run_command_for_baseline(["true"], cwd=worktree)

    env = seen[0]
    assert env is not None
    assert not set(INTERPRETER_REDIRECT_KEYS) & env.keys()
