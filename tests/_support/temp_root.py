"""Point the run's ``tempfile`` root under the basetemp, inside the harness ceiling (#7076).

``GIT_CEILING_DIRECTORIES`` (``tests/_support/git_ceiling.py``, #7022) only governs
directories **below** a listed entry. ``tempfile``'s root is the platform temp root —
``/tmp`` on this host — which is above every entry, so each directory a test makes with
``tempfile.TemporaryDirectory`` / ``mkdtemp`` (59 test modules do) sits outside the
harness's hermeticity boundary. Where the platform temp root has itself gained a stray
``.git`` (an agent sandbox that puts ``TMPDIR`` under a checkout, a shared ``/tmp``
someone ran ``git init`` in), those temporaries are *inside a foreign repository*: lock
paths resolve into its ``.git``, mission-state repair re-anchors on it and finds no
missions, and "not a repository" probes are never reached.

The fix is to make the run's temp root a directory *inside* the basetemp, which is
already a ceiling entry, and therefore inherits three things for free:

* the ceiling — everything ``tempfile`` makes is below it by construction;
* the run's lifecycle — ``run_basetemp`` wipes the tree per run and reaps it on success,
  so leaked temporaries are not a second cleanup problem (no second reaper, C-004);
* per-worker separation — every xdist worker owns its own ``popen-gwN`` basetemp.

Ordering is load-bearing, twice over:

1. This install must run **after** ``install_run_basetemp`` (which sets
   ``config.option.basetemp``) and **after** ``_worker_home_base`` has resolved, because
   that helper reads ``tempfile.gettempdir()`` and the worker's isolated home is meant to
   stay under the platform temp root, where ``git_ceiling`` lists it as its own entry.
2. pytest **removes and recreates** a *given* basetemp at first use
   (``_pytest.tmpdir.TempPathFactory.getbasetemp``: ``if basetemp.exists(): rm_rf(...)``),
   so a directory created only in ``pytest_configure`` is gone before the first test
   body. :func:`install_temp_root` creates it eagerly — collection and import time then
   see a real directory — and the autouse session fixture at the bottom of this module
   re-creates it immediately after the one and only reset. That guard is load-bearing, and
   its absence is **silent**: ``tempfile.gettempdir()`` validates each candidate and falls
   through to the next one when a directory is missing or unwritable, so a wiped temp root
   does not raise — it quietly puts every temporary back in the platform temp root, which
   is the bug this module exists to fix. Measured by removing the guard: the harness test
   then reports ``tempfile root /tmp is not below the run basetemp``.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any

import pytest

from tests._support.git_ceiling import GIT_CEILING_ENV

#: The directory name under the basetemp. Kept short: the basetemp path is already deep
#: (``…/spec-kitty-pytest-tmp/run-<pid>/<test-name>/``) and Windows still has a path
#: ceiling for some tools.
TEMP_ROOT_NAME = "tmp"

#: ``tempfile._candidate_tempdir_list`` reads ``TMPDIR`` first on **every** platform, so
#: that alone would move ``tempfile``. ``TEMP``/``TMP`` follow it because on Windows it is
#: those two that git and other child tools read — pointing all three at one root keeps
#: ``tempfile`` and every subprocess inside the same ceiling.
TEMP_ROOT_VARS = ("TMPDIR", "TEMP", "TMP")

#: Plugin name the guard fixture is registered under (one per process).
GUARD_PLUGIN_NAME = "spec-kitty-temp-root"


def temp_root_for(basetemp: str | Path | None) -> Path | None:
    """``<basetemp>/tmp``, or ``None`` when this run has no basetemp.

    Callers pass ``config.option.basetemp`` — the controller's run basetemp or, in an
    xdist worker, the per-worker ``popen-gwN`` directory — or a factory-resolved basetemp.
    Read per process, never cached in this module.
    """
    if not basetemp:
        return None
    return Path(basetemp) / TEMP_ROOT_NAME


def temp_root_dir(config: Any) -> Path | None:
    """This process's temp root, from a ``pytest.Config``-shaped object."""
    return temp_root_for(getattr(config.option, "basetemp", None))


def ensure_temp_root(root: Path) -> Path:
    """Create *root* if it is missing and return it (idempotent)."""
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


def install_temp_root(config: Any, environ: MutableMapping[str, str]) -> Path | None:
    """Point this process's ``tempfile`` root below the run's basetemp.

    Sets ``TMPDIR``/``TEMP``/``TMP``, creates the directory and resets
    ``tempfile.tempdir`` so the stdlib re-reads the environment instead of the value it
    cached the first time anything asked. A no-op when the run has no basetemp.

    Also registers :class:`_TempRootGuard`, the session fixture that re-creates the root
    after pytest's one basetemp reset. Registration (rather than a ``pytest_plugins``
    entry) keeps this module free of the "module already imported, cannot be rewritten"
    warning the plugin import path emits for a module ``tests/conftest.py`` imports first.
    """
    root = temp_root_dir(config)
    if root is None:
        return None
    ensure_temp_root(root)
    for variable in TEMP_ROOT_VARS:
        environ[variable] = str(root)
    # ``tempfile`` caches the resolved root in a module global; without this reset the new
    # variables are ignored for the rest of the process.
    tempfile.tempdir = None
    _register_guard(config, root)
    return root


def harness_env(environ: MutableMapping[str, str] | None = None) -> dict[str, str]:
    """The harness-owned variables a from-scratch child environment must inherit.

    Child environments built from an allowlist (``tests/upgrade/preview_support``), or
    copied and stripped of ``GIT_*`` (three git helpers and one fixture), otherwise lose
    the harness boundary and let the child's git and root walks climb out of the test's
    tree. Only these are returned: the ceiling and the temp-root triple. Credentials,
    repository selectors and git config stay the caller's business, exactly as the strips
    intend.
    """
    source = os.environ if environ is None else environ
    names = (GIT_CEILING_ENV, *TEMP_ROOT_VARS)
    return {name: source[name] for name in names if name in source}


class _TempRootGuard:
    """Re-create the run's temp root once pytest has removed and recreated the basetemp.

    ``getbasetemp()`` is what performs the single reset (see this module's docstring), so
    resolving it here and creating the root immediately after closes the only window in
    which ``TMPDIR`` points at a missing directory. Session-scoped and autouse, so this
    runs once per process, before any test body, and costs one ``mkdir`` (NFR-002).
    """

    def __init__(self, root: Path) -> None:
        self._root = root

    @pytest.fixture(scope="session", autouse=True)
    def _reinstall_temp_root(self, tmp_path_factory: pytest.TempPathFactory) -> None:
        tmp_path_factory.getbasetemp()  # this call is the one reset
        ensure_temp_root(self._root)


def _register_guard(config: Any, root: Path) -> None:
    """Register :class:`_TempRootGuard` on *config* once."""
    pluginmanager = getattr(config, "pluginmanager", None)
    if pluginmanager is None:
        return  # a bare stub config (unit tests): the env install is all that is asked for
    if pluginmanager.has_plugin(GUARD_PLUGIN_NAME):
        return
    pluginmanager.register(_TempRootGuard(root), GUARD_PLUGIN_NAME)
