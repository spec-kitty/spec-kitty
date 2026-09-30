"""CI-shape guard for the always-on ``docs-lint`` job and ``make docs-lint`` (#5426).

The docs prose lint (``scripts.docs.check_spelling`` and
``scripts.docs.check_changelog_style``) must block every PR (FR-013) and be
runnable locally with one command (FR-014). A job that silently passes is worse
than no job, so each contract clause below is a small checker over parsed data,
and every checker has a companion mutant test that feeds a mutated in-memory
copy through the SAME checker and expects a failure (non-vacuity).

The checks are key-level, not substring greps: ``continue-on-error`` and a step
``if:`` are dict keys, so a mutant that adds ``continue-on-error: false`` still
trips the guard (the key must be absent, not merely falsy).
"""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ROUTER_PATH = _REPO_ROOT / ".github" / "workflows" / "ci-router.yml"
_MAKEFILE_PATH = _REPO_ROOT / "Makefile"

_JOB = "docs-lint"
_SPELLING_CMD = "python -m scripts.docs.check_spelling"
_CHANGELOG_CMD = "python -m scripts.docs.check_changelog_style"
_REQUIRED_COMMANDS = (_SPELLING_CMD, _CHANGELOG_CMD)
# Regexes, not substrings: every whitespace variant of a failure-swallowing idiom must be refused.
# `\b` keeps lookalikes (`exit 01`, `reset +e`, `|| true_value`) from tripping the guard.
_FORBIDDEN_IN_RUN = (
    r"\|\|\s*true\b",
    r"\|\|\s*:",
    r"\bset\s+\+e\b",
    r"\bexit\s+0\b",
    r"\bpytest\b",
    r"\bmake\s",
)


# ---------------------------------------------------------------------------
# Checkers: each takes parsed data and returns a list of violation strings.
# ---------------------------------------------------------------------------
def _run_text(job: dict[str, Any]) -> str:
    return "\n".join(str(step["run"]) for step in job.get("steps", []) if "run" in step)


def check_job_unconditional(job: dict[str, Any]) -> list[str]:
    return ["job carries an `if:` key"] if "if" in job else []


def check_required_commands(job: dict[str, Any]) -> list[str]:
    run = _run_text(job)
    return [f"missing command: {cmd}" for cmd in _REQUIRED_COMMANDS if cmd not in run]


def check_no_forbidden_run_text(job: dict[str, Any]) -> list[str]:
    run = _run_text(job)
    return [f"forbidden run text: {bad!r}" for bad in _FORBIDDEN_IN_RUN if re.search(bad, run)]


