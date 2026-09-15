"""Unit tests for the WP05 token-budget enforcement (NFR-001).

The tests cover the standalone :func:`apply_token_budget` helper plus
the end-to-end self-sufficiency check that the full bootstrap render
respects the budget for a bounded, single-directive profile fixture.
"""

from __future__ import annotations

import re

import pytest

from charter.activation.context_renderers import (
    BUDGET_DEFAULT,
    RenderedSection,
    apply_token_budget,
    fetch_stanza,
    warning_line,
)
from charter.activation.context_renderers.fetch_stanza import (
    DEFAULT_WHEN_CLAUSE,
    format_selector,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit]


def _make_section(
    section_id: str,
    body: str,
    *,
    selector: str = "",
    substitutable: bool = True,
    header: str = "",
    when: str = "are about to apply a code change",
    indent: str = "",
) -> RenderedSection:
    """Build a RenderedSection with reasonable defaults for the test grid."""

    if selector == "" and substitutable:
        selector = f"section:{section_id}"
    return RenderedSection(
        section_id=section_id,
        header=header,
        body=body,
        selector=selector,
        when_doing_clause=when,
        substitutable=substitutable,
        indent=indent,
    )


# ---------------------------------------------------------------------------
# apply_token_budget — substitution algorithm
# ---------------------------------------------------------------------------


class TestUnderBudget:
    """The under-budget path emits the original text and reports no swaps."""

    def test_under_budget_no_substitution(self) -> None:
        sections = [
            _make_section("alpha", "a" * 2_000),
            _make_section("beta", "b" * 3_000),
            _make_section("gamma", "g" * 3_000),
        ]
        joined, notes = apply_token_budget(sections, budget=32_000)

        assert notes == []
        # Original bodies survive verbatim
        assert "a" * 2_000 in joined
        assert "b" * 3_000 in joined
        assert "g" * 3_000 in joined
        # No warning line
        assert "# Governance payload" not in joined


class TestOverBudgetSubstitution:
    """The over-budget path swaps the longest body first."""

    def test_over_budget_substitutes_longest_first(self) -> None:
        long_body = "L" * 30_000
        sections = [
            _make_section("alpha", "a" * 200),
            _make_section("longest", long_body, selector="directive:DIRECTIVE_010"),
            _make_section("gamma", "g" * 5_000),
        ]
        joined, notes = apply_token_budget(sections, budget=10_000)

        # Longest body is gone
        assert long_body not in joined
        # Replaced with the canonical fetch stanza
        assert "spec-kitty charter context --include directive:DIRECTIVE_010" in joined
        assert "When you" in joined
        # Shorter bodies survive
        assert "a" * 200 in joined
        assert "g" * 5_000 in joined
        # Note recorded the swap
        assert any("longest" in note for note in notes)

    def test_severely_over_budget_substitutes_all_bodies(self) -> None:
        big_a = "A" * 20_000
        big_b = "B" * 20_000
        big_c = "C" * 20_000
        sections = [
            _make_section("alpha", big_a, selector="directive:A"),
            _make_section("beta", big_b, selector="tactic:B"),
            _make_section("gamma", big_c, selector="section:C"),
        ]
        joined, notes = apply_token_budget(sections, budget=10_000)

        # All three bodies replaced
        assert big_a not in joined
        assert big_b not in joined
        assert big_c not in joined
        # All three selectors appear in the substituted output
        assert "directive:A" in joined
        assert "tactic:B" in joined
        assert "section:C" in joined
        # All three swapped
        assert len(notes) == 3

    def test_substitution_is_deterministic_under_ties(self) -> None:
        # Three bodies of equal length — section_id ascending wins the tie.
        sections = [
            _make_section("zebra", "x" * 5_000, selector="directive:Z"),
            _make_section("apple", "x" * 5_000, selector="directive:A"),
            _make_section("mango", "x" * 5_000, selector="directive:M"),
        ]
        # Force two swaps
        _, notes1 = apply_token_budget(sections, budget=11_000)
        _, notes2 = apply_token_budget(sections, budget=11_000)

        assert notes1 == notes2
        # apple sorts first under ties (ascending section_id)
        assert "apple" in notes1[0]


# ---------------------------------------------------------------------------
# Warning line emission
# ---------------------------------------------------------------------------


