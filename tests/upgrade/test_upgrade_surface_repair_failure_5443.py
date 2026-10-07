"""#5443 — a tool-surface repair that fails after the migrations succeeded commits nothing.

``finalize_upgrade`` runs the churn commit after the surface repair. Before the
gate in ``_finalizer_step_commit_churn``, a repair whose recheck refused to apply
(``Profile source/config input root changed``) still let the upgrade commit land,
and the run then closed with "Upgrade failed." (exit 1): a failed upgrade that
committed. The end-to-end case drives a real ``spec-kitty upgrade`` in the hermetic
sandbox of ``_legacy_upgrade_fixture`` with the repair forced to report that
precondition change through a ``sitecustomize`` shim on the child's ``PYTHONPATH``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from specify_cli.cli.commands import upgrade as upgrade_cmd
from specify_cli.upgrade import autocommit
from specify_cli.upgrade.outcome import SurfaceRepairReport, UpgradeOutcome
from specify_cli.upgrade.runner import UpgradeResult
from tests.upgrade._legacy_upgrade_fixture import MARKED_COMMAND_FILE, build_legacy, flat, head, run_upgrade, status_z

_INPUT_ROOT_CHANGED = "Profile source/config input root changed"
_SHIM = f'''\
"""Test shim: every tool-surface repair batch reports a changed precondition (no writes)."""
import specify_cli.upgrade.assessment as _assessment
from specify_cli.tool_surface.operations import Diagnostic, OwnerApplyResult


def _input_root_changed(_prepared):
    diagnostic = Diagnostic("precondition_changed", "agent_profiles", "error", {_INPUT_ROOT_CHANGED!r})
    return (OwnerApplyResult("agent_profiles", diagnostics=(diagnostic,), outcome="precondition_changed"),)


_assessment.apply_upgrade_repairs = _input_root_changed
'''
_IMPLEMENT = ".claude/commands/spec-kitty.implement.md"
_CUSTOM = ".claude/commands/spec-kitty.custom.md"
_CUSTOM_BODY = "# my own command\nhand written, no version marker\n"
_DIRTY_SOURCE = "A = 2  # operator edit in progress\n"
_UNTRACKED_NOTE = "notes/todo.md"


@pytest.mark.regression
@pytest.mark.git_repo
@pytest.mark.non_sandbox
def test_failed_surface_repair_commits_nothing(tmp_path: Path) -> None:
    project, env = build_legacy(
        tmp_path,
        agents=["claude"],
        gitignore="*.pyc\n",
        extra_files={_IMPLEMENT: MARKED_COMMAND_FILE, _CUSTOM: _CUSTOM_BODY},
    )
    shim = tmp_path / "shim"
    shim.mkdir()
    (shim / "sitecustomize.py").write_text(_SHIM, encoding="utf-8")
    env["PYTHONPATH"] = f"{shim}{os.pathsep}{env['PYTHONPATH']}"
    (project / "src" / "app.py").write_text(_DIRTY_SOURCE, encoding="utf-8")
    (project / _UNTRACKED_NOTE).parent.mkdir()
    (project / _UNTRACKED_NOTE).write_text("operator scratch\n", encoding="utf-8")
    head0 = head(project, env)

    result = run_upgrade(project, env)
    output = flat(result.stdout + result.stderr)

    assert _INPUT_ROOT_CHANGED in output, "the shim must make the surface repair fail"
    assert result.returncode != 0, output
    assert "Upgrade failed." in output
    assert head(project, env) == head0, "a failed surface repair must leave no upgrade commit"
    assert "Auto-committed upgrade changes" not in output
    assert flat(autocommit.FAILED_RUN_LEFT_UNCOMMITTED_WARNING) in output
    assert (project / "src" / "app.py").read_text(encoding="utf-8") == _DIRTY_SOURCE
    assert (project / _CUSTOM).read_text(encoding="utf-8") == _CUSTOM_BODY
    assert (project / _UNTRACKED_NOTE).read_text(encoding="utf-8") == "operator scratch\n"
    assert (" M", "src/app.py") in status_z(project, env), "the operator's edit stays an unstaged change"


def _outcome(*, surface_failed: bool = False, worktree_failed: bool = False, drifted: bool = False) -> UpgradeOutcome:
    outcome = UpgradeOutcome(
        result=UpgradeResult(success=True, from_version="2.1.0", to_version="4.0.0"),
        worktree_failures=["Worktree wt-a: boom"] if worktree_failed else [],
        had_migrations=True,
    )
    outcome.record_surface_repair(
        SurfaceRepairReport(
            failed=surface_failed,
            failure_messages=(_INPUT_ROOT_CHANGED,) if surface_failed else (),
            drifted_paths=(Path(".claude/commands/x.md"),) if drifted else (),
        )
    )
    return outcome


def _run_commit_step(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, outcome: UpgradeOutcome) -> tuple[bool, list[tuple[object, ...]]]:
    calls: list[tuple[object, ...]] = []

    def _recording_commit(*args: object) -> tuple[bool, list[str], None]:
        calls.append(args)
        return True, ["src/new.py"], None

    monkeypatch.setattr(autocommit, "commit_touched_checkout", _recording_commit)
    ctx = upgrade_cmd._FinalizerRenderContext()
    committed = upgrade_cmd._finalizer_step_commit_churn(outcome, ctx, project_path=tmp_path, baseline_changed_paths=set())
    return committed, calls


@pytest.mark.unit
@pytest.mark.fast
@pytest.mark.regression
def test_commit_step_commits_nothing_after_failed_surface_repair(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    committed, calls = _run_commit_step(monkeypatch, tmp_path, _outcome(surface_failed=True))
    assert committed is False
    assert calls == [], "commit_touched_checkout must not run once the outcome already reports failure"


@pytest.mark.unit
@pytest.mark.fast
@pytest.mark.parametrize(
    "outcome_kwargs",
    [
        pytest.param({}, id="clean"),
        pytest.param({"drifted": True}, id="drift-held-for-consent"),
        pytest.param({"worktree_failed": True}, id="worktree-failure-gates-only-its-own-commit"),
    ],
)
def test_commit_step_still_commits_main_checkout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, outcome_kwargs: dict[str, bool]) -> None:
    committed, calls = _run_commit_step(monkeypatch, tmp_path, _outcome(**outcome_kwargs))
    assert committed is True
    assert len(calls) == 1


@pytest.mark.unit
@pytest.mark.fast
@pytest.mark.regression
def test_no_commit_reason_after_failed_surface_repair_is_the_failed_run_reason() -> None:
    reason = upgrade_cmd._no_commit_reason(
        _outcome(surface_failed=True),
        dry_run=False,
        should_commit_main=True,
        baseline_available=True,
        metadata_dirty_at_baseline=False,
        churn_present=True,
    )
    assert reason == autocommit.FAILED_RUN_LEFT_UNCOMMITTED_WARNING
