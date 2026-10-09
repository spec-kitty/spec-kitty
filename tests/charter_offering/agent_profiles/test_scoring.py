"""Tests for the DDR-011 scoring helpers in charter.offering.agent_profiles.repository.

These tests target the pure scoring functions directly so that mutations on
return values (1.0 vs 0.0), threshold comparisons (≤ vs <), and weight
constants are distinguished from one another.

Patterns applied:
- Boundary Pair: exact threshold boundaries for workload and complexity.
- Non-Identity Inputs: distinct language/framework/keyword values, not defaults.
- Bi-Directional Logic: both match and non-match cases asserted together.
"""

import pytest

from charter.offering.agent_profiles.profile import AgentProfile, Role, SpecializationContext, TaskContext
from charter.offering.agent_profiles.repository import (
    _complexity_adjustment,
    _exact_id_signal,
    _file_pattern_signal,
    _filter_candidates_by_role,
    _framework_signal,
    _item_key,
    _keyword_signal,
    _language_signal,
    _score_profile,
    _union_merge,
    _workload_penalty,
)

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_profile(
    profile_id: str = "test-p",
    role: Role | str = Role.IMPLEMENTER,
    routing_priority: int = 50,
    languages: list[str] | None = None,
    frameworks: list[str] | None = None,
    file_patterns: list[str] | None = None,
    domain_keywords: list[str] | None = None,
) -> AgentProfile:
    # Lineage (``specializes-from``) is no longer a profile field (FR-002 / WP06
    # hard cutover); it is resolved from DRG ``specializes_from`` edges and
    # surfaces to scoring as the ``is_specialist`` flag on ``_score_profile``.
    ctx = None
    if any(x is not None for x in (languages, frameworks, file_patterns, domain_keywords)):
        ctx = SpecializationContext(
            languages=languages or [],
            frameworks=frameworks or [],
            file_patterns=file_patterns or [],
            domain_keywords=domain_keywords or [],
        )
    return AgentProfile(
        **{
            "profile-id": profile_id,
            "name": profile_id,
            "purpose": "test",
            "role": role,
            "routing-priority": routing_priority,
            "specialization": {"primary-focus": "Testing"},
            "specialization-context": ctx.model_dump(by_alias=True) if ctx else None,
        }
    )


# ── _workload_penalty ──────────────────────────────────────────────────────


class TestWorkloadPenalty:
    """Exact threshold and return-value assertions for _workload_penalty."""

    def test_workload_zero_returns_full_score(self):
        assert _workload_penalty(0) == 1.0

    def test_workload_at_low_ceiling_returns_full_score(self):
        # _MAX_LOW_WORKLOAD = 2; workload=2 must still be 1.0
        assert _workload_penalty(2) == 1.0

    def test_workload_just_above_low_ceiling_applies_medium_penalty(self):
        # workload=3 crosses _MAX_LOW_WORKLOAD; penalty drops to 0.85
        assert _workload_penalty(3) == 0.85

    def test_workload_at_medium_ceiling_applies_medium_penalty(self):
        # _MAX_MEDIUM_WORKLOAD = 4; workload=4 still gives 0.85
        assert _workload_penalty(4) == 0.85

    def test_workload_just_above_medium_ceiling_applies_high_penalty(self):
        # workload=5 crosses _MAX_MEDIUM_WORKLOAD; penalty drops to 0.70
        assert _workload_penalty(5) == 0.70

    def test_workload_well_above_ceiling_applies_high_penalty(self):
        assert _workload_penalty(100) == 0.70

    def test_low_workload_produces_higher_score_than_high_workload(self):
        assert _workload_penalty(1) > _workload_penalty(5)

    def test_medium_workload_produces_higher_score_than_high_workload(self):
        assert _workload_penalty(3) > _workload_penalty(5)


# ── _complexity_adjustment ─────────────────────────────────────────────────


