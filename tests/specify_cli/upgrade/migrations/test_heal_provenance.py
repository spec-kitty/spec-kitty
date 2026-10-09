"""Tests for m_3_2_7_heal_provenance_paths (T014, C-PRV-4).

Mirrors the established migration-test pattern (see
``tests/specify_cli/upgrade/test_normalize_activation_absence.py``): every
test calls ``detect()``/``can_apply()``/``apply()`` directly on a migration
instance against a synthetic project, never through the upgrade pipeline, so
the ``target_version`` guard never interferes. ``SPEC_KITTY_PACKS_ROOT`` is
pointed at a synthetic ``packs/built-in`` tree (mirrors
``tests/charter_offering/test_provenance_normalizer.py``'s fixture) so built-in-pack
classification is deterministic regardless of where this checkout lives.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from specify_cli.upgrade.migrations.m_3_2_7_heal_provenance_paths import (
    MIGRATION_ID,
    HealProvenancePathsMigration,
)
from specify_cli.upgrade.registry import MigrationRegistry

pytestmark = [pytest.mark.unit]


@pytest.fixture
def packs_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "packs"
    (root / "built-in" / "paradigms").mkdir(parents=True)
    (root / "built-in" / "missions" / "software-dev").mkdir(parents=True)
    (root / "built-in" / "agent_profiles").mkdir(parents=True)
    monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(root))
    return root


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _charter_yaml_with_catalog(references_yaml_block: str) -> str:
    return f"""\
schema_version: "2.0.0"
governance:
  testing: {{}}
directives: []
catalog:
  mission: software-dev
  template_set: software-dev-default
  languages: []
  references:
{references_yaml_block}
overrides: {{}}
metadata:
  bundle_schema_version: 2
