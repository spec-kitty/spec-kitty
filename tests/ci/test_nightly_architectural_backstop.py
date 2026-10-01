"""Pin the nightly ``architectural-backstop`` job (#5510, FR-001, SC-003).

A green nightly must mean the full architectural battery ran. Before the
backstop existed the nightly only reached the battery through the
``-m "fast or unit"`` selection of one interpreter shard. The backstop runs the
plain per-PR battery base command (no partition plugin) on four workers.

This file proves the **command-parity** half of FR-001 statically: the
backstop's parsed selection (paths, ignores, marker) equals the per-PR battery
base read from ``ci-router.yml``. The other half (fast + S1 + S2 = base) is
proven by the partition proof elsewhere; neither half alone establishes the
whole set-equality.

Every property is evaluated by ONE production check, ``backstop_violations``;
the live test and every mutation test call that same function (Standing
Order #5: a mutation that never reaches the production check proves nothing).
"""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

import pytest

import tests.architectural._gate_coverage as gc
from tests.ci.test_nightly_timeout_headroom import _cap_violations

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOWS_DIR = _REPO_ROOT / ".github" / "workflows"
_NIGHTLY_PATH = _WORKFLOWS_DIR / "ci-nightly.yml"
_ROUTER_PATH = _WORKFLOWS_DIR / "ci-router.yml"

_BACKSTOP_JOB = "architectural-backstop"
_SUMMARY_JOB = "nightly-summary"
_BATTERY_PATH = "tests/architectural"
_SUITE_KEY = "architectural"
_BATTERY_PYTHON = "3.12"
_QUIET_FLAG_RE = re.compile(r"(?:^|\s)-q+(?:\s|$)")


def _run_text(job: dict[str, Any]) -> str:
    return "\n".join(step["run"] for step in job.get("steps", []) if isinstance(step.get("run"), str))


def _is_continue_on_error(value: object) -> bool:
    return value is True or str(value).strip().lower() == "true"


def _step_withs(job: dict[str, Any], action_prefix: str) -> list[dict[str, Any]]:
    return [step.get("with") or {} for step in job.get("steps", []) if str(step.get("uses", "")).startswith(action_prefix)]


def _selection_violations(router_gates: list[gc.Gate], nightly_gates: list[gc.Gate]) -> list[str]:
    backstops = [gate for gate in nightly_gates if gate.job == _BACKSTOP_JOB]
    if len(backstops) != 1:
        return [f"expected exactly one parsed gate for job {_BACKSTOP_JOB!r} in ci-nightly.yml, found {len(backstops)}"]
    backstop = backstops[0]
    family = [gate for gate in router_gates if gate.paths == [_BATTERY_PATH]]
    if not family:
        return [f"ci-router.yml carries no per-PR battery gate with paths == [{_BATTERY_PATH!r}]"]
    selections = {(frozenset(gate.ignores), gate.marker_expr) for gate in family}
    if len(selections) != 1:
        return [f"per-PR battery family disagrees on its selection: {sorted(gate.label() for gate in family)}"]
    ((base_ignores, base_marker),) = selections
    problems: list[str] = []
    if backstop.paths != [_BATTERY_PATH]:
        problems.append(f"backstop paths {backstop.paths} != [{_BATTERY_PATH!r}]")
    if backstop.marker_expr != base_marker:
        problems.append(f"backstop marker {backstop.marker_expr!r} != per-PR battery marker {base_marker!r}")
    if frozenset(backstop.ignores) != base_ignores:
        missing = sorted(base_ignores - frozenset(backstop.ignores))
        extra = sorted(frozenset(backstop.ignores) - base_ignores)
        problems.append(f"backstop deselects differ from per-PR battery base (missing {missing}, extra {extra})")
    return problems


