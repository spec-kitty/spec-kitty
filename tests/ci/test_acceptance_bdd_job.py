"""Pin the nightly ``acceptance-bdd`` job shape (WP03, FR-010/FR-011, NFR-004)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.architectural._gate_coverage import load_spliced_workflow

pytestmark = [pytest.mark.fast]

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci-nightly.yml"
UPLOAD_PATH = "acceptance-jvm/build/acceptance/"


@pytest.fixture(scope="module")
def job() -> dict[str, Any]:
    jobs = load_spliced_workflow(WORKFLOW)["jobs"]
    return jobs["acceptance-bdd"]


def _steps_running(job: dict[str, Any], needle: str) -> list[dict[str, Any]]:
    return [s for s in job["steps"] if needle in str(s.get("run") or "")]


def test_job_is_not_a_pull_request_job(job: dict[str, Any]) -> None:
    assert "pull_request" not in str(job["if"])


_LOOP_MARKERS = ("||", "for ", "while ", "until ", "retry")


def _assert_no_retry(step: dict[str, Any]) -> None:
    run = str(step.get("run") or "")
    assert not [marker for marker in _LOOP_MARKERS if marker in run.lower()], run
    assert "uses" not in step
    assert not [key for key in step if "retr" in key.lower() or "attempt" in key.lower()]


def test_gating_step_has_pass_property_and_no_retry(job: dict[str, Any]) -> None:
    (step,) = _steps_running(job, "-Pacceptance.pass=gating")
    assert not step.get("continue-on-error")
    _assert_no_retry(step)


def test_evidence_step_has_no_fallback(job: dict[str, Any]) -> None:
    (step,) = _steps_running(job, "scripts.ci.acceptance_evidence")
    assert not step.get("continue-on-error")
    _assert_no_retry(step)


@pytest.mark.parametrize(
    "step",
    [
        {"run": "gradle test || gradle test"},
        {"run": "for i in 1 2; do gradle test; done"},
        {"run": "while ! gradle test; do :; done"},
        {"run": "gradle test --retry 2"},
        {"run": "gradle test", "retry-on-error": True},
        {"uses": "some/retry-action@v1", "with": {"command": "gradle test"}},
    ],
)
def test_no_retry_guard_rejects_retry_shapes(step: dict[str, Any]) -> None:
    with pytest.raises(AssertionError):
        _assert_no_retry(step)


def test_wip_step_is_non_gating(job: dict[str, Any]) -> None:
    (step,) = _steps_running(job, "-Pacceptance.pass=wip")
    assert step["continue-on-error"] is True


def test_no_step_uses_cucumber_filter_tags(job: dict[str, Any]) -> None:
    assert not _steps_running(job, "cucumber.filter.tags")
    assert len(_steps_running(job, "-Pacceptance.pass=")) == 2


def test_evidence_step_runs_always(job: dict[str, Any]) -> None:
    (step,) = _steps_running(job, "scripts.ci.acceptance_evidence")
    assert step["if"] == "always()"
    run = step["run"]
    assert "--root acceptance-jvm/build/acceptance" in run
    assert '--os "${{ matrix.os }}"' in run
    (gating,) = _steps_running(job, "-Pacceptance.pass=gating")
    assert f'--gating-step-outcome "${{{{ steps.{gating["id"]}.outcome }}}}"' in run


def test_upload_is_strict_and_single_path(job: dict[str, Any]) -> None:
    uploads = [s for s in job["steps"] if str(s.get("uses") or "").startswith("actions/upload-artifact@")]
    (step,) = uploads
    assert step["if"] == "always()"
    assert step["with"]["name"] == "acceptance-bdd-results-${{ matrix.os }}"
    assert str(step["with"]["path"]).strip() == UPLOAD_PATH
    assert step["with"]["if-no-files-found"] == "error"
    assert step["with"]["retention-days"] == 30


def test_evidence_runs_before_upload(job: dict[str, Any]) -> None:
    names = [s.get("run", s.get("uses", "")) for s in job["steps"]]
    evidence = next(i for i, n in enumerate(names) if "acceptance_evidence" in n)
    upload = next(i for i, n in enumerate(names) if n.startswith("actions/upload-artifact@"))
    assert evidence < upload


# --- acceptance-bdd-escalation (ADR 2026-10-15-1, decision 5) -------------------------------------


@pytest.fixture(scope="module")
def jobs() -> dict[str, Any]:
    return load_spliced_workflow(WORKFLOW)["jobs"]


def _escalation_keys(job: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for step in job["steps"]:
        run = str(step.get("run") or "")
        if "nightly_escalation.py" in run:
            tokens = run.split()
            keys.append(tokens[tokens.index("--suite-key") + 1])
    return keys


def test_one_escalation_for_every_leg(jobs: dict[str, Any]) -> None:
    escalation = jobs["acceptance-bdd-escalation"]
    assert escalation["needs"] == ["acceptance-bdd"]
    assert "strategy" not in escalation, "one job, not one per OS: a break that reds every leg files one issue"
    assert str(escalation["runs-on"]).startswith("ubuntu")
    assert _escalation_keys(escalation) == ["acceptance-bdd"]
    assert _escalation_keys(jobs["acceptance-bdd"]) == [], "the matrix legs must not escalate on their own"


def test_escalation_runs_after_a_red_matrix_and_only_files_from_main(jobs: dict[str, Any]) -> None:
    escalation = jobs["acceptance-bdd-escalation"]
    # Fork guard first (tests/ci/test_fork_guard.py), then always(): it must run after a red matrix.
    assert str(escalation["if"]).endswith("&& always()")
    assert escalation["permissions"] == {"contents": "read", "issues": "write"}
    (step,) = [s for s in escalation["steps"] if "nightly_escalation.py" in str(s.get("run") or "")]
    assert step["if"] == "always() && github.ref == 'refs/heads/main'"
    assert step["env"]["ACCEPTANCE_RESULT"] == "${{ needs.acceptance-bdd.result }}"


def test_escalation_is_fail_closed(jobs: dict[str, Any]) -> None:
    """Only an explicit ``success`` of the matrix closes the P0; any other result files one."""
    escalation = jobs["acceptance-bdd-escalation"]
    runs = [str(s.get("run") or "") for s in escalation["steps"]]
    (decide,) = [run for run in runs if "nightly_escalation.py" in run]
    assert '"${ACCEPTANCE_RESULT:-failure}" = "success" ]; then conclusion=success; else conclusion=failure' in decide
    (verdict,) = [run for run in runs if run.strip().endswith('= "success" ]')]
    assert "${ACCEPTANCE_RESULT:-failure}" in verdict


def test_escalation_names_the_failing_gating_scenarios_of_every_leg(jobs: dict[str, Any]) -> None:
    """#6369: the P0 lists the red scenarios, read from each leg's gating JUnit XML (never wip/)."""
    steps = jobs["acceptance-bdd-escalation"]["steps"]
    uses = [str(s.get("uses") or "") for s in steps]
    download_index = next(i for i, u in enumerate(uses) if u.startswith("actions/download-artifact@"))
    download = steps[download_index]
    assert download["if"] == "always() && github.ref == 'refs/heads/main'"
    assert download["continue-on-error"] is True
    assert download["with"]["pattern"] == "acceptance-bdd-results-*"
    assert download["with"]["merge-multiple"] is False, "Gradle's TEST-<class>.xml names collide across legs"
    escalate_index = next(i for i, s in enumerate(steps) if "nightly_escalation.py" in str(s.get("run") or ""))
    assert download_index < escalate_index
    run = str(steps[escalate_index]["run"])
    path = download["with"]["path"]
    assert f"{path}/acceptance-bdd-results-*/gating/junit" in run
    assert 'xunit_args+=(--xunit "$junit")' in run
    assert '"${xunit_args[@]}"' in run
    assert "/wip/" not in run


def test_acceptance_jobs_are_aggregated_by_nightly_summary(jobs: dict[str, Any]) -> None:
    needs = jobs["nightly-summary"]["needs"]
    assert {"acceptance-bdd", "acceptance-bdd-escalation"} <= set(needs)


def test_job_timeout_fits_the_slowest_measured_leg(job: dict[str, Any]) -> None:
    """The Windows leg took over 30 minutes for 56 scenarios (run 38761757042); the cap must not drop back."""
    assert int(job["timeout-minutes"]) >= 60
