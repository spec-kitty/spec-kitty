"""Pin least-privilege ``GITHUB_TOKEN`` scopes on ``ci-aggregate.yml`` (#5554).

``ci-aggregate.yml`` runs in the privileged ``workflow_run`` context: it executes the
default branch's copy of its own file while reading a *different* run's artefacts. With
no workflow-level ``permissions:`` block every job inherited the repository's default
token scopes, so the reachable blast radius was whatever the repository default happened
to be. The workflow now declares ``contents: read`` as the floor; a job that needs more
(``actions: read`` to download the source attempt, ``pull-requests: read`` for the Sonar
PR metadata) grants it job-locally, and a job-level block REPLACES the default.

Each checker below has a mutant fed through the same helper (non-vacuity): a checker that
cannot fail is not a pin.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parents[2]
AGGREGATE = ROOT / ".github" / "workflows" / "ci-aggregate.yml"

#: Scopes that can mutate repository state; none of this workflow's jobs needs one.
_WRITE_SCOPES = frozenset({"write", "write-all"})


def _workflow() -> dict[str, Any]:
    return dict(yaml.safe_load(AGGREGATE.read_text(encoding="utf-8")))


def _jobs(workflow: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {key: job for key, job in workflow["jobs"].items() if isinstance(job, dict)}


def _effective_permissions(workflow: dict[str, Any], job: dict[str, Any]) -> dict[str, str]:
    """The scopes *job* actually gets: its own block, else the workflow default."""
    declared = job.get("permissions")
    if declared is None:
        declared = workflow.get("permissions")
    return dict(declared or {})


def _write_scope_violations(workflow: dict[str, Any]) -> list[str]:
    return [
        f"{key}: {scope}={value}"
        for key, job in _jobs(workflow).items()
        for scope, value in _effective_permissions(workflow, job).items()
        if value in _WRITE_SCOPES or str(value).endswith("-all")
    ]


def test_the_workflow_declares_a_read_only_default() -> None:
    assert _workflow()["permissions"] == {"contents": "read"}


def test_a_missing_workflow_default_is_caught() -> None:
    mutant = copy.deepcopy(_workflow())
    mutant.pop("permissions")

    assert _effective_permissions(mutant, mutant["jobs"]["aggregate-gate"]) == {}


def test_every_job_resolves_to_an_explicit_read_only_grant() -> None:
    workflow = _workflow()
    jobs = _jobs(workflow)

    assert jobs, "no jobs parsed: the workflow shape changed under this pin"
    for key, job in jobs.items():
        effective = _effective_permissions(workflow, job)
        assert effective, f"{key} resolves to no permission set; declare the workflow default"
        # ``collect`` (artefact download) and ``sonar-pr`` (PR metadata) legitimately
        # widen the scope *set*; widening is not the same as gaining a write scope.
        assert "contents" in effective, f"{key} must grant at least contents: read"


def test_no_job_grants_a_write_scope() -> None:
    assert _write_scope_violations(_workflow()) == []


def test_a_job_level_write_grant_is_caught() -> None:
    mutant = copy.deepcopy(_workflow())
    mutant["jobs"]["aggregate-gate"]["permissions"] = {"contents": "write"}

    assert _write_scope_violations(mutant) == ["aggregate-gate: contents=write"]


def test_a_workflow_level_write_default_is_caught() -> None:
    mutant = copy.deepcopy(_workflow())
    mutant["permissions"] = {"contents": "read", "issues": "write-all"}

    # ``aggregate-gate`` declares no job-level block, so it is the job that inherits it.
    assert _write_scope_violations(mutant) == ["aggregate-gate: issues=write-all"]
