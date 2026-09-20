"""#3469 — ``move-task`` accepts ``--actor``/``--reason`` as aliases of
``--agent``/``--note``.

Regression proof: before this fix, ``move-task`` only accepted ``--agent``/
``--note``; the natural ``--actor``/``--reason`` spelling — the vocabulary
the sibling ``issue-verdict`` command already uses — failed with Typer's
"No such option" error. This drives the LIVE Typer entry point
(``specify_cli.cli.commands.agent.tasks.app``) and inspects the
``_MoveTaskArgs`` handed to ``_do_move_task`` (patched out so the test needs
no real mission fixture — this WP tests CLI-surface flag resolution, not
transition execution) to confirm the alias resolves to the SAME parameter
values as the canonical spelling.

RED on the planning base (``fix/move-task-approval-ergonomics`` pre-WP04):
Typer rejects ``--actor``/``--reason`` outright (exit_code=2, "No such
option"). GREEN once the aliases land on the same ``--agent``/``--note``
options (T016).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.tasks import _MoveTaskArgs, app

pytestmark = pytest.mark.regression

runner = CliRunner()


def _invoke_and_capture(extra_args: list[str]) -> _MoveTaskArgs:
    """Drive ``move-task`` with ``extra_args`` and return the captured
    ``_MoveTaskArgs`` passed to the (patched-out) ``_do_move_task`` orchestrator.
    """
    with patch("specify_cli.cli.commands.agent.tasks._do_move_task") as mock_do_move_task:
        result = runner.invoke(
            app,
            ["move-task", "WP01", "--to", "doing", *extra_args],
            catch_exceptions=False,
        )
    assert result.exit_code == 0, result.output
    mock_do_move_task.assert_called_once()
    args, kwargs = mock_do_move_task.call_args
    assert not kwargs, "_do_move_task is invoked with a single positional _MoveTaskArgs"
    assert len(args) == 1
    captured = args[0]
    assert isinstance(captured, _MoveTaskArgs)
    return captured


def test_actor_and_reason_apply_same_values_as_agent_and_note() -> None:
    """#3469 (FR-005, US3 Scenario 1): ``--actor``/``--reason`` must behave
    identically to ``--agent``/``--note``.
    """
    via_actor = _invoke_and_capture(["--actor", "claude", "--reason", "starting WP01"])
    via_agent = _invoke_and_capture(["--agent", "claude", "--note", "starting WP01"])

    assert via_actor.agent == "claude"
    assert via_actor.note == "starting WP01"
    assert via_actor.agent == via_agent.agent
    assert via_actor.note == via_agent.note


def test_agent_and_note_still_work_no_regression() -> None:
    """#3469 (FR-005 no-regression): the canonical ``--agent``/``--note``
    spelling must keep working unchanged.
    """
    captured = _invoke_and_capture(["--agent", "claude", "--note", "starting WP01"])
    assert captured.agent == "claude"
    assert captured.note == "starting WP01"


def test_both_spellings_passed_last_one_wins() -> None:
    """#3469 (T016): when both spellings are passed, exactly one value wins.

    ``--agent``/``--actor`` (and ``--note``/``--reason``) are the same
    underlying option carrying two accepted flag names — the last flag
    supplied on the command line wins, matching the documented precedence.
    """
    agent_last = _invoke_and_capture(["--actor", "bob", "--agent", "claude", "--note", "x"])
    assert agent_last.agent == "claude"

    actor_last = _invoke_and_capture(["--agent", "claude", "--actor", "bob", "--note", "x"])
    assert actor_last.agent == "bob"

    note_last = _invoke_and_capture(["--agent", "claude", "--reason", "y", "--note", "z"])
    assert note_last.note == "z"

    reason_last = _invoke_and_capture(["--agent", "claude", "--note", "z", "--reason", "y"])
    assert reason_last.note == "y"
