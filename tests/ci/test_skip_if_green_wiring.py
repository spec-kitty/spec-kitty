"""FR-011 skip-if-green wiring (WP18): the three selection jobs suppress their path-filter step.

On a ``pull_request`` ``ready_for_review`` event whose tested key already has a green run,
``scripts/ci/green_match.py decide`` (WP16) answers ``skip=true``.  Router ``changes``, Packs
``changes`` and CI Modules ``generate-matrix`` each run it as a first step and fold the answer
into **steps**, never into a job ``if:`` / ``needs:`` / ``outputs:`` expression (C-003: the
event-level suppression is not a third CI path routing authority; amendment A4).

Every pin here is derived, not hand-listed:

* the steps that must be suppressed are derived from each job's ``outputs:`` (transitively
  through step ``env``), so a future output-producing step cannot silently escape the guard;
* step and job ``if:`` expressions are evaluated semantically, never matched as text;
* the path-gated job set of the skip-context golden test is derived from the ``if:`` text.
"""

from __future__ import annotations

import copy
import os
import re
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.ci._gh_if import GhIfEvaluator, eval_gh_if, strip_expr_wrapper, tokenize_gh_if

pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"

#: (workflow file, selection job id) -- the three jobs that carry the ``green`` step.
SELECTION_JOBS = [
    ("ci-router.yml", "changes"),
    ("packs.yml", "changes"),
    ("ci-modules.yml", "generate-matrix"),
]
#: Workflows whose selection-job outputs are produced by suppressible steps. CI Modules'
#: output step (``build``) is the documented exception: it folds ``GREEN_SKIP`` itself.
FILTER_FED_WORKFLOWS = [("ci-router.yml", "changes"), ("packs.yml", "changes")]
#: The one step allowed to stay unguarded because it forces the empty selection itself.
GREEN_SKIP_FOLD_STEPS = {("ci-modules.yml", "generate-matrix"): "build"}

UPLOAD_ARTIFACT_PIN = "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"  # v7.0.1
MARKER_EXPR = "${{ steps.green.outputs.marker }}"
SKIP_GUARD_KEY = "steps.green.outputs.skip"

_STEP_REF = re.compile(r"steps\.([\w-]+)\.outputs")
_STEP_COND_RE = re.compile(r"([A-Za-z0-9_.-]+)\s*(==|!=)\s*'([^']*)'")


# --- loading ---------------------------------------------------------------------------------


def _load(workflow: str) -> dict[str, Any]:
    return dict(yaml.safe_load((WORKFLOWS / workflow).read_text(encoding="utf-8")))


def _job(workflow: str, job: str) -> dict[str, Any]:
    return dict(_load(workflow)["jobs"][job])


def _triggers(workflow: Mapping[Any, Any]) -> dict[str, Any]:
    # PyYAML parses the bare ``on:`` key as the boolean True (YAML 1.1).
    return dict(workflow.get("on") or workflow[True])


