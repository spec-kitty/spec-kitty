"""Red-first unit tests for the ledger backfill migration (WP01 / IC-06 seed).

WP01 asserts only that the backfill WRITES ledger records: tracked records
unconditionally, clone-local records only when the migration's ``detect()``
confirms the effect is present on this checkout (ADR 2026-10-17-1 §6). The
permanent strip of the on-disk ``migrations:`` block is WP-F's concern.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from kernel.clock import now_utc

from specify_cli.upgrade.ledger import MigrationLedger
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.migrations.base import BaseMigration, MigrationResult
from specify_cli.upgrade.migrations.m_4_0_0rc8_backfill_migration_ledger import (
    BackfillMigrationLedgerMigration,
)
from specify_cli.upgrade.registry import MigrationRegistry


class _TrackedFake(BaseMigration):
    migration_id = "fake_tracked_effect"
    description = "tracked fake"
    target_version = "4.0.0rc8"
    clone_local_effect = False

    def detect(self, project_path: Path) -> bool:  # noqa: ARG002
        return False

    def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:  # noqa: ARG002
        return MigrationResult(success=True)


class _CloneAbsentFake(BaseMigration):
    migration_id = "fake_clone_absent"
    description = "clone-local fake whose effect is ABSENT here"
    target_version = "4.0.0rc8"
    clone_local_effect = True

    def detect(self, project_path: Path) -> bool:  # noqa: ARG002 - True = old state present = effect absent
        return True

    def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:  # noqa: ARG002
        return MigrationResult(success=True)


class _ClonePresentFake(BaseMigration):
    migration_id = "fake_clone_present"
    description = "clone-local fake whose effect is PRESENT here"
    target_version = "4.0.0rc8"
    clone_local_effect = True

    def detect(self, project_path: Path) -> bool:  # noqa: ARG002 - False = effect already present
        return False

    def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:  # noqa: ARG002
        return MigrationResult(success=True)


@pytest.fixture
def seeded_project(tmp_path: Path) -> Iterator[Path]:
    """A project whose metadata records three prior migrations, with fakes registered."""
    auto_discover_migrations()
    for cls in (_TrackedFake, _CloneAbsentFake, _ClonePresentFake):
        MigrationRegistry.register(cls)

    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    # The backfill reads ``metadata.yaml.migrations.applied`` -- the pre-ledger
    # record it adopts. ``ProjectMetadata.save()`` no longer persists that block
    # after the WP04 hard cutover (C-001), so write it to disk directly (the
    # legacy on-disk shape a real pre-ledger project carries).
    stamp = now_utc().isoformat()
    (kittify / "metadata.yaml").write_text(
        yaml.dump(
            {
                "spec_kitty": {"version": "4.0.0rc8", "initialized_at": stamp},
                "migrations": {
                    "applied": [
                        {"id": "fake_tracked_effect", "applied_at": stamp, "result": "success"},
                        {"id": "fake_clone_absent", "applied_at": stamp, "result": "success"},
                        {"id": "fake_clone_present", "applied_at": stamp, "result": "success"},
                    ]
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    yield tmp_path


def test_backfill_writes_tracked_record_unconditionally(seeded_project: Path) -> None:
    BackfillMigrationLedgerMigration().apply(seeded_project)
    ledger = MigrationLedger(seeded_project)
    assert "fake_tracked_effect" in {r.id for r in ledger.read_tracked()}


def test_backfill_writes_clone_local_record_only_when_effect_present(seeded_project: Path) -> None:
    BackfillMigrationLedgerMigration().apply(seeded_project)
    ledger = MigrationLedger(seeded_project)
    clone_ids = {r.id for r in ledger.read_clone_local()}
    assert "fake_clone_present" in clone_ids  # detect() False -> effect present -> recorded
    assert "fake_clone_absent" not in clone_ids  # detect() True -> effect absent -> left pending


def test_backfill_clone_local_records_carry_the_flag(seeded_project: Path) -> None:
    BackfillMigrationLedgerMigration().apply(seeded_project)
    ledger = MigrationLedger(seeded_project)
    present = next(r for r in ledger.read_clone_local() if r.id == "fake_clone_present")
    assert present.clone_local is True


def test_backfill_dry_run_writes_nothing(seeded_project: Path) -> None:
    BackfillMigrationLedgerMigration().apply(seeded_project, dry_run=True)
    ledger = MigrationLedger(seeded_project)
    assert ledger.read_tracked() == []
    assert ledger.read_clone_local() == []


def test_backfill_is_idempotent(seeded_project: Path) -> None:
    mig = BackfillMigrationLedgerMigration()
    mig.apply(seeded_project)
    mig.apply(seeded_project)  # second run must not duplicate records
    ledger = MigrationLedger(seeded_project)
    tracked_ids = [r.id for r in ledger.read_tracked()]
    assert tracked_ids.count("fake_tracked_effect") == 1


def test_backfill_detect_true_when_metadata_has_unrecorded_migrations(seeded_project: Path) -> None:
    mig = BackfillMigrationLedgerMigration()
    assert mig.detect(seeded_project) is True
    mig.apply(seeded_project)
    assert mig.detect(seeded_project) is False  # everything recorded -> nothing left to backfill


def test_backfill_is_gate_valid_and_registered() -> None:
    auto_discover_migrations()
    found = MigrationRegistry.get_by_id("4.0.0rc8_backfill_migration_ledger")
    assert found is not None
    assert found.target_version == "4.0.0rc8"
