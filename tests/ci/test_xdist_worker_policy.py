"""Static xdist worker-policy guard for the battery-class pytest commands (FR-002, #5510).

``-n auto`` resolves to the *physical* core count (2 on the 4-vCPU hosted runner),
so the battery ran on half the available parallelism. FR-002 pins a literal
``-n 4`` -- equal to the registry ``special_tiers.architectural.workers`` -- on
every battery-class command, and forbids ``-q`` so xdist prints
``created: 4/4 workers`` in the job log (the evidence line).

The four battery-class commands are the per-PR ``architectural-fast`` job, every
``architectural-heavy`` matrix leg, the nightly ``architectural-backstop`` and the
Packs corpus suite. The ``Makefile`` deliberately keeps ``-n auto`` (C-005: a
developer machine has an unknown core count; the literal is a CI-runner fact).

Every property is evaluated by ONE production function, ``worker_policy_violations``;
the live test and every mutation test call that same function (Standing Order #5:
a mutation that never reaches the production check proves nothing).
"""

from __future__ import annotations

import copy
import functools
import shlex
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
import yaml

import tests.architectural._gate_coverage as gc

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REGISTRY_PATH = _REPO_ROOT / ".github" / "ci-module-registry.yml"
_MAKEFILE_PATH = _REPO_ROOT / "Makefile"

ROUTER = "ci-router.yml"
NIGHTLY = "ci-nightly.yml"
PACKS = "packs.yml"

BATTERY_CLASS_JOBS: tuple[tuple[str, str], ...] = (
    (ROUTER, "architectural-fast"),
    (ROUTER, "architectural-heavy"),  # every matrix leg
    (NIGHTLY, "architectural-backstop"),
    (PACKS, "built-in-corpus-suite"),
)

# Only the router battery jobs share one partitioned base command, so only they must
# carry the file-level dist mode (per-worker HOME isolation relies on whole files).
_DIST_LOADFILE_WORKFLOWS = frozenset({ROUTER})

_WORKER_SHORT = "-n"
_WORKER_LONG = "--numprocesses"
_QUIET_LONG = "--quiet"


def _worker_value(tokens: list[str]) -> str | None:
    """The xdist worker count a tokenised pytest command asks for, or None when absent.

    Accepts ``-n N``, ``-nN``, ``--numprocesses N`` and ``--numprocesses=N``. The value
    is returned verbatim (``auto``, ``logical``, ``4``...): judging it is the caller's job.
    """
    for index, token in enumerate(tokens):
        if token in (_WORKER_SHORT, _WORKER_LONG):
            return tokens[index + 1] if index + 1 < len(tokens) else ""
        if token.startswith(f"{_WORKER_LONG}="):
            return token.split("=", 1)[1]
        if token.startswith(_WORKER_SHORT) and not token.startswith("--"):
            return token[len(_WORKER_SHORT) :]
    return None


def _is_quiet(tokens: list[str]) -> bool:
    """True when the command carries ``-q`` / ``-qq`` / ``--quiet`` (a ``-m`` value is not a flag)."""
    for token in tokens:
        if token == _QUIET_LONG:
            return True
        if token.startswith("-q") and set(token[1:]) == {"q"}:
            return True
    return False


def _dist_mode(tokens: list[str]) -> str | None:
    for index, token in enumerate(tokens):
        if token == "--dist":
            return tokens[index + 1] if index + 1 < len(tokens) else ""
        if token.startswith("--dist="):
            return token.split("=", 1)[1]
    return None


def _job_run_scripts(job: Mapping[str, Any]) -> list[str]:
    return [step["run"] for step in job.get("steps") or [] if isinstance(step, dict) and isinstance(step.get("run"), str)]


def _legs(job: Mapping[str, Any]) -> list[dict[str, Any] | None]:
    include = ((job.get("strategy") or {}).get("matrix") or {}).get("include")
    return list(include) if isinstance(include, list) and include else [None]


def _pytest_lines(job: Mapping[str, Any]) -> list[tuple[str, list[str]]]:
    """Every logical pytest line of *job*, once per matrix leg, as ``(leg label, tokens)``."""
    found: list[tuple[str, list[str]]] = []
    for leg in _legs(job):
        label = str((leg or {}).get("shard", "-"))
        for script in _job_run_scripts(job):
            for logical in gc.join_continuations(gc.substitute_matrix(script, leg or {})):
                if gc.suite_invocations(logical):
                    found.append((label, shlex.split(logical, comments=True)))
    return found


