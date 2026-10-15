"""End-to-end CLI smoke test for the full spec-kitty workflow.

Exercises the complete sequence:
  mission create -> mission setup-plan -> mission finalize-tasks -> implement -> move-task

This test creates a fresh temporary git repo, runs each CLI command via
subprocess, and verifies that intermediate artifacts exist at each step.
It is entirely self-contained: no state leaks to the source repository.

Marked with pytest.mark.e2e for optional CI separation:
    pytest tests/ -m "not e2e"    # skip E2E in fast runs
    pytest tests/e2e/ -v -s       # run E2E only
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


pytestmark = [pytest.mark.e2e, pytest.mark.git_repo]

SUBSTANTIVE_SPEC = """# E2E Smoke Spec

## Functional Requirements

| ID | Requirement | Acceptance Criteria | Status |
| --- | --- | --- | --- |
| FR-001 | Exercise the E2E smoke workflow. | setup-plan can run against committed spec content. | proposed |
"""


@pytest.mark.e2e
@pytest.mark.slow
class TestFullCLIWorkflow:
    """Exercise the complete spec-kitty CLI workflow end-to-end."""

    def test_configured_spec_and_plan_project_overrides(
        self,
        e2e_project: Path,
        run_cli,
    ) -> None:
        """Both live readers honor the configured mapping and override tier."""
        override_dir = e2e_project / ".kittify" / "overrides" / "templates"
        override_dir.mkdir(parents=True, exist_ok=True)
        spec_bytes = b"# Configured specification override\n\n<!-- exact bytes -->\n"
        plan_bytes = b"# Configured planning override\n\n<!-- exact bytes -->\n"
        (override_dir / "spec-template.md").write_bytes(spec_bytes)
        (override_dir / "plan-template.md").write_bytes(plan_bytes)
        subprocess.run(
            ["git", "add", "."],
            cwd=e2e_project,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Add configured template overrides"],
            cwd=e2e_project,
            check=True,
            capture_output=True,
        )

        result = run_cli(
            e2e_project,
            "agent",
            "mission",
            "create",
            "configured-template-smoke",
            "--json",
        )
        assert result.returncode == 0, result.stderr
        output = json.loads(result.stdout)
        feature_dir = Path(output["feature_dir"])
        assert (feature_dir / "spec.md").read_bytes() == spec_bytes

        (feature_dir / "spec.md").write_text(SUBSTANTIVE_SPEC, encoding="utf-8")
        subprocess.run(
            ["git", "add", "."],
            cwd=e2e_project,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Author configured-template smoke spec"],
            cwd=e2e_project,
            check=True,
            capture_output=True,
        )

        result = run_cli(
            e2e_project,
            "agent",
            "mission",
            "setup-plan",
            "--mission",
            output["mission_slug"],
            "--json",
        )
        assert result.returncode == 0, result.stderr
        assert (feature_dir / "plan.md").read_bytes() == plan_bytes
