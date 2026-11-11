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


# WP04 review follow-up: pin the partition decision of ``_lifecycle_log_for_plan_commit`` directly.


@pytest.mark.parametrize(
    ("topology", "expected"),
    [("SINGLE_BRANCH", True), ("LANES", True), ("COORD", False), ("LANES_WITH_COORD", False)],
)
def test_lifecycle_log_joins_the_plan_commit_only_on_a_primary_status_partition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, topology: str, expected: bool
) -> None:
    from types import SimpleNamespace

    from mission_runtime import MissionTopology
    from specify_cli.cli.commands.agent.mission_setup_plan import _lifecycle_log_for_plan_commit

    log = tmp_path / "status.events.jsonl"
    log.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr("mission_runtime.resolve_topology", lambda *_a, **_k: MissionTopology[topology])

    assert _lifecycle_log_for_plan_commit(tmp_path, tmp_path, "m", None) == ((log,) if expected else ())
    # An owned run reads the topology off its fact and never re-resolves the repository.
    monkeypatch.setattr("mission_runtime.resolve_topology", lambda *_a, **_k: pytest.fail("owned run re-resolved the topology"))
    owned = SimpleNamespace(topology=MissionTopology[topology])
    assert _lifecycle_log_for_plan_commit(tmp_path, tmp_path, "m", owned) == ((log,) if expected else ())  # type: ignore[arg-type]


def test_no_lifecycle_log_means_nothing_extra_to_commit(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from mission_runtime import MissionTopology
    from specify_cli.cli.commands.agent.mission_setup_plan import _lifecycle_log_for_plan_commit

    owned = SimpleNamespace(topology=MissionTopology.SINGLE_BRANCH)
    assert _lifecycle_log_for_plan_commit(tmp_path, tmp_path, "m", owned) == ()  # type: ignore[arg-type]
