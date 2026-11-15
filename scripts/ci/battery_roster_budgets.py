"""The architectural battery's roster budget rule, and its regeneration (#7115).

``.github/ci-module-registry.yml`` -> ``special_tiers.architectural.fast_gate.roster`` gives
every always-on battery file a ``budget_seconds``. The rule is :func:`budget_rule`:
``max(10, ceil(1.5 x seed))`` over the file's committed seconds in
``battery_file_durations.architectural``. ``tests/ci/test_battery_roster_budgets.py``
checks it, and the scheduled recapture keeps it true: whenever it refreshes the battery
table it re-derives every budget with :func:`rerule_registry`, so a refresh never leaves
the roster off its own rule. What stays a human decision is the roster itself: a file
whose rule budget exceeds ``max_file_budget_seconds``, or a roster total above
``max_total_measured_seconds``, is still reported red by the test and needs rows moved.

The registry is edited line by line, never re-serialised, so its comments and layout
survive; :func:`rerule_registry` re-parses the result and refuses an edit that changed
anything but the budgets it meant to change.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from scripts.ci.battery_partition_plugin import load_battery_spec, load_battery_timings

__all__ = ["BUDGET_FLOOR_SECONDS", "BUDGET_MULTIPLIER", "RosterRerule", "budget_rule", "has_roster", "rerule_files", "rerule_registry"]

BUDGET_FLOOR_SECONDS = 10
BUDGET_MULTIPLIER = 1.5

#: One roster row as the registry writes it: ``- {path: <file>, budget_seconds: <n>, reason: ...}``.
_ROW = re.compile(r"^(?P<head>\s*- \{path: )(?P<path>[^,\s]+)(?P<mid>, budget_seconds: )(?P<budget>\d+)(?P<tail>,.*)$")


def budget_rule(seed_seconds: float) -> int:
    """The one budget rule: ``max(10, ceil(1.5 x seed))`` (research R1 section 4b)."""
    return max(BUDGET_FLOOR_SECONDS, math.ceil(BUDGET_MULTIPLIER * seed_seconds))


@dataclass(frozen=True)
class RosterRerule:
    """The re-derived registry text, and ``{path: (old, new)}`` for every budget it changed."""

    text: str
    changed: Mapping[str, tuple[int, int]] = field(default_factory=dict)


def _roster(document: Any) -> list[Any]:
    roster: list[Any] = document["special_tiers"]["architectural"]["fast_gate"]["roster"]
    return roster


def _roster_budgets(text: str) -> dict[str, int]:
    return {str(row["path"]): int(row["budget_seconds"]) for row in _roster(yaml.safe_load(text))}


def has_roster(text: str) -> bool:
    """True when *text* declares the architectural battery's fast roster."""
    document = yaml.safe_load(text)
    try:
        _roster(document)
    except (KeyError, TypeError):
        return False
    return True


def rerule_registry(text: str, timings: Mapping[str, float]) -> RosterRerule:
    """*text* with every timed roster row's ``budget_seconds`` set by :func:`budget_rule`.

    A row whose file has no timing keeps its budget (the roster test reports it as untimed).
    Raises :class:`ValueError` when a roster row is not in the one-line form this edit
    understands, or when the edited text does not parse to exactly the intended budgets.
    """
    before = _roster_budgets(text)
    changed: dict[str, tuple[int, int]] = {}
    seen: set[str] = set()
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        match = _ROW.match(line.rstrip("\n"))
        if match is None or match["path"] not in before:
            continue
        path = match["path"]
        seen.add(path)
        if path not in timings:
            continue
        new = budget_rule(timings[path])
        old = int(match["budget"])
        if new != old:
            changed[path] = (old, new)
            newline = "\n" if line.endswith("\n") else ""
            lines[index] = f"{match['head']}{path}{match['mid']}{new}{match['tail']}{newline}"
    missing = sorted(set(before) - seen)
    if missing:
        msg = f"roster rows not in the one-line form `- {{path: ..., budget_seconds: N, reason: ...}}`: {missing}"
        raise ValueError(msg)
    edited = "".join(lines)
    expected = yaml.safe_load(text)
    for row in _roster(expected):
        if str(row["path"]) in changed:
            row["budget_seconds"] = changed[str(row["path"])][1]
    if yaml.safe_load(edited) != expected:
        msg = "the budget edit did not parse back to the original registry with only the intended budgets changed"
        raise ValueError(msg)
    return RosterRerule(edited, changed)


def rerule_files(registry_path: Path, timings_path: Path) -> Mapping[str, tuple[int, int]]:
    """Re-derive the roster budgets in *registry_path* from the battery table in *timings_path*.

    Writes the registry only when a budget changed; returns ``{path: (old, new)}``, empty
    when the registry declares no architectural roster at all. Raises
    :class:`ValueError` (nothing written) when either file cannot be read as expected.
    """
    text = registry_path.read_text(encoding="utf-8")
    if not has_roster(text):
        return {}
    spec = load_battery_spec(yaml.safe_load(text))
    payload = json.loads(timings_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"{timings_path} did not parse to a mapping"
        raise ValueError(msg)
    rerule = rerule_registry(text, load_battery_timings(payload, spec.timings_key))
    if rerule.changed:
        registry_path.write_text(rerule.text, encoding="utf-8")
    return rerule.changed
