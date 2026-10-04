"""Opt-in working-directory isolation for the charter write commands (#5317).

The charter commands ``generate``, ``synthesize`` and ``resynthesize`` resolve
their write root with ``resolve_charter_write_root(Path.cwd())``. That guard
probes the **process working directory** and refuses when it is a linked
worktree. A test that aims a command at a **test tmp project** by patching
``specify_cli.cli.commands.charter.find_repo_root`` does not move the process
working directory, so the guard still sees the checkout pytest was started
from. Started from a linked worktree (a Spec Kitty lane worktree), the command
refuses and the test fails for a reason unrelated to what it exercises.

``charter_cwd_isolation`` is the one owner of the fix. It points both the
process working directory and the command's repository-root lookup at the same
test tmp project. It is opt-in: a test that needs the repository root checkout
it was started from simply does not request it.

The real guard still runs. Nothing here patches, wraps or replaces
``resolve_charter_write_root``, so a test that later moves the process working
directory into a linked worktree is still refused.

This module is a pytest plugin, registered by the root ``tests/conftest.py``
through ``pytest_plugins``.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

#: Dotted name the charter command modules resolve ``find_repo_root`` through at call time.
CHARTER_FIND_REPO_ROOT = "specify_cli.cli.commands.charter.find_repo_root"


def _point_charter_commands_at(root: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Make ``root`` both the process working directory and the repository root lookup.

    The only place the isolation is applied; the ``charter_cwd_isolation``
    fixture delegates here. Private on purpose: a test file that called it
    directly would bypass the fixture, and with it the one definition (C-004)
    and the fixture-owned teardown. Every change goes through ``monkeypatch``, so the
    caller's teardown undoes it. Returns ``root``.
    """
    monkeypatch.chdir(root)
    monkeypatch.setattr(CHARTER_FIND_REPO_ROOT, lambda *args, **kwargs: root)
    return root


@pytest.fixture
def charter_cwd_isolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[..., Path]:
    """Return ``isolate(project_root=None) -> Path`` for a charter command test.

    Calling ``isolate`` changes the process working directory to ``project_root``
    (default: the test's ``tmp_path``) and makes the charter command package's
    ``find_repo_root`` return that same directory. It returns the root it used.
    Both changes are undone at test teardown.

    ``project_root`` should be a test tmp project that is not a linked worktree.
    A test's own later ``patch`` of ``find_repo_root`` still takes precedence.

    ``activate`` and ``deactivate`` resolve their root from ``--repo-root``, which
    defaults to ``.``, so the working-directory change is what aims them at the
    test tmp project. A command that binds ``find_repo_root`` at import (for
    example ``charter preflight``, ``specify_cli/charter_runtime/preflight/cli.py``)
    does not read the patched package-level name, so for it only the working-directory
    change takes effect.
    """

    def isolate(project_root: Path | None = None) -> Path:
        return _point_charter_commands_at(tmp_path if project_root is None else project_root, monkeypatch)

    return isolate
