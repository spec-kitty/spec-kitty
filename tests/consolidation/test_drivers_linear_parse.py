"""The merge drivers' section-id and issue-ref parses are linear and match the former regexes.

Sonar S8786, #4696: both former patterns backtracked quadratically.
"""

from __future__ import annotations

import random
import re
import time

import pytest

from specify_cli.consolidation.drivers import _canonicalize_issue_ref, _trace_section_id

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# The patterns the parsers replaced, kept here as behavioural oracles.
_FORMER_SECTION_ID = re.compile(r"^<!--\s*section:(.*?)\s*-->\s*$")
_FORMER_ISSUE_REF_DIGITS = re.compile(r"(\d+)\s*$")

_SECTION_PIECES = ("<!--", "section:", "-->", "->", "-", ">", " ", "\t", " ", "id", "a b", ":")
_REF_PIECES = ("#", "GH-", "gh#", "1", "726", "١٢", "²", " ", "\t", " ", "x", "-")


def _former_section_id(line: str) -> str | None:
    match = _FORMER_SECTION_ID.match(line)
    return match.group(1) if match else None


def _former_canonical_ref(raw_ref: str) -> str:
    match = _FORMER_ISSUE_REF_DIGITS.search(raw_ref.strip())
    return f"#{match.group(1)}" if match else raw_ref.strip()


@pytest.mark.parametrize(
    "line",
    [
        "<!-- section:intro -->",
        "<!--section:intro-->",
        "<!--   section:  spaced id   -->   ",
        "<!-- section:a --> -->",
        "<!-- section:--->",
        "<!-- section:-->",
        "<!-- section: -->",
        "<!-- section:intro",
        "<!-- sections:intro -->",
        "## heading",
        "",
    ],
)
def test_trace_section_id_matches_the_former_regex(line: str) -> None:
    assert _trace_section_id(line) == _former_section_id(line)


def test_trace_section_id_matches_the_former_regex_on_generated_lines() -> None:
    rng = random.Random(4696)
    for _ in range(5000):
        line = "".join(rng.choice(_SECTION_PIECES) for _ in range(rng.randint(0, 9)))
        assert _trace_section_id(line) == _former_section_id(line), repr(line)


@pytest.mark.parametrize("raw_ref", ["#1726", "GH-1726", " 1726 ", "gh#12 34", "no-digits", "", "1x", "١٢"])
def test_canonicalize_issue_ref_matches_the_former_regex(raw_ref: str) -> None:
    assert _canonicalize_issue_ref(raw_ref) == _former_canonical_ref(raw_ref)


def test_canonicalize_issue_ref_matches_the_former_regex_on_generated_refs() -> None:
    rng = random.Random(4696)
    for _ in range(5000):
        raw_ref = "".join(rng.choice(_REF_PIECES) for _ in range(rng.randint(0, 8)))
        assert _canonicalize_issue_ref(raw_ref) == _former_canonical_ref(raw_ref), repr(raw_ref)


def test_trace_section_id_is_linear_on_a_long_space_run() -> None:
    # The former regex took about 10 s on this line; the parser takes microseconds.
    line = "<!-- section:" + " " * 100_000 + "x"
    started = time.perf_counter()
    assert _trace_section_id(line) is None
    assert time.perf_counter() - started < 1.0


def test_canonicalize_issue_ref_is_linear_on_a_long_digit_run() -> None:
    # The former regex took over 10 s on this ref; the parser takes milliseconds.
    raw_ref = "1" * 40_000 + "x"
    started = time.perf_counter()
    assert _canonicalize_issue_ref(raw_ref) == raw_ref
    assert time.perf_counter() - started < 1.0
