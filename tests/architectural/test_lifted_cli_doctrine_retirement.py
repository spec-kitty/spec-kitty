"""Always-on regression gate: the ``spec-kitty doctrine`` group is gone.

The group was removed in mission ``charter-pack-cutover-01M491G6`` (#3732,
FR-007, C-001): every former leaf has a ``charter`` home (FR-006) and the old
spellings reach Typer's unknown-command path, exit 2, with no alias, hidden
stub or redirect. The pre-DRG curation subcommands (``curate``, ``promote``)
deleted in mission ``excise-doctrine-curation-and-inline-references-01KP54J6``
stay unknown as well.

This gate covers the group itself, every former leaf of the FR-006 table and
the two curation commands. Each path is invoked through the root app, so a
re-registered group (visible or hidden) makes it fail.
"""

from __future__ import annotations

import os

import pytest
from typer.testing import CliRunner

from specify_cli import app

pytestmark = [pytest.mark.architectural]

#: Typer's unknown-command message (the only output an old spelling gets).
_UNKNOWN_COMMAND = "No such command"

#: The group, its help and every former leaf (FR-006 table), plus the pre-DRG
#: curation commands. Arguments are realistic so a resurrected leaf would run.
_FORMER_SPELLINGS: tuple[tuple[str, ...], ...] = (
    ("doctrine",),
    ("doctrine", "--help"),
    ("doctrine", "fetch"),
    ("doctrine", "new", "tactic", "example-tactic"),
    ("doctrine", "validate"),
    ("doctrine", "org", "init", "org-pack"),
    ("doctrine", "org", "validate", "org-pack"),
    ("doctrine", "pack", "validate", "org-pack"),
    ("doctrine", "pack", "assemble", "out", "org-pack"),
    ("doctrine", "regenerate-graph", "--check"),
    ("doctrine", "asset", "list"),
    ("doctrine", "asset", "path", "common-docs-structural-lint"),
    ("doctrine", "mission-type", "list"),
    ("doctrine", "curate"),
    ("doctrine", "promote"),
)


@pytest.fixture(autouse=True)
def _pin_no_upgrade_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the upgrade-check opt-out set for every test (was a module-level ``setdefault``)."""
    monkeypatch.setenv("SPEC_KITTY_NO_UPGRADE_CHECK", os.environ.get("SPEC_KITTY_NO_UPGRADE_CHECK", "1"))


@pytest.mark.parametrize("argv", _FORMER_SPELLINGS, ids=" ".join)
def test_doctrine_group_is_unknown_command(argv: tuple[str, ...]) -> None:
    result = CliRunner().invoke(app, list(argv))
    assert result.exit_code == 2, result.output
    assert _UNKNOWN_COMMAND in result.output, result.output
    assert "'doctrine'" in result.output, result.output


def test_root_help_does_not_list_doctrine() -> None:
    """Control: the root app renders its help, and ``doctrine`` is not in it."""
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    assert "charter" in result.output
    assert "doctrine" not in result.output
