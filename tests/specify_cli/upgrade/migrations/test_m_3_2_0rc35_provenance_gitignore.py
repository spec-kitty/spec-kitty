"""Regression tests for the encoding-provenance gitignore repair.

Covers the bug where ``.kittify/encoding-provenance/global.jsonl`` was listed
for untracking but never added to ``.gitignore``, so a freshly-generated
(untracked) provenance log showed up in ``git status`` forever.

- apply() adds the provenance entry to .gitignore
- detect() returns True when the provenance entry is missing even though
  sync-state is already present (the already-upgraded-project case)
- detect() returns False once both entries are present and nothing is tracked
- apply() is idempotent when both entries are already present
"""

from __future__ import annotations

import subprocess
from kernel.clock import now_utc
from pathlib import Path

import pytest

from specify_cli.upgrade.migrations.m_3_2_0rc35_sync_state_gitignore import (
    KittifyRuntimeGitHygieneMigration,
)
from specify_cli.upgrade.migrations.m_3_2_3_encoding_provenance_gitignore_backfill import (
    EncodingProvenanceGitignoreBackfillMigration,
)
from specify_cli.upgrade.ledger import MigrationLedger, build_record
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.runner import MigrationRunner

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _settle_all_except(project: Path, *keep_unsettled: str) -> None:
    """Seed the ledger so every declared migration except ``keep_unsettled`` is ``success``.

    Post-cutover ``get_applicable`` is a ledger-diff over the full declared set
    (the version window is retired, ADR 2026-10-17-1), so a bare fixture with an
    empty ledger runs ~every migration and an unrelated gitignore backfill can
    pre-satisfy the one under test. Seeding the ledger to a fully-adopted project
    isolates the subject migration. Fixture setup only -- explicit success records.
    """
    for migration in MigrationRegistry.get_all():
        if migration.migration_id not in keep_unsettled:
            MigrationLedger(project).append(build_record(migration, "success"))

_PROVENANCE_GITIGNORE_ENTRY = ".kittify/encoding-provenance/"
_PROVENANCE_LOG_PATH = ".kittify/encoding-provenance/global.jsonl"
_SYNC_STATE_ENTRY = ".kittify/sync-state.json"
_OPS_INDEX_ENTRY = "kitty-ops/ops-index.jsonl"


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


