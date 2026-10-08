"""``runs_first`` ordering and version-independent selection (#3732, WP10 T050/T054).

Planted migration classes only: the global registry is snapshotted and
restored around every test, so nothing leaks into other tests.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from kernel.clock import now_utc
from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations.base import BaseMigration, MigrationResult
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.runner import MigrationRunner

pytestmark = [pytest.mark.unit, pytest.mark.fast]

#: The file a planted migration's content-driven ``detect()`` looks for.
LEGACY_MARKER = "legacy-state.txt"
#: The file a planted migration's ``structural_detect()`` looks for.
STRUCTURAL_MARKER = "structural-state.txt"
FIRST_ID = "planted_runs_first"


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


def _planted(name: str, target: str, *, first: bool = False, detected: bool = False) -> type[BaseMigration]:
    """A planted migration class (not registered)."""

    class Planted(BaseMigration):
        migration_id = name
        description = f"planted {name}"
        target_version = target
        runs_first = first

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


def _register_abf(registry: type[MigrationRegistry], *, first_target: str = "9.9.9") -> None:
    registry.register(_planted("planted_a", "3.1.0"))
    registry.register(_planted("planted_b", "3.2.0"))
    registry.register(_planted(FIRST_ID, first_target, first=True))


def _ids(migrations: list[BaseMigration]) -> list[str]:
    return [m.migration_id for m in migrations]


def _project(tmp_path: Path, version: str, *, recorded: tuple[str, ...] = ()) -> Path:
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    metadata = ProjectMetadata(version=version, initialized_at=now_utc())
    for migration_id in recorded:
        metadata.record_migration(migration_id, "success")
    metadata.save(kittify)
    return tmp_path


# --------------------------------------------------------------------------------------
# Ordering
# --------------------------------------------------------------------------------------


def test_runs_first_leads_then_version_order(registry: type[MigrationRegistry]) -> None:
    _register_abf(registry)
    assert _ids(registry.get_applicable("3.0.0", "9.9.9")) == [FIRST_ID, "planted_a", "planted_b"]


def test_get_all_stays_in_version_order(registry: type[MigrationRegistry]) -> None:
    _register_abf(registry)
    assert _ids(registry.get_all()) == ["planted_a", "planted_b", FIRST_ID]


def test_same_version_selection_still_works_and_first_still_leads(registry: type[MigrationRegistry], tmp_path: Path) -> None:
    registry.register(_planted("planted_a", "3.1.0", detected=True))
    registry.register(_planted("planted_b", "3.2.0"))
    registry.register(_planted(FIRST_ID, "3.1.0", first=True, detected=True))
    project = _project(tmp_path, "3.1.0")

    assert _ids(registry.get_applicable("3.1.0", "3.2.0", project_path=project)) == [FIRST_ID, "planted_a", "planted_b"]


def test_second_runs_first_class_is_refused_naming_both(registry: type[MigrationRegistry]) -> None:
    registry.register(_planted(FIRST_ID, "4.0.0", first=True))
    second = _planted("planted_second_first", "4.0.0", first=True)

    with pytest.raises(ValueError, match="at most one migration may run first") as excinfo:
        registry.register(second)

    assert "Planted_planted_runs_first" in str(excinfo.value)
    assert "Planted_planted_second_first" in str(excinfo.value)
    assert "planted_second_first" not in registry._migrations


def test_without_runs_first_order_is_unchanged(registry: type[MigrationRegistry], tmp_path: Path) -> None:
    """Regression pin: no ``runs_first`` class -> the old window + same-version order."""
    registry.register(_planted("planted_c", "3.3.0"))
    registry.register(_planted("planted_a", "3.1.0", detected=True))
    registry.register(_planted("planted_b", "3.2.0"))
    project = _project(tmp_path, "3.1.0")

    assert _ids(registry.get_applicable("3.0.0", "3.3.0")) == ["planted_a", "planted_b", "planted_c"]
    assert _ids(registry.get_applicable("3.1.0", "3.3.0", project_path=project)) == ["planted_a", "planted_b", "planted_c"]


# --------------------------------------------------------------------------------------
# Version-independent selection
# --------------------------------------------------------------------------------------


def test_project_stamped_above_target_with_legacy_content_selects_runs_first(registry: type[MigrationRegistry], tmp_path: Path) -> None:
    _register_abf(registry, first_target="4.0.0")
    project = _project(tmp_path, "4.1.0")
    (project / LEGACY_MARKER).write_text("legacy", encoding="utf-8")

    assert _ids(registry.get_applicable("4.1.0", "4.2.0", project_path=project)) == [FIRST_ID]


def test_project_stamped_above_target_without_legacy_content_selects_nothing(registry: type[MigrationRegistry], tmp_path: Path) -> None:
    _register_abf(registry, first_target="4.0.0")
    project = _project(tmp_path, "4.1.0")

    assert registry.get_applicable("4.1.0", "4.2.0", project_path=project) == []


def test_outside_window_needs_a_project_path(registry: type[MigrationRegistry]) -> None:
    _register_abf(registry, first_target="4.0.0")
    assert registry.get_applicable("4.1.0", "4.2.0") == []


def test_recorded_with_structural_state_is_reselected(registry: type[MigrationRegistry], tmp_path: Path) -> None:
    _register_abf(registry, first_target="4.0.0")
    project = _project(tmp_path, "4.1.0", recorded=(FIRST_ID,))
    (project / STRUCTURAL_MARKER).write_text("legacy root", encoding="utf-8")

    assert _ids(registry.get_applicable("4.1.0", "4.2.0", project_path=project)) == [FIRST_ID]


def test_recorded_without_structural_state_is_not_reselected(registry: type[MigrationRegistry], tmp_path: Path) -> None:
    _register_abf(registry, first_target="4.0.0")
    project = _project(tmp_path, "4.1.0", recorded=(FIRST_ID,))
    (project / LEGACY_MARKER).write_text("detect() alone is true", encoding="utf-8")

    assert registry.get_applicable("4.1.0", "4.2.0", project_path=project) == []


def test_structural_detect_defaults_to_false_and_never_reselects_a_normal_migration(tmp_path: Path) -> None:
    normal = _planted("planted_normal", "3.1.0")()
    (tmp_path / STRUCTURAL_MARKER).write_text("x", encoding="utf-8")
    assert BaseMigration.structural_detect(normal, tmp_path) is False
    assert normal.reselect_when_recorded(tmp_path) is False


# --------------------------------------------------------------------------------------
# Runner: a recorded runs_first migration is applied again on structural state
# --------------------------------------------------------------------------------------


def _run(project: Path) -> tuple[list[str], list[str]]:
    result = MigrationRunner(project).upgrade("4.2.0", include_worktrees=False)
    assert result.success, result.errors
    return result.migrations_applied, result.migrations_skipped


def test_runner_reapplies_recorded_runs_first_on_structural_state(registry: type[MigrationRegistry], tmp_path: Path) -> None:
    _register_abf(registry, first_target="4.0.0")
    project = _project(tmp_path, "4.1.0", recorded=(FIRST_ID,))
    (project / STRUCTURAL_MARKER).write_text("legacy root", encoding="utf-8")
    (project / LEGACY_MARKER).write_text("legacy", encoding="utf-8")

    applied, _skipped = _run(project)

    assert applied == [FIRST_ID]
    assert (project / f"applied-{FIRST_ID}.txt").exists()


def test_runner_skips_recorded_runs_first_without_structural_state(registry: type[MigrationRegistry], tmp_path: Path) -> None:
    """In the version window and recorded: the recorded result still settles it."""
    _register_abf(registry, first_target="4.2.0")
    project = _project(tmp_path, "4.1.0", recorded=(FIRST_ID,))
    (project / LEGACY_MARKER).write_text("legacy", encoding="utf-8")

    applied, skipped = _run(project)

    assert applied == []
    assert skipped == [FIRST_ID]
    assert not (project / f"applied-{FIRST_ID}.txt").exists()


# --------------------------------------------------------------------------------------
# Selector parity: detector and compat planner report the runs_first migration first
# --------------------------------------------------------------------------------------


def test_detector_and_planner_report_runs_first_first(registry: type[MigrationRegistry], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.upgrade.migrations as migrations_pkg
    from specify_cli.compat import planner
    from specify_cli.upgrade.detector import VersionDetector

    # Keep the planted registry: discovery would re-register the real migrations.
    monkeypatch.setattr(migrations_pkg, "auto_discover_migrations", lambda: None)
    monkeypatch.setattr(planner, "_REGISTRY_AUTOLOADED", True)
    _register_abf(registry, first_target="4.0.0")
    project = _project(tmp_path, "3.0.0")

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

    assert detected == [FIRST_ID, "planted_a", "planted_b"]
    assert previewed == detected
