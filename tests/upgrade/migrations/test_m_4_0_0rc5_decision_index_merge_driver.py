"""Tests for migration 4.0.0rc5_decision_index_merge_driver (FR-009b / #5023).

Mirrors ``tests/upgrade/migrations/test_m_3_2_6_decisions_event_log_merge_driver.py``:
fresh repository gets the line + config added, an already-seeded repository is a
no-op, and the migration carries its own distinct id (never folded into a
sibling migration's recorded id, which would strand it for an already-upgraded
consumer -- the #2709 re-inheritance risk the runner-level test below pins).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.upgrade.migrations.m_3_2_7_review_cycle_merge_driver import (
    ReviewCycleMergeDriverMigration,
)
from specify_cli.upgrade.migrations.m_4_0_0rc5_decision_index_merge_driver import (
    DecisionIndexMergeDriverMigration,
)
from specify_cli.upgrade.runner import MigrationRunner
from kernel.clock import now_utc
from specify_cli.upgrade.metadata import ProjectMetadata

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_DECISION_INDEX_ENTRY = "kitty-specs/**/decisions/index.json merge=spec-kitty-decision-index"
_REVIEW_CYCLE_ID = "3.2.7_review_cycle_merge_driver"


def _git(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *cmd], cwd=cwd, text=True, capture_output=True, check=True)


def _init_repo(tmp_path: Path) -> Path:
    _git(["init", "-b", "main"], tmp_path)
    _git(["config", "user.email", "test@example.com"], tmp_path)
    _git(["config", "user.name", "Spec Kitty"], tmp_path)
    (tmp_path / ".kittify").mkdir(exist_ok=True)
    return tmp_path


def test_target_version_does_not_exceed_package_version() -> None:
    """Binding correction: ``target_version`` must equal the installed package
    version (``4.0.0rc5``) so an already-rc5 project still gains the driver
    purely through ``detect()``, never silently skipped by the version gate."""
    assert DecisionIndexMergeDriverMigration.target_version == "4.0.0rc5"


def test_apply_installs_decision_index_driver(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    migration = DecisionIndexMergeDriverMigration()
    assert migration.detect(repo) is True

    result = migration.apply(repo)
    assert result.success is True

    attributes = (repo / ".gitattributes").read_text(encoding="utf-8")
    assert _DECISION_INDEX_ENTRY in attributes
    assert _git(["config", "--local", "--get", "merge.spec-kitty-decision-index.driver"], repo).stdout.strip() == "spec-kitty merge-driver-decision-index %O %A %B"
    assert migration.detect(repo) is False


def test_apply_is_idempotent(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    migration = DecisionIndexMergeDriverMigration()

    first = migration.apply(repo)
    assert first.success is True
    assert first.changes_made

    second = migration.apply(repo)
    assert second.success is True
    assert second.changes_made == []


def test_preserves_unrelated_gitattributes_content(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / ".gitattributes").write_text("*.png binary\n", encoding="utf-8")

    DecisionIndexMergeDriverMigration().apply(repo)

    text = (repo / ".gitattributes").read_text(encoding="utf-8")
    assert "*.png binary" in text
    assert _DECISION_INDEX_ENTRY in text


def test_ships_as_distinct_id_from_review_cycle() -> None:
    """A distinct id is the whole point -- see the runner re-run test below."""
    assert DecisionIndexMergeDriverMigration.migration_id != ReviewCycleMergeDriverMigration.migration_id


def test_prior_review_cycle_upgrade_does_not_strand_decision_index_driver(
    tmp_path: Path,
) -> None:
    """Runner-level binding (#2709 class): the runner skips a migration whose id
    is already recorded BEFORE calling ``detect()``. A repo that recorded the
    review-cycle migration id on a prior upgrade must still gain the
    decision-index driver, because it carries a DISTINCT id that is not yet
    recorded.

    Exercises both branches of the ``has_migration`` short-circuit so it cannot
    pass vacuously: the un-recorded distinct id is applied; recording it skips.
    """
    repo = _init_repo(tmp_path)

    # Simulate a consumer already at the review-cycle-driver state.
    ReviewCycleMergeDriverMigration().apply(repo)
    metadata = ProjectMetadata(version="3.2.7", initialized_at=now_utc())
    metadata.record_migration(_REVIEW_CYCLE_ID, "success")
    assert metadata.has_migration(_REVIEW_CYCLE_ID) is True
    assert _DECISION_INDEX_ENTRY not in (repo / ".gitattributes").read_text(encoding="utf-8")

    runner = MigrationRunner(repo)

    _result, status = runner._apply_migration(DecisionIndexMergeDriverMigration(), metadata, dry_run=False)
    assert status == "applied"
    assert _DECISION_INDEX_ENTRY in (repo / ".gitattributes").read_text(encoding="utf-8")

    metadata.record_migration(DecisionIndexMergeDriverMigration.migration_id, "success")
    _result2, status2 = runner._apply_migration(DecisionIndexMergeDriverMigration(), metadata, dry_run=False)
    assert status2 == "skipped"
