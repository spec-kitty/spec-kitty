"""#2573 fast-follow (partial): ``--skip-pre-review-gate`` flag + disable-env
honoring + running-progress legibility on ``_mt_run_pre_review_gate``.

``move-task --to for_review`` runs a synchronous, potentially multi-minute
scoped pytest subprocess (``pre_review_gate.run_scoped_tests_at_head``) with
no way to skip it — the loop-friction fast-follow spec
(``docs/plans/investigations/loop-friction-fastfollow-spec.md`` FR-002/FR-003) adds:

1. an explicit ``--skip-pre-review-gate`` CLI flag (``st.skip_pre_review_gate``),
2. honoring the gate's own ``SPEC_KITTY_SKIP_PRE_REVIEW_GATE`` env var as a
   process-wide opt-out (#3980 — the sync-disable vocabulary is no longer
   read here),
3. a console notice before the scoped run starts, so it never reads as a
   silent hang.

Every skip scenario below proves the workspace is NEVER touched (no
``_mt_resolve_pre_review_workspace`` call, so no diff/subprocess can follow)
— the escape hatch must short-circuit BEFORE any I/O, not merely suppress
the eventual verdict. The default-behavior test proves the opposite: with
neither the flag nor an env var set, the gate still attempts to resolve the
workspace exactly as before this fix (NFR-003 backward compatibility).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import click
import pytest
from typer.main import get_command
from typer.testing import CliRunner

from specify_cli.cli.commands.agent import tasks_move_task
from specify_cli.cli.commands.agent.tasks import app
from specify_cli.cli.commands.agent.tasks_move_task import _MoveTaskState
from specify_cli.review import pre_review_gate
from specify_cli.review.gate_bindings import GateBindingResolution, GateCoverage
from specify_cli.status import Lane

pytestmark = pytest.mark.fast

_TASKS = "specify_cli.cli.commands.agent.tasks"
_MODULE = "specify_cli.cli.commands.agent.tasks_move_task"

runner = CliRunner()


class _WorkspaceTouched(Exception):
    """Raised by the sentinel workspace resolver to prove it was reached."""


def _make_state(**overrides: Any) -> _MoveTaskState:
    kwargs: dict[str, Any] = {
        "task_id": "WP01",
        "to": "for_review",
        "mission": "test-pre-review-escape",
        "agent": "claude",
        "assignee": None,
        "shell_pid": None,
        "note": None,
        "review_feedback_file": None,
        "approval_ref": None,
        "reviewer": None,
        "self_review_fallback": False,
        "intended_reviewer": None,
        "reviewer_failure_reason": None,
        "done_override_reason": None,
        "force": False,
        "tracker_ref": None,
        "skip_review_artifact_check": False,
        "auto_commit": None,
        "json_output": False,
        "skip_pre_review_gate": False,
    }
    field_names = set(_MoveTaskState.__dataclass_fields__)
    field_overrides = {k: v for k, v in overrides.items() if k in kwargs}
    kwargs.update(field_overrides)
    st = _MoveTaskState(**kwargs)
    for key, value in overrides.items():
        if key not in field_overrides:
            assert key in field_names, f"unknown _MoveTaskState field: {key!r}"
            setattr(st, key, value)
    st.target_lane = Lane.FOR_REVIEW
    # Category-B sentinel (not a shared-temp-dir literal): the gate is skipped,
    # so this repo root is never touched — a fixed non-existent absolute path.
    st.main_repo_root = Path("/nonexistent/pre-review-skip-repo-root")
    st.target_branch = "main"
    st.mission_slug = "test-pre-review-escape"
    st.wp = SimpleNamespace(path=Path("WP01-x.md"), frontmatter="")
    return st


# --------------------------------------------------------------------------- #
# Skip escape hatches (FR-002) — must short-circuit BEFORE any workspace I/O.
# --------------------------------------------------------------------------- #


def test_skip_flag_skips_gate_without_touching_workspace() -> None:
    """``--skip-pre-review-gate`` never resolves a workspace or runs pytest."""
    st = _make_state(skip_pre_review_gate=True)
    with patch(
        f"{_MODULE}._mt_resolve_pre_review_workspace", side_effect=_WorkspaceTouched
    ) as workspace_mock:
        tasks_move_task._mt_run_pre_review_gate(st)
    workspace_mock.assert_not_called()
    assert st.pre_review_gate_metadata is not None
    assert st.pre_review_gate_metadata["outcome"] == pre_review_gate.GateOutcome.NO_COVERAGE.value
    assert "--skip-pre-review-gate flag" in (st.pre_review_gate_metadata["reason"] or "")
    assert st.pre_review_gate_metadata["blocked"] is False


@pytest.mark.parametrize("env_var", ["SPEC_KITTY_SKIP_PRE_REVIEW_GATE"])
def test_disable_env_var_skips_gate_without_touching_workspace(
    env_var: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The gate's own opt-out env var short-circuits the gate the same way
    as the explicit flag — no workspace resolution, no subprocess."""
    monkeypatch.setenv(env_var, "1")
    st = _make_state()
    with patch(
        f"{_MODULE}._mt_resolve_pre_review_workspace", side_effect=_WorkspaceTouched
    ) as workspace_mock:
        tasks_move_task._mt_run_pre_review_gate(st)
    workspace_mock.assert_not_called()
    assert st.pre_review_gate_metadata is not None
    assert env_var in (st.pre_review_gate_metadata["reason"] or "")


