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

Each file is one line per violation: ``<repo-relative path>:<line>``. Blank
lines and ``#``-prefixed comments are ignored.

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

_EXEMPTIONS_DIR = Path(__file__).resolve().parent / "_exemptions"
_GLOB_PATTERN = "os-detect-ban-*.txt"


def _iter_exemption_lines() -> list[str]:
    lines: list[str] = []
    for path in sorted(_EXEMPTIONS_DIR.glob(_GLOB_PATTERN)):
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            lines.append(stripped)
    return lines


def load_os_detection_exemptions() -> frozenset[tuple[str, int]]:
    """Every ``(repo-relative path, line)`` pair exempted from the OS-detection ban."""
    exemptions: set[tuple[str, int]] = set()
    for line in _iter_exemption_lines():
        path_part, _, lineno_part = line.rpartition(":")
        if not path_part:
            continue
        exemptions.add((path_part, int(lineno_part)))
    return frozenset(exemptions)
