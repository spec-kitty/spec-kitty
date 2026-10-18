"""Selection ordering + ledger-diff selection after the authority flip (WP02, ADR 2026-10-17-1).

The version window is RETIRED as the applied authority. Selection is now
**ledger-diff**: a declared migration (in order-manifest order) is selected when
its id is not recorded in the partition that is authoritative for it, OR when
``reselect_when_recorded`` forces it (a ``runs_first`` migration whose
``structural_detect`` reports the legacy state present). Ordering is the
checked-in order manifest; ``Version(target_version)`` is demoted to a fallback
for migrations absent from the manifest (the planted classes these tests
register). ``runs_first`` no longer front-pulls — the manifest owns order, and
its one annotated runs-first lead (the backfill) leads by sitting at index 0.

Planted migration classes only (plus one real-registry get_all smoke test): the
global registry is snapshotted and restored around every test.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from kernel.clock import now_utc
from packaging.version import Version
from specify_cli.upgrade.ledger import LedgerRecord, MigrationLedger, build_record
from specify_cli.upgrade.manifest import load_order_manifest
from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations.base import BaseMigration, MigrationResult
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.runner import MigrationRunner

pytestmark = [pytest.mark.unit, pytest.mark.fast]

#: The file a planted migration's content-driven ``detect()`` looks for.
LEGACY_MARKER = "legacy-state.txt"
#: The file a planted migration's ``structural_detect()`` looks for.
STRUCTURAL_MARKER = "structural-state.txt"
FIRST_ID = "planted_runs_first"
#: The one annotated runs-first lead in the real order manifest.
BACKFILL_ID = "4.0.0rc8_backfill_migration_ledger"


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


def _planted(
    name: str,
    target: str,
    *,
    first: bool = False,
    detected: bool = False,
    clone_local: bool = False,
) -> type[BaseMigration]:
    """A planted migration class (not registered)."""

    class Planted(BaseMigration):
        migration_id = name
        description = f"planted {name}"
        target_version = target
        runs_first = first
        clone_local_effect = clone_local

        def detect(self, project_path: Path) -> bool:
            return detected or (project_path / LEGACY_MARKER).exists()

        def structural_detect(self, project_path: Path) -> bool:
            return (project_path / STRUCTURAL_MARKER).exists()

        def can_apply(self, project_path: Path) -> tuple[bool, str]:
            return True, ""

        def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
            if not dry_run:
                (project_path / f"applied-{name}.txt").write_text("x", encoding="utf-8")
            return MigrationResult(success=True, changes_made=[f"applied {name}"])

    Planted.__name__ = Planted.__qualname__ = f"Planted_{name}"
    return Planted


def _register_abf(registry: type[MigrationRegistry], *, first_target: str = "9.9.9", detected: bool = False) -> None:
    registry.register(_planted("planted_a", "3.1.0", detected=detected))
    registry.register(_planted("planted_b", "3.2.0", detected=detected))
    registry.register(_planted(FIRST_ID, first_target, first=True, detected=detected))


def _ids(migrations: list[BaseMigration]) -> list[str]:
    return [m.migration_id for m in migrations]


def _project(tmp_path: Path, version: str) -> Path:
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    ProjectMetadata(version=version, initialized_at=now_utc()).save(kittify)
    return tmp_path


def _record_in_ledger(project: Path, migration: BaseMigration, result: str = "success") -> None:
    """Record *migration* applied in its authoritative ledger partition."""
    MigrationLedger(project).append(build_record(migration, result))


# --------------------------------------------------------------------------------------
# Ordering: the order manifest is the authority; version is the fallback cross-check
# --------------------------------------------------------------------------------------


def test_get_all_falls_back_to_version_order_for_non_manifest_migrations(registry: type[MigrationRegistry]) -> None:
    """Planted classes are NOT in the real manifest, so they sort by the demoted
    ``Version(target_version)`` fallback -- the only order get_all can give them."""
    _register_abf(registry)
    assert _ids(registry.get_all()) == ["planted_a", "planted_b", FIRST_ID]


def test_get_all_follows_manifest_index_overriding_version(registry: type[MigrationRegistry], monkeypatch: pytest.MonkeyPatch) -> None:
    """get_all orders by MANIFEST INDEX, not version: a manifest that reverses the
    version order is honoured verbatim (the demoted version key never fights it)."""
    registry.register(_planted("planted_a", "3.1.0"))
    registry.register(_planted("planted_b", "3.2.0"))
    # Manifest deliberately contradicts version order (b before a):
    monkeypatch.setattr("specify_cli.upgrade.registry.load_order_manifest", lambda: ["planted_b", "planted_a"])
    assert _ids(registry.get_all()) == ["planted_b", "planted_a"]


def test_real_get_all_is_manifest_order_with_backfill_leading(registry: type[MigrationRegistry]) -> None:
    """Honest end-to-end: the REAL registry's get_all equals the order manifest, and the
    runs-first backfill (target 4.0.0rc8) leads despite its late version slot (NFR-004)."""
    from specify_cli.upgrade.migrations import auto_discover_migrations

    MigrationRegistry.clear()
    auto_discover_migrations()

    all_ids = _ids(MigrationRegistry.get_all())
    assert all_ids == load_order_manifest()  # get_all CONSUMES the manifest
    assert all_ids[0] == BACKFILL_ID  # the annotated runs-first lead is first
    # Proof it is NOT version order: rc8 is greater than the version at index 1,
    # so pure version-sort would place the backfill last, not first.
    second = MigrationRegistry.get_by_id(all_ids[1])
    assert second is not None
    assert Version("4.0.0rc8") > Version(second.target_version)


# --------------------------------------------------------------------------------------
# Ledger-diff selection (version window retired)
# --------------------------------------------------------------------------------------


def test_get_applicable_without_path_returns_all_declared_in_order(registry: type[MigrationRegistry]) -> None:
    """No project_path ⇒ no ledger to diff ⇒ every declared migration, in get_all order.
    ``runs_first`` no longer front-pulls: FIRST_ID (9.9.9) sorts last by the version fallback."""
    _register_abf(registry)
    assert _ids(registry.get_applicable("0.0.0", "9.9.9")) == ["planted_a", "planted_b", FIRST_ID]


def test_get_applicable_excludes_a_ledger_recorded_migration(registry: type[MigrationRegistry], tmp_path: Path) -> None:
    _register_abf(registry, detected=True)  # detect() True ⇒ they pass the needed/applicable filter
    project = _project(tmp_path, "4.1.0")
    _record_in_ledger(project, _planted("planted_a", "3.1.0")())

    selected = _ids(registry.get_applicable("0.0.0", "9.9.9", project_path=project))
    assert "planted_a" not in selected
    assert "planted_b" in selected
    assert FIRST_ID in selected


def test_get_applicable_version_stamp_is_irrelevant(registry: type[MigrationRegistry], tmp_path: Path) -> None:
    """A project stamped well ABOVE every target still selects an unrecorded migration:
    the version window is gone, only the ledger (plus the needed/applicable filter) decides."""
    registry.register(_planted("planted_sub", "0.13.1", detected=True))
    project = _project(tmp_path, "4.1.0")  # far above 0.13.1; empty ledger

    assert _ids(registry.get_applicable("4.1.0", "4.1.0", project_path=project)) == ["planted_sub"]


# --------------------------------------------------------------------------------------
# runs_first reselection: structural_detect re-selects a LEDGER-recorded migration
# --------------------------------------------------------------------------------------


def test_runs_first_recorded_with_structural_state_is_reselected(registry: type[MigrationRegistry], tmp_path: Path) -> None:
    _register_abf(registry, first_target="4.0.0")
    project = _project(tmp_path, "4.1.0")
    _record_in_ledger(project, _planted(FIRST_ID, "4.0.0", first=True)())
    (project / STRUCTURAL_MARKER).write_text("legacy root", encoding="utf-8")

    assert FIRST_ID in _ids(registry.get_applicable("4.1.0", "4.2.0", project_path=project))


def test_runs_first_recorded_without_structural_state_is_not_reselected(registry: type[MigrationRegistry], tmp_path: Path) -> None:
    _register_abf(registry, first_target="4.0.0")
    project = _project(tmp_path, "4.1.0")
    _record_in_ledger(project, _planted(FIRST_ID, "4.0.0", first=True)())
    # A content-driven detect() alone must NOT reselect a recorded runs_first migration.
    (project / LEGACY_MARKER).write_text("detect() alone is true", encoding="utf-8")

    assert FIRST_ID not in _ids(registry.get_applicable("4.1.0", "4.2.0", project_path=project))


def test_structural_detect_defaults_to_false_and_never_reselects_a_normal_migration(tmp_path: Path) -> None:
    normal = _planted("planted_normal", "3.1.0")()
    (tmp_path / STRUCTURAL_MARKER).write_text("x", encoding="utf-8")
    assert BaseMigration.structural_detect(normal, tmp_path) is False
    assert normal.reselect_when_recorded(tmp_path) is False


def test_clone_local_no_longer_reselects_via_reselect_hook(tmp_path: Path) -> None:
    """Regression pin for the C3 collapse: ``reselect_when_recorded`` no longer fires for a
    clone-local migration (the per-clone PARTITION owns that now), only for runs_first+structural."""
    clone_local = _planted("planted_cl", "3.1.0", detected=True, clone_local=True)()
    assert clone_local.reselect_when_recorded(tmp_path) is False


def test_second_runs_first_class_is_refused_naming_both(registry: type[MigrationRegistry]) -> None:
    registry.register(_planted(FIRST_ID, "4.0.0", first=True))
    second = _planted("planted_second_first", "4.0.0", first=True)

    with pytest.raises(ValueError, match="at most one migration may run first") as excinfo:
        registry.register(second)

    assert "Planted_planted_runs_first" in str(excinfo.value)
    assert "Planted_planted_second_first" in str(excinfo.value)
    assert "planted_second_first" not in registry._migrations


# --------------------------------------------------------------------------------------
# Clone-local selection is the per-clone PARTITION's job (replaces #6233 machinery)
# --------------------------------------------------------------------------------------


def test_clone_local_unrecorded_in_per_clone_ledger_is_selected(registry: type[MigrationRegistry], tmp_path: Path) -> None:
    """A pulled clone's per-clone ledger is empty ⇒ ledger-diff selects the clone-local
    migration -- exactly what the deleted ``_clone_local_selected_below_window`` carried."""
    registry.register(_planted("planted_cl_sub", "0.13.1", clone_local=True, detected=True))
    project = _project(tmp_path, "4.0.0rc7")  # empty ledger

    assert _ids(registry.get_applicable("4.0.0rc7", "4.0.0rc7", project_path=project)) == ["planted_cl_sub"]


def test_clone_local_recorded_only_in_tracked_partition_is_still_selected(registry: type[MigrationRegistry], tmp_path: Path) -> None:
    """Partition routing proof: a clone-local migration's authority is the PER-CLONE ledger.
    A record sitting in the wrong (tracked) partition -- as a pushed tracked ledger would carry
    for a different clone -- does NOT settle it on THIS checkout."""
    registry.register(_planted("planted_cl_sub", "0.13.1", clone_local=True, detected=True))
    project = _project(tmp_path, "4.0.0rc7")
    # Force a record into the TRACKED partition (clone_local=False) even though the migration is clone-local.
    MigrationLedger(project).append(
        LedgerRecord(
            id="planted_cl_sub",
            applied_at=now_utc(),
            result="success",
            identity="planted_cl_sub",
            content_hash="",
            cli_version="test",
            clone_local=False,
        )
    )

    assert _ids(registry.get_applicable("4.0.0rc7", "4.0.0rc7", project_path=project)) == ["planted_cl_sub"]


def test_clone_local_recorded_in_per_clone_ledger_is_not_selected(registry: type[MigrationRegistry], tmp_path: Path) -> None:
    registry.register(_planted("planted_cl_settled", "0.13.1", clone_local=True, detected=True))
    project = _project(tmp_path, "4.0.0rc7")
    _record_in_ledger(project, _planted("planted_cl_settled", "0.13.1", clone_local=True, detected=True)())

    assert registry.get_applicable("4.0.0rc7", "4.0.0rc7", project_path=project) == []


def test_tracked_recorded_migration_stays_out(registry: type[MigrationRegistry], tmp_path: Path) -> None:
    """A TRACKED (non-clone-local) migration recorded in the tracked ledger is settled."""
    registry.register(_planted("planted_tracked_sub", "0.13.1", clone_local=False, detected=True))
    project = _project(tmp_path, "4.0.0rc7")
    _record_in_ledger(project, _planted("planted_tracked_sub", "0.13.1", detected=True)())

    assert registry.get_applicable("4.0.0rc7", "4.0.0rc7", project_path=project) == []


def test_clone_local_selected_in_manifest_order_not_front(registry: type[MigrationRegistry], tmp_path: Path) -> None:
    """Clone-local migrations are NOT runs_first and do not front-pull: they appear in
    get_all (version-fallback) order among the selected set."""
    registry.register(_planted("planted_cl_sub", "0.13.1", clone_local=True, detected=True))
    registry.register(_planted("planted_window_mig", "4.1.0", detected=True))
    registry.register(_planted(FIRST_ID, "4.0.0", first=True, detected=True))
    project = _project(tmp_path, "4.0.0rc7")  # empty ledger ⇒ all three pending

    # Version-fallback order: 0.13.1 < 4.0.0 < 4.1.0.
    assert _ids(registry.get_applicable("4.0.0rc7", "4.2.0", project_path=project)) == [
        "planted_cl_sub",
        FIRST_ID,
        "planted_window_mig",
    ]


# --------------------------------------------------------------------------------------
# Runner: the skip gate reads the LEDGER (clone-local via per-clone partition)
# --------------------------------------------------------------------------------------


def test_runner_applies_clone_local_when_per_clone_ledger_empty(tmp_path: Path) -> None:
    """A clone-local migration whose per-clone ledger lacks it is applied (detect() True)."""
    migration = _planted("planted_clone_local", "3.1.0", detected=True, clone_local=True)()
    project = _project(tmp_path, "3.1.0")

    _result, status = MigrationRunner(project)._apply_migration(migration, ProjectMetadata.load(project / ".kittify"), dry_run=False)
    assert status == "applied"
    assert (project / "applied-planted_clone_local.txt").exists()


def test_runner_skips_clone_local_recorded_in_per_clone_ledger(tmp_path: Path) -> None:
    migration = _planted("planted_clone_local_settled", "3.1.0", detected=True, clone_local=True)()
    project = _project(tmp_path, "3.1.0")
    _record_in_ledger(project, migration)

    _result, status = MigrationRunner(project)._apply_migration(migration, ProjectMetadata.load(project / ".kittify"), dry_run=False)
    assert status == "skipped"


def test_runner_skips_tracked_recorded_migration(tmp_path: Path) -> None:
    migration = _planted("planted_tracked", "3.1.0", detected=True)()
    project = _project(tmp_path, "3.1.0")
    _record_in_ledger(project, migration)

    assert migration.clone_local_effect is False
    _result, status = MigrationRunner(project)._apply_migration(migration, ProjectMetadata.load(project / ".kittify"), dry_run=False)
    assert status == "skipped"
    assert not (project / "applied-planted_tracked.txt").exists()


# --------------------------------------------------------------------------------------
# Runner: a recorded runs_first migration re-applies on structural state
# --------------------------------------------------------------------------------------


def _run(project: Path) -> tuple[list[str], list[str]]:
    result = MigrationRunner(project).upgrade("4.2.0", include_worktrees=False)
    assert result.success, result.errors
    return result.migrations_applied, result.migrations_skipped


def test_runner_reapplies_recorded_runs_first_on_structural_state(registry: type[MigrationRegistry], tmp_path: Path) -> None:
    _register_abf(registry, first_target="4.0.0")
    project = _project(tmp_path, "4.1.0")
    _record_in_ledger(project, _planted(FIRST_ID, "4.0.0", first=True)())
    (project / STRUCTURAL_MARKER).write_text("legacy root", encoding="utf-8")
    (project / LEGACY_MARKER).write_text("legacy", encoding="utf-8")

    applied, _skipped = _run(project)

    assert FIRST_ID in applied
    assert (project / f"applied-{FIRST_ID}.txt").exists()


def test_runner_does_not_reapply_recorded_runs_first_without_structural_state(registry: type[MigrationRegistry], tmp_path: Path) -> None:
    """A recorded runs_first migration with no structural state is EXCLUDED at selection
    (ledger-diff), so the runner never processes it -- not applied and not classified
    "skipped" (that classification only happens for a migration the selection returned)."""
    _register_abf(registry, first_target="4.2.0")
    project = _project(tmp_path, "4.1.0")
    _record_in_ledger(project, _planted(FIRST_ID, "4.2.0", first=True)())
    (project / LEGACY_MARKER).write_text("legacy", encoding="utf-8")

    applied, skipped = _run(project)

    assert FIRST_ID not in applied
    assert FIRST_ID not in skipped  # excluded at selection, never processed
    assert not (project / f"applied-{FIRST_ID}.txt").exists()


# --------------------------------------------------------------------------------------
# Selector parity: detector and compat planner mirror get_applicable
# --------------------------------------------------------------------------------------


def test_detector_preview_reflects_ledger_diff_selection(registry: type[MigrationRegistry], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Preview parity: the detector's applicable_migrations mirrors get_applicable, so a
    --dry-run truthfully reports an unrecorded clone-local migration that would apply."""
    import specify_cli.upgrade.migrations as migrations_pkg
    from specify_cli.upgrade.detector import VersionDetector

    monkeypatch.setattr(migrations_pkg, "auto_discover_migrations", lambda: None)
    registry.register(_planted("planted_cl_sub", "0.13.1", clone_local=True, detected=True))
    project = _project(tmp_path, "4.0.0rc7")

    previewed = _ids(VersionDetector(project).applicable_migrations("4.0.0rc7"))
    assert previewed == ["planted_cl_sub"]


def test_detector_and_planner_mirror_get_applicable(registry: type[MigrationRegistry], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.upgrade.migrations as migrations_pkg
    from specify_cli.compat import planner
    from specify_cli.upgrade.detector import VersionDetector

    monkeypatch.setattr(migrations_pkg, "auto_discover_migrations", lambda: None)
    monkeypatch.setattr(planner, "_REGISTRY_AUTOLOADED", True)
    _register_abf(registry, first_target="4.0.0", detected=True)
    project = _project(tmp_path, "3.0.0")  # empty ledger ⇒ all pending

    detected = _ids(VersionDetector(project).applicable_migrations("4.0.0"))
    status = planner.ProjectStatus(
        state=planner.ProjectState.COMPATIBLE,
        project_root=project,
        schema_version=None,
        min_supported=0,
        max_supported=0,
        metadata_error=None,
    )
    previewed = [step.migration_id for step in planner._pending_migrations_for(status, "4.0.0")]

    # Version-fallback order (no runs_first front-pull): 3.1.0, 3.2.0, 4.0.0.
    assert detected == ["planted_a", "planted_b", FIRST_ID]
    assert previewed == detected
