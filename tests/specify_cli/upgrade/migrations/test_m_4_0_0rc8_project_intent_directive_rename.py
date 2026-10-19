"""#6443 / FR-008: the ``4.0.0rc8_project_intent_directive_rename`` upgrade migration.

The conversion itself is covered by ``tests/charter/synthesizer/test_legacy_rename.py``; this
module pins the migration's contract: ``detect``, ``apply`` delegating to the shared helper,
dry run, a refusal as a failed result, and the ledger recording success through the runner.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from kernel.clock import now_utc
from specify_cli.upgrade.ledger import MigrationLedger, build_record
from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.migrations.m_4_0_0rc8_project_intent_directive_rename import (
    ProjectIntentDirectiveRenameMigration,
)
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.runner import MigrationRunner

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_PACK_DIR = Path(".kittify") / "charter-packs" / "directive"
_GRAPH = Path(".kittify") / "charter-packs" / "graph.yaml"
_LEGACY = "001-mission-type-scope-directive.directive.yaml"
_NEW = "001-project-intent-directive.directive.yaml"
_GRAPH_TEXT = (
    "schema_version: '1.0'\n"
    "nodes:\n"
    "- {urn: 'directive:PROJECT_001', kind: directive, label: Mission Type Scope Directive}\n"
    "- {urn: 'mission_type:software-dev', kind: mission_type, label: Software Dev}\n"
    "edges:\n"
    "- {source: 'directive:PROJECT_001', target: 'mission_type:software-dev', relation: requires}\n"
)


def _legacy_project(root: Path) -> None:
    (root / _PACK_DIR).mkdir(parents=True)
    (root / _PACK_DIR / _LEGACY).write_text("id: PROJECT_001\n", encoding="utf-8")
    (root / _GRAPH).write_text(_GRAPH_TEXT, encoding="utf-8")


def _settle_all_except(project: Path, *keep_unsettled: str) -> None:
    for migration in MigrationRegistry.get_all():
        if migration.migration_id not in keep_unsettled:
            MigrationLedger(project).append(build_record(migration, "success"))


def test_migration_identity_and_ledger_routing() -> None:
    migration = ProjectIntentDirectiveRenameMigration()
    assert migration.migration_id == "4.0.0rc8_project_intent_directive_rename"
    assert migration.target_version == "4.0.0rc8"
    assert migration.clone_local_effect is False


def test_detect_is_true_on_legacy_state_and_false_after_apply(tmp_path: Path) -> None:
    _legacy_project(tmp_path)
    migration = ProjectIntentDirectiveRenameMigration()
    assert migration.detect(tmp_path) is True

    result = migration.apply(tmp_path)

    assert result.success, result.errors
    assert (tmp_path / _PACK_DIR / _NEW).is_file()
    assert not (tmp_path / _PACK_DIR / _LEGACY).exists()
    assert YAML(typ="safe").load((tmp_path / _GRAPH).read_text())["edges"] == []
    assert migration.detect(tmp_path) is False


def test_dry_run_writes_nothing_and_names_the_changes(tmp_path: Path) -> None:
    _legacy_project(tmp_path)

    result = ProjectIntentDirectiveRenameMigration().apply(tmp_path, dry_run=True)

    assert result.success
    assert any(change.startswith("Would move") and _LEGACY in change for change in result.changes_made)
    assert (tmp_path / _PACK_DIR / _LEGACY).is_file()
    assert (tmp_path / _GRAPH).read_text() == _GRAPH_TEXT


def test_a_refusal_is_a_failed_result_with_the_helper_message(tmp_path: Path) -> None:
    _legacy_project(tmp_path)
    (tmp_path / _PACK_DIR / _NEW).write_text("id: PROJECT_001\n", encoding="utf-8")
    migration = ProjectIntentDirectiveRenameMigration()

    assert migration.detect(tmp_path) is True  # a refusal is routed through apply(), not skipped
    result = migration.apply(tmp_path)

    assert not result.success
    assert "already exists" in result.errors[0] and "Nothing was changed" in result.errors[0]
    assert (tmp_path / _PACK_DIR / _LEGACY).is_file()


def test_a_project_without_a_charter_pack_is_a_clean_no_op(tmp_path: Path) -> None:
    migration = ProjectIntentDirectiveRenameMigration()
    assert migration.detect(tmp_path) is False
    assert migration.apply(tmp_path).success


def test_the_runner_applies_it_and_the_ledger_records_success(tmp_path: Path) -> None:
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    ProjectMetadata(version="4.0.0rc8", initialized_at=now_utc()).save(tmp_path / ".kittify")
    _legacy_project(tmp_path)
    auto_discover_migrations()
    _settle_all_except(tmp_path, ProjectIntentDirectiveRenameMigration.migration_id)

    result = MigrationRunner(tmp_path).upgrade("4.0.0rc8", include_worktrees=False)

    assert result.success, result.errors
    assert ProjectIntentDirectiveRenameMigration.migration_id in result.migrations_applied
    assert (tmp_path / _PACK_DIR / _NEW).is_file()
    records = MigrationLedger(tmp_path).read_tracked()
    ours = [r for r in records if r.id == ProjectIntentDirectiveRenameMigration.migration_id]
    assert ours and ours[-1].result == "success"