class TestWarningLine:
    def test_warning_line_emitted_when_any_substitution_happens(self) -> None:
        long_body = "L" * 30_000
        sections = [
            _make_section("longest", long_body, selector="directive:DIRECTIVE_010"),
            _make_section("small", "s" * 100),
        ]
        joined, notes = apply_token_budget(sections, budget=5_000)

        assert notes  # at least one swap
        # The warning line is appended at the tail.
        assert joined.rstrip().endswith(warning_line(len(notes), 5_000))

    def test_warning_line_absent_when_no_substitution(self) -> None:
        sections = [
            _make_section("alpha", "a" * 500),
            _make_section("beta", "b" * 500),
        ]
        joined, notes = apply_token_budget(sections, budget=32_000)

        assert notes == []
        assert "# Governance payload" not in joined

    def test_warning_line_counts_against_budget_after_substitution(self) -> None:
        long_body = "L" * 1_000
        short_body = "S" * 400
        sections = [
            _make_section("longest", long_body, selector="directive:DIRECTIVE_010"),
            _make_section("short", short_body, selector="tactic:TACTIC_010"),
        ]
        first_swap_text = "\n\n".join(
            [
                fetch_stanza("directive:DIRECTIVE_010", "are about to apply a code change"),
                short_body,
            ]
        )
        budget = len(first_swap_text) + 30

        joined, notes = apply_token_budget(sections, budget=budget)

        assert len(joined) <= budget
        assert long_body not in joined
        assert short_body not in joined
        assert len(notes) == 2
        assert joined.rstrip().endswith(warning_line(len(notes), budget))

    def test_production_context_budget_counts_warning_line(self) -> None:
        from charter.activation.context_renderers.token_budget import _enforce_token_budget

        section_block = "S" * 1_000
        profile_block = "P" * 400
        text = f"Charter Context (Bootstrap):\n\n{section_block}\n\n{profile_block}"
        first_swap_text = text.replace(
            section_block,
            fetch_stanza(
                "section:critical-implement",
                "need to consult the action-critical charter sections",
                indent="  ",
            ),
            1,
        )
        budget = len(first_swap_text) + 30

        result = _enforce_token_budget(
            text,
            action="implement",
            profile_block=profile_block,
            section_block=section_block,
            budget=budget,
        )

        assert len(result) <= budget
        assert section_block not in result
        assert profile_block not in result
        assert result.rstrip().endswith(warning_line(2, budget))


# ---------------------------------------------------------------------------
# Header preservation on substitution (landing fold, origin 873832aa1) —
# ``_enforce_token_budget`` used to hand the WHOLE ``section_block`` /
# ``profile_block`` string to ``RenderedSection`` with ``header=""``, even
# though each block's own first line IS its anchor header (e.g.
# ``Profile-Cited Directives (<profile-id>):``). A budget-forced swap then
# deleted the header along with the body it was meant to label — the
# invariant this module's own ``RenderedSection.header`` docstring promises
# ("the substitution algorithm never touches the header") did not hold for
# either caller. These tests pin the fix at the unit level so the defect
# cannot silently regress behind the (much slower) integration test that
# first caught it.
# ---------------------------------------------------------------------------


class TestHeaderSurvivesSubstitution:
    """A section whose body starts with its own header line keeps that
    header after token-budget substitution."""

    def test_single_header_body_keeps_header_after_swap(self) -> None:
        from charter.activation.context_renderers.token_budget import _enforce_token_budget

        header_line = "Profile-Cited Directives (reviewer-renata):"
        profile_block = header_line + "\n" + ("x" * 40_000)
        text = "Preamble.\n\n" + profile_block

        result = _enforce_token_budget(
            text,
            action="advise",
            profile_block=profile_block,
            section_block="",
        )

        # The block was big enough to force a swap...
        assert "# Governance payload" in result
        assert ("x" * 40_000) not in result
        # ...but the anchor header line survived the swap verbatim.
        assert header_line in result

    def test_multi_kind_profile_block_keeps_every_populated_header(self) -> None:
        """profile_block joins several kind-blocks (directives, tactics, ...);
        ALL of their headers must survive, not just the first one swapped."""
        from charter.activation.context_renderers.token_budget import _enforce_token_budget

        directives_header = "Profile-Cited Directives (reviewer-renata):"
        tactics_header = "Profile-Cited Tactics (reviewer-renata):"
        profile_block = "\n\n".join(
            [
                directives_header + "\n" + ("d" * 20_000),
                tactics_header + "\n" + ("t" * 20_000),
            ]
        )
        text = "Preamble.\n\n" + profile_block

        # A tight budget forces BOTH kind-blocks to swap, not just the
        # longer one — proving every populated header survives, not only
        # whichever block happens to be picked first.
        result = _enforce_token_budget(
            text,
            action="advise",
            profile_block=profile_block,
            section_block="",
            budget=200,
        )

        assert "# Governance payload" in result
        assert ("d" * 20_000) not in result
        assert ("t" * 20_000) not in result
        assert directives_header in result
        assert tactics_header in result

    def test_action_critical_section_block_keeps_outer_header_after_swap(
        self,
    ) -> None:
        from charter.activation.context_renderers.token_budget import _enforce_token_budget

        header_line = "Action-Critical Charter Sections (implement):"
        section_block = header_line + "\n" + ("y" * 40_000)
        text = "Preamble.\n\n" + section_block

        result = _enforce_token_budget(
            text,
            action="implement",
            profile_block="",
            section_block=section_block,
        )

        assert "# Governance payload" in result
        assert ("y" * 40_000) not in result
        assert header_line in result

    def test_header_less_body_still_fully_substituted(self) -> None:
        """A section with no separate header line (single-line body, the
        RenderedSection.header='' by-design case) still swaps its ENTIRE
        body — the header-preservation fix must not change this baseline."""
        from charter.activation.context_renderers.token_budget import _enforce_token_budget

        body_only = "z" * 40_000
        text = "Preamble.\n\n" + body_only

        result = _enforce_token_budget(
            text,
            action="advise",
            profile_block=body_only,
            section_block="",
        )

        assert "# Governance payload" in result
        assert body_only not in result


