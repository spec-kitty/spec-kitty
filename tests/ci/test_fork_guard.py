"""Automated CI runs are core-repo only: forks must not run them.

A fork inherits every workflow. Without a guard, a fork's scheduled nightly,
its own ``main`` pushes (a "Sync fork" is a push) and the ``workflow_run``
followers all execute there: they burn the fork owner's Actions budget and mail
them nightly failures (and ``ci-nightly.yml`` / ``ci-fleet-verdict.yml`` can open
P0 issues in the fork).

The rule these tests pin: in every workflow that has an automated trigger
(``schedule``, ``push``, ``workflow_run``), every job that can start on its own
(a root job with no ``needs``, or a job whose ``if:`` uses ``always()`` and so
runs even when its needs were skipped) carries a canonical fork guard as the
first top-level ``&&`` conjunct of its ``if:``. Everything else only runs after a
guarded job, so it skips with it. ``pull_request`` and ``workflow_dispatch``
keep running on forks, so fork contributors' PR CI and manual runs are unchanged.
"""

from __future__ import annotations

import itertools
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.fast

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
CORE_REPOSITORY = "spec-kitty/spec-kitty"

AUTOMATED_TRIGGERS = frozenset({"schedule", "push", "workflow_run"})

# Workflows with an automated trigger that deliberately carry no fork guard.
EXEMPT_WORKFLOWS = {
    # Tag push only: cutting a release tag is a deliberate human act, and the
    # PyPI trusted publisher is bound to the core repository anyway.
    "release.yml": "tag-push release, human-initiated",
}

_ATOM_RE = re.compile(
    r"(github\.repository|github\.event_name|github\.event\.workflow_run\.event)"
    r"\s*==\s*'([^']+)'"
)


def _load(path: Path) -> dict[Any, Any]:
    data: dict[Any, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data


def _triggers(workflow: dict[Any, Any]) -> set[str]:
    # PyYAML reads the bare ``on:`` key as boolean True.
    on = workflow.get("on", workflow.get(True))
    if isinstance(on, str):
        return {on}
    if isinstance(on, list):
        return set(on)
    return set(on or {})


def _automated_workflows() -> list[Path]:
    return sorted(path for path in WORKFLOWS_DIR.glob("*.yml") if path.name not in EXEMPT_WORKFLOWS and _triggers(_load(path)) & AUTOMATED_TRIGGERS)


def _normalize(condition: str) -> str:
    text = " ".join(condition.split())
    match = re.fullmatch(r"\$\{\{\s*(.*?)\s*\}\}", text)
    return match.group(1) if match else text


def _leading_guard(condition: str) -> str:
    """The first top-level ``&&`` conjunct, which must be the parenthesised guard."""
    text = _normalize(condition)
    assert text.startswith("("), f"if: does not open with the fork guard: {text!r}"
    depth = 0
    for index, char in enumerate(text):
        depth += {"(": 1, ")": -1}.get(char, 0)
        if depth == 0:
            guard, rest = text[: index + 1], text[index + 1 :].strip()
            assert rest == "" or rest.startswith("&&"), f"fork guard is not a top-level conjunct: {text!r}"
            return guard
    raise AssertionError(f"unbalanced if: {text!r}")


def _guard_allows(guard: str, *, repository: str, event_name: str, run_event: str | None) -> bool:
    """Evaluate a guard: a parenthesised ``||`` of ``==`` atoms (no other shape)."""
    inner = guard[1:-1]
    context = {
        "github.repository": repository,
        "github.event_name": event_name,
        "github.event.workflow_run.event": run_event,
    }
    atoms = [atom.strip() for atom in inner.split("||")]
    results = []
    for atom in atoms:
        match = _ATOM_RE.fullmatch(atom)
        assert match, f"unmodeled fork-guard atom: {atom!r}"
        results.append(context[match.group(1)] == match.group(2))
    return any(results)


def _self_starting_jobs(workflow: dict[Any, Any]) -> list[tuple[str, dict[str, Any]]]:
    jobs: dict[str, dict[str, Any]] = workflow.get("jobs") or {}
    return [(name, job) for name, job in jobs.items() if not job.get("needs") or "always()" in str(job.get("if", ""))]


def _guarded_jobs() -> list[tuple[str, str, dict[str, Any]]]:
    return [(path.name, name, job) for path in _automated_workflows() for name, job in _self_starting_jobs(_load(path))]


def test_the_automated_workflow_set_is_not_empty() -> None:
    names = {path.name for path in _automated_workflows()}
    assert {"ci-nightly.yml", "ci-router.yml", "ci-fleet-verdict.yml", "sonar.yml"} <= names


@pytest.mark.parametrize(
    ("workflow", "job_name", "job"),
    _guarded_jobs(),
    ids=lambda value: value if isinstance(value, str) else "",
)
def test_every_self_starting_job_is_fork_guarded(workflow: str, job_name: str, job: dict[str, Any]) -> None:
    condition = job.get("if")
    assert isinstance(condition, str), f"{workflow}:{job_name} has no if: fork guard"
    guard = _leading_guard(condition)
    assert f"github.repository == '{CORE_REPOSITORY}'" in guard

    # On the core repository the guard never changes anything.
    for event_name, run_event in itertools.product(("schedule", "push", "workflow_run", "pull_request", "workflow_dispatch"), ("push", "pull_request", None)):
        assert _guard_allows(guard, repository=CORE_REPOSITORY, event_name=event_name, run_event=run_event)

    # On a fork, automated main-branch runs skip...
    fork = "someone/spec-kitty"
    for event_name in ("schedule", "push"):
        assert not _guard_allows(guard, repository=fork, event_name=event_name, run_event=None)
    assert not _guard_allows(guard, repository=fork, event_name="workflow_run", run_event="push")
    assert not _guard_allows(guard, repository=fork, event_name="workflow_run", run_event="schedule")


@pytest.mark.parametrize("workflow", [p.name for p in _automated_workflows()])
def test_fork_pull_request_ci_keeps_running(workflow: str) -> None:
    """A fork's own PR and manual runs stay live wherever the workflow takes them."""
    data = _load(WORKFLOWS_DIR / workflow)
    triggers = _triggers(data)
    fork = "someone/spec-kitty"
    for name, job in _self_starting_jobs(data):
        guard = _leading_guard(str(job["if"]))
        if "pull_request" in triggers:
            assert _guard_allows(guard, repository=fork, event_name="pull_request", run_event=None), name
        if "workflow_dispatch" in triggers:
            assert _guard_allows(guard, repository=fork, event_name="workflow_dispatch", run_event=None), name


def test_fleet_verdict_is_core_only_even_for_fork_pull_requests() -> None:
    """The fleet verdict writes comments and P0 issues; it never runs on a fork."""
    data = _load(WORKFLOWS_DIR / "ci-fleet-verdict.yml")
    guard = _leading_guard(str(data["jobs"]["identify"]["if"]))
    assert not _guard_allows(guard, repository="someone/spec-kitty", event_name="workflow_run", run_event="pull_request")


def test_guard_evaluator_rejects_unknown_atoms() -> None:
    with pytest.raises(AssertionError, match="unmodeled"):
        _guard_allows("(github.ref == 'refs/heads/main')", repository=CORE_REPOSITORY, event_name="push", run_event=None)
