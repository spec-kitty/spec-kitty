"""Landing fold (PR #4992): each ``_COMMAND_REGISTRARS`` key must register a
top-level command/group named exactly that key.

``register_commands()``'s lazy single-leaf path (WP05) looks up
``_COMMAND_REGISTRARS[single_leaf](app)`` by NAME and runs only that one
registrar. The correctness contract behind that lookup is: for every
``(name, registrar)`` pair in the table, running ``registrar`` on a fresh
``typer.Typer()`` yields a top-level command or group literally named
``name``.

Neither existing guard checks this. ``test_command_registrar_tables_cover_each_other.py``
only proves ``_COMMAND_REGISTRARS`` and ``_ALL_COMMAND_REGISTRARS`` reference
the same set of registrar FUNCTIONS -- it says nothing about whether a given
KEY's registrar actually registers something named that key. The full-app
fallback tests (e.g. ``--help`` listings, docs-parity, completion-manifest
freshness) all build the app with EVERY registrar applied via
``_ALL_COMMAND_REGISTRARS``, so a key pointed at the wrong registrar in
``_COMMAND_REGISTRARS`` would still produce a correct full command tree there
-- the desync would only break ``spec-kitty <name>`` through the lazy
single-leaf path, invisible to those tests.

Non-vacuity was proven by hand before this test was committed: temporarily
mutating a copy of the table so ``"doctor"`` pointed at ``_register_accept``
reproduced exactly the failure shape this test asserts against
(``('doctor', '_register_accept', ['accept'])``), confirming the test is not
vacuously green just because the table happens to be well-formed today.
"""

from __future__ import annotations

import click
import pytest
import typer
from typer.main import get_command

from specify_cli.cli.commands import _COMMAND_REGISTRARS

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _top_level_names_after_registering(registrar: object) -> set[str]:
    """Return the top-level command/group name(s) *registrar* installs on a
    fresh ``typer.Typer()``.

    A registrar that installs exactly one un-named command (e.g.
    ``app.command()(some_func)``) collapses to a single Click ``Command`` at
    ``get_command()`` time rather than a ``Group`` -- Typer's own behaviour
    when there is nothing to group -- so ``list_commands`` is unavailable and
    the single command's own resolved ``.name`` is the answer. A registrar
    that installs a sub-group (``app.add_typer(...)``) or several commands
    (e.g. the lifecycle/merge-driver registrars, which fan out to multiple
    keys) yields a real ``Group``, whose ``list_commands`` enumerates every
    installed name.
    """
    app = typer.Typer()
    registrar(app)  # type: ignore[operator]
    click_command = get_command(app)
    if hasattr(click_command, "list_commands"):
        ctx = click.Context(click_command, info_name=click_command.name)
        return set(click_command.list_commands(ctx))
    assert click_command.name is not None, "a registered top-level command must have a resolved name"
    return {click_command.name}


def test_command_registrar_table_is_non_empty() -> None:
    """Guards against this test suite going vacuously green if the table were
    ever emptied out from under it."""
    assert len(_COMMAND_REGISTRARS) > 10


@pytest.mark.parametrize("name", sorted(_COMMAND_REGISTRARS))
def test_command_registrar_registers_its_own_key(name: str) -> None:
    registrar = _COMMAND_REGISTRARS[name]
    registered = _top_level_names_after_registering(registrar)

    assert name in registered, (
        f"_COMMAND_REGISTRARS[{name!r}] = {registrar.__name__} does not register "
        f"a top-level command/group named {name!r} (registered: {sorted(registered)}) "
        f"-- the lazy single-leaf path `spec-kitty {name}` would resolve to the wrong command tree"
    )
