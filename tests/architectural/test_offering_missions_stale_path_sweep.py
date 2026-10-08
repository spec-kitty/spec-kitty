"""Architectural test: active doctrine prose must not send readers to the
retired ``src/charter/offering/missions/`` *data* path.

Adversarial-squad finding M1 on PR #3453: WP02 (see
``test_claudemd_template_source.py``) corrected CLAUDE.md/AGENTS.md, but the
same stale ``src/charter/offering/missions/mission-steps/...`` and
``src/charter/offering/missions/<type>/...`` fragments survived in five active
doctrine surfaces under ``packs/**`` and ``src/charter/offering/skills/**`` — an
agent loading a tactic, directive, styleguide, or shipped skill would be
sent to a directory that no longer holds that data (verified: neither
``src/charter/offering/missions/mission-steps/`` nor
``src/charter/offering/missions/software-dev/`` exist on disk). The canonical data
home is ``packs/built-in/missions/`` (see CLAUDE.md's own "Template Source
Location" table).

This is intentionally *not* a blind ``fragment not in content`` check (that
shape lives in ``test_claudemd_has_no_stale_mission_steps_source_path``
above, scoped to CLAUDE.md only). ``src/charter/offering/missions/`` is not wholly
retired: it is still the real, live location of the ``charter.offering.missions``
Python package (``primitives.py``, ``repository.py``, ``models.py``, etc. —
see ``packs/built-in/missions/README.md``'s "Python Utilities" section,
which correctly and currently points there). A blind substring ban would
force that legitimate reference to be deleted or excluded by name. Instead,
every ``src/charter/offering/missions/<remainder>`` occurrence found in scope is
resolved against the real filesystem: if ``src/charter/offering/missions/<remainder>``
exists on disk today, the reference is live and passes; if it does not
(the mission-steps/software-dev/documentation/research/built_in_step_contracts/
mission_types data subtrees, or a ``<type>``/``{mission-key}`` placeholder
pattern describing that retired shape), it is stale and fails.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_OFFERING_MISSIONS_ROOT = _REPO_ROOT / "src" / "charter" / "offering" / "missions"
_STALE_FRAGMENT = "src/charter/offering/missions/"
_SCAN_ROOTS = (
    _REPO_ROOT / "packs",
    _REPO_ROOT / "src" / "charter" / "offering" / "skills",
)
_SCAN_SUFFIXES = {".md", ".yaml", ".yml"}
# Path-token characters that may legitimately follow the stale fragment in
# prose: word chars, path separators, and placeholder markup such as
# <type>/templates/ or {mission-key}/.
_REFERENCE_RE = re.compile(r"src/charter/offering/missions/([\w\-{}<>./*]*)")


def _iter_scan_files() -> Iterator[Path]:
    for root in _SCAN_ROOTS:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix in _SCAN_SUFFIXES:
                yield path


def _resolves_on_disk(remainder: str) -> bool:
    """True if src/charter/offering/missions/<remainder> is a real path today."""
    candidate = (_OFFERING_MISSIONS_ROOT / remainder).resolve()
    try:
        candidate.relative_to(_OFFERING_MISSIONS_ROOT.resolve())
    except ValueError:
        # remainder escaped the directory (e.g. "../"); never legitimate here.
        return False
    return candidate.exists()


def test_no_stale_offering_missions_data_path_in_shipped_prose() -> None:
    """packs/** and src/charter/offering/skills/** must not reference retired
    src/charter/offering/missions/ data paths; the canonical data home is
    packs/built-in/missions/. References that still resolve on disk (the
    surviving charter.offering.missions Python modules) are exempt.
    """
    violations: list[str] = []
    for path in _iter_scan_files():
        content = path.read_text(encoding="utf-8")
        for match in _REFERENCE_RE.finditer(content):
            remainder = match.group(1)
            if _resolves_on_disk(remainder):
                continue
            line_no = content.count("\n", 0, match.start()) + 1
            violations.append(f"{path.relative_to(_REPO_ROOT)}:{line_no}: {_STALE_FRAGMENT}{remainder}")

    assert not violations, (
        "Stale src/charter/offering/missions/ data references found in active doctrine "
        "prose (canonical home is packs/built-in/missions/; see "
        "test_claudemd_template_source.py and CLAUDE.md's Template Source "
        "Location table):\n" + "\n".join(violations)
    )
