"""FR-004: consistency checks preserve typed diagnostics for unreadable config."""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.consistency_check import _load_config_yaml_mapping
from charter.activation.pack_context import CharterPackConfigError

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.mark.parametrize("contents", [b"\xffbad", b"charter: [broken"])
def test_unreadable_config_mapping_names_file(tmp_path: Path, contents: bytes) -> None:
    config = tmp_path / "config.yaml"
    config.write_bytes(contents)
    with pytest.raises(CharterPackConfigError) as caught:
        _load_config_yaml_mapping(config)
    assert str(config) in caught.value.body


def test_directory_config_mapping_names_file(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.mkdir()
    with pytest.raises(CharterPackConfigError) as caught:
        _load_config_yaml_mapping(config)
    assert str(config) in caught.value.body


def test_missing_and_valid_config_mapping(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    assert _load_config_yaml_mapping(config) == {}
    config.write_text("activated_directives: [DIRECTIVE_001]\n", encoding="utf-8")
    assert _load_config_yaml_mapping(config) == {"activated_directives": ["DIRECTIVE_001"]}


def test_consistency_entry_point_reports_config_decode_failure(tmp_path: Path) -> None:
    from charter.activation.consistency_check import run_consistency_check
    from charter.activation.invocation_context import ProjectContext

    config = tmp_path / ".kittify" / "config.yaml"
    config.parent.mkdir()
    config.write_text("mission_type_activations: [software-dev]\n", encoding="utf-8")
    context = ProjectContext.from_repo(tmp_path)
    config.write_bytes(b"\xffbad")
    report = run_consistency_check(context)
    assert not report.coherent
    assert any("config.yaml" in message and "decode" in message for message in report.verification_errors)
