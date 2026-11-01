"""Make the test run's own temp roots a git ceiling (#7022, #5356).

Many fixtures build a project in ``tmp_path`` without ``git init`` and rely on
it being outside every repository. That holds only while the platform temp
root is outside every git work tree. When it is not (an agent sandbox that
puts ``TMPDIR`` under a checkout, a ``/tmp`` someone ran ``git init`` in),
git discovery climbs from ``tmp_path`` into the foreign repository: lock paths
resolve into its ``.git``, mission-state repair re-anchors on it and finds no
missions, non-repository probes are never reached. ``make test-fast`` went red
on such hosts while CI, whose ``/tmp`` has no enclosing repository, stayed
green.

The cure is git's own mechanism: ``GIT_CEILING_DIRECTORIES``. Listing a
directory there stops discovery from climbing above it, for git itself and for
both root walks of :mod:`specify_cli.core.paths` (``locate_project_root`` and
``resolve_canonical_root``), which honor the same variable. ``tests/conftest.py`` installs the roots this harness owns -- the
run's basetemp and the worker's isolated home base -- once per process from
``pytest_configure``, before collection, so every test, xdist worker and
spawned subprocess inherits it. A repository a test creates *inside* its own
``tmp_path`` is below the ceiling and is still found.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, MutableMapping
from pathlib import Path
from typing import Any

#: The variable git (and ``specify_cli.core.paths``) reads for discovery ceilings.
GIT_CEILING_ENV = "GIT_CEILING_DIRECTORIES"


def harness_git_ceilings(config: Any, home_base: Path) -> list[Path]:
    """The directories this harness owns and discovery must never climb above.

    ``config.option.basetemp`` is the run's private basetemp (set by
    ``install_run_basetemp``, an explicit ``--basetemp``, or the per-worker
    ``popen-gwN`` dir xdist hands a worker); ``home_base`` is the worker's
    isolated home. Paths are resolved so a symlinked temp root (``/tmp`` on
    macOS) matches what git compares against.
    """
    ceilings: list[Path] = []
    basetemp = getattr(config.option, "basetemp", None)
    if basetemp:
        ceilings.append(Path(basetemp).resolve())
    ceilings.append(home_base.resolve())
    return ceilings


def install_git_ceilings(dirs: Iterable[Path], environ: MutableMapping[str, str]) -> None:
    """Append *dirs* to ``GIT_CEILING_DIRECTORIES`` in *environ*, idempotently.

    An existing value is kept verbatim and only appended to: a leading empty
    entry is meaningful to git (later entries skip ``realpath``), so the value
    is never re-parsed into a normalised form.
    """
    current = environ.get(GIT_CEILING_ENV, "")
    listed = set(current.split(os.pathsep)) if current else set()
    value = current
    for directory in dirs:
        entry = str(directory)
        if entry in listed:
            continue
        listed.add(entry)
        value = f"{value}{os.pathsep}{entry}" if value else entry
    environ[GIT_CEILING_ENV] = value
