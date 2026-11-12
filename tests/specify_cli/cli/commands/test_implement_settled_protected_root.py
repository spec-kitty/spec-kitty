"""Implement and move-task from a repository root checkout on protected ``main`` (#7601).

A default Mission settled ``lanes_with_coord`` at its first ``finalize-tasks`` keeps its
PRIMARY partition on the Mission topic branch, held by the coordination worktree, while the
repository root checkout returns to protected ``main``. The claim commit and the WP-file
commit run in that holder, so the protected-branch checks judge the branch of the checkout
the commit actually runs in (operator ruling, decision ``01M78JFMRQS6GE04BENPXGQX8J``,
option B), never the root checkout's ``main``.

Every case drives the real CLI in a subprocess from the repository root on a Mission built
by the real ``agent mission create`` core and ``finalize-tasks``. ``main`` never moves. The
positive control (an explicit ``lanes_with_coord`` Mission targeting protected ``main``)
pins that a Mission with no topic holder keeps today's refusal and today's skip.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.specify_cli.cli.commands.agent.test_finalize_topology_settlement import (
    REPO_ROOT,
    THREE_LANES,
    DefaultMission,
    git,
    make_default_mission,
    run_finalize,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]

_ANALYSIS_REPORT = "# Analysis\n\nNo critical issues.\n"
_PROTECTED_CLAIM_REFUSAL = "Refusing to start implementation status on protected branch 'main'"
_NO_AUTO_COMMIT = "--no-auto-commit"
_HATCH = "SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS"


def _spec_kitty(root: Path, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["SPEC_KITTY_NON_INTERACTIVE"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "specify_cli", *args],
        cwd=root,
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def _ready_mission(tmp_path: Path, *, explicit: str | None = None) -> DefaultMission:
    """A finalized three-lane Mission whose analysis gate is satisfied, the root checkout on ``main``.

    An explicit-topology Mission keeps its planning artifacts on ``main`` itself, so its setup
    commits there under the operator hatch; the hatch is cleared before any case runs.
    """
    if explicit is None:
        return _finalized(make_default_mission(tmp_path, THREE_LANES))
    os.environ[_HATCH] = "1"
    try:
        return _finalized(make_default_mission(tmp_path, THREE_LANES, explicit=explicit))
    finally:
        del os.environ[_HATCH]


def _finalized(mission: DefaultMission) -> DefaultMission:
    (mission.root_mission_dir / "plan.md").write_text("# Plan\n\nDo it.\n", encoding="utf-8")
    git(mission.root, "add", "kitty-specs")
    git(mission.root, "commit", "-qm", "plan")
    code, payload = run_finalize(mission)
    assert code == 0, payload
    recorded = _spec_kitty(
        mission.root, "agent", "mission", "record-analysis", "--mission", mission.slug, "--input-file", "-", "--agent", "claude", stdin=_ANALYSIS_REPORT
    )
    assert recorded.returncode == 0, recorded.stdout + recorded.stderr
    assert git(mission.root, "branch", "--show-current") == "main"
    return mission


def _flat(result: subprocess.CompletedProcess[str]) -> str:
    """Stdout and stderr with the console's line wrapping and tree rails folded away."""
    return " ".join((result.stdout + result.stderr).replace("│", " ").split())


def _tip(root: Path, ref: str) -> str:
    return git(root, "rev-parse", ref)


def _last_json(text: str) -> dict[str, object]:
    payloads = [json.loads(line) for line in text.splitlines() if line.startswith("{")]
    assert payloads, text
    payload: dict[str, object] = payloads[-1]
    return payload


def _wp_file_at(root: Path, ref: str, slug: str, wp_id: str) -> str:
    return git(root, "show", f"{ref}:kitty-specs/{slug}/tasks/{wp_id}-work.md")