def check_no_soft_fail_keys(job: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    if "continue-on-error" in job:
        violations.append("job has a `continue-on-error` key")
    for index, step in enumerate(job.get("steps", [])):
        if "continue-on-error" in step:
            violations.append(f"step {index} has a `continue-on-error` key")
        if "if" in step:
            violations.append(f"step {index} has an `if:` key")
        if "shell" in step:
            violations.append(f"step {index} overrides `shell:`")
    return violations


def check_in_router_gate_needs(workflow: dict[str, Any]) -> list[str]:
    needs = workflow["jobs"]["router-gate"]["needs"]
    return [] if _JOB in needs else [f"{_JOB} is not in router-gate.needs"]


def _recipe(makefile_text: str, target: str) -> str:
    match = re.search(rf"^{re.escape(target)}:[^\n]*\n((?:\t[^\n]*\n?)*)", makefile_text, re.MULTILINE)
    assert match is not None, f"Makefile has no `{target}` target"
    return match.group(1)


def check_make_recipe(makefile_text: str) -> list[str]:
    recipe = _recipe(makefile_text, _JOB)
    violations = [f"recipe missing command: {cmd}" for cmd in _REQUIRED_COMMANDS if cmd not in recipe]
    if "pytest" in recipe:
        violations.append("recipe runs pytest")
    return violations


def check_makefile_phony(makefile_text: str) -> list[str]:
    phony = " ".join(re.findall(r"^\.PHONY:([^\n]*)", makefile_text, re.MULTILINE))
    return [] if _JOB in phony.split() else [f"{_JOB} is not in .PHONY"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def workflow() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(_ROUTER_PATH.read_text(encoding="utf-8"))
    return loaded


@pytest.fixture()
def job(workflow: dict[str, Any]) -> dict[str, Any]:
    assert _JOB in workflow["jobs"], f"ci-router.yml has no `{_JOB}` job"
    job_copy: dict[str, Any] = copy.deepcopy(workflow["jobs"][_JOB])
    return job_copy


@pytest.fixture(scope="module")
def makefile_text() -> str:
    return _MAKEFILE_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# The contract against the real files
# ---------------------------------------------------------------------------
def test_job_is_unconditional(job: dict[str, Any]) -> None:
    assert check_job_unconditional(job) == []


def test_job_runs_both_module_commands(job: dict[str, Any]) -> None:
    assert check_required_commands(job) == []


def test_job_has_no_forbidden_run_text(job: dict[str, Any]) -> None:
    assert check_no_forbidden_run_text(job) == []


def test_job_has_no_soft_fail_keys(job: dict[str, Any]) -> None:
    assert check_no_soft_fail_keys(job) == []


def test_job_is_in_router_gate_needs(workflow: dict[str, Any]) -> None:
    assert check_in_router_gate_needs(workflow) == []


def test_make_target_runs_both_commands_without_pytest(makefile_text: str) -> None:
    assert check_make_recipe(makefile_text) == []


def test_make_target_is_phony(makefile_text: str) -> None:
    assert check_makefile_phony(makefile_text) == []


# ---------------------------------------------------------------------------
# Non-vacuity: each mutant must be caught by the same checker.
# ---------------------------------------------------------------------------
def _last_run_step(job: dict[str, Any]) -> dict[str, Any]:
    steps: list[dict[str, Any]] = [step for step in job["steps"] if "run" in step]
    return steps[-1]


def test_mutant_a_or_true_is_caught(job: dict[str, Any]) -> None:
    step = _last_run_step(job)
    step["run"] = str(step["run"]).rstrip("\n") + " || true\n"
    assert check_no_forbidden_run_text(job)


@pytest.mark.parametrize(
    "masking",
    ["||true", "|| true", "||  true", "|| :", "||:", "|| \t:", "set +e", "set  +e", "exit 0", "exit  0"],
)
def test_mutant_masking_spellings_are_caught(job: dict[str, Any], masking: str) -> None:
    """Every whitespace-tolerant way of swallowing a failing lint exit code is refused."""
    step = _last_run_step(job)
    step["run"] = str(step["run"]).rstrip("\n") + f"\n{masking}\n"
    assert check_no_forbidden_run_text(job)


@pytest.mark.parametrize("innocent", ["exit 01", "exit 10", "echo reset +e", "cmd || true_value_check"])
def test_masking_regexes_do_not_flag_lookalikes(job: dict[str, Any], innocent: str) -> None:
    step = _last_run_step(job)
    step["run"] = str(step["run"]).rstrip("\n") + f"\n{innocent}\n"
    assert check_no_forbidden_run_text(job) == []


def test_mutant_b_job_level_if_is_caught(job: dict[str, Any]) -> None:
    job["if"] = "${{ needs.changes.outputs.docs == 'true' }}"
    assert check_job_unconditional(job)


def test_mutant_c_removed_command_is_caught(job: dict[str, Any]) -> None:
    step = _last_run_step(job)
    step["run"] = "\n".join(line for line in str(step["run"]).splitlines() if _CHANGELOG_CMD not in line)
    assert check_required_commands(job) == [f"missing command: {_CHANGELOG_CMD}"]


def test_mutant_d_job_continue_on_error_is_caught(job: dict[str, Any]) -> None:
    job["continue-on-error"] = True
    assert check_no_soft_fail_keys(job)


def test_mutant_d2_job_continue_on_error_false_key_is_caught(job: dict[str, Any]) -> None:
    job["continue-on-error"] = False  # key-level: even a falsy value must be refused
    assert check_no_soft_fail_keys(job)


def test_mutant_e_step_continue_on_error_is_caught(job: dict[str, Any]) -> None:
    _last_run_step(job)["continue-on-error"] = True
    assert check_no_soft_fail_keys(job)


def test_mutant_f_step_if_false_is_caught(job: dict[str, Any]) -> None:
    _last_run_step(job)["if"] = False
    assert check_no_soft_fail_keys(job)


def test_mutant_g_pytest_in_makefile_recipe_is_caught(makefile_text: str) -> None:
    recipe = _recipe(makefile_text, _JOB)
    mutated = makefile_text.replace(recipe, recipe + "\tuv run --frozen pytest tests/ci -q\n", 1)
    assert mutated != makefile_text
    assert check_make_recipe(mutated) == ["recipe runs pytest"]


def test_mutant_step_shell_override_is_caught(job: dict[str, Any]) -> None:
    _last_run_step(job)["shell"] = "bash {0} || true"
    assert check_no_soft_fail_keys(job)


def test_mutant_router_gate_without_job_is_caught(workflow: dict[str, Any]) -> None:
    mutated = copy.deepcopy(workflow)
    mutated["jobs"]["router-gate"]["needs"] = [n for n in mutated["jobs"]["router-gate"]["needs"] if n != _JOB]
    assert check_in_router_gate_needs(mutated)


def test_mutant_phony_without_target_is_caught(makefile_text: str) -> None:
    mutated = re.sub(r"(^\.PHONY:[^\n]*?)\bdocs-lint\b", r"\1", makefile_text, flags=re.MULTILINE)
    assert check_makefile_phony(mutated)
