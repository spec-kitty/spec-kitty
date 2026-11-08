"""A nightly suite that runs out of time must escalate as a failure, not a silent cancel (#6787, epic #4437).

Escalating nightly lanes in ``ci-nightly.yml`` record their suite's verdict in
one of two ways: the suite step runs under ``set +e`` and writes its exit into
``$GITHUB_ENV`` (``<NAME>_EXIT=``), or a later step reads the suite step's
``steps.<id>.outcome``. ``if: always()`` steps then upload the reports, call
``scripts/ci/nightly_escalation.py`` and fail the job. The ``${X_EXIT:-1}``
defaults (FIND-1, #5034) were written so that a suite killed mid-run reads as a
failure (exit 1).

They never fired for a job-level timeout. When the JOB reaches its
``timeout-minutes`` cap, GitHub cancels the job and runs none of the remaining
steps, ``if: always()`` included: nightly run 42442477189 (2026-11-08) left
``integration-next`` ``cancelled`` with its upload, escalation and fail-loud
steps never started, so #6787 was neither bumped nor kept honest.

A STEP-level ``timeout-minutes`` behaves differently: the step fails, and the
``if: always()`` steps after it still run, read the unset exit as a failure and
escalate. This module requires every such suite step to carry one, below its
job cap by :data:`RESERVE_MINUTES`, so the step always times out first and the
remaining steps keep time to run; a step cap must also exceed its job's recorded
#5378 maximum suite time, and every escalating lane must have such a step. It
reads only the workflow text.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.ci.integration_next_shard import SHARD_JOB_KEYS
from tests.ci.test_nightly_timeout_headroom import _is_nightly_target, headroom_record

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_WORKFLOW_PATH = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci-nightly.yml"
# Minutes a suite step's own cap must leave under its job cap: job setup before
# the step (checkout, uv and environment sync, packs and service extras; up to
# 2:45 measured on an interpreter shard, run 40812120655) plus the upload,
# escalation (GitHub API calls) and fail-loud steps after it.
RESERVE_MINUTES = 5
# Non-vacuity floor: the suite steps on 2026-11-08 (performance, e2e, stress,
# p0-repro, six interpreter shards, four integration-next shards (#7456), specify-cli-out-of-matrix,
# architectural-backstop, integration-slice, mission-state-audit, events-latest,
# acceptance-bdd's gating run).
_MIN_SUITE_STEPS = 20
_EXIT_WRITE_RE = re.compile(r"\b[A-Z][A-Z0-9_]*_EXIT=")
_OUTCOME_REF_RE = re.compile(r"\bsteps\.([A-Za-z0-9_-]+)\.(?:outcome|conclusion)\b")
_ESCALATION = "nightly_escalation.py"
# A step cap must clear the recorded maximum plus pytest start-up and report writing.
_SUITE_OVERHEAD_MINUTES = 0.5


def _is_suite_step(step: dict[str, Any], referenced_ids: set[str]) -> bool:
    run = str(step.get("run") or "")
    writes_exit = bool(_EXIT_WRITE_RE.search(run)) and "GITHUB_ENV" in run
    return writes_exit or step.get("id") in referenced_ids


def _suite_steps(workflow: dict[str, Any]) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    """Return ``(job_key, job, step)`` for every step whose verdict a later step reads.

    That is a step writing ``<NAME>_EXIT=`` into ``$GITHUB_ENV``, or a step whose
    ``steps.<id>.outcome`` / ``.conclusion`` the job reads.
    """
    found: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for job_key, job in (workflow.get("jobs") or {}).items():
        steps = job.get("steps") or []
        referenced = set(_OUTCOME_REF_RE.findall(yaml.safe_dump(steps)))
        found.extend((job_key, job, step) for step in steps if _is_suite_step(step, referenced))
    return found


def _lanes_without_suite_step(workflow: dict[str, Any]) -> list[str]:
    """Return escalating jobs with no suite step; an aggregator reading ``needs.`` is exempt."""
    with_suite = {job_key for job_key, _, _ in _suite_steps(workflow)}
    missing: list[str] = []
    for job_key, job in (workflow.get("jobs") or {}).items():
        escalations = [step for step in job.get("steps") or [] if _ESCALATION in str(step.get("run") or "")]
        if escalations and job_key not in with_suite and not any("needs." in yaml.safe_dump(step) for step in escalations):
            missing.append(job_key)
    return missing


def step_timeout_violations(workflow: dict[str, Any]) -> list[str]:
    """Return one named message per suite step whose own cap cannot fire before its job's."""
    problems: list[str] = []
    for job_key, job, step in _suite_steps(workflow):
        name = step.get("name", "<unnamed>")
        job_cap = job.get("timeout-minutes")
        step_cap = step.get("timeout-minutes")
        if not isinstance(job_cap, int):
            problems.append(f"{job_key}: no integer job-level `timeout-minutes`")
            continue
        if not isinstance(step_cap, int):
            problems.append(f"{job_key} / {name}: no step-level `timeout-minutes`, so a timeout cancels the job and skips its `if: always()` escalation")
            continue
        if not 0 < step_cap <= job_cap - RESERVE_MINUTES:
            problems.append(
                f"{job_key} / {name}: step `timeout-minutes` {step_cap} must be in 1..{job_cap - RESERVE_MINUTES} "
                f"(job cap {job_cap} minus a {RESERVE_MINUTES}-minute reserve for setup and the escalation steps)"
            )
    problems.extend(
        f"{job_key}: escalates but has no suite step whose verdict it reads, so no step cap can be checked" for job_key in _lanes_without_suite_step(workflow)
    )
    return problems


