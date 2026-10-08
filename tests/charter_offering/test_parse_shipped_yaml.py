"""``parse_shipped_yaml`` parses each shipped file at most once per change (#5526)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.offering import yaml_utils
from charter.offering.yaml_utils import parse_shipped_yaml

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.fixture
def parses(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    monkeypatch.setattr(yaml_utils, "_SHIPPED_DOCUMENT_MEMO", {})
    return []


def _counting_parser(calls: list[Path]) -> Any:
    yaml = YAML(typ="safe")

    def _parse(path: Path) -> Any:
        calls.append(path)
        return yaml.load(path)

    return _parse


def test_repeat_reads_parse_once_and_return_independent_copies(tmp_path: Path, parses: list[Path]) -> None:
    path = tmp_path / "artifact.yaml"
    path.write_text("id: ONE\ntags: [a]\n", encoding="utf-8")
    parse = _counting_parser(parses)

    first = parse_shipped_yaml(path, parse, variant="safe")
    first["tags"].append("mutated")
    second = parse_shipped_yaml(path, parse, variant="safe")

    assert parses == [path]
    assert second == {"id": "ONE", "tags": ["a"]}


def test_an_edited_file_is_reparsed(tmp_path: Path, parses: list[Path]) -> None:
    path = tmp_path / "artifact.yaml"
    path.write_text("id: ONE\n", encoding="utf-8")
    parse = _counting_parser(parses)

    assert parse_shipped_yaml(path, parse, variant="safe") == {"id": "ONE"}
    path.write_text("id: TWO-CHANGED\n", encoding="utf-8")

    assert parse_shipped_yaml(path, parse, variant="safe") == {"id": "TWO-CHANGED"}
    assert len(parses) == 2


def test_variants_never_share_an_entry(tmp_path: Path, parses: list[Path]) -> None:
    path = tmp_path / "artifact.yaml"
    path.write_text("id: ONE\n", encoding="utf-8")
    parse = _counting_parser(parses)

    parse_shipped_yaml(path, parse, variant="safe")
    parse_shipped_yaml(path, parse, variant="safe-text")

    assert len(parses) == 2


def test_parse_errors_propagate_and_are_not_cached(tmp_path: Path, parses: list[Path]) -> None:
    path = tmp_path / "artifact.yaml"
    path.write_text("id: [unclosed\n", encoding="utf-8")
    parse = _counting_parser(parses)

    for _ in range(2):
        with pytest.raises(YAMLError, match="flow sequence"):
            parse_shipped_yaml(path, parse, variant="safe")

    assert len(parses) == 2
    assert yaml_utils._SHIPPED_DOCUMENT_MEMO == {}


def test_a_missing_file_raises(tmp_path: Path, parses: list[Path]) -> None:
    with pytest.raises(FileNotFoundError):
        parse_shipped_yaml(tmp_path / "absent.yaml", _counting_parser(parses), variant="safe")
    assert parses == []
