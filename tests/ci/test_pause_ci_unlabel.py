"""Removing ``pr:pause-ci`` restarts CI; any other label event is a no-op (#7019).

The workflows that produce the three required checks trigger on ``labeled`` / ``unlabeled`` so
that removing the pause label starts a full run on the PR's current head, with no push. Every
other label event also starts those workflows (GitHub cannot filter ``pull_request`` triggers by
label name), so such a run must stay a cheap no-op that neither cancels nor supersedes the real run:

- **Jobs:** every job that can start on its own carries the label guard, so the whole run skips.
- **Required checks:** a skipped job still posts a check run under its own name, and a skipped
  required check passes. The gate jobs therefore carry a different name in a no-op run. (These
  tests prove the name expression never resolves to the required name there. GitHub posts a
  skipped job under the raw text of its ``name:`` expression, not its evaluated value, as seen
  on #7047; that text differs from the required name too.)
- **Concurrency:** a no-op run gets its own group, so it never cancels the in-flight run.
- **Followers:** CI Aggregate keys a skipped CI Modules source apart, and the fleet verdict never
  reads a skipped label-triggered run as the latest evidence.
- **Closed PRs:** a label change on a closed PR is a no-op too (there is no merge ref to test).
- **The pause workflow** cancels these three workflows' runs created before the label, but spares
  the run the label event started, and never re-runs their cancelled runs (a re-run would join the
  shared concurrency group and cancel the fresh run).

These are property tests: they evaluate the real ``if:``, ``name:`` and ``concurrency`` expressions
under synthetic events (``tests/ci/_gh_expr.py``), not text pins.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.ci import fleet_verdict
from tests.ci._gh_expr import evaluate, github_context, interpolate

pytestmark = pytest.mark.fast

_WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
_PAUSE = "pr:pause-ci"
_OTHER = "area:docs"
_PR_TYPES = ["opened", "synchronize", "reopened", "ready_for_review", "labeled", "unlabeled"]
_GATE_LOOP_RE = re.compile(r"for gate in ((?:\"[^\"]+\"\s*)+);")
_STATUS_FUNCTIONS = ("always()", "cancelled()", "failure()")


def _load(name: str) -> dict[Any, Any]:
    data: dict[Any, Any] = yaml.safe_load((_WORKFLOWS / name).read_text(encoding="utf-8"))
    return data


def _on(workflow: dict[Any, Any]) -> dict[str, Any]:
    on = workflow.get("on", workflow.get(True))
    return on if isinstance(on, dict) else {}


def _required_check_names() -> set[str]:
    match = _GATE_LOOP_RE.search((_WORKFLOWS / "pr-pause-ci.yml").read_text(encoding="utf-8"))
    assert match is not None, "pr-pause-ci.yml no longer lists the required gates in a `for gate in ...` loop"
    return set(re.findall(r'"([^"]+)"', match.group(1)))


_SYNCHRONIZE = github_context("pull_request", action="synchronize")


def _producers() -> dict[str, tuple[str, str]]:
    """Required check name -> (workflow file, job id), resolving each job's name on a normal PR event."""
    found: dict[str, tuple[str, str]] = {}
    for path in sorted(_WORKFLOWS.glob("*.yml")):
        for job_id, job in (_load(path.name).get("jobs") or {}).items():
            name = str(job.get("name", ""))
            if re.search(r"\b(matrix|inputs|needs|strategy)\.", name):
                continue  # a per-leaf or per-caller name is never a fixed required check
            resolved = interpolate(name, _SYNCHRONIZE)
            if resolved in _required_check_names():
                found[resolved] = (path.name, job_id)
    return found


def _producer_files() -> list[str]:
    return sorted({workflow for workflow, _ in _producers().values()})


def _label_triggered_files() -> list[str]:
    found = []
    for path in sorted(_WORKFLOWS.glob("*.yml")):
        pull_request = _on(_load(path.name)).get("pull_request") or {}
        if {"labeled", "unlabeled"} & set(pull_request.get("types") or []):
            found.append(path.name)
    return found


def _self_starting_jobs(workflow: str) -> list[tuple[str, dict[str, Any]]]:
    """Jobs that can run although their needs skipped: no ``needs``, or a status function in ``if:``."""
    jobs = _load(workflow)["jobs"]
    return [(job_id, job) for job_id, job in jobs.items() if not job.get("needs") or any(function in str(job.get("if", "")) for function in _STATUS_FUNCTIONS)]


def _runs(job: dict[str, Any], context: dict[str, Any]) -> bool:
    return bool(evaluate(str(job.get("if", "true")), {**context, "true": True}))


def _cases() -> list[tuple[str, str, dict[str, Any]]]:
    return [(workflow, job_id, job) for workflow in _producer_files() for job_id, job in _self_starting_jobs(workflow)]


