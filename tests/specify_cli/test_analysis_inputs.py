"""Material dependency closure is stable across incidental runtime writes."""

import subprocess
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


def _generated_charter_in_second_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Compile from this checkout, then write the generated catalog into another checkout."""
    from charter.activation.compiler import compile_charter, write_compiled_charter
    from charter.activation.interview import default_interview

    monkeypatch.delenv("SPEC_KITTY_PACKS_ROOT", raising=False)
    monkeypatch.delenv("SPEC_KITTY_TEMPLATE_ROOT", raising=False)

    checkout_b = tmp_path / "checkout-b"
    kittify = checkout_b / ".kittify"
    kittify.mkdir(parents=True)
    subprocess.run(["git", "init", "--quiet", str(checkout_b)], check=True)
    (kittify / "config.yaml").write_text("charter: .kittify/charter/charter.yaml\n", encoding="utf-8")

    checkout_a = Path(__file__).resolve().parents[2]
    compiled = compile_charter(
        mission="software-dev",
        interview=default_interview(mission="software-dev", profile="minimal"),
        repo_root=checkout_a,
    )
    charter_dir = kittify / "charter"
    write_compiled_charter(charter_dir, compiled, repo_root=checkout_b)
    return checkout_b, charter_dir / "charter.yaml"


def test_charter_generated_from_checkout_a_collects_in_checkout_b(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A generated catalog refers to the current package, never checkout A's home path."""
    from ruamel.yaml import YAML
    from specify_cli.analysis_inputs import collect_material_inputs

    checkout_b, charter_path = _generated_charter_in_second_checkout(tmp_path, monkeypatch)
    charter = YAML(typ="safe").load(charter_path.read_text(encoding="utf-8"))
    template_ref = next(ref for ref in charter["catalog"]["references"] if ref["kind"] == "template_set")

    assert template_ref["source_path"] == ("${SPEC_KITTY_PACKS_ROOT}/built-in/missions/software-dev/mission.yaml")
    inputs = collect_material_inputs(checkout_b / "kitty-specs" / "second-checkout", checkout_b)
    assert "package:built-in" in inputs


def test_external_mutable_catalog_source_still_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Portable bundled references do not weaken rejection of external mutable sources."""
    from specify_cli.analysis_inputs import MaterialInputError, collect_material_inputs
    from charter.activation.charter_yaml_io import load_charter_yaml, update_charter_yaml_section

    checkout_b, charter_path = _generated_charter_in_second_checkout(tmp_path, monkeypatch)
    mission = checkout_b / "kitty-specs" / "second-checkout"
    collect_material_inputs(mission, checkout_b)

    external_source = tmp_path / "external-authority" / "custom.yaml"
    external_source.parent.mkdir()
    external_source.write_text("id: external\n", encoding="utf-8")

    catalog = load_charter_yaml(charter_path)["catalog"]
    catalog["references"].append(
        {
            "id": "DIRECTIVE:external",
            "kind": "directive",
            "title": "External mutable authority",
            "summary": "test control",
            "source_path": str(external_source),
            "local_path": "_LIBRARY/external.md",
        }
    )
    update_charter_yaml_section(charter_path, "catalog", catalog)

    with pytest.raises(MaterialInputError, match="External mutable analysis authority is unsupported"):
        collect_material_inputs(mission, checkout_b)


def test_malformed_wp_definition_is_refused(tmp_path: Path):
    from specify_cli.analysis_inputs import MaterialInputError, collect_material_inputs

    mission = tmp_path / "kitty-specs/test"
    (mission / "tasks").mkdir(parents=True)
    (mission / "tasks/WP01-test.md").write_text("missing definition frontmatter")
    with pytest.raises(MaterialInputError, match="Invalid WP definition"):
        collect_material_inputs(mission, tmp_path)
