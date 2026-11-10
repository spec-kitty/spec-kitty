"""Pin the nightly ``acceptance-bdd`` job shape (WP03, FR-010/FR-011, NFR-004)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import fnmatch

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


# Scripts this job runs that import ``kernel`` from ``src/`` (directly or through ``scripts/sync_services.py``).
_KERNEL_IMPORTING_SCRIPTS = ("scripts/sync_services.py", "scripts/ci/acceptance_jvm_gradle_pin_check.py")


def test_kernel_importing_scripts_run_with_src_on_the_path(job: dict[str, Any]) -> None:
    """The job installs without the project (``--no-install-project``), so ``kernel`` resolves only through PYTHONPATH.

    The Gradle pin check once ran without it and exited 2 ("No module named 'kernel'") before any scenario.
    """
    assert any("--no-install-project" in str(s.get("run") or "") for s in job["steps"]), "the premise moved: re-derive this guard"
    lines = [line for s in job["steps"] for line in str(s.get("run") or "").splitlines() if any(sc in line for sc in _KERNEL_IMPORTING_SCRIPTS)]
    assert lines, "the scan must see the job's kernel-importing script runs"
    assert [line.strip() for line in lines if "PYTHONPATH=" not in line] == []


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


def test_gating_leg_runs_no_wip_pass(job: dict[str, Any]) -> None:
    """#7492: the non-gating @wip pass must never spend the gating leg's job budget.

    Nightly runs 41961190305 (2026-11-05) and 42748989805 (2026-11-10): the Windows gating
    pass went green in ~47 minutes, then the @wip step ran the leg into its 60-minute job cap,
    the leg was cancelled and the whole acceptance-bdd run escalated as a P0 with no failing test.
    """
    assert _steps_running(job, "-Pacceptance.pass=wip") == []


def test_no_step_uses_cucumber_filter_tags(job: dict[str, Any], wip_job: dict[str, Any]) -> None:
    for each in (job, wip_job):
        assert not _steps_running(each, "cucumber.filter.tags")
        assert len(_steps_running(each, "-Pacceptance.pass=")) == 1


def test_evidence_step_runs_always(job: dict[str, Any]) -> None:
    (step,) = _steps_running(job, "scripts.ci.acceptance_evidence")
    assert step["if"] == "always()"
    run = step["run"]
    assert "--root acceptance-jvm/build/acceptance" in run
    assert '--os "${{ matrix.os }}"' in run
    assert "--pass gating" in run and "--pass wip" not in run
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


@pytest.fixture(scope="module")
def jobs() -> dict[str, Any]:
    return load_spliced_workflow(WORKFLOW)["jobs"]


# --- acceptance-bdd-wip (#7492, FR-014) -----------------------------------------------------------

WIP_JOB = "acceptance-bdd-wip"
WIP_ARTIFACT = "acceptance-bdd-wip-results-${{ matrix.os }}"
# Minutes the @wip step cap leaves under its job cap (setup before it, evidence and upload after),
# the same reserve tests/ci/test_nightly_suite_step_timeout.py requires of a suite step.
_STEP_RESERVE_MINUTES = 5


@pytest.fixture(scope="module")
def wip_job(jobs: dict[str, Any]) -> dict[str, Any]:
    return jobs[WIP_JOB]


def test_wip_job_runs_on_every_gating_os_without_fail_fast(job: dict[str, Any], wip_job: dict[str, Any]) -> None:
    assert wip_job["strategy"]["matrix"]["os"] == job["strategy"]["matrix"]["os"]
    assert wip_job["strategy"]["fail-fast"] is False
    assert wip_job["if"] == job["if"]
    assert "pull_request" not in str(wip_job["if"])


def test_wip_step_is_non_gating_and_bounded_below_its_job_cap(wip_job: dict[str, Any]) -> None:
    """A slow @wip pass fails only its own continue-on-error step; the evidence and upload still run."""
    (step,) = _steps_running(wip_job, "-Pacceptance.pass=wip")
    assert step["continue-on-error"] is True
    assert isinstance(step.get("timeout-minutes"), int)
    assert 0 < step["timeout-minutes"] <= int(wip_job["timeout-minutes"]) - _STEP_RESERVE_MINUTES


def test_wip_job_never_gates_anything(jobs: dict[str, Any], wip_job: dict[str, Any]) -> None:
    """FR-014: no job waits on the wip job, it never escalates and asks for no write scope."""
    dependants = [key for key, other in jobs.items() if WIP_JOB in (other.get("needs") or [])]
    assert dependants == []
    assert _escalation_keys(wip_job) == []
    assert "permissions" not in wip_job


def test_wip_evidence_covers_the_wip_pass_and_records_its_step_outcome(wip_job: dict[str, Any]) -> None:
    (step,) = _steps_running(wip_job, "scripts.ci.acceptance_evidence")
    assert step["if"] == "always()"
    run = step["run"]
    assert "--pass wip" in run and "--pass gating" not in run
    (wip,) = _steps_running(wip_job, "-Pacceptance.pass=wip")
    assert f'--wip-step-outcome "${{{{ steps.{wip["id"]}.outcome }}}}"' in run


def test_wip_results_upload_under_a_name_the_escalation_never_reads(jobs: dict[str, Any], wip_job: dict[str, Any]) -> None:
    (upload,) = [s for s in wip_job["steps"] if str(s.get("uses") or "").startswith("actions/upload-artifact@")]
    assert upload["if"] == "always()"
    assert upload["with"]["name"] == WIP_ARTIFACT
    assert str(upload["with"]["path"]).strip() == UPLOAD_PATH
    assert upload["with"]["if-no-files-found"] == "error"
    download = next(s for s in jobs["acceptance-bdd-escalation"]["steps"] if str(s.get("uses") or "").startswith("actions/download-artifact@"))
    assert not fnmatch.fnmatch(WIP_ARTIFACT.replace("${{ matrix.os }}", "windows-latest"), download["with"]["pattern"])


# --- acceptance-bdd-escalation (ADR 2026-10-15-1, decision 5) -------------------------------------


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


def test_escalation_names_the_matrix_result(jobs: dict[str, Any]) -> None:
    """#7492: a cancelled (timed-out) leg is named in the P0, not only 'no failing tests'."""
    (step,) = [s for s in jobs["acceptance-bdd-escalation"]["steps"] if "nightly_escalation.py" in str(s.get("run") or "")]
    assert '--job-result "${ACCEPTANCE_RESULT:-failure}"' in step["run"]


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
    assert f"for leg in {path}/acceptance-bdd-results-*; do" in run
    assert 'junit="$leg/gating/junit"' in run
    # The gating folder is the only --xunit source: no other flag, no other folder.
    assert run.count("--xunit") == 1
    assert 'xunit_args+=(--xunit "$junit")' in run
    assert "wip" not in run
    assert '"${xunit_args[@]}"' in run
    assert "::warning::" in run, "a leg without gating JUnit XML must be named, not silently dropped"


def test_acceptance_jobs_are_aggregated_by_nightly_summary(jobs: dict[str, Any]) -> None:
    needs = jobs["nightly-summary"]["needs"]
    assert {"acceptance-bdd", "acceptance-bdd-escalation"} <= set(needs)


def test_job_timeout_fits_the_slowest_measured_leg(job: dict[str, Any]) -> None:
    """The Windows leg took over 30 minutes for 56 scenarios (run 38761757042); the cap must not drop back."""
    assert int(job["timeout-minutes"]) >= 60