# ---------------------------------------------------------------------------
# Fetch stanza contract
# ---------------------------------------------------------------------------


class TestFetchStanzaContract:
    """The substituted fetch stanza MUST satisfy the ATDD regex pair."""

    _FETCH_CMD_RE = re.compile(
        r"spec-kitty\s+charter\s+context\b",
        re.IGNORECASE,
    )
    _WHEN_DOING_RE = re.compile(
        r"when\s+you\s+(are\s+about\s+to|need\s+to|encounter|introduce|rename|review)",
        re.IGNORECASE,
    )

    def test_fetch_stanza_carries_when_doing_clause(self) -> None:
        long_body = "L" * 30_000
        sections = [
            _make_section(
                "directive_010",
                long_body,
                selector="directive:DIRECTIVE_010",
                when="are about to apply a code change",
            ),
        ]
        joined, _notes = apply_token_budget(sections, budget=5_000)

        # The fetch command line and the when-doing line both match the
        # contract regexes pinned by the ATDD helper.
        assert self._FETCH_CMD_RE.search(joined), joined
        assert self._WHEN_DOING_RE.search(joined), joined
        # The selector is present verbatim.
        assert "directive:DIRECTIVE_010" in joined

    def test_default_when_clause_used_when_omitted(self) -> None:
        long_body = "L" * 30_000
        sections = [
            _make_section(
                "directive_010",
                long_body,
                selector="directive:DIRECTIVE_010",
                when="",  # falls back to DEFAULT_WHEN_CLAUSE
            ),
        ]
        joined, notes = apply_token_budget(sections, budget=5_000)

        assert notes
        assert DEFAULT_WHEN_CLAUSE in joined

    def test_fetch_stanza_helper_matches_contract(self) -> None:
        stanza = fetch_stanza("directive:DIRECTIVE_010", "rename or introduce a term in the diff")
        lines = stanza.splitlines()
        assert len(lines) == 2
        assert lines[0] == "Run: spec-kitty charter context --include directive:DIRECTIVE_010"
        assert lines[1].startswith("When you rename or introduce a term in the diff,")

    def test_format_selector_canonical_forms(self) -> None:
        assert format_selector("directive", "DIRECTIVE_010") == "directive:DIRECTIVE_010"
        assert format_selector("tactic", "lang-driven-design") == "tactic:lang-driven-design"
        assert format_selector("section", "terminology-canon") == "section:terminology-canon"
        # Unknown but non-empty kind round-trips (callers may extend).
        assert format_selector("custom", "x") == "custom:x"
        # Empty inputs collapse to the empty string.
        assert format_selector("", "x") == ""
        assert format_selector("directive", "") == ""


# ---------------------------------------------------------------------------
# Non-substitutable sections
# ---------------------------------------------------------------------------


