"""Regression tests for WP04 T020: resilient write in write_mission_brief."""
from __future__ import annotations

import pytest
import yaml
from pathlib import Path
from specify_cli.mission_brief import (
    BRIEF_SOURCE_FILENAME,
    MISSION_BRIEF_FILENAME,
    BriefExistsError,
    read_brief_source,
    read_mission_brief,
    write_mission_brief,
)


pytestmark = [pytest.mark.unit, pytest.mark.fast]

def test_write_mission_brief_success(tmp_path):
    """Both files exist after a successful call, no temp files left."""
    brief_path, source_path = write_mission_brief(tmp_path, "# Test brief", "test.md")
    assert brief_path.exists()
    assert source_path.exists()
    kittify = tmp_path / ".kittify"
    assert not list(kittify.glob(".tmp-brief-*.md"))
    assert not list(kittify.glob(".tmp-source-*.yaml"))


def test_write_mission_brief_refuses_brief_without_source_by_default(tmp_path):
    """#4910/#4921: a brief present with no source sidecar is UNKNOWN
    provenance, not recoverable partial state — the existence-alone gate
    refuses without explicit ``overwrite=True`` and leaves the original bytes
    untouched (superseded the old "post-replace-1 crash auto-recovers"
    assumption, which was the #4910 bug class)."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / MISSION_BRIEF_FILENAME).write_text("# partial", encoding="utf-8")
    # No brief-source.yaml — unknown provenance, not partial state.
    with pytest.raises(BriefExistsError):
        write_mission_brief(tmp_path, "# recovered", "test.md")
    assert (kittify / MISSION_BRIEF_FILENAME).read_text(encoding="utf-8") == "# partial"
    assert not (kittify / BRIEF_SOURCE_FILENAME).exists()


def test_write_mission_brief_overwrite_true_recovers_from_brief_without_source(tmp_path):
    """The same brief-without-source state recovers when the caller explicitly
    authorizes it via ``overwrite=True`` (e.g. CLI ``--force``)."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / MISSION_BRIEF_FILENAME).write_text("# partial", encoding="utf-8")
    # No brief-source.yaml — partial state
    brief_path, source_path = write_mission_brief(tmp_path, "# recovered", "test.md", overwrite=True)
    assert brief_path.exists()
    assert source_path.exists()
    # Content should be the new content, not the partial
    assert "recovered" in brief_path.read_text(encoding="utf-8")


def test_write_mission_brief_recovers_from_source_without_brief(tmp_path):
    """If source exists without brief, next call recovers."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / BRIEF_SOURCE_FILENAME).write_text(
        yaml.safe_dump({"source_file": "partial", "ingested_at": "t", "brief_hash": "h"}),
        encoding="utf-8",
    )
    brief_path, source_path = write_mission_brief(tmp_path, "# new", "test.md")
    assert brief_path.exists()
    assert source_path.exists()


def test_write_mission_brief_pre_replace_crash_leaves_no_final_files(tmp_path, monkeypatch):
    """A crash during the second atomic write (after the brief landed) must not
    leave a half-written final source file or a stranded ``.tmp`` file.

    WP02 T010 routes the writes through ``atomic_write_text`` (open + fsync +
    replace), so the natural injection point for a "crash" is ``os.replace``.
    The pre-WP02 implementation patched ``Path.write_text``; the same
    invariant — no partial final state — still holds.
    """
    import os as _os

    call_count = [0]
    original_replace = _os.replace

    def patched_replace(src, dst):
        call_count[0] += 1
        if call_count[0] == 2:
            raise OSError("simulated crash")
        return original_replace(src, dst)

    monkeypatch.setattr("specify_cli.intake.brief_writer.os.replace", patched_replace)
    with pytest.raises(OSError):
        write_mission_brief(tmp_path, "# Test", "test.md")
    kittify = tmp_path / ".kittify"
    # Source lands first and brief.md is the commit marker. A crash during
    # the second rename leaves source.yaml on disk, but the reader surface
    # still treats that state as "no brief".
    assert (kittify / BRIEF_SOURCE_FILENAME).exists()
    assert not (kittify / MISSION_BRIEF_FILENAME).exists()
    assert read_mission_brief(tmp_path) is None
    assert read_brief_source(tmp_path) is None
    # No .tmp leftovers from either write.
    assert not list(kittify.glob("*.tmp"))


def test_write_mission_brief_return_value(tmp_path):
    result = write_mission_brief(tmp_path, "# content", "source.md")
    assert isinstance(result, tuple) and len(result) == 2
    brief, source = result
    assert brief.name == MISSION_BRIEF_FILENAME
    assert source.name == BRIEF_SOURCE_FILENAME
