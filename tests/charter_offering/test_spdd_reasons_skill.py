"""Discovery tests for the spk-charter-spdd-reasons skill (WP03; renamed by #3732).

Validates that the SKILL.md file exists, parses, declares the right name,
embeds all five FR-010 trigger phrases, lists every canonical canvas
section, and warns about the three "Does NOT" rules.
"""

from __future__ import annotations

import re

import pytest
import yaml

from tests.charter_offering.conftest import OFFERING_SOURCE_ROOT

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

SKILL_PATH = (
    OFFERING_SOURCE_ROOT / "skills" / "spk-charter-spdd-reasons" / "SKILL.md"
)

FR_010_TRIGGERS = [
    "use SPDD",
    "use REASONS",
    "generate a REASONS canvas",
    "apply structured prompt driven development",
    "make this mission SPDD",
]

CANVAS_SECTIONS = [
    "Requirements",
    "Entities",
    "Approach",
    "Structure",
    "Operations",
    "Norms",
    "Safeguards",
]


def _split_frontmatter(text: str) -> tuple[dict, str]:
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    assert match, "SKILL.md must open with a YAML frontmatter block"
    fm = yaml.safe_load(match.group(1))
    assert isinstance(fm, dict), "frontmatter must parse as a mapping"
    return fm, match.group(2)


def test_skill_file_exists() -> None:
    assert SKILL_PATH.is_file(), f"missing skill file: {SKILL_PATH}"


def test_skill_frontmatter_name_and_triggers() -> None:
    fm, _ = _split_frontmatter(SKILL_PATH.read_text(encoding="utf-8"))
    assert fm.get("name") == "spk-charter-spdd-reasons"
    description = fm.get("description") or ""
    missing = [t for t in FR_010_TRIGGERS if t not in description]
    assert not missing, f"description missing FR-010 triggers: {missing}"


def test_skill_body_lists_seven_canvas_sections() -> None:
    _, body = _split_frontmatter(SKILL_PATH.read_text(encoding="utf-8"))
    missing = [s for s in CANVAS_SECTIONS if s not in body]
    assert not missing, f"body missing canvas sections: {missing}"


def test_skill_body_warns_about_three_does_not_rules() -> None:
    body = SKILL_PATH.read_text(encoding="utf-8").lower()
    # 1. No full system mirror.
    assert "mirror" in body, "must warn against mirroring code as prose"
    # 2. No overwrite of user-authored content.
    assert "overwrite" in body, "must warn against overwriting user content"
    # 3. No silent enforcement on non-opted-in projects.
    assert "silently enforce" in body or "silent" in body, (
        "must warn against silent enforcement when charter has not opted in"
    )
