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
    violations: list[str] = []
    for key, job in _jobs(workflow).items():
        declared = job.get("permissions")
        if declared is None:
            declared = workflow.get("permissions")
        if isinstance(declared, str):
            # ``write-all`` / ``read-all`` shorthand: name it rather than crash on ``.items()``.
            violations.append(f"{key}: permissions shorthand {declared!r}")
            continue
        violations.extend(f"{key}: {scope}={value}" for scope, value in dict(declared or {}).items() if value in _WRITE_SCOPES or str(value).endswith("-all"))
    return violations


#: Each job's EFFECTIVE token scopes, exactly. ``collect`` downloads the source attempt's
#: artefacts (``actions: read``); ``sonar-pr`` also reads PR metadata (``pull-requests:
#: read``); the other jobs run on the workflow default. ci-aggregate.yml is a
#: ``workflow_run`` workflow, so PR CI never exercises it: dropping a scope here would only
#: break main-only CI.
_EXPECTED_EFFECTIVE_PERMISSIONS: dict[str, dict[str, str]] = {
    "collect": {"contents": "read", "actions": "read"},
    "diff-cover": {"contents": "read"},
    "sonar-pr": {"contents": "read", "actions": "read", "pull-requests": "read"},
    "aggregate-gate": {"contents": "read"},
}


def _permission_drift(workflow: dict[str, Any]) -> list[str]:
    """Name every job whose effective scopes differ from the pinned map."""
    actual = {
        key: _effective_permissions(workflow, job)
        for key, job in _jobs(workflow).items()
        if not isinstance(job.get("permissions", workflow.get("permissions")), str)
    }
    return [
        f"{key}: expected {_EXPECTED_EFFECTIVE_PERMISSIONS.get(key)} got {actual.get(key)}"
        for key in sorted(set(_EXPECTED_EFFECTIVE_PERMISSIONS) | set(actual))
        if actual.get(key) != _EXPECTED_EFFECTIVE_PERMISSIONS.get(key)
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


def test_each_job_effective_permissions_match_the_pinned_map_exactly() -> None:
    assert _permission_drift(_workflow()) == []


@pytest.mark.parametrize(
    ("job", "scope"),
    [("collect", "actions"), ("sonar-pr", "pull-requests"), ("sonar-pr", "actions")],
)
def test_dropping_a_read_scope_is_caught_where_the_old_pins_were_not(job: str, scope: str) -> None:
    mutant = copy.deepcopy(_workflow())
    del mutant["jobs"][job]["permissions"][scope]

    # Non-vacuity: the pre-existing checks accept this mutant (still read-only, still has contents).
    assert _write_scope_violations(mutant) == []
    assert all("contents" in _effective_permissions(mutant, j) for j in _jobs(mutant).values())
    # The exact pin reports it.
    assert len(_permission_drift(mutant)) == 1
    assert _permission_drift(mutant)[0].startswith(f"{job}: ")


@pytest.mark.parametrize("shorthand", ["write-all", "read-all"])
def test_a_string_permissions_shorthand_is_a_named_violation_not_a_crash(shorthand: str) -> None:
    mutant = copy.deepcopy(_workflow())
    mutant["jobs"]["aggregate-gate"]["permissions"] = shorthand

    assert _write_scope_violations(mutant) == [f"aggregate-gate: permissions shorthand {shorthand!r}"]
    assert any(line.startswith("aggregate-gate: ") for line in _permission_drift(mutant))
