"""Strict preset loader: every rejection names the field (FR-019, T036/T040)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.packs.presets import (
    ActivationPreset,
    PresetFormatError,
    kind_gate_omissions,
    load_preset_file,
    preset_activation_key,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _write(directory: Path, stem: str, body: Any) -> Path:
    path = directory / f"{stem}.yaml"
    yaml = YAML()
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(body, handle)
    return path


def _valid(name: str = "team", **extra: Any) -> dict[str, Any]:
    return {"name": name, "description": "A team preset", **extra}


def test_valid_preset_loads_with_absent_and_empty_keys_preserved(tmp_path: Path) -> None:
    path = _write(tmp_path, "team", _valid(activated_directives=["010-specification-fidelity-requirement"], activated_tactics=[]))
    preset = load_preset_file(path)
    assert isinstance(preset, ActivationPreset)
    assert preset.name == "team"
    assert preset.source == path
    assert preset.activations == {"activated_directives": ("010-specification-fidelity-requirement",), "activated_tactics": ()}
    assert "activated_styleguides" not in preset.activations  # absent stays absent (unrestricted)
    assert preset.activated_kinds is None
    assert preset.mission_type_activations is None
    assert preset.listed_kinds() == (ArtifactKind.DIRECTIVE, ArtifactKind.TACTIC)


def test_anti_patterns_and_kind_gate_and_mission_types_load(tmp_path: Path) -> None:
    body = _valid(activated_anti_patterns=["big-ball-of-mud"], activated_kinds=["anti_patterns", "skills"], mission_type_activations=["research"])
    preset = load_preset_file(_write(tmp_path, "team", body))
    assert preset.activations == {preset_activation_key(ArtifactKind.ANTI_PATTERN): ("big-ball-of-mud",)}
    assert preset.activated_kinds == ("anti_patterns", "skills")
    assert preset.mission_type_activations == ("research",)


#: case -> (file stem, body, field the error must name).
REJECTIONS: dict[str, tuple[str, Any, str]] = {
    "unknown_key": ("team", _valid(unknown_key=1), "unknown_key"),
    "activated_skills": ("team", _valid(activated_skills=["x"]), "activated_skills"),
    "activated_glossary_packs": ("team", _valid(activated_glossary_packs=["x"]), "activated_glossary_packs"),
    "context_scoped_activations": ("team", _valid(activations=[{"kind": "directive", "id": "x"}]), "activations"),
    "name_not_stem": ("other", _valid(), "name"),
    "name_grammar": ("Bad_Name", _valid(name="Bad_Name"), "name"),
    "name_too_long": ("a" * 65, _valid(name="a" * 65), "name"),
    "name_not_string": ("team", {"name": 3, "description": "x"}, "name"),
    "name_missing": ("team", {"description": "x"}, "name"),
    "description_missing": ("team", {"name": "team"}, "description"),
    "description_empty": ("team", {"name": "team", "description": "  "}, "description"),
    "non_list_value": ("team", _valid(activated_tactics="acceptance-test-first"), "activated_tactics"),
    "duplicate_ids": ("team", _valid(activated_tactics=["a", "a"]), "activated_tactics"),
    "empty_string_id": ("team", _valid(activated_tactics=[""]), "activated_tactics"),
    "non_string_id": ("team", _valid(mission_type_activations=[1]), "mission_type_activations"),
    "unknown_kind_in_gate": ("team", _valid(activated_kinds=["widgets"]), "activated_kinds"),
}


@pytest.mark.parametrize("case", sorted(REJECTIONS))
def test_rejection_names_the_field(tmp_path: Path, case: str) -> None:
    stem, body, field = REJECTIONS[case]
    path = _write(tmp_path, stem, body)
    with pytest.raises(PresetFormatError) as excinfo:
        load_preset_file(path)
    assert excinfo.value.field == field
    assert excinfo.value.path == path
    assert field in str(excinfo.value) and path.name in str(excinfo.value)


def test_ungoverned_kinds_are_explained(tmp_path: Path) -> None:
    with pytest.raises(PresetFormatError, match="do not govern"):
        load_preset_file(_write(tmp_path, "team", _valid(activated_skills=["x"])))


def test_context_scoped_entries_are_explained(tmp_path: Path) -> None:
    with pytest.raises(PresetFormatError, match="context-scoped"):
        load_preset_file(_write(tmp_path, "team", _valid(activations=[])))


@pytest.mark.parametrize(
    ("text", "detail"),
    [("name: [unclosed\n", "YAML parse error"), ("- a\n- b\n", "mapping"), ("", "mapping")],
)
def test_unparseable_or_non_mapping_file(tmp_path: Path, text: str, detail: str) -> None:
    path = tmp_path / "team.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(PresetFormatError, match=detail) as excinfo:
        load_preset_file(path)
    assert excinfo.value.field == "<file>"


def test_unreadable_file(tmp_path: Path) -> None:
    path = tmp_path / "team.yaml"
    path.write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(PresetFormatError, match="cannot be read"):
        load_preset_file(path)


def test_kind_gate_omissions(tmp_path: Path) -> None:
    gated = load_preset_file(_write(tmp_path, "gated", _valid("gated", activated_kinds=["directives"], activated_directives=[], activated_tactics=["x"])))
    assert kind_gate_omissions(gated) == ("tactics",)
    ungated = load_preset_file(_write(tmp_path, "open", _valid("open", activated_tactics=["x"])))
    assert kind_gate_omissions(ungated) == ()