class TestComplexityAdjustment:
    """Exact return-value assertions for _complexity_adjustment."""

    # Specialist (specializes_from is not None) cases
    def test_specialist_low_complexity_applies_discount(self):
        assert _complexity_adjustment(is_specialist=True, complexity="low") == 0.9

    def test_specialist_medium_complexity_is_neutral(self):
        assert _complexity_adjustment(is_specialist=True, complexity="medium") == 1.0

    def test_specialist_high_complexity_gets_bonus(self):
        assert _complexity_adjustment(is_specialist=True, complexity="high") == 1.1

    # Generalist (specializes_from is None) cases
    def test_generalist_low_complexity_is_neutral(self):
        assert _complexity_adjustment(is_specialist=False, complexity="low") == 1.0

    def test_generalist_medium_complexity_is_neutral(self):
        assert _complexity_adjustment(is_specialist=False, complexity="medium") == 1.0

    def test_generalist_high_complexity_applies_discount(self):
        assert _complexity_adjustment(is_specialist=False, complexity="high") == 0.9

    def test_unknown_complexity_falls_back_to_neutral(self):
        # Unknown complexity string must not raise; default is 1.0
        assert _complexity_adjustment(is_specialist=True, complexity="unknown") == 1.0
        assert _complexity_adjustment(is_specialist=False, complexity="unknown") == 1.0


# ── Signal functions ───────────────────────────────────────────────────────


class TestLanguageSignal:
    """_language_signal returns 1.0 on match, 0.0 otherwise."""

    def test_matching_language_returns_one(self):
        profile = _make_profile(languages=["python", "go"])
        ctx = TaskContext(language="python")
        assert _language_signal(ctx, profile) == 1.0

    def test_non_matching_language_returns_zero(self):
        profile = _make_profile(languages=["python"])
        ctx = TaskContext(language="rust")
        assert _language_signal(ctx, profile) == 0.0

    def test_no_context_language_returns_zero(self):
        profile = _make_profile(languages=["python"])
        ctx = TaskContext()
        assert _language_signal(ctx, profile) == 0.0

    def test_no_profile_specialization_context_returns_zero(self):
        profile = _make_profile()  # no languages
        ctx = TaskContext(language="python")
        assert _language_signal(ctx, profile) == 0.0

    def test_case_insensitive_match(self):
        profile = _make_profile(languages=["Python"])
        ctx = TaskContext(language="python")
        assert _language_signal(ctx, profile) == 1.0


class TestFrameworkSignal:
    """_framework_signal returns 1.0 on match, 0.0 otherwise."""

    def test_matching_framework_returns_one(self):
        profile = _make_profile(frameworks=["django", "pytest"])
        ctx = TaskContext(framework="pytest")
        assert _framework_signal(ctx, profile) == 1.0

    def test_non_matching_framework_returns_zero(self):
        profile = _make_profile(frameworks=["django"])
        ctx = TaskContext(framework="fastapi")
        assert _framework_signal(ctx, profile) == 0.0

    def test_no_context_framework_returns_zero(self):
        profile = _make_profile(frameworks=["django"])
        ctx = TaskContext()
        assert _framework_signal(ctx, profile) == 0.0


class TestFilePatternSignal:
    """_file_pattern_signal returns 1.0 when any file matches any pattern."""

    def test_matching_pattern_returns_one(self):
        profile = _make_profile(file_patterns=["**/*.py"])
        ctx = TaskContext(file_paths=["src/foo.py"])
        assert _file_pattern_signal(ctx, profile) == 1.0

    def test_non_matching_pattern_returns_zero(self):
        profile = _make_profile(file_patterns=["**/*.py"])
        ctx = TaskContext(file_paths=["src/foo.ts"])
        assert _file_pattern_signal(ctx, profile) == 0.0

    def test_one_of_many_files_matches_returns_one(self):
        profile = _make_profile(file_patterns=["**/*.py"])
        ctx = TaskContext(file_paths=["src/foo.ts", "src/bar.py"])
        assert _file_pattern_signal(ctx, profile) == 1.0

    def test_empty_file_paths_returns_zero(self):
        profile = _make_profile(file_patterns=["**/*.py"])
        ctx = TaskContext()
        assert _file_pattern_signal(ctx, profile) == 0.0


