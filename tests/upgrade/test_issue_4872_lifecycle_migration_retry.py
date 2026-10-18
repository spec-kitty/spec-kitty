"""Regression coverage for #4872: refused lifecycle migration stays retryable."""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.clock import now_utc
from specify_cli.migration.schema_version import REQUIRED_SCHEMA_VERSION
from specify_cli.status.lifecycle_events import (
    emit_project_initialized,
    emit_wp_created_local,
    mission_event_log_path,
    project_event_log_path,
    read_lifecycle_events,
)
from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations.m_3_2_9_migrate_lifecycle_envelope import (
    MigrateLifecycleEnvelopeMigration,
)
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.runner import MigrationRunner

pytestmark = [pytest.mark.integration, pytest.mark.regression]

_FROM_VERSION = "3.2.6rc1"
_TARGET_VERSION = "3.2.6rc2"
_MIGRATION_ID = "migrate_lifecycle_envelope"
_MISSION_SLUG = "042-interrupted-envelope-migration"


def _seed_project(project_root: Path) -> tuple[Path, Path]:
    ProjectMetadata(
        version=_FROM_VERSION,
        initialized_at=now_utc(),
        schema_version=REQUIRED_SCHEMA_VERSION,
    ).save(project_root / ".kittify")

    project_uuid = "48724872-4872-4872-4872-487248724872"
    emit_project_initialized(project_root, project_uuid=project_uuid, project_slug="demo")

    feature_dir = project_root / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)
    emit_wp_created_local(
        feature_dir,
        mission_slug=_MISSION_SLUG,
        wp_id="WP01",
        wp_title="Retry refused migration",
        project_uuid=project_uuid,
        project_slug="demo",
    )
    return project_event_log_path(project_root), mission_event_log_path(feature_dir)


def _only_lifecycle_migration(
    cls: type[MigrationRegistry],
    from_version: str,
    to_version: str,
    project_path: Path | None = None,
) -> list[MigrateLifecycleEnvelopeMigration]:
    """Keep the regression focused on the real migration and real runner."""
    del cls, from_version, to_version, project_path
    return [MigrateLifecycleEnvelopeMigration()]


def test_refusal_is_recorded_failed_then_retried_after_backup_removal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The prescribed repair must make an ordinary second upgrade converge."""
    project_log, mission_log = _seed_project(tmp_path)
    stale_backup = mission_log.with_name(mission_log.name + ".pre-migration.bak")
    stale_backup.write_text("STALE SNAPSHOT FROM AN INTERRUPTED RUN", encoding="utf-8")
    mission_original = mission_log.read_text(encoding="utf-8")

    monkeypatch.setattr(
        MigrationRegistry,
        "get_applicable",
        classmethod(_only_lifecycle_migration),
    )

    first = MigrationRunner(tmp_path).upgrade(_TARGET_VERSION, include_worktrees=False)

    assert first.success is False
    assert first.migrations_applied == []
    assert _MIGRATION_ID in first.migration_results
    assert first.migration_results[_MIGRATION_ID].success is False
    assert any(str(mission_log) in error for error in first.errors)

    # Corpus execution continued: the unblocked project log converged, while
    # the refused mission log and its operator snapshot remained untouched.
    assert read_lifecycle_events(project_log)[0]["schema_version"] == "3.0.0"
    assert mission_log.read_text(encoding="utf-8") == mission_original
    assert stale_backup.read_text(encoding="utf-8") == ("STALE SNAPSHOT FROM AN INTERRUPTED RUN")

    failed_metadata = ProjectMetadata.load(tmp_path / ".kittify")
    assert failed_metadata is not None
    assert failed_metadata.version == _FROM_VERSION
    # The ledger -- not metadata.yaml (retired as authority, C-001/WP04) -- carries
    # the failed row; a failed record does not settle the migration, so the retry
    # below re-selects it.
    from specify_cli.upgrade.ledger import MigrationLedger
    from specify_cli.upgrade.registry import migration_settled

    _migration = next(m for m in [MigrateLifecycleEnvelopeMigration()] if m.migration_id == _MIGRATION_ID)
    _ledger = MigrationLedger(tmp_path)
    assert [r.result for r in _ledger.read_all() if r.id == _MIGRATION_ID] == ["failed"]
    assert migration_settled(_ledger, _migration) is False

    # Follow the refusal's prescribed repair, then run the ordinary upgrade
    # path again. A failed ledger row must not make the migration look applied.
    stale_backup.unlink()
    second = MigrationRunner(tmp_path).upgrade(_TARGET_VERSION, include_worktrees=False)

    assert second.success is True
    assert second.migrations_applied == [_MIGRATION_ID]
    assert read_lifecycle_events(mission_log)[0]["schema_version"] == "3.0.0"

    converged_metadata = ProjectMetadata.load(tmp_path / ".kittify")
    assert converged_metadata is not None
    assert converged_metadata.version == _TARGET_VERSION
    # Applied-state is read from the ledger (C-001/WP04): the retry's success now
    # settles the migration. ``read_all`` collapses to the live record per id
    # (``_normalize_records``), so the resolved result is ``success``.
    assert migration_settled(_ledger, _migration) is True
    assert [r.result for r in _ledger.read_all() if r.id == _MIGRATION_ID] == ["success"]
