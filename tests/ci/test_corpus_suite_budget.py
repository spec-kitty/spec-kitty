"""The advisory corpus job's own budget, and what a budget expiry says (#7206, #4437).

``packs.yml`` runs the ``-m "corpus and not windows_ci"`` selection as the advisory job
``built-in-corpus-suite``. Its measured duration is 20.3 min at p95 against 1 624 items, and almost
all of a PR run is fixed cost: the whole ``tests/`` tree is collected in every worker, and the
content-addressed wall-clock policy scan has no cache on PR runs by design. Neither is corpus work,
and neither can be removed from this lane without breaking a guard the lane depends on
(``tests/ci/test_corpus_blocking_home.py`` requires tree-wide corpus reach; ``tests/ci/
test_contracts_routing.py`` requires exactly one pytest invocation), so the cap is derived from the
measurement instead — by the repository's own #5378 headroom rule, enforced in
``tests/ci/test_nightly_timeout_headroom.py``, whose :func:`headroom_record` is this module's only
reader of that record.

This module holds the rest of the contract, and nothing about what the job selects:

* the suite step carries its own ``timeout-minutes``, strictly below the job cap, so a killed suite
  still reaches the notice step (a *job-cap* expiry runs no further steps, which is why #7206's
  cancellations ended at ``The operation was canceled.`` with no explanation);
* that notice says the run did not finish, that the lane is advisory, and that this is **not a test
  failure** — #4437's rule that a cancellation must never masquerade as either a failure or a pass;
* the recorded measured maximum stays within the issue's acceptance ratio (p95 ≤ 75 % of the cap; the
  record is the suite step's measured maximum, a lower bound on the step time; the job's p95 is somewhat
  higher, and the recorded value is checked as the closest measured proxy for it).

Every property is evaluated by ONE production function, :func:`budget_violations`, and each assertion
has a mutation control that calls that same function on a broken copy — a control that never reaches
the production check proves nothing.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.ci.test_nightly_timeout_headroom import (
    _PACKS_CORPUS_JOB,
    _is_packs_corpus_target,
    headroom_record,
)

pytestmark = pytest.mark.fast

_PACKS_PATH = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "packs.yml"
_SUITE_MARKER = '-m "corpus and not windows_ci"'
_NOTICE_STEP_NAME = "Advisory corpus failure notice"
#: The issue's acceptance rule: p95 duration is at most 75 % of ``timeout-minutes``.
_ACCEPTANCE_RATIO = 0.75
#: Below this the step budget would start killing healthy runs (measured suite p95 20.3 min,
#: recorded worst case 19:55).
_MIN_STEP_BUDGET_MINUTES = 20
#: The words that make a killed run legible instead of a bare cancellation (#4437).
_NOTICE_PHRASES = ("INCOMPLETE", "advisory", "not a test failure")


def _load_packs() -> dict[str, Any]:
    data = yaml.safe_load(_PACKS_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict), "packs.yml must parse to a mapping"
    return data


def _job(packs: dict[str, Any], name: str = _PACKS_CORPUS_JOB) -> dict[str, Any]:
    jobs = packs.get("jobs")
    assert isinstance(jobs, dict), "packs.yml must carry a `jobs:` mapping"
    assert name in jobs, f"packs.yml has no `{name}` job"
    return copy.deepcopy(jobs[name])


def _steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    steps = job.get("steps")
    assert isinstance(steps, list) and steps, "the advisory corpus job must carry steps"
    return steps


def _suite_step(job: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """The one step that runs the corpus selection, with its index."""
    matches = [(index, step) for index, step in enumerate(_steps(job)) if _SUITE_MARKER in str(step.get("run", ""))]
    assert len(matches) == 1, f"expected exactly one step running the corpus selection, found {len(matches)}"
    return matches[0]


def _minutes(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _ratio_violation(cap_minutes: int, max_suite: str) -> str | None:
    """Return a message when the recorded maximum exceeds the acceptance ratio of *cap_minutes*."""
    minutes, seconds = max_suite.split(":")
    recorded = int(minutes) + int(seconds) / 60
    if recorded > cap_minutes * _ACCEPTANCE_RATIO:
        return (
            f"recorded max-suite {max_suite} is {recorded / cap_minutes:.0%} of the {cap_minutes}-minute cap, "
            f"over the {_ACCEPTANCE_RATIO:.0%} acceptance rule: raise timeout-minutes or re-measure"
        )
    return None


def budget_violations(packs: dict[str, Any]) -> list[str]:
    """Every way the advisory corpus job's budget contract is broken, as named messages."""
    problems: list[str] = []
    try:
        job = _job(packs)
    except AssertionError as exc:
        return [str(exc)]

    cap = _minutes(job.get("timeout-minutes"))
    if cap is None:
        problems.append(f"{_PACKS_CORPUS_JOB}: no job-level `timeout-minutes:` found")

    steps = _steps(job)
    try:
        suite_index, suite_step = _suite_step(job)
    except AssertionError as exc:
        problems.append(str(exc))
        suite_index, suite_step = -1, {}

    step_budget = _minutes(suite_step.get("timeout-minutes"))
    if step_budget is None:
        problems.append("the corpus suite step has no step-level `timeout-minutes`: a job-cap expiry skips the notice step")
    elif cap is not None:
        if step_budget >= cap:
            problems.append(f"the suite step budget ({step_budget} min) must be strictly below the job cap ({cap} min), or it never fires first")
        if step_budget < _MIN_STEP_BUDGET_MINUTES:
            problems.append(
                f"the suite step budget ({step_budget} min) is below the measured suite p95 "
                f"(~20.3 min; floor {_MIN_STEP_BUDGET_MINUTES} min) and would kill healthy runs"
            )
    if suite_step.get("continue-on-error") is not None:
        problems.append("the suite step must not carry `continue-on-error`: it would swallow the failure the notice reports")

    notices = [(index, step) for index, step in enumerate(steps) if step.get("name") == _NOTICE_STEP_NAME]
    if not notices:
        problems.append(f"no `{_NOTICE_STEP_NAME}` step: a killed run would end at a bare cancellation")
    else:
        notice_index, notice = notices[0]
        if "failure()" not in str(notice.get("if", "")):
            problems.append(f"`{_NOTICE_STEP_NAME}` must be gated on `failure()` so a timed-out step reaches it")
        if notice_index < suite_index:
            problems.append(f"`{_NOTICE_STEP_NAME}` must run after the suite step")
        text = str(notice.get("run", ""))
        missing = [phrase for phrase in _NOTICE_PHRASES if phrase not in text]
        if missing:
            problems.append(f"`{_NOTICE_STEP_NAME}` does not say what happened; missing wording: {missing}")
    return problems


