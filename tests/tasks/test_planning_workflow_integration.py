"""Integration tests for planning workflow in main repository (v0.11.0+).

Tests that /spec-kitty.specify, /spec-kitty.plan, and /spec-kitty.tasks workflows
work correctly in main repository WITHOUT creating worktrees.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.tasks.conftest import create_mission_fast

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]  # non_sandbox: run_cli subprocess fixture


@pytest.fixture(autouse=True)
def _disable_saas_sync_for_planning_workflow_tests(
    monkeypatch: pytest.MonkeyPatch,
    isolated_env: dict[str, str],
) -> None:
    """Opt out of the autouse ``SPEC_KITTY_ENABLE_SAAS_SYNC=1`` fixture.

    The autouse fixture in ``tests/conftest.py`` flips the SAAS_SYNC
    flag on globally so legacy sync/auth tests still exercise the
    wired path. This module's tests exercise the planning workflow
    (``mission create``, ``setup-plan``) end-to-end via subprocess
    invocations; they do not exercise the sync emission path.
    Upstream commit ``cc5e1ca9`` adds an FR-011 auth-presence gate at
    the head of ``setup-plan`` that exits 2
    (``SAAS_SYNC_UNAUTHENTICATED``) before the contract under test
    runs, because the test environment has no auth scope.

    Unset the flag (also for the subprocess via ``isolated_env``'s
    ``os.environ.copy()``) so these tests exercise the
    SAAS-sync-disabled planning path.
    """
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
    isolated_env["SPEC_KITTY_ENABLE_SAAS_SYNC"] = "0"
    isolated_env["SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS"] = "1"

SUBSTANTIVE_PLAN_TEMPLATE = """# Implementation Plan

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: Typer
"""


def test_create_feature_in_main_no_worktree(test_project: Path, run_cli) -> None:
    """Test that create command works in main without creating worktree."""
    # Run create command
    result = run_cli(
        test_project,
        "agent",
        "mission",
        "create",
        "test-planning-workflow",
        "--json",
    )

    assert result.returncode == 0, f"create failed: {result.stderr}"
    payload = json.loads(result.stdout)
    mission_slug = payload["mission_slug"]
    feature_dir = Path(payload["feature_dir"])

    # Verify feature directory created in main repo
    assert feature_dir.exists(), "Feature directory not created in main repo"
    assert (feature_dir / "spec.md").exists(), "spec.md not created"
    assert (feature_dir / "tasks").is_dir(), "tasks/ directory not created"
    assert (feature_dir / "checklists").is_dir(), "checklists/ directory not created"
    assert (feature_dir / "research").is_dir(), "research/ directory not created"

    # Verify NO worktree was created
    worktree_dir = test_project / ".worktrees" / mission_slug
    assert not worktree_dir.exists(), "Worktree should NOT be created during feature creation"

    # Verify spec.md remains an uncommitted scaffold until /spec-kitty.specify
    # writes substantive content.
    spec_tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str((feature_dir / "spec.md").relative_to(test_project))],
        cwd=test_project,
        capture_output=True,
        text=True,
    )
    assert spec_tracked.returncode != 0, "scaffold spec.md should not be committed at create time"

def test_setup_plan_in_main(test_project: Path, run_cli) -> None:
    """Test that setup-plan command works in main repo and commits plan.md."""
    # Setup: create mission in-process (not the test target)
    feature_dir = create_mission_fast(test_project, "plan-test")
    mission_slug = feature_dir.name

    # Create a minimal plan template for testing
    plan_template_dir = test_project / ".kittify" / "templates"
    plan_template_dir.mkdir(parents=True, exist_ok=True)
    plan_template = plan_template_dir / "plan-template.md"
    plan_template.write_text(SUBSTANTIVE_PLAN_TEMPLATE, encoding="utf-8")

    # Run setup-plan command
    result = run_cli(
        test_project,
        "agent",
        "mission",
        "setup-plan",
        "--mission",
        mission_slug,
        "--json",
    )

    assert result.returncode == 0, f"setup-plan failed: {result.stderr}"

    # Verify plan.md created in feature directory
    plan_file = feature_dir / "plan.md"
    assert plan_file.exists(), "plan.md not created"

    # Verify plan.md was committed to main
    log_result = subprocess.run(
        ["git", "log", "--oneline", "-2"],
        cwd=test_project,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "plan" in log_result.stdout.lower(), "plan.md should be committed to main"

def test_setup_plan_explicit_feature_reports_spec_path(test_project: Path, run_cli) -> None:
    """setup-plan with explicit --mission returns deterministic context fields."""
    # Setup: create mission in-process
    feature_dir = create_mission_fast(test_project, "plan-explicit-test")
    mission_slug = feature_dir.name

    plan_template_dir = test_project / ".kittify" / "templates"
    plan_template_dir.mkdir(parents=True, exist_ok=True)
    (plan_template_dir / "plan-template.md").write_text(SUBSTANTIVE_PLAN_TEMPLATE, encoding="utf-8")

    result = run_cli(
        test_project,
        "agent",
        "mission",
        "setup-plan",
        "--mission",
        mission_slug,
        "--json",
    )

    assert result.returncode == 0, f"setup-plan failed: {result.stderr}"
    payload = json.loads(result.stdout)
    assert payload["result"] == "success"
    assert payload["mission_slug"] == mission_slug
    assert payload["feature_dir"] == str(feature_dir)
    assert payload["spec_file"] == str(feature_dir / "spec.md")
    assert payload["plan_file"] == str(feature_dir / "plan.md")

def test_setup_plan_ambiguous_context_returns_candidates(test_project: Path, run_cli) -> None:
    """setup-plan without explicit context returns candidate missions and remediation."""
    # Setup: create two missions in-process
    create_mission_fast(test_project, "feature-a", number=1)
    create_mission_fast(test_project, "feature-b", number=2)

    result = run_cli(
        test_project,
        "agent",
        "mission",
        "setup-plan",
        "--json",
    )

    assert result.returncode != 0, "setup-plan should fail without explicit mission in ambiguous context"
    payload = json.loads(result.stdout.strip().split("\n")[0])
    assert payload["error_code"] == "PLAN_CONTEXT_UNRESOLVED"
    assert len(payload["available_missions"]) >= 2
    assert "--mission" in payload["example_command"]

def test_setup_plan_missing_spec_reports_absolute_path(test_project: Path, run_cli) -> None:
    """setup-plan should fail when spec.md is missing for an explicit mission."""
    # Setup: create mission in-process, then remove spec.md
    feature_dir = create_mission_fast(test_project, "missing-spec")
    mission_slug = feature_dir.name
    spec_file = feature_dir / "spec.md"
    spec_file.unlink()

    result = run_cli(
        test_project,
        "agent",
        "mission",
        "setup-plan",
        "--mission",
        mission_slug,
        "--json",
    )

    assert result.returncode != 0, "setup-plan should fail when spec.md is missing"
    payload = json.loads(result.stdout.strip().split("\n")[0])
    assert payload["error_code"] == "SPEC_FILE_MISSING"
    assert payload["mission_slug"] == mission_slug
    assert payload["spec_file"] == str(spec_file.resolve())

def test_full_planning_workflow_no_worktrees(test_project: Path, run_cli) -> None:
    """Test complete planning workflow (specify → plan → [manual tasks]) without worktrees."""
    # Create plan template
    plan_template_dir = test_project / ".kittify" / "templates"
    plan_template_dir.mkdir(parents=True, exist_ok=True)
    (plan_template_dir / "plan-template.md").write_text(SUBSTANTIVE_PLAN_TEMPLATE, encoding="utf-8")

    # Step 1: Create mission in-process (not the test target for this test)
    feature_dir = create_mission_fast(test_project, "full-workflow-test")
    mission_slug = feature_dir.name
    assert feature_dir.exists(), "Feature directory not created"
    assert (feature_dir / "spec.md").exists(), "spec.md not created"

    # Step 2: Setup plan (plan phase)
    result = run_cli(
        test_project,
        "agent",
        "mission",
        "setup-plan",
        "--mission",
        mission_slug,
        "--json",
    )
    assert result.returncode == 0, "Plan setup failed"
    assert (feature_dir / "plan.md").exists(), "plan.md not created"

    # Populate spec requirements referenced by tasks.md
    spec_md = feature_dir / "spec.md"
    spec_md.write_text(
        """# Full Workflow Test Spec

