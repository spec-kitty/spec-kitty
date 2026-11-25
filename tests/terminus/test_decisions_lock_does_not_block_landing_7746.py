"""#7746 — the decisions runtime lock must not block ``consolidate``'s target advance.

The decisions lock (``kitty-specs/<mission>/decisions/index.json.lock``) stays
on disk, untracked and excluded, on purpose (#5925); no dirty-state gate may
refuse on it (#6628). In the repository-root checkout it can be the only file
of an ignored directory, so ``git status --ignored`` reports that directory as
one collapsed ``!!`` entry. When the landing brings tracked content into the
same directory (here the Mission's decisions index from its coordination
branch), the collapsed entry overlapped the target tree and ``consolidate``
refused to advance the target, although ``git reset --hard`` overwrites
nothing in it.

Drives the real ``spec-kitty consolidate`` against a real coordination Mission
(``tests/terminus`` harness, nothing stubbed).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.coordination.workspace import CoordinationWorkspace
from tests.terminus.conftest import _git, _git_out, build_coord_mission, run_terminus

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.slow]

_LOCK_EXCLUDE = "**/kitty-specs/*/decisions/index.json.lock"


def _exclude_path(repo: Path) -> Path:
    raw = Path(_git_out(repo, "rev-parse", "--git-path", "info/exclude"))
    return raw if raw.is_absolute() else repo / raw


@pytest.mark.regression
def test_consolidate_lands_past_a_lock_only_decisions_directory(tmp_path: Path) -> None:
    mission = build_coord_mission(tmp_path)
    decisions_rel = f"kitty-specs/{mission.slug}/decisions"

    # The coordination branch carries the Mission's committed decisions index.
    coord = CoordinationWorkspace.worktree_path(mission.repo, mission.slug, mission.mid8)
    (coord / decisions_rel).mkdir(parents=True, exist_ok=True)
    (coord / decisions_rel / "index.json").write_text('{"decisions": []}\n', encoding="utf-8")
    _git(coord, "add", "--", f"{decisions_rel}/index.json")
    _git(coord, "commit", "-qm", f"chore({mission.slug}): record decisions index")

    # The repository-root checkout holds only the persistent, excluded lock there.
    with _exclude_path(mission.repo).open("a", encoding="utf-8") as handle:
        handle.write(f"{_LOCK_EXCLUDE}\n")
    lock = mission.repo / decisions_rel / "index.json.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_bytes(b"")
    inode = lock.stat().st_ino
    assert f"!! {decisions_rel}/" in _git_out(mission.repo, "status", "--porcelain", "--ignored").splitlines()
    target_before = mission.rev(mission.target_branch)

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes", "--keep-branch", "--keep-worktree"])

    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "Refusing to advance branch" not in result.stdout + result.stderr
    assert mission.rev(mission.target_branch) != target_before
    assert _git_out(mission.repo, "show", f"{mission.target_branch}:{decisions_rel}/index.json") == '{"decisions": []}'
    assert lock.exists() and lock.stat().st_ino == inode
    assert lock.read_bytes() == b""
