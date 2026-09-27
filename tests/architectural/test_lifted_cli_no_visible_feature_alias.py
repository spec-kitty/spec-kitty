"""Always-on freshness gate: the retired ``--feature`` alias never resurfaces.

Lifted from ``tests/specify_cli/cli/test_no_visible_feature_alias.py``, whose
directory (``tests/specify_cli/cli``) is recorded ``out_of_matrix`` in
``.github/ci-module-registry.yml`` — no per-PR lane selects it (#4374, #4479).

Terminology Canon prohibits ``feature*`` aliases for the Mission domain
object. FR-006/FR-009 (mission ``feature-alias-removal-01KW0N87``) removed
every ``--feature`` CLI flag; this gate pins that it stays removed: zero
``--feature`` options anywhere in the live Typer/Click command tree, and
(defensively) any that ever reappear must at least be hidden from rendered
help.
"""

from __future__ import annotations

import os

import click
import pytest
from typer.main import get_command

from specify_cli import app as _typer_app

pytestmark = [pytest.mark.architectural]

cli: click.Group = get_command(_typer_app)  # type: ignore[assignment]


@pytest.fixture(autouse=True)
def _pin_no_upgrade_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the upgrade-check opt-out set for every test (was a module-level ``setdefault``)."""
    monkeypatch.setenv("SPEC_KITTY_NO_UPGRADE_CHECK", os.environ.get("SPEC_KITTY_NO_UPGRADE_CHECK", "1"))


def _walk_leaf_commands(group: click.Group, prefix: tuple[str, ...] = ()):
    for name, cmd in group.commands.items():
        path = prefix + (name,)
        if isinstance(cmd, click.Group):
            yield from _walk_leaf_commands(cmd, path)
        else:
            yield path, cmd


def _param_declares_feature_flag(param: click.Parameter) -> bool:
    declared = list(getattr(param, "opts", []) or []) + list(getattr(param, "secondary_opts", []) or [])
    return "--feature" in declared


def test_zero_feature_flags_exist_cli_wide() -> None:
    feature_options: list[str] = []
    for path, cmd in _walk_leaf_commands(cli):
        for param in cmd.params:
            if _param_declares_feature_flag(param):
                feature_options.append(" ".join(path))
    assert feature_options == [], (
        f"Found {len(feature_options)} '--feature' option(s) in CLI tree on "
        f"command(s): {feature_options}. All --feature aliases must be removed "
        "(Terminology Canon / FR-009)."
    )


def test_any_surviving_feature_flag_would_be_hidden() -> None:
    offenders: list[str] = []
    for path, cmd in _walk_leaf_commands(cli):
        for param in cmd.params:
            if _param_declares_feature_flag(param) and not getattr(param, "hidden", False):
                offenders.append(" ".join(path))
    assert not offenders, "--feature flag is visible on these commands (must be hidden=True):\n  " + "\n  ".join(offenders)