## Functional Requirements

| ID | Requirement | Acceptance Criteria | Status |
| --- | --- | --- | --- |
| FR-001 | Foundation tasks are implemented first. | WP01 is planned and finalized. | proposed |
| FR-002 | API tasks can depend on foundation tasks. | WP02 depends on WP01. | proposed |

## Non-Functional Requirements

| ID | Requirement | Measurable Threshold | Status |
| --- | --- | --- | --- |
| NFR-001 | Finalization must be deterministic. | Re-running finalize does not rewrite unchanged files. | proposed |
| NFR-002 | Dependency parsing must remain explicit. | Dependency links are represented in WP frontmatter. | proposed |

## Constraints

| ID | Constraint | Rationale | Status |
| --- | --- | --- | --- |
| C-001 | Keep generated artifacts in kitty-specs. | Maintains planning workflow structure. | fixed |
""",
        encoding="utf-8",
    )

    # Step 3: Generate sample WP files and tasks.md (simulating /spec-kitty.tasks LLM output)
    tasks_dir = feature_dir / "tasks"

    # Create tasks.md with dependencies
    tasks_md = feature_dir / "tasks.md"
    tasks_md.write_text("""# Work Packages

## Work Package WP01: Foundation
**Dependencies**: None
**Requirement Refs**: FR-001, NFR-001, C-001

