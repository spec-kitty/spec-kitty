"""Regression (#1589): finalize must not clobber the coordination event log.

On coordination-topology missions the canonical ``status.events.jsonl`` +
``status.json`` are owned by the transactional status emitter, which commits the
bootstrap's lane-state events into the coordination worktree. Finalize used to
copy the primary checkout's stale copies over them before committing, wiping the
seeded lane state. These tests pin the corrected staging behaviour.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.cli.commands.agent.mission import (
    _branch_tree_relative_path,
    _collect_finalize_artifacts,
    _stage_finalize_artifacts_in_coord_worktree,
)

pytestmark = pytest.mark.integration


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _commit_all(worktree: Path) -> None:
    for argv in (
        ["init", "-q"],
        ["add", "-A"],
        ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "seed"],
    ):
        subprocess.run(["git", *argv], cwd=worktree, check=True)


def test_canonical_status_files_excluded_from_coord_staging(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    feature_dir = repo_root / "kitty-specs" / "060-test"

    primary_events = _write(feature_dir / "status.events.jsonl", "STALE-PRIMARY\n")
    primary_snapshot = _write(feature_dir / "status.json", "{}\n")
    tasks_md = _write(feature_dir / "tasks.md", "# tasks\n")
    lanes = _write(feature_dir / "lanes.json", '{"lanes": []}\n')
    files_to_commit = [primary_events, primary_snapshot, tasks_md, lanes]

    coord_wt = tmp_path / "coord"
    coord_feature = coord_wt / "kitty-specs" / "060-test"
    # The seeded lane-state log the transactional emitter already wrote.
    seeded = _write(coord_feature / "status.events.jsonl", "SEEDED-LANE-EVENTS\n")
    # The emitter commits that log, so the coord twin is a clean git checkout
    # (#5513 reads the twin's git status and fails closed outside a repository).
    _commit_all(coord_wt)

    staged = _stage_finalize_artifacts_in_coord_worktree(
        files_to_commit, coord_wt, repo_root
    )

    staged_names = {p.name for p in staged}
    # The canonical status log + snapshot are NOT staged from the primary copy.
    assert staged_names == {"tasks.md", "lanes.json"}
    # Planning artifacts are copied into the coord worktree for the commit.
    assert (coord_feature / "tasks.md").read_text(encoding="utf-8") == "# tasks\n"
    # The seeded coordination event log is left intact (not clobbered).
    assert seeded.read_text(encoding="utf-8") == "SEEDED-LANE-EVENTS\n"


def test_staging_copies_only_existing_non_status_artifacts(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    feature_dir = repo_root / "kitty-specs" / "060-test"
    tasks_md = _write(feature_dir / "tasks.md", "# tasks\n")
    missing = feature_dir / "acceptance-matrix.json"  # not created on disk
    files_to_commit = [tasks_md, missing]

    coord_wt = tmp_path / "coord"

    staged = _stage_finalize_artifacts_in_coord_worktree(
        files_to_commit, coord_wt, repo_root
    )

    # Both non-status paths are returned (for staging); only the existing one is
    # physically copied into the coord worktree.
    assert {p.name for p in staged} == {"tasks.md", "acceptance-matrix.json"}
    assert (coord_wt / "kitty-specs" / "060-test" / "tasks.md").exists()
    assert not (coord_wt / "kitty-specs" / "060-test" / "acceptance-matrix.json").exists()


def test_collect_finalize_artifacts_includes_issue_matrix_json(tmp_path: Path) -> None:
    """write-surface-coherence WP08 (#2804 / #2404 T043 / G3): the terminal
    ``issue-matrix.json`` is the finalize-commit candidate — the retired
    ``issue-matrix.md`` (no canonical path authors it any more, WP05) is not.
    """
    feature_dir = tmp_path / "repo" / "kitty-specs" / "060-test"
    tasks_dir = feature_dir / "tasks"
    _write(feature_dir / "tasks.md", "# tasks\n")
    _write(feature_dir / "issue-matrix.json", '{"schema_version": 1, "rows": {}}\n')
    _write(tasks_dir / "WP01.md", "# WP01\n")

    artifacts = _collect_finalize_artifacts(feature_dir, tasks_dir)

    assert feature_dir / "issue-matrix.json" in artifacts
    assert feature_dir / "issue-matrix.md" not in artifacts


def test_branch_tree_relative_path_strips_target_worktree_prefix(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    coord_wt = repo_root / ".worktrees" / "060-test-01KT3YBD-coord"
    plan_file = _write(
        coord_wt / "kitty-specs" / "060-test-01KT3YBD" / "plan.md",
        "# plan\n",
    )

    assert (
        _branch_tree_relative_path(plan_file, repo_root)
        == "kitty-specs/060-test-01KT3YBD/plan.md"
    )


def test_staging_includes_artifacts_already_in_target_coord_worktree(tmp_path: Path) -> None:
    """#1954: coord-local sources are already at branch-tree paths."""
    repo_root = tmp_path / "repo"
    coord_wt = repo_root / ".worktrees" / "060-test-01KT3YBD-coord"
    coord_source = _write(
        coord_wt / "kitty-specs" / "060-test-01KT3YBD" / "tasks.md",
        "# tasks\n",
    )

    staged = _stage_finalize_artifacts_in_coord_worktree(
        [coord_source], coord_wt, repo_root
    )

    assert staged == [coord_source]
    assert not (
        coord_wt / ".worktrees" / "060-test-01KT3YBD-coord"
    ).exists()


def test_staging_skips_foreign_worktree_artifacts(tmp_path: Path) -> None:
    """FR-035: foreign coord-resolved sources must not create nested paths."""
    repo_root = tmp_path / "repo"
    coord_wt = repo_root / ".worktrees" / "060-test-01KT3YBD-coord"
    foreign_source = _write(
        repo_root / ".worktrees" / "other-coord" / "kitty-specs" / "060-test-01KT3YBD" / "tasks.md",
        "# tasks\n",
    )

    staged = _stage_finalize_artifacts_in_coord_worktree(
        [foreign_source], coord_wt, repo_root
    )

    assert staged == []
    assert not (
        coord_wt / ".worktrees" / "060-test-01KT3YBD-coord"
    ).exists()


def test_staging_skips_nested_worktree_artifacts(tmp_path: Path) -> None:
    """FR-035: nested .worktrees paths inside the coord worktree stay blocked."""
    repo_root = tmp_path / "repo"
    coord_wt = repo_root / ".worktrees" / "060-test-01KT3YBD-coord"
    nested_source = _write(
        coord_wt / ".worktrees" / "nested" / "kitty-specs" / "060-test-01KT3YBD" / "tasks.md",
        "# tasks\n",
    )

    staged = _stage_finalize_artifacts_in_coord_worktree(
        [nested_source], coord_wt, repo_root
    )

    assert staged == []
