"""Sonar remediation tests for ``token_budget.py`` (WP01).

Characterizes the helpers extracted from ``_enforce_token_budget``:

- ``S3776`` at :365 (cognitive complexity 28) — ``_enforce_token_budget``
  was decomposed into ``_collect_section_block_candidates``,
  ``_collect_profile_block_candidates``, and ``_swap_candidates_into_text``.
  These tests characterize each helper directly and confirm the top-level
  function's observable behaviour is unchanged.
"""

from __future__ import annotations

import pytest

from charter.activation.context_renderers.token_budget import (
    RenderedSection,
    _collect_profile_block_candidates,
    _collect_section_block_candidates,
    _enforce_token_budget,
    _swap_candidates_into_text,
)

pytestmark = [pytest.mark.unit]

# ---------------------------------------------------------------------------
# S3776 — extracted helper characterization
# ---------------------------------------------------------------------------


class TestCollectSectionBlockCandidates:
    """Characterize ``_collect_section_block_candidates`` in isolation."""

    def test_empty_block_returns_no_candidates(self) -> None:
        assert _collect_section_block_candidates("", action="implement") == []

    def test_headed_block_yields_one_candidate_per_heading(self) -> None:
        section_block = (
            "Action-Critical Charter Sections (implement):\n\n"
            "### Terminology Canon\nBody one.\n\n"
            "### Regression Vigilance\nBody two."
        )

        candidates = _collect_section_block_candidates(section_block, action="implement")

        ids = [c.section_id for c in candidates]
        assert ids == [
            "action-critical-sections:Terminology Canon",
            "action-critical-sections:Regression Vigilance",
        ]
        assert all(c.substitutable for c in candidates)
        assert all(c.indent == "  " for c in candidates)
        assert candidates[0].header == "### Terminology Canon"
        assert candidates[0].body == "Body one."

    def test_headed_block_skips_empty_bodies(self) -> None:
        section_block = "### Empty Heading\n\n### Real Heading\nBody."

        candidates = _collect_section_block_candidates(section_block, action="implement")

        assert [c.section_id for c in candidates] == [
            "action-critical-sections:Real Heading"
        ]

    def test_unheaded_block_falls_back_to_single_candidate(self) -> None:
        # No "### " sub-structure at all — single-blob fallback path.
        section_block = "Action-Critical Charter Sections (advise):\n" + ("y" * 500)

        candidates = _collect_section_block_candidates(section_block, action="advise")

        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate.section_id == "action-critical-sections"
        assert candidate.header == "Action-Critical Charter Sections (advise):"
        assert candidate.selector == "section:critical-advise"
        assert candidate.body == "y" * 500

    def test_unheaded_body_less_block_yields_no_candidate(self) -> None:
        # A header line followed by nothing (a trailing newline with no
        # remainder) has nothing left worth swapping — see
        # _split_leading_header: the header/body split leaves body="".
        section_block = "HeaderLine\n"

        candidates = _collect_section_block_candidates(section_block, action="implement")

        assert candidates == []


class TestCollectProfileBlockCandidates:
    """Characterize ``_collect_profile_block_candidates`` in isolation."""

    def test_empty_block_returns_no_candidates(self) -> None:
        assert _collect_profile_block_candidates("") == []

    def test_multi_kind_block_yields_one_candidate_per_kind(self) -> None:
        profile_block = "\n\n".join(
            [
                "Profile-Cited Directives (reviewer-renata):\nD body.",
                "Profile-Cited Tactics (reviewer-renata):\nT body.",
            ]
        )

        candidates = _collect_profile_block_candidates(profile_block)

        assert [c.section_id for c in candidates] == [
            "profile-cited-sections-0",
            "profile-cited-sections-1",
        ]
        assert candidates[0].header == "Profile-Cited Directives (reviewer-renata):"
        assert candidates[0].body == "D body."
        assert candidates[1].header == "Profile-Cited Tactics (reviewer-renata):"
        assert candidates[1].selector == "section:profile-citations"

    def test_single_body_less_chunk_yields_no_candidate(self) -> None:
        # The one shape that produces a body-less chunk from
        # _split_profile_blocks is a lone trailing-newline-only block (no
        # "\n\n" boundary present at all, so there is exactly one chunk
        # and its header/body split leaves body="").
        profile_block = "HeaderOnly\n"

        candidates = _collect_profile_block_candidates(profile_block)

        assert candidates == []


class TestSwapCandidatesIntoText:
    """Characterize ``_swap_candidates_into_text`` in isolation."""

    def test_no_candidates_returns_text_unchanged(self) -> None:
        text = "Preamble body."
        result_text, swapped = _swap_candidates_into_text(text, [], budget=5)
        assert result_text == text
        assert swapped == []

    def test_swaps_until_under_budget_longest_first(self) -> None:
        long_body = "L" * 1_000
        short_body = "S" * 50
        text = f"Preamble.\n\n{long_body}\n\n{short_body}"
        candidates = [
            RenderedSection(
                section_id="short",
                header="",
                body=short_body,
                selector="section:short",
                when_doing_clause="need to consult it",
            ),
            RenderedSection(
                section_id="long",
                header="",
                body=long_body,
                selector="section:long",
                when_doing_clause="need to consult it",
            ),
        ]
        # Pre-sorted longest-first, as the caller (_enforce_token_budget)
        # guarantees.
        candidates.sort(key=lambda sec: (-len(sec.body), sec.section_id))

        budget = len(text) - 500  # force at least one swap
        result_text, swapped = _swap_candidates_into_text(text, candidates, budget)

        assert long_body not in result_text
        assert swapped == ["long"]
        assert short_body in result_text

    def test_missing_body_is_skipped_defensively(self) -> None:
        text = "Preamble only, no matching body here."
        candidates = [
            RenderedSection(
                section_id="ghost",
                header="",
                body="this body is not present in text",
                selector="section:ghost",
                when_doing_clause="need to consult it",
            ),
        ]

        result_text, swapped = _swap_candidates_into_text(text, candidates, budget=1)

        assert result_text == text
        assert swapped == []


class TestEnforceTokenBudgetIntegration:
    """End-to-end characterization of ``_enforce_token_budget`` post-refactor."""

    def test_under_budget_returns_text_unchanged(self) -> None:
        text = "short text"
        result = _enforce_token_budget(
            text, action="implement", profile_block="", section_block="", budget=1_000
        )
        assert result == text

    def test_no_candidates_over_budget_returns_original_text(self) -> None:
        text = "x" * 100
        result = _enforce_token_budget(
            text, action="implement", profile_block="", section_block="", budget=10
        )
        assert result == text

    def test_swaps_section_block_headings_and_profile_kinds_together(self) -> None:
        section_block = "### Terminology Canon\n" + ("t" * 2_000)
        profile_block = "Profile-Cited Directives (x):\n" + ("d" * 2_000)
        text = f"Preamble.\n\n{section_block}\n\n{profile_block}"

        result = _enforce_token_budget(
            text,
            action="implement",
            profile_block=profile_block,
            section_block=section_block,
            budget=500,
        )

        assert "t" * 2_000 not in result
        assert "d" * 2_000 not in result
        assert "# Governance payload" in result
