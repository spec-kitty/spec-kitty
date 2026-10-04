"""PR-BOUNDARY-002 (severity 2): asserts the ``_resolve_mission_dir_or_fail``
seam invariant directly, rather than restating it as a hardcoded call-site
count in a docstring.

That docstring has been wrong twice: an original "all 8 read endpoints"
undercount, then a "17 call sites" snapshot that itself undercounted the
true 19 (its own suggested verification grep,
``grep -c '_resolve_mission_dir_or_fail(cmd' commands.py``, self-matches its
own quoted text -- the docstring's literal example string contains the
pattern it tells the reader to grep for). A number in prose drifts silently
every time a verb is added or removed; this test cannot drift the same way
because it re-derives the call-site set from the live AST on every run and
fails the moment a mission-scoped endpoint stops routing through the seam.

The invariant: every command registered on ``orchestrator_api.commands.app``
that accepts a ``mission`` parameter -- i.e. every endpoint that reads an
EXISTING mission's directory -- calls ``_resolve_mission_dir_or_fail``
somewhere in its own body. The single documented exception is ``specify``,
which *creates* a mission rather than looking one up, so it legitimately
never resolves an existing mission dir through this seam.
"""

from __future__ import annotations

import ast
import inspect
import textwrap

import pytest

from specify_cli.orchestrator_api.commands import app

pytestmark = [pytest.mark.fast]

# ``specify`` mints a brand-new mission directory; it has nothing existing to
# resolve through ``_resolve_mission_dir_or_fail`` and is the one documented,
# deliberate exception to the invariant below.
_MISSION_CREATING_EXEMPT_COMMANDS = frozenset({"specify"})

_SEAM = "_resolve_mission_dir_or_fail"


def _calls_seam(node: ast.FunctionDef) -> bool:
    """True when the body calls the seam, bare or as ``_common.<seam>`` (#5628)."""
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        func = sub.func
        if isinstance(func, ast.Name) and func.id == _SEAM:
            return True
        if isinstance(func, ast.Attribute) and func.attr == _SEAM:
            return True
    return False


def _mission_scoped_app_commands() -> list[ast.FunctionDef]:
    """Every command registered on the live ``app`` that takes ``mission``.

    Discovery reads the registered callbacks, not one file's decorators, so
    the invariant follows a verb into whichever module defines it (#5628).
    """
    nodes: list[ast.FunctionDef] = []
    for info in app.registered_commands:
        callback = info.callback
        assert callback is not None
        if "mission" not in inspect.signature(callback).parameters:
            continue
        tree = ast.parse(textwrap.dedent(inspect.getsource(callback)))
        node = tree.body[0]
        assert isinstance(node, ast.FunctionDef)
        nodes.append(node)
    return nodes


def test_every_mission_scoped_endpoint_routes_through_the_seam() -> None:
    mission_scoped = _mission_scoped_app_commands()
    # Sanity: this must find a non-trivial number of endpoints, or the AST
    # walk itself is broken (e.g. the file moved) and the test is vacuously
    # passing on zero functions.
    assert len(mission_scoped) >= 10, f"expected several mission-scoped registered endpoints, found {len(mission_scoped)} -- the discovery walk is likely broken"

    missing = [node.name for node in mission_scoped if node.name not in _MISSION_CREATING_EXEMPT_COMMANDS and not _calls_seam(node)]
    assert missing == [], (
        "these mission-scoped orchestrator-api endpoints accept a `mission` "
        "parameter but do not call `_resolve_mission_dir_or_fail` anywhere "
        f"in their body: {missing}. Either route them through the seam or "
        "add them to `_MISSION_CREATING_EXEMPT_COMMANDS` with a one-line "
        "reason (mirroring `specify`, which mints a new mission rather than "
        "resolving an existing one)."
    )

    exempt_but_present = [name for name in _MISSION_CREATING_EXEMPT_COMMANDS if name not in {n.name for n in mission_scoped}]
    assert exempt_but_present == [], (
        f"exemption list names commands that no longer exist as mission-scoped registered endpoints: {exempt_but_present} -- prune the stale exemption"
    )
