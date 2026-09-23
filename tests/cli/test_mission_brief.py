"""Unit tests for ``specify_cli.mission_brief``."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from specify_cli.mission_brief import (
    BRIEF_SOURCE_FILENAME,
    MISSION_BRIEF_FILENAME,
    clear_mission_brief,
    read_brief_source,
    read_mission_brief,
    write_mission_brief,
)

pytestmark = pytest.mark.fast

RAW_CONTENT = "# My Plan\n\nDo the thing.\n"


def test_write_creates_kittify_if_absent(tmp_path: Path) -> None:
    """write_mission_brief creates .kittify/ when it does not exist."""
    kittify = tmp_path / ".kittify"
    assert not kittify.exists()

    write_mission_brief(tmp_path, RAW_CONTENT, "plan.md")

    assert kittify.is_dir()


def test_write_brief_content(tmp_path: Path) -> None:
    """mission-brief.md contains the provenance header then the original content."""
    write_mission_brief(tmp_path, RAW_CONTENT, "plan.md")

    brief_path = tmp_path / ".kittify" / MISSION_BRIEF_FILENAME
    text = brief_path.read_text(encoding="utf-8")

    assert "<!-- spec-kitty intake: ingested from plan.md at " in text
    assert "<!-- brief_hash: " in text
    assert RAW_CONTENT in text
    header_end = text.index("<!-- brief_hash:")
    content_start = text.index(RAW_CONTENT)
    assert header_end < content_start


def test_write_brief_hash_is_sha256_of_raw_content(tmp_path: Path) -> None:
    """The brief_hash in both the header and YAML matches SHA-256 of raw content."""
    write_mission_brief(tmp_path, RAW_CONTENT, "plan.md")

    expected_hash = hashlib.sha256(RAW_CONTENT.encode()).hexdigest()  # noqa: TID251 — mission-brief content fingerprint, not charter freshness hashing

    brief_path = tmp_path / ".kittify" / MISSION_BRIEF_FILENAME
    text = brief_path.read_text(encoding="utf-8")
    assert f"<!-- brief_hash: {expected_hash} -->" in text

    source = read_brief_source(tmp_path)
    assert source is not None
    assert source["brief_hash"] == expected_hash


def test_write_source_yaml_fields(tmp_path: Path) -> None:
    """brief-source.yaml has source_file, ingested_at, and brief_hash fields."""
    write_mission_brief(tmp_path, RAW_CONTENT, "plan.md")

    source = read_brief_source(tmp_path)
    assert source is not None
    assert "source_file" in source
    assert "ingested_at" in source
    assert "brief_hash" in source
    assert source["source_file"] == "plan.md"


def test_write_source_stdin(tmp_path: Path) -> None:
    """source_file is 'stdin' when that string is passed as the source."""
    write_mission_brief(tmp_path, RAW_CONTENT, "stdin")

    source = read_brief_source(tmp_path)
    assert source is not None
    assert source["source_file"] == "stdin"


def test_read_brief_returns_none_when_absent(tmp_path: Path) -> None:
    """read_mission_brief returns None when the file does not exist."""
    result = read_mission_brief(tmp_path)
    assert result is None


def test_read_brief_returns_content_when_present(tmp_path: Path) -> None:
    """read_mission_brief returns the full file content (header + body) when present."""
    write_mission_brief(tmp_path, RAW_CONTENT, "plan.md")

    result = read_mission_brief(tmp_path)
    assert result is not None
    assert RAW_CONTENT in result
    assert "<!-- spec-kitty intake:" in result


def test_read_source_returns_none_when_absent(tmp_path: Path) -> None:
    """read_brief_source returns None when the YAML file does not exist."""
    result = read_brief_source(tmp_path)
    assert result is None


def test_read_source_returns_dict_when_present(tmp_path: Path) -> None:
    """read_brief_source returns a dict with expected keys when the file is present."""
    write_mission_brief(tmp_path, RAW_CONTENT, "plan.md")

    result = read_brief_source(tmp_path)
    assert isinstance(result, dict)
    assert "source_file" in result
    assert "ingested_at" in result
    assert "brief_hash" in result


def test_read_source_raises_on_non_mapping_yaml(tmp_path: Path) -> None:
    """FR-011: read_brief_source MUST raise on a corrupt YAML root.

    Pre-fix this returned None, collapsing 'corrupt sidecar' into the
    same state as 'no brief'. The mission stability-and-hygiene-hardening
    -2026-04 review caught the gap: callers cannot tell whether the brief
    is genuinely absent or whether the provenance file is malformed and
    needs operator attention. The reader now raises a structured
    IntakeFileUnreadableError; legitimate "no brief" still returns None
    (pinned by other tests in this module and by
    test_mission_brief_missing_vs_corrupt.py).
    """
    from specify_cli.intake.errors import IntakeFileUnreadableError

    source_path = tmp_path / ".kittify" / BRIEF_SOURCE_FILENAME
    source_path.parent.mkdir()
    source_path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    with pytest.raises(IntakeFileUnreadableError):
        read_brief_source(tmp_path)


def test_clear_removes_both_files(tmp_path: Path) -> None:
    """clear_mission_brief removes both artefacts."""
    write_mission_brief(tmp_path, RAW_CONTENT, "plan.md")

    brief_path = tmp_path / ".kittify" / MISSION_BRIEF_FILENAME
    source_path = tmp_path / ".kittify" / BRIEF_SOURCE_FILENAME
    assert brief_path.exists()
    assert source_path.exists()

    clear_mission_brief(tmp_path)

    assert not brief_path.exists()
    assert not source_path.exists()


def test_clear_is_idempotent(tmp_path: Path) -> None:
    """clear_mission_brief does not raise when files are already absent."""
    clear_mission_brief(tmp_path)
    clear_mission_brief(tmp_path)


def test_write_twice_overwrites(tmp_path: Path) -> None:
    """A second write_mission_brief call with overwrite=True replaces the
    first (hash changes). #4921: the second call must explicitly authorize
    the overwrite — an unauthorized call now refuses via BriefExistsError
    (see test_mission_brief_overwrite_chokepoint.py) instead of the old
    unconditional-clobber default."""
    write_mission_brief(tmp_path, RAW_CONTENT, "plan.md")
    first_hash = hashlib.sha256(RAW_CONTENT.encode()).hexdigest()  # noqa: TID251 — mission-brief content fingerprint, not charter freshness hashing

    new_content = "# New Plan\n\nDifferent content.\n"
    write_mission_brief(tmp_path, new_content, "plan.md", overwrite=True)
    second_hash = hashlib.sha256(new_content.encode()).hexdigest()  # noqa: TID251 — mission-brief content fingerprint, not charter freshness hashing

    source = read_brief_source(tmp_path)
    assert source is not None
    assert source["brief_hash"] == second_hash
    assert source["brief_hash"] != first_hash

    brief_text = read_mission_brief(tmp_path)
    assert brief_text is not None
    assert new_content in brief_text
    assert RAW_CONTENT not in brief_text


def test_write_packet_meta_lands_in_sidecar_without_changing_content_hash(
    tmp_path: Path,
) -> None:
    """Packet overlay fields are sidecar-only; brief_hash stays SHA-256 of raw content."""
    packet_meta = {
        "packet_version": 1,
        "source_tool": "example-tool",
        "source_mission": "widget-booking",
        "requirement_count": 2,
    }
    write_mission_brief(
        tmp_path, RAW_CONTENT, "packet.md", packet_meta=packet_meta
    )
    expected_hash = hashlib.sha256(RAW_CONTENT.encode()).hexdigest()  # noqa: TID251 — mission-brief content fingerprint, not charter freshness hashing
    source = read_brief_source(tmp_path)
    assert source is not None
    assert source["brief_hash"] == expected_hash
    assert source["source_tool"] == "example-tool"
    assert source["source_mission"] == "widget-booking"
    assert source["requirement_count"] == 2
    assert source["packet_version"] == 1