def _synthetic(job_cap: object, step_cap: object | None) -> dict[str, Any]:
    step: dict[str, Any] = {"name": "Run suite", "if": "always()", "run": 'set +e\npytest\ncode=$?\necho "SUITE_EXIT=$code" >> "$GITHUB_ENV"\n'}
    if step_cap is not None:
        step["timeout-minutes"] = step_cap
    return {"jobs": {"lane": {"timeout-minutes": job_cap, "steps": [step, {"name": "Escalate", "if": "always()", "run": "true"}]}}}


def test_missing_step_cap_is_reported() -> None:
    assert step_timeout_violations(_synthetic(45, None)) == [
        "lane / Run suite: no step-level `timeout-minutes`, so a timeout cancels the job and skips its `if: always()` escalation"
    ]


@pytest.mark.parametrize("step_cap", [45, 41, 0, 99])
def test_step_cap_without_reserve_is_reported(step_cap: int) -> None:
    problems = step_timeout_violations(_synthetic(45, step_cap))
    assert len(problems) == 1 and "must be in 1..40" in problems[0], problems


def test_step_cap_inside_reserve_passes() -> None:
    assert step_timeout_violations(_synthetic(45, 40)) == []


def test_job_without_cap_is_reported() -> None:
    assert step_timeout_violations(_synthetic(None, 10)) == ["lane: no integer job-level `timeout-minutes`"]


def test_steps_that_record_no_suite_exit_are_not_judged() -> None:
    workflow = {"jobs": {"lane": {"timeout-minutes": 5, "steps": [{"name": "Escalate", "run": "python3 scripts/ci/nightly_escalation.py"}]}}}
    assert _suite_steps(workflow) == []


def test_outcome_read_step_is_judged() -> None:
    workflow = {
        "jobs": {
            "audit": {
                "timeout-minutes": 10,
                "steps": [
                    {"name": "Audit", "id": "audit", "run": "audit"},
                    {"name": "Escalate", "if": "always()", "env": {"OUTCOME": "${{ steps.audit.outcome }}"}, "run": "python3 scripts/ci/nightly_escalation.py"},
                ],
            }
        }
    }
    assert [step["name"] for _, _, step in _suite_steps(workflow)] == ["Audit"]
    assert step_timeout_violations(workflow) == [
        "audit / Audit: no step-level `timeout-minutes`, so a timeout cancels the job and skips its `if: always()` escalation"
    ]


@pytest.mark.parametrize(
    "write", ['echo "FOO_EXIT=${code}" >> "$GITHUB_ENV"', 'echo "FOO_EXIT=$?" >> "$GITHUB_ENV"', 'printf "FOO_EXIT=%s\\n" "$rc" >> "$GITHUB_ENV"']
)
def test_exit_write_spellings_are_recognised(write: str) -> None:
    workflow = {"jobs": {"lane": {"timeout-minutes": 20, "steps": [{"name": "Run", "run": write}]}}}
    assert len(_suite_steps(workflow)) == 1


def test_escalating_lane_without_suite_step_is_reported() -> None:
    workflow = {
        "jobs": {
            "lane": {
                "timeout-minutes": 20,
                "steps": [{"name": "Run", "run": "pytest"}, {"name": "Escalate", "if": "always()", "run": "python3 scripts/ci/nightly_escalation.py"}],
            }
        }
    }
    assert step_timeout_violations(workflow) == ["lane: escalates but has no suite step whose verdict it reads, so no step cap can be checked"]


def test_aggregator_reading_needs_is_exempt() -> None:
    workflow = {
        "jobs": {
            "agg": {"timeout-minutes": 5, "steps": [{"name": "Escalate", "env": {"R": "${{ needs.x.result }}"}, "run": "python3 scripts/ci/nightly_escalation.py"}]}
        }
    }
    assert step_timeout_violations(workflow) == []


def test_step_caps_exceed_recorded_suite_maximum() -> None:
    """A step cap at or below the measured suite time would turn a normal run into a false red."""
    text = _WORKFLOW_PATH.read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    judged = 0
    for job_key, _, step in _suite_steps(workflow):
        if not _is_nightly_target(job_key):
            continue
        _, max_suite = headroom_record(text, job_key, is_target=_is_nightly_target)
        minutes, seconds = max_suite.split(":")
        assert step["timeout-minutes"] >= math.ceil(int(minutes) + int(seconds) / 60 + _SUITE_OVERHEAD_MINUTES), (job_key, max_suite, step["timeout-minutes"])
        judged += 1
    assert judged >= 10, f"non-vacuity: expected >=10 recorded lanes, judged {judged}"


def test_every_nightly_suite_step_times_out_before_its_job() -> None:
    workflow = yaml.safe_load(_WORKFLOW_PATH.read_text(encoding="utf-8"))
    steps = _suite_steps(workflow)
    jobs = {job_key for job_key, _, _ in steps}
    assert len(steps) >= _MIN_SUITE_STEPS, f"non-vacuity: expected >={_MIN_SUITE_STEPS} suite steps, found {sorted(jobs)}"
    assert {*SHARD_JOB_KEYS, "performance", "mission-state-audit"} <= jobs
    assert step_timeout_violations(workflow) == []
