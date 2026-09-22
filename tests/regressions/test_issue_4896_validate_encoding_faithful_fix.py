"""Regression test for #4896: `validate-encoding --fix` must repair faithfully.

Before the fix, ``text_sanitization.py::sanitize_file`` (driven by
``spec-kitty validate-encoding --mission <slug> --fix``) corrupted files while
still reporting success:

- a single stray non-UTF-8 byte anywhere in a file triggered a *whole-file*
  cp1252/latin-1 re-decode, mojibaking every already-valid multi-byte UTF-8
  character in that file;
- files were scoped purely by the ``.md`` extension, so a binary file
  (e.g. a PNG) merely named ``*.md`` was decoded and rewritten;
- files were read in universal-newline text mode and written back with
  ``newline=""``, silently converting CRLF line endings to LF file-wide;
- a forced rewrite happened whenever a decode fallback was used, even when
  the "repair" was not faithful.

This test exercises the real CLI (``spec-kitty validate-encoding --fix``)
over a fixture mission directory covering all three corruption modes plus
two untouched controls, and pins the faithful-repair contract (FR-006 to
FR-008 / T016-T019).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from specify_cli.text_sanitization import sanitize_file
from tests.test_isolation_helpers import get_venv_python

pytestmark = [pytest.mark.regression, pytest.mark.git_repo]

MISSION_SLUG = "001-issue-4896"

# A minimal, deterministic "binary" payload: a real PNG signature followed by
# non-text bytes (including NUL bytes), named with a ``.md`` extension to
# reproduce the extension-only scoping bug.
PNG_BYTES = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]) + bytes(range(0, 60))

# "Valid: café\n" (proper UTF-8 for é = 0xC3 0xA9) followed by a line where
# the same character was mistakenly written as a lone cp1252/latin-1 byte
# (0xE9) instead of being UTF-8 encoded. Only the *second* café's é is
# invalid UTF-8 -- the first is already correct and must survive untouched.
MIXED_BEFORE = b"Valid: caf\xc3\xa9\nBroken: caf\xe9 shop\n"

# CRLF line endings with one Windows-1252-style smart quote (already valid
# UTF-8: ’ encodes as 0xE2 0x80 0x99) that sanitize_markdown_text should
# normalize to a straight apostrophe.
CRLF_BEFORE = b"Line one\r\nUser\xe2\x80\x99s line two\r\n"
CRLF_CLEAN = b"Line one\r\nLine two\r\n"
CLEAN = b"Plain ASCII content with no issues.\n"

# A byte cp1252 itself cannot decode (0x81 is undefined in cp1252), so a
# faithful repair is impossible and the file must be refused, not corrupted.
IRREPARABLE = b"Before \x81 after\n"


def _run_validate_encoding(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    command = [str(get_venv_python()), "-m", "specify_cli.__init__", "validate-encoding", *args]
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )


def _init_fixture_mission(tmp_path: Path) -> Path:
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)
    (tmp_path / ".kittify").mkdir()
    feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG
    feature_dir.mkdir(parents=True)
    return feature_dir


class TestIssue4896FaithfulFix:
    """CLI-level regression: --fix must not corrupt while reporting success."""

    def test_fix_repairs_faithfully_without_corruption(self, tmp_path: Path) -> None:
        feature_dir = _init_fixture_mission(tmp_path)

        mixed = feature_dir / "mixed.md"
        mixed.write_bytes(MIXED_BEFORE)

        binary = feature_dir / "binary.md"
        binary.write_bytes(PNG_BYTES)

        crlf = feature_dir / "crlf.md"
        crlf.write_bytes(CRLF_BEFORE)

        crlf_clean = feature_dir / "crlf-clean.md"
        crlf_clean.write_bytes(CRLF_CLEAN)

        clean = feature_dir / "clean.md"
        clean.write_bytes(CLEAN)

        result = _run_validate_encoding("--mission", MISSION_SLUG, "--fix", "--no-backup", cwd=tmp_path)

        assert result.returncode == 0, f"--fix should exit 0: stdout={result.stdout!r} stderr={result.stderr!r}"

        # --- mixed.md: stray byte repaired; already-valid UTF-8 untouched ---
        mixed_after = mixed.read_bytes().decode("utf-8")
        assert "CafÃ" not in mixed_after, f"whole-file cp1252 mojibake corrupted valid UTF-8: {mixed_after!r}"
        assert mixed_after.count("café") == 2, f"expected both occurrences of 'café' intact/repaired, got: {mixed_after!r}"

        # --- binary.md: skipped, byte-for-byte unchanged ---
        assert binary.read_bytes() == PNG_BYTES, "binary file named *.md must not be rewritten"

        # --- crlf.md: smart quote normalized, CRLF preserved everywhere ---
        crlf_after = crlf.read_bytes()
        assert crlf_after.count(b"\r\n") == CRLF_BEFORE.count(b"\r\n"), f"CRLF line endings must be preserved, got: {crlf_after!r}"
        assert b"\xe2\x80\x99" not in crlf_after, "smart quote should have been normalized"
        assert b"User's line two" in crlf_after

        # A raw \n not preceded by \r would indicate LF-normalization happened.
        bare_lf_count = crlf_after.count(b"\n") - crlf_after.count(b"\r\n")
        assert bare_lf_count == 0, f"unexpected LF-only line ending introduced: {crlf_after!r}"

        # --- controls: byte-identical, never touched ---
        assert crlf_clean.read_bytes() == CRLF_CLEAN, "clean CRLF control must be byte-identical"
        assert clean.read_bytes() == CLEAN, "clean ASCII control must be byte-identical"

        # Controls must never have been reported as "Fixed" -- verify directly
        # against the sanitizer, independent of CLI table rendering.
        modified_crlf_clean, err_crlf_clean = sanitize_file(crlf_clean, backup=False, dry_run=True)
        assert modified_crlf_clean is False and err_crlf_clean is None
        modified_clean, err_clean = sanitize_file(clean, backup=False, dry_run=True)
        assert modified_clean is False and err_clean is None
        modified_binary, err_binary = sanitize_file(binary, backup=False, dry_run=True)
        assert modified_binary is False, "binary file must never be reported as needing a fix"


class TestIssue4896SanitizeFileUnitContract:
    """Direct sanitize_file() checks pinning the faithful-repair contract."""

    def test_binary_named_md_is_skipped_by_content_sniff(self, tmp_path: Path) -> None:
        binary = tmp_path / "binary.md"
        binary.write_bytes(PNG_BYTES)

        modified, error = sanitize_file(binary, backup=False, dry_run=False)

        assert modified is False
        assert error is None
        assert binary.read_bytes() == PNG_BYTES

    def test_stray_byte_is_repaired_without_whole_file_transcode(self, tmp_path: Path) -> None:
        mixed = tmp_path / "mixed.md"
        mixed.write_bytes(MIXED_BEFORE)

        modified, error = sanitize_file(mixed, backup=False, dry_run=False)

        assert modified is True
        assert error is None
        after = mixed.read_text(encoding="utf-8")
        assert "CafÃ" not in after
        assert after.count("café") == 2

    def test_crlf_preserved_through_repair(self, tmp_path: Path) -> None:
        crlf = tmp_path / "crlf.md"
        crlf.write_bytes(CRLF_BEFORE)

        modified, error = sanitize_file(crlf, backup=False, dry_run=False)

        assert modified is True
        assert error is None
        after = crlf.read_bytes()
        assert after.count(b"\r\n") == CRLF_BEFORE.count(b"\r\n")

    def test_clean_control_reports_no_modification(self, tmp_path: Path) -> None:
        clean = tmp_path / "clean.md"
        clean.write_bytes(CLEAN)

        modified, error = sanitize_file(clean, backup=False, dry_run=False)

        assert modified is False
        assert error is None
        assert clean.read_bytes() == CLEAN

    def test_irreparable_byte_is_refused_with_offset_not_corrupted(self, tmp_path: Path) -> None:
        irreparable = tmp_path / "irreparable.md"
        irreparable.write_bytes(IRREPARABLE)

        modified, error = sanitize_file(irreparable, backup=False, dry_run=False)

        assert modified is False, "a file that cannot be faithfully repaired must not be 'Fixed'"
        assert error is not None
        # "Before " is 7 bytes, so the offending 0x81 sits at offset 7.
        assert "7" in error, f"error should report the offending byte offset, got: {error!r}"
        # File on disk must be untouched -- refusal must not corrupt it.
        assert irreparable.read_bytes() == IRREPARABLE
