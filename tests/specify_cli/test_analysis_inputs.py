"""Material dependency closure is stable across incidental runtime writes."""

from pathlib import Path

import pytest


def test_bundled_authority_failure_uses_charter_exception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from charter.pack_paths import PackRootNotFound
    from specify_cli import analysis_inputs

    def unavailable():
        raise PackRootNotFound("built-in")

    monkeypatch.setattr(analysis_inputs, "built_in_root", unavailable)
    with pytest.raises(analysis_inputs.MaterialInputError, match="Bundled analysis authority unavailable"):
        analysis_inputs.collect_material_inputs(tmp_path / "kitty-specs/test", tmp_path)


def test_declared_authority_and_absent_sentinel(tmp_path: Path):
    from specify_cli.analysis_inputs import collect_material_inputs

    charter = tmp_path / ".kittify/charter"
    charter.mkdir(parents=True)
    (tmp_path / ".kittify/config.yaml").write_text("charter: .kittify/charter/charter.yaml\n")
    (charter / "charter.yaml").write_text("governance:\n  doctrine:\n    authority_paths: [authority]\n    governance_references: [missing.md]\n")
    mission = tmp_path / "kitty-specs/test"
    (mission / "tasks").mkdir(parents=True)
    for name in ("spec.md", "plan.md", "tasks.md", "meta.json"):
        (mission / name).write_text("{}" if name.endswith("json") else name)
    authority = tmp_path / "authority"
    authority.mkdir()
    (authority / "rule.md").write_text("rule")
    before = collect_material_inputs(mission, tmp_path)
    assert before["material:missing.md"]["sha256"] is None
    assert "material:authority/rule.md" in before
    (charter / "context.json").write_text("runtime output")
    (mission / "status.events.jsonl").write_text("runtime output")
    assert collect_material_inputs(mission, tmp_path) == before
    (tmp_path / "missing.md").write_text("new authority")
    assert collect_material_inputs(mission, tmp_path) != before


def test_declared_authority_symlink_escape_rejected(tmp_path: Path):
    from specify_cli.analysis_inputs import MaterialInputError, collect_material_inputs

    root = tmp_path / "repo"
    (root / ".kittify/charter").mkdir(parents=True)
    (root / ".kittify/config.yaml").write_text("charter: .kittify/charter/charter.yaml\n")
    (root / ".kittify/charter/charter.yaml").write_text("governance:\n  doctrine:\n    authority_paths: [authority]\n")
    (root / "authority").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(MaterialInputError, match="symlink"):
        collect_material_inputs(root / "kitty-specs/test", root)


def test_wp_runtime_fields_do_not_change_definition_hash(tmp_path: Path):
    from specify_cli.analysis_inputs import collect_material_inputs

    mission = tmp_path / "kitty-specs/test"
    (mission / "tasks").mkdir(parents=True)
    wp = mission / "tasks/WP01-test.md"
    wp.write_text("---\nwork_package_id: WP01\nlane: planned\n---\nDefinition.\n")
    before = collect_material_inputs(mission, tmp_path)
    wp.write_text("---\nwork_package_id: WP01\nlane: in_progress\n---\nDefinition.\n")
    assert collect_material_inputs(mission, tmp_path) == before
    wp.write_text("---\nwork_package_id: WP01\nlane: in_progress\n---\nChanged definition.\n")
    assert collect_material_inputs(mission, tmp_path) != before


@pytest.mark.parametrize("text", ["[not: valid", "[]"])
def test_malformed_configuration_refuses_dependency_proof(tmp_path: Path, text: str):
    from specify_cli.analysis_inputs import MaterialInputError, collect_material_inputs

    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify/config.yaml").write_text(text)
    with pytest.raises(MaterialInputError):
        collect_material_inputs(tmp_path / "kitty-specs/test", tmp_path)


@pytest.mark.parametrize("declaration", ["charter: []", "charter: {authority_paths: invalid}", "charter: {authority_paths: ['../outside']}"])
def test_invalid_or_escaping_authority_refuses(tmp_path: Path, declaration: str):
    from specify_cli.analysis_inputs import MaterialInputError, collect_material_inputs

    charter = tmp_path / ".kittify/charter"
    charter.mkdir(parents=True)
    (charter / "charter.yaml").write_text(f"governance:\n  {declaration}\n")
    with pytest.raises(MaterialInputError):
        collect_material_inputs(tmp_path / "kitty-specs/test", tmp_path)


def test_external_charter_pointer_refuses(tmp_path: Path):
    from specify_cli.analysis_inputs import MaterialInputError, collect_material_inputs

    root = tmp_path / "repo"
    (root / ".kittify").mkdir(parents=True)
    external = tmp_path / "authority.yaml"
    external.write_text("{}")
    (root / ".kittify/config.yaml").write_text(f"charter: {external}\n")
    with pytest.raises(MaterialInputError, match="External mutable"):
        collect_material_inputs(root / "kitty-specs/test", root)


def test_catalog_source_and_library_content_are_material(tmp_path: Path):
    from specify_cli.analysis_inputs import collect_material_inputs

    charter = tmp_path / ".kittify/charter"
    (charter / "_LIBRARY").mkdir(parents=True)
    (charter / "charter.yaml").write_text(
        "catalog:\n- source_path: source.md\n  local_path: _LIBRARY/ref.md\n- source_path: '${SPEC_KITTY_PACKS_ROOT}/built-in/example.yaml'\n"
    )
    (tmp_path / "source.md").write_text("source")
    (charter / "_LIBRARY/ref.md").write_text("resolved authority")
    mission = tmp_path / "kitty-specs/test"
    before = collect_material_inputs(mission, tmp_path)
    assert "material:source.md" in before
    assert "material:.kittify/charter/_LIBRARY/ref.md" in before
    (tmp_path / "source.md").write_text("changed source")
    assert collect_material_inputs(mission, tmp_path) != before


def test_malformed_wp_definition_is_refused(tmp_path: Path):
    from specify_cli.analysis_inputs import MaterialInputError, collect_material_inputs

    mission = tmp_path / "kitty-specs/test"
    (mission / "tasks").mkdir(parents=True)
    (mission / "tasks/WP01-test.md").write_text("missing definition frontmatter")
    with pytest.raises(MaterialInputError, match="Invalid WP definition"):
        collect_material_inputs(mission, tmp_path)