class TestKeywordSignal:
    """_keyword_signal returns 1.0 when any context keyword hits a profile keyword."""

    def test_matching_keyword_returns_one(self):
        profile = _make_profile(domain_keywords=["backend", "api"])
        ctx = TaskContext(keywords=["api"])
        assert _keyword_signal(ctx, profile) == 1.0

    def test_non_matching_keyword_returns_zero(self):
        profile = _make_profile(domain_keywords=["backend"])
        ctx = TaskContext(keywords=["frontend"])
        assert _keyword_signal(ctx, profile) == 0.0

    def test_empty_keywords_returns_zero(self):
        profile = _make_profile(domain_keywords=["backend"])
        ctx = TaskContext()
        assert _keyword_signal(ctx, profile) == 0.0


class TestExactIdSignal:
    """_exact_id_signal returns 1.0 when required_role matches profile_id or role value."""

    def test_matches_profile_id_returns_one(self):
        profile = _make_profile(profile_id="python-pedro", role=Role.IMPLEMENTER)
        ctx = TaskContext(required_role="python-pedro")
        assert _exact_id_signal(ctx, profile) == 1.0

    def test_matches_role_value_returns_one(self):
        profile = _make_profile(profile_id="python-pedro", role=Role.IMPLEMENTER)
        ctx = TaskContext(required_role="implementer")
        assert _exact_id_signal(ctx, profile) == 1.0

    def test_no_match_returns_zero(self):
        profile = _make_profile(profile_id="python-pedro", role=Role.IMPLEMENTER)
        ctx = TaskContext(required_role="reviewer")
        assert _exact_id_signal(ctx, profile) == 0.0

    def test_no_required_role_returns_zero(self):
        profile = _make_profile(profile_id="python-pedro", role=Role.IMPLEMENTER)
        ctx = TaskContext()
        assert _exact_id_signal(ctx, profile) == 0.0


# ── _filter_candidates_by_role ────────────────────────────────────────────


class TestFilterCandidatesByRole:
    """_filter_candidates_by_role conditions and edge cases."""

    def _profiles(self) -> list[AgentProfile]:
        return [
            _make_profile("impl-a", role=Role.IMPLEMENTER),
            _make_profile("rev-a", role=Role.REVIEWER),
            _make_profile("arch-a", role=Role.ARCHITECT),
        ]

    def test_no_required_role_returns_all_candidates(self):
        result = _filter_candidates_by_role(self._profiles(), required_role=None)
        assert len(result) == 3

    def test_empty_string_role_returns_all_candidates(self):
        result = _filter_candidates_by_role(self._profiles(), required_role="")
        assert len(result) == 3

    def test_role_string_filters_by_role_value(self):
        result = _filter_candidates_by_role(self._profiles(), required_role="implementer")
        assert len(result) == 1
        assert result[0].profile_id == "impl-a"

    def test_role_string_filters_case_insensitively(self):
        result = _filter_candidates_by_role(self._profiles(), required_role="REVIEWER")
        assert len(result) == 1
        assert result[0].profile_id == "rev-a"

    def test_profile_id_match_is_included(self):
        # A profile whose profile_id exactly matches required_role is included
        # even if its role field doesn't match.
        profiles = [_make_profile("special-agent", role=Role.IMPLEMENTER)]
        result = _filter_candidates_by_role(profiles, required_role="special-agent")
        assert len(result) == 1

    def test_nonexistent_role_returns_empty(self):
        result = _filter_candidates_by_role(self._profiles(), required_role="curator")
        assert result == []


# ── _item_key ──────────────────────────────────────────────────────────────


