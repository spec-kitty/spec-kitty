"""Unit tests for DirectiveRepository."""

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.offering.directives.repository import DirectiveRepository

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


class TestDirectiveRepository:
    def test_list_all_from_shipped(self, tmp_directive_dir: Path) -> None:
        """list_all returns all directives from the given directory."""
        repo = DirectiveRepository(built_in_dir=tmp_directive_dir)
        directives = repo.list_all()
        assert {d.id for d in directives} == {"DIRECTIVE_999"}
        assert directives[0].id == "DIRECTIVE_999"

    def test_get_by_full_id(self, tmp_directive_dir: Path) -> None:
        """get() with full ID returns the directive."""
        repo = DirectiveRepository(built_in_dir=tmp_directive_dir)
        directive = repo.get("DIRECTIVE_999")
        assert directive is not None
        assert directive.title == "Test Directive"

    def test_get_by_numeric_shorthand(self, tmp_directive_dir: Path) -> None:
        """get() with numeric shorthand normalizes and returns."""
        repo = DirectiveRepository(built_in_dir=tmp_directive_dir)
        directive = repo.get("999")
        assert directive is not None
        assert directive.id == "DIRECTIVE_999"

    def test_get_returns_none_for_unknown(self, tmp_directive_dir: Path) -> None:
        repo = DirectiveRepository(built_in_dir=tmp_directive_dir)
        assert repo.get("888") is None

    def test_get_numeric_and_full_return_same(self, tmp_directive_dir: Path) -> None:
        repo = DirectiveRepository(built_in_dir=tmp_directive_dir)
        by_num = repo.get("999")
        by_full = repo.get("DIRECTIVE_999")
        assert by_num is not None
        assert by_full is not None
        assert by_num.id == by_full.id

    def test_get_by_slug_stem(self, tmp_directive_dir: Path) -> None:
        """get() accepts the file-stem slug the ``--json`` surface advertises.

        #3816: ``charter context --action <x> --json`` enumerates directive IDs
        as their file-stem slug (``999-test-directive``); the repository lookup
        must resolve that exact identifier or the advertised ID is a dead end.
        """
        repo = DirectiveRepository(built_in_dir=tmp_directive_dir)
        directive = repo.get("999-test-directive")
        assert directive is not None
        assert directive.id == "DIRECTIVE_999"

    def test_get_slug_numeric_full_return_same(self, tmp_directive_dir: Path) -> None:
        """Slug / numeric / full ID all resolve the same directive (#3816 parity)."""
        repo = DirectiveRepository(built_in_dir=tmp_directive_dir)
        by_slug = repo.get("999-test-directive")
        by_num = repo.get("999")
        by_full = repo.get("DIRECTIVE_999")
        assert by_slug is not None
        assert by_num is not None
        assert by_full is not None
        assert by_slug.id == by_num.id == by_full.id == "DIRECTIVE_999"

    def test_malformed_yaml_skipped_with_warning(self, tmp_path: Path) -> None:
        """Malformed YAML files are skipped, not crash."""
        shipped = tmp_path / "built-in"
        shipped.mkdir()
        bad_file = shipped / "bad.directive.yaml"
        bad_file.write_text("not: valid: yaml: [")

        with pytest.warns(UserWarning, match="Skipping invalid"):
            repo = DirectiveRepository(built_in_dir=shipped)

        assert repo.list_all() == []

    def test_save_writes_valid_yaml(self, tmp_path: Path, sample_directive_data: dict) -> None:
        from charter.offering.directives.models import Directive

        project_dir = tmp_path / "project"
        repo = DirectiveRepository(built_in_dir=tmp_path / "empty", project_dir=project_dir)

        directive = Directive.model_validate(sample_directive_data)
        path = repo.save(directive)

        assert path.exists()
        assert path.suffix == ".yaml"

        # Verify the saved file is loadable
        yaml = YAML(typ="safe")
        data = yaml.load(path)
        assert data["id"] == "DIRECTIVE_999"

    def test_save_raises_without_project_dir(self, tmp_path: Path, sample_directive_data: dict) -> None:
        from charter.offering.directives.models import Directive

        repo = DirectiveRepository(built_in_dir=tmp_path / "empty")
        directive = Directive.model_validate(sample_directive_data)
        with pytest.raises(ValueError, match="project_dir not configured"):
            repo.save(directive)

    def test_field_level_merge_with_project_override(self, tmp_path: Path) -> None:
        """Project directive overrides shipped fields at field level."""
        shipped = tmp_path / "built-in"
        shipped.mkdir()
        project = tmp_path / "project"
        project.mkdir()

        yaml = YAML()
        yaml.default_flow_style = False

        base = {
            "schema_version": "1.0",
            "id": "DIRECTIVE_100",
            "title": "Base Title",
            "intent": "Base intent.",
            "enforcement": "required",
        }
        override = {
            "schema_version": "1.0",
            "id": "DIRECTIVE_100",
            "title": "Overridden Title",
            "intent": "Overridden intent.",
            "enforcement": "advisory",
        }

        with (shipped / "100-base.directive.yaml").open("w") as f:
            yaml.dump(base, f)
        with (project / "100-base.directive.yaml").open("w") as f:
            yaml.dump(override, f)

        repo = DirectiveRepository(built_in_dir=shipped, project_dir=project)
        directive = repo.get("DIRECTIVE_100")
        assert directive is not None
        assert directive.title == "Overridden Title"
        assert directive.enforcement.value == "advisory"


