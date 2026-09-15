"""Sonar remediation tests for ``token_budget.py`` (WP01).

Two independent findings are pinned here:

- ``S8786`` (BLOCKER) at :308 — ``_HEADING_LINE_RE`` originally read
  ``r"^###\\s+(.+?)\\s*$"``. Sonar flags this because ``.`` and ``\\s``
  overlap in what they can match, giving the engine more than one way to
  partition a run of trailing whitespace between the lazy ``.+?`` and the
  greedy ``\\s*`` (an ambiguous backtracking shape). Squad review (see
  ``post-tasks-squad-findings.md``, WP01 section) established the pattern
  is NOT catastrophic in practice — worst case is quadratic and the real
  input is always a single short heading line — so the acceptance proof
  here is **match-equivalence** against the old pattern (kept inline as the
  oracle), not a timing comparison, plus explicit coverage of the one
  documented divergence (``"###    "`` — marker + only whitespace).
- ``S3776`` at :365 (cognitive complexity 28) — ``_enforce_token_budget``
  was decomposed into ``_collect_section_block_candidates``,
  ``_collect_profile_block_candidates``, and ``_swap_candidates_into_text``.
  These tests characterize each helper directly and confirm the top-level
  function's observable behaviour is unchanged.
"""

from __future__ import annotations

import random
import re
import string

import pytest

from charter.activation.context_renderers.token_budget import (
    _HEADING_LINE_RE,
    RenderedSection,
    _collect_profile_block_candidates,
    _collect_section_block_candidates,
    _enforce_token_budget,
    _swap_candidates_into_text,
)

pytestmark = [pytest.mark.unit]

# ---------------------------------------------------------------------------
# S8786 — regex match-equivalence oracle
# ---------------------------------------------------------------------------

# The pre-fix pattern, kept verbatim as the oracle. This is the EXACT
# pattern Sonar flagged at token_budget.py:308 before this WP's rewrite —
# do not "clean it up"; its whole purpose here is to be the old behaviour.
_OLD_HEADING_LINE_RE = re.compile(r"^###\s+(.+?)\s*$")


def _old_and_new_agree(line: str) -> tuple[object, object]:
    """Return the (old, new) match results (``None`` or captured group 1)."""

    old_match = _OLD_HEADING_LINE_RE.match(line)
    new_match = _HEADING_LINE_RE.match(line)
    old_result = old_match.group(1) if old_match else None
    new_result = new_match.group(1) if new_match else None
    return old_result, new_result


def _is_documented_whitespace_tail_divergence(line: str) -> bool:
    """True when *line* hits the one documented S8786 divergence shape.

    The divergence only fires when the ENTIRE tail after the literal
    ``###`` prefix is whitespace and at least 2 characters long: the old
    pattern's ``\\s+`` needs to give back at least one trailing character
    for the lazy ``(.+?)`` to claim (so it needs >=2 whitespace chars total
    to have one left over after satisfying its own ``+`` minimum), and that
    leftover character is whatever the tail's last whitespace character is
    — it captures it. The new pattern's ``(\\S.*?)`` can never start on a
    whitespace character, so it fails outright and returns ``None``. A tail
    of exactly 1 whitespace character does NOT diverge: ``\\s+`` consumes
    it entirely (it cannot back off below its ``+`` minimum), leaving
    nothing for ``(.+?)`` to claim, so the OLD pattern also returns
    ``None`` there — both agree.
    """

    if not line.startswith("###"):
        return False
    tail = line[3:]
    return len(tail) >= 2 and tail.strip() == ""