def _line_violations(where: str, tokens: list[str], *, workers: int, needs_dist: bool) -> list[str]:
    problems: list[str] = []
    value = _worker_value(tokens)
    if value is None:
        problems.append(f"{where}: no xdist worker flag (expected a literal -n {workers})")
    elif value != str(workers):
        problems.append(f"{where}: worker count {value!r} != the literal {workers} (registry workers); auto-detection resolves to physical cores")
    if _is_quiet(tokens):
        problems.append(f"{where}: -q/--quiet hides xdist's 'created: {workers}/{workers} workers' evidence line (FR-002)")
    if needs_dist and _dist_mode(tokens) != "loadfile":
        problems.append(f"{where}: missing --dist loadfile (whole-file scheduling is required for per-worker HOME isolation)")
    return problems


def worker_policy_violations(workflows: Mapping[str, dict[str, Any]], *, workers: int) -> list[str]:
    """Every breach of the battery-class worker policy across *workflows* (``[]`` = compliant)."""
    problems: list[str] = []
    for workflow, job_key in BATTERY_CLASS_JOBS:
        job = (workflows.get(workflow) or {}).get("jobs", {}).get(job_key)
        if job is None:
            problems.append(f"{workflow}::{job_key}: job not found (a renamed job must not silently pass)")
            continue
        lines = _pytest_lines(job)
        if not lines:
            problems.append(f"{workflow}::{job_key}: no pytest line found (non-vacuity)")
            continue
        for leg, tokens in lines:
            where = f"{workflow}::{job_key} [leg {leg}]"
            problems.extend(_line_violations(where, tokens, workers=workers, needs_dist=workflow in _DIST_LOADFILE_WORKFLOWS))
    return problems


def _registry_workers() -> int:
    registry = yaml.safe_load(_REGISTRY_PATH.read_text(encoding="utf-8"))
    return int(registry["special_tiers"]["architectural"]["workers"])


@functools.cache
def _live_workflows() -> dict[str, dict[str, Any]]:
    """Parsed once per process; every mutation test works on a deep copy (see ``live``)."""
    return {name: gc.load_spliced_workflow(gc.WORKFLOWS_DIR / name) for name in (ROUTER, NIGHTLY, PACKS)}


def test_battery_class_commands_use_the_registry_worker_count() -> None:
    assert worker_policy_violations(_live_workflows(), workers=_registry_workers()) == []


def test_the_registry_worker_count_is_four() -> None:
    """The registry worker count is exactly 4, matching the literal ``-n 4`` the workflows carry."""
    assert _registry_workers() == 4


def _mutate_run_scripts(workflows: dict[str, dict[str, Any]], workflow: str, job_key: str, old: str, new: str) -> None:
    job = workflows[workflow]["jobs"][job_key]
    touched = 0
    for step in job["steps"]:
        if isinstance(step.get("run"), str) and old in step["run"]:
            step["run"] = step["run"].replace(old, new)
            touched += 1
    assert touched, f"mutation anchor {old!r} not found in {workflow}::{job_key} (the mutation proves nothing)"


@pytest.fixture
def live() -> dict[str, dict[str, Any]]:
    return copy.deepcopy(_live_workflows())


@pytest.mark.parametrize(("workflow", "job_key"), BATTERY_CLASS_JOBS)
def test_auto_detection_is_reported_on_every_battery_class_job(live: dict[str, dict[str, Any]], workflow: str, job_key: str) -> None:
    _mutate_run_scripts(live, workflow, job_key, "-n 4", "-n auto")

    problems = worker_policy_violations(live, workers=_registry_workers())
    assert any(f"{workflow}::{job_key}" in p and "'auto'" in p for p in problems), problems


def test_logical_numprocesses_spelling_is_reported(live: dict[str, dict[str, Any]]) -> None:
    _mutate_run_scripts(live, ROUTER, "architectural-fast", "-n 4", "--numprocesses=logical")

    problems = worker_policy_violations(live, workers=_registry_workers())

    assert any("architectural-fast" in p and "'logical'" in p for p in problems), problems


