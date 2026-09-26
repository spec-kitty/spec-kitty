"""Per-owner exemption loader for the canonical lock-primitive ban gate (FR-010).

Deliberately separate from ``tests.architectural._exemptions`` (the shared
loader for the ``kernel.clock`` dual gate's ``IMPORT:``/``CALL:`` line
shapes) and from ``tests.architectural._os_detection_exemptions`` (the
sibling OS-detection gate's own plural-glob loader): this gate globs ITS OWN
plural file set -- ``tests/architectural/_exemptions/lock-ban-*.txt`` --
inside the SAME shared ``_exemptions/`` directory. The other two gates'
loaders ignore these files (their line shapes/glob patterns do not match),
so all three coexist without interference.

Each file is one line per exempted site, in the content-addressed form
rendered by :func:`tests.architectural._content_identity.render_descriptor_line`::

    <repo-relative path>::<qualname>::<token_substring>[::<occurrence>]

(e.g. ``src/pkg/mod.py::<module>::import fcntl``). The line is a
:class:`~tests.architectural._ratchet_keys.ContentDescriptor`: it resolves to
exactly one finding by enclosing qualname and normalized-token substring, so
it survives line drift, and a stale line fails the gate. The owning file's
name becomes the descriptor's ``rationale``. A ``<path>:<line>`` pin is
refused with a ``ValueError`` naming the file and the line (DIR-041). Blank
lines and ``#``-prefixed comments are ignored. Both files hold zero entries;
this is the only sanctioned shape should a site ever need one.

**Per-WP split (post-tasks squad S-2)**: ``lock-ban-wp04.txt`` /
``lock-ban-wp05.txt`` -- not-yet-routed sites owned by WP04 (migrate stdlib
lock sites) / WP05 (migrate the remaining filelock sites), seeded fail-closed
at WP03 landing with every currently-detected raw-lock import/call outside
``kernel/locks.py``. Each WP shrinks ONLY its own file so the two parallel
migration lanes never collide on a shared allow-list file.
"""

from __future__ import annotations

from pathlib import Path

from tests.architectural._content_identity import parse_descriptor_line
from tests.architectural._ratchet_keys import ContentDescriptor

_EXEMPTIONS_DIR = Path(__file__).resolve().parent / "_exemptions"
_GLOB_PATTERN = "lock-ban-*.txt"


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


def load_lock_ban_exemptions() -> frozenset[ContentDescriptor]:
    """Every content descriptor exempted from the lock-primitive ban (rationale = owning file)."""
    exemptions: set[ContentDescriptor] = set()
    for filename, line in _iter_exemption_entries():
        try:
            exemptions.add(parse_descriptor_line(line, rationale=filename))
        except ValueError as exc:
            raise ValueError(f"{filename}: {exc}") from exc
    return frozenset(exemptions)