@pytest.mark.parametrize("layer", ["built-in", "org", "project"])
@pytest.mark.parametrize("literal_id", ["ACME-001-FOO", "TEAM-POLICY", "A1-LITERAL"])
def test_literal_identity_round_trip(tmp_path: Path, layer: str, literal_id: str) -> None:
    """Every listed declared ID remains retrievable without slug normalization."""
    directory = tmp_path / layer
    directory.mkdir()
    (directory / "policy.directive.yaml").write_text(
        f'schema_version: "1.0"\nid: {literal_id}\ntitle: Literal\nintent: Preserve identity.\nenforcement: required\n'
    )
    repo = DirectiveRepository(
        built_in_dir=directory if layer == "built-in" else tmp_path / "empty",
        org_dirs=[directory] if layer == "org" else [],
        project_dir=directory if layer == "project" else None,
    )
    assert len(repo.list_all()) == 1
    assert repo.get(literal_id) == repo.list_all()[0]
    assert repo.get("not-a-directive") is None


def test_exact_identity_wins_over_normalized_alias(tmp_path: Path) -> None:
    for name, identity in [("literal", "ACME-001-FOO"), ("alias", "ACME_001_FOO")]:
        (tmp_path / f"{name}.directive.yaml").write_text(
            f'schema_version: "1.0"\nid: {identity}\ntitle: {name}\nintent: Preserve identity.\nenforcement: required\n'
        )
    repo = DirectiveRepository(built_in_dir=tmp_path)
    assert repo.get("ACME-001-FOO").title == "literal"
    assert repo.get("ACME_001_FOO").title == "alias"
    assert repo.get("acme-001-foo").title == "alias"


def test_literal_identity_keeps_org_chain_and_project_precedence(tmp_path: Path) -> None:
    directories = [tmp_path / name for name in ["builtin", "org1", "org2", "project"]]
    for index, directory in enumerate(directories):
        directory.mkdir()
        (directory / f"policy-{index}.directive.yaml").write_text(
            f'schema_version: "1.0"\nid: ACME-001-FOO\ntitle: Layer {index}\nintent: Preserve identity.\nenforcement: required\n'
        )
    repo = DirectiveRepository(built_in_dir=directories[0], org_dirs=directories[1:3], project_dir=directories[3])
    assert repo.get("ACME-001-FOO") == repo.list_all()[0]
    assert repo.get("ACME-001-FOO").title == "Layer 3"