def recorded_ratio_violation(packs_text: str, packs: dict[str, Any]) -> str | None:
    """The acceptance-ratio check over the workflow's own headroom record."""
    job = _job(packs)
    cap = _minutes(job.get("timeout-minutes"))
    if cap is None:
        return f"{_PACKS_CORPUS_JOB}: no job-level `timeout-minutes:` found"
    recorded_cap, max_suite = headroom_record(packs_text, _PACKS_CORPUS_JOB, is_target=_is_packs_corpus_target)
    if recorded_cap != cap:
        return f"the headroom record says {recorded_cap} min but the job cap is {cap} min"
    return _ratio_violation(cap, max_suite)


# ---------------------------------------------------------------------------
# Live: the job carries a defensible budget and a legible expiry
# ---------------------------------------------------------------------------
def test_the_advisory_corpus_job_meets_its_budget_contract() -> None:
    packs = _load_packs()
    job = _job(packs)

    # Non-vacuity: the job really is the advisory corpus lane, so the checks below
    # are about the thing the issue names.
    assert job.get("continue-on-error") is True, "the corpus lane is advisory (job-level `continue-on-error`)"
    _suite_step(job)

    assert budget_violations(packs) == []


def test_the_recorded_maximum_is_within_the_acceptance_ratio() -> None:
    """#7206 acceptance: p95 ≤ 75 % of the cap, checked against the recorded maximum."""
    text = _PACKS_PATH.read_text(encoding="utf-8")
    packs = _load_packs()
    _, max_suite = headroom_record(text, _PACKS_CORPUS_JOB, is_target=_is_packs_corpus_target)
    assert max_suite == "19:55", f"re-measure before changing the record; it says {max_suite}"
    assert recorded_ratio_violation(text, packs) is None


def test_the_ratio_check_can_fail() -> None:
    """Mutation control for the acceptance rule: a slower record against the same cap is refused."""
    assert _ratio_violation(31, "19:55") is None
    message = _ratio_violation(31, "24:00")
    assert message is not None and "over the 75% acceptance rule" in message
    assert _ratio_violation(20, "19:55") is not None, "the retired 20-minute cap fails the rule, as the issue reports"


