"""Every `spec-kitty ...` command a shipped step contract declares must parse (#4031).

A step contract's `command` is an instruction handed to a host or an operator to
run verbatim. Nothing previously checked it against the CLI that has to accept
it, so all 17 shipped contracts declared

    spec-kitty charter context --action <x> --role <x> --json

against a `charter context` parser that has no `--role`. Every one exited 2 with
`No such option: --role`, which meant the governance-context bootstrap was
broken for every mission action — specify, plan, tasks, implement, review, all
five research steps and all seven documentation steps.

Contract text and CLI signature drifted because they are edited in different
places and only meet at runtime, in an instruction a human or agent pastes. This
module is the seam that makes them meet in CI instead.
"""

from __future__ import annotations

import shlex

import pytest
import click
from typer.main import get_command

from charter.offering.missions.step_contracts import MissionStepContractRepository

pytestmark = [pytest.mark.fast, pytest.mark.corpus]


def _shipped_steps() -> list[tuple[str, str, str]]:
    """Every (contract id, step id, command) whose command invokes `spec-kitty`."""
    repo = MissionStepContractRepository()
    found: list[tuple[str, str, str]] = []
    for contract in repo.all():
        for step in contract.steps:
            command = (getattr(step, "command", None) or "").strip()
            if command.startswith("spec-kitty "):
                found.append((contract.id, step.id, command))
    return found


SHIPPED_STEPS = _shipped_steps()


def test_some_commands_were_discovered() -> None:
    """Guard the guard.

    If discovery silently returns nothing — the repository API changes, or
    `command` is renamed — every parametrized test below vanishes and the suite
    goes green while checking nothing. This is the canary for that.
    """
    assert SHIPPED_STEPS, "discovered no spec-kitty commands in shipped step contracts"


def _resolve(argv: list[str]):
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
    ("contract_id", "step_id", "command"),
    SHIPPED_STEPS,
    ids=[f"{c}:{s}" for c, s, _ in SHIPPED_STEPS],
)
def test_declared_command_parses(contract_id: str, step_id: str, command: str) -> None:
    """The declared command's options all exist on the CLI that must accept it.

    Parse only — nothing is executed, so this stays a fast unit check with no
    repository, network, or first-load state involved.
    """
    argv = shlex.split(command)
    assert argv[0] == "spec-kitty"

    leaf, remaining = _resolve(argv[1:])
    try:
        leaf.make_context(leaf.name, list(remaining), resilient_parsing=False).close()
    except click.NoSuchOption as exc:  # the #4031 failure mode, called out by name
        pytest.fail(
            f"{contract_id}:{step_id} declares `{command}`, but the CLI rejects "
            f"{exc.option_name!r}. A contract may not advertise a flag the parser "
            f"does not have — an operator or host runs this string verbatim."
        )
    except click.UsageError as exc:
        pytest.fail(f"{contract_id}:{step_id} declares `{command}`, which does not parse: {exc}")


@pytest.mark.parametrize(
    ("contract_id", "step_id", "command"),
    SHIPPED_STEPS,
    ids=[f"{c}:{s}" for c, s, _ in SHIPPED_STEPS],
)
def test_declared_command_carries_no_role_flag(contract_id: str, step_id: str, command: str) -> None:
    """`--role` specifically, in case a future parser gains an unrelated `--role`.

    The flag was pure redundancy — its value was always identical to `--action`
    — so reintroducing it would add no information even if some command later
    accepts one. Named explicitly so a regression reads as itself rather than as
    a generic parse failure.
    """
    assert "--role" not in shlex.split(command), f"{contract_id}:{step_id} reintroduced `--role` in `{command}`; `--action` already carries that value (#4031)."


# NOTE: the seven documentation contracts additionally advertise `--profile`
# (`wp.agent_profile`) and `--tool` (`env.agent_tool`) as optional `inputs` on
# the bootstrap step, and the `charter context` parser accepts neither. That is
# deliberately NOT fixed here. `executor._render_declared_command` DOES append
# those inputs to the "Declared command:" line, but only as an unsubstituted,
# bracketed template — `[--profile {wp.agent_profile}]` — whose `{source}`
# placeholders nothing in `src/` resolves or executes; the executor is untouched
# by this PR, so their un-parseability is pre-existing and there is no exit-2
# runtime path the way a raw `--role` in `command` was. Removing them would also
# trip `test_shipped_contracts.test_all_builtin_bootstrap_inputs_are_preserved`,
# which guards them on purpose (added by #1541 after they were lost once).
# Resolving it is a design call — either the CLI grows the flags or the
# contracts drop them — not a hotfix. Tracked separately; see #4031's thread.