def _command_violations(job: dict[str, Any]) -> list[str]:
    text = _run_text(job)
    problems: list[str] = []
    for forbidden in ("--battery-part", "battery_partition_plugin"):
        if forbidden in text:
            problems.append(f"backstop must be partition-free but its run text contains {forbidden!r}")
    for required in ("-n 4", "--dist loadfile"):
        if required not in text:
            problems.append(f"backstop run text must carry the literal {required!r}")
    if _QUIET_FLAG_RE.search(text):
        problems.append("backstop must not pass -q (xdist worker report lines are the FR-002 evidence)")
    return problems


def _wiring_violations(jobs: dict[str, Any], job: dict[str, Any]) -> list[str]:
    summary = jobs.get(_SUMMARY_JOB) or {}
    needs = summary.get("needs") or []
    problems: list[str] = []
    if _BACKSTOP_JOB not in needs:
        problems.append(f"{_BACKSTOP_JOB} is not in {_SUMMARY_JOB}.needs")
    if f"needs.{_BACKSTOP_JOB}.result" not in _run_text(summary):
        problems.append(f"{_SUMMARY_JOB} does not echo needs.{_BACKSTOP_JOB}.result")
    text = _run_text(job)
    if "nightly_escalation.py" not in text or f"--suite-key {_SUITE_KEY}" not in text:
        problems.append(f"no escalation step invokes nightly_escalation.py --suite-key {_SUITE_KEY}")
    if _is_continue_on_error(job.get("continue-on-error")) or any(_is_continue_on_error(step.get("continue-on-error")) for step in job.get("steps", [])):
        problems.append("backstop job or one of its steps is continue-on-error: true (the red would not reach the run conclusion)")
    return problems


