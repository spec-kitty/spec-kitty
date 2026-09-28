"""Guidelines single-owner tests.

``mission-steps/<type>/<action>/guidelines.md`` is the single owner of action
guidelines; the ``packs/built-in/missions/<type>/actions/<action>/guidelines.md``
copies (the loader's old, undocumented target) do not exist. This module pins
four invariants:

(a) No ``packs/built-in/missions/*/actions/*/guidelines.md`` file exists.
(b) For every mission type/action with a ``mission-steps/<type>/<action>/
    guidelines.md`` on disk, ``MissionTemplateRepository.get_action_guidelines``
    returns that file's content and an origin naming the ``mission-steps``
    path.
(c) The served software-dev ``implement``/``plan``/``review`` guidelines each
    carry the supply-chain section heading (pinned verbatim, as it appears in
    the ``mission-steps`` copy) and that section mentions ``DIRECTIVE_051``;
    ``review`` states the dependency rule as approved/done (the
    ``dependency_readiness_for_wp`` gate, where ``approved`` satisfies it).
(d) No served guideline says "main repository": guidelines use "repository
    root checkout" (charter Branch-Intent Terminology Governance).
"""

from __future__ import annotations

import pytest

from charter.offering.missions.repository import MissionTemplateRepository
from tests.doctrine.conftest import BUILT_IN_MISSIONS_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.doctrine]

_MISSION_STEPS_ROOT = BUILT_IN_MISSIONS_ROOT / "mission-steps"

# Pinned verbatim, as authored in the mission-steps/software-dev copies. The
# sections are references to DIRECTIVE_051 -- only the heading + the
# DIRECTIVE_051 mention are pinned here, never the pillar text.
_SOFTWARE_DEV_SUPPLY_CHAIN_HEADINGS = {
    "implement": "## Supply-Chain Security Check (dependency changes)",
    "plan": "## Supply-Chain Security & Adversarial Evidence",
    "review": "## Supply-Chain Security Evidence",
}

# Forbidden by the charter's Branch-Intent Terminology Governance: the
# non-worktree checkout is the "repository root checkout".
_FORBIDDEN_PHRASES = ("main repository",)


def _all_mission_step_guideline_pairs() -> list[tuple[str, str]]:
    """Every (mission_type, action) with a mission-steps guidelines.md on disk."""
    pairs: list[tuple[str, str]] = []
    for guidelines_path in sorted(_MISSION_STEPS_ROOT.glob("*/*/guidelines.md")):
        action_dir = guidelines_path.parent
        mission_type = action_dir.parent.name
        action = action_dir.name
        pairs.append((mission_type, action))
    return pairs


_MISSION_STEP_PAIRS = _all_mission_step_guideline_pairs()


class TestActionsCopiesAbsent:
    """No packs/built-in/missions/*/actions/*/guidelines.md exists."""

    def test_no_actions_guidelines_copies_remain(self) -> None:
        stragglers = sorted(BUILT_IN_MISSIONS_ROOT.glob("*/actions/*/guidelines.md"))
        assert not stragglers, f"actions/*/guidelines.md copies must be deleted -- mission-steps/ is the single owner (#5202): {stragglers}"


class TestLoaderResolvesMissionSteps:
    """MissionTemplateRepository serves the mission-steps copy, by origin."""

    @pytest.mark.parametrize(("mission_type", "action"), _MISSION_STEP_PAIRS)
    def test_repository_resolves_mission_steps_guidelines(self, mission_type: str, action: str) -> None:
        repo = MissionTemplateRepository(BUILT_IN_MISSIONS_ROOT)
        result = repo.get_action_guidelines(mission_type, action)
        assert result is not None, f"{mission_type}/{action}: loader did not resolve a mission-steps guidelines.md that exists on disk"
        on_disk = (_MISSION_STEPS_ROOT / mission_type / action / "guidelines.md").read_text(encoding="utf-8")
        assert result.content == on_disk, f"{mission_type}/{action}: served content does not match the mission-steps source on disk"
        assert "mission-steps" in result.origin, f"{mission_type}/{action}: origin {result.origin!r} does not name the mission-steps path"


class TestSoftwareDevSupplyChainSections:
    """supply-chain headings + DIRECTIVE_051 mention; review states approved/done."""

    @pytest.mark.parametrize(("action", "heading"), sorted(_SOFTWARE_DEV_SUPPLY_CHAIN_HEADINGS.items()))
    def test_supply_chain_heading_and_directive_051(self, action: str, heading: str) -> None:
        repo = MissionTemplateRepository(BUILT_IN_MISSIONS_ROOT)
        result = repo.get_action_guidelines("software-dev", action)
        assert result is not None
        assert heading in result.content, f"software-dev/{action}: served guidelines lost the pinned supply-chain heading {heading!r}"
        section = result.content.split(heading, 1)[1]
        assert "DIRECTIVE_051" in section, f"software-dev/{action}: supply-chain section does not mention DIRECTIVE_051"

    def test_review_dependency_rule_states_approved_or_done(self) -> None:
        repo = MissionTemplateRepository(BUILT_IN_MISSIONS_ROOT)
        result = repo.get_action_guidelines("software-dev", "review")
        assert result is not None
        dependency_rule_line = next(
            (line for line in result.content.splitlines() if "dependencies" in line and "frontmatter" in line),
            None,
        )
        assert dependency_rule_line is not None, "review guidelines must carry a dependency-rule line mentioning the `dependencies` frontmatter field"
        assert "approved" in dependency_rule_line and "done" in dependency_rule_line, (
            "the dependency-rule line must state the rule as approved/done "
            f"(dependency_readiness_for_wp: approved satisfies the gate); got: "
            f"{dependency_rule_line!r}"
        )
        assert "merged to main" not in result.content, "review guidelines must not gate on 'merged to main' -- the gate is approved/done, not a merge-to-main check"


class TestNoStalePhrases:
    """(d) served guidelines use "repository root checkout", never "main repository"."""

    @pytest.mark.parametrize(("mission_type", "action"), _MISSION_STEP_PAIRS)
    @pytest.mark.parametrize("phrase", _FORBIDDEN_PHRASES)
    def test_no_forbidden_phrase(self, mission_type: str, action: str, phrase: str) -> None:
        repo = MissionTemplateRepository(BUILT_IN_MISSIONS_ROOT)
        result = repo.get_action_guidelines(mission_type, action)
        assert result is not None
        assert phrase not in result.content, f"{mission_type}/{action}: served guidelines carry the forbidden phrase {phrase!r} (use 'repository root checkout')"