@pytest.fixture(autouse=True)
def _isolated_run(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.status.emit as emit_module

    # Vacuity guard: with the operator hatch set, no protected-branch check would ever refuse.
    monkeypatch.delenv(_HATCH, raising=False)
    # The in-process ``finalize-tasks`` runs from the source tree and fans out no status event.
    monkeypatch.chdir(REPO_ROOT)
    monkeypatch.setattr(emit_module, "_status_fan_out", lambda *a, **k: None)


@pytest.fixture
def settled(tmp_path: Path) -> DefaultMission:
    mission = _ready_mission(tmp_path)
    meta = json.loads((mission.coord_mission_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["topology"] == "lanes_with_coord" and meta["coordination_branch"] == mission.topic
    return mission


def test_implement_from_a_protected_root_claims_on_the_topic_branch(settled: DefaultMission) -> None:
    """(a) + (d): the claim lands on the topic branch; ``main`` never moves; no unfollowable remedy."""
    main_tip, topic_tip = _tip(settled.root, "main"), _tip(settled.root, settled.topic)

    result = _spec_kitty(settled.root, "agent", "action", "implement", "WP01", "--mission", settled.slug, "--agent", "claude")

    output = _flat(result)
    assert result.returncode == 0, output
    assert _PROTECTED_CLAIM_REFUSAL not in output
    assert _NO_AUTO_COMMIT not in output
    assert _tip(settled.root, "main") == main_tip
    assert _tip(settled.root, settled.topic) != topic_tip
    events = git(settled.root, "show", f"{settled.topic}:kitty-specs/{settled.slug}/status.events.jsonl")
    assert any(json.loads(line).get("wp_id") == "WP01" and json.loads(line).get("to_lane") == "claimed" for line in events.splitlines())


def test_move_task_with_a_note_commits_it_on_the_topic_branch(settled: DefaultMission) -> None:
    """(b): ``--note`` is no longer refused; the activity entry is committed on the topic branch."""
    main_tip = _tip(settled.root, "main")

    result = _spec_kitty(
        settled.root,
        "agent",
        "tasks",
        "move-task",
        "WP02",
        "--to",
        "claimed",
        "--mission",
        settled.slug,
        "--agent",
        "claude",
        "--note",
        "Claimed for #7601",
        "--json",
    )

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "WP_METADATA_UNSUPPORTED_ON_PROTECTED_COORD_BRANCH" not in output
    assert _tip(settled.root, "main") == main_tip
    assert "Claimed for #7601" in _wp_file_at(settled.root, settled.topic, settled.slug, "WP02")


def test_move_task_without_a_note_commits_the_wp_file_instead_of_skipping_it(settled: DefaultMission) -> None:
    """(c) silent-skip regression: the WP frontmatter change is committed, never reported ``skipped``."""
    main_tip = _tip(settled.root, "main")
    before = _wp_file_at(settled.root, settled.topic, settled.slug, "WP03")

    result = _spec_kitty(settled.root, "agent", "tasks", "move-task", "WP03", "--to", "claimed", "--mission", settled.slug, "--agent", "claude", "--json")

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    payload = _last_json(result.stdout)
    assert payload.get("wp_file_update") != "skipped", payload
    assert _tip(settled.root, "main") == main_tip
    assert _wp_file_at(settled.root, settled.topic, settled.slug, "WP03") != before
    assert git(settled.coord_mission_dir.parents[1], "status", "--porcelain", "--", f"kitty-specs/{settled.slug}/tasks") == ""


def test_explicit_coordination_mission_on_a_protected_root_keeps_todays_behaviour(tmp_path: Path) -> None:
    """(e) positive control: no topic holder, so the root checkout's ``main`` is still judged."""
    mission = _ready_mission(tmp_path, explicit="lanes_with_coord")
    main_tip = _tip(mission.root, "main")

    implement = _spec_kitty(mission.root, "agent", "action", "implement", "WP01", "--mission", mission.slug, "--agent", "claude")
    move = _spec_kitty(mission.root, "agent", "tasks", "move-task", "WP02", "--to", "claimed", "--mission", mission.slug, "--agent", "claude", "--json")

    refusal = _flat(implement)
    assert implement.returncode == 1, refusal
    assert _PROTECTED_CLAIM_REFUSAL in refusal
    # (d) the refusal's remedy names no option ``agent action implement`` lacks.
    assert _NO_AUTO_COMMIT not in refusal
    assert move.returncode == 0, move.stdout + move.stderr
    assert _last_json(move.stdout).get("wp_file_update") == "skipped"
    assert _tip(mission.root, "main") == main_tip
