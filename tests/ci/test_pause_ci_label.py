"""Pin the ``pr:pause-ci`` label contract.

A paused PR must (a) skip heavy work and (b) stay unmergeable. A skipped required check passes,
so the three required gates must still RUN under the label and fail with the documented message.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.fast

_WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
_LABEL = "pr:pause-ci"
_LABEL_NEGATION = f"!contains(github.event.pull_request.labels.*.name, '{_LABEL}')"
_MESSAGE = "CI is paused on this PR by the pr:pause-ci label; remove the label to run CI."
_REQUIRED_GATES = [
    ("ci-router.yml", "router-gate"),
    ("ci-modules.yml", "modules-gate"),
    ("ci-quality.yml", "clean-install-verification"),
]


def _jobs(workflow: str) -> dict[str, Any]:
    return yaml.safe_load((_WORKFLOWS / workflow).read_text(encoding="utf-8"))["jobs"]


@pytest.mark.parametrize(("workflow", "job"), _REQUIRED_GATES)
def test_required_gate_runs_and_fails_under_the_pause_label(workflow: str, job: str) -> None:
    spec = _jobs(workflow)[job]
    condition = str(spec["if"])
    assert "always()" in condition, f"{job} must run even when its needs were skipped"
    assert _LABEL_NEGATION not in condition, f"{job} must not skip under the label (a skipped check passes)"
    first = spec["steps"][0]
    assert _LABEL in first["if"] and "contains(" in first["if"] and "!contains" not in first["if"]
    assert _MESSAGE in first["run"]
    assert "exit 1" in first["run"]


@pytest.mark.parametrize(("workflow", "job"), [("ci-router.yml", "changes"), ("ci-modules.yml", "generate-matrix"), ("packs.yml", "changes")])
def test_root_jobs_skip_under_the_pause_label(workflow: str, job: str) -> None:
    assert _LABEL_NEGATION in str(_jobs(workflow)[job]["if"])


def test_pause_workflow_never_checks_out_pr_code() -> None:
    workflow = yaml.safe_load((_WORKFLOWS / "pr-pause-ci.yml").read_text(encoding="utf-8"))
    assert set(workflow[True]) == {"pull_request_target"}  # PyYAML parses the `on` key as True
    for job in workflow["jobs"].values():
        assert not any("uses" in step for step in job["steps"]), "pull_request_target jobs must not use actions"
