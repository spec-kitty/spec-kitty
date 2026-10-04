"""FR-011 regression at the mission_brief reader layer.

The intake scanner's ``read_brief()`` already distinguishes a missing
file from a corrupt one (covered in
``tests/unit/intake/test_missing_vs_corrupt.py``). The first review of
mission ``stability-and-hygiene-hardening-2026-04`` caught that the
production reader functions in :mod:`specify_cli.mission_brief` still
collapsed every failure to ``None``: a corrupt provenance YAML or an
I/O error on the brief file looked identical to "no brief".

These tests pin the post-fix behaviour:

* Missing file → return ``None`` (legitimate "no brief").
* File present but undecodable / unreadable / non-mapping →
  raise :class:`IntakeFileUnreadableError`.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests._support.eacces import deny_path_method
from specify_cli.intake.errors import IntakeFileUnreadableError
from specify_cli.mission_brief import (
    BRIEF_SOURCE_FILENAME,
    MISSION_BRIEF_FILENAME,
    read_brief_source,
    read_mission_brief,
)


pytestmark = [pytest.mark.fast]


# ---------------------------------------------------------------------------
# read_mission_brief — happy path / missing path
# ---------------------------------------------------------------------------


def test_read_mission_brief_returns_none_when_file_is_absent(tmp_path: Path) -> None:
    assert read_mission_brief(tmp_path) is None


def test_read_mission_brief_returns_text_when_present(tmp_path: Path) -> None:
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / MISSION_BRIEF_FILENAME).write_text(
        "# my brief\n", encoding="utf-8"
    )
    assert read_mission_brief(tmp_path) == "# my brief\n"


# ---------------------------------------------------------------------------
# read_mission_brief — corrupt (FR-011 distinction)
# ---------------------------------------------------------------------------


def test_read_mission_brief_raises_on_invalid_utf8(tmp_path: Path) -> None:
    """A brief file that contains invalid UTF-8 is corrupt, not missing."""
    (tmp_path / ".kittify").mkdir()
    bad = tmp_path / ".kittify" / MISSION_BRIEF_FILENAME
    bad.write_bytes(b"\xff\xfe not valid utf-8 \xc0\xc1")

    with pytest.raises(IntakeFileUnreadableError) as ei:
        read_mission_brief(tmp_path)

    # The structured error must carry the path so the CLI surface can
    # render it without re-deriving anything.
    assert str(bad) in str(ei.value)


# ---------------------------------------------------------------------------
# read_brief_source — happy path / missing path
# ---------------------------------------------------------------------------


def test_read_brief_source_returns_none_when_file_is_absent(tmp_path: Path) -> None:
    assert read_brief_source(tmp_path) is None


def test_read_brief_source_returns_dict_when_valid(tmp_path: Path) -> None:
    """A complete brief pair (sidecar + commit marker) returns the parsed dict."""
    (tmp_path / ".kittify").mkdir()
    # P2.5 pair-atomicity: read_brief_source returns None unless brief.md
    # also exists (it is the commit marker). A complete pair must include
    # both files for the parsed dict to be surfaced.
    (tmp_path / ".kittify" / MISSION_BRIEF_FILENAME).write_text(
        "# brief\n", encoding="utf-8"
    )
    (tmp_path / ".kittify" / BRIEF_SOURCE_FILENAME).write_text(
        "source_file: /nonexistent/plan.md\n"
        "ingested_at: 2026-04-26T00:00:00Z\n"
        "brief_hash: abc123\n",
        encoding="utf-8",
    )
    out = read_brief_source(tmp_path)
    assert isinstance(out, dict)
    assert out["source_file"] == "/nonexistent/plan.md"


def test_read_brief_source_returns_none_when_yaml_is_empty(tmp_path: Path) -> None:
    """An empty YAML file is treated as 'no brief', matching prior behavior."""
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / BRIEF_SOURCE_FILENAME).write_text("", encoding="utf-8")
    assert read_brief_source(tmp_path) is None


# ---------------------------------------------------------------------------
# read_brief_source — corrupt (FR-011 distinction)
# ---------------------------------------------------------------------------


def test_read_brief_source_raises_on_invalid_yaml(tmp_path: Path) -> None:
    """Malformed YAML is corrupt; must raise, not silently return None."""
    (tmp_path / ".kittify").mkdir()
    bad = tmp_path / ".kittify" / BRIEF_SOURCE_FILENAME
    # YAML scanner error (mismatched braces / tabs in flow context).
    bad.write_text("key: {unbalanced\n  - tabs and braces are illegal\n", encoding="utf-8")

    with pytest.raises(IntakeFileUnreadableError) as ei:
        read_brief_source(tmp_path)

    assert str(bad) in str(ei.value)


def test_read_brief_source_raises_on_non_mapping_yaml(tmp_path: Path) -> None:
    """YAML that parses to a non-dict (e.g. a list) is structurally corrupt."""
    (tmp_path / ".kittify").mkdir()
    bad = tmp_path / ".kittify" / BRIEF_SOURCE_FILENAME
    bad.write_text("- one\n- two\n", encoding="utf-8")

    with pytest.raises(IntakeFileUnreadableError) as ei:
        read_brief_source(tmp_path)

    assert "mapping" in str(ei.value).lower() or "list" in str(ei.value).lower()


def test_read_brief_source_raises_on_invalid_utf8(tmp_path: Path) -> None:
    (tmp_path / ".kittify").mkdir()
    bad = tmp_path / ".kittify" / BRIEF_SOURCE_FILENAME
    bad.write_bytes(b"source_file: \xff\xfe\xff\n")

    with pytest.raises(IntakeFileUnreadableError):
        read_brief_source(tmp_path)


# ---------------------------------------------------------------------------
# Permission-denied path
# ---------------------------------------------------------------------------


def test_read_mission_brief_raises_on_permission_denied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".kittify").mkdir()
    locked = tmp_path / ".kittify" / MISSION_BRIEF_FILENAME
    locked.write_text("# brief\n", encoding="utf-8")
    # Deny at the read seam instead of chmod(0): root bypasses file mode bits,
    # so a chmod-based setup gave a different verdict per uid (#5622).
    deny_path_method(monkeypatch, "read_text", locked)

    with pytest.raises(IntakeFileUnreadableError):
        read_mission_brief(tmp_path)
