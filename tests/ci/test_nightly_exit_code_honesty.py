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
import yaml

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW_PATH = _REPO_ROOT / ".github" / "workflows" / "ci-nightly.yml"

# suite key -> ($GITHUB_ENV exit variable, job name)
_MARKER_LANES = {
    "performance": ("PERF_EXIT", "performance"),
    "e2e": ("E2E_EXIT", "e2e"),
    "stress": ("STRESS_EXIT", "stress"),
    "interpreter": ("INTERPRETER_EXIT", "interpreter-matrix"),
}
_DIRECTORY_LANE_JOB = "integration-next"
_DIRECTORY_LANE_VAR = "INTEGRATION_EXIT"

_ALL_EXIT_VARS = [var for var, _job in _MARKER_LANES.values()] + [_DIRECTORY_LANE_VAR]


def _load_workflow() -> dict[str, Any]:
    with _WORKFLOW_PATH.open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    assert isinstance(loaded, dict), f"expected a YAML mapping at the file root, got {type(loaded)!r}"
    return loaded


def _run_text_for_job(workflow: dict[str, Any], job_name: str) -> str:
    job = workflow["jobs"][job_name]
    return "\n".join(step["run"] for step in job["steps"] if isinstance(step.get("run"), str))


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
        integration_run_text = _run_text_for_job(workflow, _DIRECTORY_LANE_JOB)
        assert f"${{{_DIRECTORY_LANE_VAR}:-1}}" in integration_run_text, (
            f"expected {_DIRECTORY_LANE_JOB!r} to default an unset {_DIRECTORY_LANE_VAR} to the failure sentinel `1`; run text: {integration_run_text!r}"
        )


# ---------------------------------------------------------------------------
# FIND-2: integration-next is a DIRECTORY lane, not a marker lane -- exit 5
# must NOT be exempted from failure there, but must stay exempted everywhere
# marker selection legitimately produces it.
# ---------------------------------------------------------------------------
class TestZeroCollectedFloorScopedToDirectoryLane:
    def test_integration_next_does_not_exempt_exit_five_from_failure(self) -> None:
        workflow = _load_workflow()
        run_text = _run_text_for_job(workflow, _DIRECTORY_LANE_JOB)
        assert "-ne 5" not in run_text, (
            f"{_DIRECTORY_LANE_JOB!r} runs pytest BY DIRECTORY "
            "(tests/integration tests/next), so exit 5 ('no tests collected') "
            "means the corpus vanished or was fully deselected -- never a "
            "legitimate skip. This job must not exempt it from failure "
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
