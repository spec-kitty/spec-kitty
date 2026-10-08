"""Scope: mock-boundary tests for doctrine catalog loading — no real git."""

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.activation.catalog import _load_yaml_id_catalog, load_offering_catalog

pytestmark = pytest.mark.fast


def test_catalog_loads_packaged_directives_and_paradigms() -> None:
    """Packaged catalog contains expected directives and paradigms."""
    # Arrange
    # (no precondition)

    # Assumption check
    # (no precondition)

    # Act
    catalog = load_offering_catalog()

    # Assert — shipped directives use DIRECTIVE_NNN identifiers
    assert "DIRECTIVE_003" in catalog.directives  # decision-documentation-requirement


def test_catalog_includes_mission_template_sets() -> None:
    """Packaged catalog includes the default software-dev template set."""
    # Arrange
    # (no precondition)

    # Assumption check
    # (no precondition)

    # Act
    catalog = load_offering_catalog()

    # Assert
    assert "software-dev-default" in catalog.template_sets


def test_catalog_filters_language_scoped_artifacts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    doctrine_root = tmp_path / "doctrine"
    yaml = YAML()
    yaml.default_flow_style = False

    fixtures = {
        Path("styleguides/python.styleguide.yaml"): {
            "schema_version": "1.0",
            "id": "python-style",
            "title": "Python Style",
            "scope": "code",
            "applies_to_languages": ["python"],
            "principles": ["Use Python idioms"],
        },
        Path("styleguides/generic.styleguide.yaml"): {
            "schema_version": "1.0",
            "id": "generic-style",
            "title": "Generic Style",
            "scope": "code",
            "principles": ["Be clear"],
        },
        Path("toolguides/python.toolguide.yaml"): {
            "schema_version": "1.0",
            "id": "python-toolguide",
            "tool": "pytest",
            "title": "Python Toolguide",
            "guide_path": "src/charter/offering/toolguides/built-in/python.md",
            "summary": "Python checks",
            "applies_to_languages": ["python"],
        },
        Path("toolguides/generic.toolguide.yaml"): {
            "schema_version": "1.0",
            "id": "generic-toolguide",
            "tool": "git",
            "title": "Generic Toolguide",
            "guide_path": "src/charter/offering/toolguides/built-in/generic.md",
            "summary": "Generic checks",
        },
        Path("agent_profiles/python.agent.yaml"): {
            "profile-id": "python-pedro",
            "name": "Python Pedro",
            "roles": ["implementer"],
            "purpose": "Python specialist",
            "applies_to_languages": ["python"],
            "specialization": {"primary-focus": "python"},
        },
        Path("agent_profiles/generic.agent.yaml"): {
            "profile-id": "generic-implementer",
            "name": "Generic Implementer",
            "roles": ["implementer"],
            "purpose": "General specialist",
            "specialization": {"primary-focus": "general"},
        },
        Path("missions/software-dev/mission.yaml"): {
            "name": "software-dev",
            "description": "Software development mission",
        },
    }

    for relative_path, data in fixtures.items():
        path = doctrine_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            yaml.dump(data, handle)

    monkeypatch.setattr("charter.activation.catalog.resolve_offering_root", lambda: doctrine_root)
    # Built-in pack content is flat under ``packs/built-in/<kind>/`` and is
    # resolved per-kind via ``built_in_dir`` (mission
    # doctrine-built-in-seam-consolidation-01KYW3TX, WP02); point it at the
    # tmp root's flat per-kind directories.
    monkeypatch.setattr("charter.activation.catalog.built_in_dir", lambda kind: doctrine_root / kind.plural)

    catalog = load_offering_catalog(active_languages=["typescript"])

    assert "generic-style" in catalog.styleguides
    assert "python-style" not in catalog.styleguides
    assert "generic-toolguide" in catalog.toolguides
    assert "python-toolguide" not in catalog.toolguides
    assert "generic-implementer" in catalog.agent_profiles
    assert "python-pedro" not in catalog.agent_profiles


