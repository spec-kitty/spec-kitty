"""Guard: ``tests/status/`` stays hermetic against an ambient ancestor ``.git``.

Issue #142: lifecycle/status writers resolve their lock root by climbing from
the log path to the nearest ``.git`` (``resolve_canonical_root`` →
``_repo_root_for_lifecycle_log`` → ``feature_status_lock``), then ``mkdir``
``<root>/.git/spec-kitty-locks/``. Mission fixtures here build feature
directories under plain ``tmp_path`` without a repo, so on any host where an
ancestor of basetemp is itself a git checkout the lock lands in *that*
checkout — and when it is read-only, :func:`append_lifecycle_event` swallows
the ``PermissionError`` and silently persists nothing (130 nodes red in the
#142 repro on main ``8321594a``).

The original fix was an autouse fixture in this package's conftest that ran
``git init`` in every ``tmp_path`` whose resolution escaped. #7022 replaced it
with one run-wide authority: the root conftest makes the run's basetemp a
``GIT_CEILING_DIRECTORIES`` entry (``tests/_support/git_ceiling.py``), which
git and both root walks of ``specify_cli.core.paths`` honor, so resolution
never escapes in the first place. The end-to-end repro below keeps that
guarantee pinned for this package: a child pytest run with a read-only
``.git`` planted above its ``--basetemp`` must still record events.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest


pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]

#: A compact status-transition node whose assertions depend on lifecycle
#: persistence -- one of the nodes the #142 repro turned red. If it moves,
#: point this at another append-dependent node in this package.
_REPRESENTATIVE_NODE = "tests/status/test_emit.py::TestEmitStatusTransition::test_happy_path_planned_to_claimed"


def _git_init(path: Path) -> None:
    subprocess.run(
        ["git", "init", "-q", "-b", "main"],
        cwd=path,
        capture_output=True,
        check=True,
    )


@contextmanager
def _read_only_ancestor_git(host: Path) -> Iterator[Path]:
    """Turn *host* into a git checkout whose ``.git`` is read-only.

    Yields the ``.git`` path; restores write bits afterwards so pytest's
    tmp-path cleanup can remove the tree even though the sandbox lives below
    a directory root that mode bits protect.
    """
    git_dir = host / ".git"
    _git_init(host)
    for path in (git_dir, *git_dir.rglob("*")):
        path.chmod(0o755 if path.is_dir() else 0o644)
    git_dir.chmod(0o555)
    try:
        yield git_dir
    finally:
        for path in (git_dir, *git_dir.rglob("*")):
            path.chmod(0o755 if path.is_dir() else 0o644)


@pytest.mark.skipif(
    os.geteuid() == 0,
    reason="root ignores mode bits, so a read-only ancestor .git cannot be simulated",
)
def test_suite_records_events_under_read_only_ancestor_git(tmp_path: Path) -> None:
    """End-to-end #142 repro: read-only `.git` above `--basetemp` must not
    silence event recording anywhere in this package."""
    host = tmp_path / "host"
    host.mkdir()
    child_basetemp = host / "basetemp"
    child_basetemp.mkdir()
    with _read_only_ancestor_git(host):
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                _REPRESENTATIVE_NODE,
                "-q",
                "--basetemp",
                str(child_basetemp),
                "-p",
                "no:cacheprovider",
            ],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
            env={**os.environ, "PWHEADLESS": "1"},
            check=False,
        )
    assert completed.returncode == 0, (
        f"representative node failed under a read-only ancestor .git; the harness git ceiling did not keep resolution inside the sandbox:\n{completed.stdout}"
    )
