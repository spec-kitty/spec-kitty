"""Successor plumbing for the residue-safe migrations (#6669, WP02).

Covers the registry's ``settled_in_selection_view`` (one predicate shared with
``get_applicable``) and the private ``_residue_successor`` helpers.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kernel.git import GitCommandError
from specify_cli.context.mission_resolver import residue_notice, residue_notice_path
from specify_cli.upgrade.ledger import MigrationLedger, build_record
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.migrations._residue_successor import (
    partition_kitty_specs,
    residue_warnings,
)
from specify_cli.upgrade.registry import MigrationRegistry, settled_in_selection_view

pytestmark = [pytest.mark.unit, pytest.mark.fast]

#: A real, registered, tracked migration whose target (3.1.1) sits between the pre-ledger versions below.
_MIGRATION_ID = "3.1.1_charter_rename"
_TARGET = "99.0.0"

_PRE_LEDGER_METADATA = """spec_kitty:
  version: {version}
  initialized_at: '2026-01-01T00:00:00+00:00'
  last_upgraded_at: null
environment:
  python_version: ''
  platform: ''
  platform_version: ''
migrations:
  applied: []
"""


@pytest.fixture(autouse=True)
def _discovered() -> None:
    auto_discover_migrations()


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """A git repository with one committed Mission under ``kitty-specs/``."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    mission = tmp_path / "kitty-specs" / "real-mission"
    mission.mkdir(parents=True)
    (mission / "spec.md").write_text("# spec\n", encoding="utf-8")
    (mission / "meta.json").write_text('{"mission_id": "01ABCDEFGHJKMNPQRSTVWXYZ00"}', encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def _selected_ids(project: Path) -> set[str]:
    return {m.migration_id for m in MigrationRegistry.get_applicable("0.0.0", _TARGET, project_path=project)}


def _record(project: Path, result: str) -> None:
    migration = MigrationRegistry.get_by_id(_MIGRATION_ID)
    assert migration is not None
    MigrationLedger(project).append(build_record(migration, result))


@pytest.mark.parametrize("state", [None, "success", "skipped", "failed"])
def test_settled_view_equals_selection_for_each_ledger_state(tmp_path: Path, state: str | None) -> None:
    (tmp_path / ".kittify").mkdir()
    if state is not None:
        _record(tmp_path, state)
    expected = _MIGRATION_ID not in _selected_ids(tmp_path)
    assert settled_in_selection_view(tmp_path, _MIGRATION_ID) is expected
    assert expected is (state == "success")


@pytest.mark.parametrize(("version", "settled"), [("2.0.6", False), ("3.2.0", True)])
def test_settled_view_equals_selection_for_pre_ledger_adoption(tmp_path: Path, version: str, settled: bool) -> None:
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "metadata.yaml").write_text(_PRE_LEDGER_METADATA.format(version=version), encoding="utf-8")
    expected = _MIGRATION_ID not in _selected_ids(tmp_path)
    assert settled_in_selection_view(tmp_path, _MIGRATION_ID) is expected
    assert expected is settled


def test_unknown_migration_id_is_not_settled(tmp_path: Path) -> None:
    (tmp_path / ".kittify").mkdir()
    assert settled_in_selection_view(tmp_path, "no_such_migration_6669") is False


def test_partition_splits_mission_from_residue_in_a_tracked_project(git_repo: Path) -> None:
    residue = git_repo / "kitty-specs" / "leftover" / "tasks"
    residue.mkdir(parents=True)
    (residue / "WP01.md").write_text("x", encoding="utf-8")
    (git_repo / "kitty-specs" / "stray.lock").write_text("", encoding="utf-8")

    missions, leftovers = partition_kitty_specs(git_repo / "kitty-specs", git_repo)

    assert missions == [git_repo / "kitty-specs" / "real-mission"]
    assert leftovers == [git_repo / "kitty-specs" / "leftover"]


