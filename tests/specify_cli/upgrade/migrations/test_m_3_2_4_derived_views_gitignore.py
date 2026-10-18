"""Regression tests for the ``.kittify/derived/`` gitignore backfill (#2369, Defect B).

Covers the bug where an already-initialised project that runs
``spec-kitty materialize`` had its regenerable ``.kittify/derived/`` views show
up as untracked — dirtying the tree and failing ``spec-kitty accept``'s
``git_dirty`` check — because no upgrade migration added ``.kittify/derived/``
to ``.gitignore``.

- apply() adds the derived entry and hides a generated views dir
- detect() is True when the entry is missing (already-upgraded project)
- detect() is False once the entry is present
- detect() ignores a commented-out entry
- apply() is idempotent
- the backfill fires end-to-end via MigrationRunner on an already-current 3.2.4 project
"""

from __future__ import annotations

import os
import subprocess
from kernel.clock import now_utc
from pathlib import Path

import pytest

from specify_cli.gitignore_manager import GitignorePathError
from specify_cli.upgrade.ledger import MigrationLedger, build_record
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.migrations.m_3_2_4_derived_views_gitignore_backfill import (
    DerivedViewsGitignoreBackfillMigration,
)
from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.runner import MigrationRunner

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _settle_all_except(project: Path, *keep_unsettled: str) -> None:
    """Seed the ledger so every declared migration except ``keep_unsettled`` is ``success``.

    Post-cutover ``get_applicable`` is a ledger-diff over the full declared set
    (version window retired, ADR 2026-10-17-1); seeding a fully-adopted ledger
    stops an unrelated gitignore backfill from pre-satisfying the subject. Fixture
    setup only -- explicit success records.
    """
    for migration in MigrationRegistry.get_all():
        if migration.migration_id not in keep_unsettled:
            MigrationLedger(project).append(build_record(migration, "success"))

_DERIVED_VIEWS_ENTRY = ".kittify/derived/"
_DERIVED_VIEW_PATH = ".kittify/derived/some-mission/lifecycle.json"


def _init_git_repo(project_root: Path) -> None:
    subprocess.run(["git", "-C", str(project_root), "init", "-q"], check=True)


def _write_gitignore(project_root: Path, *entries: str) -> None:
    project_root.joinpath(".gitignore").write_text(
        "# Added by Spec Kitty CLI (auto-managed)\n" + "\n".join(entries) + "\n",
        encoding="utf-8",
    )


def _write_metadata(project_root: Path, version: str) -> None:
    ProjectMetadata(version=version, initialized_at=now_utc()).save(
        project_root / ".kittify"
    )


def _is_ignored(project_root: Path, path: str) -> bool:
    return (
        subprocess.run(
            ["git", "-C", str(project_root), "check-ignore", "--quiet", path],
            check=False,
        ).returncode
        == 0
    )


def test_apply_adds_derived_entry_and_hides_generated_views(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    view = tmp_path / _DERIVED_VIEW_PATH
    view.parent.mkdir(parents=True)
    view.write_text("{}\n", encoding="utf-8")

    DerivedViewsGitignoreBackfillMigration().apply(tmp_path)

    gitignore_text = tmp_path.joinpath(".gitignore").read_text(encoding="utf-8")
    assert _DERIVED_VIEWS_ENTRY in gitignore_text
    assert _is_ignored(tmp_path, _DERIVED_VIEW_PATH)


def test_detect_true_when_derived_entry_missing(tmp_path: Path) -> None:
    """Already-upgraded project: other entries present, derived missing."""
    _init_git_repo(tmp_path)
    _write_gitignore(tmp_path, ".kittify/sync-state.json")

    assert DerivedViewsGitignoreBackfillMigration().detect(tmp_path) is True


def test_detect_false_when_derived_entry_present(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    _write_gitignore(tmp_path, _DERIVED_VIEWS_ENTRY)

    assert DerivedViewsGitignoreBackfillMigration().detect(tmp_path) is False


def test_detect_rejects_symlinked_gitignore(tmp_path: Path) -> None:
    """detect() must not follow a .gitignore that is a symlink (issue #626)."""
    _init_git_repo(tmp_path)
    outside_target = tmp_path.parent / f"outside-target-{os.getpid()}.txt"
    outside_target.write_text("do-not-touch\n")
    (tmp_path / ".gitignore").symlink_to(outside_target)

    try:
        with pytest.raises(GitignorePathError):
            DerivedViewsGitignoreBackfillMigration().detect(tmp_path)
    finally:
        outside_target.unlink(missing_ok=True)


def test_detect_false_for_no_trailing_slash_variant(tmp_path: Path) -> None:
    # A hand-added ``.kittify/derived`` (no trailing slash) ignores the same
    # dir; the backfill must treat it as present so it never adds a duplicate.
    _init_git_repo(tmp_path)
    _write_gitignore(tmp_path, ".kittify/derived")

    migration = DerivedViewsGitignoreBackfillMigration()
    assert migration.detect(tmp_path) is False
    migration.apply(tmp_path)
    entries = [
        line.strip()
        for line in tmp_path.joinpath(".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert ".kittify/derived/" not in entries  # no duplicate beside the variant


def test_detect_ignores_commented_out_derived_entry(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    _write_gitignore(tmp_path, f"# {_DERIVED_VIEWS_ENTRY}")

    assert DerivedViewsGitignoreBackfillMigration().detect(tmp_path) is True


def test_apply_is_idempotent(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    _write_gitignore(tmp_path, _DERIVED_VIEWS_ENTRY)

    first = DerivedViewsGitignoreBackfillMigration().apply(tmp_path)
    second = DerivedViewsGitignoreBackfillMigration().apply(tmp_path)

    assert first.success
    assert second.success
    gitignore_text = tmp_path.joinpath(".gitignore").read_text(encoding="utf-8")
    assert gitignore_text.count(_DERIVED_VIEWS_ENTRY) == 1


def test_dry_run_reports_without_mutating(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    _write_gitignore(tmp_path, ".kittify/sync-state.json")

    result = DerivedViewsGitignoreBackfillMigration().apply(tmp_path, dry_run=True)

    assert result.success
    assert result.changes_made == [f"Would add {_DERIVED_VIEWS_ENTRY} to .gitignore"]
    # Dry run must not touch the file.
    assert _DERIVED_VIEWS_ENTRY not in tmp_path.joinpath(".gitignore").read_text(
        encoding="utf-8"
    )


def test_backfill_fires_on_already_current_3_2_4_project(tmp_path: Path) -> None:
    """The user's exact case: a 3.2.4 project whose .gitignore lacks derived/."""
    _init_git_repo(tmp_path)
    _write_metadata(tmp_path, "3.2.4")
    _write_gitignore(tmp_path, ".kittify/sync-state.json")
    view = tmp_path / _DERIVED_VIEW_PATH
    view.parent.mkdir(parents=True)
    view.write_text("{}\n", encoding="utf-8")

    auto_discover_migrations()
    _settle_all_except(tmp_path, DerivedViewsGitignoreBackfillMigration.migration_id)
    result = MigrationRunner(tmp_path).upgrade("3.2.4", include_worktrees=False)

    assert result.success
    assert (
        DerivedViewsGitignoreBackfillMigration.migration_id
        in result.migrations_applied
    )
    assert _is_ignored(tmp_path, _DERIVED_VIEW_PATH)