class TestItemKey:
    """_item_key extracts a stable deduplication key."""

    def test_dict_with_code_key_returns_code(self):
        assert _item_key({"code": "010", "name": "some directive"}) == "010"

    def test_dict_without_code_key_returns_str_repr(self):
        item = {"name": "no-code"}
        assert _item_key(item) == str(item)

    def test_string_returns_string(self):
        assert _item_key("read") == "read"

    def test_integer_returns_str(self):
        assert _item_key(42) == "42"


# ── _union_merge ───────────────────────────────────────────────────────────


class TestUnionMerge:
    """_union_merge semantics: list-type fields unite, scalars child-replaces."""

    def test_list_field_deduplicated_on_merge(self):
        parent = {"capabilities": ["read", "write"]}
        child = {"capabilities": ["write", "search"]}  # "write" already in parent
        merged = _union_merge(parent, child)
        assert merged["capabilities"] == ["read", "write", "search"]
        assert merged["capabilities"].count("write") == 1  # no duplicate

    def test_list_field_new_items_appended(self):
        parent = {"capabilities": ["read"]}
        child = {"capabilities": ["search"]}
        merged = _union_merge(parent, child)
        assert "read" in merged["capabilities"]
        assert "search" in merged["capabilities"]

    def test_non_list_scalar_child_replaces_parent(self):
        parent = {"routing-priority": 50, "name": "Parent"}
        child = {"routing-priority": 80}
        merged = _union_merge(parent, child)
        assert merged["routing-priority"] == 80
        assert merged["name"] == "Parent"  # unchanged

    def test_nested_dict_merges_one_level_deep(self):
        parent = {"specialization": {"primary-focus": "A", "avoidance-boundary": "B"}}
        child = {"specialization": {"primary-focus": "C"}}
        merged = _union_merge(parent, child)
        assert merged["specialization"]["primary-focus"] == "C"
        assert merged["specialization"]["avoidance-boundary"] == "B"

    def test_directive_references_deduplicated_by_code(self):
        parent = {"directive-references": [{"code": "010", "name": "D010"}]}
        child = {"directive-references": [{"code": "010", "name": "D010"}, {"code": "025", "name": "D025"}]}
        merged = _union_merge(parent, child)
        codes = [item["code"] for item in merged["directive-references"]]
        assert codes.count("010") == 1
        assert "025" in codes


# ── _score_profile integration ─────────────────────────────────────────────


class TestScoreProfile:
    """Integration tests that confirm weight contributions are distinguishable."""

    def test_language_match_increases_score_over_no_match(self):
        profile_with = _make_profile("with-lang", routing_priority=50, languages=["python"])
        profile_without = _make_profile("no-lang", routing_priority=50)
        ctx = TaskContext(language="python")
        assert _score_profile(ctx, profile_with) > _score_profile(ctx, profile_without)

    def test_high_routing_priority_wins_when_no_signals_match(self):
        low = _make_profile("low-p", routing_priority=10)
        high = _make_profile("high-p", routing_priority=90)
        ctx = TaskContext()  # no signals
        assert _score_profile(ctx, high) > _score_profile(ctx, low)

    def test_workload_penalty_reduces_score(self):
        profile = _make_profile(routing_priority=50, languages=["python"])
        ctx_light = TaskContext(language="python", current_workload=0)
        ctx_heavy = TaskContext(language="python", current_workload=5)
        assert _score_profile(ctx_light, profile) > _score_profile(ctx_heavy, profile)

    def test_specialist_high_complexity_bonus_applies(self):
        specialist = _make_profile("spec", routing_priority=50)
        generalist = _make_profile("gen", routing_priority=50)
        ctx = TaskContext(complexity="high")
        # is_specialist now comes from DRG lineage resolution, passed explicitly.
        assert _score_profile(ctx, specialist, is_specialist=True) > _score_profile(
            ctx, generalist, is_specialist=False
        )
