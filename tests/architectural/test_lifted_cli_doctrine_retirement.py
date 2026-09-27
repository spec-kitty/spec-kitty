"""Always-on regression gate: retired ``doctrine curate``/``doctrine promote``.

Lifted from ``tests/specify_cli/cli/test_doctrine_cli_removed.py``, whose
directory (``tests/specify_cli/cli``) is recorded ``out_of_matrix`` in
``.github/ci-module-registry.yml`` — no per-PR lane selects it (#4374, #4479).

The pre-DRG curation subcommands (``curate``, ``promote``) deleted in mission
``excise-doctrine-curation-and-inline-references-01KP54J6`` must stay
unregistered; the ``doctrine`` parent group itself must stay registered — it
now carries the DRG-era org-layer authoring commands.
"""

from __future__ import annotations

import os

import pytest
from typer.testing import CliRunner

from specify_cli import app

pytestmark = [pytest.mark.architectural]


@pytest.fixture(autouse=True)
def _pin_no_upgrade_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the upgrade-check opt-out set for every test (was a module-level ``setdefault``)."""
    monkeypatch.setenv("SPEC_KITTY_NO_UPGRADE_CHECK", os.environ.get("SPEC_KITTY_NO_UPGRADE_CHECK", "1"))


def test_doctrine_curate_is_unknown_command() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["doctrine", "curate"])
    assert result.exit_code != 0


def test_doctrine_promote_is_unknown_command() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["doctrine", "promote"])
    assert result.exit_code != 0


def test_doctrine_group_is_registered() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["doctrine", "--help"])
    assert result.exit_code == 0
