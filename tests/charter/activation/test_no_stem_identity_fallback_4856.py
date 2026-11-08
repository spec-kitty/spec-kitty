"""An artifact YAML with no authored ``id`` has no identity (#4856).

``catalog._extract_artifact_id`` dropped the filename-stem fallback; its twins
(``kind_vocabulary._parse_id`` and the compiler's ``_index_yaml_assets``) must
apply the same single rule rather than keying on the cosmetic filename.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.activation import catalog, compiler, kind_vocabulary

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _write(directory: Path, name: str, body: str) -> Path:
    path = directory / name
    path.write_text(body, encoding="utf-8")
    return path


def test_parse_id_returns_none_without_authored_id(tmp_path: Path) -> None:
    path = _write(tmp_path, "my-stem.directive.yaml", "title: no id here\n")
    assert kind_vocabulary._parse_id(path, "id", YAML(typ="safe")) is None


def test_index_yaml_assets_skips_idless_entry(tmp_path: Path) -> None:
    _write(tmp_path, "my-stem.directive.yaml", "title: no id here\n")
    _write(tmp_path, "other.directive.yaml", "id: AUTHORED\ntitle: has id\n")
    index = compiler._index_yaml_assets(tmp_path, "*.directive.yaml")
    assert list(index) == ["authored"]


@pytest.mark.parametrize(
    ("body", "expected"),
    [("title: no id\n", None), ("id: AUTHORED\n", "AUTHORED")],
)
def test_catalog_and_kind_vocabulary_agree(tmp_path: Path, body: str, expected: str | None) -> None:
    path = _write(tmp_path, "my-stem.directive.yaml", body)
    from_catalog = catalog._extract_artifact_id(path, "id", None, YAML(typ="safe"))
    from_vocab = kind_vocabulary._parse_id(path, "id", YAML(typ="safe"))
    assert from_catalog == from_vocab == expected