_CASE_IDS = [f"{workflow}:{job_id}" for workflow, job_id, _ in _cases()]


# --- triggers ------------------------------------------------------------------------------


def test_the_required_producers_are_the_three_gate_workflows() -> None:
    assert set(_producers()) == _required_check_names() == {"router gate", "CI Modules gate", "Clean install verification"}
    assert _producer_files() == ["ci-modules.yml", "ci-quality.yml", "ci-router.yml"]


@pytest.mark.parametrize("workflow", _producer_files())
def test_required_producers_trigger_on_label_events(workflow: str) -> None:
    on = _on(_load(workflow))
    assert on["pull_request"]["types"] == _PR_TYPES
    assert "merge_group" in on and "push" in on, "merge_group and push triggers are unchanged"


def test_only_the_required_producers_trigger_on_label_events() -> None:
    """An optional workflow on a label trigger would start a run for every label on every PR."""
    assert _label_triggered_files() == _producer_files()


# --- jobs ----------------------------------------------------------------------------------


@pytest.mark.parametrize(("workflow", "job_id", "job"), _cases(), ids=_CASE_IDS)
def test_an_unrelated_label_event_skips_every_self_starting_job(workflow: str, job_id: str, job: dict[str, Any]) -> None:
    for action in ("labeled", "unlabeled"):
        for labels in ([_OTHER], [_OTHER, _PAUSE], []):
            context = github_context("pull_request", action=action, label=_OTHER, labels=labels)
            assert not _runs(job, context), f"{workflow}:{job_id} runs on `{action}` of an unrelated label (labels={labels})"


@pytest.mark.parametrize(("workflow", "job_id", "job"), _cases(), ids=_CASE_IDS)
def test_a_pause_label_event_on_a_closed_pr_skips_every_self_starting_job(workflow: str, job_id: str, job: dict[str, Any]) -> None:
    for action, labels in (("unlabeled", []), ("labeled", [_PAUSE])):
        context = github_context("pull_request", action=action, label=_PAUSE, labels=labels, state="closed")
        assert not _runs(job, context), f"{workflow}:{job_id} runs on `{action}` of {_PAUSE} on a closed PR"


@pytest.mark.parametrize(("workflow", "job_id", "job"), _cases(), ids=_CASE_IDS)
def test_removing_the_pause_label_runs_like_a_push_to_the_pr(workflow: str, job_id: str, job: dict[str, Any]) -> None:
    for labels in ([], [_OTHER]):
        unlabeled = github_context("pull_request", action="unlabeled", label=_PAUSE, labels=labels)
        synchronize = github_context("pull_request", action="synchronize", labels=labels)
        assert _runs(job, unlabeled) == _runs(job, synchronize) is True


@pytest.mark.parametrize(("workflow", "job_id", "job"), _cases(), ids=_CASE_IDS)
def test_adding_the_pause_label_re_reports_paused(workflow: str, job_id: str, job: dict[str, Any]) -> None:
    labeled = github_context("pull_request", action="labeled", label=_PAUSE, labels=[_PAUSE])
    synchronize_paused = github_context("pull_request", action="synchronize", labels=[_PAUSE])
    assert _runs(job, labeled) == _runs(job, synchronize_paused)
    if job_id in {producer_job for _, producer_job in _producers().values()}:
        assert _runs(job, labeled), f"{job_id} must run (and fail) under the pause label: a skipped required check passes"


@pytest.mark.parametrize(("workflow", "job_id", "job"), _cases(), ids=_CASE_IDS)
@pytest.mark.parametrize(
    "context",
    [
        github_context("push", ref="refs/heads/main"),
        github_context("merge_group", action="checks_requested", ref="refs/heads/gh-readonly-queue/main/pr-7-abc"),
        github_context("workflow_dispatch", ref="refs/heads/main"),
    ],
    ids=["push", "merge_group", "workflow_dispatch"],
)
def test_non_pr_events_are_unchanged(workflow: str, job_id: str, job: dict[str, Any], context: dict[str, Any]) -> None:
    assert _runs(job, context), f"{workflow}:{job_id} must still run on {context['github.event_name']}"


# --- required check names ------------------------------------------------------------------


@pytest.mark.parametrize("check", sorted(_required_check_names()))
def test_a_no_op_run_never_posts_a_required_check_name(check: str) -> None:
    """A skipped job posts a check run under its name, and a skipped required check passes."""
    workflow, job_id = _producers()[check]
    name = str(_load(workflow)["jobs"][job_id]["name"])
    for action in ("labeled", "unlabeled"):
        for label, state in ((_OTHER, "open"), (_PAUSE, "closed")):
            no_op = interpolate(name, github_context("pull_request", action=action, label=label, state=state))
            assert no_op != check and check in no_op, f"{workflow}:{job_id} posts {no_op!r} on a no-op label event"
    for context in (
        github_context("pull_request", action="unlabeled", label=_PAUSE),
        github_context("pull_request", action="labeled", label=_PAUSE, labels=[_PAUSE]),
        github_context("pull_request", action="opened"),
        github_context("push", ref="refs/heads/main"),
        github_context("merge_group", action="checks_requested"),
    ):
        assert interpolate(name, context) == check


