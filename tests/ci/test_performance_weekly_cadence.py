"""The `performance` suite runs weekly, every other nightly job daily (#7704).

Operator ruling on #7704: the performance tier moves from nightly to weekly,
on-demand runs stay available through ``workflow_dispatch``, and the red ->
P0 escalation keeps working on the weekly run. ``ci-nightly.yml`` carries two
cron entries that together fire once a day (Monday-Saturday, and Sunday); the
`performance` job's ``if:`` admits a scheduled run only for the Sunday entry.

These tests read the real workflow and pin that shape, so a cron edit that
silently drops the weekly run, doubles a day's nightly, or leaves the job on
every nightly goes red on the pull request that makes it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = [pytest.mark.fast]

_WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci-nightly.yml"
_WEEKLY_CRON = "17 3 * * 0"
_CADENCE_CONDITION = f"(github.event_name != 'schedule' || github.event.schedule == '{_WEEKLY_CRON}')"


def _workflow() -> dict[Any, Any]:
    data = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _triggers(data: dict[Any, Any]) -> dict[str, Any]:
    # PyYAML reads the bare key `on` as the boolean True.
    on = data.get("on", data.get(True))
    assert isinstance(on, dict), "ci-nightly.yml must declare its triggers as a mapping"
    return on


def _crons(data: dict[Any, Any]) -> list[str]:
    return [entry["cron"] for entry in _triggers(data)["schedule"]]


def _weekdays(cron: str) -> set[int]:
    """Days of week (0 = Sunday) a 5-field cron with `*` day-of-month and month fires on."""
    minute, hour, day_of_month, month, day_of_week = cron.split()
    assert (day_of_month, month) == ("*", "*"), f"unmodeled cron {cron!r}"
    if day_of_week == "*":
        return set(range(7))
    days: set[int] = set()
    for part in day_of_week.split(","):
        if "-" in part:
            low, high = (int(bound) for bound in part.split("-"))
            days.update(range(low, high + 1))
        else:
            days.add(int(part))
    return days


def test_the_schedule_fires_exactly_once_a_day_and_includes_the_weekly_entry() -> None:
    crons = _crons(_workflow())
    assert _WEEKLY_CRON in crons, f"the weekly performance cron {_WEEKLY_CRON!r} is missing from {crons}"
    fired: list[int] = []
    for cron in crons:
        fired.extend(_weekdays(cron))
    assert sorted(fired) == list(range(7)), f"the nightly must fire once on every day of the week, got {sorted(fired)} from {crons}"


def test_the_performance_job_runs_on_the_weekly_cron_and_on_dispatch_only() -> None:
    condition = " ".join(str(_workflow()["jobs"]["performance"]["if"]).split())
    assert condition.endswith(f"&& {_CADENCE_CONDITION}"), condition


@pytest.mark.parametrize(
    ("event_name", "schedule", "runs"),
    [
        ("schedule", _WEEKLY_CRON, True),
        ("schedule", "17 3 * * 1-6", False),
        ("workflow_dispatch", None, True),
    ],
)
def test_the_cadence_condition_admits_the_expected_runs(event_name: str, schedule: str | None, runs: bool) -> None:
    """Evaluate the cadence conjunct the way Actions would for each event."""
    match = re.fullmatch(r"\(github\.event_name != '(\w+)' \|\| github\.event\.schedule == '([^']+)'\)", _CADENCE_CONDITION)
    assert match
    admitted = event_name != match.group(1) or schedule == match.group(2)
    assert admitted is runs


def test_no_other_job_is_gated_on_the_weekly_cron() -> None:
    gated = [name for name, job in _workflow()["jobs"].items() if name != "performance" and "github.event.schedule" in str(job.get("if", ""))]
    assert gated == [], f"only the performance job follows the weekly cadence; also gated: {gated}"


def test_the_performance_job_still_escalates_its_red_to_a_p0() -> None:
    steps = _workflow()["jobs"]["performance"]["steps"]
    commands = [str(step.get("run", "")) for step in steps]
    assert any("nightly_escalation.py --suite-key performance" in command for command in commands)
