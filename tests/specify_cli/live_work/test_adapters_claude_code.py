"""Claude Code hook adapter — the capture mapping, machine-tested.

Fixtures are the documented Claude Code hook payload shapes (one JSON event
per hook invocation). The attribution test builds two overlapping mission
worktrees and proves the issue's acceptance criterion: "Two agents edit
different and same files in overlapping worktrees: accurate attribution or
explicit uncertainty; runs and file actions appear in the correct mission."
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.live_work.adapters.claude_code import ClaudeCodeHookAdapter
from specify_cli.live_work.kinds import WorkEmissionKind
from specify_cli.live_work.models import FileDetail, FileOperation, TestRunDetail, ToolDetail, ToolOutcome, ToolState

pytestmark = pytest.mark.fast


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A git repository with an origin remote and one initial commit."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-b", "main")
    _git(root, "remote", "add", "origin", "https://github.com/acme/repo.git")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / "README.md").write_text("x\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(root, "commit", "-m", "init")
    return root


def _payload(repo: Path, **overrides) -> dict:
    base = {
        "hook_event_name": "PostToolUse",
        "session_id": "sess-abc123",
        "transcript_path": str(repo / "transcript.jsonl"),
        "cwd": str(repo),
        "tool_name": "Edit",
        "tool_input": {"file_path": str(repo / "src" / "a.py"), "old_string": "x", "new_string": "yyyy"},
        "tool_response": {},
    }
    base.update(overrides)
    return base


def test_session_start_and_end_map_to_session_kinds(repo: Path) -> None:
    adapter = ClaudeCodeHookAdapter()
    started = adapter.parse(
        {"hook_event_name": "SessionStart", "session_id": "s1", "cwd": str(repo), "source": "startup"},
        repo_root=repo,
    )
    assert [obs.kind for obs in started] == [WorkEmissionKind.SESSION_STARTED]
    assert started[0].repository is not None
    assert started[0].repository.slug == "repo"  # repo_name: the origin-derived name, never the directory
    ended = adapter.parse(
        {"hook_event_name": "SessionEnd", "session_id": "s1", "cwd": str(repo), "reason": "clear"},
        repo_root=repo,
    )
    assert [obs.kind for obs in ended] == [WorkEmissionKind.SESSION_ENDED]


def test_pre_tool_use_maps_to_started_tool_invocation(repo: Path) -> None:
    adapter = ClaudeCodeHookAdapter()
    observations = adapter.parse(
        _payload(
            repo,
            hook_event_name="PreToolUse",
            tool_name="Bash",
            tool_input={"command": "pytest tests/ -q"},
            tool_response=None,
        ),
        repo_root=repo,
    )
    assert len(observations) == 1
    detail = observations[0].action
    assert isinstance(detail, ToolDetail)
    assert detail.tool == "Bash"
    assert detail.state == ToolState.STARTED
    assert detail.outcome is None


def test_post_tool_use_edit_maps_to_file_observation_with_deltas(repo: Path) -> None:
    adapter = ClaudeCodeHookAdapter()
    observations = adapter.parse(_payload(repo), repo_root=repo)
    kinds = {obs.kind for obs in observations}
    assert WorkEmissionKind.FILE_EDITED in kinds
    assert WorkEmissionKind.TOOL_INVOKED in kinds
    file_observation = next(obs for obs in observations if obs.kind == WorkEmissionKind.FILE_EDITED)
    detail = file_observation.action
    assert isinstance(detail, FileDetail)
    assert detail.operation == FileOperation.EDIT
    assert detail.path == "src/a.py"
    assert detail.bytes_added == 4
    assert detail.bytes_removed == 1
    assert detail.attribution == "exact"


def test_post_tool_use_read_is_a_read_observation(repo: Path) -> None:
    adapter = ClaudeCodeHookAdapter()
    observations = adapter.parse(
        _payload(repo, tool_name="Read", tool_input={"file_path": str(repo / "docs" / "notes.md")}),
        repo_root=repo,
    )
    detail = next(obs.action for obs in observations if obs.kind == WorkEmissionKind.FILE_EDITED)
    assert isinstance(detail, FileDetail)
    assert detail.operation == FileOperation.READ


def test_test_run_counts_are_parsed_and_raw_output_never_enters(repo: Path) -> None:
    adapter = ClaudeCodeHookAdapter()
    stdout = "collected 10 items\n....F.s\n=== 7 passed, 1 failed, 2 skipped in 0.5s ===\nSECRET=s3cr3tvalue"
    observations = adapter.parse(
        _payload(
            repo,
            tool_name="Bash",
            tool_input={"command": "uv run pytest tests/unit -q"},
            tool_response={"stdout": stdout, "is_error": False},
        ),
        repo_root=repo,
    )
    test_observation = next(obs for obs in observations if obs.kind == WorkEmissionKind.TEST_EXECUTED)
    detail = test_observation.action
    assert isinstance(detail, TestRunDetail)
    assert detail.state == ToolState.RESULT
    assert (detail.passed, detail.failed, detail.skipped) == (7, 1, 2)
    assert detail.outcome == ToolOutcome.FAILURE
    # Raw output — and anything inside it — never enters the observation.
    assert "stdout" not in (test_observation.model_dump()["action"])
    assert "SECRET" not in json.dumps(test_observation.model_dump())


def test_non_test_bash_command_produces_no_test_observation(repo: Path) -> None:
    adapter = ClaudeCodeHookAdapter()
    observations = adapter.parse(
        _payload(repo, tool_name="Bash", tool_input={"command": "ls -la"}, tool_response={"stdout": "files"}),
        repo_root=repo,
    )
    assert WorkEmissionKind.TEST_EXECUTED not in {obs.kind for obs in observations}


def test_delegation_pair_maps_to_session_delegation_kinds(repo: Path) -> None:
    adapter = ClaudeCodeHookAdapter()
    started = adapter.parse(
        _payload(
            repo,
            hook_event_name="PreToolUse",
            tool_name="Task",
            tool_input={"description": "research", "subagent_type": "general-purpose"},
        ),
        repo_root=repo,
    )
    assert [obs.kind for obs in started] == [WorkEmissionKind.DELEGATION_STARTED]
    assert started[0].counterpart == "general-purpose"
    ended = adapter.parse(
        _payload(
            repo,
            tool_name="Task",
            tool_input={"description": "research", "subagent_type": "general-purpose"},
            tool_response={"is_error": False},
        ),
        repo_root=repo,
    )
    assert [obs.kind for obs in ended] == [WorkEmissionKind.DELEGATION_ENDED]


def test_failed_and_interrupted_tools_carry_honest_outcomes(repo: Path) -> None:
    adapter = ClaudeCodeHookAdapter()
    failed = adapter.parse(
        _payload(repo, tool_name="Bash", tool_input={"command": "make test"}, tool_response={"is_error": True}),
        repo_root=repo,
    )
    detail = next(obs.action for obs in failed if obs.kind == WorkEmissionKind.TOOL_INVOKED)
    assert isinstance(detail, ToolDetail)
    assert detail.outcome == ToolOutcome.FAILURE
    cancelled = adapter.parse(
        _payload(repo, tool_name="Bash", tool_input={"command": "make test"}, tool_response={"interrupted": True}),
        repo_root=repo,
    )
    detail = next(obs.action for obs in cancelled if obs.kind == WorkEmissionKind.TOOL_INVOKED)
    assert isinstance(detail, ToolDetail)
    assert detail.state == ToolState.CANCELLED


def test_secret_file_edit_produces_nothing_at_all(repo: Path) -> None:
    adapter = ClaudeCodeHookAdapter()
    observations = adapter.parse(
        _payload(repo, tool_input={"file_path": str(repo / ".env"), "content": "TOKEN=x"}),
        repo_root=repo,
    )
    assert WorkEmissionKind.FILE_EDITED not in {obs.kind for obs in observations}
    # Nothing anywhere names the file.
    assert ".env" not in json.dumps([obs.model_dump() for obs in observations])


def test_unknown_event_and_missing_session_are_tolerated(repo: Path) -> None:
    adapter = ClaudeCodeHookAdapter()
    assert adapter.parse({"hook_event_name": "UserPromptSubmit", "session_id": "s", "prompt": "hi"}, repo_root=repo) == []
    assert adapter.parse({"hook_event_name": "SessionStart"}, repo_root=repo) == []
    assert adapter.parse({"hook_event_name": "PreCompact", "session_id": "s"}, repo_root=repo) == []


def test_malformed_tool_input_never_raises(repo: Path) -> None:
    adapter = ClaudeCodeHookAdapter()
    observations = adapter.parse(_payload(repo, tool_input="not-a-mapping", tool_response=None), repo_root=repo)
    assert all(obs.kind == WorkEmissionKind.TOOL_INVOKED for obs in observations)


def test_token_in_command_summary_is_redacted_on_the_record(repo: Path) -> None:
    adapter = ClaudeCodeHookAdapter()
    observations = adapter.parse(
        _payload(
            repo,
            tool_name="Bash",
            tool_input={"command": "deploy --api-key sk-live-abc123def456ghi789 --env prod"},
            tool_response={"stdout": "ok"},
        ),
        repo_root=repo,
    )
    dumped = json.dumps([obs.model_dump() for obs in observations])
    assert "sk-live-abc123def456ghi789" not in dumped
    assert any(obs.extensions and "x-summary" in obs.extensions for obs in observations)


# ── the overlapping-worktree attribution criterion ───────────────────────────


@pytest.fixture
def mission_repo(repo: Path) -> tuple[Path, str]:
    """A repo with one identity-bearing mission and two overlapping worktrees."""
    mission_id = "01J" + "23456789ABCDEFGHJKMNPQRST"[:23]  # valid Crockford chars
    slug = "080-demo-mission"
    mission_dir = repo / "kitty-specs" / slug
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(json.dumps({"mission_id": mission_id, "mission_slug": slug}), encoding="utf-8")
    (mission_dir / "status.events.jsonl").write_text("", encoding="utf-8")
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-m", "mission")
    worktree_root = repo / ".worktrees"
    worktree_root.mkdir()
    for lane in ("01", "02"):
        _git(repo, "worktree", "add", str(worktree_root / f"{slug}-{mission_id[:8]}-lane-{lane}"), "-b", f"kitty/mission-{slug}-{mission_id[:8]}-lane-{lane}")
    return repo, mission_id


def test_two_agents_in_overlapping_worktrees_attributed_exactly(mission_repo) -> None:
    repo, mission_id = mission_repo
    lane1 = repo / ".worktrees" / f"080-demo-mission-{mission_id[:8]}-lane-01"
    lane2 = repo / ".worktrees" / f"080-demo-mission-{mission_id[:8]}-lane-02"
    adapter = ClaudeCodeHookAdapter()

    # Two agents, different sessions, editing the SAME file in two
    # overlapping worktrees: each observation is attributed to its own
    # session and the same mission — exact, never merged.
    observations_agent_a = adapter.parse(
        _payload(lane1, session_id="agent-a", tool_input={"file_path": str(lane1 / "src" / "shared.py"), "old_string": "a", "new_string": "bbbb"}),
        repo_root=lane1,
    )
    observations_agent_b = adapter.parse(
        _payload(lane2, session_id="agent-b", tool_input={"file_path": str(lane2 / "src" / "shared.py"), "old_string": "a", "new_string": "cc"}),
        repo_root=lane2,
    )
    for observations, session in ((observations_agent_a, "agent-a"), (observations_agent_b, "agent-b")):
        file_observation = next(obs for obs in observations if obs.kind == WorkEmissionKind.FILE_EDITED)
        assert file_observation.session.session_id == session
        assert file_observation.mission is not None
        assert file_observation.mission.mission_id == mission_id
        detail = file_observation.action
        assert isinstance(detail, FileDetail)
        assert detail.path == "src/shared.py"
        assert detail.attribution == "exact"

    # Distinct concurrent activity ids are preserved, never collapsed.
    activities_a = {obs.activity.activity_id for obs in observations_agent_a if obs.activity}
    activities_b = {obs.activity.activity_id for obs in observations_agent_b if obs.activity}
    assert activities_a and activities_b
    assert not (activities_a & activities_b)


def test_repo_root_session_stays_repository_bound_never_guesses_mission(mission_repo) -> None:
    repo, _ = mission_repo
    adapter = ClaudeCodeHookAdapter()
    observations = adapter.parse(_payload(repo), repo_root=repo)
    file_observation = next(obs for obs in observations if obs.kind == WorkEmissionKind.FILE_EDITED)
    # A plain checkout carries a mission, but the hook payload does not
    # name one — repository-bound, never guessed (LW-02).
    assert file_observation.mission is None
    assert file_observation.repository is not None