# --- concurrency ---------------------------------------------------------------------------


def _group(workflow: str, context: dict[str, Any]) -> str:
    return interpolate(str(_load(workflow)["concurrency"]["group"]), context)


@pytest.mark.parametrize("workflow", _producer_files())
def test_a_no_op_run_never_shares_the_pr_concurrency_group(workflow: str) -> None:
    real = _group(workflow, github_context("pull_request", action="synchronize", run_id=1))
    for action in ("labeled", "unlabeled"):
        first = _group(workflow, github_context("pull_request", action=action, label=_OTHER, run_id=2))
        second = _group(workflow, github_context("pull_request", action=action, label=_OTHER, run_id=3))
        closed = _group(workflow, github_context("pull_request", action=action, label=_PAUSE, run_id=4, state="closed"))
        assert len({real, first, second, closed}) == 4


@pytest.mark.parametrize("workflow", _producer_files())
def test_a_pause_label_event_shares_the_pr_concurrency_group(workflow: str) -> None:
    """Removing the label supersedes the paused run; adding it cancels the in-flight run."""
    real = _group(workflow, github_context("pull_request", action="synchronize", run_id=1))
    for action in ("labeled", "unlabeled"):
        assert _group(workflow, github_context("pull_request", action=action, label=_PAUSE, run_id=2)) == real


@pytest.mark.parametrize(
    ("workflow", "push_group"),
    [("ci-router.yml", "ci-router-" + "a" * 40), ("ci-modules.yml", "ci-modules-refs/heads/main"), ("ci-quality.yml", "ci-quality-refs/heads/main")],
)
def test_push_and_merge_group_concurrency_is_unchanged(workflow: str, push_group: str) -> None:
    assert _group(workflow, github_context("push", ref="refs/heads/main")) == push_group
    queue_ref = "refs/heads/gh-readonly-queue/main/pr-7-abc"
    prefix = workflow.removesuffix(".yml")
    assert _group(workflow, github_context("merge_group", action="checks_requested", ref=queue_ref)) == f"{prefix}-{queue_ref}"


# --- the pause workflow --------------------------------------------------------------------


def _workflow_names(files: list[str]) -> list[str]:
    return sorted(str(_load(name)["name"]) for name in files)


def _pause_env(job_id: str) -> dict[str, str]:
    return {str(k): str(v) for k, v in _load("pr-pause-ci.yml")["jobs"][job_id]["env"].items()}


@pytest.mark.parametrize("job_id", ["pause", "resume"])
def test_the_pause_workflow_names_the_label_triggered_workflows(job_id: str) -> None:
    env = _pause_env(job_id)
    assert sorted(json.loads(env["LABEL_TRIGGERED_WORKFLOWS"])) == _workflow_names(_label_triggered_files())
    script = "\n".join(str(step.get("run", "")) for step in _load("pr-pause-ci.yml")["jobs"][job_id]["steps"])
    assert '--argjson own "$LABEL_TRIGGERED_WORKFLOWS"' in script


def _jq(program: str, runs: list[dict[str, Any]], **args: str) -> list[int]:
    jq = shutil.which("jq")
    if jq is None:
        pytest.skip("jq is not installed (it is preinstalled on the ubuntu-24.04 runner)")
    env = _pause_env("pause")
    command = [jq, "-r", "--argjson", "own", env["LABEL_TRIGGERED_WORKFLOWS"]]
    for name, value in args.items():
        command += ["--arg", name, value]
    out = subprocess.run([*command, program], input=json.dumps(runs), capture_output=True, text=True, check=True).stdout
    return [int(line) for line in out.split()]


_LABELED_AT = "2026-11-01T15:55:00Z"


def test_the_pause_job_cancels_old_runs_but_spares_the_label_triggered_ones() -> None:
    runs = [
        {"databaseId": 1, "workflowName": "CI Router", "createdAt": "2026-11-01T15:50:00Z"},  # before the label
        {"databaseId": 2, "workflowName": "CI Router", "createdAt": "2026-11-01T15:55:00Z"},  # the label's own run
        {"databaseId": 3, "workflowName": "CI Quality", "createdAt": "2026-11-01T15:55:02Z"},
        {"databaseId": 4, "workflowName": "Packs", "createdAt": "2026-11-01T15:55:03Z"},  # optional: always cancelled
        {"databaseId": 5, "workflowName": "CI", "createdAt": "2026-11-01T15:56:00Z"},  # a prefix is no match
    ]
    assert _jq(_pause_env("pause")["CANCEL_FILTER"], runs, labeled_at=_LABELED_AT) == [1, 4, 5]
    assert _pause_env("pause")["LABELED_AT"] == "${{ github.event.pull_request.updated_at }}"


