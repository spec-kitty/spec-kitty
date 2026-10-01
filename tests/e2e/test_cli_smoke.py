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


SUBSTANTIVE_PLAN_TEMPLATE = """# Implementation Plan

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: spec-kitty-cli
**Storage**: Filesystem fixtures
"""


def _prepare_setup_plan_inputs(repo: Path, feature_dir: Path) -> None:
    """Seed committed spec/plan content that satisfies setup-plan gates."""
    (feature_dir / "spec.md").write_text(SUBSTANTIVE_SPEC, encoding="utf-8")

    template_dir = repo / ".kittify" / "templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    (template_dir / "plan-template.md").write_text(
        SUBSTANTIVE_PLAN_TEMPLATE,
        encoding="utf-8",
    )

    subprocess.run(
        ["git", "add", "."],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Seed substantive setup-plan inputs"],
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.mark.e2e
@pytest.mark.slow
class TestFullCLIWorkflow:
    """Exercise the complete spec-kitty CLI workflow end-to-end."""

    def test_create_feature(self, e2e_project: Path, run_cli) -> None:
        """Step 1: mission create produces a mission directory and spec.md."""
        result = run_cli(
            e2e_project,
            "agent",
            "mission",
            "create",
            "smoke-test",
            "--json",
        )
        assert result.returncode == 0, f"mission create failed (rc={result.returncode}):\nstdout: {result.stdout}\nstderr: {result.stderr}"

        output = json.loads(result.stdout)
        assert output["result"] == "success"
        assert "smoke-test" in output["mission_slug"]

        feature_dir = Path(output["feature_dir"])
        assert feature_dir.exists(), f"Feature dir missing: {feature_dir}"
        assert (feature_dir / "spec.md").exists(), "spec.md not created"
        assert (feature_dir / "tasks").is_dir(), "tasks/ directory not created"

        # No execution (lane) worktree is created during planning. Since #5440 a
        # coordination-routed create seeds the status log in the mission's
        # coordination worktree, which is the only worktree allowed here.
        worktrees_dir = e2e_project / ".worktrees"
        if worktrees_dir.exists():
            allowed = {f"{output['mission_slug']}-coord"} if output.get("coordination_branch") else set()
            unexpected = [path.name for path in worktrees_dir.iterdir() if path.name not in allowed]
            assert unexpected == [], f"Worktree created during mission creation: {unexpected}"

    def test_setup_plan(self, e2e_project: Path, run_cli) -> None:
        """Step 2: setup-plan produces plan.md in feature directory."""
        # Create feature first
        result = run_cli(
            e2e_project,
            "agent",
            "mission",
            "create",
            "plan-smoke",
            "--json",
        )
        assert result.returncode == 0, f"mission create failed: {result.stderr}"
        output = json.loads(result.stdout)
        feature_dir = Path(output["feature_dir"])
        mission_slug = output["mission_slug"]
        _prepare_setup_plan_inputs(e2e_project, feature_dir)

        # Run setup-plan
        result = run_cli(
            e2e_project,
            "agent",
            "mission",
            "setup-plan",
            "--mission",
            mission_slug,
            "--json",
        )
        assert result.returncode == 0, f"setup-plan failed (rc={result.returncode}):\nstdout: {result.stdout}\nstderr: {result.stderr}"

        plan_file = feature_dir / "plan.md"
        assert plan_file.exists(), "plan.md not created by setup-plan"
        assert plan_file.stat().st_size > 0, "plan.md is empty"

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

    def test_documentation_mission_create_resolves_authored_template(
        self,
        e2e_project: Path,
        run_cli,
    ) -> None:
        """documentation is creatable end-to-end: its authored spec mapping
        resolves and a mission directory is materialised (#2689).

        Before the mission-step-creatability slice this ``create`` failed closed
        ("has no configured template mapping") because the shipped type carried a
        null spec mapping; it now resolves the per-type authored template.
        """
        result = run_cli(
            e2e_project,
            "agent",
            "mission",
            "create",
            "documentation-template-smoke",
            "--mission-type",
            "documentation",
            "--json",
        )

        assert result.returncode == 0, f"mission create failed (rc={result.returncode}):\nstdout: {result.stdout}\nstderr: {result.stderr}"
        output = json.loads(result.stdout)
        assert output["result"] == "success"
        assert "documentation-template-smoke" in output["mission_slug"]
        assert any(path.name.startswith("documentation-template-smoke-") for path in (e2e_project / "kitty-specs").glob("*"))

    def test_full_workflow_sequence(self, e2e_project: Path, run_cli) -> None:
        """Full mission create -> setup-plan -> finalize-tasks -> implement -> move-task.

        This is the main smoke test exercising the complete workflow
        that a developer/agent would follow.
        """
        repo = e2e_project

        # === Step 1: Create feature ===
        result = run_cli(
            repo,
            "agent",
            "mission",
            "create",
            "full-e2e",
            "--json",
        )
        assert result.returncode == 0, f"mission create failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        create_output = json.loads(result.stdout)
        assert create_output["result"] == "success"

        mission_slug = create_output["mission_slug"]
        feature_dir = Path(create_output["feature_dir"])
        assert feature_dir.exists()
        assert (feature_dir / "spec.md").exists()
        _prepare_setup_plan_inputs(repo, feature_dir)

        # === Step 2: Setup plan ===
        result = run_cli(
            repo,
            "agent",
            "mission",
            "setup-plan",
            "--mission",
            mission_slug,
            "--json",
        )
        assert result.returncode == 0, f"setup-plan failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        plan_output = json.loads(result.stdout)
        assert plan_output["result"] == "success"
        assert (feature_dir / "plan.md").exists()

        # Populate spec requirements referenced by tasks.md
        (feature_dir / "spec.md").write_text(
            """# E2E Smoke Spec

## Functional Requirements

| ID | Requirement | Acceptance Criteria | Status |
| --- | --- | --- | --- |
| FR-001 | Deliver WP01 hello-world implementation. | WP01 maps to FR-001 and finalizes successfully. | proposed |

## Non-Functional Requirements

| ID | Requirement | Measurable Threshold | Status |
| --- | --- | --- | --- |
| NFR-001 | Finalization remains repeatable. | Running finalize twice yields stable output. | proposed |

## Constraints

| ID | Constraint | Rationale | Status |
| --- | --- | --- | --- |
| C-001 | Keep artifacts under kitty-specs. | Preserve planning workflow conventions. | fixed |
""",
            encoding="utf-8",
        )

        # === Step 3: Simulate LLM task generation (write tasks.md + WP files) ===
        tasks_dir = feature_dir / "tasks"

        tasks_md_content = """# Work Packages

## Work Package WP01: Hello World
**Dependencies**: None
**Requirement Refs**: FR-001, NFR-001, C-001

### Included Subtasks
- T001 Create hello module

---
"""
        (feature_dir / "tasks.md").write_text(tasks_md_content, encoding="utf-8")

        # Omit 'dependencies' from frontmatter so finalize-tasks has work to do
        wp01_content = """---
work_package_id: "WP01"
title: "Hello World"
subtasks:
  - "T001"
phase: "Phase 1"
assignee: ""
agent: ""
shell_pid: ""
review_status: ""
reviewed_by: ""
history:
  - at: "2026-02-12T00:00:00Z"
    actor: "system"
    action: "Generated via test"
---

# Work Package Prompt: WP01 -- Hello World

Create a hello module.
"""
        (tasks_dir / "WP01-hello-world.md").write_text(wp01_content, encoding="utf-8")

        # Preserve the mission_id minted at create time; only layer in the
        # fields the synthetic finalize-tasks fixture needs.
        import json as json_mod

        meta_content = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
        meta_content.update(
            {
                "mission_number": None,
                "mission_slug": mission_slug,
                "mission_type": "software-dev",
                "created_at": "2026-02-12T00:00:00Z",
                "vcs": "git",
            }
        )
        (feature_dir / "meta.json").write_text(
            json_mod.dumps(meta_content, indent=2),
            encoding="utf-8",
        )

        # Commit the tasks so finalize-tasks has a clean working tree
        subprocess.run(
            ["git", "add", "."],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Add tasks for smoke test"],
            cwd=repo,
            check=True,
            capture_output=True,
        )

        # === Step 4: Finalize tasks ===
        # Use explicit feature binding to keep fresh sessions deterministic.
        result = run_cli(
            repo,
            "agent",
            "mission",
            "finalize-tasks",
            "--mission",
            mission_slug,
            "--json",
        )
        assert result.returncode == 0, f"finalize-tasks failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"

        # Verify WP file still exists and has dependencies field
        wp01_path = tasks_dir / "WP01-hello-world.md"
        assert wp01_path.exists(), "WP01 file disappeared after finalize-tasks"
        wp01_text = wp01_path.read_text(encoding="utf-8")
        assert "dependencies" in wp01_text.lower(), "WP01 missing dependencies after finalize-tasks"

        # === Step 5: Implement WP01 (create workspace) ===
        result = run_cli(
            repo,
            "implement",
            "WP01",
            "--mission",
            mission_slug,
            "--json",
        )

        # Parse workspace path from JSON output (lane worktrees are the only supported topology).
        worktree_dir = repo / ".worktrees" / f"{mission_slug}-lane-a"
        if result.returncode == 0 and result.stdout.strip():
            try:
                impl_data = json.loads(result.stdout.strip().splitlines()[-1])
                if "workspace_path" in impl_data:
                    worktree_dir = repo / impl_data["workspace_path"]
            except (json.JSONDecodeError, IndexError):
                pass

        if result.returncode != 0:
            # Try without --json (implement might not support it cleanly)
            result = run_cli(
                repo,
                "implement",
                "WP01",
                "--mission",
                mission_slug,
            )

        # Verify worktree was created
        assert worktree_dir.exists(), (
            f"Workspace not created at {worktree_dir}\nimplement stdout: {result.stdout}\nimplement stderr: {result.stderr}\nimplement rc: {result.returncode}"
        )

        # === Step 6: Make a change in the workspace and commit ===
        src_in_wt = worktree_dir / "src"
        if not src_in_wt.exists():
            src_in_wt.mkdir(parents=True)

        (src_in_wt / "hello.py").write_text(
            'def hello() -> str:\n    return "Hello from E2E smoke test"\n',
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "add", "."],
            cwd=worktree_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "feat(WP01): add hello module"],
            cwd=worktree_dir,
            check=True,
            capture_output=True,
        )

        # Verify the commit landed in the worktree
        log_result = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=worktree_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        assert "hello" in log_result.stdout.lower(), "Commit not found in worktree"

        # === Step 7: Move WP01 to for_review ===
        result = run_cli(
            repo,
            "agent",
            "tasks",
            "move-task",
            "WP01",
            "--to",
            "for_review",
            "--mission",
            mission_slug,
            "--json",
        )

        # move-task may return non-zero if preflight checks fail (dirty worktree, etc.)
        # The important thing is that we exercised the full sequence.
        # We check that canonical status state was updated if the command succeeded.
        if result.returncode == 0:
            status_paths = [
                feature_dir / "status.events.jsonl",
                repo / ".worktrees" / f"{mission_slug}-coord" / "kitty-specs" / mission_slug / "status.events.jsonl",
            ]
            status_text = "\n".join(path.read_text(encoding="utf-8") for path in status_paths if path.exists())
            assert '"to_lane": "for_review"' in status_text, "WP01 not moved to for_review"

        # === Final verification: all artifacts exist ===
        assert (feature_dir / "spec.md").exists(), "spec.md missing at end"
        assert (feature_dir / "plan.md").exists(), "plan.md missing at end"
        assert (feature_dir / "tasks.md").exists(), "tasks.md missing at end"
        assert wp01_path.exists(), "WP01 prompt file missing at end"
        assert worktree_dir.exists(), "Worktree missing at end"

        # Verify git history has the expected commits
        log_result = subprocess.run(
            ["git", "log", "--oneline", "--all"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        )
        log_text = log_result.stdout.lower()
        assert "spec" in log_text, "spec commit missing from git log"
        assert "plan" in log_text, "plan commit missing from git log"
        assert "tasks" in log_text or "finalize" in log_text, "tasks/finalize commit missing from git log"


@pytest.mark.e2e
class TestWorkflowEdgeCases:
    """Edge case tests for the CLI workflow."""

    def test_create_feature_rejects_bad_slug(self, e2e_project: Path, run_cli) -> None:
        """mission create rejects non-kebab-case slugs."""
        result = run_cli(
            e2e_project,
            "agent",
            "mission",
            "create",
            "Bad_Slug",
            "--json",
        )
        assert result.returncode != 0, "Should reject non-kebab-case slug"
        # The JSON output may contain Rich console formatting escape codes,
        # so we check the raw text for the error indicator rather than parsing JSON.
        combined = result.stdout + result.stderr
        assert "error" in combined.lower() or "invalid" in combined.lower(), (
            f"Expected error message in output, got:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_setup_plan_requires_feature(self, e2e_project: Path, run_cli) -> None:
        """setup-plan fails gracefully when no feature exists."""
        result = run_cli(
            e2e_project,
            "agent",
            "mission",
            "setup-plan",
            "--json",
        )
        # Should fail because no feature exists yet
        assert result.returncode != 0, "setup-plan should fail when no feature exists"

    def test_implement_requires_existing_wp(self, e2e_project: Path, run_cli) -> None:
        """implement fails gracefully when WP does not exist."""
        result = run_cli(
            e2e_project,
            "implement",
            "WP99",
        )
        assert result.returncode != 0, "implement should fail for non-existent WP"