"""


def _charter_yaml_path(project_root: Path) -> Path:
    return project_root / ".kittify" / "charter" / "charter.yaml"


def _write_manifest(project_root: Path, entries: list[dict[str, object]]) -> Path:
    manifest_path = project_root / ".kittify" / "agent_profiles_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps({"schema_version": 1, "entries": entries}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def _manifest_entry(**overrides: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "profile_urn": "agent_profile:example",
        "source_layer": "builtin",
        "tool_key": "claude",
        "output_path": ".claude/agents/example.md",
        "format": "markdown",
        "file_hash": "deadbeef",
        "source_path": None,
        "source_hash": None,
        "projection_version": 1,
    }
    entry.update(overrides)
    return entry


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_migration_is_registered() -> None:
    found = MigrationRegistry.get_by_id(MIGRATION_ID)
    assert found is not None
    assert found.migration_id == MIGRATION_ID
    assert found.runs_on_worktrees is False


# ---------------------------------------------------------------------------
# Catalog (charter.yaml) heal
# ---------------------------------------------------------------------------


class TestCatalogHeal:
    def test_detect_true_for_absolute_built_in_source(self, tmp_path: Path, packs_root: Path) -> None:
        abs_source = packs_root / "built-in" / "paradigms" / "atomic-design.paradigm.yaml"
        refs = (
            "  - id: PARADIGM:atomic-design\n"
            "    kind: paradigm\n"
            "    title: Atomic Design\n"
            "    summary: x\n"
            f"    source_path: {abs_source}\n"
            "    local_path: _LIBRARY/paradigm-atomic-design.md\n"
        )
        _write(_charter_yaml_path(tmp_path), _charter_yaml_with_catalog(refs))

        migration = HealProvenancePathsMigration()
        assert migration.detect(tmp_path) is True

    def test_apply_rewrites_absolute_built_in_source_to_token(self, tmp_path: Path, packs_root: Path) -> None:
        abs_source = packs_root / "built-in" / "paradigms" / "atomic-design.paradigm.yaml"
        refs = (
            "  - id: PARADIGM:atomic-design\n"
            "    kind: paradigm\n"
            "    title: Atomic Design\n"
            "    summary: x\n"
            f"    source_path: {abs_source}\n"
            "    local_path: _LIBRARY/paradigm-atomic-design.md\n"
        )
        charter_path = _charter_yaml_path(tmp_path)
        _write(charter_path, _charter_yaml_with_catalog(refs))

        migration = HealProvenancePathsMigration()
        result = migration.apply(tmp_path, dry_run=False)

        assert result.success is True
        assert result.changes_made

        data = YAML(typ="safe").load(charter_path.read_text(encoding="utf-8"))
        ref = data["catalog"]["references"][0]
        assert ref["source_path"] == "${SPEC_KITTY_PACKS_ROOT}/built-in/paradigms/atomic-design.paradigm.yaml"

    def test_template_set_kind_is_excluded_and_stays_absolute(self, tmp_path: Path, packs_root: Path) -> None:
        abs_source = packs_root / "built-in" / "missions" / "software-dev" / "mission.yaml"
        refs = (
            "  - id: TEMPLATE_SET:software-dev-default\n"
            "    kind: template_set\n"
            "    title: software-dev-default\n"
            "    summary: x\n"
            f"    source_path: {abs_source}\n"
            "    local_path: _LIBRARY/template-set-software-dev-default.md\n"
        )
        charter_path = _charter_yaml_path(tmp_path)
        _write(charter_path, _charter_yaml_with_catalog(refs))

        migration = HealProvenancePathsMigration()
        assert migration.detect(tmp_path) is False

        result = migration.apply(tmp_path, dry_run=False)
        assert result.changes_made == []

        data = YAML(typ="safe").load(charter_path.read_text(encoding="utf-8"))
        ref = data["catalog"]["references"][0]
        assert ref["source_path"] == str(abs_source)

    def test_out_of_tree_non_built_in_absolute_source_untouched(self, tmp_path: Path, packs_root: Path) -> None:
        elsewhere = tmp_path / "elsewhere" / "custom.directive.yaml"
        elsewhere.parent.mkdir(parents=True)
        elsewhere.write_text("id: custom\n", encoding="utf-8")
        refs = (
            "  - id: DIRECTIVE:custom\n"
            "    kind: directive\n"
            "    title: Custom\n"
            "    summary: x\n"
            f"    source_path: {elsewhere}\n"
            "    local_path: _LIBRARY/directive-custom.md\n"
        )
        _write(_charter_yaml_path(tmp_path), _charter_yaml_with_catalog(refs))

        migration = HealProvenancePathsMigration()
        assert migration.detect(tmp_path) is False

    def test_dry_run_reports_without_mutating(self, tmp_path: Path, packs_root: Path) -> None:
        abs_source = packs_root / "built-in" / "paradigms" / "atomic-design.paradigm.yaml"
        refs = (
            "  - id: PARADIGM:atomic-design\n"
            "    kind: paradigm\n"
            "    title: Atomic Design\n"
            "    summary: x\n"
            f"    source_path: {abs_source}\n"
            "    local_path: _LIBRARY/paradigm-atomic-design.md\n"
        )
        charter_path = _charter_yaml_path(tmp_path)
        original = _charter_yaml_with_catalog(refs)
        _write(charter_path, original)

        migration = HealProvenancePathsMigration()
        result = migration.apply(tmp_path, dry_run=True)

        assert result.changes_made
        assert charter_path.read_text(encoding="utf-8") == original

    def test_absent_charter_yaml_detects_false(self, tmp_path: Path, packs_root: Path) -> None:
        migration = HealProvenancePathsMigration()
        assert migration.detect(tmp_path) is False


# ---------------------------------------------------------------------------
# Manifest (agent_profiles_manifest.json) heal
# ---------------------------------------------------------------------------


class TestManifestHeal:
    def test_apply_rewrites_manifest_source_path_to_token(self, tmp_path: Path, packs_root: Path) -> None:
        abs_source = packs_root / "built-in" / "agent_profiles" / "example.agent.yaml"
        abs_source.write_text("id: example\n", encoding="utf-8")

        manifest_path = _write_manifest(tmp_path, [_manifest_entry(source_path=str(abs_source))])

        migration = HealProvenancePathsMigration()
        assert migration.detect(tmp_path) is True

        result = migration.apply(tmp_path, dry_run=False)
        assert result.success is True

        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        entry = raw["entries"][0]
        assert entry["source_path"] == "${SPEC_KITTY_PACKS_ROOT}/built-in/agent_profiles/example.agent.yaml"
        # output_path is a distinct, excluded carrier -- never touched here.
        assert entry["output_path"] == ".claude/agents/example.md"

    def test_manifest_output_path_never_healed_even_if_absolute(self, tmp_path: Path, packs_root: Path) -> None:
        """Belt-and-braces: this migration never reads/writes output_path at all."""
        abs_output = str(tmp_path / "legacy-absolute-output.md")
        _write_manifest(
            tmp_path,
            [_manifest_entry(output_path=abs_output, source_path=None, source_hash=None, projection_version=None)],
        )

        migration = HealProvenancePathsMigration()
        assert migration.detect(tmp_path) is False

    def test_none_source_path_is_not_healable(self, tmp_path: Path, packs_root: Path) -> None:
        _write_manifest(tmp_path, [_manifest_entry(source_path=None)])

        migration = HealProvenancePathsMigration()
        assert migration.detect(tmp_path) is False

    def test_absent_manifest_detects_false(self, tmp_path: Path, packs_root: Path) -> None:
        migration = HealProvenancePathsMigration()
        assert migration.detect(tmp_path) is False


# ---------------------------------------------------------------------------
# Idempotency (C-MIG-1)
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_rerun_after_heal_yields_zero_changes(self, tmp_path: Path, packs_root: Path) -> None:
        abs_source = packs_root / "built-in" / "paradigms" / "atomic-design.paradigm.yaml"
        refs = (
            "  - id: PARADIGM:atomic-design\n"
            "    kind: paradigm\n"
            "    title: Atomic Design\n"
            "    summary: x\n"
            f"    source_path: {abs_source}\n"
            "    local_path: _LIBRARY/paradigm-atomic-design.md\n"
        )
        _write(_charter_yaml_path(tmp_path), _charter_yaml_with_catalog(refs))
        abs_manifest_source = packs_root / "built-in" / "agent_profiles" / "example.agent.yaml"
        abs_manifest_source.write_text("id: example\n", encoding="utf-8")
        _write_manifest(tmp_path, [_manifest_entry(source_path=str(abs_manifest_source))])

        migration = HealProvenancePathsMigration()
        first = migration.apply(tmp_path, dry_run=False)
        assert first.changes_made

        assert migration.detect(tmp_path) is False
        second = migration.apply(tmp_path, dry_run=False)
        assert second.changes_made == []


# ---------------------------------------------------------------------------
# can_apply
# ---------------------------------------------------------------------------


class TestCanApply:
    def test_can_apply_false_reason_when_nothing_healable(self, tmp_path: Path, packs_root: Path) -> None:
        migration = HealProvenancePathsMigration()
        can_apply, reason = migration.can_apply(tmp_path)
        assert can_apply is False
        assert reason