class TestNonSubstitutable:
    """Authority paths and core doctrine MUST stay inline regardless of budget."""

    def test_authority_paths_never_substituted(self) -> None:
        # The authority-paths block is small but marked non-substitutable;
        # the long substitutable section is the only swap candidate.
        authority_block = "Project authority paths:\n  - docs/context/    (canonical terminology)"
        long_body = "L" * 30_000
        sections = [
            _make_section(
                "authority-paths",
                authority_block,
                selector="",
                substitutable=False,
            ),
            _make_section(
                "long-section",
                long_body,
                selector="section:long",
            ),
        ]
        joined, notes = apply_token_budget(sections, budget=5_000)

        # Authority block survives byte-for-byte.
        assert authority_block in joined
        # Long body is swapped.
        assert long_body not in joined
        assert any("long-section" in note for note in notes)

    def test_no_swap_when_only_non_substitutable_over_budget(self) -> None:
        # When every section is non-substitutable the algorithm returns
        # the over-budget text rather than looping forever.
        sections = [
            _make_section("only", "x" * 50_000, substitutable=False),
        ]
        joined, notes = apply_token_budget(sections, budget=10_000)

        assert notes == []
        assert len(joined) > 10_000  # over budget but content preserved


# ---------------------------------------------------------------------------
# Defaults + edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_input_returns_empty_text(self) -> None:
        joined, notes = apply_token_budget([], budget=32_000)
        assert joined == ""
        assert notes == []

    def test_default_budget_is_40k(self) -> None:
        # Raised 32_000 -> 40_000 (2026-08-12) so the software-dev doctrine
        # cascade wired by 3bcdda344 fits without compacting away the
        # anti-drift anchors (DIRECTIVE_032, glossary, ADR). See
        # BUDGET_DEFAULT's docstring in token_budget.py.
        assert BUDGET_DEFAULT == 40_000

    def test_non_positive_budget_is_noop(self) -> None:
        sections = [_make_section("a", "x" * 100)]
        joined, notes = apply_token_budget(sections, budget=0)
        assert notes == []
        assert "x" * 100 in joined


# ---------------------------------------------------------------------------
# Aggregate self-sufficiency — end-to-end render under budget
# ---------------------------------------------------------------------------


class TestAggregateUnderBudget:
    """A bounded bootstrap includes directive navigation without compaction."""

    def test_aggregate_self_sufficiency_under_budget(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        from types import SimpleNamespace

        from charter.activation.context import build_charter_context
        from charter.activation.profile_resolution import _reset_agent_profile_cache
        from charter.offering.agent_profiles import AgentProfile

        # Keep the input bounded independently of the development repo's growing
        # charter and profile corpus. Exercise the actual aggregate renderer.
        charter_dir = tmp_path / ".kittify/charter"
        charter_dir.mkdir(parents=True)
        (charter_dir / "charter.md").write_text(
            "# Project Charter\n\n## Policy Summary\n\n- Intent: deterministic delivery\n",
            encoding="utf-8",
        )
        (charter_dir / "charter.yaml").write_text(
            'schema_version: "2.0.0"\ngovernance:\n  charter:\n    selected_directives: [DIRECTIVE_025]\n',
            encoding="utf-8",
        )
        (tmp_path / ".kittify/config.yaml").write_text("mission_type_activations: [software-dev]\n", encoding="utf-8")
        profile = AgentProfile.model_validate(
            {
                "profile-id": "budget-fixture-agent",
                "name": "Budget Fixture Agent",
                "roles": ["implementer"],
                "purpose": "Bounded bootstrap fixture",
                "specialization": {"primary-focus": "testing"},
                "directive-references": [{"code": "025", "name": "Boy Scout Rule", "rationale": "Preserve local cleanup"}],
            }
        )
        repository = SimpleNamespace(get=lambda name: profile if name == profile.profile_id else None)
        monkeypatch.setattr("charter.activation.context._default_agent_profile_repository", lambda: repository)
        _reset_agent_profile_cache()
        try:
            result = build_charter_context(tmp_path, profile=profile.profile_id, action="implement", mark_loaded=False)
        finally:
            _reset_agent_profile_cache()
        assert len(result.text) <= BUDGET_DEFAULT, f"Bootstrap render produced {len(result.text)} chars, exceeding NFR-001 budget of {BUDGET_DEFAULT}."
        assert "Selected directives:" in result.text
        assert "Profile-Cited Directives (budget-fixture-agent):" in result.text
        assert "Run: spec-kitty charter context --include directive:DIRECTIVE_025" in result.text
        assert "DIRECTIVE_025" in result.text or "025-boy-scout-rule" in result.text
        assert "sections substituted with fetch commands" not in result.text