def test_catalog_keeps_language_scoped_artifacts_when_active_languages_are_unset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doctrine_root = tmp_path / "doctrine"
    yaml = YAML()
    yaml.default_flow_style = False

    fixtures = {
        Path("styleguides/python.styleguide.yaml"): {
            "schema_version": "1.0",
            "id": "python-style",
            "title": "Python Style",
            "scope": "code",
            "applies_to_languages": ["python"],
            "principles": ["Use Python idioms"],
        },
        Path("toolguides/python.toolguide.yaml"): {
            "schema_version": "1.0",
            "id": "python-toolguide",
            "tool": "pytest",
            "title": "Python Toolguide",
            "guide_path": "src/charter/offering/toolguides/built-in/python.md",
            "summary": "Python checks",
            "applies_to_languages": ["python"],
        },
        Path("agent_profiles/python.agent.yaml"): {
            "profile-id": "python-pedro",
            "name": "Python Pedro",
            "roles": ["implementer"],
            "purpose": "Python specialist",
            "applies_to_languages": ["python"],
            "specialization": {"primary-focus": "python"},
        },
        Path("missions/software-dev/mission.yaml"): {
            "name": "software-dev",
            "description": "Software development mission",
        },
    }

    for relative_path, data in fixtures.items():
        path = doctrine_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            yaml.dump(data, handle)

    monkeypatch.setattr("charter.activation.catalog.resolve_offering_root", lambda: doctrine_root)
    # Built-in pack content is flat under ``packs/built-in/<kind>/`` and is
    # resolved per-kind via ``built_in_dir`` (mission
    # doctrine-built-in-seam-consolidation-01KYW3TX, WP02); point it at the
    # tmp root's flat per-kind directories.
    monkeypatch.setattr("charter.activation.catalog.built_in_dir", lambda kind: doctrine_root / kind.plural)

    catalog = load_offering_catalog()

    assert "python-style" in catalog.styleguides
    assert "python-toolguide" in catalog.toolguides
    assert "python-pedro" in catalog.agent_profiles


def test_load_yaml_id_catalog_scans_flat_directory_only(tmp_path: Path) -> None:
    """Built-in content dirs are flat (WP02): a nested ``built-in/`` or
    ``_proposed/`` subdirectory is never traversed -- the pre-relocation
    dual-read fallback for that nested pre-move shape was removed in mission
    doctrine-built-in-seam-consolidation-01KYW3TX (WP02). This also guards
    against reintroducing that dual-read.
    """
    doctrine_dir = tmp_path / "styleguides"
    nested_built_in = doctrine_dir / "built-in"
    nested_proposed = doctrine_dir / "_proposed"
    nested_built_in.mkdir(parents=True)
    nested_proposed.mkdir(parents=True)

    yaml = YAML()
    yaml.default_flow_style = False
    with (doctrine_dir / "shipped.styleguide.yaml").open("w", encoding="utf-8") as handle:
        yaml.dump(
            {"schema_version": "1.0", "id": "shipped-style", "title": "Shipped", "scope": "code"},
            handle,
        )
    # Content placed in the (now-inert) nested subdirectories must NOT surface.
    with (nested_built_in / "ignored.styleguide.yaml").open("w", encoding="utf-8") as handle:
        yaml.dump(
            {"schema_version": "1.0", "id": "nested-built-in-style", "title": "Nested", "scope": "code"},
            handle,
        )
    with (nested_proposed / "ignored.styleguide.yaml").open("w", encoding="utf-8") as handle:
        yaml.dump(
            {"schema_version": "1.0", "id": "nested-proposed-style", "title": "Nested Proposed", "scope": "code"},
            handle,
        )

    ids = _load_yaml_id_catalog(doctrine_dir, "*.styleguide.yaml", include_proposed=True)

    assert ids == {"shipped-style"}
