"""The non-git status-lock fallback never creates a project or repository marker (#6367).

Taking a status lock in a bare non-git tree used to create ``<root>/.kittify``,
the project marker ``locate_project_root`` walks up for. Every later walk from
below that root then found a project that does not exist: in the nightly, a
finalize test that locked on the shared pytest basetemp turned every sibling
test's ``tmp_path`` into the inside of a "project". These tests pin the
fallback's three branches and, end to end, that a walk from below a locked bare
tree still finds no project.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.core.paths import locate_project_root
from specify_cli.status.locking import feature_status_lock, feature_status_lock_path, project_event_log_lock
from specify_cli.status.mission_write import mission_write_lock

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_KEY = "001-mission"


def test_bare_tree_locks_under_a_non_marker_home(tmp_path: Path) -> None:
    lock_path = feature_status_lock_path(tmp_path, _KEY)
    assert lock_path == tmp_path / ".spec-kitty" / "spec-kitty-locks" / f"{_KEY}.status.lock"
    with feature_status_lock(tmp_path, _KEY, timeout=2), project_event_log_lock(tmp_path, timeout=2):
        pass
    assert not (tmp_path / ".kittify").exists()
    assert not (tmp_path / ".git").exists()


def test_existing_kittify_keeps_its_lock_location(tmp_path: Path) -> None:
    (tmp_path / ".kittify").mkdir()
    assert feature_status_lock_path(tmp_path, _KEY) == tmp_path / ".kittify" / "spec-kitty-locks" / f"{_KEY}.status.lock"
    assert not (tmp_path / ".spec-kitty").exists()


def test_existing_dot_git_dir_keeps_its_lock_location(tmp_path: Path) -> None:
    # A ``.git`` directory the git probe cannot resolve (no HEAD): the historical location stays.
    (tmp_path / ".git").mkdir()
    assert feature_status_lock_path(tmp_path, _KEY) == tmp_path / ".git" / "spec-kitty-locks" / f"{_KEY}.status.lock"


def test_mission_write_lock_on_a_bare_dir_leaves_no_project_for_its_children(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The #6367 path: a mission write lock anchored on a dir not under ``kitty-specs/``.

    ``resolve_status_lock_root`` uses such a directory itself as the lock root, so the
    lock lands on whatever directory the caller named (in #6367, the shared basetemp).
    """
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    shared = tmp_path / "shared"
    child = shared / "sibling-test"
    child.mkdir(parents=True)
    with mission_write_lock(shared):
        pass
    assert not (shared / ".kittify").exists()
    assert locate_project_root(child, stop=tmp_path) is None
