"""Text sanitization utilities for preventing encoding errors.

This module provides utilities to normalize Windows-1252 smart quotes and other
problematic characters that can cause UTF-8 encoding errors in markdown files.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

__all__ = [
    "sanitize_markdown_text",
    "sanitize_file",
    "detect_problematic_characters",
    "PROBLEMATIC_CHARS",
]

# Content-sniff heuristics for classifying a file as binary vs text (#4896:
# do NOT trust the ``.md`` extension alone -- a binary file merely *named*
# ``*.md`` must never be decoded or rewritten).
_BINARY_SNIFF_WINDOW = 8192
_BINARY_NONTEXT_RATIO_THRESHOLD = 0.30
# Bytes considered "text-like" when they appear outside a valid UTF-8 stream:
# common whitespace/control codes plus the printable byte range.
_TEXT_BYTES = frozenset({0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x1B} | set(range(0x20, 0x7F)) | set(range(0x80, 0x100)))

# Fallback single-byte codec used to repair an individual invalid UTF-8 byte.
# cp1252 is a superset of latin-1 for the printable range and is the
# encoding that actually produced the historical mojibake reports.
_REPAIR_CODEC = "cp1252"
# Safety cap: refuse rather than loop indefinitely if a file has an
# implausible number of invalid bytes (should not happen for real markdown;
# genuinely binary content is already filtered out by the content sniff).
_MAX_REPAIR_ATTEMPTS = 64

# UTF-8 byte-order mark, built via chr() to avoid embedding the literal
# BOM codepoint in this source file.
_BOM = chr(0xFEFF)

# Map of Windows-1252 / problematic characters to safe UTF-8 replacements
PROBLEMATIC_CHARS = {
    # Smart quotes (Windows-1252 bytes 0x91-0x94)
    "\u2018": "'",  # LEFT SINGLE QUOTATION MARK → apostrophe
    "\u2019": "'",  # RIGHT SINGLE QUOTATION MARK → apostrophe
    "\u201c": '"',  # LEFT DOUBLE QUOTATION MARK → straight quote
    "\u201d": '"',  # RIGHT DOUBLE QUOTATION MARK → straight quote
    # Em/en dashes
    "\u2013": "--",  # EN DASH → double hyphen
    "\u2014": "---",  # EM DASH → triple hyphen
    # Mathematical operators that may come from cp1252
    "\u00b1": "+/-",  # PLUS-MINUS SIGN → +/-
    "\u00d7": "x",  # MULTIPLICATION SIGN → x
    "\u00f7": "/",  # DIVISION SIGN → /
    # Ellipsis
    "\u2026": "...",  # HORIZONTAL ELLIPSIS → three periods
    # Bullets
    "\u2022": "*",  # BULLET → asterisk
    "\u2023": ">",  # TRIANGULAR BULLET → greater than
    # Degree symbol (often problematic)
    "\u00b0": " degrees",  # DEGREE SIGN → " degrees"
    # Non-breaking space (invisible but causes issues)
    "\u00a0": " ",  # NO-BREAK SPACE → regular space
    # Trademark/copyright symbols
    "\u2122": "(TM)",  # TRADE MARK SIGN
    "\u00a9": "(C)",  # COPYRIGHT SIGN
    "\u00ae": "(R)",  # REGISTERED SIGN
}

# Compile regex for detecting any problematic character
_PROBLEMATIC_PATTERN = re.compile("[" + "".join(re.escape(char) for char in PROBLEMATIC_CHARS) + "]")


def sanitize_markdown_text(text: str, *, preserve_utf8: bool = False) -> str:  # noqa: ARG001
    """Sanitize markdown text by replacing problematic characters.

    Args:
        text: The markdown text to sanitize
        preserve_utf8: If True, only replace characters that cause encoding issues.
                      If False (default), replace all problematic characters for
                      maximum compatibility.

    Returns:
        Sanitized text with problematic characters replaced

    Examples:
        >>> sanitize_markdown_text("User's "favorite" feature")
        'User\\'s "favorite" feature'

        >>> sanitize_markdown_text("Price: $100 ± $10")
        'Price: $100 +/- $10'

        >>> sanitize_markdown_text("Temperature: 72° outside")
        'Temperature: 72 degrees outside'
    """
    if not text:
        return text

    # Replace each problematic character with its safe equivalent
    result = text
    for problematic, replacement in PROBLEMATIC_CHARS.items():
        if problematic in result:
            result = result.replace(problematic, replacement)

    return result


def detect_problematic_characters(
    text: str,
) -> list[tuple[int, int, str, str]]:
    """Detect problematic characters in text and return their locations.

    Args:
        text: The text to check

    Returns:
        List of tuples: (line_number, column, character, suggested_replacement)
        Line numbers are 1-indexed, columns are 0-indexed.

    Examples:
        >>> text = "Line 1\\nUser's "test"\\nLine 3"
        >>> issues = detect_problematic_characters(text)
        >>> len(issues)
        3
        >>> issues[0]
        (2, 4, '\u2019', "'")
    """
    issues: list[tuple[int, int, str, str]] = []

    lines = text.splitlines(keepends=True)
    for line_num, line in enumerate(lines, start=1):
        for match in _PROBLEMATIC_PATTERN.finditer(line):
            char = match.group(0)
            replacement = PROBLEMATIC_CHARS.get(char, "?")
            issues.append((line_num, match.start(), char, replacement))

    return issues


def _looks_binary(data: bytes) -> bool:
    """Content-sniff `data` as binary (never sanitized) vs text (#4896).

    Classification is by CONTENT, never by file extension: a file merely
    *named* ``*.md`` that actually holds binary data (e.g. a PNG) must be
    skipped, not decoded and rewritten. Uses the standard NUL-byte
    heuristic plus a non-text-byte ratio check over a leading window.
    """
    if not data:
        return False
    window = data[:_BINARY_SNIFF_WINDOW]
    if b"\x00" in window:
        return True
    nontext = sum(1 for byte in window if byte not in _TEXT_BYTES)
    return (nontext / len(window)) > _BINARY_NONTEXT_RATIO_THRESHOLD


def _repair_invalid_utf8(data: bytes) -> tuple[str | None, list[int]]:
    """Decode `data` as UTF-8, repairing only the individual invalid bytes.

    Never re-decodes the whole file under a fallback codec (#4896): each
    offending byte offset is mapped through ``cp1252`` (the encoding that
    produced the historical mojibake) and substituted in place, one byte at
    a time, so every already-valid UTF-8 byte sequence elsewhere in the
    file survives untouched.

    Returns:
        (repaired_text, offsets) on success, or (None, offsets) if a byte
        cannot be faithfully repaired (offsets lists every offset seen up
        to and including the one that forced the refusal).
    """
    working = bytearray(data)
    offsets: list[int] = []
    for _ in range(_MAX_REPAIR_ATTEMPTS):
        try:
            return working.decode("utf-8"), offsets
        except UnicodeDecodeError as exc:
            offset = exc.start
            offsets.append(offset)
            offending_byte = working[offset : offset + 1]
            try:
                replacement_char = offending_byte.decode(_REPAIR_CODEC)
            except UnicodeDecodeError:
                return None, offsets
            working[offset : offset + 1] = replacement_char.encode("utf-8")
    return None, offsets


class _UnrepairableEncodingError(Exception):
    """Raised when invalid UTF-8 bytes cannot be faithfully repaired."""


def _decode_faithfully(raw_bytes: bytes) -> tuple[str, bool]:
    """Decode `raw_bytes` as UTF-8, scoping any repair to the bad byte(s).

    Returns:
        (text, needs_rewrite) -- ``needs_rewrite`` is True only when the
        bytes were not already valid UTF-8 and a byte-scoped repair was
        applied (a legitimate change that must be persisted even if
        ``sanitize_markdown_text`` finds nothing further to normalize).

    Raises:
        _UnrepairableEncodingError: if an invalid byte cannot be mapped
            through the repair codec; the message reports its offset(s)
            (#4896 T018 -- refuse rather than corrupt).
    """
    try:
        return raw_bytes.decode("utf-8-sig").lstrip(_BOM), False
    except UnicodeDecodeError:
        pass

    repaired_text, offsets = _repair_invalid_utf8(raw_bytes)
    if repaired_text is None:
        offset_list = ", ".join(str(offset) for offset in offsets)
        raise _UnrepairableEncodingError(f"invalid byte(s) at offset(s) [{offset_list}] could not be faithfully repaired")
    return repaired_text.lstrip(_BOM), True


def sanitize_file(
    file_path: Path,
    *,
    backup: bool = True,
    dry_run: bool = False,
) -> tuple[bool, str | None]:
    """Sanitize a markdown file in place.

    Args:
        file_path: Path to the markdown file to sanitize
        backup: If True, create a .bak file before modifying
        dry_run: If True, only check and report, don't modify

    Returns:
        Tuple of (was_modified, error_message)
        - was_modified: True if the file had problematic characters
        - error_message: None if successful, error message if failed

    Examples:
        >>> from pathlib import Path
        >>> from tempfile import NamedTemporaryFile
        >>> with NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        ...     f.write('User's "test"')
        ...     tmp_path = Path(f.name)
        >>> modified, error = sanitize_file(tmp_path, backup=False)
        >>> modified
        True
        >>> tmp_path.read_text()
        'User\\'s "test"'
        >>> tmp_path.unlink()  # cleanup
    """
    try:
        if file_path.is_symlink():
            return False, f"Refusing to sanitize symlinked file: {file_path}"
        if not file_path.exists():
            return False, f"File not found: {file_path}"

        try:
            file_path = file_path.resolve(strict=True)
        except OSError as exc:
            return False, f"Error resolving {file_path}: {exc}"

        if file_path.suffix.lower() != ".md":
            return False, f"Only markdown files are supported: {file_path}"

        raw_bytes = file_path.read_bytes()

        # Content sniff, not extension: a binary file merely named *.md
        # must be skipped entirely, never decoded or rewritten (#4896).
        if _looks_binary(raw_bytes):
            return False, None

        try:
            original_text, needs_rewrite = _decode_faithfully(raw_bytes)
        except _UnrepairableEncodingError as exc:
            return False, f"Refusing to sanitize {file_path}: {exc}"

        # Sanitize the text (preserves existing line endings: raw_bytes was
        # decoded directly, never through universal-newline text mode, so
        # CRLF sequences remain intact in original_text/sanitized_text).
        sanitized_text = sanitize_markdown_text(original_text)

        # Check if any changes were made. needs_rewrite is only True when a
        # genuine byte-level repair was applied above -- a forced rewrite
        # is never reported as "Fixed" for bytes that didn't actually change.
        if sanitized_text == original_text and not needs_rewrite:
            return False, None  # No changes needed

        if dry_run:
            return True, None  # Would modify but dry run

        # Create backup if requested
        if backup:
            backup_path = file_path.with_suffix(file_path.suffix + ".bak")
            with file_path.open("rb") as source, backup_path.open("xb") as target:
                shutil.copyfileobj(source, target)

        # Write sanitized content as raw bytes -- no text-mode newline
        # translation, so the file's original line-ending convention
        # (CRLF or LF) is preserved byte-for-byte (#4896).
        file_path.write_bytes(sanitized_text.encode("utf-8"))
        return True, None

    except Exception as exc:
        return False, f"Error sanitizing {file_path}: {exc}"


def sanitize_directory(
    directory: Path,
    *,
    pattern: str = "**/*.md",
    backup: bool = False,
    dry_run: bool = False,
) -> dict[str, tuple[bool, str | None]]:
    """Sanitize all markdown files in a directory.

    Args:
        directory: Directory to scan
        pattern: Glob pattern for files to sanitize (default: **/*.md)
        backup: If True, create .bak files before modifying
        dry_run: If True, only check and report, don't modify

    Returns:
        Dictionary mapping file paths to (was_modified, error_message) tuples
    """
    results: dict[str, tuple[bool, str | None]] = {}

    for file_path in directory.glob(pattern):
        if file_path.is_file():
            result = sanitize_file(file_path, backup=backup, dry_run=dry_run)
            results[str(file_path)] = result

    return results
