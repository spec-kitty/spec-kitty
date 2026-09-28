"""Tests for charter hasher module."""

import pytest
from pathlib import Path

from ruamel.yaml import YAML

from charter.hasher import hash_content, hash_charter, is_stale

pytestmark = pytest.mark.fast

def test_hash_content_deterministic():
    """Hash function produces consistent output for same content."""
    content = "# My Charter\n\nSome content here."

    hash1 = hash_content(content)
    hash2 = hash_content(content)

    assert hash1 == hash2
    assert hash1.startswith("sha256:")


def test_hash_content_whitespace_normalization():
    """Hash normalizes trailing whitespace but preserves internal formatting."""
    content1 = "# Charter\n\nContent."
    content2 = "# Charter\n\nContent.\n\n\n"  # Extra trailing newlines
    content3 = "# Charter\n\nContent.\t  \n"  # Trailing tabs and spaces

    hash1 = hash_content(content1)
    hash2 = hash_content(content2)
    hash3 = hash_content(content3)

    # All should produce same hash after normalization
    assert hash1 == hash2 == hash3


def test_hash_content_crlf_and_cr_normalize_to_lf():
    """`hash_content` delegates its newline step to `kernel.text_decode.normalize_newlines`
    (D5, #4998, WP01) -- CRLF and lone-CR variants of the same content must hash identically
    to the LF form, and the digest must be byte-for-byte the pinned value below."""
    lf = "# Charter\nline one\nline two\nline three\n"
    crlf = "# Charter\r\nline one\r\nline two\r\nline three\r\n"
    cr = "# Charter\rline one\rline two\rline three\r"

    expected = "sha256:d16c8cec5f460428fdabc97b00f41d49a40bd5881c50b8ed4ae939dbb96f9444"

    assert hash_content(lf) == expected
    assert hash_content(crlf) == expected
    assert hash_content(cr) == expected


def test_hash_content_internal_whitespace_preserved():
    """Hash preserves internal whitespace differences."""
    content1 = "# Charter\nContent."
    content2 = "# Charter\n\nContent."  # Extra newline

    hash1 = hash_content(content1)
    hash2 = hash_content(content2)

    # Should be different because internal whitespace differs
    assert hash1 != hash2


def test_hash_charter_reads_file(tmp_path: Path):
    """hash_charter reads file and hashes content."""
    charter_file = tmp_path / "charter.md"
    charter_file.write_text("# Test Charter\n\nRules here.", encoding="utf-8")

    result = hash_charter(charter_file)

    assert result.startswith("sha256:")
    # Should match hash_content of same text
    expected = hash_content("# Test Charter\n\nRules here.")
    assert result == expected


def test_is_stale_no_metadata(tmp_path: Path):
    """is_stale returns True when metadata doesn't exist."""
    charter_file = tmp_path / "charter.md"
    charter_file.write_text("# Charter", encoding="utf-8")

    metadata_file = tmp_path / "metadata.yaml"

    stale, current_hash, stored_hash = is_stale(charter_file, metadata_file)

    assert stale is True
    assert current_hash.startswith("sha256:")
    assert stored_hash == ""


def test_is_stale_matching_hash(tmp_path: Path):
    """is_stale returns False when hashes match."""
    charter_file = tmp_path / "charter.md"
    content = "# Charter\n\nRules."
    charter_file.write_text(content, encoding="utf-8")

    # Create metadata with matching hash
    metadata_file = tmp_path / "metadata.yaml"
    expected_hash = hash_content(content)

    yaml = YAML()
    metadata = {"charter_hash": expected_hash}
    yaml.dump(metadata, metadata_file)

    stale, current_hash, stored_hash = is_stale(charter_file, metadata_file)

    assert stale is False
    assert current_hash == expected_hash
    assert stored_hash == expected_hash


def test_is_stale_mismatched_hash(tmp_path: Path):
    """is_stale returns True when hashes don't match."""
    charter_file = tmp_path / "charter.md"
    charter_file.write_text("# New Content", encoding="utf-8")

    # Create metadata with old hash
    metadata_file = tmp_path / "metadata.yaml"
    old_hash = hash_content("# Old Content")

    yaml = YAML()
    metadata = {"charter_hash": old_hash}
    yaml.dump(metadata, metadata_file)

    stale, current_hash, stored_hash = is_stale(charter_file, metadata_file)

    assert stale is True
    assert current_hash != old_hash
    assert stored_hash == old_hash


def test_is_stale_empty_metadata(tmp_path: Path):
    """is_stale handles empty metadata file."""
    charter_file = tmp_path / "charter.md"
    charter_file.write_text("# Charter", encoding="utf-8")

    # Create empty metadata file
    metadata_file = tmp_path / "metadata.yaml"
    metadata_file.write_text("", encoding="utf-8")

    stale, current_hash, stored_hash = is_stale(charter_file, metadata_file)

    assert stale is True
    assert current_hash.startswith("sha256:")
    assert stored_hash == ""


def test_is_stale_missing_hash_field(tmp_path: Path):
    """is_stale handles metadata without charter_hash field."""
    charter_file = tmp_path / "charter.md"
    charter_file.write_text("# Charter", encoding="utf-8")

    # Create metadata without charter_hash field
    metadata_file = tmp_path / "metadata.yaml"
    yaml = YAML()
    metadata = {"timestamp_utc": "2026-01-01T00:00:00Z"}
    yaml.dump(metadata, metadata_file)

    stale, current_hash, stored_hash = is_stale(charter_file, metadata_file)

    assert stale is True
    assert current_hash.startswith("sha256:")
    assert stored_hash == ""
