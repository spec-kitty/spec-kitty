"""FR-018: language-independent built-in tactics carry no language scope.

Doctrine and especially tactics are language independent. Three shipped
tactics were wrongly scoped to a fixed language list, so they silently
disappeared for projects in any other language. They must be unscoped and
must not embed Spec Kitty repo-internal references. (Other shipped tactics'
in-house residue is tracked by the provenance ratchet, not this WP.)
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from charter.offering.tactics.repository import TacticRepository

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

REPO_ROOT = Path(__file__).resolve().parents[2]
TACTICS_DIR = REPO_ROOT / "packs" / "built-in" / "tactics"

UNSCOPED_TACTIC_IDS = (
    "secure-regex-catastrophic-backtracking",
    "chain-of-responsibility-rule-pipeline",
    "dependency-hygiene",
)
IN_HOUSE_MARKERS = (
    re.compile(r"src/specify_cli/"),
    re.compile(r"tests/regressions/"),
    re.compile(r"\bpython:S\d+"),
)


@pytest.fixture(scope="module")
def all_tactics() -> TacticRepository:
    return TacticRepository()


@pytest.mark.parametrize("tactic_id", UNSCOPED_TACTIC_IDS)
def test_tactic_declares_no_language_scope(all_tactics: TacticRepository, tactic_id: str) -> None:
    tactic = all_tactics.get(tactic_id)
    assert tactic is not None
    assert not tactic.applies_to_languages


@pytest.mark.parametrize("tactic_id", UNSCOPED_TACTIC_IDS)
@pytest.mark.parametrize("languages", [["python"], ["zig"], ["unknown"]])
def test_tactic_resolves_for_any_active_language(tactic_id: str, languages: list[str]) -> None:
    repo = TacticRepository(active_languages=languages)
    assert repo.get(tactic_id) is not None


def test_unscoped_tactics_embed_no_in_house_references() -> None:
    offenders: list[str] = []
    paths = sorted(p for tid in UNSCOPED_TACTIC_IDS for p in TACTICS_DIR.rglob(f"{tid}.tactic.yaml"))
    # Non-vacuity floor: all three tactic files must be found, or the scan below proves nothing.
    assert len(paths) == len(UNSCOPED_TACTIC_IDS) == 3, paths
    for path in paths:
        text = path.read_text(encoding="utf-8")
        offenders.extend(f"{path.relative_to(REPO_ROOT)} matches {marker.pattern}" for marker in IN_HOUSE_MARKERS if marker.search(text))
    assert offenders == []
