"""Static budget and balance checks for the architectural battery (mission
ci-runtime-stabilisation-01M3TZH6, WP14 / T027; FR-004, NFR-001, NFR-002; research
D-06, D-29; contract ``contracts/battery-partition.md`` "Proof obligations").

Every check reads **committed numbers only** -- the registry's
``special_tiers.architectural`` entry and the seeded
``battery_file_durations`` table of ``.github/ci-shard-timings.json``. Nothing here
runs the battery or asserts wall-clock time (a runtime budget would mint a flake
class; the plugin reports overruns as warnings).

The rules are pure functions over data, so each mutation control feeds the same
function a synthetic registry/timings pair and demands a report. A control that
stays green while the rule is weakened would prove nothing.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

import pytest
import yaml

from scripts.ci import shard_select
from scripts.ci.battery_partition_plugin import BatterySpec, load_battery_spec, load_battery_timings

pytestmark = pytest.mark.fast

_REPO_ROOT: Final = Path(__file__).resolve().parents[2]
_REGISTRY: Final = _REPO_ROOT / ".github" / "ci-module-registry.yml"
_TIMINGS: Final = _REPO_ROOT / ".github" / "ci-shard-timings.json"
_PROVENANCE_TABLE: Final = "battery_capture_provenance"
_REQUIRED_PROVENANCE: Final = ("producer", "captured_at", "selection", "workers", "files_measured")
_MAX_LEG_SKEW: Final = 0.20  # same ceiling the module skew gate uses
_MAX_STALE_KEY_FRACTION: Final = 0.10
_MAX_UNTIMED_BASE_FRACTION: Final = 0.10
_BUDGET_FLOOR_SECONDS: Final = 10
_BUDGET_MULTIPLIER: Final = 1.5


# ---------------------------------------------------------------------------
# Pure rules (data in, problems out)
# ---------------------------------------------------------------------------
def roster_budget_problems(spec: BatterySpec, timings: Mapping[str, float]) -> list[str]:
    """Roster files that are untimed, over their budget, or whose budget exceeds the per-file cap."""
    problems = []
    for entry in spec.roster:
        if entry.path not in timings:
            problems.append(f"{entry.path}: no timing in the battery table -- seed it (capture_shard_timings --suite) or drop it from the roster")
            continue
        seconds = timings[entry.path]
        if seconds > entry.budget_seconds:
            problems.append(
                f"{entry.path}: timing {seconds:.2f}s > budget {entry.budget_seconds}s"
                " -- move it to the shards, or raise its budget within the cap after a recapture"
            )
        if entry.budget_seconds > spec.max_file_budget_seconds:
            problems.append(
                f"{entry.path}: budget {entry.budget_seconds}s > max_file_budget_seconds {spec.max_file_budget_seconds}s"
                " -- it does not qualify for the fast gate; move it to the shards"
            )
    return problems


def roster_total_problems(spec: BatterySpec, timings: Mapping[str, float]) -> list[str]:
    """The roster's summed measured seconds against ``max_total_measured_seconds`` (NFR-002 sizing)."""
    total = sum(timings.get(path, 0.0) for path in spec.roster_paths)
    if total > spec.max_total_measured_seconds:
        return [f"roster total {total:.1f} worker-s > max_total_measured_seconds {spec.max_total_measured_seconds} -- drop the lowest-priority rows"]
    return []


def leg_skew(loads: Mapping[str, float]) -> float:
    """``(max - min) / max`` over the numbered legs; 0.0 for an empty or all-zero set."""
    values = list(loads.values())
    peak = max(values, default=0.0)
    return (peak - min(values)) / peak if peak else 0.0


def leg_balance_problems(loads: Mapping[str, float]) -> list[str]:
    skew = leg_skew(loads)
    if skew > _MAX_LEG_SKEW:
        return [f"predicted leg loads {dict(loads)} skew {skew:.1%} > {_MAX_LEG_SKEW:.0%} (FR-004)"]
    return []


def stale_key_problems(timings: Mapping[str, float], base_files: Sequence[str]) -> list[str]:
    """Keys that name no base file; tolerated up to a tenth of the table so a mass rename cannot hide."""
    base = set(base_files)
    stale = sorted(key for key in timings if key not in base)
    if len(stale) > _MAX_STALE_KEY_FRACTION * len(timings):
        return [f"{len(stale)} of {len(timings)} timing keys name no base file (> {_MAX_STALE_KEY_FRACTION:.0%}): {stale[:5]} ... -- refresh the table"]
    return []


