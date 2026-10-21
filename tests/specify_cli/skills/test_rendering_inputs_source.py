"""``rendering_inputs`` learns the activation source from the resolver only (WP04, carry-forward L5).

Strict (swept): rendering identity needs the source, never the activation
values, so a malformed value in the ledger does not raise there; the ledger
path is still the rendering authority.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.activation_ledger_store import activation_ledger_path
from specify_cli.skills.command_renderer import rendering_inputs

pytestmark = [pytest.mark.fast]


def test_a_non_list_ledger_value_does_not_raise_in_rendering_identity(tmp_path: Path) -> None:
    (tmp_path / ".kittify" / "charter").mkdir(parents=True)
    (tmp_path / ".kittify" / "config.yaml").write_text("{}\n", encoding="utf-8")
    activation_ledger_path(tmp_path).write_text("activated_tactics: not-a-list\n", encoding="utf-8")

    assert rendering_inputs(tmp_path)[-1] == activation_ledger_path(tmp_path)


def test_a_fresh_project_renders_against_the_ledger_path(tmp_path: Path) -> None:
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text("{}\n", encoding="utf-8")

    assert rendering_inputs(tmp_path) == (tmp_path / ".kittify" / "config.yaml", activation_ledger_path(tmp_path))
