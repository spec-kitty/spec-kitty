"""The GitHub merge queue can land a pull request only if CI runs on its ``merge_group`` events.

The queue tests each PR against ``main`` plus the PRs ahead of it, on a temporary
``gh-readonly-queue/main/...`` ref, and merges only when the required checks pass there. These
tests read the real workflow files and pin what that needs:

* every workflow that produces a required check triggers on ``merge_group``;
* every step that picks a diff base by event knows the ``merge_group`` base, so a queue run is
  path-scoped like the PR run instead of falling back to every module;
* CI Aggregate (diff coverage, already judged on the PR) does not run on queue runs.

CI Fleet Verdict's concurrency key, which must not let a queue run cancel the push-to-main verdict
of the same commit, is pinned exactly in ``test_fleet_verdict.py``.

The required check names come from ``pr-pause-ci.yml``, which posts them as failures to pause a PR.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = [pytest.mark.fast]

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
MERGE_GROUP = "merge_group"
_GATE_LOOP_RE = re.compile(r'for gate in ((?:"[^"]+"\s*)+);')
_CASE_ARM_RE = re.compile(r"^\s*([a-z_]+)\)", re.MULTILINE)


def _load(name: str) -> dict[Any, Any]:
    data: dict[Any, Any] = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    return data


def _triggers(workflow: dict[Any, Any]) -> set[str]:
    on = workflow.get("on", workflow.get(True))
    if isinstance(on, str):
        return {on}
    if isinstance(on, list):
        return set(on)
    return set(on or {})


def required_check_names() -> set[str]:
    text = (WORKFLOWS / "pr-pause-ci.yml").read_text(encoding="utf-8")
    match = _GATE_LOOP_RE.search(text)
    assert match is not None, "pr-pause-ci.yml no longer lists the required gates in a `for gate in ...` loop"
    return set(re.findall(r'"([^"]+)"', match.group(1)))


def _all_workflows() -> list[str]:
    return sorted(path.name for path in WORKFLOWS.glob("*.yml"))


def _producers() -> dict[str, str]:
    """Required check name -> the workflow file whose job carries that name."""
    found: dict[str, str] = {}
    for name in _all_workflows():
        for job in (_load(name).get("jobs") or {}).values():
            if job.get("name") in required_check_names():
                found[job["name"]] = name
    return found


def test_the_required_checks_are_known() -> None:
    assert required_check_names() == {"router gate", "CI Modules gate", "Clean install verification"}
    assert set(_producers()) == required_check_names()


@pytest.mark.parametrize("check", sorted(required_check_names()))
def test_every_required_check_reports_on_merge_group_runs(check: str) -> None:
    workflow = _producers()[check]
    assert MERGE_GROUP in _triggers(_load(workflow)), f"{workflow} produces required check {check!r} but does not trigger on merge_group"


def _event_case_steps(workflow: dict[Any, Any]) -> list[tuple[str, dict[str, Any]]]:
    steps: list[tuple[str, dict[str, Any]]] = []
    for job_id, job in (workflow.get("jobs") or {}).items():
        for step in job.get("steps") or []:
            run = str(step.get("run", ""))
            if 'case "$EVENT_NAME"' in run:
                steps.append((f"{job_id}/{step.get('id') or step.get('name')}", step))
    return steps


def _merge_group_workflows() -> list[str]:
    return [name for name in _all_workflows() if MERGE_GROUP in _triggers(_load(name))]


def test_the_queue_triggered_set_is_the_required_producers() -> None:
    """Only the required-check workflows join the queue; optional ones would run on every group."""
    assert set(_merge_group_workflows()) == set(_producers().values())


@pytest.mark.parametrize("workflow", _merge_group_workflows() or ["<none>"])
def test_event_keyed_diff_bases_handle_merge_group(workflow: str) -> None:
    if workflow == "<none>":
        pytest.fail("no workflow triggers on merge_group")
    for where, step in _event_case_steps(_load(workflow)):
        run = str(step["run"])
        arms = set(_CASE_ARM_RE.findall(run))
        if "push" not in arms:
            continue
        assert re.search(r'^\s*merge_group\)\s*base="\$MERGE_GROUP_BASE"\s*;;', run, re.MULTILINE), (
            f"{workflow} {where}: the merge_group arm must take the queue's base SHA"
        )
        env = {str(key): str(value) for key, value in (step.get("env") or {}).items()}
        assert " ".join(env.get("MERGE_GROUP_BASE", "").split()) == "${{ github.event.merge_group.base_sha }}", (
            f"{workflow} {where}: MERGE_GROUP_BASE must be github.event.merge_group.base_sha"
        )


def test_the_diff_base_steps_are_found() -> None:
    """Non-vacuity: the two path-scoping steps exist where the tests above look for them."""
    assert _event_case_steps(_load("ci-modules.yml"))
    assert _event_case_steps(_load("ci-router.yml"))


_SKIP_QUEUE = "github.event.workflow_run.event != 'merge_group'"


def _top_level_conjuncts(condition: str) -> list[str]:
    """Split an ``if:`` on ``&&`` outside parentheses, so a conjunct inside an ``||`` never counts."""
    text = " ".join(condition.split())
    match = re.fullmatch(r"\$\{\{\s*(.*?)\s*\}\}", text)
    text = match.group(1) if match else text
    parts: list[str] = []
    depth, start, index = 0, 0, 0
    while index < len(text):
        char = text[index]
        depth += {"(": 1, ")": -1}.get(char, 0)
        if depth == 0 and text.startswith("&&", index):
            parts.append(text[start:index].strip())
            start = index + 2
            index += 2
            continue
        index += 1
    parts.append(text[start:].strip())
    return parts


@pytest.mark.parametrize("job", ["collect", "diff-cover", "aggregate-gate"])
def test_ci_aggregate_skips_merge_group_sources(job: str) -> None:
    condition = str(_load("ci-aggregate.yml")["jobs"][job]["if"])
    assert _SKIP_QUEUE in _top_level_conjuncts(condition), f"ci-aggregate {job} would run on a merge-group CI Modules run"


def test_the_conjunct_split_ignores_a_skip_inside_an_or() -> None:
    """Non-vacuity of the check above: a skip nested in an ``||`` is not a top-level conjunct."""
    nested = f"(a == 'b' || {_SKIP_QUEUE}) && always()"
    assert _SKIP_QUEUE not in _top_level_conjuncts(nested)
    assert _SKIP_QUEUE in _top_level_conjuncts(f"(a == 'b') && {_SKIP_QUEUE} && always()")
