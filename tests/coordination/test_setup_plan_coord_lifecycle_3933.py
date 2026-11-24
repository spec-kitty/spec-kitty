"""#3933 (Slice 1b): ``setup-plan`` commits its lifecycle events on a coordination Mission.

On a Mission whose coordination branch exists when setup-plan runs (an explicit
``--topology coord`` / ``lanes_with_coord``), setup-plan writes ``SpecifyCompleted``,
``PlanStarted`` and ``PlanCompleted`` to the coordination worktree's status log.
Before this fix nothing committed them there: the repository root checkout stayed
clean, the coordination worktree was left with a modified ``status.events.jsonl``.
Mission ``setup-plan-coord-lifecycle-commit-01M84SXJ``; every test drives the real
CLI on a real git repository.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import pytest

from tests.integration.cli_mission_fixture_7545 import dirty, flat, git, init_repo, json_of, run_sk

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.timeout(900)]

_SPEC = (
    "# Spec\n\n## Requirements\n\n| ID | Title | User Story | Priority | Status |\n|---|---|---|---|---|\n"
    "| FR-001 | things work | As a user I want things so that ok. | High | Open |\n"
)
_PLAN = """# Implementation Plan

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: none
**Storage**: N/A
**Testing**: pytest
**Target Platform**: Linux
**Project Type**: single
"""
_SETUP_PLAN_EVENTS = ("SpecifyCompleted", "PlanStarted", "PlanCompleted")


class _Mission:
    def __init__(self, repo: Path, env: dict[str, str], slug: str, mission_dir: Path) -> None:
        self.repo = repo
        self.env = env
        self.slug = slug
        self.mission_dir = mission_dir

    @property
    def meta(self) -> dict[str, object]:
        data: dict[str, object] = json.loads((self.mission_dir / "meta.json").read_text(encoding="utf-8"))
        return data

    @property
    def coord_branch(self) -> str:
        return str(self.meta["coordination_branch"])

    @property
    def coord_root(self) -> Path:
        return self.repo / ".worktrees" / f"{self.slug}-coord"

    def setup_plan(self) -> dict[str, object]:
        proc = run_sk(self.repo, self.env, "agent", "mission", "setup-plan", "--mission", self.slug, "--json")
        assert proc.returncode == 0, flat(proc)[-2000:]
        return json_of(proc)

    def write_plan(self) -> None:
        (self.mission_dir / "plan.md").write_text(_PLAN, encoding="utf-8")

    def coord_events(self) -> list[str]:
        text = git(self.repo, "show", f"{self.coord_branch}:kitty-specs/{self.slug}/status.events.jsonl")
        return [str(json.loads(line).get("event_type")) for line in text.splitlines() if line.strip()]


def _mission(tmp_path: Path, topology: str | None) -> _Mission:
    repo, env = init_repo(tmp_path)
    topology_args = ("--topology", topology) if topology else ()
    created = run_sk(
        repo,
        env,
        *("agent", "mission", "create", "gamma", "--mission-type", "software-dev", *topology_args),
        *("--target-branch", "dev", "--friendly-name", "gamma", "--purpose-tldr", "g", "--purpose-context", "Fixture.", "--json"),
        check=True,
    )
    payload = json_of(created)
    mission = _Mission(repo, env, str(payload["mission_slug"]), Path(str(payload["mission_dir"])))
    (mission.mission_dir / "spec.md").write_text(_SPEC, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "spec")
    return mission


@pytest.mark.parametrize("topology", ["lanes_with_coord", "coord"])
def test_coord_setup_plan_commits_lifecycle_events_on_the_coordination_branch(tmp_path: Path, topology: str) -> None:
    mission = _mission(tmp_path, topology)
    mission.setup_plan()  # scaffold
    mission.write_plan()

    payload = mission.setup_plan()

    assert payload["commit_created"] is True, payload
    assert dirty(mission.repo) == []
    assert dirty(mission.coord_root) == [], "setup-plan left its lifecycle events uncommitted in the coordination worktree"
    events = mission.coord_events()
    assert all(event in events for event in _SETUP_PLAN_EVENTS), events
    lifecycle = payload["lifecycle_commit"]
    assert isinstance(lifecycle, dict)
    assert lifecycle["status"] == "committed", "the run that adds PlanCompleted must commit"
    assert git(mission.repo, "rev-parse", mission.coord_branch) == git(mission.coord_root, "rev-parse", "HEAD")


def test_coord_scaffold_only_run_commits_the_events_recorded_so_far(tmp_path: Path) -> None:
    mission = _mission(tmp_path, "lanes_with_coord")

    payload = mission.setup_plan()

    assert payload.get("scaffold_only") is True, payload
    assert dirty(mission.coord_root) == []
    events = mission.coord_events()
    assert "SpecifyCompleted" in events and "PlanStarted" in events, events
    lifecycle = payload["lifecycle_commit"]
    assert isinstance(lifecycle, dict) and lifecycle["status"] == "committed"


def test_coord_rerun_makes_no_new_commit(tmp_path: Path) -> None:
    mission = _mission(tmp_path, "lanes_with_coord")
    mission.setup_plan()
    mission.write_plan()
    mission.setup_plan()
    tip = git(mission.repo, "rev-parse", mission.coord_branch)

    payload = mission.setup_plan()

    assert git(mission.repo, "rev-parse", mission.coord_branch) == tip
    lifecycle = payload["lifecycle_commit"]
    assert isinstance(lifecycle, dict) and lifecycle["status"] == "unchanged"
    assert dirty(mission.coord_root) == []


@pytest.mark.parametrize("topology", ["single_branch", "lanes", None], ids=["single_branch", "lanes", "default_before_settlement"])
def test_non_coordination_setup_plan_is_unchanged(tmp_path: Path, topology: str | None) -> None:
    mission = _mission(tmp_path, topology)
    mission.setup_plan()
    mission.write_plan()

    payload = mission.setup_plan()

    assert payload["commit_created"] is True, payload
    committed = git(mission.repo, "show", "--name-only", "--format=", str(payload["commit_hash"])).splitlines()
    assert f"kitty-specs/{mission.slug}/plan.md" in committed
    assert f"kitty-specs/{mission.slug}/status.events.jsonl" in committed
    assert dirty(mission.repo) == []
    assert "lifecycle_commit" not in payload
    assert not (mission.repo / ".worktrees").exists()


# ---------------------------------------------------------------------------
# FR-004: a refused coordination commit fails loud (in process, so the router can be refused)
# ---------------------------------------------------------------------------


def _run_setup_plan_in_process(mission: _Mission, monkeypatch: pytest.MonkeyPatch) -> tuple[int, dict[str, object]]:
    from typer.testing import CliRunner

    from specify_cli.cli.commands.agent import mission as mission_module

    for key, value in mission.env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.chdir(mission.repo)
    monkeypatch.setattr(mission_module, "locate_project_root", lambda *a, **k: mission.repo)
    result = CliRunner().invoke(mission_module.app, ["setup-plan", "--mission", mission.slug, "--json"], catch_exceptions=False)
    payloads = [json.loads(line) for line in result.output.splitlines() if line.startswith("{")]
    return result.exit_code, (payloads[-1] if payloads else {"raw": result.output})


@pytest.mark.parametrize("status", ["error", "no_op_wrong_surface"])
def test_refused_coordination_commit_fails_loud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: Literal["error", "no_op_wrong_surface"]) -> None:
    from mission_runtime import MissionArtifactKind
    from specify_cli.coordination import commit_router
    from specify_cli.coordination.commit_router import CommitRouterResult

    mission = _mission(tmp_path, "lanes_with_coord")
    mission.setup_plan()
    mission.write_plan()
    real = commit_router.commit_for_mission

    def _refuse_status(*args: Any, **kwargs: Any) -> CommitRouterResult:
        if kwargs.get("kind") is MissionArtifactKind.STATUS_STATE:
            return CommitRouterResult(status=status, placement_ref=mission.coord_branch, diagnostic="coordination surface refused (test)")
        return real(*args, **kwargs)

    monkeypatch.setattr(commit_router, "commit_for_mission", _refuse_status)

    code, payload = _run_setup_plan_in_process(mission, monkeypatch)

    assert code == 1, payload
    assert payload["error_code"] == "SETUP_PLAN_LIFECYCLE_UNCOMMITTED", payload
    assert "coordination surface refused (test)" in str(payload["lifecycle_diagnostic"])
    uncommitted = payload["lifecycle_events_in_log"]
    assert isinstance(uncommitted, list) and set(_SETUP_PLAN_EVENTS) <= set(uncommitted)
    assert payload["commit_hash"], "the plan commit that landed must still be reported"
    assert payload["phase_complete"] is False
    assert "commit them in that checkout" in str(payload["error"]), "a non-loss refusal keeps the plain remedy"
    assert f"The plan commit {payload['commit_hash']} was kept" in str(payload["error"])


# ---------------------------------------------------------------------------
# Review cycle 1, B1: never commit a worktree log that lost events the coordination branch committed
# ---------------------------------------------------------------------------


def _advance_coord_branch_with_foreign_event(mission: _Mission) -> tuple[str, str]:
    """Another writer appends one event on the coordination branch by plumbing; the worktree is not resynced.

    Returns ``(new_tip, foreign_event_id)``.
    """
    import os
    import subprocess

    branch = mission.coord_branch
    head = git(mission.repo, "rev-parse", branch)
    rel = f"kitty-specs/{mission.slug}/status.events.jsonl"
    committed = git(mission.repo, "show", f"{head}:{rel}")
    template = json.loads(committed.splitlines()[-1])
    foreign_id = "01ZZZZZZZZZZZZZZZZZZZZZZZZ"
    template.update({"event_id": foreign_id, "event_type": "ForeignWriterEvent"})
    content = committed + "\n" + json.dumps(template, sort_keys=True) + "\n"
    blob = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=mission.repo, input=content, capture_output=True, text=True, check=True).stdout.strip()
    env = {**os.environ, "GIT_INDEX_FILE": str(mission.repo / ".git" / "foreign-writer.index")}
    subprocess.run(["git", "read-tree", head], cwd=mission.repo, env=env, check=True)
    subprocess.run(["git", "update-index", "--cacheinfo", f"100644,{blob},{rel}"], cwd=mission.repo, env=env, check=True)
    tree = subprocess.run(["git", "write-tree"], cwd=mission.repo, env=env, capture_output=True, text=True, check=True).stdout.strip()
    commit = git(mission.repo, "-c", "user.email=t@example.com", "-c", "user.name=t", "commit-tree", tree, "-p", head, "-m", "foreign writer")
    git(mission.repo, "update-ref", f"refs/heads/{branch}", commit, head)
    return commit, foreign_id


def test_coord_setup_plan_never_erases_events_the_branch_committed(tmp_path: Path) -> None:
    mission = _mission(tmp_path, "lanes_with_coord")
    mission.setup_plan()  # scaffold
    tip, foreign_id = _advance_coord_branch_with_foreign_event(mission)
    mission.write_plan()

    proc = run_sk(mission.repo, mission.env, "agent", "mission", "setup-plan", "--mission", mission.slug, "--json")

    assert proc.returncode == 1, flat(proc)[-2000:]
    payload = json_of(proc)
    assert payload["error_code"] == "SETUP_PLAN_LIFECYCLE_UNCOMMITTED", payload
    assert "COORD_STATUS_SURFACE_DIVERGED" in str(payload["lifecycle_diagnostic"])
    error = str(payload["error"])
    assert "commit them in that checkout" not in error, "committing the stale log erases the committed events"
    assert "Do not commit this checkout's status log" in error
    assert "re-run setup-plan" in error
    assert git(mission.repo, "rev-parse", mission.coord_branch) == tip, "the coordination branch must not move"
    assert foreign_id in git(mission.repo, "show", f"{mission.coord_branch}:kitty-specs/{mission.slug}/status.events.jsonl")


# ---------------------------------------------------------------------------
# Review cycle 1, S1/S2/S3: every failure reaches the named refusal; the helpers' edges
# ---------------------------------------------------------------------------


def test_raising_router_reaches_the_named_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from mission_runtime import MissionArtifactKind
    from specify_cli.coordination import commit_router
    from specify_cli.coordination.commit_router import CommitRouterResult

    mission = _mission(tmp_path, "lanes_with_coord")
    real = commit_router.commit_for_mission

    def _raise_on_status(*args: Any, **kwargs: Any) -> CommitRouterResult:
        if kwargs.get("kind") is MissionArtifactKind.STATUS_STATE:
            raise RuntimeError("coordination worktree could not be resolved (test)")
        return real(*args, **kwargs)

    monkeypatch.setattr(commit_router, "commit_for_mission", _raise_on_status)

    code, payload = _run_setup_plan_in_process(mission, monkeypatch)

    assert code == 1, payload
    assert payload["error_code"] == "SETUP_PLAN_LIFECYCLE_UNCOMMITTED", payload
    assert "RuntimeError: coordination worktree could not be resolved (test)" in str(payload["lifecycle_diagnostic"])


def test_refusal_renders_in_text_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    from mission_runtime import MissionArtifactKind
    from specify_cli.cli.commands.agent import mission as mission_module
    from specify_cli.coordination import commit_router
    from specify_cli.coordination.commit_router import CommitRouterResult

    mission = _mission(tmp_path, "lanes_with_coord")
    real = commit_router.commit_for_mission

    def _refuse_status(*args: Any, **kwargs: Any) -> CommitRouterResult:
        if kwargs.get("kind") is MissionArtifactKind.STATUS_STATE:
            return CommitRouterResult(status="error", placement_ref=mission.coord_branch, diagnostic="refused [for a test]")
        return real(*args, **kwargs)

    monkeypatch.setattr(commit_router, "commit_for_mission", _refuse_status)
    for key, value in mission.env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.chdir(mission.repo)
    monkeypatch.setattr(mission_module, "locate_project_root", lambda *a, **k: mission.repo)

    result = CliRunner().invoke(mission_module.app, ["setup-plan", "--mission", mission.slug], catch_exceptions=False)

    assert result.exit_code == 1, result.output
    flat_output = " ".join(result.output.split())
    assert "SETUP_PLAN_LIFECYCLE_UNCOMMITTED" in flat_output
    assert "refused [for a test]" in flat_output, "an untrusted diagnostic must render literally, never as markup"


def _coordination_location(path: Path) -> Any:
    from types import SimpleNamespace

    return SimpleNamespace(path=path, surface_root=path)


def test_absent_log_on_a_coordination_topology_is_a_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import mission_runtime
    from mission_runtime import MissionTopology
    from specify_cli.cli.commands.agent import mission_setup_plan

    monkeypatch.setattr(mission_runtime, "resolve_topology", lambda *_a, **_k: MissionTopology.LANES_WITH_COORD)

    result = mission_setup_plan._commit_lifecycle_events_on_coordination(tmp_path, "m", _coordination_location(tmp_path), None)

    assert result is not None and result.status == "error"
    assert "no status log" in str(result.diagnostic)


def test_unreadable_committed_log_is_a_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.cli.commands.agent import mission_setup_plan
    from specify_cli.coordination import status_surface_guard
    from specify_cli.coordination.transaction_errors import BookkeepingStatusSurfaceUnreadable

    log = tmp_path / "status.events.jsonl"

    def _unreadable(worktree_root: Path, events_path: Path) -> list[str]:
        raise BookkeepingStatusSurfaceUnreadable(worktree_root=worktree_root, events_path=events_path, reason="torn (test)")

    monkeypatch.setattr(status_surface_guard, "committed_events_missing_from_worktree", _unreadable)

    result = mission_setup_plan._lifecycle_log_divergence(tmp_path, log)

    assert result is not None and result.status == "error"
    assert "COORD_STATUS_SURFACE_UNREADABLE" in str(result.diagnostic)


def test_setup_plan_events_in_log_edges(tmp_path: Path) -> None:
    from specify_cli.cli.commands.agent import mission_setup_plan

    assert mission_setup_plan._setup_plan_events_in_log(tmp_path / "missing") == []
    (tmp_path / "status.events.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"event_type": "PlanStarted"}),
                "{not json",
                json.dumps(["not", "an", "object"]),
                json.dumps({"event_type": "SpecifyCompleted"}),
                json.dumps({"event_type": "PlanStarted"}),
                json.dumps({"event_type": "MissionCreated"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert mission_setup_plan._setup_plan_events_in_log(tmp_path) == ["PlanStarted", "SpecifyCompleted"]

    damaged = tmp_path / "damaged"
    damaged.mkdir()
    (damaged / "status.events.jsonl").write_bytes(b"\xff\xfe not utf-8\n")
    assert mission_setup_plan._setup_plan_events_in_log(damaged) == []


# ---------------------------------------------------------------------------
# Review cycle 2, B2: the commit is bound to the HEAD the guard checked (compare-and-swap)
# B3: a divergence refusal never tells the operator to commit the stale log
# ---------------------------------------------------------------------------


def test_foreign_commit_after_the_guard_is_never_erased(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.cli.commands.agent import mission_setup_plan

    mission = _mission(tmp_path, "lanes_with_coord")
    mission.setup_plan()  # scaffold
    mission.write_plan()
    real_guard = mission_setup_plan._lifecycle_log_divergence
    injected: dict[str, str] = {}

    def _guard_then_foreign_writer(surface_root: Path, log: Path) -> Any:
        verdict = real_guard(surface_root, log)
        injected["tip"], injected["event_id"] = _advance_coord_branch_with_foreign_event(mission)
        return verdict

    monkeypatch.setattr(mission_setup_plan, "_lifecycle_log_divergence", _guard_then_foreign_writer)

    code, payload = _run_setup_plan_in_process(mission, monkeypatch)

    assert injected, "the guard must run on a coordination Mission"
    assert code == 1, payload
    assert payload["error_code"] == "SETUP_PLAN_LIFECYCLE_UNCOMMITTED", payload
    assert git(mission.repo, "rev-parse", mission.coord_branch) == injected["tip"], "the foreign commit must stay the branch tip"
    assert "moved after setup-plan checked it" in str(payload["lifecycle_diagnostic"])
    assert "Do not commit this checkout's status log" in str(payload["error"])
    assert injected["event_id"] in git(mission.repo, "show", f"{mission.coord_branch}:kitty-specs/{mission.slug}/status.events.jsonl")


def test_unresolvable_coordination_head_is_a_loss_risk_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import mission_runtime
    from mission_runtime import MissionTopology
    from specify_cli.cli.commands.agent import mission_setup_plan

    # Assumes pytest's basetemp is not inside a git checkout (true under the repository's pytest config).
    assert mission_setup_plan._checkout_head(tmp_path) is None, "a directory that is not a checkout has no HEAD"
    (tmp_path / "status.events.jsonl").write_text(json.dumps({"event_type": "PlanStarted"}) + "\n", encoding="utf-8")
    monkeypatch.setattr(mission_runtime, "resolve_topology", lambda *_a, **_k: MissionTopology.LANES_WITH_COORD)

    result = mission_setup_plan._commit_lifecycle_events_on_coordination(tmp_path, "m", _coordination_location(tmp_path), None)

    assert result is not None and result.status == "error"
    assert "could not be resolved" in str(result.diagnostic)
    assert result.reason == mission_setup_plan._LIFECYCLE_LOSS_RISK


def test_concurrent_status_write_that_carried_our_events_is_not_a_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Squad finding on B2: another status write commits the whole log (ours included) and wins the race."""
    from mission_runtime import MissionArtifactKind
    from specify_cli.coordination import commit_router
    from specify_cli.coordination.commit_router import CommitRouterResult

    mission = _mission(tmp_path, "lanes_with_coord")
    mission.setup_plan()
    mission.write_plan()
    real = commit_router.commit_for_mission

    def _another_writer_commits_first(*args: Any, **kwargs: Any) -> CommitRouterResult:
        if kwargs.get("kind") is MissionArtifactKind.STATUS_STATE:
            git(mission.coord_root, "add", f"kitty-specs/{mission.slug}/status.events.jsonl")
            git(mission.coord_root, "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-qm", "move-task status write")
            return CommitRouterResult(status="error", placement_ref=mission.coord_branch, diagnostic="conditional advance failed (test)")
        return real(*args, **kwargs)

    monkeypatch.setattr(commit_router, "commit_for_mission", _another_writer_commits_first)

    code, payload = _run_setup_plan_in_process(mission, monkeypatch)

    assert code == 0, payload
    lifecycle = payload["lifecycle_commit"]
    assert isinstance(lifecycle, dict) and lifecycle["status"] == "unchanged"
    assert "PlanCompleted" in mission.coord_events()


