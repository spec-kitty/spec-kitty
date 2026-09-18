"""#3029 (representation half, WP04): ``move-task --agent`` persists the
acting identity into the reduced ownership slot.

Verify-first finding (T015, live on the lane tip after WP01-WP03 landed):
this is a **characterization** test, not a red-first repro. The original
"no agent key at all" symptom is stale — ``_mt_emit_runtime_state`` (see
``tasks_move_task.py:2858``) already threads ``st.agent`` into the off-axis
``InnerStateChanged`` delta for any non-claim, non-rollback hop::

    if st.agent and not (st.target_lane == Lane.PLANNED and
                          _actor_key(st.agent) == _actor_key(st.current_agent)):
        fields["agent"] = st.agent

and WP03's T012 fix (commit ``5222cf5cc7``) additionally threads the claim
owner through the per-transition ``annotation_delta`` channel on the
``planned -> claimed`` hop itself, so the claim path is covered too.

This test drives the REAL ``move-task`` CLI (mirrors the harness in
``test_fixmode_ownership_4673.py``) through a plain non-claim hop
(``claimed -> in_progress --agent <identity>``) and asserts:

1. the reduced ownership snapshot (``status.reducer.reduce`` over the real
   event log) carries the acting identity in its ``agent`` slot immediately
   after that hop (FR-009's literal claim), and
2. that persisted identity is genuinely VISIBLE TO A LATER OWNERSHIP CHECK
   (FR-009's "so that downstream ownership checks see it") — a differing
   agent attempting the next hop without ``--force`` is refused with
   ``Agent mismatch`` against the identity persisted in step 1, and the
   legitimate owner is unaffected by the refused attempt.

Excluded per C-004 (representation half only): #3029's alternative
resolutions (dropping the ``--agent`` flag; demoting the accept gate to a
warning) and its #2993 precondition are not exercised here.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.cli.commands.agent import tasks as tasks_module
from specify_cli.cli.commands.agent.tasks import app as tasks_app
from specify_cli.status import Lane
from specify_cli.status.models import StatusEvent
from specify_cli.status.reducer import reduce as reduce_snapshot
from specify_cli.status.store import append_event, read_event_stream
from tests.lane_test_utils import write_single_lane_manifest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_MISSION_SLUG = "001-move-task-agent-persistence-3029"
_OWNER = "implementer-a"
_OTHER_AGENT = "someone-else"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _build_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "3029@example.invalid")
    _git(repo, "config", "user.name", "Move Task Agent Persistence")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.yaml").write_text("auto_commit: false\nprotection:\n  protected_branches: []\n", encoding="utf-8")

    feature_dir = repo / "kitty-specs" / _MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",))

    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["status_phase"] = "1"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    (feature_dir / "tasks.md").write_text("# Tasks\n\n## WP01 - Core\n\n(no subtasks)\n", encoding="utf-8")
    (tasks_dir / "WP01-core.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Core\nsubtasks: []\ntracker_refs: []\ndependencies: []\n---\n\n# WP01\n\n## Activity Log\n",
        encoding="utf-8",
    )

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "seed move-task-agent-persistence-3029 fixture")

    # GENESIS -> PLANNED is seeded directly (mirrors test_fixmode_ownership_4673.py);
    # every hop under test below drives the REAL move-task CLI entry point.
    append_event(
        feature_dir,
        StatusEvent(
            event_id="seed-genesis-planned",
            mission_slug=_MISSION_SLUG,
            wp_id="WP01",
            from_lane=Lane.GENESIS,
            to_lane=Lane.PLANNED,
            at="2026-01-01T00:00:01+00:00",
            actor="fixture",
            force=True,
            execution_mode="worktree",
        ),
    )

    monkeypatch.chdir(repo)
    monkeypatch.setattr(tasks_module, "locate_project_root", lambda: repo)
    monkeypatch.setattr(tasks_module, "_validate_ready_for_review", lambda *_a, **_k: (True, []))
    monkeypatch.setattr(tasks_module, "get_mission_type", lambda *_a, **_k: "software-dev")
    return repo, feature_dir


def _snapshot_wp_state(feature_dir: Path) -> dict[str, object]:
    stream = read_event_stream(feature_dir)
    snapshot = reduce_snapshot(stream.transitions, stream.annotations)
    return snapshot.work_packages.get("WP01") or {}


def _move(args: list[str]) -> Result:
    return CliRunner().invoke(tasks_app, ["move-task", *args])


def test_move_task_agent_persists_into_reduced_ownership_slot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T015/T016 (#3029): a plain non-claim ``move-task --agent`` hop
    persists the acting identity into the reduced ``agent`` slot, and that
    persisted identity is what a LATER ownership check reads.

    Verify-first evidence (T015): live-run on this lane's tip, driving the
    real CLI exactly as below, confirms the identity IS persisted — see the
    module docstring for the grounded mechanism (``tasks_move_task.py:2858``,
    WP03 T012 commit ``5222cf5cc7``). This is therefore a GREEN
    characterization test, not a red-first repro (C-004/NFR-003).
    """
    repo, feature_dir = _build_mission(tmp_path, monkeypatch)

    claimed = _move(
        [
            "WP01",
            "--to",
            "claimed",
            "--mission",
            _MISSION_SLUG,
            "--agent",
            _OWNER,
            "--shell-pid",
            "111",
            "--no-auto-commit",
        ]
    )
    assert claimed.exit_code == 0, claimed.output

    # --- The hop under test: a plain, non-claim ``move-task --agent`` call.
    # No prior code touched the reduced ``agent`` slot outside the claim
    # transition's own policy_metadata until this hop runs. ---
    moved = _move(
        [
            "WP01",
            "--to",
            "in_progress",
            "--mission",
            _MISSION_SLUG,
            "--agent",
            _OWNER,
            "--no-auto-commit",
        ]
    )
    assert moved.exit_code == 0, moved.output

    # T015 evidence read: the reduced ownership slot after the non-claim hop.
    after_move = _snapshot_wp_state(feature_dir)
    assert after_move.get("agent") == _OWNER, (
        f"reduced ownership slot did not persist the acting identity after a non-claim move-task --agent hop: {after_move.get('agent')!r}"
    )

    # --- FR-009's "so that downstream ownership checks see it": a genuinely
    # different agent, without --force, is refused against the identity just
    # persisted above. ---
    refused = _move(
        [
            "WP01",
            "--to",
            "for_review",
            "--mission",
            _MISSION_SLUG,
            "--agent",
            _OTHER_AGENT,
            "--no-auto-commit",
        ]
    )
    assert refused.exit_code != 0, refused.output
    assert "Agent mismatch" in refused.output

    # The genuine owner's identity is unaffected by the refused attempt.
    unaffected = _snapshot_wp_state(feature_dir)
    assert unaffected.get("agent") == _OWNER

    # --- The legitimate owner's own submission succeeds, and the reduced
    # slot still (genuinely) carries the acting identity. ---
    submitted = _move(
        [
            "WP01",
            "--to",
            "for_review",
            "--mission",
            _MISSION_SLUG,
            "--agent",
            _OWNER,
            "--no-auto-commit",
        ]
    )
    assert submitted.exit_code == 0, submitted.output

    final_state = _snapshot_wp_state(feature_dir)
    assert final_state.get("agent") == _OWNER
