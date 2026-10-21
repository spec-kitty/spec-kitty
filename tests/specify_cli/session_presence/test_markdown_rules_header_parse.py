"""The session-presence header parse is linear and matches the former regex (Sonar S8786, #4696)."""

from __future__ import annotations

import random
import re
import time

import pytest

from specify_cli.session_presence.writers.markdown_rules import _parse_header

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# The pattern the parser replaced, kept here as the behavioural oracle.
_FORMER_HEADER = re.compile(
    r"^\*\*Spec Kitty v([^\n]+?)\*\* — project: ([^\n]+?) \((healthy|upgrade-available|migration-required)\)$",
    re.MULTILINE,
)

_PIECES = (
    "**Spec Kitty v",
    "** — project: ",
    " (healthy)",
    " (upgrade-available)",
    " (migration-required)",
    "1.2.3",
    "demo",
    "*",
    " ",
    "\n",
    "\r",
    "(",
    ")",
    "—",
    "x",
)


def _former(text: str) -> tuple[str, ...] | None:
    match = _FORMER_HEADER.search(text)
    return match.groups() if match else None


@pytest.mark.parametrize(
    "text",
    [
        "**Spec Kitty v3.2.0** — project: example (healthy)",
        "intro\n**Spec Kitty v4.0.0rc8** — project: my-app (upgrade-available)\nmore",
        "**Spec Kitty v1** — project: a** — project: b (migration-required)",
        "**Spec Kitty v** — project: x (healthy)",
        "**Spec Kitty v1** — project:  (healthy)",
        "**Spec Kitty v1** — project: x (healthy) ",
        "**Spec Kitty v1** — project: x (unknown)",
        "**Spec Kitty v1** — project: x (healthy)\n**Spec Kitty v2** — project: y (healthy)",
        "",
    ],
)
def test_parse_header_matches_the_former_regex(text: str) -> None:
    assert _parse_header(text) == _former(text)


def test_parse_header_matches_the_former_regex_on_generated_text() -> None:
    rng = random.Random(4696)
    for _ in range(3000):
        text = "".join(rng.choice(_PIECES) for _ in range(rng.randint(0, 12)))
        assert _parse_header(text) == _former(text), text


def test_parse_header_is_linear_on_a_repeated_separator() -> None:
    # The former regex took over 20 s on this line; the parser takes milliseconds.
    text = "**Spec Kitty v" + "** — project: " * 20_000 + "x"
    started = time.perf_counter()
    assert _parse_header(text) is None
    assert time.perf_counter() - started < 1.0