@pytest.mark.parametrize("falsy_value", ["0", "false", "", "no"])
def test_falsy_env_value_does_not_skip_gate(
    falsy_value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A present-but-falsy env var must NOT trip the skip — only recognized
    truthy tokens (the ``core.env.is_truthy`` grammar) do."""
    monkeypatch.setenv("SPEC_KITTY_SKIP_PRE_REVIEW_GATE", falsy_value)


@pytest.mark.parametrize("env_var", ["SPEC_KITTY_SYNC_DISABLE", "SPEC_KITTY_SYNC_MINIMAL_IMPORT"])
def test_sync_disable_vocabulary_no_longer_skips_gate(
    env_var: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#3980: disarming sync must not silently skip a review gate — the gate
    no longer reads the sync-disable vocabulary, so a truthy value there
    leaves the gate enforcing (the workspace is still resolved)."""
    monkeypatch.setenv(env_var, "1")
    st = _make_state()
    with patch(
        f"{_MODULE}._mt_resolve_pre_review_workspace", return_value=None
    ) as workspace_mock:
        tasks_move_task._mt_run_pre_review_gate(st)
    workspace_mock.assert_called_once()


def test_skip_prints_explicit_skip_notice(monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-003 legibility: a skip is announced, not silent."""
    st = _make_state(skip_pre_review_gate=True, json_output=False)
    with (
        patch(f"{_MODULE}._mt_resolve_pre_review_workspace", side_effect=_WorkspaceTouched),
        patch(f"{_TASKS}.console") as console_mock,
    ):
        tasks_move_task._mt_run_pre_review_gate(st)
    printed = " ".join(str(call.args[0]) for call in console_mock.print.call_args_list)
    assert "SKIPPED" in printed
    assert "--skip-pre-review-gate flag" in printed


def test_skip_prints_nothing_under_json_output() -> None:
    """``--json`` output stays machine-readable — no console noise on skip."""
    st = _make_state(skip_pre_review_gate=True, json_output=True)
    with (
        patch(f"{_MODULE}._mt_resolve_pre_review_workspace", side_effect=_WorkspaceTouched),
        patch(f"{_TASKS}.console") as console_mock,
    ):
        tasks_move_task._mt_run_pre_review_gate(st)
    console_mock.print.assert_not_called()


# --------------------------------------------------------------------------- #
# Default behavior (NFR-003) — neither flag nor env set: gate still runs.
# --------------------------------------------------------------------------- #


def test_default_still_attempts_to_resolve_workspace_and_run_gate() -> None:
    """With no flag and no env var set, the gate is NOT skipped — it still
    resolves the workspace exactly as before this fix."""
    st = _make_state()
    with patch(
        f"{_MODULE}._mt_resolve_pre_review_workspace", return_value=None
    ) as workspace_mock:
        tasks_move_task._mt_run_pre_review_gate(st)
    workspace_mock.assert_called_once()
    assert st.pre_review_gate_metadata is not None
    reason = st.pre_review_gate_metadata["reason"] or ""
    assert "gate skipped" not in reason
    assert "--skip-pre-review-gate" not in reason
    assert "SPEC_KITTY_SKIP_PRE_REVIEW_GATE" not in reason


def test_default_does_not_print_skip_notice() -> None:
    """The ordinary (non-skip) console line must not claim SKIPPED."""
    st = _make_state()
    with (
        patch(f"{_MODULE}._mt_resolve_pre_review_workspace", return_value=None),
        patch(f"{_TASKS}.console") as console_mock,
    ):
        tasks_move_task._mt_run_pre_review_gate(st)
    printed = " ".join(str(call.args[0]) for call in console_mock.print.call_args_list)
    assert "SKIPPED" not in printed


# --------------------------------------------------------------------------- #
# Progress legibility (FR-003) — a non-empty scope prints a running notice
# BEFORE the (mocked) scoped test run, so it never reads as a silent hang.
# --------------------------------------------------------------------------- #


def test_progress_notice_printed_before_running_nonempty_scope() -> None:
    """WP09 migration: under the inverted hook, a non-empty scope = a non-empty
    changed-file set with an ACTIVE doctrine binding. The hook prints the running
    notice in ``_mt_collect_transition_gate_verdicts`` BEFORE dispatching the
    bound handler. The dispatch seam is stubbed so no real handler/subprocess
    runs; the assertion is purely about notice-before-dispatch ordering + content
    (the incumbent's frontmatter-override tier is retired — the scope is the
    changed-files SSOT applied through the ScopeSource).
    """
    st = _make_state()
    call_order: list[str] = []
    active = GateBindingResolution(
        coverage=GateCoverage.ACTIVE,
        edge_key="in_progress->for_review",
        owning_contract_urn="mission_step_contract:software-dev/review",
        reason="1 active gate binding(s)",
        active=(SimpleNamespace(handler="spec-kitty-pre-review"),),
    )
    fake_verdict = pre_review_gate.GateVerdict(
        outcome=pre_review_gate.GateOutcome.NO_NEW_FAILURES,
        scope=pre_review_gate.ScopeResult.from_override(("tests/foo/test_bar.py",)),
        reason="stubbed dispatch — no real run",
    )

    def _fake_dispatch(*args: Any, **kwargs: Any) -> list[pre_review_gate.GateVerdict]:
        call_order.append("dispatch")
        return [fake_verdict]

    with (
        patch(f"{_MODULE}._mt_resolve_pre_review_workspace", return_value=Path("/lane")),
        patch(f"{_MODULE}._mt_pre_review_changed_files", return_value=("src/example.py",)),
        patch(f"{_MODULE}._mt_pre_review_dirty_paths", return_value=()),
        patch(f"{_MODULE}._mt_resolve_active_gate_bindings", return_value=active),
        # #3821: this arm is about a RUNNING gate, so the fixture repo counts as
        # declared (the undeclared-repo quiet skip is covered in
        # ``test_pre_review_gate_integration.py``).
        patch(f"{_MODULE}._mt_pre_review_gate_declared", return_value=True),
        patch(f"{_MODULE}._mt_build_transition_gate_context", return_value=object()),
        patch(f"{_MODULE}._mt_dispatch_transition_gates", side_effect=_fake_dispatch),
        patch(f"{_TASKS}.console") as console_mock,
    ):
        console_mock.print.side_effect = lambda *a, **k: call_order.append("print")
        tasks_move_task._mt_run_pre_review_gate(st)

    assert call_order[0] == "print", "the progress notice must print BEFORE dispatch"
    assert "dispatch" in call_order
    assert call_order.index("print") < call_order.index("dispatch")
    printed = " ".join(str(call.args[0]) for call in console_mock.print.call_args_list)
    assert "running scoped tests at head" in printed
    assert "may take a few minutes" in printed


def test_no_progress_notice_when_scope_is_empty() -> None:
    """No changed files -> the cheap empty-scope path short-circuits before
    binding resolution and never claims it's "running" anything (it isn't)."""
    st = _make_state()
    with (
        patch(f"{_MODULE}._mt_resolve_pre_review_workspace", return_value=None),
        patch(f"{_TASKS}.console") as console_mock,
    ):
        tasks_move_task._mt_run_pre_review_gate(st)
    printed = " ".join(str(call.args[0]) for call in console_mock.print.call_args_list)
    assert "running scoped tests at head" not in printed


# --------------------------------------------------------------------------- #
# Not-a-for_review-move: the gate does not even reach the skip check.
# --------------------------------------------------------------------------- #


def test_non_for_review_lane_returns_before_any_skip_logic() -> None:
    st = _make_state(skip_pre_review_gate=True)
    st.target_lane = Lane.IN_PROGRESS
    with patch(
        f"{_MODULE}._mt_resolve_pre_review_workspace", side_effect=_WorkspaceTouched
    ) as workspace_mock:
        tasks_move_task._mt_run_pre_review_gate(st)
    workspace_mock.assert_not_called()
    assert st.pre_review_gate_metadata is None


# --------------------------------------------------------------------------- #
# CLI wiring — the ``move-task`` Typer command declares ``--skip-pre-review-gate``
# and forwards it to ``_do_move_task`` (the orchestrator this module tests
# above). These prove the flag actually reaches the seam, not just that the
# seam behaves correctly once fed it.
# --------------------------------------------------------------------------- #


def test_skip_pre_review_gate_flag_is_registered_on_move_task_help() -> None:
    result = runner.invoke(app, ["move-task", "--help"], terminal_width=160)

    assert result.exit_code == 0, result.output
    group = get_command(app)
    assert isinstance(group, click.Group)
    click_command = group.commands["move-task"]
    option = next(
        param
        for param in click_command.params
        if isinstance(param, click.Option) and param.name == "skip_pre_review_gate"
    )
    assert "--skip-pre-review-gate" in option.opts
    assert option.default is False
    assert "SPEC_KITTY_SKIP_PRE_REVIEW_GATE" in (option.help or "")


def test_move_task_cli_forwards_skip_flag_to_orchestrator() -> None:
    """The Typer wrapper passes ``--skip-pre-review-gate`` through as
    ``skip_pre_review_gate=True`` — proving the CLI-declared flag actually
    reaches ``_do_move_task`` (not just that it parses).

    WP07 (T033, #2649): the wrapper now passes a single ``_MoveTaskArgs``
    parameter object positionally rather than individual kwargs — assert on
    the constructed object's field instead of a top-level kwarg.
    """
    with patch(f"{_TASKS}._do_move_task") as do_move_task_mock:
        result = runner.invoke(
            app,
            [
                "move-task",
                "WP01",
                "--to",
                "for_review",
                "--skip-pre-review-gate",
                "--mission",
                "test-mission",
            ],
        )
    assert result.exit_code == 0, result.output
    do_move_task_mock.assert_called_once()
    forwarded_args = do_move_task_mock.call_args.args[0]
    assert forwarded_args.skip_pre_review_gate is True


def test_move_task_cli_default_omits_skip_flag() -> None:
    """Without the flag, the orchestrator receives ``skip_pre_review_gate=False``
    — the default stays the enforcing behavior (NFR-003)."""
    with patch(f"{_TASKS}._do_move_task") as do_move_task_mock:
        result = runner.invoke(
            app,
            [
                "move-task",
                "WP01",
                "--to",
                "for_review",
                "--mission",
                "test-mission",
            ],
        )
    assert result.exit_code == 0, result.output
    do_move_task_mock.assert_called_once()
    forwarded_args = do_move_task_mock.call_args.args[0]
    assert forwarded_args.skip_pre_review_gate is False