def test_events_landed_is_false_outside_a_checkout_and_event_ids_skip_malformed_lines(tmp_path: Path) -> None:
    from specify_cli.cli.commands.agent import mission_setup_plan

    ours = b'{"event_type":"PlanStarted","event_id":"A"}\n'
    assert mission_setup_plan._lifecycle_events_landed(tmp_path, tmp_path / "status.events.jsonl", ours) is False
    assert mission_setup_plan._setup_plan_event_ids('{"event_type":"PlanStarted","event_id":"A"}\nnot json\n[1]\n') == {"A"}


class _NamedWriteLocationError(RuntimeError):
    error_code = "COORD_SEED_FORK_REFUSED"


def test_write_location_refusal_keeps_its_error_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """N2: a write-location error now ends the run before the plan commit, so its code must reach the JSON."""
    from specify_cli.cli.commands.agent import mission_setup_plan

    mission = _mission(tmp_path, "lanes_with_coord")

    def _refuse(*_a: object, **_k: object) -> None:
        raise _NamedWriteLocationError("coordination seed refused")

    monkeypatch.setattr(mission_setup_plan, "_lifecycle_write_location", _refuse)
    exit_code, payload = _run_setup_plan_in_process(mission, monkeypatch)

    assert exit_code == 1
    assert payload["error"] == "coordination seed refused"
    assert payload["error_code"] == "COORD_SEED_FORK_REFUSED"


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (RuntimeError("plain"), {"error": "plain"}),
        (type("Coded", (RuntimeError,), {"code": "STATUS_LOCK_HELD"})("held"), {"error": "held", "error_code": "STATUS_LOCK_HELD"}),
        (type("NonStr", (RuntimeError,), {"code": 3})("n"), {"error": "n"}),
    ],
)
def test_generic_error_payload(exc: Exception, expected: dict[str, object]) -> None:
    from specify_cli.cli.commands.agent import mission_setup_plan

    assert mission_setup_plan._generic_error_payload(exc) == expected