def test_a_record_disagreeing_with_the_cap_is_refused() -> None:
    packs = _load_packs()
    text = _PACKS_PATH.read_text(encoding="utf-8")
    job = _job(packs)
    job["timeout-minutes"] = 99
    packs["jobs"][_PACKS_CORPUS_JOB] = job
    message = recorded_ratio_violation(text, packs)
    assert message is not None and "the headroom record says 31 min but the job cap is 99 min" in message


# ---------------------------------------------------------------------------
# Mutation controls: every property above is load-bearing
# ---------------------------------------------------------------------------
def _mutated(mutate: Callable[[dict[str, Any], list[dict[str, Any]]], None]) -> dict[str, Any]:
    packs = _load_packs()
    job = _job(packs)
    mutate(job, _steps(job))
    packs["jobs"][_PACKS_CORPUS_JOB] = job
    return packs


def _has(problems: list[str], needle: str) -> bool:
    return any(needle in problem for problem in problems)


def test_a_missing_step_budget_is_reported() -> None:
    def mutate(job: dict[str, Any], steps: list[dict[str, Any]]) -> None:
        _, suite = _suite_step(job)
        suite.pop("timeout-minutes", None)

    assert _has(budget_violations(_mutated(mutate)), "no step-level `timeout-minutes`")


def test_a_step_budget_at_or_above_the_job_cap_is_reported() -> None:
    def mutate(job: dict[str, Any], steps: list[dict[str, Any]]) -> None:
        _, suite = _suite_step(job)
        suite["timeout-minutes"] = job["timeout-minutes"]

    assert _has(budget_violations(_mutated(mutate)), "strictly below the job cap")

    def above(job: dict[str, Any], steps: list[dict[str, Any]]) -> None:
        _, suite = _suite_step(job)
        suite["timeout-minutes"] = int(job["timeout-minutes"]) + 5

    assert _has(budget_violations(_mutated(above)), "strictly below the job cap")


def test_a_step_budget_below_the_measured_p95_is_reported() -> None:
    def mutate(job: dict[str, Any], steps: list[dict[str, Any]]) -> None:
        _, suite = _suite_step(job)
        suite["timeout-minutes"] = 12

    assert _has(budget_violations(_mutated(mutate)), "below the measured suite p95")


def test_a_swallowed_suite_failure_is_reported() -> None:
    def mutate(job: dict[str, Any], steps: list[dict[str, Any]]) -> None:
        _, suite = _suite_step(job)
        suite["continue-on-error"] = True

    assert _has(budget_violations(_mutated(mutate)), "must not carry `continue-on-error`")


def test_a_missing_notice_is_reported() -> None:
    def mutate(job: dict[str, Any], steps: list[dict[str, Any]]) -> None:
        job["steps"] = [step for step in steps if step.get("name") != _NOTICE_STEP_NAME]

    assert _has(budget_violations(_mutated(mutate)), "a killed run would end at a bare cancellation")


def test_a_notice_that_cannot_fire_on_a_timeout_is_reported() -> None:
    def mutate(job: dict[str, Any], steps: list[dict[str, Any]]) -> None:
        notice = next(step for step in steps if step.get("name") == _NOTICE_STEP_NAME)
        notice["if"] = "success()"

    assert _has(budget_violations(_mutated(mutate)), "must be gated on `failure()`")


def test_a_notice_ordered_before_the_suite_is_reported() -> None:
    def mutate(job: dict[str, Any], steps: list[dict[str, Any]]) -> None:
        notice_index = next(index for index, step in enumerate(steps) if step.get("name") == _NOTICE_STEP_NAME)
        steps.insert(0, steps.pop(notice_index))

    assert _has(budget_violations(_mutated(mutate)), "must run after the suite step")


@pytest.mark.parametrize("phrase", _NOTICE_PHRASES)
def test_a_notice_missing_its_wording_is_reported(phrase: str) -> None:
    def mutate(job: dict[str, Any], steps: list[dict[str, Any]]) -> None:
        notice = next(step for step in steps if step.get("name") == _NOTICE_STEP_NAME)
        notice["run"] = str(notice["run"]).replace(phrase, "")

    assert _has(budget_violations(_mutated(mutate)), "missing wording")


def test_a_renamed_job_is_reported_not_silently_passed() -> None:
    packs = _load_packs()
    job = packs["jobs"].pop(_PACKS_CORPUS_JOB)
    packs["jobs"]["built-in-corpus-suite-renamed"] = job
    assert _has(budget_violations(packs), f"packs.yml has no `{_PACKS_CORPUS_JOB}` job")
