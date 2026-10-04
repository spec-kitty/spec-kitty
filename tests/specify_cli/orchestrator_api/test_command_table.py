"""Pins the orchestrator-api verb order and each verb's owning module (#5628).

``commands.py`` is the façade: it owns the Typer ``app`` and registers every
verb, in contract order, from its command table. The handlers live in
per-concern modules. These tests keep both facts explicit: a reordered
``--help`` or a verb drifting into another concern module fails here first.
"""

from __future__ import annotations

import pytest

from specify_cli.orchestrator_api import commands
from specify_cli.orchestrator_api.commands import app

pytestmark = [pytest.mark.fast]

_PKG = "specify_cli.orchestrator_api"

#: Contract order of the verbs (the order ``--help`` lists them in) and the
#: module that defines each handler.
_EXPECTED: tuple[tuple[str, str], ...] = (
    ("contract-version", "commands"),
    ("mission-state", "commands"),
    ("list-ready", "commands"),
    ("resolve-workspace", "wp_lifecycle"),
    ("start-implementation", "wp_lifecycle"),
    ("start-review", "wp_lifecycle"),
    ("transition", "wp_lifecycle"),
    ("append-history", "wp_lifecycle"),
    ("accept-mission", "consolidation"),
    ("consolidate-mission", "consolidation"),
    ("specify", "design_phase"),
    ("plan", "design_phase"),
    ("tasks", "design_phase"),
    ("check-prerequisites", "design_phase"),
    ("record-analysis", "design_phase"),
    ("open-decision", "decision_verbs"),
    ("resolve-decision", "decision_verbs"),
    ("defer-decision", "decision_verbs"),
    ("cancel-decision", "decision_verbs"),
    ("answer-decision", "decision_verbs"),
    ("design-status", "design_status"),
)


def _registered() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for info in app.registered_commands:
        assert info.name is not None
        assert info.callback is not None
        rows.append((info.name, info.callback.__module__.removeprefix(f"{_PKG}.")))
    return rows


def test_verbs_register_in_contract_order_from_their_concern_modules() -> None:
    assert _registered() == list(_EXPECTED)


def test_command_table_holds_every_verb_defined_outside_the_facade() -> None:
    table_names = [name for name, _handler in commands._COMMAND_TABLE]
    outside_facade = [name for name, module in _EXPECTED if module != "commands"]
    assert table_names == outside_facade


def test_each_verb_is_registered_once() -> None:
    names = [name for name, _module in _registered()]
    assert len(names) == len(set(names))
