"""Regression pins for the canonical standalone ``spec-kitty`` skill."""

from __future__ import annotations

import re

import pytest

from tests.charter_offering.conftest import OFFERING_SOURCE_ROOT

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

_SPEC_KITTY_SKILL = OFFERING_SOURCE_ROOT / "skills" / "spec-kitty" / "SKILL.md"


@pytest.fixture(scope="module")
def skill_text() -> str:
    assert _SPEC_KITTY_SKILL.is_file(), f"SOURCE skill not found: {_SPEC_KITTY_SKILL!s}. If the file was moved, update the path in this test."
    return _SPEC_KITTY_SKILL.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# FR-006 pin: dispatch must be present as the canonical command
# ---------------------------------------------------------------------------


def test_dispatch_is_documented_as_canonical_command(skill_text: str) -> None:
    assert "spec-kitty dispatch" in skill_text, "Regression: 'spec-kitty dispatch' was removed from src/charter/offering/skills/spec-kitty/SKILL.md."


def test_frontmatter_names_spec_kitty(skill_text: str) -> None:
    assert "name: spec-kitty\n" in skill_text


def test_dispatch_op_lifecycle_is_documented(skill_text: str) -> None:
    assert "governance_context_text" in skill_text
    assert "profile-invocation complete" in skill_text
    assert "kitty-ops/<invocation_id>.jsonl" in skill_text


def test_removed_standalone_commands_are_not_taught(skill_text: str) -> None:
    removed = ("do", "ask", "advise")
    for command in removed:
        assert re.search(rf"spec-kitty {command}(\s|$|\"|`)", skill_text) is None
