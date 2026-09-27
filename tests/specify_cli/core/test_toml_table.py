"""Coverage for the shared atomic TOML-table rewrite extracted from
``zeitgeist_client.moments.write_agents_mode`` (WP01/T002).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from specify_cli.core.toml_table import write_toml_table_key

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _read(path: Path) -> dict[str, object]:
    with path.open("rb") as fh:
        return tomllib.load(fh)


class TestWriteTomlTableKey:
    def test_creates_a_fresh_file(self, tmp_path: Path) -> None:
        path = tmp_path / "nested" / "config.toml"

        written = write_toml_table_key(path, table="hosted", key="drain", value=True)

        assert written == path
        assert _read(path) == {"hosted": {"drain": True}}

    def test_preserves_unrelated_tables_and_keys(self, tmp_path: Path) -> None:
        path = tmp_path / "config.toml"
        path.write_text('[hosted]\nother_key = "keep"\n[unrelated]\nvalue = 1\n')

        write_toml_table_key(path, table="hosted", key="drain", value=True)

        document = _read(path)
        assert document["hosted"] == {"other_key": "keep", "drain": True}
        assert document["unrelated"] == {"value": 1}

    def test_overwrites_an_existing_key(self, tmp_path: Path) -> None:
        path = tmp_path / "config.toml"
        path.write_text("[hosted]\ndrain = false\n")

        write_toml_table_key(path, table="hosted", key="drain", value=True)

        assert _read(path)["hosted"]["drain"] is True  # type: ignore[index]

    def test_default_strict_false_tolerates_a_corrupt_file(self, tmp_path: Path) -> None:
        path = tmp_path / "config.toml"
        path.write_text("not [ valid toml")

        write_toml_table_key(path, table="hosted", key="drain", value=True)

        assert _read(path) == {"hosted": {"drain": True}}

    def test_strict_raises_on_a_corrupt_file_and_leaves_bytes_unchanged(self, tmp_path: Path) -> None:
        path = tmp_path / "config.toml"
        original = b"not [ valid toml"
        path.write_bytes(original)

        with pytest.raises(tomllib.TOMLDecodeError):
            write_toml_table_key(path, table="hosted", key="drain", value=True, strict=True)

        assert path.read_bytes() == original

    def test_strict_still_starts_from_empty_on_a_missing_file(self, tmp_path: Path) -> None:
        path = tmp_path / "config.toml"

        written = write_toml_table_key(path, table="hosted", key="drain", value=True, strict=True)

        assert written == path
        assert _read(path) == {"hosted": {"drain": True}}
