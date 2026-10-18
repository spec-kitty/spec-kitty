"""The ``spec-kitty migrate ledger`` read surface (WP03 / IC-05, FR-011, SC-005).

The ONE canonical, read-only visibility surface over the two-partition migration
ledger. It prints the recorded setup steps in declared (manifest) order, the
tracked / clone-local partition, whether a clone-local step is *in place here*
(the effect is present on this checkout) vs merely *recorded elsewhere but not
here* (via the migration's own ``detect()``), and a per-row drift flag
(content changed since it ran). ``--json`` emits the one structured shape both
paths share.

Discipline (SC-005): the surface is **read-only** — it never commits and never
writes a file. Drift is audit-only; it is reported, never re-applied (C-004).

The surface consumes WP01's ``assemble_report`` (declared/applied/partition/
in-place-here/drift) and ``detector.applicable_migrations`` (the single pending
source); it does NOT re-implement selection or drift. These tests drive the
real ``migrate ledger`` CLI entry point over a seeded ledger with planted
migrations; the global registry is snapshotted/cleared/restored so only the
planted migrations under test are visible.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from kernel.clock import now_utc
from specify_cli.cli.commands.migrate_cmd import app
from specify_cli.upgrade.ledger import (
    LedgerRecord,
    MigrationLedger,
    build_record,
)
from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations.base import BaseMigration, MigrationResult
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.registry import MigrationRegistry

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()


# --------------------------------------------------------------------------- #
# Planted migrations — each exercises one visibility axis.
# target_version only orders the planted classes among themselves (they are not
# in the order-manifest, so get_all() sorts them by ascending target_version).
# --------------------------------------------------------------------------- #


class _Base(BaseMigration):
    """A concrete planted migration; apply() is never reached by the read surface."""

    def detect(self, project_path: Path) -> bool:  # noqa: ARG002 - overridden per fake
        return False

    def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:  # noqa: ARG002
        return MigrationResult(success=True, changes_made=[])


class _TrackedApplied(_Base):
    migration_id = "tracked_applied"
    description = "a tracked step already recorded"
    target_version = "3.1.0"


class _CloneLocalInPlace(_Base):
    migration_id = "clone_local_in_place"
    description = "a per-clone step whose effect is present here"
    target_version = "3.2.0"
    clone_local_effect = True

    def detect(self, project_path: Path) -> bool:  # noqa: ARG002
        # OLD state absent ⇒ effect IS in place here.
        return False


class _CloneLocalElsewhere(_Base):
    migration_id = "clone_local_elsewhere"
    description = "a per-clone step recorded but absent on this checkout"
    target_version = "3.3.0"
    clone_local_effect = True

    def detect(self, project_path: Path) -> bool:  # noqa: ARG002
        # OLD state present ⇒ effect is NOT in place here (recorded elsewhere).
        return True


class _TrackedDrifted(_Base):
    migration_id = "tracked_drifted"
    description = "a tracked step whose recorded hash no longer matches"
    target_version = "3.4.0"


class _Pending(_Base):
    migration_id = "pending_step"
    description = "a declared step with no ledger record"
    target_version = "3.5.0"


@pytest.fixture
def registry() -> Iterator[type[MigrationRegistry]]:
    """An empty registry for the test; the real one is restored afterwards.

    Discover first: a migration module imported for the first time inside the
    cleared window would register into the throwaway registry, be wiped by the
    restore, and never register again (the module stays cached in sys.modules).
    """
    auto_discover_migrations()
    saved = dict(MigrationRegistry._migrations)
    MigrationRegistry.clear()
    try:
        yield MigrationRegistry
    finally:
        MigrationRegistry._migrations.clear()
        MigrationRegistry._migrations.update(saved)


@pytest.fixture
def seeded_project(
    registry: type[MigrationRegistry],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """A project with a seeded two-partition ledger and the planted registry.

    ``auto_discover_migrations`` is neutralised so the real migration modules
    do not repopulate the registry over the planted set when the surface (and
    ``applicable_migrations``) calls it.
    """
    monkeypatch.setattr(
        "specify_cli.upgrade.migrations.auto_discover_migrations",
        lambda: None,
    )
    for migration in (_TrackedApplied, _CloneLocalInPlace, _CloneLocalElsewhere, _TrackedDrifted, _Pending):
        registry.register(migration)

    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    ProjectMetadata(version="4.0.0rc7", initialized_at=now_utc()).save(kittify)

    ledger = MigrationLedger(tmp_path)
    # Tracked, applied, no drift: the recorded hash matches the current source.
    ledger.append(build_record(_TrackedApplied(), "success"))
    # Clone-local, applied, effect present here (detect() False ⇒ in place).
    ledger.append(build_record(_CloneLocalInPlace(), "success"))
    # Clone-local, applied, effect ABSENT here (detect() True ⇒ recorded elsewhere).
    ledger.append(build_record(_CloneLocalElsewhere(), "success"))
    # Tracked, applied, DRIFTED: recorded hash does not match the current source.
    ledger.append(
        LedgerRecord(
            id="tracked_drifted",
            applied_at=now_utc(),
            result="success",
            identity="tracked_drifted",
            content_hash="sha256:deadbeef",
            cli_version="test",
        )
    )
    # _Pending is deliberately NOT recorded.

    monkeypatch.chdir(tmp_path)
    return tmp_path


def _snapshot_tree(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


# --------------------------------------------------------------------------- #
# SC-005 — applied set in declared (manifest) order.
# --------------------------------------------------------------------------- #


def test_json_lists_recorded_steps_in_declared_order(seeded_project: Path) -> None:
    result = runner.invoke(app, ["ledger", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)

    ids = [step["id"] for step in payload["steps"]]
    # declared (manifest) order == ascending target_version for the planted set.
    assert ids == [
        "tracked_applied",
        "clone_local_in_place",
        "clone_local_elsewhere",
        "tracked_drifted",
        "pending_step",
    ]
    applied_ids = [step["id"] for step in payload["steps"] if step["applied"]]
    assert applied_ids == ["tracked_applied", "clone_local_in_place", "clone_local_elsewhere", "tracked_drifted"]


def test_human_summary_lists_steps_in_declared_order(seeded_project: Path) -> None:
    result = runner.invoke(app, ["ledger"])
    assert result.exit_code == 0, result.output
    out = result.stdout
    positions = [out.index(mid) for mid in ("tracked_applied", "clone_local_in_place", "clone_local_elsewhere", "pending_step")]
    assert positions == sorted(positions)


# --------------------------------------------------------------------------- #
# SC-005 — recorded-elsewhere vs in-place-here (clone-local detect()).
# --------------------------------------------------------------------------- #


def test_json_distinguishes_recorded_elsewhere_from_in_place(seeded_project: Path) -> None:
    result = runner.invoke(app, ["ledger", "--json"])
    assert result.exit_code == 0, result.output
    by_id = {step["id"]: step for step in json.loads(result.stdout)["steps"]}

    assert by_id["clone_local_in_place"]["partition"] == "clone-local"
    assert by_id["clone_local_in_place"]["in_place_here"] is True
    assert by_id["clone_local_in_place"]["state"] == "in-place"

    assert by_id["clone_local_elsewhere"]["partition"] == "clone-local"
    assert by_id["clone_local_elsewhere"]["in_place_here"] is False
    assert by_id["clone_local_elsewhere"]["state"] == "recorded-elsewhere"

    # A tracked step has no clone-local in-place meaning.
    assert by_id["tracked_applied"]["partition"] == "tracked"
    assert by_id["tracked_applied"]["in_place_here"] is None


def test_human_summary_uses_consumer_language_for_elsewhere(seeded_project: Path) -> None:
    result = runner.invoke(app, ["ledger"])
    assert result.exit_code == 0, result.output
    assert "recorded elsewhere but not here" in result.stdout
    assert "already in place" in result.stdout


# --------------------------------------------------------------------------- #
# SC-005 — drift flag (audit-only, read-only).
# --------------------------------------------------------------------------- #


def test_json_flags_a_drifted_step(seeded_project: Path) -> None:
    result = runner.invoke(app, ["ledger", "--json"])
    assert result.exit_code == 0, result.output
    by_id = {step["id"]: step for step in json.loads(result.stdout)["steps"]}

    assert by_id["tracked_drifted"]["drift"] is True
    assert by_id["tracked_applied"]["drift"] is False
    assert json.loads(result.stdout)["summary"]["drift"] == 1


def test_human_summary_notes_drift_in_consumer_language(seeded_project: Path) -> None:
    result = runner.invoke(app, ["ledger"])
    assert result.exit_code == 0, result.output
    assert "content changed since it ran" in result.stdout


# --------------------------------------------------------------------------- #
# FR-011 — pending sourced from applicable_migrations (the single pending source).
# --------------------------------------------------------------------------- #


def test_json_marks_the_unrecorded_step_pending(seeded_project: Path) -> None:
    result = runner.invoke(app, ["ledger", "--json"])
    assert result.exit_code == 0, result.output
    by_id = {step["id"]: step for step in json.loads(result.stdout)["steps"]}

    assert by_id["pending_step"]["pending"] is True
    assert by_id["pending_step"]["applied"] is False
    # A settled (success-recorded) step is not pending.
    assert by_id["tracked_applied"]["pending"] is False
    assert json.loads(result.stdout)["summary"]["pending"] == 1


# --------------------------------------------------------------------------- #
# SC-005 — the surface is READ-ONLY: no commit, no file write.
# --------------------------------------------------------------------------- #


def test_surface_writes_nothing(seeded_project: Path) -> None:
    before = _snapshot_tree(seeded_project)
    result = runner.invoke(app, ["ledger"])
    assert result.exit_code == 0, result.output
    result_json = runner.invoke(app, ["ledger", "--json"])
    assert result_json.exit_code == 0, result_json.output
    after = _snapshot_tree(seeded_project)
    assert after == before  # no file created, removed, or rewritten


# --------------------------------------------------------------------------- #
# No project ⇒ a clean structured error (not a traceback).
# --------------------------------------------------------------------------- #


def test_no_project_root_exits_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)  # a bare dir with no .kittify/ in any parent
    monkeypatch.setattr(
        "specify_cli.cli.commands.migrate_cmd.locate_project_root",
        lambda *a, **k: None,
    )
    result = runner.invoke(app, ["ledger"])
    assert result.exit_code == 1
