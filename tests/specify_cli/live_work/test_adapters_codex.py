"""Codex notify adapter — the honest partial surface, machine-tested."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.live_work.adapters.codex import CodexNotifyAdapter
from specify_cli.live_work.kinds import WorkEmissionKind
from specify_cli.live_work.models import ToolDetail, ToolState

pytestmark = pytest.mark.fast


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/acme/repo.git"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return root


def _payload(repo: Path, **overrides) -> dict:
    base = {
        "type": "agent-turn-complete",
        "turn_id": "turn-42",
        "thread_id": "thread-7",
        "cwd": str(repo),
        "input_messages": [{"role": "user", "content": "please refactor the module"}],
        "last_assistant_message": "I considered several approaches and chose…",
    }
    base.update(overrides)
    return base


def test_turn_complete_maps_to_the_codex_turn_tool_action(repo: Path) -> None:
    adapter = CodexNotifyAdapter()
    observations = adapter.parse(_payload(repo), repo_root=repo)
    assert len(observations) == 1
    observation = observations[0]
    assert observation.kind == WorkEmissionKind.TOOL_INVOKED
    detail = observation.action
    assert isinstance(detail, ToolDetail)
    assert detail.tool == "codex.turn"
    assert detail.state == ToolState.RESULT
    assert observation.session.session_id.startswith("thread-7") or observation.session.session_id
    assert observation.provenance.limitation is not None
    assert "not observable" in observation.provenance.limitation


def test_prose_never_enters_the_observation(repo: Path) -> None:
    adapter = CodexNotifyAdapter()
    observations = adapter.parse(_payload(repo), repo_root=repo)
    dumped = json.dumps([obs.model_dump() for obs in observations])
    assert "refactor the module" not in dumped
    assert "several approaches" not in dumped
    assert "input_messages" not in dumped
    assert "last_assistant_message" not in dumped


def test_unknown_event_types_are_tolerated(repo: Path) -> None:
    adapter = CodexNotifyAdapter()
    assert adapter.parse({"type": "future-event", "turn_id": "t"}, repo_root=repo) == []
    assert adapter.parse({}, repo_root=repo) == []


def test_missing_identity_is_honest_nothing(repo: Path) -> None:
    adapter = CodexNotifyAdapter()
    assert adapter.parse({"type": "agent-turn-complete"}, repo_root=repo) == []


def test_capability_notes_name_the_not_observable_surfaces() -> None:
    notes = CodexNotifyAdapter().capability_notes()
    for surface in ("tools", "files", "tests", "prose"):
        assert surface in notes
    assert "not observable" in notes["tools"]
    assert "watcher fallback" in notes["files"]
