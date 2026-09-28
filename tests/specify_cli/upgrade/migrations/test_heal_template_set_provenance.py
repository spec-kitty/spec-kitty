"""Forward migration tests for legacy built-in template-set provenance."""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from specify_cli.upgrade.migrations.m_4_0_0rc5_heal_template_set_provenance import (
    MIGRATION_ID,
    TARGET_VERSION,
    HealTemplateSetProvenanceMigration,
)
from specify_cli.upgrade.registry import MigrationRegistry

pytestmark = [pytest.mark.unit]


@pytest.fixture
def packs_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "packs"
    (root / "built-in" / "missions" / "software-dev").mkdir(parents=True)
    monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(root))
    return root


def _charter_path(project_root: Path) -> Path:
    return project_root / ".kittify" / "charter" / "charter.yaml"


def _write_charter(path: Path, refs: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    YAML().dump(
        {
            "schema_version": "2.0.0",
            "governance": {"testing": {}},
            "directives": [],
            "catalog": {
                "mission": "software-dev",
                "template_set": "software-dev-default",
                "languages": [],
                "references": refs,
            },
            "overrides": {},
            "metadata": {"bundle_schema_version": 2},
        },
        path.open("w", encoding="utf-8"),
    )


def _template_ref(source_path: str) -> dict[str, str]:
    return {
        "id": "TEMPLATE_SET:software-dev-default",
        "kind": "template_set",
        "title": "software-dev-default",
        "summary": "Built-in template set",
        "source_path": source_path,
        "local_path": "_LIBRARY/template-set-software-dev-default.md",
    }


def test_forward_migration_is_registered_at_current_release_version() -> None:
    migration = MigrationRegistry.get_by_id(MIGRATION_ID)

    assert migration is not None
    assert migration.target_version == TARGET_VERSION == "4.0.0rc5"
    assert migration.runs_on_worktrees is False


def test_current_version_project_still_selects_new_migration_when_needed(tmp_path: Path, packs_root: Path) -> None:
    path = packs_root / "built-in" / "missions" / "software-dev" / "mission.yaml"
    _write_charter(_charter_path(tmp_path), [_template_ref(str(path))])

    applicable = MigrationRegistry.get_applicable(TARGET_VERSION, TARGET_VERSION, tmp_path)

    assert any(migration.migration_id == MIGRATION_ID for migration in applicable)


def test_template_set_migration_rewrites_only_builtin_absolute_source(tmp_path: Path, packs_root: Path) -> None:
    abs_source = packs_root / "built-in" / "missions" / "software-dev" / "mission.yaml"
    abs_paradigm = packs_root / "built-in" / "paradigms" / "atomic-design.yaml"
    charter_path = _charter_path(tmp_path)
    _write_charter(
        charter_path,
        [
            _template_ref(str(abs_source)),
            {
                "id": "PARADIGM:atomic-design",
                "kind": "paradigm",
                "title": "Atomic Design",
                "summary": "other migration owns this row",
                "source_path": str(abs_paradigm),
                "local_path": "_LIBRARY/paradigm-atomic-design.md",
            },
        ],
    )
    migration = HealTemplateSetProvenanceMigration()

    assert migration.detect(tmp_path) is True
    result = migration.apply(tmp_path)

    data = YAML(typ="safe").load(charter_path.read_text(encoding="utf-8"))
    refs = {ref["id"]: ref for ref in data["catalog"]["references"]}
    assert result.success is True
    assert len(result.changes_made) == 1
    assert refs["TEMPLATE_SET:software-dev-default"]["source_path"] == ("${SPEC_KITTY_PACKS_ROOT}/built-in/missions/software-dev/mission.yaml")
    assert refs["PARADIGM:atomic-design"]["source_path"] == str(abs_paradigm)


def test_template_set_migration_recognizes_missing_path_from_another_checkout(tmp_path: Path, packs_root: Path) -> None:
    stale_source = tmp_path / "former-checkout" / "packs" / "built-in" / "missions" / "software-dev" / "mission.yaml"
    charter_path = _charter_path(tmp_path)
    _write_charter(charter_path, [_template_ref(str(stale_source))])
    migration = HealTemplateSetProvenanceMigration()

    assert not stale_source.exists()
    assert migration.detect(tmp_path) is True
    result = migration.apply(tmp_path)
    data = YAML(typ="safe").load(charter_path.read_text(encoding="utf-8"))
    assert result.success is True
    assert data["catalog"]["references"][0]["source_path"] == ("${SPEC_KITTY_PACKS_ROOT}/built-in/missions/software-dev/mission.yaml")


def test_template_set_migration_repairs_path_while_former_checkout_still_exists(tmp_path: Path, packs_root: Path) -> None:
    stale_source = tmp_path / "former-checkout" / "packs" / "built-in" / "missions" / "software-dev" / "mission.yaml"
    stale_source.parent.mkdir(parents=True)
    stale_source.write_text("name: software-dev\n", encoding="utf-8")
    charter_path = _charter_path(tmp_path)
    _write_charter(charter_path, [_template_ref(str(stale_source))])
    migration = HealTemplateSetProvenanceMigration()

    assert migration.detect(tmp_path) is True
    assert migration.apply(tmp_path).success is True
    data = YAML(typ="safe").load(charter_path.read_text(encoding="utf-8"))
    assert data["catalog"]["references"][0]["source_path"] == ("${SPEC_KITTY_PACKS_ROOT}/built-in/missions/software-dev/mission.yaml")


def test_template_set_migration_is_dry_run_safe_and_idempotent(tmp_path: Path, packs_root: Path) -> None:
    abs_source = packs_root / "built-in" / "missions" / "software-dev" / "mission.yaml"
    charter_path = _charter_path(tmp_path)
    _write_charter(charter_path, [_template_ref(str(abs_source))])
    original = charter_path.read_text(encoding="utf-8")
    migration = HealTemplateSetProvenanceMigration()

    dry_run = migration.apply(tmp_path, dry_run=True)
    assert dry_run.changes_made
    assert charter_path.read_text(encoding="utf-8") == original

    migration.apply(tmp_path)
    assert migration.detect(tmp_path) is False
    assert migration.apply(tmp_path).changes_made == []


def test_external_template_set_path_is_preserved_and_not_reported(tmp_path: Path, packs_root: Path) -> None:
    external = tmp_path / "external" / "built-in" / "missions" / "software-dev" / "mission.yaml"
    external.parent.mkdir(parents=True)
    external.write_text("name: custom\n", encoding="utf-8")
    charter_path = _charter_path(tmp_path)
    _write_charter(charter_path, [_template_ref(str(external))])
    migration = HealTemplateSetProvenanceMigration()

    assert migration.detect(tmp_path) is False
    assert migration.apply(tmp_path).changes_made == []
    data = YAML(typ="safe").load(charter_path.read_text(encoding="utf-8"))
    assert data["catalog"]["references"][0]["source_path"] == str(external)