def _environment_violations(job: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    checkouts = _step_withs(job, "actions/checkout@")
    if not checkouts or any(with_.get("fetch-depth") != 0 for with_ in checkouts):
        problems.append("checkout step must set fetch-depth: 0")
    setups = _step_withs(job, "astral-sh/setup-uv@")
    if not setups or any(str(with_.get("python-version")) != _BATTERY_PYTHON for with_ in setups):
        problems.append(f"setup-uv must pin python-version: '{_BATTERY_PYTHON}' (the per-PR battery interpreter)")
    return problems


def backstop_violations(nightly_jobs: dict[str, Any], router_gates: list[gc.Gate], nightly_gates: list[gc.Gate]) -> list[str]:
    """One message per broken backstop property; ``[]`` when all hold.

    The live test and every mutation test call this single function.
    """
    problems = _selection_violations(router_gates, nightly_gates)
    job = nightly_jobs.get(_BACKSTOP_JOB)
    if not isinstance(job, dict):
        return [*problems, f"ci-nightly.yml has no {_BACKSTOP_JOB!r} job"]
    return [*problems, *_command_violations(job), *_wiring_violations(nightly_jobs, job), *_environment_violations(job)]


def _live_router_gates() -> list[gc.Gate]:
    return gc.parse_workflow(_ROUTER_PATH)


def _violations_for_text(text: str, tmp_path: Path) -> list[str]:
    """Run the production check over a scratch copy of ci-nightly.yml."""
    scratch = tmp_path / "ci-nightly.yml"
    scratch.write_text(text, encoding="utf-8")
    jobs = gc.load_spliced_workflow(scratch)["jobs"]
    return backstop_violations(jobs, _live_router_gates(), gc.parse_workflow(scratch))


def _live_text() -> str:
    return _NIGHTLY_PATH.read_text(encoding="utf-8")


def test_live_nightly_backstop_has_no_violations() -> None:
    jobs = gc.load_spliced_workflow(_NIGHTLY_PATH)["jobs"]
    assert backstop_violations(jobs, _live_router_gates(), gc.parse_workflow(_NIGHTLY_PATH)) == []


def test_missing_backstop_job_is_reported() -> None:
    jobs = copy.deepcopy(gc.load_spliced_workflow(_NIGHTLY_PATH)["jobs"])
    jobs.pop(_BACKSTOP_JOB, None)
    nightly_gates = [gate for gate in gc.parse_workflow(_NIGHTLY_PATH) if gate.job != _BACKSTOP_JOB]
    problems = backstop_violations(jobs, _live_router_gates(), nightly_gates)
    assert any("expected exactly one parsed gate" in problem for problem in problems)
    assert any("has no 'architectural-backstop' job" in problem for problem in problems)


def test_dropping_the_job_from_summary_needs_is_reported() -> None:
    jobs = copy.deepcopy(gc.load_spliced_workflow(_NIGHTLY_PATH)["jobs"])
    jobs[_SUMMARY_JOB]["needs"] = [name for name in jobs[_SUMMARY_JOB]["needs"] if name != _BACKSTOP_JOB]
    problems = backstop_violations(jobs, _live_router_gates(), gc.parse_workflow(_NIGHTLY_PATH))
    assert f"{_BACKSTOP_JOB} is not in {_SUMMARY_JOB}.needs" in problems


def test_continue_on_error_is_reported() -> None:
    jobs = copy.deepcopy(gc.load_spliced_workflow(_NIGHTLY_PATH)["jobs"])
    jobs[_BACKSTOP_JOB]["continue-on-error"] = True
    problems = backstop_violations(jobs, _live_router_gates(), gc.parse_workflow(_NIGHTLY_PATH))
    assert any("continue-on-error" in problem for problem in problems)


def test_shallow_checkout_is_reported() -> None:
    jobs = copy.deepcopy(gc.load_spliced_workflow(_NIGHTLY_PATH)["jobs"])
    for with_ in _step_withs(jobs[_BACKSTOP_JOB], "actions/checkout@"):
        with_["fetch-depth"] = 1
    problems = backstop_violations(jobs, _live_router_gates(), gc.parse_workflow(_NIGHTLY_PATH))
    assert "checkout step must set fetch-depth: 0" in problems


def _backstop_block(text: str) -> tuple[int, int]:
    start = text.index(f"\n  {_BACKSTOP_JOB}:\n")
    end = text.index("\n  # ----", start + 1)
    return start, end


def _mutate_backstop(text: str, old: str, new: str) -> str:
    start, end = _backstop_block(text)
    block = text[start:end]
    assert old in block, f"mutation anchor {old!r} not present in the backstop job"
    return text[:start] + block.replace(old, new, 1) + text[end:]


def test_wrong_marker_is_reported(tmp_path: Path) -> None:
    mutated = _mutate_backstop(_live_text(), '-m "not performance and not stress and not timing"', '-m "fast or unit"')
    assert any("marker" in problem for problem in _violations_for_text(mutated, tmp_path))


def test_battery_part_flag_is_reported(tmp_path: Path) -> None:
    mutated = _mutate_backstop(_live_text(), "-n 4 --dist loadfile", "-n 4 --dist loadfile --battery-part 1/2")
    assert any("--battery-part" in problem for problem in _violations_for_text(mutated, tmp_path))


def test_worker_count_drift_is_reported(tmp_path: Path) -> None:
    mutated = _mutate_backstop(_live_text(), "-n 4", "-n auto")
    assert "backstop run text must carry the literal '-n 4'" in _violations_for_text(mutated, tmp_path)


def test_quiet_flag_is_reported(tmp_path: Path) -> None:
    mutated = _mutate_backstop(_live_text(), "-n 4 --dist loadfile", "-q -n 4 --dist loadfile")
    assert any("-q" in problem for problem in _violations_for_text(mutated, tmp_path))


def test_removed_deselect_is_reported(tmp_path: Path) -> None:
    mutated = _mutate_backstop(_live_text(), "--deselect tests/architectural/test_layer_rules.py", "")
    assert any("deselects differ" in problem for problem in _violations_for_text(mutated, tmp_path))


def test_backstop_timeout_headroom_holds() -> None:
    assert _cap_violations(_live_text(), lambda key: key == _BACKSTOP_JOB) == []
