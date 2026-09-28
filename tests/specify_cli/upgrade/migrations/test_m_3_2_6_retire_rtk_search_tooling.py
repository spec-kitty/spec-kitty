"""Tests for the retired ``rtk-search-tooling`` toolguide cleanup migration.

The rc35 default-pack migration copied ``rtk-search-tooling`` into every
upgraded project's ``activated_toolguides`` and only ever writes *absent*
keys, so nothing removes the entry once the artefact is deleted. The charter
compiler is fail-closed, so a stale entry is a hard ``UnknownArtifactIdError``
at compile time. These tests pin the cleanup behaviour on each surface.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from specify_cli.upgrade.migrations.m_3_2_6_retire_rtk_search_tooling import (
    RETIRED_TOOLGUIDE_STEM,
    RetireRtkSearchToolingMigration,
)

#: Catalog/reference block id of the retired toolguide, as compiled into
#: ``.kittify/charter/charter.yaml`` (``catalog``) and ``references.yaml``.
RETIRED_TOOLGUIDE_REFERENCE_ID = f"TOOLGUIDE:{RETIRED_TOOLGUIDE_STEM}"

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_CONFIG_WITH_ENTRY = f"""\
project_name: demo
activated_toolguides:
- plantuml-diagramming
- python-review-checks
- {RETIRED_TOOLGUIDE_STEM}
- terminology-guard
"""

_CONFIG_WITHOUT_ENTRY = """\
project_name: demo
activated_toolguides:
- plantuml-diagramming
- terminology-guard
"""

_CHARTER_WITH_ENTRY = f"""\
schema_version: 2.0.0
catalog:
  - id: TOOLGUIDE:python-review-checks
    kind: toolguide
    title: Python Review Checks
    source_path: ''
    local_path: _LIBRARY/toolguide-python-review-checks.md
  - id: {RETIRED_TOOLGUIDE_REFERENCE_ID}
    kind: toolguide
    title: RTK Interception and Search Tooling
    source_path: ''
    local_path: _LIBRARY/toolguide-rtk-search-tooling.md
  - id: TOOLGUIDE:terminology-guard
    kind: toolguide
    title: Terminology Guard
    source_path: ''
    local_path: _LIBRARY/toolguide-terminology-guard.md
activated_toolguides:
- python-review-checks
- {RETIRED_TOOLGUIDE_STEM}
- terminology-guard
"""

_REFERENCES_WITH_ENTRY = f"""\
schema_version: 1.0.0
references:
- id: TOOLGUIDE:python-review-checks
  kind: toolguide
  title: Python Review Checks
  source_path: ''
  local_path: _LIBRARY/toolguide-python-review-checks.md
- id: {RETIRED_TOOLGUIDE_REFERENCE_ID}
  kind: toolguide
  title: RTK Interception and Search Tooling
  source_path: ''
  local_path: _LIBRARY/toolguide-rtk-search-tooling.md
- id: TOOLGUIDE:terminology-guard
  kind: toolguide
  title: Terminology Guard
  source_path: ''
  local_path: _LIBRARY/toolguide-terminology-guard.md