def _steps_by_id(job: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {step["id"]: step for step in job["steps"] if "id" in step}


# --- a small evaluator for step ``if:`` expressions (reuses the router golden evaluator) -----


class _StepIfEvaluator(GhIfEvaluator):
    """``GhIfEvaluator``'s recursive descent, over ``<context path> ==/!= '<literal>'`` terms."""

    def __init__(self, tokens: list[str], values: Mapping[str, str]) -> None:
        super().__init__(tokens, {})
        self._values = values

    def _eval_condition(self, text: str) -> bool:
        match = _STEP_COND_RE.fullmatch(text.strip())
        assert match, f"unmodeled step if: condition fragment: {text!r}"
        key, op, literal = match.groups()
        assert key in self._values, f"step if: context does not model {key!r}"
        return (self._values[key] == literal) == (op == "==")


def _eval_step_if(raw_if: str, values: Mapping[str, str]) -> bool:
    return _StepIfEvaluator(tokenize_gh_if(strip_expr_wrapper(raw_if)), values).evaluate()


#: Context under which a path-gated step would otherwise run (a normal pull request).
_RUNNING_CONTEXT = {
    "steps.resolve-mode.outputs.mode": "pr",
    "steps.resolve-mode.outputs.selection-forced-full": "false",
}


def _runs_when(step: Mapping[str, Any], green_skip: str) -> bool:
    raw = step.get("if")
    return True if raw is None else _eval_step_if(str(raw), {**_RUNNING_CONTEXT, SKIP_GUARD_KEY: green_skip})


def _suppressed_on_skip(step: Mapping[str, Any]) -> bool:
    """Off on ``skip=true``, and still on for ``skip=false`` and for a missing output."""
    return (not _runs_when(step, "true")) and _runs_when(step, "false") and _runs_when(step, "")


# --- the suppression checker (a pure helper with a positive control below) -------------------


def _output_step_ids(job: Mapping[str, Any], by_id: Mapping[str, Mapping[str, Any]], stop: frozenset[str]) -> set[str]:
    """Step ids the job's ``outputs:`` depend on, transitively through step ``env`` values."""
    found: set[str] = set()
    pending = [match for value in job.get("outputs", {}).values() for match in _STEP_REF.findall(str(value))]
    while pending:
        step_id = pending.pop()
        if step_id in found:
            continue
        found.add(step_id)
        if step_id in stop or step_id not in by_id:
            continue
        env = by_id[step_id].get("env") or {}
        pending.extend(match for value in env.values() for match in _STEP_REF.findall(str(value)))
    return found


def _always_guarded_ids(job: Mapping[str, Any]) -> set[str]:
    """Every path-filter step is guarded regardless of what feeds the outputs."""
    return {
        str(step.get("id") or step.get("name"))
        for step in job["steps"]
        if str(step.get("uses", "")).startswith("dorny/paths-filter") or step.get("id") == "changed-files"
    }


def unsuppressed_steps(job: Mapping[str, Any], exempt: frozenset[str] = frozenset()) -> list[str]:
    """Output-producing / path-filter steps that still run when ``green`` says skip."""
    by_id = _steps_by_id(job)
    required = (_output_step_ids(job, by_id, exempt) | _always_guarded_ids(job)) - {"green"} - exempt
    return sorted(step_id for step_id in required if step_id in by_id and not _suppressed_on_skip(by_id[step_id]))


def _exempt(workflow: str, job: str) -> frozenset[str]:
    step = GREEN_SKIP_FOLD_STEPS.get((workflow, job))
    return frozenset({step}) if step else frozenset()


# --- a tiny GitHub expression evaluator for the job ``outputs:`` fold ------------------------

_EXPR_TOKEN = re.compile(r"\s*(\|\||&&|==|!=|\(|\)|'[^']*'|[A-Za-z0-9_.\-]+)")


class _OutputExpr:
    """``||`` / ``&&`` / ``==`` over string literals and context references (GitHub semantics:
    ``a && b`` is ``b`` when ``a`` is truthy else ``a``; ``a || b`` is ``a`` when truthy else
    ``b``; the empty string is falsy)."""

    def __init__(self, text: str, context: Mapping[str, str]) -> None:
        self._tokens = _EXPR_TOKEN.findall(text)
        assert "".join(self._tokens).replace(" ", "") == re.sub(r"\s+", "", text), f"unlexable expression: {text!r}"
        self._pos = 0
        self._context = context

    def evaluate(self) -> str:
        value = self._or()
        assert self._pos == len(self._tokens), f"unconsumed tokens: {self._tokens[self._pos :]!r}"
        return str(value)

    def _peek(self) -> str | None:
        return self._tokens[self._pos] if self._pos < len(self._tokens) else None

    def _take(self) -> str:
        token = str(self._tokens[self._pos])
        self._pos += 1
        return token

    def _or(self) -> str | bool:
        value = self._and()
        while self._peek() == "||":
            self._take()
            right = self._and()
            value = value if value else right
        return value

    def _and(self) -> str | bool:
        value = self._cmp()
        while self._peek() == "&&":
            self._take()
            right = self._cmp()
            value = right if value else value
        return value

    def _cmp(self) -> str | bool:
        left = self._operand()
        if self._peek() in {"==", "!="}:
            op = self._take()
            right = self._operand()
            return (left == right) == (op == "==")
        return left

    def _operand(self) -> str | bool:
        token = self._take()
        if token == "(":
            value = self._or()
            assert self._take() == ")"
            return value
        if token.startswith("'"):
            return token[1:-1]
        assert token in self._context, f"expression context does not model {token!r}"
        return self._context[token]


def _skip_context_outputs(job: Mapping[str, Any]) -> dict[str, str]:
    """Each job output on a skip run: every step output is the empty string (steps skipped),
    on a ``pull_request`` event whose ``inputs.mode`` is empty."""
    context: dict[str, str] = {"inputs.mode": "", "github.event_name": "pull_request"}
    for value in job["outputs"].values():
        for ref in re.findall(r"steps\.[\w-]+\.outputs\.[\w-]+", str(value)):
            context[ref] = ""
    return {name: _OutputExpr(strip_expr_wrapper(str(value)), context).evaluate() for name, value in job["outputs"].items()}


# --- the checks ------------------------------------------------------------------------------


@pytest.mark.parametrize(("workflow", "job_id"), SELECTION_JOBS)
def test_green_step_runs_first_after_checkout(workflow: str, job_id: str) -> None:
    steps = _job(workflow, job_id)["steps"]
    assert str(steps[0].get("uses", "")).startswith("actions/checkout@"), "checkout must stay the first step"
    green = steps[1]
    assert green.get("id") == "green", "the green step must be the first step after checkout"
    assert "if" not in green, "the green step must always run"
    assert f"python3 scripts/ci/green_match.py decide --workflow {workflow}" in green["run"]
    assert green["continue-on-error"] is True
    assert green["env"]["GH_TOKEN"] == "${{ github.token }}"
    assert '--marker-dir "$RUNNER_TEMP/green-match"' in green["run"]


@pytest.mark.parametrize(("workflow", "job_id"), SELECTION_JOBS)
def test_selection_job_grants_actions_read(workflow: str, job_id: str) -> None:
    # A job-level block REPLACES the workflow-level grant, so contents is restated.
    assert _job(workflow, job_id).get("permissions") == {"contents": "read", "actions": "read"}


@pytest.mark.parametrize(("workflow", "job_id"), SELECTION_JOBS)
def test_every_output_producing_step_is_suppressed_on_skip(workflow: str, job_id: str) -> None:
    job = _job(workflow, job_id)
    assert unsuppressed_steps(job, _exempt(workflow, job_id)) == []


@pytest.mark.parametrize(("workflow", "job_id"), FILTER_FED_WORKFLOWS)
def test_the_derived_suppression_set_is_not_vacuous(workflow: str, job_id: str) -> None:
    job = _job(workflow, job_id)
    derived = _output_step_ids(job, _steps_by_id(job), frozenset()) | _always_guarded_ids(job)
    assert "filter" in derived
    assert len(derived - {"green"}) >= 2, f"{workflow}: the derivation found too few steps to be meaningful"


def test_the_corpus_selection_step_is_derived_and_guarded() -> None:
    job = _job("packs.yml", "changes")
    assert "corpus" in _output_step_ids(job, _steps_by_id(job), frozenset())
    assert _suppressed_on_skip(_steps_by_id(job)["corpus"])


def test_ci_modules_changed_files_is_guarded_and_build_folds_green_skip() -> None:
    job = _job("ci-modules.yml", "generate-matrix")
    by_id = _steps_by_id(job)
    changed = by_id["changed-files"]
    assert _suppressed_on_skip(changed)
    # Still off in the contexts that already turned it off, still on when it ran before.
    assert not _eval_step_if(str(changed["if"]), {**_RUNNING_CONTEXT, SKIP_GUARD_KEY: "false", "steps.resolve-mode.outputs.mode": "full"})
    assert not _eval_step_if(
        str(changed["if"]),
        {**_RUNNING_CONTEXT, SKIP_GUARD_KEY: "false", "steps.resolve-mode.outputs.selection-forced-full": "true"},
    )
    assert by_id["build"]["env"]["GREEN_SKIP"] == "${{ steps.green.outputs.skip }}"
    assert "if" not in by_id["build"], "build must still run on a skip, to publish selected-modules = []"


@pytest.mark.parametrize(("workflow", "job_id"), SELECTION_JOBS)
def test_marker_artifact_is_uploaded(workflow: str, job_id: str) -> None:
    steps = _job(workflow, job_id)["steps"]
    green_index = next(index for index, step in enumerate(steps) if step.get("id") == "green")
    uploads = [(index, step) for index, step in enumerate(steps) if step.get("with", {}).get("name") == MARKER_EXPR]
    assert len(uploads) == 1, "exactly one marker upload step"
    index, upload = uploads[0]
    assert index > green_index
    assert upload["uses"].startswith(UPLOAD_ARTIFACT_PIN)
    # The upload runs for a marker (executing PR run or skip run) and for nothing else.
    marker_condition = {"steps.green.outputs.marker": "x"}
    assert _eval_step_if(str(upload["if"]), marker_condition) is True
    assert _eval_step_if(str(upload["if"]), {"steps.green.outputs.marker": ""}) is False
    with_ = upload["with"]
    # BY OUTPUT NAME, never the whole directory: a stale JSON body must not ride along.
    assert with_["path"] == f"${{{{ runner.temp }}}}/green-match/{MARKER_EXPR}.json"
    assert with_["retention-days"] == 30
    assert with_["if-no-files-found"] == "error"
    # A re-run attempt re-uploads under the same name; the default (false) would fail it.
    assert with_["overwrite"] is True


def test_ci_modules_selected_modules_upload_survives_a_re_run() -> None:
    steps = _job("ci-modules.yml", "generate-matrix")["steps"]
    upload = next(step for step in steps if step.get("with", {}).get("name") == "selected-modules")
    assert "if" not in upload, "selected-modules is published on skip runs too (holds [])"
    assert upload["with"]["overwrite"] is True


@pytest.mark.parametrize(("workflow", "job_id"), SELECTION_JOBS)
def test_no_job_condition_references_the_green_step(workflow: str, job_id: str) -> None:
    """C-003 / ``gate_selection._GROUP_REF`` safety: no job-level ``if:`` / ``needs`` / ``outputs``."""
    for name, job in _load(workflow)["jobs"].items():
        for field in ("if", "needs", "outputs"):
            text = str(job.get(field, ""))
            assert "green" not in text and "outputs.skip" not in text, f"{workflow} job {name!r} {field}: references the green step"
    for step in _job(workflow, job_id)["steps"]:
        if str(step.get("uses", "")).startswith("dorny/paths-filter"):
            assert "green" not in step["with"]["filters"], "never put green/skip into a filter block"


@pytest.mark.parametrize(("workflow", "_job_id"), SELECTION_JOBS)
def test_ready_for_review_stays_a_trigger(workflow: str, _job_id: str) -> None:
    assert "ready_for_review" in _triggers(_load(workflow))["pull_request"]["types"]


# --- skip-context goldens --------------------------------------------------------------------


def _gated_jobs(workflow: Mapping[str, Any], selection_job: str) -> dict[str, str]:
    """Jobs whose ``if:`` reads ``needs.<selection_job>.outputs.*`` -- derived from the text."""
    marker = f"needs.{selection_job}.outputs."
    return {name: str(job["if"]) for name, job in workflow["jobs"].items() if marker in str(job.get("if", ""))}


def _context_from_outputs(selection_job: str, outputs: Mapping[str, str]) -> dict[str, bool]:
    return {f"{selection_job}.{name}": value == "true" for name, value in outputs.items()}


@pytest.mark.parametrize(("workflow", "job_id"), FILTER_FED_WORKFLOWS)
def test_skip_leaves_every_selection_output_empty(workflow: str, job_id: str) -> None:
    outputs = _skip_context_outputs(_job(workflow, job_id))
    assert outputs, "non-vacuity"
    assert set(outputs.values()) == {""}, f"{workflow}: a selection output survives a skip run: {outputs}"


def test_router_skip_context_turns_every_path_gated_job_off() -> None:
    workflow = _load("ci-router.yml")
    gated = _gated_jobs(workflow, "changes")
    assert {"architectural-heavy", "tests-docs", "tests-e2e", "tests-corpus-blocking"} <= set(gated)
    context = _context_from_outputs("changes", _skip_context_outputs(workflow["jobs"]["changes"]))

    # prose-scan is NOT suppressed (it computes prose_only itself): evaluate both ways.
    still_on_not_prose = {name for name, raw in gated.items() if eval_gh_if(raw, {**context, "prose-scan.prose_only": False})}
    assert still_on_not_prose == set(), f"a path-gated router job survives a skip run: {still_on_not_prose}"

    # D-35 residual, pinned EXACTLY: on a prose-only skip run, `tests-docs` (docs || prose_only)
    # still runs because prose-scan is not suppressed. Any new leak reds this test instead of
    # joining a silent allowlist.
    still_on_prose = {name for name, raw in gated.items() if eval_gh_if(raw, {**context, "prose-scan.prose_only": True})}
    assert still_on_prose == {"tests-docs"}


def test_router_always_on_lanes_are_unaffected_by_a_skip() -> None:
    """The always-on lanes (incl. WP12's `architectural-fast`) stay on the fork guard only."""
    jobs = _load("ci-router.yml")["jobs"]
    always_on = [
        "prose-scan",
        "ruff",
        "commit-msg",
        "markdownlint",
        "uv-lock",
        "import-linter",
        "regen-check",
        "terminology",
        "docs-lint",
        "layer-rules",
        "archive-freeze",
        "architectural-fast",
    ]
    guard = jobs["ruff"]["if"]
    for name in always_on:
        assert "needs" not in jobs[name], f"{name} must not depend on the selection job"
        assert jobs[name]["if"] == guard, f"{name} must carry only the fork guard"
        assert "green" not in str(jobs[name]), f"{name} must not read the green step"


def test_packs_skip_context_turns_every_path_gated_job_off() -> None:
    workflow = _load("packs.yml")
    gated = _gated_jobs(workflow, "changes")
    assert {"built-in-regen-check", "built-in-corpus-suite", "internal-org-validate"} <= set(gated)
    context = _context_from_outputs("changes", _skip_context_outputs(workflow["jobs"]["changes"]))
    leaked = {name for name, raw in gated.items() if eval_gh_if(raw, context)}
    assert leaked == set(), f"a path-gated packs job survives a skip run: {leaked}"


def test_ci_modules_skip_turns_the_test_matrix_off() -> None:
    jobs = _load("ci-modules.yml")["jobs"]
    # The hyphenated `has-selection` output is outside the shared evaluator's grammar (and the
    # file is not owned here), so pin the exact expression: false for '' and for 'false'.
    assert jobs["test"]["if"] == "${{ needs.generate-matrix.outputs.has-selection == 'true' }}"
    assert _eval_step_if("steps.build.outputs.has-selection == 'true'", {"steps.build.outputs.has-selection": "false"}) is False


# --- the GREEN_SKIP fold, executed -----------------------------------------------------------


def _run_build_step(tmp_path: Path, green_skip: str) -> tuple[str, str]:
    """Execute the real `build` step script; return (selected-modules.json, GITHUB_OUTPUT)."""
    build = _steps_by_id(_job("ci-modules.yml", "generate-matrix"))["build"]
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "ci-module-registry.yml").write_text((ROOT / ".github" / "ci-module-registry.yml").read_text(encoding="utf-8"), encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    # A wrapper, not a symlink: a symlinked venv interpreter loses its pyvenv.cfg (and the extras).
    shim = bin_dir / "python3"
    shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', encoding="utf-8")
    shim.chmod(0o755)
    github_output = tmp_path / "github_output"
    github_output.write_text("", encoding="utf-8")
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "MODE": "pr",
        "SELECTION_FORCED_FULL": "false",
        "CHANGED_FILES": '["src/specify_cli/status/store.py"]',
        "CHANGED_FILTER_OUTCOME": "success",
        "GREEN_SKIP": green_skip,
        "PYTHONPATH": str(ROOT),
        "GITHUB_OUTPUT": str(github_output),
    }
    subprocess.run(["bash", "-c", build["run"]], cwd=tmp_path, env=env, check=True, capture_output=True, text=True)
    selected = (tmp_path / "out" / "ci-modules" / "selected-modules.json").read_text(encoding="utf-8")
    return selected, github_output.read_text(encoding="utf-8")


