"""ATDD tests for the auto-discovered ``migrate_lifecycle_envelope`` migration.

WIRE-M2-03 (M2 canonical integration follow-up, 2026-08-22). Proves
``spec-kitty upgrade`` runs the previously caller-less
``status.migrate_lifecycle_envelope.migrate_lifecycle_envelope`` over BOTH
lifecycle event log targets :mod:`specify_cli.status.lifecycle_events`
defines: the project-level ``.kittify/canonical-events.jsonl`` log, and
every mission-level ``kitty-specs/<mission>/status.events.jsonl`` log.

RED-first: before the wrapper existed the module
``upgrade.migrations.m_3_2_9_migrate_lifecycle_envelope`` did not exist, so
the import at the top of this file failed at collection and every test
errored. GREEN once the wrapper is wired.

All tests call ``detect()``/``can_apply()``/``apply()`` directly on a
``MigrateLifecycleEnvelopeMigration`` instance -- the established pattern in
``test_verdict_provenance_backfill_migration.py`` /
``test_runtime_state_backfill_migration.py`` -- so the ``target_version``
guard never interferes. Fixtures seed genuine legacy 9-key rows via the real
PRODUCTION lifecycle emitters (still legacy-shaped -- confirmed by
``migrate_lifecycle_envelope``'s own module docstring: the local appenders
have not been cut over to write the strict shape directly), so this suite
exercises the real on-disk row a deployed project would actually carry; the
live repository is never mutated (everything runs under ``tmp_path``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.status.lifecycle_events import (
    emit_project_initialized,
    emit_wp_created_local,
    mission_event_log_path,
    project_event_log_path,
    read_lifecycle_events,
)
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.migrations.m_3_2_9_migrate_lifecycle_envelope import (
    MigrateLifecycleEnvelopeMigration,
)
from specify_cli.upgrade.registry import MigrationRegistry

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_THIS_MIGRATION_ID = "migrate_lifecycle_envelope"
_MISSION_SLUG = "042-migrate-lifecycle-envelope-demo"


def _seed_legacy_project_log(project_path: Path, *, project_uuid: str) -> None:
    """Write one genuine legacy ``ProjectInitialized`` row via the real emitter."""
    emit_project_initialized(project_path, project_uuid=project_uuid, project_slug="demo")


def _seed_legacy_mission_log(
    project_path: Path, *, project_uuid: str, slug: str = _MISSION_SLUG
) -> Path:
    """Write one genuine legacy ``WPCreated`` row via the real emitter.

    Returns the created mission ``feature_dir``.
    """
    feature_dir = project_path / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    emit_wp_created_local(
        feature_dir,
        mission_slug=slug,
        wp_id="WP01",
        wp_title="T",
        project_uuid=project_uuid,
        project_slug="demo",
    )
    return feature_dir


def test_apply_migrates_project_and_mission_logs(tmp_path: Path) -> None:
    """The load-bearing wiring proof: ``apply()`` rewrites BOTH log targets."""
    project_uuid = "11111111-1111-1111-1111-111111111111"
    _seed_legacy_project_log(tmp_path, project_uuid=project_uuid)
    _seed_legacy_mission_log(tmp_path, project_uuid=project_uuid)

    migration = MigrateLifecycleEnvelopeMigration()
    assert migration.detect(tmp_path) is True

    result = migration.apply(tmp_path)

    assert result.success is True
    assert result.changes_made, "a rewrite that migrated rows must report it"
    assert result.warnings == []

    project_entries = read_lifecycle_events(project_event_log_path(tmp_path))
    assert len(project_entries) == 1
    assert project_entries[0]["schema_version"] == "3.0.0"
    assert "aggregate_type" not in project_entries[0]
    assert "node_id" in project_entries[0]

    mission_entries = read_lifecycle_events(
        mission_event_log_path(tmp_path / "kitty-specs" / _MISSION_SLUG)
    )
    assert len(mission_entries) == 1
    assert mission_entries[0]["schema_version"] == "3.0.0"
    assert "aggregate_type" not in mission_entries[0]
    assert "build_id" in mission_entries[0]


def test_detect_false_and_apply_noop_once_converged(tmp_path: Path) -> None:
    """Idempotency (MIG2, reused unchanged): a second ``apply()`` rewrites
    nothing and ``detect()`` reports the converged corpus as needing no work."""
    project_uuid = "22222222-2222-2222-2222-222222222222"
    _seed_legacy_mission_log(tmp_path, project_uuid=project_uuid)
    migration = MigrateLifecycleEnvelopeMigration()

    first = migration.apply(tmp_path)
    assert first.changes_made

    assert migration.detect(tmp_path) is False
    can_apply, reason = migration.can_apply(tmp_path)
    assert can_apply is False
    assert "no legacy-shaped lifecycle envelope rows" in reason

    second = migration.apply(tmp_path)
    assert second.success is True
    assert second.changes_made == [], "converged re-run must rewrite nothing"
    assert second.warnings == []


def test_dry_run_previews_without_writing(tmp_path: Path) -> None:
    """A dry-run reports the would-rewrite count and writes NO event log."""
    project_uuid = "33333333-3333-3333-3333-333333333333"
    feature_dir = _seed_legacy_mission_log(tmp_path, project_uuid=project_uuid)
    log_path = mission_event_log_path(feature_dir)
    original = log_path.read_text(encoding="utf-8")

    migration = MigrateLifecycleEnvelopeMigration()
    result = migration.apply(tmp_path, dry_run=True)

    assert result.success is True
    assert any("dry-run" in line for line in result.changes_made)
    assert log_path.read_text(encoding="utf-8") == original
    assert not log_path.with_name(log_path.name + ".pre-migration.bak").exists()
    # Still legacy-shaped -- nothing was rewritten.
    assert migration.detect(tmp_path) is True


def test_noop_on_fresh_install_without_any_log(tmp_path: Path) -> None:
    """No ``.kittify/canonical-events.jsonl`` and no ``kitty-specs/`` (fresh
    install) is a clean no-op, not a crash."""
    migration = MigrateLifecycleEnvelopeMigration()

    assert migration.detect(tmp_path) is False
    result = migration.apply(tmp_path)

    assert result.success is True
    assert result.changes_made == []
    assert result.warnings == []


def test_mig4_refusal_on_one_log_is_a_warning_not_a_corpus_abort(tmp_path: Path) -> None:
    """A stale ``.pre-migration.bak`` on ONE log is surfaced as a warning and
    does NOT block the rest of the corpus from migrating (module docstring:
    MIG4 refusal is per-file, not per-corpus)."""
    project_uuid = "44444444-4444-4444-4444-444444444444"
    _seed_legacy_project_log(tmp_path, project_uuid=project_uuid)
    feature_dir = _seed_legacy_mission_log(tmp_path, project_uuid=project_uuid)

    mission_log = mission_event_log_path(feature_dir)
    stale_backup = mission_log.with_name(mission_log.name + ".pre-migration.bak")
    stale_backup.write_text("STALE SNAPSHOT FROM AN INTERRUPTED RUN", encoding="utf-8")
    mission_log_original = mission_log.read_text(encoding="utf-8")

    migration = MigrateLifecycleEnvelopeMigration()
    result = migration.apply(tmp_path)

    assert result.success is True
    assert len(result.warnings) == 1
    assert "refusing to migrate" in result.warnings[0]
    assert str(mission_log) in result.warnings[0]

    # The project-level log (no stale backup) still migrated.
    project_entries = read_lifecycle_events(project_event_log_path(tmp_path))
    assert project_entries[0]["schema_version"] == "3.0.0"

    # The mission-level log (stale backup present) was left completely untouched.
    assert mission_log.read_text(encoding="utf-8") == mission_log_original
    assert stale_backup.read_text(encoding="utf-8") == "STALE SNAPSHOT FROM AN INTERRUPTED RUN"


def test_migration_is_auto_discovered_and_registered() -> None:
    """The wiring is real: the migration self-registers via auto-discovery
    (``pkgutil.iter_modules`` + ``@MigrationRegistry.register``), at the
    installed-package-pinned ``target_version``, and is opted OUT of
    per-worktree re-runs (module docstring: shared project/mission state,
    not per-worktree branch content)."""
    auto_discover_migrations()

    migration = MigrationRegistry.get_by_id(_THIS_MIGRATION_ID)
    assert migration is not None, (
        "migrate_lifecycle_envelope must be auto-discovered and registered"
    )
    assert migration.target_version == "3.2.6rc2"
    assert migration.runs_on_worktrees is False
