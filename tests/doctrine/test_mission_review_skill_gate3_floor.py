"""Regression pins for the spec-kitty-mission-review skill's Gate 3 floor.

Guards against the retired-sync residue tracked by spec-kitty#4949 / #5003:
the shipped skill named the deleted ``scenarios/saas_sync_enabled.py`` E2E
scenario (removed from ``EXPERIMENTAL-spec-kitty-end-to-end-testing`` by
commit ``e59564b``) as a mandatory Gate 3 floor scenario, and pinned
``SPEC_KITTY_ENABLE_SAAS_SYNC=1`` on gate commands. Confirmed against the live
E2E repo (``gh api .../contents/scenarios``) and this repo's own
``tests/contract/`` surface: the pin has no verified effect on either gate --
Gate 1's ``tests/contract/`` already forces the flag collection-wide via
``tests/conftest.py``, and none of the three surviving E2E scenarios read the
outer shell's value for it (``contract_drift_caught.py`` builds its own fully
sanitized child env and pins the flag to ``0`` there regardless of the outer
command).
"""

from __future__ import annotations

import re

import pytest

from tests.doctrine.conftest import DOCTRINE_SOURCE_ROOT

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

_MISSION_REVIEW_SKILL = DOCTRINE_SOURCE_ROOT / "skills" / "spec-kitty-mission-review" / "SKILL.md"


@pytest.fixture(scope="module")
def skill_text() -> str:
    assert _MISSION_REVIEW_SKILL.is_file(), f"SOURCE skill not found: {_MISSION_REVIEW_SKILL!s}. If the file was moved, update the path in this test."
    return _MISSION_REVIEW_SKILL.read_text(encoding="utf-8")


def test_retired_saas_sync_scenario_is_not_a_gate3_floor(skill_text: str) -> None:
    assert re.search(r"^-\s*`saas_sync_enabled\.py`", skill_text, re.MULTILINE) is None, (
        "Regression: the retired scenarios/saas_sync_enabled.py (deleted from "
        "EXPERIMENTAL-spec-kitty-end-to-end-testing by commit e59564b) must not "
        "be listed as a Gate 3 floor scenario. See spec-kitty#4949."
    )


def test_gate3_floor_lists_exactly_the_three_surviving_scenarios(skill_text: str) -> None:
    for name in (
        "dependent_wp_planning_lane.py",
        "uninitialized_repo_fail_loud.py",
        "contract_drift_caught.py",
    ):
        assert name in skill_text, f"Regression: Gate 3 floor scenario {name} missing from the skill."


def test_gate3_heading_does_not_cite_retired_fr_040(skill_text: str) -> None:
    heading_match = re.search(r"^### Gate 3:.*$", skill_text, re.MULTILINE)
    assert heading_match is not None, "Regression: Gate 3 heading not found in the mission-review skill."
    assert "FR-040" not in heading_match.group(0), (
        "Regression: FR-040 (the retired saas-sync contract) must not be cited in the Gate 3 heading. See spec-kitty#4949."
    )


def _gate_command_surfaces(skill_text: str) -> str:
    """Return only the surfaces where a Gate 1 / Gate 3 flag pin would matter:
    the ```bash fences under the "### Gate 1" and "### Gate 3" headings (the
    commands a reviewer actually runs), and the `- Command:` lines in the
    Gate Results report template. Prose elsewhere in the skill -- e.g. a
    future, legitimate explanation of the flag's still-live #3980 opt-out
    meaning -- is out of scope for this regression guard.
    """
    surfaces: list[str] = []
    for heading_prefix in ("### Gate 1:", "### Gate 3:"):
        heading_idx = skill_text.index(heading_prefix)
        fence_start = skill_text.index("```bash", heading_idx)
        fence_end = skill_text.index("```", fence_start + len("```bash"))
        surfaces.append(skill_text[fence_start:fence_end])
    surfaces.extend(re.findall(r"^- Command:.*$", skill_text, re.MULTILINE))
    return "\n".join(surfaces)


def test_gate_commands_do_not_pin_retired_saas_sync_flag(skill_text: str) -> None:
    surfaces = _gate_command_surfaces(skill_text)
    assert re.search(r"SPEC_KITTY_ENABLE_SAAS_SYNC\s*=\s*[01]\b", surfaces) is None, (
        "Regression: the mission-review skill must not pin SPEC_KITTY_ENABLE_SAAS_SYNC on "
        "gate commands (the Gate 1 / Gate 3 ```bash fences or the Gate Results `- Command:` "
        "lines) -- the pin has no verified effect on Gate 1 (tests/contract/ already forces "
        "the flag via tests/conftest.py) or Gate 3 (none of the surviving E2E scenarios read "
        "the outer shell's value). See spec-kitty#5003."
    )