class TestHeadingRegexMatchEquivalence:
    """Prove the S8786 rewrite is match-equivalent to the old pattern.

    NFR-003 is satisfied by removing the static ``.``/``\\s`` overlap, not
    by a timing improvement (the old pattern was already fast on the real
    single-short-line input — see the module docstring on
    ``_HEADING_LINE_RE``). The proof below is therefore behavioural.
    """

    @pytest.mark.parametrize(
        "line",
        [
            "### Terminology Canon",
            "###    Terminology Canon",  # extra leading whitespace after marker
            "### Terminology Canon   ",  # trailing whitespace
            "###Terminology Canon",  # no space after marker at all (still requires \\s+... see below)
            "### A",  # single-character heading
            "### Heading With   Internal   Spaces",
            "### Heading-With-Punctuation! (parens) [brackets] #hash",
            "###\tTerminology Canon",  # tab as the separator whitespace
            "### 中文标题",  # non-ASCII heading text
            "not a heading at all",
            "",
            "###",
        ],
    )
    def test_representative_inputs_agree(self, line: str) -> None:
        old_result, new_result = _old_and_new_agree(line)
        assert old_result == new_result, (line, old_result, new_result)

    def test_random_inputs_agree(self) -> None:
        """Fuzz a large, deterministic (seeded) corpus of near-heading lines.

        Covers the shapes most likely to expose a divergence: varying marker
        prefixes, whitespace runs of different lengths/kinds, and heading
        bodies with embedded whitespace/punctuation.
        """

        rng = random.Random(20260810)  # noqa: S311 - deterministic test fuzzing, not security-sensitive
        alphabet = string.ascii_letters + string.digits + " \t.,!()[]-_#"
        markers = ["###", "## ", "####", "###", " ###", "###x"]
        whitespace_runs = ["", " ", "  ", "\t", " \t ", "   "]

        checked = 0
        divergences_seen = 0
        for _ in range(500):
            marker = rng.choice(markers)
            sep = rng.choice(whitespace_runs)
            body_len = rng.randint(0, 12)
            body = "".join(rng.choice(alphabet) for _ in range(body_len))
            trailing = rng.choice(whitespace_runs)
            line = f"{marker}{sep}{body}{trailing}"

            old_result, new_result = _old_and_new_agree(line)
            if _is_documented_whitespace_tail_divergence(line):
                # The one documented divergence: old captures a trailing
                # whitespace char, new returns None.
                assert old_result is not None
                assert new_result is None
                divergences_seen += 1
            else:
                assert old_result == new_result, (line, old_result, new_result)
            checked += 1

        assert checked == 500
        # The whitespace-only-tail markers/runs above make this shape
        # reachable but not certain per draw — assert the fuzz actually
        # exercised the documented divergence at least once so this
        # coverage claim is not vacuous.
        assert divergences_seen > 0

    def test_whitespace_only_body_diverges_as_documented(self) -> None:
        """The one intentional divergence: marker + only whitespace.

        Old pattern captures a single space (the lazy ``.+?`` backtracks
        into the whitespace run). New pattern requires the capture to start
        with a non-space character, so it returns ``None`` entirely — an
        intentionally-dropped dead input, since no real ``### <heading>``
        line is whitespace-only.
        """

        line = "###    "

        old_match = _OLD_HEADING_LINE_RE.match(line)
        new_match = _HEADING_LINE_RE.match(line)

        assert old_match is not None
        assert old_match.group(1) == " "
        assert new_match is None

    @pytest.mark.parametrize("space_count", [2, 3, 8])
    def test_whitespace_only_body_diverges_across_lengths(self, space_count: int) -> None:
        line = "###" + (" " * space_count)

        old_match = _OLD_HEADING_LINE_RE.match(line)
        new_match = _HEADING_LINE_RE.match(line)

        assert old_match is not None
        assert new_match is None

    def test_single_whitespace_char_tail_does_not_diverge(self) -> None:
        """A tail of exactly 1 whitespace char is too short to diverge:
        old's ``\\s+`` cannot back off below its own ``+`` minimum to leave
        a character for ``(.+?)``, so it also returns ``None`` — both
        patterns agree here (see
        :func:`_is_documented_whitespace_tail_divergence`)."""

        line = "### "

        old_match = _OLD_HEADING_LINE_RE.match(line)
        new_match = _HEADING_LINE_RE.match(line)

        assert old_match is None
        assert new_match is None

    def test_new_pattern_still_matches_real_heading_after_divergent_input(self) -> None:
        """Sanity: the divergence is isolated to whitespace-only bodies; a
        real heading immediately after still matches identically."""

        real_heading = "### Regression Vigilance"
        old_result, new_result = _old_and_new_agree(real_heading)
        assert old_result == new_result == "Regression Vigilance"


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
