"""WP05 (#4417-deferred): lazy command-module imports in ``register_commands()``.

``register_commands()`` (``specify_cli/cli/commands/__init__.py``) used to
unconditionally import all ~50 command/group modules on every invocation not
already covered by the pre-existing ``next``/``live-work hook`` fast paths
(``_is_next_fast_path``/``_is_live_work_hook_fast_path``). This mission
generalizes that same argv-sniffing idiom into a lazy lookup keyed by the
invoked top-level command/group name (``_COMMAND_REGISTRARS``), so a
single-leaf-command invocation only imports the one module tree its invoked
command actually needs.

This proves the deferral mechanism itself -- that a command module does NOT
land in ``sys.modules`` until its command name appears in argv -- which is
not otherwise covered as a side effect of the existing CLI-contract suite
(that suite proves commands still *work*, not that unrelated modules stay
unimported). Modeled on the ``#4409``/``next``-fast-path precedent's own
self-mutation-testable style
(``tests/specify_cli/next/test_next_import_footprint.py``,
``test_next_fast_path_registers_only_next_command``): a fresh subprocess per
invocation, since module imports are cached process-wide and a single
process could not observe a second invocation's own deferred-import set.

**Non-vacuousness, proven at authoring time (WP05 T018 step 3):** every test
in this file was run against a deliberately-reverted, pre-fix copy of
``register_commands()`` (the unconditional-eager-import version this WP
replaces) and confirmed to fail there -- a single-leaf invocation pulled in
every command module, including the ones asserted absent below -- before
being confirmed to pass against the real lazy-lookup implementation.

**PR-TESTS-001 relocation (fix round):** moved here from
``tests/specify_cli/cli/test_lazy_command_imports.py`` -- a directory
``.github/ci-module-registry.yml``'s ``out_of_matrix_test_dirs`` names as an
accepted "``make test-full``-only" gap (the ``tests/specify_cli/cli`` entry,
"Accepted named gap: the residual behavioral files in this tree remain
``make test-full``-only"). No per-PR or nightly automation ever selected that
directory -- ``ci-router.yml``'s hardcoded ``tests-cli`` job runs
``pytest tests/cli -q`` (the literal top-level path, not the
``tests/specify_cli/cli`` mirror), and the diff-scoped per-PR matrix
(``.github/workflows/module-tests.yml`` via ``.github/ci-module-registry.yml``)
has no ``test_dirs`` override for the ``cli`` module, so it falls back to
the ``tests/{module}`` default -- ``tests/cli`` again. This file lives in
that top-level ``tests/cli/`` directory now, so BOTH authorities select it,
matching its structural sibling ``test_register_commands_lazy_import_shape.py``
(itself relocated here in WP06 for the identical reason). Renamed
(``test_lazy_command_module_imports.py``) so the two files never collide on
the old, no-longer-selected path.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"


def _run_register_commands(argv_tail: list[str]) -> set[str]:
    """Run ``register_commands()`` with the given argv tail in a fresh subprocess.

    Returns the set of ``specify_cli.cli.commands.*`` submodules present in
    ``sys.modules`` afterward.
    """
    script = (
        "import sys, typer\n"
        "from specify_cli.cli.commands import register_commands\n"
        f"sys.argv = ['spec-kitty'] + {argv_tail!r}\n"
        "app = typer.Typer()\n"
        "register_commands(app)\n"
        "mods = sorted(m for m in sys.modules if m.startswith('specify_cli.cli.commands.'))\n"
        "sys.stderr.write('MODS=' + repr(mods))\n"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_SRC)
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert result.returncode == 0, f"register_commands(argv_tail={argv_tail!r}) failed.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    marker = "MODS="
    idx = result.stderr.rindex(marker)
    mods_repr = result.stderr[idx + len(marker) :]
    mods: list[str] = ast.literal_eval(mods_repr)
    return set(mods)


def test_single_leaf_command_imports_only_its_own_module() -> None:
    """A single leaf-command invocation imports only that command's module.

    ``merge`` is a clean single-module probe: it is neither of the two
    pre-existing fast paths (``next``, ``live-work hook``), so this exercises
    WP05's new generalized lazy lookup, not the pre-existing idiom it
    deliberately leaves untouched.
    """
    mods = _run_register_commands(["merge", "--help"])
    assert mods == {"specify_cli.cli.commands.merge"}, f"`merge --help` imported unexpected command modules: {sorted(mods)}"


def test_a_second_unrelated_leaf_command_stays_isolated_too() -> None:
    """A second, unrelated leaf-command group proves the deferral generalizes.

    ``doctor`` legitimately pulls in a family of private ``_*`` helper
    submodules (that's the doctor group's own internal structure, not a
    lazy-lookup leak), but must not pull in any *other* top-level command
    module's own backing module.
    """
    mods = _run_register_commands(["doctor", "--help"])
    assert "specify_cli.cli.commands.doctor" in mods

    other_command_modules = {
        "specify_cli.cli.commands.merge",
        "specify_cli.cli.commands.merge_driver",
        "specify_cli.cli.commands.upgrade",
        "specify_cli.cli.commands.zeitgeist",
        "specify_cli.cli.commands.tracker",
        "specify_cli.cli.commands.charter",
    }
    assert not (other_command_modules & mods), f"`doctor --help` imported unrelated command modules: {sorted(other_command_modules & mods)}"


def test_module_backing_multiple_command_names_is_still_lazy() -> None:
    """A module backing several registered names (``merge_driver``) also defers.

    ``merge_driver`` backs six hidden ``merge-driver-*`` commands
    (many-to-one, same as the pre-existing module-to-command mapping); a
    single-leaf invocation of just one of those names must not pull in
    unrelated top-level modules like ``merge`` or ``doctor``.
    """
    mods = _run_register_commands(["merge-driver-meta", "BASE", "OURS", "THEIRS"])
    assert mods == {"specify_cli.cli.commands.merge_driver"}, f"`merge-driver-meta` imported unexpected command modules: {sorted(mods)}"


def test_top_level_help_still_imports_every_command_module() -> None:
    """The full command listing (bare ``--help``) must still see everything.

    A naive "only ever import the one matched command" implementation would
    break the top-level ``--help`` listing (WP05's own named risk). Bare
    ``--help`` does not cleanly resolve to one leaf command, so it must fall
    through to registering everything, exactly as before this WP.
    """
    mods = _run_register_commands(["--help"])
    for expected in (
        "specify_cli.cli.commands.doctor",
        "specify_cli.cli.commands.merge",
        "specify_cli.cli.commands.merge_driver",
        "specify_cli.cli.commands.zeitgeist",
        "specify_cli.cli.commands.charter",
        "specify_cli.cli.commands.retrospect",
    ):
        assert expected in mods, f"bare `--help` no longer imports {expected}: {sorted(mods)}"


def test_unrecognized_command_still_imports_every_command_module() -> None:
    """An unresolvable first token falls back to full registration.

    Typer's "no such command" error is reported against the full command
    set; a lazily-scoped registration would silently narrow the set that
    error (and its "did you mean" suggestions) is computed against.
    """
    mods = _run_register_commands(["not-a-real-command"])
    assert "specify_cli.cli.commands.doctor" in mods
    assert "specify_cli.cli.commands.merge" in mods


def test_next_and_live_work_hook_fast_paths_are_unchanged() -> None:
    """WP05 must not touch the two pre-existing fast paths' own behavior.

    Locks in that ``next``/``live-work hook`` still register only their own
    module, guarding against this WP's lookup table accidentally growing to
    include (and thus re-import) either of those two already-fast-pathed
    names.
    """
    next_mods = _run_register_commands(["next", "--help"])
    assert next_mods == {"specify_cli.cli.commands.next_cmd"}, sorted(next_mods)

    live_work_mods = _run_register_commands(["live-work", "hook", "claude"])
    assert live_work_mods == {"specify_cli.cli.commands.live_work"}, sorted(live_work_mods)
