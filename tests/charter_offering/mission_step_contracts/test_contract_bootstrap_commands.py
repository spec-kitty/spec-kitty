"""Every built-in step contract's bootstrap command must parse against the CLI.

A contract's bootstrap step declares ``spec-kitty charter context --action <x>
--json`` plus optional ``inputs``. The executor's ``_render_declared_command``
appends those ``inputs`` to the command string an operator or host runs
verbatim. Every built-in contract advertised ``--profile {wp.agent_profile}``
and ``--tool {env.agent_tool}`` inputs, which ``charter context`` rejects — the
rendered command does not parse.

This module renders each built-in contract's bootstrap command through the real
``_render_declared_command`` seam and parses it against the Click command, so
the contract text and the CLI signature meet in CI rather than at paste time.
"""

from __future__ import annotations

import shlex
from pathlib import Path

import click
import pytest
from typer.main import get_command

from charter.offering.missions.step_contracts import MissionStepContractRepository
from specify_cli.mission_step_contracts.executor import StepContractExecutor

pytestmark = [pytest.mark.fast, pytest.mark.corpus]

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _bootstrap_commands() -> list[tuple[str, str]]:
    """Every (contract id, rendered bootstrap command) for the built-in contracts."""
    repo = MissionStepContractRepository()
    executor = StepContractExecutor(repo_root=_REPO_ROOT)
    found: list[tuple[str, str]] = []
    for contract in repo.all():
        bootstrap = contract.steps[0]
        rendered = executor._render_declared_command(bootstrap).strip()
        if rendered.startswith("spec-kitty "):
            found.append((contract.id, rendered))
    return found


BOOTSTRAP_COMMANDS = _bootstrap_commands()


def test_some_bootstrap_commands_were_discovered() -> None:
    """Guard the guard: if discovery returns nothing the parametrized test vanishes."""
    assert BOOTSTRAP_COMMANDS, "discovered no spec-kitty bootstrap commands in built-in step contracts"


def _resolve(argv: list[str]) -> tuple[click.Command, list[str]]:
    """Walk the Click group tree to the leaf command, returning (cmd, remaining argv)."""
    from specify_cli import app

    node = get_command(app)
    rest = list(argv)
    while rest:
        sub = getattr(node, "commands", None)
        if not sub or rest[0] not in sub:
            break
        node = sub[rest.pop(0)]
    return node, rest


@pytest.mark.parametrize(
    ("contract_id", "command"),
    BOOTSTRAP_COMMANDS,
    ids=[contract_id for contract_id, _ in BOOTSTRAP_COMMANDS],
)
def test_bootstrap_command_parses(contract_id: str, command: str) -> None:
    """The rendered bootstrap command's options all exist on the CLI that runs it.

    Parse only — nothing is executed, so this stays a fast unit check.
    """
    argv = shlex.split(command)
    assert argv[0] == "spec-kitty"

    leaf, remaining = _resolve(argv[1:])
    try:
        leaf.make_context(leaf.name, list(remaining), resilient_parsing=False).close()
    except click.NoSuchOption as exc:
        pytest.fail(
            f"{contract_id} bootstrap renders `{command}`, but the CLI rejects "
            f"{exc.option_name!r}. A contract may not advertise a flag the parser does "
            f"not have — an operator or host runs this rendered string verbatim."
        )
    except click.UsageError as exc:  # noqa: TID251 — test names the click universe of the command it built itself, or deliberately the standalone-click spelling
        pytest.fail(f"{contract_id} bootstrap renders `{command}`, which does not parse: {exc}")
