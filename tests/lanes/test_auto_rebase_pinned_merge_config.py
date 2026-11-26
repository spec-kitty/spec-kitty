"""The auto-rebase tool merge runs under the pinned merge config (squad-3 A2).

``--incorporate`` runs its merge under ``merge_probe_env``: ``MERGE_PROBE_CONFIG_PINS`` override every
clone-level or environment config source, so a hostile ``merge.directoryRenames`` cannot change what git
computes. The auto-rebase merge is the other tool merge a verdict depends on (a recorded auto-rebase merge
is exempt from the FR-004 own-content check), so it runs under the same pins: a hostile config yields the
same outcome as no config at all (the behaviour ``--incorporate`` has), never a different merge.

The control pins that the pins change nothing for a repository without hostile config: the auto-rebase
merge's tree is the tree ``git merge-tree --write-tree`` computes with the default config.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.lanes.test_auto_rebase_record import _MISSION, _advance_mission, _clean_shape, _commit, _git, _init_repo, _lane_worktree, _rebase

pytestmark = pytest.mark.git_repo


def _directory_rename_shape(tmp_path: Path, *, hostile: str | None) -> tuple[Path, Path]:
    """The Mission branch renames ``olddir/`` to ``newdir/``; the lane adds ``olddir/b.py``.

    git's default (``merge.directoryRenames=conflict``) stops on a file-location conflict;
    ``merge.directoryRenames=true`` silently moves the lane's new file into ``newdir/``.
    """
    tmp_path.mkdir(parents=True)
    root = _init_repo(tmp_path)
    (root / "olddir").mkdir()
    _commit(root, "olddir/a.py", "a = 1\n", "seed olddir")
    _git(root, "branch", "-f", _MISSION, "main")
    worktree = _lane_worktree(root)
    _commit(worktree, "olddir/b.py", "b = 2\n", "lane: add olddir/b.py")
    _git(root, "checkout", "-q", _MISSION)
    _git(root, "mv", "olddir", "newdir")
    _git(root, "commit", "-q", "-m", "mission: rename olddir to newdir")
    _git(root, "checkout", "-q", "main")
    if hostile is not None:
        _git(root, "config", "merge.directoryRenames", hostile)
    return root, worktree


def _outcome(root: Path, worktree: Path) -> tuple[bool, str, list[str]]:
    before = _git(worktree, "rev-parse", "HEAD")
    report = _rebase(root, worktree)
    after = _git(worktree, "rev-parse", "HEAD")
    tree = _git(worktree, "ls-tree", "-r", "--name-only", "HEAD").splitlines()
    return report.succeeded, "moved" if after != before else "unmoved", tree


def test_hostile_directory_renames_config_does_not_change_the_tool_merge(tmp_path: Path) -> None:
    control = _outcome(*_directory_rename_shape(tmp_path / "control", hostile=None))
    hostile = _outcome(*_directory_rename_shape(tmp_path / "hostile", hostile="true"))

    assert hostile == control, f"a clone-level merge.directoryRenames changed the auto-rebase merge: {hostile} != {control}"
    assert "newdir/b.py" not in hostile[2], hostile


def test_hostile_config_through_the_environment_does_not_change_the_tool_merge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    control = _outcome(*_directory_rename_shape(tmp_path / "control", hostile=None))
    root, worktree = _directory_rename_shape(tmp_path / "hostile", hostile=None)
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "merge.directoryRenames")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "true")

    assert _outcome(root, worktree) == control


def test_pins_leave_a_normal_auto_rebase_merge_tree_unchanged(tmp_path: Path) -> None:
    """Control: without hostile config the pinned merge's tree is git's default merge tree."""
    root, worktree = _clean_shape(tmp_path)
    _advance_mission(root, "more.py", "m = 5\n")
    expected = _git(root, "merge-tree", "--write-tree", _git(worktree, "rev-parse", "HEAD"), _MISSION).splitlines()[0]

    report = _rebase(root, worktree)

    assert report.succeeded, report.halt_reason
    assert _git(worktree, "rev-parse", "HEAD^{tree}") == expected
