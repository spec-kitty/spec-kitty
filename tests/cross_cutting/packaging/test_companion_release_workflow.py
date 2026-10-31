"""``release.yml`` builds, verifies and publishes the companion before the CLI (#6904, WP06).

ADR 2026-10-29-1, Amendment 2026-10-31. Reads the workflow YAML only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.fast

_WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "release.yml"
_PUBLISH_ACTION = "pypa/gh-action-pypi-publish@"
_SYNC_ACTION = "./.github/actions/sync-services"


@pytest.fixture(scope="module")
def jobs() -> dict[str, Any]:
    workflow = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    return dict(workflow["jobs"])


def _runs(job: dict[str, Any]) -> list[str]:
    return [str(step.get("run", "")) for step in job["steps"]]


def _index(runs: list[str], needle: str) -> int:
    return next(i for i, run in enumerate(runs) if needle in run)


def _needs(job: dict[str, Any]) -> list[str]:
    needs = job.get("needs", [])
    return [needs] if isinstance(needs, str) else list(needs)


def test_build_release_verifies_the_pinned_services_before_building(jobs: dict[str, Any]) -> None:
    runs = _runs(jobs["build-release"])
    packs = _index(runs, "scripts/sync_packs.py --pack all --check")
    fetch = next(i for i, run in enumerate(runs) if "scripts/sync_services.py --service all" in run and "--check" not in run)
    check = _index(runs, "scripts/sync_services.py --service all --check")
    build = _index(runs, "python -m build")
    assert packs < fetch < check < build


def test_the_companion_is_built_and_verified_in_its_own_job(jobs: dict[str, Any]) -> None:
    job = jobs["build-companion-wheels"]
    assert _needs(job) == ["build-release"]
    runs = _runs(job)
    build = _index(runs, "scripts/build_services_wheel.py --out dist-services")
    verify = _index(runs, "scripts/build_services_wheel.py --verify dist-services")
    twine = _index(runs, "twine check dist-services/*")
    assert build < verify < twine
    assert not [run for run in runs if "dist/" in run.replace("dist-services/", "")]
    upload = next(step for step in job["steps"] if str(step.get("uses", "")).startswith("actions/upload-artifact@"))
    assert upload["with"]["name"] == "companion-distributions"


def test_the_companion_publishes_from_its_own_environment(jobs: dict[str, Any]) -> None:
    job = jobs["publish-companion-pypi"]
    assert _needs(job) == ["build-companion-wheels"]
    assert job["environment"]["name"] == "pypi-services"
    assert job["permissions"]["id-token"] == "write"
    publish = next(step for step in job["steps"] if str(step.get("uses", "")).startswith(_PUBLISH_ACTION))
    cli_publish = next(step for step in jobs["publish-pypi"]["steps"] if str(step.get("uses", "")).startswith(_PUBLISH_ACTION))
    assert publish["uses"] == cli_publish["uses"]  # the same pinned SHA
    assert publish["with"]["packages-dir"] == "dist-services/"
    assert jobs["publish-pypi"]["environment"]["name"] == "pypi"  # positive control: the CLI keeps its own environment


def test_the_cli_publishes_only_after_the_companion(jobs: dict[str, Any]) -> None:
    job = jobs["publish-pypi"]
    assert "publish-companion-pypi" in _needs(job)
    assert "needs.publish-companion-pypi.result == 'success'" in job["if"]


def test_no_release_job_uses_the_sync_services_action(jobs: dict[str, Any]) -> None:
    """The action's "wire it now" ratchet (tests/ci/test_sync_services.py) belongs to the conformance jobs."""
    uses = [str(step.get("uses", "")) for job in jobs.values() for step in job.get("steps", [])]
    assert _SYNC_ACTION not in uses


def test_the_glibc_floor_is_passed_explicitly(jobs: dict[str, Any]) -> None:
    runs = _runs(jobs["build-companion-wheels"])
    assert "--glibc-floor 2_39" in runs[_index(runs, "build_services_wheel.py --out")]
    assert "--glibc-floor 2_39" in runs[_index(runs, "build_services_wheel.py --verify")]


def test_the_companion_publish_rechecks_the_artifact_and_tolerates_a_rerun(jobs: dict[str, Any]) -> None:
    job = jobs["publish-companion-pypi"]
    names = [step.get("name", "") for step in job["steps"]]
    runs = _runs(job)
    check = _index(runs, "sha256sum -c SHA256SUMS-services.txt")
    publish = next(i for i, step in enumerate(job["steps"]) if str(step.get("uses", "")).startswith(_PUBLISH_ACTION))
    assert check < publish, names
    assert job["steps"][publish]["with"]["skip-existing"] is True


def test_the_published_extra_is_checked_to_resolve_the_companion(jobs: dict[str, Any]) -> None:
    runs = _runs(jobs["verify-pypi-installability"])
    extra = runs[_index(runs, "spec-kitty-cli[services]==")]
    assert "--dry-run" in extra
    assert "spec-kitty-services-${VERSION}" in extra
