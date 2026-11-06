"""``GIT_CEILING_DIRECTORIES`` is the one boundary for the two root walks (#7076).

Both walks already honour git's discovery ceiling (#7022), and #7056 moved the other
parent-enumerating walks in ``src/`` onto the same reader. ``stop=`` was the second, parallel boundary: a
keyword only tests passed, with its own semantics to keep in sync with the ceiling, and
no coverage the ceiling does not already give — git's ceiling bounds child processes too.
#7076 retired it, so a caller cannot bound a walk with a mechanism the production code no
longer reads.

The behavioural guard rejects the retired caller-supplied boundary. The control keeps
the inclusive ceiling: ``find_repo_root`` still finds a project at the ceiling directory
itself. Above-ceiling exclusion stays with the core caller's actual ambient-marker test;
``locate_project_root``'s stronger negative and inclusive cases stay in
``tests/specify_cli/core/test_paths.py``. No signature representation is pinned.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.core.paths import locate_project_root
from specify_cli.task_utils.support import find_repo_root
from tests._support.git_ceiling import GIT_CEILING_ENV

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.mark.parametrize("walk", [locate_project_root, find_repo_root], ids=["locate", "find_repo"])
def test_passing_stop_is_a_type_error(walk: object, tmp_path: Path) -> None:
    """A caller that still passes the retired boundary fails loudly rather than silently."""
    with pytest.raises(TypeError, match="stop"):
        walk(tmp_path, stop=tmp_path)


def test_a_project_at_the_ceiling_directory_is_still_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The ceiling directory is examined, so a project there is found rather than skipped."""
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    jail = tmp_path / "jail"
    (jail / "child" / "grandchild").mkdir(parents=True)
    (jail / ".kittify").mkdir()
    monkeypatch.setenv(GIT_CEILING_ENV, str(jail))

    assert find_repo_root(jail / "child" / "grandchild") == jail