def test_the_resume_job_never_re_runs_the_label_triggered_workflows() -> None:
    runs = [
        {"databaseId": 1, "workflowName": "CI Router", "event": "pull_request"},
        {"databaseId": 2, "workflowName": "CI Modules", "event": "pull_request"},
        {"databaseId": 3, "workflowName": "Packs", "event": "pull_request"},
        {"databaseId": 4, "workflowName": "Packs", "event": "push"},
    ]
    assert _jq(_pause_env("resume")["RERUN_FILTER"], runs) == [3]


# --- followers -----------------------------------------------------------------------------


def _aggregate_group(conclusion: str, run_id: int) -> str:
    context = {
        "github.event.workflow_run.head_branch": "feature",
        "github.event.workflow_run.conclusion": conclusion,
        "github.event.workflow_run.id": run_id,
        "github.ref": "refs/heads/main",
    }
    return interpolate(str(_load("ci-aggregate.yml")["concurrency"]["group"]), context)


def test_ci_aggregate_never_lets_a_skipped_source_cancel_the_real_aggregate() -> None:
    assert _aggregate_group("success", 1) == _aggregate_group("failure", 2) == "ci-aggregate-feature"
    assert _aggregate_group("skipped", 3) not in {"ci-aggregate-feature", _aggregate_group("skipped", 4)}


def _aggregate_context(conclusion: str, collect_result: str) -> dict[str, Any]:
    collect_ran = collect_result == "success"
    return {
        "github.repository": "spec-kitty/spec-kitty",
        "github.event_name": "workflow_run",
        "github.event.workflow_run.event": "pull_request",
        "github.event.workflow_run.conclusion": conclusion,
        "github.event.workflow_run.head_repository.full_name": "spec-kitty/spec-kitty",
        "needs.collect.result": collect_result,
        "needs.collect.outputs.mode": "pr" if collect_ran else "",
        "needs.collect.outputs.complete": "true" if collect_ran else "",
        "needs.collect.outputs.coverage": "true" if collect_ran else "",
        "needs.diff-cover.result": "success" if collect_ran else "skipped",
        "true": True,
    }


def test_ci_aggregate_skips_every_job_for_a_skipped_source() -> None:
    jobs = _load("ci-aggregate.yml")["jobs"]
    skipped = _aggregate_context("skipped", "skipped")
    real = _aggregate_context("success", "success")
    for job_id, job in jobs.items():
        assert not evaluate(str(job.get("if", "true")), skipped), f"ci-aggregate {job_id} runs for a skipped (no-op) source"
    assert evaluate(str(jobs["aggregate-gate"]["if"]), real), "aggregate-gate must still run for a real source"


def test_fleet_verdict_knows_the_label_triggered_workflows() -> None:
    assert sorted(fleet_verdict.LABEL_TRIGGERED_WORKFLOWS) == _label_triggered_files()


def _run(name: str, run_id: int, conclusion: str) -> dict[str, Any]:
    head = "a" * 40
    repository = "spec-kitty/spec-kitty"
    return {
        "id": run_id,
        "run_attempt": 1,
        "workflow_id": 1,
        "path": f".github/workflows/{name}",
        "repository": {"full_name": repository},
        "head_sha": head,
        "event": "pull_request",
        "status": "completed",
        "conclusion": conclusion,
        "pull_requests": [{"number": 7, "head": {"sha": head}, "base": {"repo": {"url": f"https://api.github.com/repos/{repository}"}}}],
    }


@pytest.mark.parametrize("name", _producer_files())
def test_fleet_verdict_ignores_a_skipped_label_triggered_run(name: str) -> None:
    real, no_op = _run(name, 10, "failure"), _run(name, 11, "skipped")
    chosen = fleet_verdict.latest_run([real, no_op], workflow_id=1, repository="spec-kitty/spec-kitty", head="a" * 40, number=7, name=name)
    assert chosen == real


def test_fleet_verdict_still_reads_a_skipped_run_of_other_workflows() -> None:
    real, skipped = _run("packs.yml", 10, "success"), _run("packs.yml", 11, "skipped")
    chosen = fleet_verdict.latest_run([real, skipped], workflow_id=1, repository="spec-kitty/spec-kitty", head="a" * 40, number=7, name="packs.yml")
    assert chosen == skipped
