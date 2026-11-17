"""Guard: the acceptance driver's per-command ceilings stay named, recorded and bounded (#7689).

``CliProcessDriver`` gives every CLI invocation of the nightly acceptance suite a hard ceiling
(``DEFAULT_TIMEOUT``, two minutes): "a slower run is a defect, not a wait". #7689 tuned one
command's budget with evidence (``CONSOLIDATE_TIMEOUT``, a Windows-runner timeout of
``spec-kitty consolidate``), as the flakiness policy allows for a budget gate. This guard keeps that
tune from turning into a general wait:

* the shared default stays two minutes;
* every named ceiling is a constant above the default and at or below ``MAX_COMMAND_TIMEOUT``,
  which itself stays at or below five minutes;
* the set of commands with a named ceiling is exactly the one listed here, so adding one is a
  deliberate edit of this file;
* every named ceiling's comment cites its issue, and the flakiness ledger has a row for it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = [pytest.mark.fast]

_ROOT = Path(__file__).resolve().parents[2]
DRIVER = _ROOT / "acceptance-jvm" / "src" / "test" / "java" / "kitty" / "acceptance" / "driver" / "CliProcessDriver.java"
LEDGER = _ROOT / "docs" / "development" / "testing" / "testing-flakiness.md"

#: The commands allowed a named ceiling, with the issue that recorded the evidence for it.
EXPECTED_CEILINGS = {"consolidate": ("CONSOLIDATE_TIMEOUT", "#7689")}

DEFAULT_SECONDS = 120
#: The hard cap on ``MAX_COMMAND_TIMEOUT`` itself.
CAP_SECONDS = 300

_DURATION = re.compile(r"static final Duration (\w+) = Duration\.of(Seconds|Minutes)\((\d+)\);")
_MAP_ENTRY = re.compile(r'"([a-z-]+)",\s*(\w+)')
_COMMAND_MAP = re.compile(r"COMMAND_TIMEOUTS = Map\.of\(([^;]*)\);")
_UNIT_SECONDS = {"Seconds": 1, "Minutes": 60}


@dataclass(frozen=True)
class Ceilings:
    durations: dict[str, int]
    commands: dict[str, str]
    javadoc: dict[str, str]


def parse(source: str) -> Ceilings:
    """Read the driver's Duration constants, the named command map and each constant's Javadoc."""
    durations: dict[str, int] = {}
    javadoc: dict[str, str] = {}
    for match in _DURATION.finditer(source):
        name, unit, amount = match.groups()
        durations[name] = int(amount) * _UNIT_SECONDS[unit]
        before = source[: match.start()]
        start = before.rfind("/**")
        javadoc[name] = before[start:] if start != -1 and "*/" in before[start:] else ""
    map_match = _COMMAND_MAP.search(source)
    commands = dict(_MAP_ENTRY.findall(map_match.group(1))) if map_match else {}
    return Ceilings(durations=durations, commands=commands, javadoc=javadoc)


def violations(ceilings: Ceilings, ledger: str) -> list[str]:
    """Every way *ceilings* breaks the bounded-ceiling rule; empty when it holds."""
    found: list[str] = []
    default = ceilings.durations.get("DEFAULT_TIMEOUT")
    if default != DEFAULT_SECONDS:
        found.append(f"DEFAULT_TIMEOUT is {default}s, not {DEFAULT_SECONDS}s")
    maximum = ceilings.durations.get("MAX_COMMAND_TIMEOUT")
    if maximum is None or maximum > CAP_SECONDS:
        found.append(f"MAX_COMMAND_TIMEOUT is {maximum}s; it must exist and be at most {CAP_SECONDS}s")
    expected = {command: constant for command, (constant, _issue) in EXPECTED_CEILINGS.items()}
    if ceilings.commands != expected:
        found.append(f"named ceilings are {ceilings.commands}, expected exactly {expected}")
    for command, constant in ceilings.commands.items():
        seconds = ceilings.durations.get(constant)
        if seconds is None:
            found.append(f"{command}: {constant} is not a Duration constant")
            continue
        if not (DEFAULT_SECONDS < seconds <= (maximum or 0)):
            found.append(f"{command}: {constant} is {seconds}s, not above the default and at most MAX_COMMAND_TIMEOUT")
        issue = EXPECTED_CEILINGS.get(command, ("", ""))[1]
        if issue and issue not in ceilings.javadoc.get(constant, ""):
            found.append(f"{command}: the comment of {constant} does not cite {issue}")
        if issue and not any(issue in line and constant in line for line in ledger.splitlines() if line.startswith("|")):
            found.append(f"{command}: no flakiness-ledger row names both {issue} and {constant}")
    return found


def test_the_driver_ceilings_stay_named_recorded_and_bounded() -> None:
    ceilings = parse(DRIVER.read_text(encoding="utf-8"))
    assert ceilings.durations, "no Duration constants parsed from CliProcessDriver.java"
    assert violations(ceilings, LEDGER.read_text(encoding="utf-8")) == []


_GOOD = """
    /** Hard ceiling. */
    static final Duration DEFAULT_TIMEOUT = Duration.ofMinutes(2);
    /** Ceiling for consolidate (#7689). */
    static final Duration CONSOLIDATE_TIMEOUT = Duration.ofMinutes(4);
    /** Cap. */
    static final Duration MAX_COMMAND_TIMEOUT = Duration.ofMinutes(5);
    static final Map<String, Duration> COMMAND_TIMEOUTS = Map.of("consolidate", CONSOLIDATE_TIMEOUT);
"""
_LEDGER = "| driver ceiling `CONSOLIDATE_TIMEOUT` (#7689) | 1 | tuned |\n"


def test_the_planted_good_shape_passes() -> None:
    assert violations(parse(_GOOD), _LEDGER) == []


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ("CONSOLIDATE_TIMEOUT = Duration.ofMinutes(4)", "CONSOLIDATE_TIMEOUT = Duration.ofMinutes(6)", "not above the default and at most"),
        ("CONSOLIDATE_TIMEOUT = Duration.ofMinutes(4)", "CONSOLIDATE_TIMEOUT = Duration.ofMinutes(2)", "not above the default and at most"),
        ("MAX_COMMAND_TIMEOUT = Duration.ofMinutes(5)", "MAX_COMMAND_TIMEOUT = Duration.ofMinutes(10)", "at most 300s"),
        ("DEFAULT_TIMEOUT = Duration.ofMinutes(2)", "DEFAULT_TIMEOUT = Duration.ofMinutes(3)", "DEFAULT_TIMEOUT is 180s"),
        ('Map.of("consolidate", CONSOLIDATE_TIMEOUT)', 'Map.of("consolidate", CONSOLIDATE_TIMEOUT, "accept", CONSOLIDATE_TIMEOUT)', "expected exactly"),
        ("Ceiling for consolidate (#7689).", "Ceiling for consolidate.", "does not cite #7689"),
    ],
)
def test_a_planted_violation_is_reported(old: str, new: str, expected: str) -> None:
    planted = _GOOD.replace(old, new)
    assert planted != _GOOD
    assert any(expected in v for v in violations(parse(planted), _LEDGER))


def test_a_missing_ledger_row_is_reported() -> None:
    assert any("flakiness-ledger row" in v for v in violations(parse(_GOOD), "| other | 1 | x |\n"))
