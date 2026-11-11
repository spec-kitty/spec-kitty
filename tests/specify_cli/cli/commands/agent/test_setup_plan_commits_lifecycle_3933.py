"""#3933: ``setup-plan`` commits the lifecycle events it writes together with the plan.

Before the fix ``setup-plan`` committed ``plan.md`` alone and appended
SpecifyCompleted, PlanStarted and (after its commit) PlanCompleted to the
Mission's ``status.events.jsonl``, leaving that log dirty; the next gate then
refused on it. Reproduced on this very Mission (tracer, hand commit 2).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.integration.cli_mission_fixture_7545 import dirty, flat, git, init_repo, json_of, run_sk

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.timeout(900)]

_PLAN = """# Implementation Plan

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: none
**Storage**: N/A
**Testing**: pytest
**Target Platform**: Linux
**Project Type**: single
"""


def test_setup_plan_commits_plan_and_lifecycle_events_together(tmp_path: Path) -> None:
    repo, env = init_repo(tmp_path)
    created = run_sk(
        repo,
        env,
        *("agent", "mission", "create", "gamma", "--mission-type", "software-dev", "--topology", "single_branch"),
        *("--target-branch", "dev", "--friendly-name", "gamma", "--purpose-tldr", "g", "--purpose-context", "Fixture.", "--json"),
        check=True,
    )
    slug = str(json_of(created)["mission_slug"])
    feature_dir = repo / "kitty-specs" / slug
    (feature_dir / "spec.md").write_text(
        "# Spec\n\n## Requirements\n\n| ID | Title | User Story | Priority | Status |\n|---|---|---|---|---|\n"
        "| FR-001 | things work | As a user I want things so that ok. | High | Open |\n",
        encoding="utf-8",
    )
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "spec")
    run_sk(repo, env, "agent", "mission", "setup-plan", "--mission", slug, "--json", check=True)  # scaffold
    (feature_dir / "plan.md").write_text(_PLAN, encoding="utf-8")

    proc = run_sk(repo, env, "agent", "mission", "setup-plan", "--mission", slug, "--json")

    assert proc.returncode == 0, flat(proc)[-2000:]
    payload = json_of(proc)
    assert payload["commit_created"] is True, payload
    assert payload["commit_hash"] == git(repo, "rev-parse", "HEAD")
    committed = git(repo, "show", "--name-only", "--format=", "HEAD").splitlines()
    assert f"kitty-specs/{slug}/plan.md" in committed
    assert f"kitty-specs/{slug}/status.events.jsonl" in committed
    assert dirty(repo) == []
    events = [json.loads(line)["event_type"] for line in (feature_dir / "status.events.jsonl").read_text(encoding="utf-8").splitlines() if '"event_type"' in line]
    assert "PlanCompleted" in events