def untimed_base_problems(missing: Sequence[str], base_files: Sequence[str]) -> list[str]:
    """Base files with no timing; the selector fills them with the median and warns, so a few new
    test files must not red every PR (the #5189 drift precedent). Past a tenth of the base the
    prediction stops meaning anything and the table needs a recapture."""
    if len(missing) > _MAX_UNTIMED_BASE_FRACTION * len(base_files):
        share = f"{len(missing)} of {len(base_files)} base files have no timing (> {_MAX_UNTIMED_BASE_FRACTION:.0%})"
        return [f"{share}: {sorted(missing)[:5]} ... -- recapture the table"]
    return []


def budget_rule(seed_seconds: float) -> int:
    """The one budget rule: ``max(10, ceil(1.5 x seed))`` (research R1 section 4b)."""
    return max(_BUDGET_FLOOR_SECONDS, math.ceil(_BUDGET_MULTIPLIER * seed_seconds))


def budget_rule_problems(spec: BatterySpec, timings: Mapping[str, float]) -> list[str]:
    return [
        f"{entry.path}: budget {entry.budget_seconds}s != rule max(10, ceil(1.5 x {timings[entry.path]:.2f})) = {budget_rule(timings[entry.path])}s"
        for entry in spec.roster
        if entry.path in timings and entry.budget_seconds != budget_rule(timings[entry.path])
    ]


def provenance_problems(provenance: Mapping[str, Any] | None, spec: BatterySpec, timings: Mapping[str, float]) -> list[str]:
    if not provenance:
        return [f"{_PROVENANCE_TABLE}.{spec.timings_key} is missing"]
    problems = [f"provenance field {key!r} is missing" for key in _REQUIRED_PROVENANCE if key not in provenance]
    if provenance.get("selection") != spec.base.marker:
        problems.append(f"provenance selection {provenance.get('selection')!r} != registry base marker {spec.base.marker!r}")
    if provenance.get("files_measured") != len(timings):
        problems.append(f"provenance files_measured {provenance.get('files_measured')!r} != table length {len(timings)}")
    return problems


# ---------------------------------------------------------------------------
# Real data
# ---------------------------------------------------------------------------
def _spec() -> BatterySpec:
    return load_battery_spec(yaml.safe_load(_REGISTRY.read_text(encoding="utf-8")))


def _payload() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(_TIMINGS.read_text(encoding="utf-8"))
    return payload


def _timings(spec: BatterySpec) -> dict[str, float]:
    return load_battery_timings(_payload(), spec.timings_key)


def _base_files(spec: BatterySpec) -> tuple[str, ...]:
    return shard_select.enumerate_base_files(spec.base.paths, deselect=spec.base.deselect, root=_REPO_ROOT)


def test_battery_timings_present_with_provenance() -> None:
    spec = _spec()
    timings = _timings(spec)
    assert timings, f"battery_file_durations.{spec.timings_key} is empty or missing (seed it, D-29)"
    provenance = (_payload().get(_PROVENANCE_TABLE) or {}).get(spec.timings_key)
    assert provenance_problems(provenance, spec, timings) == []


def test_every_roster_file_is_timed_and_within_budget() -> None:
    spec = _spec()
    assert roster_budget_problems(spec, _timings(spec)) == []


def test_roster_budgets_follow_the_one_rule() -> None:
    spec = _spec()
    timings = _timings(spec)
    assert timings, "no battery timings to derive budgets from"
    assert budget_rule_problems(spec, timings) == []


def test_roster_total_within_cap() -> None:
    spec = _spec()
    timings = _timings(spec)
    assert timings, "no battery timings to total"
    assert roster_total_problems(spec, timings) == []


def test_predicted_legs_balanced(capsys: pytest.CaptureFixture[str]) -> None:
    spec = _spec()
    timings = _timings(spec)
    assert timings, "no battery timings to balance"
    partition = shard_select.battery_parts(_base_files(spec), spec.roster_paths, spec.shard_count, timings)
    fast_load = sum(timings[path] for path in spec.roster_paths)
    with capsys.disabled():
        print(f"\npredicted loads (worker-s): fast={fast_load:.1f} " + " ".join(f"{leg}={load:.1f}" for leg, load in partition.loads.items()))
    assert leg_balance_problems(partition.loads) == []
    assert untimed_base_problems(sorted(partition.resolution.missing), _base_files(spec)) == []


def test_timing_keys_are_base_files_or_reported() -> None:
    spec = _spec()
    timings = _timings(spec)
    assert timings, "no battery timings to check"
    assert stale_key_problems(timings, _base_files(spec)) == []


