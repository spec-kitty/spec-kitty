"""Guard: documentation doctrine names only iteration modes the code accepts (#5205).

A terminology sweep once renamed the machine value in doctrine
(``mission-specific``) but not in code (``feature_specific``), so agents
following doctrine wrote a value ``doc_state`` rejects. Every iteration-mode
token named on an iteration-mode line in the shipped documentation doctrine
must be a canonical ``doc_state`` token, spelled exactly as the code spells it.
"""

from __future__ import annotations

import re

import pytest

from specify_cli.doc_analysis.doc_state import ITERATION_MODES
from tests.charter_offering.conftest import REPO_ROOT

pytestmark = [pytest.mark.doctrine, pytest.mark.fast]

_DOCUMENTATION_DOCTRINE_ROOTS = (
    REPO_ROOT / "packs" / "built-in" / "missions" / "documentation",
    REPO_ROOT / "packs" / "built-in" / "missions" / "mission-steps" / "documentation",
)
_ITERATION_MODE_LINE = re.compile(r"iteration[ _]mode", re.IGNORECASE)
# Every spelling a mode token has ever had, canonical or not.
_MODE_TOKEN = re.compile(r"(?<![\w-])(initial|gap[_-]filling|(?:mission|feature)[_-]specific)(?![\w-])")


def _named_modes() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for root in _DOCUMENTATION_DOCTRINE_ROOTS:
        for path in sorted(root.rglob("*")):
            if path.suffix not in {".md", ".yaml", ".yml"} or not path.is_file():
                continue
            lines = path.read_text(encoding="utf-8").splitlines()
            for index, line in enumerate(lines):
                if not _ITERATION_MODE_LINE.search(line):
                    continue
                # A mode list may wrap onto the next line of the same sentence.
                window = " ".join(lines[index : index + 2])
                for match in _MODE_TOKEN.finditer(window):
                    found.append((f"{path.relative_to(REPO_ROOT).as_posix()}:{index + 1}", match.group(1)))
    return found


def test_documentation_doctrine_names_iteration_modes() -> None:
    """Non-vacuity: the scan finds the mode lists it is meant to police."""
    tokens = {token for _, token in _named_modes()}
    assert {"initial", "gap_filling", "mission_specific"} <= tokens


def test_documentation_doctrine_iteration_modes_are_accepted_by_doc_state() -> None:
    violations = [f"{where}: {token}" for where, token in _named_modes() if token not in ITERATION_MODES]
    assert violations == [], "Doctrine names iteration modes doc_state does not accept:\n" + "\n".join(violations)