def test_partition_tasks_only_folder_is_a_mission_without_git(tmp_path: Path) -> None:
    tasks = tmp_path / "kitty-specs" / "legacy" / "tasks"
    tasks.mkdir(parents=True)
    (tasks / "WP01.md").write_text("x", encoding="utf-8")
    empty = tmp_path / "kitty-specs" / "empty"
    empty.mkdir()

    missions, leftovers = partition_kitty_specs(tmp_path / "kitty-specs", tmp_path)

    assert missions == [tmp_path / "kitty-specs" / "legacy"]
    assert leftovers == [empty]


def _corrupt_index(monkeypatch: pytest.MonkeyPatch, cwd: Path, *, timed_out: bool) -> None:
    def _raise(_root: Path) -> frozenset[str]:
        raise GitCommandError(argv=("ls-files",), cwd=cwd, returncode=128, stderr="corrupt index", timed_out=timed_out)

    monkeypatch.setattr("specify_cli.context.mission_resolver.tracked_mission_paths", _raise)


def test_partition_degrades_to_file_presence_on_a_non_timeout_git_error(git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tasks = git_repo / "kitty-specs" / "legacy" / "tasks"
    tasks.mkdir(parents=True)
    (tasks / "WP01.md").write_text("x", encoding="utf-8")
    # Tracked mode (the probe works) reads the untracked tasks-only folder as residue.
    assert git_repo / "kitty-specs" / "legacy" in partition_kitty_specs(git_repo / "kitty-specs", git_repo)[1]

    _corrupt_index(monkeypatch, git_repo, timed_out=False)
    missions, leftovers = partition_kitty_specs(git_repo / "kitty-specs", git_repo)

    assert git_repo / "kitty-specs" / "legacy" in missions
    assert leftovers == []


def test_partition_reraises_a_git_timeout(git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _corrupt_index(monkeypatch, git_repo, timed_out=True)
    with pytest.raises(GitCommandError):
        partition_kitty_specs(git_repo / "kitty-specs", git_repo)


def test_partition_for_a_worktree_checkout_root(git_repo: Path) -> None:
    """WP03 shape: ``partition_kitty_specs(<wt>/kitty-specs, <wt>)`` for ``.worktrees/*``."""
    wt = git_repo / ".worktrees" / "wt1"
    _git(git_repo, "worktree", "add", "-q", "-b", "wt1-branch", str(wt))
    leftover = wt / "kitty-specs" / "leftover" / "tasks"
    leftover.mkdir(parents=True)
    (leftover / "WP01.md").write_text("x", encoding="utf-8")

    missions, residue = partition_kitty_specs(wt / "kitty-specs", wt)

    assert missions == [wt / "kitty-specs" / "real-mission"]
    assert residue == [wt / "kitty-specs" / "leftover"]
    assert [residue_notice_path(w) for w in residue_warnings(residue, git_repo)] == [".worktrees/wt1/kitty-specs/leftover"]


def test_partition_missing_kitty_specs_is_empty(tmp_path: Path) -> None:
    assert partition_kitty_specs(tmp_path / "kitty-specs", tmp_path) == ([], [])


def test_residue_warnings_name_project_relative_paths(tmp_path: Path) -> None:
    folders = [
        tmp_path / "kitty-specs" / "leftover",
        tmp_path / ".worktrees" / "wt1" / "kitty-specs" / "x",
    ]
    warnings = residue_warnings(folders, tmp_path)
    assert warnings == [
        residue_notice("kitty-specs/leftover"),
        residue_notice(".worktrees/wt1/kitty-specs/x"),
    ]
    assert [residue_notice_path(w) for w in warnings] == ["kitty-specs/leftover", ".worktrees/wt1/kitty-specs/x"]


def test_importing_the_module_registers_no_migration() -> None:
    import importlib

    import specify_cli.upgrade.migrations._residue_successor as module

    before = dict(MigrationRegistry._migrations)
    importlib.reload(module)
    assert dict(MigrationRegistry._migrations) == before