def test_a_missing_worker_flag_is_reported(live: dict[str, dict[str, Any]]) -> None:
    _mutate_run_scripts(live, NIGHTLY, "architectural-backstop", "-n 4 ", "")

    problems = worker_policy_violations(live, workers=_registry_workers())

    assert any("architectural-backstop" in p and "no xdist worker flag" in p for p in problems), problems


def test_the_compact_and_long_worker_spellings_are_accepted() -> None:
    assert _worker_value(shlex.split("pytest -n4")) == "4"
    assert _worker_value(shlex.split("pytest --numprocesses 4")) == "4"
    assert _worker_value(shlex.split("pytest --numprocesses=4")) == "4"
    assert _worker_value(shlex.split("pytest -m 'not slow'")) is None
    assert _worker_value(shlex.split("pytest -n")) == ""


def test_a_wrong_literal_is_reported(live: dict[str, dict[str, Any]]) -> None:
    _mutate_run_scripts(live, PACKS, "built-in-corpus-suite", "-n 4", "-n 2")

    problems = worker_policy_violations(live, workers=_registry_workers())

    assert any("built-in-corpus-suite" in p and "'2'" in p for p in problems), problems


def test_quiet_flag_is_reported_per_variant(live: dict[str, dict[str, Any]]) -> None:
    _mutate_run_scripts(live, ROUTER, "architectural-fast", "python -m pytest", "python -m pytest -q")
    problems = worker_policy_violations(live, workers=_registry_workers())
    assert any("architectural-fast" in p and "-q/--quiet" in p for p in problems), problems

    live = copy.deepcopy(_live_workflows())
    _mutate_run_scripts(live, NIGHTLY, "architectural-backstop", "python -m pytest", "python -m pytest --quiet")
    problems = worker_policy_violations(live, workers=_registry_workers())
    assert any("architectural-backstop" in p and "-q/--quiet" in p for p in problems), problems


def test_a_missing_dist_loadfile_is_reported_on_the_router_jobs(live: dict[str, dict[str, Any]]) -> None:
    _mutate_run_scripts(live, ROUTER, "architectural-fast", "--dist loadfile", "--dist load")

    problems = worker_policy_violations(live, workers=_registry_workers())

    assert any("architectural-fast" in p and "--dist loadfile" in p for p in problems), problems


def test_a_renamed_job_is_reported_not_silently_passed(live: dict[str, dict[str, Any]]) -> None:
    jobs = live[ROUTER]["jobs"]
    jobs["architectural-fast-renamed"] = jobs.pop("architectural-fast")

    problems = worker_policy_violations(live, workers=_registry_workers())

    assert any("architectural-fast" in p and "job not found" in p for p in problems), problems


def test_a_job_with_no_pytest_line_is_reported(live: dict[str, dict[str, Any]]) -> None:
    for step in live[PACKS]["jobs"]["built-in-corpus-suite"]["steps"]:
        if isinstance(step.get("run"), str):
            step["run"] = "echo nothing runs here"

    problems = worker_policy_violations(live, workers=_registry_workers())

    assert any("built-in-corpus-suite" in p and "no pytest line" in p for p in problems), problems


def test_every_matrix_leg_of_the_heavy_battery_is_checked(live: dict[str, dict[str, Any]]) -> None:
    """A policy breach that only one leg shows (matrix-substituted) is still reported."""
    job = live[ROUTER]["jobs"]["architectural-heavy"]
    legs = ((job.get("strategy") or {}).get("matrix") or {}).get("include") or []
    assert len(legs) >= 2, "the heavy battery must be a multi-leg include matrix"
    for step in job["steps"]:
        if isinstance(step.get("run"), str) and "-n 4" in step["run"]:
            step["run"] = step["run"].replace("-n 4", "-n ${{ matrix.workers }}")
    for index, leg in enumerate(legs):
        leg["workers"] = "4" if index == 0 else "auto"

    problems = worker_policy_violations(live, workers=_registry_workers())

    leg_problems = [p for p in problems if "architectural-heavy" in p]
    assert len(leg_problems) == 1 and f"[leg {legs[1]['shard']}]" in leg_problems[0], problems


def test_makefile_keeps_auto_detection_locally() -> None:
    """C-005: only the CI commands pin ``-n 4``; developer ``make`` targets keep ``-n auto``."""
    assert "-n auto" in _MAKEFILE_PATH.read_text(encoding="utf-8")
