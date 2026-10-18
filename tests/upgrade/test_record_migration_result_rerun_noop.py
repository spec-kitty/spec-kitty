"""A re-run recording an already-ledgered result is a no-op (#1838 / #1872 / #4972).

Since the ledger cutover ``ProjectMetadata.save()`` no longer writes
``migrations.applied``, so a freshly loaded ``ProjectMetadata`` has an empty
in-memory list and ``record_migration`` always reports a new record. The
runner must take its "new record" signal from the ledger write instead.
"""

from __future__ import annotations

from pathlib import Path

from kernel.clock import now_utc

from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations.m_3_1_1_charter_rename import CharterRenameMigration
from specify_cli.upgrade.runner import MigrationRunner


def _load(project: Path) -> ProjectMetadata:
    metadata = ProjectMetadata.load(project / ".kittify")
    assert metadata is not None
    return metadata


def test_second_run_recording_same_skip_returns_false_and_leaves_metadata_bytes(tmp_path: Path) -> None:
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    ProjectMetadata(version="3.0.0", initialized_at=now_utc()).save(kittify)
    runner = MigrationRunner(tmp_path)
    migration = CharterRenameMigration()

    first = runner._record_migration_result(_load(tmp_path), tmp_path, migration, "skipped", "Not applicable")
    after_first = (kittify / "metadata.yaml").read_bytes()
    second = runner._record_migration_result(_load(tmp_path), tmp_path, migration, "skipped", "Not applicable")

    assert first is True
    assert second is False
    assert (kittify / "metadata.yaml").read_bytes() == after_first
