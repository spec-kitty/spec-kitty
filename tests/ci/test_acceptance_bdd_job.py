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


def test_gating_step_has_pass_property_and_no_retry(job: dict[str, Any]) -> None:
    (step,) = _steps_running(job, "-Pacceptance.pass=gating")
    assert not step.get("continue-on-error")


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
