"""A coord mission's lifecycle never commits a status byte-set to the target branch (#5440).

Issue #5440 reports three CLI commits that put ``status.events.jsonl`` on a
coord mission's target branch: the create scaffold commit, the ``implement``
claim commit and the ``accept`` residual commit. The create leg is pinned
narrowly by ``tests/core/test_mission_create_coord_status_placement.py``
(PR #5518). This test drives the later legs through the real CLI: create,
setup-plan, finalize-tasks, record-analysis, implement and a lane move. After
every step it reads the target branch's tree in git. It also asserts the
primary mission dir never holds a status log, which is the only source
``accept``'s primary-residual commit could pick one up from.

On ``main`` before the fix this test fails at the create step.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.e2e.test_cli_smoke import _prepare_setup_plan_inputs

pytestmark = [pytest.mark.e2e, pytest.mark.slow, pytest.mark.git_repo]

_SPEC = """# Coord status placement

## Functional Requirements

| ID | Requirement | Acceptance Criteria | Status |
| --- | --- | --- | --- |
| FR-001 | Deliver WP01. | WP01 maps to FR-001. | proposed |
"""

_TASKS = """# Work Packages

## Work Package WP01: Hello
**Dependencies**: None
**Requirement Refs**: FR-001

### Included Subtasks
- T001 Create hello module

---
"""

_WP01 = """---
work_package_id: "WP01"
title: "Hello"
subtasks:
  - "T001"
phase: "Phase 1"
---

# Work Package Prompt: WP01 -- Hello

Create a hello module.
"""

_ANALYSIS = "# Analysis Report\n\nNo issues found. Every requirement maps to a work package.\n"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout


def _assert_target_clean(repo: Path, target: str, slug: str, feature_dir: Path, step: str) -> None:
    on_target = [path for path in _git(repo, "ls-tree", "-r", "--name-only", target).splitlines() if path.startswith(f"kitty-specs/{slug}/status.")]
    assert not on_target, f"after {step}: target branch {target!r} carries coord-owned status byte-set(s) {on_target} (#5440)"
    stray = [name for name in ("status.events.jsonl", "status.json") if (feature_dir / name).exists()]
    assert not stray, f"after {step}: the primary mission dir holds status byte-set(s) {stray} (#5440)"


def _ok(result: subprocess.CompletedProcess[str], step: str) -> None:
    assert result.returncode == 0, f"{step} failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"


def test_coord_lifecycle_keeps_status_off_the_target_branch(e2e_project: Path, run_cli: Callable[..., subprocess.CompletedProcess[str]]) -> None:
    repo = e2e_project
    target = _git(repo, "branch", "--show-current").strip()
    with (repo / ".gitignore").open("a", encoding="utf-8") as handle:
        handle.write(".kittify/derived/\n")
    _git(repo, "commit", "-am", "Ignore derived runtime state")

    result = run_cli(repo, "agent", "mission", "create", "coord-lifecycle", "--topology", "coord", "--json")
    _ok(result, "mission create")
    created = json.loads(result.stdout)
    slug = created["mission_slug"]
    feature_dir = Path(created["feature_dir"])
    coordination_branch = created["coordination_branch"]
    assert coordination_branch, "a coord create must mint a coordination branch"
    assert f"kitty-specs/{slug}/status.events.jsonl" in _git(repo, "ls-tree", "-r", "--name-only", coordination_branch)
    _assert_target_clean(repo, target, slug, feature_dir, "create")

    _prepare_setup_plan_inputs(repo, feature_dir)
    _ok(run_cli(repo, "agent", "mission", "setup-plan", "--mission", slug, "--json"), "setup-plan")
    _assert_target_clean(repo, target, slug, feature_dir, "setup-plan")

    (feature_dir / "spec.md").write_text(_SPEC, encoding="utf-8")
    (feature_dir / "tasks.md").write_text(_TASKS, encoding="utf-8")
    (feature_dir / "tasks" / "WP01-hello.md").write_text(_WP01, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "Add tasks")
    _ok(run_cli(repo, "agent", "mission", "finalize-tasks", "--mission", slug, "--json"), "finalize-tasks")
    _assert_target_clean(repo, target, slug, feature_dir, "finalize-tasks")
    coord_log = _git(repo, "show", f"{coordination_branch}:kitty-specs/{slug}/status.events.jsonl")
    for event_type in ("TasksStarted", "WPCreated", "TasksCompleted"):
        assert event_type in coord_log, f"finalize-tasks must record {event_type} in the coordination log"

    analysis = repo.parent / "analysis.md"
    analysis.write_text(_ANALYSIS, encoding="utf-8")
    _ok(
        run_cli(repo, "agent", "mission", "record-analysis", "--mission", slug, "--input-file", str(analysis), "--agent", "claude"),
        "record-analysis",
    )
    _assert_target_clean(repo, target, slug, feature_dir, "record-analysis")

    _ok(run_cli(repo, "agent", "action", "implement", "WP01", "--mission", slug, "--agent", "claude"), "implement")
    _assert_target_clean(repo, target, slug, feature_dir, "implement")

    _ok(
        run_cli(repo, "agent", "tasks", "move-task", "WP01", "--to", "for_review", "--mission", slug, "--force", "--note", "e2e"),
        "move-task",
    )
    _assert_target_clean(repo, target, slug, feature_dir, "move-task")

    # Every lane transition so far landed on the coordination branch.
    coord_log = _git(repo, "show", f"{coordination_branch}:kitty-specs/{slug}/status.events.jsonl")
    assert '"to_lane": "for_review"' in coord_log
    assert "MissionCreated" in coord_log
