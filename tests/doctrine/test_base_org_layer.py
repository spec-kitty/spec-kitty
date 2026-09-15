"""Unit tests for BaseDoctrineRepository three-layer loading (T010).

Tests verify:
- shipped-only loads with provenance 'builtin'
- org layer overrides shipped with provenance 'org'
- org layer adds new artifact with provenance 'org'
- project layer overrides org with provenance 'project'
- project layer overrides shipped (no org) with provenance 'project'
- bad org file is skipped with warning; valid artifacts still load
- language scope is applied after org merge
- project-only new artifact gets provenance 'project'
- get_provenance returns None for unknown IDs
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.offering.directives.repository import DirectiveRepository
from charter.offering.tactics.repository import TacticRepository

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


# ── Helpers ──────────────────────────────────────────────────────────────────


def _write_directive(directory: Path, filename: str, data: dict) -> None:
    """Write a directive YAML file into *directory*."""
    directory.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    with (directory / filename).open("w") as fh:
        yaml.dump(data, fh)


def _directive_data(
    directive_id: str = "DIRECTIVE_001",
    title: str = "Test Directive",
    intent: str = "Test intent.",
    enforcement: str = "required",
    applies_to_languages: list[str] | None = None,
) -> dict:
    """Return minimal valid directive data dict."""
    data: dict = {
        "schema_version": "1.0",
        "id": directive_id,
        "title": title,
        "intent": intent,
        "enforcement": enforcement,
    }
    if applies_to_languages is not None:
        data["applies_to_languages"] = applies_to_languages
    return data


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestShippedOnlyProvenance:
    """Shipped-only repository: all artifacts tagged 'builtin'."""

    def test_shipped_only_provenance(self, tmp_path: Path) -> None:
        shipped = tmp_path / "built-in"
        _write_directive(shipped, "001.directive.yaml", _directive_data("DIRECTIVE_001"))

        repo = DirectiveRepository(built_in_dir=shipped)

        assert repo.get("DIRECTIVE_001") is not None
        assert repo.get_provenance("DIRECTIVE_001") == "builtin"

    def test_get_provenance_unknown_id_returns_none(self, tmp_path: Path) -> None:
        shipped = tmp_path / "built-in"
        _write_directive(shipped, "001.directive.yaml", _directive_data("DIRECTIVE_001"))

        repo = DirectiveRepository(built_in_dir=shipped)

        assert repo.get_provenance("DIRECTIVE_999") is None


class TestOrgOverridesShipped:
    """Org layer overrides a shipped artifact → provenance becomes 'org'."""

    def test_org_overrides_shipped_provenance(self, tmp_path: Path) -> None:
        shipped = tmp_path / "built-in"
        org = tmp_path / "org"

        _write_directive(shipped, "001.directive.yaml", _directive_data("DIRECTIVE_001", title="Shipped Title"))
        _write_directive(
            org,
            "001.directive.yaml",
            _directive_data("DIRECTIVE_001", title="Org Title"),
        )

        repo = DirectiveRepository(built_in_dir=shipped, org_dirs=[org])

        directive = repo.get("DIRECTIVE_001")
        assert directive is not None
        assert directive.title == "Org Title"
        assert repo.get_provenance("DIRECTIVE_001") == "org"

    def test_org_overrides_shipped_field_merge(self, tmp_path: Path) -> None:
        """Org override uses field-level merge from shipped base."""
        shipped = tmp_path / "built-in"
        org = tmp_path / "org"

        shipped_data = _directive_data("DIRECTIVE_001", title="Shipped Title")
        shipped_data["scope"] = "Original scope."
        _write_directive(shipped, "001.directive.yaml", shipped_data)

        org_data = {
            "schema_version": "1.0",
            "id": "DIRECTIVE_001",
            "title": "Org Title",
            "intent": "Test intent.",
            "enforcement": "required",
        }
        _write_directive(org, "001.directive.yaml", org_data)

        repo = DirectiveRepository(built_in_dir=shipped, org_dirs=[org])

        directive = repo.get("DIRECTIVE_001")
        assert directive is not None
        assert directive.title == "Org Title"
        assert repo.get_provenance("DIRECTIVE_001") == "org"


class TestOrgAddsNewArtifact:
    """Org layer can introduce artifacts not in shipped."""

    def test_org_adds_new_artifact(self, tmp_path: Path) -> None:
        shipped = tmp_path / "built-in"
        org = tmp_path / "org"

        _write_directive(shipped, "001.directive.yaml", _directive_data("DIRECTIVE_001"))
        _write_directive(org, "002.directive.yaml", _directive_data("DIRECTIVE_002", title="Org New"))

        repo = DirectiveRepository(built_in_dir=shipped, org_dirs=[org])

        assert repo.get("DIRECTIVE_001") is not None
        assert repo.get_provenance("DIRECTIVE_001") == "builtin"

        assert repo.get("DIRECTIVE_002") is not None
        assert repo.get_provenance("DIRECTIVE_002") == "org"

    def test_org_adds_new_artifact_in_items(self, tmp_path: Path) -> None:
        shipped = tmp_path / "built-in"
        org = tmp_path / "org"

        _write_directive(shipped, "001.directive.yaml", _directive_data("DIRECTIVE_001"))
        _write_directive(org, "002.directive.yaml", _directive_data("DIRECTIVE_002"))

        repo = DirectiveRepository(built_in_dir=shipped, org_dirs=[org])

        ids = {d.id for d in repo.list_all()}
        assert "DIRECTIVE_001" in ids
        assert "DIRECTIVE_002" in ids


class TestProjectOverridesOrg:
    """Project layer overrides an org artifact → provenance becomes 'project'."""

    def test_project_overrides_org_provenance(self, tmp_path: Path) -> None:
        shipped = tmp_path / "built-in"
        org = tmp_path / "org"
        project = tmp_path / "project"

        _write_directive(shipped, "001.directive.yaml", _directive_data("DIRECTIVE_001", title="Shipped Title"))
        _write_directive(org, "001.directive.yaml", _directive_data("DIRECTIVE_001", title="Org Title"))
        _write_directive(project, "001.directive.yaml", _directive_data("DIRECTIVE_001", title="Project Title"))

        repo = DirectiveRepository(built_in_dir=shipped, org_dirs=[org], project_dir=project)

        directive = repo.get("DIRECTIVE_001")
        assert directive is not None
        assert directive.title == "Project Title"
        assert repo.get_provenance("DIRECTIVE_001") == "project"


class TestProjectOverridesShippedNoOrg:
    """Project layer overrides shipped when no org layer is present."""

    def test_project_overrides_shipped_no_org(self, tmp_path: Path) -> None:
        shipped = tmp_path / "built-in"
        project = tmp_path / "project"

        _write_directive(shipped, "001.directive.yaml", _directive_data("DIRECTIVE_001", title="Shipped Title"))
        _write_directive(project, "001.directive.yaml", _directive_data("DIRECTIVE_001", title="Project Title"))

        repo = DirectiveRepository(built_in_dir=shipped, project_dir=project)

        directive = repo.get("DIRECTIVE_001")
        assert directive is not None
        assert directive.title == "Project Title"
        assert repo.get_provenance("DIRECTIVE_001") == "project"

    def test_shipped_not_overridden_stays_builtin(self, tmp_path: Path) -> None:
        shipped = tmp_path / "built-in"
        project = tmp_path / "project"

        _write_directive(shipped, "001.directive.yaml", _directive_data("DIRECTIVE_001"))
        _write_directive(shipped, "002.directive.yaml", _directive_data("DIRECTIVE_002"))
        _write_directive(project, "001.directive.yaml", _directive_data("DIRECTIVE_001", title="Project Title"))

        repo = DirectiveRepository(built_in_dir=shipped, project_dir=project)

        assert repo.get_provenance("DIRECTIVE_001") == "project"
        assert repo.get_provenance("DIRECTIVE_002") == "builtin"


class TestBadOrgFileSkipped:
    """Invalid org YAML is skipped with a warning; valid artifacts still load."""

    def test_bad_org_file_skipped_warning(self, tmp_path: Path) -> None:
        shipped = tmp_path / "built-in"
        org = tmp_path / "org"

        _write_directive(shipped, "001.directive.yaml", _directive_data("DIRECTIVE_001"))
        org.mkdir(parents=True, exist_ok=True)
        (org / "bad.directive.yaml").write_text("not: valid: yaml: [")
        _write_directive(org, "002.directive.yaml", _directive_data("DIRECTIVE_002", title="Org New"))

        with pytest.warns(UserWarning, match="Skipping invalid"):
            repo = DirectiveRepository(built_in_dir=shipped, org_dirs=[org])

        # Shipped item intact
        assert repo.get("DIRECTIVE_001") is not None
        assert repo.get_provenance("DIRECTIVE_001") == "builtin"

        # Valid org item loaded
        assert repo.get("DIRECTIVE_002") is not None
        assert repo.get_provenance("DIRECTIVE_002") == "org"

    def test_org_file_missing_id_skipped_warning(self, tmp_path: Path) -> None:
        shipped = tmp_path / "built-in"
        org = tmp_path / "org"

        _write_directive(shipped, "001.directive.yaml", _directive_data("DIRECTIVE_001"))

        no_id_data = {
            "schema_version": "1.0",
            "title": "No ID directive",
            "intent": "Missing id field.",
            "enforcement": "required",
        }
        _write_directive(org, "noid.directive.yaml", no_id_data)
        _write_directive(org, "002.directive.yaml", _directive_data("DIRECTIVE_002"))

        with pytest.warns(UserWarning, match="no id"):
            repo = DirectiveRepository(built_in_dir=shipped, org_dirs=[org])

        assert repo.get("DIRECTIVE_002") is not None
        assert repo.get_provenance("DIRECTIVE_002") == "org"


def _tactic_data(
    tactic_id: str = "my-tactic",
    name: str = "My Tactic",
    applies_to_languages: list[str] | None = None,
) -> dict:
    """Return minimal valid tactic data dict."""
    data: dict = {
        "schema_version": "1.0",
        "id": tactic_id,
        "name": name,
        "steps": [{"title": "Do the thing", "description": "Step one."}],
    }
    if applies_to_languages is not None:
        data["applies_to_languages"] = applies_to_languages
    return data


def _write_tactic(directory: Path, filename: str, data: dict) -> None:
    """Write a tactic YAML file into *directory*."""
    directory.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    with (directory / filename).open("w") as fh:
        yaml.dump(data, fh)


class TestLanguageScopeAfterOrgMerge:
    """Language filtering is applied after org merge (uses TacticRepository which has applies_to_languages)."""

    def test_language_scope_filters_org_artifact(self, tmp_path: Path) -> None:
        shipped = tmp_path / "built-in"
        org = tmp_path / "org"

        # Shipped: all-language artifact (empty applies_to_languages = no filter)
        _write_tactic(shipped, "my-tactic.tactic.yaml", _tactic_data("my-tactic"))

        # Org: python-only artifact
        _write_tactic(
            org,
            "python-tactic.tactic.yaml",
            _tactic_data("python-tactic", applies_to_languages=["python"]),
        )

        # Active language: java → org artifact should be excluded
        repo = TacticRepository(built_in_dir=shipped, org_dirs=[org], active_languages=["java"])

        assert repo.get("my-tactic") is not None, "All-language shipped item should be present"
        assert repo.get("python-tactic") is None, "Python-only org item should be excluded for java"

    def test_language_scope_includes_matching_org_artifact(self, tmp_path: Path) -> None:
        shipped = tmp_path / "built-in"
        org = tmp_path / "org"

        _write_tactic(shipped, "my-tactic.tactic.yaml", _tactic_data("my-tactic"))
        _write_tactic(
            org,
            "python-tactic.tactic.yaml",
            _tactic_data("python-tactic", applies_to_languages=["python"]),
        )

        # Active language: python → org artifact should be included
        repo = TacticRepository(built_in_dir=shipped, org_dirs=[org], active_languages=["python"])

        assert repo.get("python-tactic") is not None
        assert repo.get_provenance("python-tactic") == "org"


class TestProjectNewArtifactProvenance:
    """Project-only new artifact gets provenance 'project'."""

    def test_project_new_artifact_provenance(self, tmp_path: Path) -> None:
        shipped = tmp_path / "built-in"
        project = tmp_path / "project"

        _write_directive(shipped, "001.directive.yaml", _directive_data("DIRECTIVE_001"))
        _write_directive(project, "002.directive.yaml", _directive_data("DIRECTIVE_002", title="Project Only"))

        repo = DirectiveRepository(built_in_dir=shipped, project_dir=project)

        assert repo.get("DIRECTIVE_001") is not None
        assert repo.get_provenance("DIRECTIVE_001") == "builtin"

        assert repo.get("DIRECTIVE_002") is not None
        assert repo.get_provenance("DIRECTIVE_002") == "project"

    def test_org_and_project_both_add_new(self, tmp_path: Path) -> None:
        shipped = tmp_path / "built-in"
        org = tmp_path / "org"
        project = tmp_path / "project"

        _write_directive(shipped, "001.directive.yaml", _directive_data("DIRECTIVE_001"))
        _write_directive(org, "002.directive.yaml", _directive_data("DIRECTIVE_002", title="Org New"))
        _write_directive(project, "003.directive.yaml", _directive_data("DIRECTIVE_003", title="Project New"))

        repo = DirectiveRepository(built_in_dir=shipped, org_dirs=[org], project_dir=project)

        assert repo.get_provenance("DIRECTIVE_001") == "builtin"
        assert repo.get_provenance("DIRECTIVE_002") == "org"
        assert repo.get_provenance("DIRECTIVE_003") == "project"

    def test_project_overrides_org_new_artifact(self, tmp_path: Path) -> None:
        """Project can re-override an artifact that was added by org (not in shipped)."""
        shipped = tmp_path / "built-in"
        org = tmp_path / "org"
        project = tmp_path / "project"

        _write_directive(shipped, "001.directive.yaml", _directive_data("DIRECTIVE_001"))
        # Org introduces DIRECTIVE_002
        _write_directive(org, "002.directive.yaml", _directive_data("DIRECTIVE_002", title="Org Title"))
        # Project also defines DIRECTIVE_002 (not in shipped → full replace)
        _write_directive(project, "002.directive.yaml", _directive_data("DIRECTIVE_002", title="Project Title"))

        repo = DirectiveRepository(built_in_dir=shipped, org_dirs=[org], project_dir=project)

        directive = repo.get("DIRECTIVE_002")
        assert directive is not None
        assert directive.title == "Project Title"
        assert repo.get_provenance("DIRECTIVE_002") == "project"


class TestOrgDirNotExists:
    """When org_dir path does not exist, loading proceeds without error."""

    def test_nonexistent_org_dir_ignored(self, tmp_path: Path) -> None:
        shipped = tmp_path / "built-in"
        nonexistent_org = tmp_path / "nonexistent_org"

        _write_directive(shipped, "001.directive.yaml", _directive_data("DIRECTIVE_001"))

        repo = DirectiveRepository(built_in_dir=shipped, org_dirs=[nonexistent_org])

        assert repo.get("DIRECTIVE_001") is not None
        assert repo.get_provenance("DIRECTIVE_001") == "builtin"


class TestDoctrineLayerCollisionWarning:
    """Collision warnings surface higher-layer override of lower-layer artifacts (MEDIUM-1)."""

    def test_org_shadows_builtin_emits_warning(self, tmp_path: Path) -> None:
        from charter.offering.base import DoctrineLayerCollisionWarning

        shipped = tmp_path / "built-in"
        org = tmp_path / "org"

        _write_directive(
            shipped,
            "001.directive.yaml",
            _directive_data("DIRECTIVE_001", title="Shipped"),
        )
        _write_directive(
            org,
            "001.directive.yaml",
            _directive_data("DIRECTIVE_001", title="Org"),
        )

        with pytest.warns(DoctrineLayerCollisionWarning) as record:
            DirectiveRepository(built_in_dir=shipped, org_dirs=[org])

        messages = [str(w.message) for w in record]
        # Exactly one collision warning, with the expected payload.
        collision_msgs = [m for m in messages if "DIRECTIVE_001" in m]
        assert len(collision_msgs) == 1, collision_msgs
        msg = collision_msgs[0]
        assert "org" in msg
        assert "builtin" in msg
        assert "shadowed" in msg
        # title was replaced; other fields inherited
        assert "field" in msg

    def test_project_shadows_org_emits_warning(self, tmp_path: Path) -> None:
        from charter.offering.base import DoctrineLayerCollisionWarning

        shipped = tmp_path / "built-in"
        org = tmp_path / "org"
        project = tmp_path / "project"

        _write_directive(
            shipped,
            "001.directive.yaml",
            _directive_data("DIRECTIVE_001", title="Shipped"),
        )
        _write_directive(
            org,
            "001.directive.yaml",
            _directive_data("DIRECTIVE_001", title="Org"),
        )
        _write_directive(
            project,
            "001.directive.yaml",
            _directive_data("DIRECTIVE_001", title="Project"),
        )

        with pytest.warns(DoctrineLayerCollisionWarning) as record:
            DirectiveRepository(
                built_in_dir=shipped, org_dirs=[org], project_dir=project
            )

        messages = [str(w.message) for w in record]
        # We expect both org-over-shipped and project-over-org collisions surfaced.
        assert any("project" in m and "org" in m for m in messages)
        assert any("org" in m and "builtin" in m for m in messages)

    def test_project_shadows_builtin_when_no_org(self, tmp_path: Path) -> None:
        from charter.offering.base import DoctrineLayerCollisionWarning

        shipped = tmp_path / "built-in"
        project = tmp_path / "project"

        _write_directive(
            shipped,
            "001.directive.yaml",
            _directive_data("DIRECTIVE_001", title="Shipped"),
        )
        _write_directive(
            project,
            "001.directive.yaml",
            _directive_data("DIRECTIVE_001", title="Project"),
        )

        with pytest.warns(DoctrineLayerCollisionWarning) as record:
            DirectiveRepository(built_in_dir=shipped, project_dir=project)

        messages = [str(w.message) for w in record]
        assert any("project" in m and "builtin" in m for m in messages)

    def test_no_warning_when_no_collision(self, tmp_path: Path) -> None:
        from charter.offering.base import DoctrineLayerCollisionWarning

        shipped = tmp_path / "built-in"
        org = tmp_path / "org"

        _write_directive(
            shipped,
            "001.directive.yaml",
            _directive_data("DIRECTIVE_001", title="Shipped"),
        )
        _write_directive(
            org,
            "002.directive.yaml",
            _directive_data("DIRECTIVE_002", title="Org-only new"),
        )

        # New org artifact is not a collision; no warning expected.
        with warnings_capture() as captured:
            DirectiveRepository(built_in_dir=shipped, org_dirs=[org])

        collision_msgs = [
            str(w.message)
            for w in captured
            if isinstance(w.message, DoctrineLayerCollisionWarning)
        ]
        assert collision_msgs == []

    def test_collision_warning_reports_field_count(self, tmp_path: Path) -> None:
        """The warning message includes how many fields were replaced and inherited."""
        from charter.offering.base import DoctrineLayerCollisionWarning

        shipped = tmp_path / "built-in"
        org = tmp_path / "org"

        shipped_data = _directive_data("DIRECTIVE_001", title="Shipped Title")
        shipped_data["scope"] = "Original scope."
        _write_directive(shipped, "001.directive.yaml", shipped_data)

        # Org overrides only title (1 field), inherits scope (1 field).
        _write_directive(
            org,
            "001.directive.yaml",
            _directive_data("DIRECTIVE_001", title="Org Title"),
        )

        with pytest.warns(DoctrineLayerCollisionWarning) as record:
            DirectiveRepository(built_in_dir=shipped, org_dirs=[org])

        msg = next(str(w.message) for w in record if "DIRECTIVE_001" in str(w.message))
        # Format includes both counts
        assert "replaced" in msg
        assert "inherited" in msg


import warnings as _stdlib_warnings
from contextlib import contextmanager


@contextmanager
def warnings_capture():
    """Capture all warnings emitted within the block, regardless of filter state."""
    with _stdlib_warnings.catch_warnings(record=True) as captured:
        _stdlib_warnings.simplefilter("always")
        yield captured


# ---------------------------------------------------------------------------
# WP03 T011 — direct unit tests for _apply_overlay_file / _merge_overlay_item /
# _insert_overlay_item, extracted from _apply_overlay_layer to keep its
# cognitive complexity within the ruff C901 limit (15).
# ---------------------------------------------------------------------------


class TestApplyOverlayFileDirect:
    def test_apply_overlay_file_records_skip_on_missing_id(self, tmp_path: Path) -> None:
        shipped = tmp_path / "built-in"
        _write_directive(shipped, "001.directive.yaml", _directive_data("DIRECTIVE_001"))
        repo = DirectiveRepository(built_in_dir=shipped)

        org = tmp_path / "org"
        org.mkdir()
        no_id_file = org / "noid.directive.yaml"
        yaml = YAML()
        yaml.dump({"schema_version": "1.0", "title": "No id"}, no_id_file)

        with pytest.warns(UserWarning, match="no id"):
            repo._apply_overlay_file(
                no_id_file, "org", yaml_parser=YAML(typ="safe"), built_in=repo._items
            )

    def test_apply_overlay_file_records_skip_on_invalid_yaml(self, tmp_path: Path) -> None:
        shipped = tmp_path / "built-in"
        _write_directive(shipped, "001.directive.yaml", _directive_data("DIRECTIVE_001"))
        repo = DirectiveRepository(built_in_dir=shipped)

        org = tmp_path / "org"
        org.mkdir()
        bad_file = org / "bad.directive.yaml"
        bad_file.write_text("not: valid: yaml: [")

        with pytest.warns(UserWarning, match="Skipping invalid"):
            repo._apply_overlay_file(
                bad_file, "org", yaml_parser=YAML(typ="safe"), built_in=repo._items
            )


class TestMergeAndInsertOverlayItemDirect:
    def test_merge_overlay_item_scope_filtered_excludes_merged_result(
        self, tmp_path: Path
    ) -> None:
        """The merge branch's scope-filtered path: an org override that
        narrows a built-in tactic to a non-active language must exclude the
        merged result (recorded in ``_scope_filtered_ids``), leaving the
        built-in item's provenance untouched."""
        shipped = tmp_path / "built-in"
        _write_tactic(shipped, "my-tactic.tactic.yaml", _tactic_data("my-tactic"))
        repo = TacticRepository(built_in_dir=shipped, active_languages=["java"])
        assert repo.get("my-tactic") is not None

        override_data = _tactic_data("my-tactic", applies_to_languages=["python"])
        repo._merge_overlay_item(
            "my-tactic",
            override_data,
            shipped / "my-tactic.tactic.yaml",
            repo._items,
            "org",
        )

        assert "my-tactic" in repo._scope_filtered_ids
        assert repo.get_provenance("my-tactic") == "builtin"

    def test_insert_overlay_item_scope_filtered_excludes_new_item(
        self, tmp_path: Path
    ) -> None:
        shipped = tmp_path / "built-in"
        _write_tactic(shipped, "base.tactic.yaml", _tactic_data("base"))
        repo = TacticRepository(built_in_dir=shipped, active_languages=["java"])

        new_data = _tactic_data("python-only", applies_to_languages=["python"])
        repo._insert_overlay_item(new_data, shipped / "python-only.tactic.yaml", "org")

        assert repo.get("python-only") is None
        assert "python-only" in repo._scope_filtered_ids

    def test_insert_overlay_item_adds_included_new_item(self, tmp_path: Path) -> None:
        shipped = tmp_path / "built-in"
        _write_tactic(shipped, "base.tactic.yaml", _tactic_data("base"))
        repo = TacticRepository(built_in_dir=shipped)

        new_data = _tactic_data("newcomer")
        repo._insert_overlay_item(new_data, shipped / "newcomer.tactic.yaml", "org")

        assert repo.get("newcomer") is not None
        assert repo.get_provenance("newcomer") == "org"
