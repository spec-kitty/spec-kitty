"""Tests for shims/registry.py — skill allowlist.

The registry sets (``CONSUMER_SKILLS`` etc.) are ``frozenset``s, whose iteration
order is randomised per process by ``PYTHONHASHSEED``. Parametrising over a bare
``list(<frozenset>)`` therefore produces a different case order in each
``pytest-xdist`` worker process, which trips xdist's collection-equivalence guard
("Different tests were collected between gw0 and gwN"). Always wrap the set in
``sorted(...)`` so the parametrised case order is deterministic across workers.
See docs/development/testing/testing-flakiness.md (Tier: parallel-collection nondeterminism).
"""

from __future__ import annotations

import pytest

from specify_cli.shims.registry import (
    CLI_DRIVEN_COMMANDS,
    CONSUMER_SKILLS,
    INTERNAL_SKILLS,
    PROMPT_DRIVEN_COMMANDS,
    get_all_skills,
    is_cli_driven,
    is_prompt_driven,
)


pytestmark = [pytest.mark.unit, pytest.mark.fast]
class TestConsumerSkills:
    @pytest.mark.parametrize(
        "skill",
        [
            "specify",
            "plan",
            "tasks",
            "tasks-outline",
            "tasks-packages",
            "tasks-finalize",
            "implement",
            "review",
            "accept",
            "consolidate",
            "status",
            "analyze",
            "research",
            "charter",
        ],
    )
    def test_known_consumer_skills_present(self, skill: str) -> None:
        assert skill in CONSUMER_SKILLS

    def test_consumer_skills_is_frozenset(self) -> None:
        assert isinstance(CONSUMER_SKILLS, frozenset)

    def test_retired_checklist_is_not_consumer_facing(self) -> None:
        assert "checklist" not in CONSUMER_SKILLS

    def test_internal_skills_not_in_consumer(self) -> None:
        for skill in INTERNAL_SKILLS:
            assert skill not in CONSUMER_SKILLS, f"{skill} should not be consumer-facing"


class TestInternalSkills:
    @pytest.mark.parametrize("skill", ["doctor", "materialize", "debug"])
    def test_known_internal_skills_present(self, skill: str) -> None:
        assert skill in INTERNAL_SKILLS

    def test_internal_skills_is_frozenset(self) -> None:
        assert isinstance(INTERNAL_SKILLS, frozenset)


class TestGetAllSkills:
    def test_contains_consumer_skills(self) -> None:
        all_skills = get_all_skills()
        assert CONSUMER_SKILLS.issubset(all_skills)

    def test_contains_internal_skills(self) -> None:
        all_skills = get_all_skills()
        assert INTERNAL_SKILLS.issubset(all_skills)

    def test_is_union(self) -> None:
        assert get_all_skills() == CONSUMER_SKILLS | INTERNAL_SKILLS

    def test_returns_frozenset(self) -> None:
        assert isinstance(get_all_skills(), frozenset)


class TestPromptDrivenCommands:
    def test_is_frozenset(self) -> None:
        assert isinstance(PROMPT_DRIVEN_COMMANDS, frozenset)

    def test_has_nine_commands(self) -> None:
        assert len(PROMPT_DRIVEN_COMMANDS) == 9

    @pytest.mark.parametrize(
        "skill",
        [
            "specify",
            "plan",
            "tasks",
            "tasks-outline",
            "tasks-packages",
            "analyze",
            "research",
            "charter",
        ],
    )
    def test_expected_commands_present(self, skill: str) -> None:
        assert skill in PROMPT_DRIVEN_COMMANDS

    def test_subset_of_consumer_skills(self) -> None:
        assert PROMPT_DRIVEN_COMMANDS.issubset(CONSUMER_SKILLS)

    def test_retired_checklist_is_not_prompt_driven(self) -> None:
        assert "checklist" not in PROMPT_DRIVEN_COMMANDS


class TestCliDrivenCommands:
    def test_is_frozenset(self) -> None:
        assert isinstance(CLI_DRIVEN_COMMANDS, frozenset)

    @pytest.mark.parametrize(
        "skill",
        [
            "implement",
            "review",
            "accept",
            "consolidate",
            "status",
            "tasks-finalize",
        ],
    )
    def test_expected_commands_present(self, skill: str) -> None:
        assert skill in CLI_DRIVEN_COMMANDS

    def test_subset_of_consumer_skills(self) -> None:
        assert CLI_DRIVEN_COMMANDS.issubset(CONSUMER_SKILLS)

    def test_disjoint_from_prompt_driven(self) -> None:
        assert frozenset() == CLI_DRIVEN_COMMANDS & PROMPT_DRIVEN_COMMANDS


class TestCommandClassificationInvariant:
    def test_union_equals_consumer_skills(self) -> None:
        assert PROMPT_DRIVEN_COMMANDS | CLI_DRIVEN_COMMANDS == CONSUMER_SKILLS

    def test_no_overlap_between_sets(self) -> None:
        assert frozenset() == PROMPT_DRIVEN_COMMANDS & CLI_DRIVEN_COMMANDS

class TestIsPromptDriven:
    @pytest.mark.parametrize("skill", sorted(PROMPT_DRIVEN_COMMANDS))
    def test_returns_true_for_prompt_driven(self, skill: str) -> None:
        assert is_prompt_driven(skill) is True

    @pytest.mark.parametrize("skill", sorted(CLI_DRIVEN_COMMANDS))
    def test_returns_false_for_cli_driven(self, skill: str) -> None:
        assert is_prompt_driven(skill) is False

    def test_returns_false_for_internal(self) -> None:
        assert is_prompt_driven("doctor") is False

    def test_returns_false_for_unknown(self) -> None:
        assert is_prompt_driven("nonexistent-xyz") is False


class TestIsCliDriven:
    @pytest.mark.parametrize("skill", sorted(CLI_DRIVEN_COMMANDS))
    def test_returns_true_for_cli_driven(self, skill: str) -> None:
        assert is_cli_driven(skill) is True

    @pytest.mark.parametrize("skill", sorted(PROMPT_DRIVEN_COMMANDS))
    def test_returns_false_for_prompt_driven(self, skill: str) -> None:
        assert is_cli_driven(skill) is False

    def test_returns_false_for_internal(self) -> None:
        assert is_cli_driven("doctor") is False

    def test_returns_false_for_unknown(self) -> None:
        assert is_cli_driven("nonexistent-xyz") is False
