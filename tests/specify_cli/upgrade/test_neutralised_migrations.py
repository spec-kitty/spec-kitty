"""Neutralised migrations are recorded no-ops (#3732, WP10 T051/T054).

``3.2.0rc35_default_charter_pack``, ``normalize_activation_absence`` and
``2.1.2_fix_glossary_context_skill`` keep their ids so recorded upgrade
history stays meaningful, but never act: ``detect()`` is false even on the
exact shape their old bodies handled, and the runner records them as
``skipped / "Not applicable"``.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from kernel.clock import now_utc
from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations.base import BaseMigration
from specify_cli.upgrade.migrations.m_2_1_2_fix_glossary_context_skill import FixGlossaryContextSkillMigration
from specify_cli.upgrade.migrations.m_3_2_0rc35_default_charter_pack import DefaultCharterPackMigration
from specify_cli.upgrade.migrations.m_3_2_x_normalize_activation_absence import NormalizeActivationAbsenceMigration
from specify_cli.upgrade.runner import MigrationRunner

pytestmark = [pytest.mark.unit, pytest.mark.fast]

SUPERSEDED = "Superseded by the charter-pack cutover"


def _config_without_per_kind_keys(project: Path) -> None:
    """The shape the rc35 seed and the normalizer acted on: absent per-kind keys."""
    kittify = project / ".kittify"
    (kittify / "charter").mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text("agents:\n  available:\n  - claude\ncharter: .kittify/charter/charter.yaml\n", encoding="utf-8")
    (kittify / "charter" / "charter.yaml").write_text("schema_version: '2.0.0'\n", encoding="utf-8")


def _old_glossary_skill(project: Path) -> None:
    """The shape the 2.1.2 glossary-context fix acted on: an old-marker SKILL.md."""
    skill = project / ".claude" / "skills" / "spec-kitty-glossary-context" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("## Step 1: Locate Glossary Context\n\nIdentify the glossary state\n", encoding="utf-8")


CASES: list[tuple[type[BaseMigration], str, str, Callable[[Path], None]]] = [
    (DefaultCharterPackMigration, "3.2.0rc35_default_charter_pack", "3.2.0rc35", _config_without_per_kind_keys),
    (NormalizeActivationAbsenceMigration, "normalize_activation_absence", "3.2.6rc1", _config_without_per_kind_keys),
    (FixGlossaryContextSkillMigration, "2.1.2_fix_glossary_context_skill", "2.1.2", _old_glossary_skill),
]
IDS = [case[1] for case in CASES]


def _tree_snapshot(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


@pytest.mark.parametrize(("cls", "migration_id", "target_version", "old_shape"), CASES, ids=IDS)
def test_identity_unchanged(cls: type[BaseMigration], migration_id: str, target_version: str, old_shape: Callable[[Path], None]) -> None:
    assert cls.migration_id == migration_id
    assert cls.target_version == target_version


@pytest.mark.parametrize(("cls", "migration_id", "target_version", "old_shape"), CASES, ids=IDS)
def test_detect_false_on_empty_and_on_old_shape(
    tmp_path: Path, cls: type[BaseMigration], migration_id: str, target_version: str, old_shape: Callable[[Path], None]
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    shaped = tmp_path / "shaped"
    shaped.mkdir()
    old_shape(shaped)

    assert cls().detect(empty) is False
    assert cls().detect(shaped) is False


@pytest.mark.parametrize(("cls", "migration_id", "target_version", "old_shape"), CASES, ids=IDS)
def test_can_apply_refuses_and_apply_changes_nothing(
    tmp_path: Path, cls: type[BaseMigration], migration_id: str, target_version: str, old_shape: Callable[[Path], None]
) -> None:
    old_shape(tmp_path)
    before = _tree_snapshot(tmp_path)

    assert cls().can_apply(tmp_path) == (False, SUPERSEDED)
    result = cls().apply(tmp_path)

    assert result.success is True
    assert result.changes_made == []
    assert result.warnings == [SUPERSEDED]
    assert _tree_snapshot(tmp_path) == before


@pytest.mark.parametrize(("cls", "migration_id", "target_version", "old_shape"), CASES, ids=IDS)
def test_runner_records_skipped_not_applicable(
    tmp_path: Path, cls: type[BaseMigration], migration_id: str, target_version: str, old_shape: Callable[[Path], None]
) -> None:
    old_shape(tmp_path)
    kittify = tmp_path / ".kittify"
    kittify.mkdir(exist_ok=True)
    metadata = ProjectMetadata(version="2.0.0", initialized_at=now_utc())
    metadata.save(kittify)

    result, status = MigrationRunner(tmp_path)._apply_migration(cls(), metadata, dry_run=False)

    assert status == "skipped"
    assert result.success is True
    reloaded = ProjectMetadata.load(kittify)
    assert reloaded is not None
    (record,) = [m for m in reloaded.applied_migrations if m.id == migration_id]
    assert (record.result, record.notes) == ("skipped", "Not applicable")
