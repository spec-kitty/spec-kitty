"""Per-owner exemption loader for the canonical lock-primitive ban gate (FR-010).

Deliberately separate from ``tests.architectural._exemptions`` (the shared
loader for the ``kernel.clock`` dual gate's ``IMPORT:``/``CALL:`` line
shapes) and from ``tests.architectural._os_detection_exemptions`` (the
sibling OS-detection gate's own plural-glob loader): this gate globs ITS OWN
plural file set -- ``tests/architectural/_exemptions/lock-ban-*.txt`` --
inside the SAME shared ``_exemptions/`` directory. The other two gates'
loaders ignore these files (their line shapes/glob patterns do not match),
so all three coexist without interference.

Each file is one line per violation: ``<repo-relative path>:<line>``. Blank
lines and ``#``-prefixed comments are ignored.

**Per-WP split (post-tasks squad S-2)**: ``lock-ban-wp04.txt`` /
``lock-ban-wp05.txt`` -- not-yet-routed sites owned by WP04 (migrate stdlib
lock sites) / WP05 (migrate the remaining filelock sites), seeded fail-closed
at WP03 landing with every currently-detected raw-lock import/call outside
``kernel/locks.py``. Each WP shrinks ONLY its own file so the two parallel
migration lanes never collide on a shared allow-list file.
"""

from __future__ import annotations

from pathlib import Path

_EXEMPTIONS_DIR = Path(__file__).resolve().parent / "_exemptions"
_GLOB_PATTERN = "lock-ban-*.txt"


def _iter_exemption_lines() -> list[str]:
    lines: list[str] = []
    for path in sorted(_EXEMPTIONS_DIR.glob(_GLOB_PATTERN)):
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            lines.append(stripped)
    return lines


def load_lock_ban_exemptions() -> frozenset[tuple[str, int]]:
    """Every ``(repo-relative path, line)`` pair exempted from the lock-primitive ban."""
    exemptions: set[tuple[str, int]] = set()
    for line in _iter_exemption_lines():
        path_part, _, lineno_part = line.rpartition(":")
        if not path_part:
            continue
        exemptions.add((path_part, int(lineno_part)))
    return frozenset(exemptions)
