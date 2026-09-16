"""#3951 — both verdict commands resolve at the ``agent`` level.

F-58: ``acceptance-verdict`` previously lived only under ``agent mission``
while ``issue-verdict`` lived at ``agent issue-verdict``, so an operator
following the one-level pattern of ``agent --help`` hit "No such command"
for the sibling verdict command.  The mission-level registration stays
(mission-step prompts and the docs name it); these tests pin the top-level
registrations so the two verdict commands cannot drift to different nesting
levels again.  F-36's ``decision list`` is pinned alongside (an orchestrating
agent's first read query — previously "No such command").
"""

from __future__ import annotations

import pytest
import typer
from typer.main import get_command

from specify_cli.cli.commands.agent import app as agent_app
from specify_cli.cli.commands.decision import decision_app

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _visible_command_names(typer_app: typer.Typer) -> set[str]:
    """Non-hidden command names registered on a Typer app (click view)."""
    click_group = get_command(typer_app)
    return {name for name, cmd in click_group.commands.items() if not getattr(cmd, "hidden", False)}


def test_both_verdict_commands_live_at_the_agent_level() -> None:
    names = _visible_command_names(agent_app)
    assert "issue-verdict" in names
    assert "acceptance-verdict" in names


def test_decision_subgroup_exposes_list() -> None:
    names = _visible_command_names(decision_app)
    assert "list" in names
    assert {"open", "resolve", "defer", "cancel", "verify"} <= names
