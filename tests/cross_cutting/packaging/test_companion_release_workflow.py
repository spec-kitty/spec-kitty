"""``release.yml`` builds, verifies and publishes the companion before the CLI (#6904, WP06).

ADR 2026-10-29-1, Amendment 2026-10-31. Reads the parsed workflow only, and asserts properties of its job graph, not its text.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.fast

_WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "release.yml"
_PUBLISH_ACTION = "pypa/gh-action-pypi-publish@"
_COMPANION_PUBLISH = "publish-companion-pypi"
_COMPANION_DIST = "dist-services/"


@pytest.fixture(scope="module")
def jobs() -> dict[str, Any]:
    workflow = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    return dict(workflow["jobs"])


def _needs(job: dict[str, Any]) -> list[str]:
    needs = job.get("needs", [])
    return [needs] if isinstance(needs, str) else list(needs)


def _publish_steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    return [step for step in job.get("steps", []) if str(step.get("uses", "")).startswith(_PUBLISH_ACTION)]


def test_publishing_is_gated_on_the_companion_and_confined_to_environments(jobs: dict[str, Any]) -> None:
    publishers = {name: job for name, job in jobs.items() if _publish_steps(job)}
    assert _COMPANION_PUBLISH in publishers
    cli_publishers = {name: job for name, job in publishers.items() if name != _COMPANION_PUBLISH}
    assert cli_publishers  # positive control: a CLI publish job exists

    # No CLI publish job runs unless the companion publish job precedes it and succeeded.
    for name, job in cli_publishers.items():
        assert _COMPANION_PUBLISH in _needs(job), name
        assert f"needs.{_COMPANION_PUBLISH}.result == 'success'" in str(job["if"]), name

    # OIDC publishing rights exist only on environment-gated jobs that publish.
    for name, job in jobs.items():
        if job.get("permissions", {}).get("id-token") == "write":
            assert name in publishers and job.get("environment"), name


def test_companion_wheels_never_land_in_the_cli_dist(jobs: dict[str, Any]) -> None:
    assert [step["with"]["packages-dir"] for step in _publish_steps(jobs[_COMPANION_PUBLISH])] == [_COMPANION_DIST]
    for name, job in jobs.items():
        if name == _COMPANION_PUBLISH:
            continue
        for step in _publish_steps(job):
            assert step["with"]["packages-dir"] != _COMPANION_DIST, name