def test_apply_adds_provenance_entry_and_hides_generated_log(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    migration = KittifyRuntimeGitHygieneMigration()
    provenance_log = tmp_path / _PROVENANCE_LOG_PATH
    provenance_log.parent.mkdir(parents=True)
    provenance_log.write_text("{}\n", encoding="utf-8")

    migration.apply(tmp_path)

    gitignore_text = tmp_path.joinpath(".gitignore").read_text(encoding="utf-8")
    assert _PROVENANCE_GITIGNORE_ENTRY in gitignore_text
    assert _SYNC_STATE_ENTRY in gitignore_text
    assert _is_ignored(tmp_path, _PROVENANCE_LOG_PATH)


def test_detect_true_when_only_provenance_entry_missing(tmp_path: Path) -> None:
    """Already-upgraded project: sync-state present, provenance entry missing."""
    _init_git_repo(tmp_path)
    _write_gitignore(tmp_path, _SYNC_STATE_ENTRY)

    assert KittifyRuntimeGitHygieneMigration().detect(tmp_path) is True


def test_detect_false_when_all_entries_present(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    _write_gitignore(
        tmp_path, _SYNC_STATE_ENTRY, _PROVENANCE_GITIGNORE_ENTRY, _OPS_INDEX_ENTRY
    )

    assert KittifyRuntimeGitHygieneMigration().detect(tmp_path) is False


def test_detect_ignores_commented_out_provenance_entry(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    _write_gitignore(tmp_path, _SYNC_STATE_ENTRY, f"# {_PROVENANCE_GITIGNORE_ENTRY}")

    assert KittifyRuntimeGitHygieneMigration().detect(tmp_path) is True


def test_apply_reports_only_missing_gitignore_entries(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    _write_gitignore(tmp_path, _SYNC_STATE_ENTRY, _OPS_INDEX_ENTRY)

    result = KittifyRuntimeGitHygieneMigration().apply(tmp_path)

    assert result.changes_made[0] == (
        f"Added gitignore entries: {_PROVENANCE_GITIGNORE_ENTRY}"
    )


def test_apply_is_idempotent(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    _write_gitignore(
        tmp_path, _SYNC_STATE_ENTRY, _PROVENANCE_GITIGNORE_ENTRY, _OPS_INDEX_ENTRY
    )

    first = KittifyRuntimeGitHygieneMigration().apply(tmp_path)
    second = KittifyRuntimeGitHygieneMigration().apply(tmp_path)

    assert first.success
    assert second.success
    assert second.errors == []
    # Entry must appear exactly once; no duplication on re-apply.
    gitignore_text = tmp_path.joinpath(".gitignore").read_text(encoding="utf-8")
    assert gitignore_text.count(_PROVENANCE_GITIGNORE_ENTRY) == 1


def _is_tracked(project_root: Path, path: str) -> bool:
    return (
        subprocess.run(
            ["git", "-C", str(project_root), "ls-files", "--error-unmatch", path],
            check=False,
            capture_output=True,
        ).returncode
        == 0
    )


def test_apply_adds_ops_index_entry_and_hides_index(tmp_path: Path) -> None:
    """The Op-index performance cache must be gitignored by the repair."""
    _init_git_repo(tmp_path)
    index = tmp_path / _OPS_INDEX_ENTRY
    index.parent.mkdir(parents=True)
    index.write_text("{}\n", encoding="utf-8")

    KittifyRuntimeGitHygieneMigration().apply(tmp_path)

    gitignore_text = tmp_path.joinpath(".gitignore").read_text(encoding="utf-8")
    assert _OPS_INDEX_ENTRY in gitignore_text
    assert _is_ignored(tmp_path, _OPS_INDEX_ENTRY)


def test_detect_true_when_only_ops_index_entry_missing(tmp_path: Path) -> None:
    """Project already carrying the other entries but missing ops-index."""
    _init_git_repo(tmp_path)
    _write_gitignore(tmp_path, _SYNC_STATE_ENTRY, _PROVENANCE_GITIGNORE_ENTRY)

    assert KittifyRuntimeGitHygieneMigration().detect(tmp_path) is True


def test_apply_untracks_committed_ops_index(tmp_path: Path) -> None:
    """A previously-committed ops-index is untracked but durable records are not."""
    _init_git_repo(tmp_path)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "t@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True
    )
    ops_dir = tmp_path / "kitty-ops"
    ops_dir.mkdir()
    (ops_dir / "ops-index.jsonl").write_text("{}\n", encoding="utf-8")
    durable = ops_dir / "01HXYZ.jsonl"
    durable.write_text("{}\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-q", "-m", "seed"], check=True
    )

    KittifyRuntimeGitHygieneMigration().apply(tmp_path)

    assert not _is_tracked(tmp_path, _OPS_INDEX_ENTRY)
    # Durable per-Op records must remain tracked.
    assert _is_tracked(tmp_path, "kitty-ops/01HXYZ.jsonl")


@pytest.mark.parametrize("from_version", ["3.2.1", "3.2.2", "3.2.3"])
def test_backfill_migration_repairs_already_current_3_2_x_project(
    tmp_path: Path,
    from_version: str,
) -> None:
    _init_git_repo(tmp_path)
    _write_metadata(tmp_path, from_version)
    _write_gitignore(tmp_path, _SYNC_STATE_ENTRY)
    provenance_log = tmp_path / _PROVENANCE_LOG_PATH
    provenance_log.parent.mkdir(parents=True)
    provenance_log.write_text("{}\n", encoding="utf-8")

    index = tmp_path / _OPS_INDEX_ENTRY
    index.parent.mkdir(parents=True)
    index.write_text("{}\n", encoding="utf-8")

    auto_discover_migrations()
    _settle_all_except(tmp_path, EncodingProvenanceGitignoreBackfillMigration.migration_id)
    result = MigrationRunner(tmp_path).upgrade("3.2.3", include_worktrees=False)

    assert result.success
    assert (
        EncodingProvenanceGitignoreBackfillMigration.migration_id
        in result.migrations_applied
    )
    assert _is_ignored(tmp_path, _PROVENANCE_LOG_PATH)
    # The backfill path (re-running rc35 hygiene) also repairs the Op-index.
    assert _is_ignored(tmp_path, _OPS_INDEX_ENTRY)
