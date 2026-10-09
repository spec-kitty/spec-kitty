"""Activation-key removal in the single writer (#3732 WP08, T041/T045).

``charter activate --preset`` replaces activation keys; a key the preset leaves
out is *removed*. Removal lives in the INV-9 single writer
(:func:`prepare_charter_yaml_section` / :func:`prepare_activation_write`), never
in a second writer, and must keep every other byte of the document.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.charter_yaml_io import apply_yaml_write, prepare_charter_yaml_section
from charter.activation.pack_manager import ACTIVATION_YAML_KEYS, prepare_activation_write

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_CHARTER_DOC = """\
# Project charter (comment kept)
governance:
  testing: strict   # inline comment kept
activated_directives:
- 001-architectural-integrity-standard
activated_kinds: [directives, tactics]
activated_skills:
- triage
catalog:
  mission: software-dev
"""

_CONFIG_DOC = """\
# config comment kept
vcs:
  type: git
activated_tactics:
- acceptance-test-first
activated_anti_patterns:
- some-smell
mission_type_activations:
- software-dev
"""


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_anti_patterns_key_is_in_the_activation_vocabulary() -> None:
    assert "activated_anti_patterns" in ACTIVATION_YAML_KEYS


def test_section_remove_drops_keys_and_preserves_every_other_byte(tmp_path: Path) -> None:
    charter = _write(tmp_path / "charter.yaml", _CHARTER_DOC)

    prepared = prepare_charter_yaml_section(charter, "activation", {}, remove=["activated_directives", "activated_kinds"])

    expected = _CHARTER_DOC.replace("activated_directives:\n- 001-architectural-integrity-standard\n", "").replace("activated_kinds: [directives, tactics]\n", "")
    assert prepared.desired_bytes.decode("utf-8") == expected
    assert charter.read_text(encoding="utf-8") == _CHARTER_DOC, "prepare never writes"


def test_section_remove_of_an_absent_key_is_a_no_op(tmp_path: Path) -> None:
    charter = _write(tmp_path / "charter.yaml", _CHARTER_DOC)

    prepared = prepare_charter_yaml_section(charter, "activation", {}, remove=["activated_paradigms"])

    assert prepared.desired_bytes.decode("utf-8") == _CHARTER_DOC


def test_section_remove_on_a_non_activation_section_raises(tmp_path: Path) -> None:
    charter = _write(tmp_path / "charter.yaml", _CHARTER_DOC)

    with pytest.raises(ValueError, match="only supported for the 'activation' section"):
        prepare_charter_yaml_section(charter, "governance", {"testing": "lax"}, remove=["activated_directives"])


def test_section_remove_of_an_unknown_key_raises(tmp_path: Path) -> None:
    charter = _write(tmp_path / "charter.yaml", _CHARTER_DOC)

    with pytest.raises(ValueError, match="Unknown activation key"):
        prepare_charter_yaml_section(charter, "activation", {}, remove=["governance"])


def test_section_key_both_written_and_removed_raises(tmp_path: Path) -> None:
    charter = _write(tmp_path / "charter.yaml", _CHARTER_DOC)

    with pytest.raises(ValueError, match="both written and removed"):
        prepare_charter_yaml_section(charter, "activation", {"activated_kinds": ["directives"]}, remove=["activated_kinds"])


def test_activation_write_removes_from_config_target(tmp_path: Path) -> None:
    config = _write(tmp_path / ".kittify" / "config.yaml", _CONFIG_DOC)

    apply_yaml_write(
        prepare_activation_write(tmp_path, {"activated_directives": ["024-locality-of-change"]}, remove=["activated_tactics", "activated_anti_patterns"])
    )

    text = config.read_text(encoding="utf-8")
    assert "activated_tactics" not in text
    assert "activated_anti_patterns" not in text
    assert "activated_directives:\n- 024-locality-of-change" in text
    assert text.startswith("# config comment kept\nvcs:\n  type: git\n")
    assert "mission_type_activations:\n- software-dev" in text


def test_activation_write_writes_anti_patterns(tmp_path: Path) -> None:
    config = _write(tmp_path / ".kittify" / "config.yaml", "vcs:\n  type: git\n")

    apply_yaml_write(prepare_activation_write(tmp_path, {"activated_anti_patterns": ["smell-a"]}))

    assert "activated_anti_patterns:\n- smell-a" in config.read_text(encoding="utf-8")


def test_activation_write_removes_from_pointed_charter_yaml(tmp_path: Path) -> None:
    config = _write(tmp_path / ".kittify" / "config.yaml", "charter: .kittify/charter/charter.yaml\n")
    charter = _write(tmp_path / ".kittify" / "charter" / "charter.yaml", _CHARTER_DOC)

    apply_yaml_write(prepare_activation_write(tmp_path, {}, remove=["activated_directives"]))

    assert "activated_directives" not in charter.read_text(encoding="utf-8")
    assert "activated_skills:\n- triage" in charter.read_text(encoding="utf-8"), "an ungoverned key is untouched"
    assert config.read_text(encoding="utf-8") == "charter: .kittify/charter/charter.yaml\n"


def test_activation_write_rejects_unknown_removal(tmp_path: Path) -> None:
    _write(tmp_path / ".kittify" / "config.yaml", _CONFIG_DOC)

    with pytest.raises(ValueError, match="Unknown activation key"):
        prepare_activation_write(tmp_path, {}, remove=["vcs"])


def test_activation_write_rejects_a_key_both_written_and_removed(tmp_path: Path) -> None:
    _write(tmp_path / ".kittify" / "config.yaml", _CONFIG_DOC)

    with pytest.raises(ValueError, match="both written and removed"):
        prepare_activation_write(tmp_path, {"activated_tactics": []}, remove=["activated_tactics"])


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("a: 1\nactivated_kinds: [directives]\ncatalog: 1\n", "a: 1\ncatalog: 1\n"),
        ("a: 1\nactivated_kinds: [directives]  # gate\ncatalog: 1\n", "a: 1\ncatalog: 1\n"),
        ("a: 1\nactivated_kinds: [directives]", "a: 1\n"),
        ("a: 1\nactivated_kinds:\n- directives\ncatalog: 1\n", "a: 1\ncatalog: 1\n"),
    ],
    ids=["flow", "flow-with-comment", "flow-last-line-no-newline", "block"],
)
def test_section_remove_leaves_no_blank_line(tmp_path: Path, before: str, after: str) -> None:
    charter = _write(tmp_path / "charter.yaml", before)

    prepared = prepare_charter_yaml_section(charter, "activation", {}, remove=["activated_kinds"])

    assert prepared.desired_bytes.decode("utf-8") == after
