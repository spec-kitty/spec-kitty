"""``GIT_CEILING_DIRECTORIES`` is the one boundary for the two root walks (#7076).

Both walks already honour git's discovery ceiling (#7022), and #7056 moved every other
walk in ``src/`` onto the same reader. ``stop=`` was the second, parallel boundary: a
keyword only tests passed, with its own semantics to keep in sync with the ceiling, and
no coverage the ceiling does not already give — git's ceiling bounds child processes too.
#7076 retired it, so a caller cannot bound a walk with a mechanism the production code no
longer reads.

The behavioural guards reject the retired caller-supplied boundary and preserve the
ceiling itself. One same-fixture control proves both directions: a directory below a
ceiling resolves to no project, and a project at the ceiling directory still resolves.
No signature representation is pinned.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.core.paths import locate_project_root
from specify_cli.task_utils.support import TaskCliError, find_repo_root
from tests._support.git_ceiling import GIT_CEILING_ENV

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.mark.parametrize("walk", [locate_project_root, find_repo_root], ids=["locate", "find_repo"])
def test_passing_stop_is_a_type_error(walk: object, tmp_path: Path) -> None:
    """A caller that still passes the retired boundary fails loudly rather than silently."""
    with pytest.raises(TypeError, match="stop"):
        walk(tmp_path, stop=tmp_path)


def test_a_ceiling_dir_is_examined_and_nothing_above_it_is(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Same fixture, two verdicts: the ceiling is the last directory examined."""
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    jail = tmp_path / "jail"
    (jail / "child" / "grandchild").mkdir(parents=True)
    monkeypatch.setenv(GIT_CEILING_ENV, str(jail))

    # Nothing at or below the ceiling is a project...
    assert locate_project_root(jail / "child" / "grandchild") is None
    with pytest.raises(TaskCliError, match="Unable to locate repository root"):
        find_repo_root(jail / "child" / "grandchild")

    # ...and the ceiling directory itself is still examined, so a project there is found.
    (jail / ".kittify").mkdir()
    assert locate_project_root(jail / "child" / "grandchild") == jail
    assert find_repo_root(jail / "child" / "grandchild") == jail
