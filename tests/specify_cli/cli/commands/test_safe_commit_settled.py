"""``safe-commit`` on a settled default Mission (#7551, FR-004, SC-003).

From the repository root checkout (back on ``create_return_branch``), committing a Mission
file to the topic branch is refused exactly as before (same exit code, same
``SAFE_COMMIT_HEAD_MISMATCH`` refusal), but the remedy must be one an operator can follow:
git refuses to check out a branch another worktree holds, so the message names that
worktree instead of suggesting ``git -C <root> checkout``. Following it then commits.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.specify_cli.cli.commands.agent.test_finalize_topology_settlement import (
    THREE_LANES,
    DefaultMission,
    git,
    make_default_mission,
    run_finalize,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]


@pytest.fixture(autouse=True)
def _quiet_fanout(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.status.emit as emit_module

    monkeypatch.setattr(emit_module, "_status_fan_out", lambda *a, **k: None)


@pytest.fixture
def settled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> DefaultMission:
    monkeypatch.setenv("SPEC_KITTY_NON_INTERACTIVE", "1")
    mission = make_default_mission(tmp_path, THREE_LANES)
    code, payload = run_finalize(mission)
    assert code == 0, payload
    return mission


def safe_commit(cwd: Path, monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, dict[str, object]]:
    from specify_cli import app as cli_app

    monkeypatch.chdir(cwd)
    result = CliRunner().invoke(cli_app, ["safe-commit", *args, "--json"], catch_exceptions=False)
    start = result.output.find("{")
    payload: dict[str, object] = json.loads(result.output[start:]) if start >= 0 else {"raw": result.output}
    return result.exit_code, payload


def test_root_refusal_names_holder_and_remedy_is_followable(settled: DefaultMission, monkeypatch: pytest.MonkeyPatch) -> None:
    holder = settled.coord_mission_dir.parents[1]
    rel = f"kitty-specs/{settled.slug}/traces/x.md"
    stray = settled.root / rel
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_text("# x\n", encoding="utf-8")
    topic_tip = git(settled.root, "rev-parse", settled.topic)

    code, payload = safe_commit(settled.root, monkeypatch, rel, "-m", "trace x", "--to-branch", settled.topic)

    assert code == 1, payload
    error = str(payload["error"])
    assert str(holder.resolve()) in error, error
    assert "git -C" not in error, error
    assert git(settled.root, "rev-parse", settled.topic) == topic_tip

    # Follow the remedy: run the command from the named worktree, with the file there.
    (holder / rel).parent.mkdir(parents=True, exist_ok=True)
    stray.rename(holder / rel)
    code, payload = safe_commit(holder, monkeypatch, rel, "-m", "trace x", "--to-branch", settled.topic)

    assert code == 0, payload
    assert git(settled.root, "log", "-1", "--format=%s", settled.topic) == "trace x"


def test_coord_worktree_cwd_commits(settled: DefaultMission, monkeypatch: pytest.MonkeyPatch) -> None:
    holder = settled.coord_mission_dir.parents[1]
    rel = f"kitty-specs/{settled.slug}/traces/design.md"
    (holder / rel).parent.mkdir(parents=True, exist_ok=True)
    (holder / rel).write_text("# design\n", encoding="utf-8")

    code, payload = safe_commit(holder, monkeypatch, rel, "-m", "trace design", "--to-branch", settled.topic)

    assert code == 0, payload
    assert git(settled.root, "log", "-1", "--format=%s", settled.topic) == "trace design"