### Included Subtasks
- T001 Setup infrastructure
- T002 Create base schema

---

## Work Package WP02: API Layer
**Dependencies**: Depends on WP01
**Requirement Refs**: FR-002, NFR-002

### Included Subtasks
- T003 Build REST endpoints
""", encoding="utf-8")

    # Create WP files WITHOUT dependencies (simulate LLM before finalize-tasks)
    wp01_content = """---
work_package_id: "WP01"
title: "Foundation"
subtasks:
  - "T001"
  - "T002"
phase: "Phase 1"
assignee: ""
agent: ""
shell_pid: ""
review_status: ""
reviewed_by: ""
owned_files:
  - src/foundation/**
authoritative_surface: src/foundation/
history:
  - at: "2025-01-01T00:00:00Z"
    actor: "system"
    action: "Generated via test"
---

# Work Package: WP01

Test work package content.
"""
    (tasks_dir / "WP01-foundation.md").write_text(wp01_content, encoding="utf-8")

    wp02_content = """---
work_package_id: "WP02"
title: "API Layer"
subtasks:
  - "T003"
phase: "Phase 1"
assignee: ""
agent: ""
shell_pid: ""
review_status: ""
reviewed_by: ""
owned_files:
  - src/api/**
authoritative_surface: src/api/
history:
  - at: "2025-01-01T00:00:00Z"
    actor: "system"
    action: "Generated via test"
---

# Work Package: WP02

Test work package content.
"""
    (tasks_dir / "WP02-api.md").write_text(wp02_content, encoding="utf-8")

    # Step 4: Run finalize-tasks to parse dependencies and commit
    result = run_cli(
        test_project,
        "agent",
        "mission",
        "finalize-tasks",
        "--mission",
        mission_slug,
        "--json",
    )
    assert result.returncode == 0, f"finalize-tasks failed: {result.stderr}"

    # Verify dependencies were added by finalize-tasks
    wp01_updated = (tasks_dir / "WP01-foundation.md").read_text()
    assert "dependencies" in wp01_updated.lower(), "WP01 should have dependencies field"
    assert "planning_base_branch: main" in wp01_updated, (
        "WP01 should record the planning branch used to generate tasks"
    )
    assert "merge_target_branch: main" in wp01_updated, (
        "WP01 should record the final merge target"
    )

    wp02_updated = (tasks_dir / "WP02-api.md").read_text()
    assert "dependencies" in wp02_updated.lower(), "WP02 should have dependencies field"
    assert "WP01" in wp02_updated, "WP02 should depend on WP01"
    assert "planning_base_branch: main" in wp02_updated
    assert "merge_target_branch: main" in wp02_updated

    # Verify: NO worktrees directory exists
    worktrees_dir = test_project / ".worktrees"
    if worktrees_dir.exists():
        # Directory might exist but should be empty
        worktree_contents = list(worktrees_dir.iterdir())
        assert len(worktree_contents) == 0, "No worktrees should be created during planning"

    # Verify: All artifacts committed to main branch
    log_result = subprocess.run(
        ["git", "log", "--oneline", "--all"],
        cwd=test_project,
        capture_output=True,
        text=True,
        check=True,
    )
    commit_log = log_result.stdout.lower()

    assert "spec" in commit_log, "spec.md commit missing"
    assert "plan" in commit_log, "plan.md commit missing"
    assert "tasks" in commit_log, "tasks commit missing"

    # Verify tasks.md included in latest commit
    commit_files = subprocess.run(
        ["git", "show", "--name-only", "--pretty=format:%H", "HEAD"],
        cwd=test_project,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "tasks.md" in commit_files.stdout, "tasks.md should be committed with tasks"

    # Verify: Current branch is still main
    branch_result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=test_project,
        capture_output=True,
        text=True,
        check=True,
    )
    default_branch = branch_result.stdout.strip()
    assert default_branch in ("main", "master"), f"Should still be on default branch, got: {default_branch}"

def test_check_prerequisites_works_in_main(test_project: Path, run_cli) -> None:
    """Test that check-prerequisites command works when run from main repo."""
    # Setup: create mission in-process
    feature_dir = create_mission_fast(test_project, "prereq-test")

    # Run check-prerequisites from main repo
    result = run_cli(
        test_project,
        "agent",
        "mission",
        "check-prerequisites",
        "--mission",
        feature_dir.name,
        "--json",
    )

    assert result.returncode == 0, f"check-prerequisites failed: {result.stderr}"

    # Should find the latest mission and validate its structure
    output = json.loads(result.stdout)
    assert output["valid"] is True, "Feature structure should be valid"
    assert "spec_file" in output["paths"], "Should detect spec.md"

def test_check_prerequisites_ambiguous_context_returns_candidates(
    test_project: Path, run_cli
) -> None:
    """check-prerequisites should fail with remediation when feature context is ambiguous."""
    # Setup: create two missions in-process
    create_mission_fast(test_project, "ambiguous-a", number=1)
    create_mission_fast(test_project, "ambiguous-b", number=2)

    result = run_cli(
        test_project,
        "agent",
        "mission",
        "check-prerequisites",
        "--json",
        "--paths-only",
        "--include-tasks",
    )

    assert result.returncode != 0, "Ambiguous mission context should fail without --mission"
    payload = json.loads(result.stdout.strip().split("\n")[0])
    assert payload["error_code"] == "MISSION_CONTEXT_UNRESOLVED"
    assert len(payload["available_missions"]) >= 2
    assert "--mission" in payload["example_command"]

def test_finalize_tasks_ambiguous_context_returns_candidates(
    test_project: Path, run_cli
) -> None:
    """finalize-tasks should fail with remediation when feature context is ambiguous."""
    # Setup: create two missions in-process
    create_mission_fast(test_project, "ambiguous-finalize-a", number=1)
    create_mission_fast(test_project, "ambiguous-finalize-b", number=2)

    result = run_cli(
        test_project,
        "agent",
        "mission",
        "finalize-tasks",
        "--json",
    )

    assert result.returncode != 0, "Ambiguous mission context should fail without --mission"
    payload = json.loads(result.stdout.strip().split("\n")[0])
    assert payload["error_code"] == "MISSION_CONTEXT_UNRESOLVED"
    assert len(payload["available_missions"]) >= 2
    assert "finalize-tasks --mission" in payload["example_command"]
