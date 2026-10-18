"""Drift instrumentation: identity + content_hash on apply, audit-only (FR-010, C-004).

WP02 / IC-04. These gates pin the NEW behaviour the selection-authority flip adds:

* ``BaseMigration`` gains ``identity`` (defaults to ``migration_id``) and
  ``content_hash_sources`` (defaults empty ⇒ the migration's own module file)
  ClassVars (D1), which the WP01 ledger reaches by defensive ``getattr``.
* The runner, on the apply success leg, writes a ledger record carrying the
  migration's ``identity`` and a ``sha256:`` ``content_hash`` (D3).
* Drift (recorded hash ≠ current hash) is flagged **read-only** by
  ``MigrationLedger.drift_for`` and NEVER re-selects or re-applies the
  migration (C-004) — a recorded migration stays recorded whatever its source
  now hashes to.
* A multi-file migration (``content_hash_sources``) hashes deterministically,
  regardless of the declaration order.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from kernel.clock import now_utc
from specify_cli.upgrade.ledger import (
    LedgerRecord,
    MigrationLedger,
    build_record,
    compute_content_hash,
)
from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations.base import BaseMigration, MigrationResult
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.runner import MigrationRunner

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.fixture
def registry() -> Iterator[type[MigrationRegistry]]:
    """An empty registry for the test; the real one is restored afterwards."""
    saved = dict(MigrationRegistry._migrations)
    MigrationRegistry.clear()
    try:
        yield MigrationRegistry
    finally:
        MigrationRegistry._migrations.clear()
        MigrationRegistry._migrations.update(saved)


def _project(tmp_path: Path, version: str = "4.0.0rc7") -> Path:
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    ProjectMetadata(version=version, initialized_at=now_utc()).save(kittify)
    return tmp_path


class _Planted(BaseMigration):
    migration_id = "planted_drift_mig"
    description = "planted drift migration"
    target_version = "3.1.0"

    def detect(self, project_path: Path) -> bool:  # noqa: ARG002 - always needed until applied
        return True

    def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        if not dry_run:
            (project_path / "drift-applied.txt").write_text("x", encoding="utf-8")
        return MigrationResult(success=True, changes_made=["applied planted_drift_mig"])


# --------------------------------------------------------------------------- #
# D1 — the drift ClassVars exist with the documented defaults.
# --------------------------------------------------------------------------- #


def test_identity_classvar_defaults_to_empty_and_resolves_to_migration_id() -> None:
    """``identity`` defaults empty on the base; the ledger resolves it to ``migration_id``."""
    assert BaseMigration.identity == ""
    record = build_record(_Planted(), "success")
    assert record.identity == "planted_drift_mig"


def test_content_hash_sources_classvar_defaults_to_empty_tuple() -> None:
    assert BaseMigration.content_hash_sources == ()


# --------------------------------------------------------------------------- #
# D3 — apply writes identity + a sha256 content_hash into the ledger record.
# --------------------------------------------------------------------------- #


def test_apply_success_stores_identity_and_content_hash(registry: type[MigrationRegistry], tmp_path: Path) -> None:
    registry.register(_Planted)
    project = _project(tmp_path)

    result = MigrationRunner(project).upgrade("4.0.0rc7", include_worktrees=False)
    assert result.success, result.errors
    assert "planted_drift_mig" in result.migrations_applied

    records = [r for r in MigrationLedger(project).read_all() if r.id == "planted_drift_mig"]
    assert len(records) == 1
    record = records[0]
    assert record.result == "success"
    assert record.identity == "planted_drift_mig"
    assert record.content_hash.startswith("sha256:")
    assert record.content_hash == compute_content_hash(_Planted())


# --------------------------------------------------------------------------- #
# FR-010 / C-004 — drift is read-only; it never re-selects or re-applies.
# --------------------------------------------------------------------------- #


def test_drift_flagged_read_only_when_recorded_hash_differs(registry: type[MigrationRegistry], tmp_path: Path) -> None:
    registry.register(_Planted)
    project = _project(tmp_path)
    ledger = MigrationLedger(project)
    # A recorded record whose content_hash does NOT match the current source.
    ledger.append(
        LedgerRecord(
            id="planted_drift_mig",
            applied_at=now_utc(),
            result="success",
            identity="planted_drift_mig",
            content_hash="sha256:deadbeef",
            cli_version="test",
        )
    )

    assert ledger.drift_for(_Planted()) is True


def test_drift_does_not_reselect_a_recorded_migration(registry: type[MigrationRegistry], tmp_path: Path) -> None:
    """A drifted-source recorded migration is NEVER re-selected (C-004: audit-only)."""
    registry.register(_Planted)
    project = _project(tmp_path)
    ledger = MigrationLedger(project)
    ledger.append(
        LedgerRecord(
            id="planted_drift_mig",
            applied_at=now_utc(),
            result="success",
            identity="planted_drift_mig",
            content_hash="sha256:deadbeef",  # drift
            cli_version="test",
        )
    )

    selected = [m.migration_id for m in registry.get_applicable("4.0.0rc7", "4.0.0rc7", project_path=project)]
    assert "planted_drift_mig" not in selected


def test_drift_does_not_trigger_apply_in_a_real_run(registry: type[MigrationRegistry], tmp_path: Path) -> None:
    registry.register(_Planted)
    project = _project(tmp_path)
    ledger = MigrationLedger(project)
    ledger.append(
        LedgerRecord(
            id="planted_drift_mig",
            applied_at=now_utc(),
            result="success",
            identity="planted_drift_mig",
            content_hash="sha256:deadbeef",  # drift
            cli_version="test",
        )
    )

    result = MigrationRunner(project).upgrade("4.0.0rc7", include_worktrees=False)
    assert result.success, result.errors
    assert "planted_drift_mig" not in result.migrations_applied
    assert not (project / "drift-applied.txt").exists()  # apply() never ran


def test_no_drift_when_recorded_hash_matches_current(registry: type[MigrationRegistry], tmp_path: Path) -> None:
    registry.register(_Planted)
    project = _project(tmp_path)
    ledger = MigrationLedger(project)
    ledger.append(build_record(_Planted(), "success"))

    assert ledger.drift_for(_Planted()) is False


# --------------------------------------------------------------------------- #
# D2/OQ-3 — multi-file content_hash is deterministic and order-independent.
# --------------------------------------------------------------------------- #


def test_multi_file_content_hash_is_deterministic_and_order_independent(tmp_path: Path) -> None:
    file_a = tmp_path / "a.py"
    file_b = tmp_path / "b.py"
    file_a.write_text("alpha\n", encoding="utf-8")
    file_b.write_text("beta\n", encoding="utf-8")

    class _MultiForward(_Planted):
        content_hash_sources = (str(file_a), str(file_b))

    class _MultiReversed(_Planted):
        content_hash_sources = (str(file_b), str(file_a))

    forward = compute_content_hash(_MultiForward())
    reversed_ = compute_content_hash(_MultiReversed())

    assert forward.startswith("sha256:")
    assert forward == reversed_  # sorted-concatenation ⇒ declaration order does not matter
    # And it differs from the single-module-file default.
    assert forward != compute_content_hash(_Planted())
