"""Per-owner exemption loader for the OS-detection ban gate (FR-012).

Deliberately separate from ``tests.architectural._exemptions`` (the shared
loader for the ``kernel.clock`` dual gate's ``IMPORT:``/``CALL:`` line
shapes): this gate has a single violation shape (one banned idiom hit, at
call-site granularity), so it globs its OWN plural file set --
``tests/architectural/_exemptions/os-detect-ban-*.txt`` -- inside the SAME
shared ``_exemptions/`` directory, rather than repurposing the clock gate's
prefix vocabulary. The clock gate's own loader ignores these files (no line
in them starts with ``IMPORT:``/``CALL:``), so the two coexist without
interference.

Each file is one line per exempted site, in the content-addressed form
rendered by :func:`tests.architectural._content_identity.render_descriptor_line`::

    <repo-relative path>::<qualname>::<token_substring>[::<occurrence>]

(e.g. ``src/kernel/locks.py::_os_lock::if sys . platform ==``). The line is a
:class:`~tests.architectural._ratchet_keys.ContentDescriptor`: it resolves to
exactly one finding by enclosing qualname and normalized-token substring, so
it survives line drift, and a stale line fails the gate (FR-007). The owning
file's name becomes the descriptor's ``rationale``, so per-owner semantics
survive the union. A ``<path>:<line>`` pin is refused with a ``ValueError``
naming the file and the line (DIR-041). Blank lines and ``#``-prefixed
comments are ignored.

Four files exist at WP01 landing time (contracts/safe-delete-and-os-seam.md
Sec C):

- ``os-detect-ban-sanctioned-raw.txt`` -- the documented, PERMANENT
  Windows-only C-module import guards (``if <win-check>: import
  msvcrt/fcntl``). This file is not expected to reach zero (terminal state
  per the contract: "OS allowlist: import-guards only").
- ``os-detect-ban-wp03.txt`` / ``os-detect-ban-wp04.txt`` -- not-yet-routed
  sites owned by WP03 (kernel lock primitive) / WP04 (migrate stdlib lock
  sites), seeded fail-closed with every site their own WP task file names.
  Each WP shrinks only its own file, so parallel lanes never collide on a
  shared allow-list file (post-tasks squad S-2).
- ``os-detect-ban-deferred.txt`` -- sites deferred outside this mission's
  scope entirely: ``specify_cli/__init__.py`` (NG-01, argv-work/version-bump
  coupling) and ``paths/windows_paths.py`` (a census gap discovered during
  WP01 landing -- no WP in this mission claims it; flagged for a follow-up
  ticket rather than silently routed or silently left un-gated).
"""

from __future__ import annotations

from pathlib import Path

from tests.architectural._content_identity import parse_descriptor_line
from tests.architectural._ratchet_keys import ContentDescriptor

_EXEMPTIONS_DIR = Path(__file__).resolve().parent / "_exemptions"
_GLOB_PATTERN = "os-detect-ban-*.txt"


def _iter_exemption_entries() -> list[tuple[str, str]]:
    """``(owning file name, entry line)`` for every non-blank, non-comment line."""
    entries: list[tuple[str, str]] = []
    for path in sorted(_EXEMPTIONS_DIR.glob(_GLOB_PATTERN)):
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            entries.append((path.name, stripped))
    return entries


def load_os_detection_exemptions() -> frozenset[ContentDescriptor]:
    """Every content descriptor exempted from the OS-detection ban (rationale = owning file)."""
    exemptions: set[ContentDescriptor] = set()
    for filename, line in _iter_exemption_entries():
        try:
            exemptions.add(parse_descriptor_line(line, rationale=filename))
        except ValueError as exc:
            raise ValueError(f"{filename}: {exc}") from exc
    return frozenset(exemptions)
