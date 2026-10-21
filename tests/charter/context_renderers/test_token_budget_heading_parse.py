"""The ``### <heading>`` parse is linear and matches the former regex (Sonar S8786, #4696)."""

from __future__ import annotations

import random
import re
import time

import pytest

from charter.activation.context_renderers.token_budget import _heading_text

pytestmark = [pytest.mark.unit]

# The pattern the parser replaced, kept here as the behavioural oracle.
_FORMER_HEADING = re.compile(r"^###\s+(\S.*?)\s*$")

# Whitespace beyond the space covers the characters where ``str.isspace`` and
# the regex ``\s`` could plausibly disagree.
_ALPHABET = ("#", "###", " ", "\t", "\r", "\x0b", "\x1c", "\x85", " ", " ", "　", "a", "Z", ".")


def _former(line: str) -> str | None:
    match = _FORMER_HEADING.match(line)
    return match.group(1) if match else None


@pytest.mark.parametrize(
    "line",
    ["### Terminology Canon", "###   Spaced  heading   ", "###NoSpace", "###    ", "## Two", "### a", "", "###\tTab"],
)
def test_heading_text_matches_the_former_regex(line: str) -> None:
    assert _heading_text(line) == _former(line)


def test_heading_text_matches_the_former_regex_on_generated_lines() -> None:
    rng = random.Random(4696)
    for _ in range(5000):
        line = "".join(rng.choice(_ALPHABET) for _ in range(rng.randint(0, 10)))
        assert _heading_text(line) == _former(line), repr(line)


def test_heading_text_is_linear_on_a_long_inner_space_run() -> None:
    # The former regex took over a minute on this line; the parser takes microseconds.
    line = "### a" + " " * 150_000 + "x"
    started = time.perf_counter()
    assert _heading_text(line) == "a" + " " * 150_000 + "x"
    assert time.perf_counter() - started < 1.0
