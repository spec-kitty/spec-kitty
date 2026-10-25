"""#6669 / FR-003: the shared migration walkers leave ``kitty-specs/`` residue folders untouched.

Covers ``backfill_runtime_state._mission_dirs`` (behind ``migrate backfill-runtime-state``
and ``migrate backfill-wp-status``), ``runner._move_derived_files`` and
``runtime_state_cutover.cutover_repo``. Residue skips are reported through the log only
(``residue_notice``), so upgrade output never names a folder twice. Non-git projects keep
the file-presence rule (a tasks-only folder is processed there).
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

import pytest

from specify_cli.context.mission_resolver import residue_notice
from specify_cli.migration.backfill_runtime_state import (
    _mission_dirs,
    apply_wp_status_backfill_repo,
    backfill_runtime_state_repo,
)
from specify_cli.migration.runner import _move_derived_files
from specify_cli.migration.runtime_state_cutover import cutover_repo

pytestmark = [pytest.mark.git_repo]

_REAL = "001-real"
_STATUS_ONLY = "050-status-only"
_TASKS_ONLY = "051-tasks-only"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _populate(root: Path) -> None:
    real = root / "kitty-specs" / _REAL
    real.mkdir(parents=True)
    (real / "spec.md").write_text("# Real\n", encoding="utf-8")
    (real / "status.json").write_text("{}\n", encoding="utf-8")


def _add_residue(root: Path) -> None:
    status_only = root / "kitty-specs" / _STATUS_ONLY
    status_only.mkdir(parents=True)
    (status_only / "status.json").write_text("{}\n", encoding="utf-8")
    tasks_only = root / "kitty-specs" / _TASKS_ONLY
    (tasks_only / "tasks").mkdir(parents=True)
    (tasks_only / "tasks" / "WP01.md").write_text("# WP\n", encoding="utf-8")


@pytest.fixture()
def tracked_project(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    _populate(root)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "mission")
    _add_residue(root)  # untracked leftovers
    return root


@pytest.fixture()
def plain_project(tmp_path: Path) -> Path:
    root = tmp_path / "plain"
    root.mkdir()
    _populate(root)
    _add_residue(root)
    return root


def _snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted((root / "kitty-specs").rglob("*")) if p.is_file()}


def test_mission_dirs_skip_residue_and_keep_real_missions(tracked_project: Path) -> None:
    assert [d.name for d in _mission_dirs(tracked_project, None)] == [_REAL]


def test_mission_dirs_skip_residue_named_by_selector(tracked_project: Path) -> None:
    assert _mission_dirs(tracked_project, _TASKS_ONLY) == []
    assert [d.name for d in _mission_dirs(tracked_project, _REAL)] == [_REAL]


def test_backfill_walkers_leave_residue_untouched(tracked_project: Path) -> None:
    before = _snapshot(tracked_project)
    runtime = backfill_runtime_state_repo(tracked_project, dry_run=True)
    wp_status = apply_wp_status_backfill_repo(tracked_project, dry_run=True)
    assert [r.slug for r in runtime] == [_REAL]
    assert len(wp_status) == 1
    assert _snapshot(tracked_project) == before


def test_move_derived_files_skips_residue(tracked_project: Path) -> None:
    moved = _move_derived_files(tracked_project)
    assert len(moved) == 1 and _REAL in moved[0]
    derived = tracked_project / ".kittify" / "derived"
    assert sorted(p.name for p in derived.iterdir()) == [_REAL]


def test_cutover_repo_reports_residue_without_writing(tracked_project: Path) -> None:
    before = _snapshot(tracked_project)
    results = {r.slug: r for r in cutover_repo(tracked_project, dry_run=True)}
    assert results[_STATUS_ONLY].residue and results[_TASKS_ONLY].residue
    assert not results[_REAL].residue
    assert _snapshot(tracked_project) == before


def test_skip_is_logged_once_per_folder(tracked_project: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    _mission_dirs(tracked_project, None)
    for slug in (_STATUS_ONLY, _TASKS_ONLY):
        notice = residue_notice(f"kitty-specs/{slug}")
        assert sum(notice in record.getMessage() for record in caplog.records) == 1


def test_non_git_fallback_processes_the_tasks_only_folder(plain_project: Path) -> None:
    names = [d.name for d in _mission_dirs(plain_project, None)]
    assert _REAL in names
    assert _TASKS_ONLY in names


class _GitCount:
    def __init__(self) -> None:
        self.calls = 0


@pytest.fixture()
def git_count(monkeypatch: pytest.MonkeyPatch) -> _GitCount:
    counting = _GitCount()
    real_init = subprocess.Popen.__init__

    def counted_init(self: Any, args: Any, *rest: Any, **kwargs: Any) -> None:
        argv = args if isinstance(args, (list, tuple)) else [args]
        if argv and Path(str(argv[0])).name == "git":
            counting.calls += 1
        real_init(self, args, *rest, **kwargs)

    monkeypatch.setattr(subprocess.Popen, "__init__", counted_init)
    return counting


def test_cutover_repo_probes_git_once_per_walk(tracked_project: Path, git_count: _GitCount) -> None:
    """WP01 review item 7: many identity-less folders cost the one batch probe (rev-parse + ls-files), not 2 each."""
    for i in range(100, 130):
        folder = tracked_project / "kitty-specs" / f"{i:03d}-bulk"
        (folder / "decisions").mkdir(parents=True)
        (folder / "decisions" / "index.json").write_text("{}\n", encoding="utf-8")
    git_count.calls = 0
    results = cutover_repo(tracked_project, dry_run=True)
    residue = [r for r in results if r.residue]
    assert len(residue) == 32
    assert git_count.calls <= 2