"""


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _load(path: Path) -> dict:
    return YAML(typ="safe").load(path.read_text(encoding="utf-8"))


def _seed_project(tmp_path: Path, *, stale: bool = True) -> Path:
    """Write a project carrying (or not carrying) the retired toolguide."""
    _write(
        tmp_path / ".kittify" / "config.yaml",
        _CONFIG_WITH_ENTRY if stale else _CONFIG_WITHOUT_ENTRY,
    )
    if stale:
        _write(tmp_path / ".kittify" / "charter" / "charter.yaml", _CHARTER_WITH_ENTRY)
        _write(
            tmp_path / ".kittify" / "charter" / "references.yaml",
            _REFERENCES_WITH_ENTRY,
        )
    return tmp_path


def test_detects_stale_activation_in_config(tmp_path: Path) -> None:
    _write(tmp_path / ".kittify" / "config.yaml", _CONFIG_WITH_ENTRY)

    assert RetireRtkSearchToolingMigration().detect(tmp_path) is True


def test_detects_stale_reference_block_in_references_only(tmp_path: Path) -> None:
    _write(tmp_path / ".kittify" / "config.yaml", _CONFIG_WITHOUT_ENTRY)
    _write(tmp_path / ".kittify" / "charter" / "references.yaml", _REFERENCES_WITH_ENTRY)

    assert RetireRtkSearchToolingMigration().detect(tmp_path) is True


def test_apply_removes_entry_from_every_surface(tmp_path: Path) -> None:
    project = _seed_project(tmp_path)

    result = RetireRtkSearchToolingMigration().apply(project)

    assert result.success is True
    assert len(result.changes_made) == 4

    config = _load(project / ".kittify" / "config.yaml")
    assert RETIRED_TOOLGUIDE_STEM not in config["activated_toolguides"]
    assert config["activated_toolguides"] == [
        "plantuml-diagramming",
        "python-review-checks",
        "terminology-guard",
    ]
    assert config["project_name"] == "demo"

    charter = _load(project / ".kittify" / "charter" / "charter.yaml")
    assert RETIRED_TOOLGUIDE_STEM not in charter["activated_toolguides"]
    assert [entry["id"] for entry in charter["catalog"]] == [
        "TOOLGUIDE:python-review-checks",
        "TOOLGUIDE:terminology-guard",
    ]

    references = _load(project / ".kittify" / "charter" / "references.yaml")
    assert [entry["id"] for entry in references["references"]] == [
        "TOOLGUIDE:python-review-checks",
        "TOOLGUIDE:terminology-guard",
    ]


def test_apply_is_a_no_op_when_entry_absent(tmp_path: Path) -> None:
    project = _seed_project(tmp_path, stale=False)
    before = (project / ".kittify" / "config.yaml").read_text(encoding="utf-8")

    result = RetireRtkSearchToolingMigration().apply(project)

    assert result.success is True
    assert result.changes_made == [
        f"{RETIRED_TOOLGUIDE_STEM} already absent; nothing to remove"
    ]
    assert (project / ".kittify" / "config.yaml").read_text(encoding="utf-8") == before
    assert RetireRtkSearchToolingMigration().detect(project) is False


def test_apply_does_not_crash_when_files_are_missing(tmp_path: Path) -> None:
    result = RetireRtkSearchToolingMigration().apply(tmp_path)

    assert result.success is True
    assert result.errors == []
    assert not (tmp_path / ".kittify").exists()


def test_apply_tolerates_a_config_without_the_activation_key(tmp_path: Path) -> None:
    _write(tmp_path / ".kittify" / "config.yaml", "project_name: demo\n")

    migration = RetireRtkSearchToolingMigration()

    assert migration.detect(tmp_path) is False
    assert migration.apply(tmp_path).success is True


def test_apply_is_idempotent(tmp_path: Path) -> None:
    project = _seed_project(tmp_path)
    migration = RetireRtkSearchToolingMigration()

    first = migration.apply(project)
    after_first = {
        path: (project / path).read_text(encoding="utf-8")
        for path in (
            ".kittify/config.yaml",
            ".kittify/charter/charter.yaml",
            ".kittify/charter/references.yaml",
        )
    }

    second = migration.apply(project)

    assert first.success is True
    assert second.success is True
    assert second.changes_made == [
        f"{RETIRED_TOOLGUIDE_STEM} already absent; nothing to remove"
    ]
    assert migration.detect(project) is False
    for path, text in after_first.items():
        assert (project / path).read_text(encoding="utf-8") == text


def test_dry_run_reports_without_writing(tmp_path: Path) -> None:
    project = _seed_project(tmp_path)
    before = (project / ".kittify" / "config.yaml").read_text(encoding="utf-8")

    result = RetireRtkSearchToolingMigration().apply(project, dry_run=True)

    assert result.success is True
    assert all(change.startswith("Would remove") for change in result.changes_made)
    assert (project / ".kittify" / "config.yaml").read_text(encoding="utf-8") == before
    assert RetireRtkSearchToolingMigration().detect(project) is True


def test_can_apply_reflects_detection(tmp_path: Path) -> None:
    migration = RetireRtkSearchToolingMigration()

    assert migration.can_apply(tmp_path) == (
        False,
        "rtk-search-tooling is not activated in this project",
    )

    _write(tmp_path / ".kittify" / "config.yaml", _CONFIG_WITH_ENTRY)
    assert migration.can_apply(tmp_path) == (True, "")


def test_migration_is_registered_by_auto_discovery() -> None:
    from specify_cli.upgrade.migrations import auto_discover_migrations
    from specify_cli.upgrade.registry import MigrationRegistry

    MigrationRegistry.clear()
    auto_discover_migrations()

    assert "3.2.6_retire_rtk_search_tooling" in MigrationRegistry._migrations
