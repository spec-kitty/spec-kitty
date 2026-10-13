"""Coverage for the shared atomic TOML-table rewrite extracted from
``zeitgeist_client.moments.write_agents_mode`` (WP01/T002).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from specify_cli.core.toml_table import UnreadableTomlTableError, write_toml_table_key

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

    def test_default_strict_false_refuses_a_present_but_unparseable_file(self, tmp_path: Path) -> None:
        # Regression for #5451: the non-strict default must NOT start from an
        # empty document and overwrite a present-but-unparseable file wholesale
        # (that silently dropped every other table/key, e.g. ``[sync].server_url``).
        # It now refuses and leaves the file byte-for-byte unchanged.
        path = tmp_path / "config.toml"
        original = b'[sync]\nserver_url = "http://127.0.0.1:9"\n\n[moments]\nkinds = ["WPStatusChanged"\n'
        path.write_bytes(original)

        with pytest.raises(UnreadableTomlTableError) as excinfo:
            write_toml_table_key(path, table="moments", key="agents", value="team")

        assert path.read_bytes() == original
        assert str(path) in str(excinfo.value)
        assert "Fix or remove" in str(excinfo.value)
        assert isinstance(excinfo.value.__cause__, tomllib.TOMLDecodeError)

    def test_default_strict_false_refuses_an_unreadable_file(self, tmp_path: Path) -> None:
        # A present-but-unreadable file (an OSError other than FileNotFoundError,
        # here a directory in the file's place) is also refused, never treated
        # as an empty document to overwrite.
        path = tmp_path / "config.toml"
        path.mkdir()

        with pytest.raises(UnreadableTomlTableError) as excinfo:
            write_toml_table_key(path, table="hosted", key="drain", value=True)

        assert path.is_dir()
        assert not path.with_suffix(path.suffix + ".tmp").exists()
        assert str(path) in str(excinfo.value)
        assert "Fix or remove" in str(excinfo.value)

    def test_default_strict_false_refuses_a_non_utf8_file(self, tmp_path: Path) -> None:
        # ``tomllib.load`` raises ``UnicodeDecodeError`` (neither a
        # ``TOMLDecodeError`` nor an ``OSError``) on non-UTF-8 bytes; that must
        # be refused too, never escape raw or start from an empty document.
        path = tmp_path / "config.toml"
        original = b'\xff\xfe[sync]\nserver_url = "http://127.0.0.1:9"\n'
        path.write_bytes(original)

        with pytest.raises(UnreadableTomlTableError) as excinfo:
            write_toml_table_key(path, table="hosted", key="drain", value=True)

        assert path.read_bytes() == original
        assert isinstance(excinfo.value.__cause__, UnicodeDecodeError)

    def test_strict_re_raises_the_original_error_on_a_non_utf8_file(self, tmp_path: Path) -> None:
        path = tmp_path / "config.toml"
        original = b"\xff\xfe[hosted]\ndrain = false\n"
        path.write_bytes(original)

        with pytest.raises(UnicodeDecodeError):
            write_toml_table_key(path, table="hosted", key="drain", value=True, strict=True)

        assert path.read_bytes() == original

    def test_default_strict_false_still_writes_a_missing_file(self, tmp_path: Path) -> None:
        # A genuinely absent file has nothing to preserve, so starting from an
        # empty document and writing is correct -- the absent-vs-unparseable
        # distinction the #5451 fix draws.
        path = tmp_path / "nested" / "config.toml"

        written = write_toml_table_key(path, table="hosted", key="drain", value=True)

        assert written == path
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