# ---------------------------------------------------------------------------
# Mutation controls: the same rules must bite on synthetic data
# ---------------------------------------------------------------------------
def _synthetic_spec(*, budget: int = 20, cap: int = 300, file_cap: int = 90, roster: Sequence[str] = ("tests/architectural/test_a.py",)) -> BatterySpec:
    registry = {
        "special_tiers": {
            "architectural": {
                "workers": 4,
                "base": {"paths": ["tests/architectural"], "marker": "not performance", "deselect": []},
                "fast_gate": {
                    "job": "architectural-fast",
                    "max_file_budget_seconds": file_cap,
                    "max_total_measured_seconds": cap,
                    "roster": [{"path": path, "budget_seconds": budget, "reason": "control"} for path in roster],
                },
                "shards": {"job": "architectural-heavy", "shard_count": 2, "granularity": "file", "timings_key": "architectural"},
            }
        }
    }
    return load_battery_spec(registry)


def test_control_roster_file_over_budget_is_reported() -> None:
    spec = _synthetic_spec(budget=20)
    assert roster_budget_problems(spec, {"tests/architectural/test_a.py": 20.01}) != []
    assert roster_budget_problems(spec, {"tests/architectural/test_a.py": 20.0}) == []


def test_control_untimed_roster_file_is_reported() -> None:
    assert any("no timing" in problem for problem in roster_budget_problems(_synthetic_spec(), {}))


def test_control_budget_above_the_file_cap_is_reported() -> None:
    spec = _synthetic_spec(budget=91, file_cap=90)
    assert any("max_file_budget_seconds" in problem for problem in roster_budget_problems(spec, {"tests/architectural/test_a.py": 1.0}))


def test_control_total_over_the_cap_is_reported() -> None:
    spec = _synthetic_spec(budget=90, cap=100, roster=("tests/architectural/test_a.py", "tests/architectural/test_b.py"))
    over = {"tests/architectural/test_a.py": 60.0, "tests/architectural/test_b.py": 40.5}
    under = {"tests/architectural/test_a.py": 60.0, "tests/architectural/test_b.py": 40.0}
    assert roster_total_problems(spec, over) != []
    assert roster_total_problems(spec, under) == []


def test_control_unbalanced_legs_are_reported() -> None:
    assert leg_balance_problems({"1/2": 300.0, "2/2": 100.0}) != []
    assert leg_balance_problems({"1/2": 100.0, "2/2": 80.0}) == []
    assert leg_balance_problems({"1/2": 100.0, "2/2": 79.0}) != []


def test_control_unbalanced_partition_is_detected_through_battery_parts() -> None:
    files = ["a.py", "b.py", "c.py"]
    partition = shard_select.battery_parts(files, [], 2, {"a.py": 300.0, "b.py": 50.0, "c.py": 50.0})
    assert leg_balance_problems(partition.loads) != []


def test_control_mass_rename_hides_no_stale_keys() -> None:
    timings = {f"tests/architectural/test_{i}.py": 1.0 for i in range(10)}
    base = [f"tests/architectural/test_{i}.py" for i in range(9)]
    assert stale_key_problems(timings, base) == []
    assert stale_key_problems(timings, base[:8]) != []


def test_control_untimed_base_files_tolerated_up_to_a_tenth() -> None:
    base = [f"tests/architectural/test_{i}.py" for i in range(20)]
    assert untimed_base_problems(base[:2], base) == []
    assert untimed_base_problems(base[:3], base) != []


def test_control_budget_rule_is_floor_then_one_and_a_half_times() -> None:
    assert budget_rule(0.0) == 10
    assert budget_rule(6.0) == 10
    assert budget_rule(6.7) == 11
    assert budget_rule(58.1) == 88
    spec = _synthetic_spec(budget=10)
    assert budget_rule_problems(spec, {"tests/architectural/test_a.py": 40.0}) != []


def test_control_incomplete_provenance_is_reported() -> None:
    spec = _synthetic_spec()
    timings = {"tests/architectural/test_a.py": 1.0}
    complete = {"producer": "x", "captured_at": "t", "selection": "not performance", "workers": 2, "files_measured": 1}
    assert provenance_problems(complete, spec, timings) == []
    assert provenance_problems(None, spec, timings) != []
    assert provenance_problems({**complete, "files_measured": 2}, spec, timings) != []
    assert provenance_problems({**complete, "selection": "other"}, spec, timings) != []
    assert provenance_problems({k: v for k, v in complete.items() if k != "workers"}, spec, timings) != []
