"""Pin the two dated ADR amendments written by mission ci-runtime-stabilisation (#5510, WP19).

Each amendment is sliced from its ``## Amendment (YYYY-MM-DD)`` heading to the next H2 (or
end of file), so a mention elsewhere in the ADR cannot satisfy these checks.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.fast]

REPO_ROOT = Path(__file__).resolve().parents[2]
ADR_DIR = REPO_ROOT / "docs" / "adr" / "3.x"
COVERAGE_HONESTY_ADR = ADR_DIR / "2026-09-26-1-ci-coverage-honesty.md"
REQUIRED_CHECKS_ADR = ADR_DIR / "2026-09-23-1-auto-merge-required-checks-gate.md"

MISSION_CONTRACTS = "kitty-specs/ci-runtime-stabilisation-01M3TZH6/contracts/"
TWO_AUTHORITY_CONTRACT = MISSION_CONTRACTS + "router-two-authority-amendment.md"
GREEN_MATCH_CONTRACT = MISSION_CONTRACTS + "green-match.md"

_AMENDMENT_HEADING = re.compile(r"^## Amendment \(\d{4}-\d{2}-\d{2}\)", re.MULTILINE)
_H2 = re.compile(r"^## ", re.MULTILINE)
_CONTRACT_LINK = re.compile(r"\]\(([^)\s]*kitty-specs/ci-runtime-stabilisation-01M3TZH6/contracts/[^)\s#]+)")


def _amendment_sections(adr: Path) -> list[str]:
    """Return the body of every dated amendment H2 in ``adr``, heading included."""
    text = adr.read_text(encoding="utf-8")
    sections: list[str] = []
    for match in _AMENDMENT_HEADING.finditer(text):
        next_h2 = _H2.search(text, match.end())
        end = next_h2.start() if next_h2 else len(text)
        sections.append(text[match.start() : end])
    return sections


def _amendment_naming(adr: Path, *needles: str) -> str:
    """Return the amendment section that contains every needle, or fail with context."""
    sections = _amendment_sections(adr)
    assert sections, f"{adr.name} has no dated '## Amendment (YYYY-MM-DD)' H2 section"
    for section in sections:
        if all(needle in section for needle in needles):
            return section
    raise AssertionError(f"no dated amendment in {adr.name} contains all of {needles!r}")


def test_coverage_honesty_amendment_names_backstop_and_links_contract() -> None:
    section = _amendment_naming(COVERAGE_HONESTY_ADR, "architectural-backstop", TWO_AUTHORITY_CONTRACT)
    assert "18.6%" in section, "the amendment must cite the 18.6% baseline it corrects"


def test_required_checks_amendment_records_skip_if_green_and_links_contract() -> None:
    section = _amendment_naming(REQUIRED_CHECKS_ADR, "ready_for_review", "tested key", GREEN_MATCH_CONTRACT)
    assert "skip-if-green" in section


@pytest.mark.parametrize("adr", [COVERAGE_HONESTY_ADR, REQUIRED_CHECKS_ADR], ids=lambda p: p.name)
def test_amendment_contract_links_resolve(adr: Path) -> None:
    sections = _amendment_sections(adr)
    assert sections, f"{adr.name} has no dated amendment section"
    links = [link for section in sections for link in _CONTRACT_LINK.findall(section)]
    assert links, f"{adr.name} amendment links no mission contract"
    for link in links:
        target = (adr.parent / link).resolve()
        assert target.is_file(), f"{adr.name}: contract link {link} does not resolve to a file"