def test_green_skip_forces_an_empty_selection_but_still_publishes_it(tmp_path: Path) -> None:
    selected, outputs = _run_build_step(tmp_path, "true")
    assert selected == "[]"
    assert "has-selection=false" in outputs
    assert "matrix=[]" in outputs


@pytest.mark.parametrize("green_skip", ["false", ""])
def test_a_run_decision_leaves_the_selection_untouched(tmp_path: Path, green_skip: str) -> None:
    selected, outputs = _run_build_step(tmp_path, green_skip)
    assert selected != "[]", "control: the same diff selects modules when there is no skip"
    assert "has-selection=true" in outputs


# --- positive controls (Standing Order #5) ---------------------------------------------------


def _without_if(job: Mapping[str, Any], step_id: str) -> dict[str, Any]:
    mutated = copy.deepcopy(dict(job))
    next(step for step in mutated["steps"] if step.get("id") == step_id).pop("if", None)
    return mutated


def test_suppression_checker_catches_an_unguarded_step() -> None:
    job = _job("ci-router.yml", "changes")
    assert unsuppressed_steps(job) == []
    assert "filter" in unsuppressed_steps(_without_if(job, "filter"))
    assert "unmatched" in unsuppressed_steps(_without_if(job, "unmatched"))


def test_suppression_checker_catches_a_condition_that_is_not_the_skip_guard() -> None:
    job = copy.deepcopy(_job("ci-router.yml", "changes"))
    step = _steps_by_id(job)["filter"]
    step["if"] = "steps.green.outputs.skip == 'true'"  # inverted: runs ONLY on skip
    assert "filter" in unsuppressed_steps(job)
    step["if"] = "steps.green.outputs.skip != 'false'"  # off for a missing output: over-suppressed
    assert "filter" in unsuppressed_steps(job)


def test_suppression_checker_catches_an_unguarded_packs_corpus_step() -> None:
    job = _job("packs.yml", "changes")
    assert unsuppressed_steps(job) == []
    assert "corpus" in unsuppressed_steps(_without_if(job, "corpus"))


def test_output_fold_evaluator_is_not_vacuous() -> None:
    job = copy.deepcopy(_job("ci-router.yml", "changes"))
    job["outputs"]["docs"] = "${{ (inputs.mode == 'full' || steps.unmatched.outputs.unmatched == 'true') && 'true' || 'true' }}"
    assert _skip_context_outputs(job)["docs"] == "true"
