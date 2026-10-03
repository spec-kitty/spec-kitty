"""ATDD pinning tests for ``ci-nightly.yml``'s exit-code honesty (#5034).

Two adversarial-squad findings on the nightly workflow's escalation/fail-loud
steps:

- **FIND-1**: every escalation/fail-loud step computes its conclusion with a
  pattern like ``if [ "${PERF_EXIT:-0}" -ne 0 ] && [ "${PERF_EXIT:-0}" -ne 5
  ]; then conclusion=failure; else conclusion=success; fi``. The exit
  variable is written by the suite step's OWN ``code=$?; echo "PERF_EXIT=$code"
  >> $GITHUB_ENV`` line, which only runs if that step gets to finish. If the
  job is killed by its ``timeout-minutes`` cap mid-run (the #4865
  timeout-cancellation scenario these very steps' comments cite), that write
  never happens -- the variable is UNSET, ``:-0`` reads it as "exit 0,
  passed", and ``nightly_escalation.py`` closes a standing P0 for a suite
  that never actually finished. This test asserts the workflow never defaults
  an unset nightly exit variable to the success sentinel `0`.

- **FIND-2**: ``integration-next`` runs ``pytest tests/integration tests/next``
  BY DIRECTORY, not by marker (unlike performance/e2e/stress/interpreter-matrix,
  each ``-m <marker>``). For a marker lane, pytest exit 5 ("no tests
  collected") legitimately means "this marker selected nothing" -- a skip,
  not a failure (spec.md Edge Case #4). For a DIRECTORY lane, exit 5 means the
  corpus vanished or was fully deselected, which is never legitimate -- every
  ``modules[]`` shard in ``module-tests.yml`` already fails closed on
  zero-collected (~L216-218, ``sys.exit(64)``). This test asserts
  ``integration-next`` does NOT exempt exit 5 from failure, while the four
  marker-based lanes still do (their exemption is correct and must survive).

Both tests parse the REAL ``.github/workflows/ci-nightly.yml`` (never a
hardcoded copy), mirroring ``tests/ci/test_interpreter_matrix_env_pinning.py``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.architectural._gate_coverage import load_spliced_workflow
from tests.architectural._interpreter_shard_roster import INTERPRETER_SHARD_JOB_KEYS, INTERPRETER_SHARDS

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW_PATH = _REPO_ROOT / ".github" / "workflows" / "ci-nightly.yml"

# suite key -> ($GITHUB_ENV exit variable, job name)
#
# #4951: the single `interpreter-matrix` job (one INTERPRETER_EXIT var) was
# split into N independent `interpreter-matrix-shard-<N>` jobs, each with its
# own `INTERPRETER_SHARD_<N>_EXIT` var -- so this dict now carries one entry
# PER SHARD. Landing pass #5244 (LAND-PAT-002): both the lane label and the
# exit var are now read straight off each roster `InterpreterShard`
# (`lane_label`/`exit_var`) instead of being independently re-derived here
# via a `job_key.rsplit('-')` + a local regex helper -- the roster is the one
# place either name is computed from `job_key`, never a second time here.
_MARKER_LANES = {
    "performance": ("PERF_EXIT", "performance"),
    "e2e": ("E2E_EXIT", "e2e"),
    "stress": ("STRESS_EXIT", "stress"),
    **{shard.lane_label: (shard.exit_var, shard.job_key) for shard in INTERPRETER_SHARDS},
}
# directory-lane job name -> $GITHUB_ENV exit variable. #5201 added the
# specify_cli out-of-matrix lane alongside integration-next; #5510 added the
# architectural-backstop lane (the plain per-PR battery base, nightly-only).
_DIRECTORY_LANES = {
    "integration-next": "INTEGRATION_EXIT",
    "specify-cli-out-of-matrix": "SPECIFY_CLI_OOM_EXIT",
    "architectural-backstop": "ARCH_BACKSTOP_EXIT",
    # The integration slice is marker-selected, but an empty collect is the
    # lost signal, not a legitimate skip. It fails closed on exit 5.
    "integration-slice": "INTEGRATION_SLICE_EXIT",
}

_ALL_EXIT_VARS = [var for var, _job in _MARKER_LANES.values()] + list(_DIRECTORY_LANES.values())


def _load_workflow() -> dict[str, Any]:
    # Landing pass #5244 (LAND-PAT-003): route through the canonical
    # splicing loader, never a raw `yaml.safe_load` -- see
    # `_gate_coverage.load_spliced_workflow`'s docstring for why every
    # workflow reader must use it (a local `uses:` caller job, such as
    # ci-nightly.yml's own `full-module-matrix`, is mis-modeled otherwise).
    loaded = load_spliced_workflow(_WORKFLOW_PATH)
    assert isinstance(loaded, dict), f"expected a YAML mapping at the file root, got {type(loaded)!r}"
    return loaded


def _run_text_for_job(workflow: dict[str, Any], job_name: str) -> str:
    job = workflow["jobs"][job_name]
    return "\n".join(step["run"] for step in job["steps"] if isinstance(step.get("run"), str))


# ---------------------------------------------------------------------------
# PR-TESTS-002 (pre-merge squad, severity 3): ``_MARKER_LANES`` merges the
# interpreter-shard entries in via a dict comprehension over
# ``INTERPRETER_SHARD_JOB_KEYS``. If the roster is ever emptied, that
# comprehension silently contributes ZERO interpreter entries -- every test
# below keeps passing over the surviving performance/e2e/stress lanes, with
# no skip or warning at all. This guard fails loudly instead, and also
# catches a SHRUNKEN (non-empty) roster.
# ---------------------------------------------------------------------------


def _interpreter_lane_non_vacuity_violation(roster_job_keys: tuple[str, ...], marker_lanes: dict[str, tuple[str, str]]) -> str | None:
    """PRODUCTION comparison for PR-TESTS-002: the roster must be non-empty,
    and ``_MARKER_LANES`` must carry exactly one interpreter-shard entry per
    roster job key. Returns a message describing the violation, or ``None``
    when they agree. Both the guard test below (the REAL roster, the REAL
    ``_MARKER_LANES``) and its required mutation test (a scratch, emptied
    roster paired with a scratch ``marker_lanes`` built the same way
    production does) call this SAME function."""
    if not roster_job_keys:
        return "INTERPRETER_SHARD_JOB_KEYS must not be empty -- _MARKER_LANES silently drops all interpreter-shard coverage otherwise"
    interpreter_lane_keys = {suite_key for suite_key in marker_lanes if suite_key.startswith("interpreter-")}
    if len(interpreter_lane_keys) != len(roster_job_keys):
        return (
            f"_MARKER_LANES carries {len(interpreter_lane_keys)} interpreter-shard lane(s) {sorted(interpreter_lane_keys)} "
            f"but the roster declares {len(roster_job_keys)} shard(s) {sorted(roster_job_keys)}"
        )
    return None


def test_interpreter_shard_lanes_are_present_and_match_the_roster() -> None:
    """PR-TESTS-002: fails loudly on an emptied or shrunken roster instead
    of letting FIND-1/FIND-2's marker-lane checks silently lose all
    interpreter-shard coverage."""
    violation = _interpreter_lane_non_vacuity_violation(INTERPRETER_SHARD_JOB_KEYS, _MARKER_LANES)
    assert violation is None, violation


def test_interpreter_shard_lane_check_fails_on_an_emptied_roster() -> None:
    """Standing Order #5 positive control: proves
    ``_interpreter_lane_non_vacuity_violation`` -- the SAME function the
    guard above calls -- actually fails when the roster is empty but
    ``_MARKER_LANES`` still carries the non-interpreter lanes (mirroring the
    real dict-comprehension's behavior on an emptied roster), without
    touching ``_interpreter_shard_roster.py`` on disk."""
    scratch_lanes = {"performance": ("PERF_EXIT", "performance"), "e2e": ("E2E_EXIT", "e2e"), "stress": ("STRESS_EXIT", "stress")}
    violation = _interpreter_lane_non_vacuity_violation((), scratch_lanes)
    assert violation is not None and "must not be empty" in violation, f"expected an empty-roster violation, got: {violation!r}"


def test_interpreter_shard_lane_check_fails_on_a_shrunken_roster() -> None:
    """Standing Order #5 positive control: a SHRUNKEN scratch roster (one
    shard dropped) paired with the unchanged, still-full ``_MARKER_LANES``
    -- modeling a lane dict that was not regenerated in lockstep with a
    roster shrink -- must also surface as a violation."""
    shrunken = INTERPRETER_SHARD_JOB_KEYS[:-1]
    violation = _interpreter_lane_non_vacuity_violation(shrunken, _MARKER_LANES)
    assert violation is not None and "carries" in violation, f"expected a count-mismatch violation, got: {violation!r}"


# ---------------------------------------------------------------------------
# FIND-1: an unset/timeout-killed exit variable must never default to the
# success sentinel `0`.
# ---------------------------------------------------------------------------
class TestUnsetExitNeverDefaultsToSuccess:
    def test_workflow_never_defaults_a_nightly_exit_var_to_zero(self) -> None:
        text = _WORKFLOW_PATH.read_text(encoding="utf-8")
        for var in _ALL_EXIT_VARS:
            unsafe_default = f"${{{var}:-0}}"
            assert unsafe_default not in text, (
                f"{unsafe_default!r} defaults an unset exit code to 0 (success). "
                f"If the suite step is killed by its timeout-minutes cap before "
                f"the `code=$?; echo {var}=$code >> $GITHUB_ENV` line runs, {var} "
                f"is UNSET here and this default falsely reads as 'passed', "
                f"closing a standing P0 for a suite that never actually "
                f"finished (FIND-1, #5034)."
            )

    def test_every_nightly_exit_var_defaults_to_a_failure_sentinel(self) -> None:
        """Positive complement: assert the actual fix shape, not just the
        absence of the broken one -- a default of e.g. `:-5` (the marker-empty
        sentinel) would also dodge the negative check above while still
        silently closing a P0 for an unset exit."""
        workflow = _load_workflow()
        for suite_key, (var, job_name) in _MARKER_LANES.items():
            run_text = _run_text_for_job(workflow, job_name)
            assert f"${{{var}:-1}}" in run_text, (
                f"expected the {suite_key!r} lane ({job_name!r}) to default an unset {var} to the failure sentinel `1`; run text: {run_text!r}"
            )
        for job_name, var in _DIRECTORY_LANES.items():
            directory_run_text = _run_text_for_job(workflow, job_name)
            assert f"${{{var}:-1}}" in directory_run_text, (
                f"expected {job_name!r} to default an unset {var} to the failure sentinel `1`; run text: {directory_run_text!r}"
            )


# ---------------------------------------------------------------------------
# FIND-2: integration-next is a DIRECTORY lane, not a marker lane -- exit 5
# must NOT be exempted from failure there, but must stay exempted everywhere
# marker selection legitimately produces it.
# ---------------------------------------------------------------------------
class TestZeroCollectedFloorScopedToDirectoryLane:
    @pytest.mark.parametrize("job_name", sorted(_DIRECTORY_LANES))
    def test_directory_lane_does_not_exempt_exit_five_from_failure(self, job_name: str) -> None:
        workflow = _load_workflow()
        run_text = _run_text_for_job(workflow, job_name)
        assert "-ne 5" not in run_text, (
            f"{job_name!r} runs pytest BY DIRECTORY, so exit 5 ('no tests "
            "collected') means the corpus vanished or was fully deselected -- "
            "never a legitimate skip. This job must not exempt it from failure "
            f"(FIND-2, #5034); run text: {run_text!r}"
        )

    def test_marker_based_lanes_still_exempt_exit_five_as_a_legitimate_skip(self) -> None:
        """FIND-2's fix is scoped to integration-next only. The marker-based
        lanes select tests with `-m <marker>`, where an empty selection (exit
        5) legitimately means "no tests carry this marker on this dispatch"
        (spec.md Edge Case #4) -- that exemption must survive untouched.
        """
        workflow = _load_workflow()
        for suite_key, (_var, job_name) in _MARKER_LANES.items():
            run_text = _run_text_for_job(workflow, job_name)
            assert "-ne 5" in run_text, f"the {suite_key!r} lane ({job_name!r}) must still exempt pytest exit 5 (marker-empty) from failure; run text: {run_text!r}"


# ---------------------------------------------------------------------------
# #5201: the specify_cli out-of-matrix lane must stay wired into the nightly
# verdict and keep deriving its exclusions from the module registry.
# ---------------------------------------------------------------------------
class TestSpecifyCliOutOfMatrixLane:
    _JOB = "specify-cli-out-of-matrix"

    def test_lane_feeds_the_nightly_summary(self) -> None:
        workflow = _load_workflow()
        needs = workflow["jobs"]["nightly-summary"]["needs"]
        assert self._JOB in needs, f"{self._JOB!r} must be in nightly-summary.needs so its verdict is reported; needs: {needs!r}"

    def test_lane_runs_specify_cli_minus_registry_claimed_dirs(self) -> None:
        run_text = _run_text_for_job(_load_workflow(), self._JOB)
        assert "pytest tests/specify_cli " in run_text, run_text
        assert ".github/ci-module-registry.yml" in run_text, (
            "the ignore list must be computed from the registry at run time, never hardcoded, "
            f"so a #4732 promotion drops its tree from this lane; run text: {run_text!r}"
        )
        assert '"${ignores[@]}"' in run_text, run_text

    def test_lane_deselects_parallel_unsafe_markers(self) -> None:
        run_text = _run_text_for_job(_load_workflow(), self._JOB)
        assert '-m "not stress and not timing"' in run_text, run_text
        assert "--dist loadfile" in run_text, run_text

    def test_lane_escalates_under_its_own_suite_key(self) -> None:
        run_text = _run_text_for_job(_load_workflow(), self._JOB)
        assert f"--suite-key {self._JOB}" in run_text, run_text


# ---------------------------------------------------------------------------
# LAND-ARCH-003 (landing pass #5244): no guard previously pinned EVERY
# escalating nightly job into nightly-summary.needs -- only the shards
# (test_interpreter_shard_coverage.py) and integration-next
# (test_module_shard_registry.py) were individually pinned, and
# TestSpecifyCliOutOfMatrixLane above pins specify-cli-out-of-matrix alone.
# A future merge conflict on that `needs:` line could silently drop ANY
# escalating job (not just the ones already named) from the aggregator --
# exactly the hazard the merge that produced this landing pass exercised.
# This closes the class: derived from the workflow itself, general over
# every job with a `nightly_escalation.py` step, not a per-job enumeration.
# ---------------------------------------------------------------------------


def _job_run_text(job: dict[str, object]) -> str:
    """All raw ``run:`` script text of one job dict, joined."""
    steps = job.get("steps") or []
    return "\n".join(str(step.get("run")) for step in steps if isinstance(step, dict) and isinstance(step.get("run"), str))


def _jobs_with_an_escalation_step(jobs: dict[str, object]) -> set[str]:
    """Every job name (excluding ``nightly-summary`` itself) whose ``run:``
    text invokes ``nightly_escalation.py`` anywhere."""
    escalating: set[str] = set()
    for job_name, job in jobs.items():
        if job_name == "nightly-summary" or not isinstance(job, dict):
            continue
        if "nightly_escalation.py" in _job_run_text(job):
            escalating.add(job_name)
    return escalating


def _escalating_jobs_missing_from_summary_needs(jobs: dict[str, object]) -> set[str]:
    """PRODUCTION comparison for LAND-ARCH-003: every job that escalates via
    ``nightly_escalation.py`` must appear in ``nightly-summary``'s ``needs``,
    or its red verdict never surfaces in the aggregator. Returns the set of
    violating job names, or the empty set when every escalating job is
    aggregated. Both the guard test below (the REAL workflow) and its
    required mutation control (a scratch ``needs`` list with one job
    dropped) call this SAME function."""
    escalating = _jobs_with_an_escalation_step(jobs)
    summary_job = jobs.get("nightly-summary")
    summary_needs = set((summary_job or {}).get("needs") or []) if isinstance(summary_job, dict) else set()
    return escalating - summary_needs


def test_every_escalating_nightly_job_is_aggregated_by_nightly_summary() -> None:
    """LAND-ARCH-003: every job in the REAL ci-nightly.yml with a
    ``nightly_escalation.py`` step must appear in ``nightly-summary.needs``."""
    jobs = _load_workflow()["jobs"]
    missing = _escalating_jobs_missing_from_summary_needs(jobs)
    assert not missing, f"job(s) escalate via nightly_escalation.py but are missing from nightly-summary.needs (their red never surfaces): {sorted(missing)}"


def test_escalating_job_aggregation_check_fails_when_a_job_is_dropped_from_needs() -> None:
    """Standing Order #5 positive control: a scratch parse of the REAL
    workflow with ``specify-cli-out-of-matrix`` dropped from
    ``nightly-summary.needs`` (its own escalation step left untouched) must
    be caught by ``_escalating_jobs_missing_from_summary_needs`` -- the SAME
    function the guard above calls. The tracked workflow itself is never
    edited."""
    jobs = dict(_load_workflow()["jobs"])
    real_summary = jobs["nightly-summary"]
    scratch_needs = [job_name for job_name in real_summary["needs"] if job_name != "specify-cli-out-of-matrix"]
    jobs["nightly-summary"] = {**real_summary, "needs": scratch_needs}

    missing = _escalating_jobs_missing_from_summary_needs(jobs)
    assert missing == {"specify-cli-out-of-matrix"}, f"dropping specify-cli-out-of-matrix from needs must surface it as missing, got: {missing}"
