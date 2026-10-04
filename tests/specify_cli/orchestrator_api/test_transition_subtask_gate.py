"""#2510/#2511 -> WP03 -> #2816 IC-10: the orchestrator-api transition door blocks
on incomplete subtasks SOLELY through the shared emit layer.

Field repro: an orchestrator-driven coordination mission moved four WPs
``in_progress -> for_review`` with ``force=false`` while the subtasks were
incomplete. The orchestrator passes no ``--subtasks-complete``; the API
forwarded ``None``; emit-time inference FAILED OPEN off the wrong surface.

WP02/WP03 fixed the shared layer to read the PRIMARY surface. #2816 IC-10 then
retired the ``tasks.md`` checkbox proxy entirely: the subtask **roster** is the
authored ``subtasks:`` WP frontmatter list and **completion** is the reduced
event-log snapshot's ``subtasks`` slot (fail-closed on a silent snapshot). These
tests drive the REAL production route (``orchestrator_api.commands.app`` ->
``emit_status_transition_transactional`` -> the shared emit layer) end-to-end,
proving the door still blocks/allows correctly under the frontmatter-roster
model -- mirroring ``tests/specify_cli/status/test_infer_subtasks_primary.py``
for the native ``agent status emit`` door.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.orchestrator_api.commands import app

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

_MISSION_ID = "01KV8NPCQ9ZX3R7W2M5T8H4FBD"
_MID8 = _MISSION_ID[:8]
# Deliberately does NOT end in ``-{mid8}`` (unlike the coord-dir naming
# grammar): a slug shaped like ``<slug>-<mid8>`` makes the transaction-dir
# probe (``_transaction_dir_name``) collapse onto this SAME primary dir,
# flipping ``transaction_meta_exists`` true and routing the transition
# through ``BookkeepingTransaction`` -- an unrelated, heavier machinery this
# WP does not touch. Keeping the slug mid8-free routes through the flat/
# non-coordination ``_emit.emit_status_transition`` path instead, which is
# the SAME shared-layer route WP02 fixed and the one this WP's removal
# affects.
_MISSION_SLUG = "subtask-gate-repro"

_POLICY = json.dumps(
    {
        "orchestrator_id": "test-orch",
        "orchestrator_version": "0.0.1",
        "agent_family": "claude",
        "approval_mode": "full_auto",
        "sandbox_mode": "workspace_write",
        "network_mode": "none",
        "dangerous_flags": [],
    }
)


@pytest.fixture(autouse=True)
def _disable_emit_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep these tests focused on the transition + completeness gate.

    Mirrors ``test_infer_subtasks_primary.py``'s fixture: the real
    (non-mocked) production route is exercised end-to-end, so SaaS fan-out
    and dossier sync -- both fire-and-forget side effects unrelated to this
    gate -- are neutralized rather than allowed to hit the network/daemon.
    """
    import specify_cli.status.emit as status_emit

    monkeypatch.setattr(status_emit, "_saas_fan_out", lambda *args, **kwargs: None)
def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _make_git_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True, text=True)
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / ".kittify").mkdir()
    (repo / "README.md").write_text("test repo\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    return repo


def _status_event(wp_id: str, from_lane: str, to_lane: str, event_id: str) -> dict:
    return {
        "event_id": event_id,
        "mission_slug": _MISSION_SLUG,
        "wp_id": wp_id,
        "from_lane": from_lane,
        "to_lane": to_lane,
        "at": "2026-06-01T12:00:00+00:00",
        "actor": "test-orch",
        "force": False,
        "execution_mode": "worktree",
        "evidence": None,
        "reason": None,
        "review_ref": None,
    }


def _seed_snapshot_subtasks(
    feature_dir: Path,
    wp_id: str,
    subtasks: dict[str, object],
) -> None:
    """Append the event-sourced subtask-completion state used by the gate."""
    from specify_cli.status.models import InnerStateChanged, WPInnerStateDelta
    from specify_cli.status.store import append_annotations_atomic_verified

    append_annotations_atomic_verified(
        feature_dir,
        [
            InnerStateChanged(
                event_id="01KX0RCH000000000000000000",
                wp_id=wp_id,
                at="2026-06-01T12:00:30+00:00",
                actor="test-orch",
                delta=WPInnerStateDelta(subtasks=subtasks),
            )
        ],
    )


def _seed_mission(
    tmp_path: Path,
    *,
    tasks_md: str,
    snapshot_subtasks: dict[str, object] | None = None,
) -> Path:
    """Build a real, flat (no coordination-branch) mission: a git repo whose
    ``kitty-specs/<slug>/`` IS the STATUS read dir AND the PRIMARY planning
    surface -- so the transition runs through the shared emit layer's
    non-transactional route (``_transaction_topology_available`` is False for
    a flat mission), exercising the SAME ``_infer_subtasks_complete`` fix
    WP02 landed at ``status/emit.py:580-582``.
    """
    repo_root = _make_git_repo(tmp_path)
    primary = repo_root / "kitty-specs" / _MISSION_SLUG
    tasks_dir = primary / "tasks"
    tasks_dir.mkdir(parents=True)
    (primary / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": _MISSION_ID,
                "mission_slug": _MISSION_SLUG,
                "slug": _MISSION_SLUG,
                "mission_number": None,
                "mission_type": "software-dev",
                "status_phase": 2,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (primary / "tasks.md").write_text(tasks_md, encoding="utf-8")
    (tasks_dir / "WP01.md").write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Example\n"
        "dependencies: []\n"
        "subtasks:\n"
        "- T001\n"
        "- T002\n"
        "---\n\n"
        "body\n",
        encoding="utf-8",
    )
    # WP01 already sits in in_progress -- the only lane from which
    # in_progress -> for_review is even a legal edge.
    events = [
        _status_event("WP01", "planned", "claimed", "01HXYZ0123456789ABCDEFGH40"),
        _status_event("WP01", "claimed", "in_progress", "01HXYZ0123456789ABCDEFGH41"),
    ]
    primary.joinpath("status.events.jsonl").write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )
    if snapshot_subtasks is not None:
        _seed_snapshot_subtasks(primary, "WP01", snapshot_subtasks)
    _git(repo_root, "add", ".")
    _git(repo_root, "commit", "-m", "seed mission")
    return repo_root


def _run_transition(repo_root: Path, extra_args: list[str] | None = None):
    """Invoke the real ``transition WP01 -> for_review`` orchestrator door.

    Only the ``to_lane == FOR_REVIEW`` commit gate (a separate, unrelated
    guard) is bypassed -- ``emit_status_transition_transactional`` and
    everything downstream of it runs for real, so a pass here proves the
    door blocks/allows through the shared emit layer alone, with no per-door
    pre-derivation left in ``orchestrator_api/commands.py``.
    """
    with (
        patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ),
        patch(
            "specify_cli.orchestrator_api.wp_lifecycle._enforce_for_review_commit_gate",
            return_value=None,
        ),
    ):
        return runner.invoke(
            app,
            [
                "transition",
                "--mission",
                _MISSION_SLUG,
                "--wp",
                "WP01",
                "--to",
                "for_review",
                "--actor",
                "test-orch",
                "--policy",
                _POLICY,
                *(extra_args or []),
            ],
        )


_UNCHECKED_TASKS_MD = (
    "# Tasks\n\n## WP01 — Repro\n- [ ] T001 First (WP01)\n- [ ] T002 Second (WP01)\n"
)
_CHECKED_TASKS_MD = (
    "# Tasks\n\n## WP01 — Repro\n- [x] T001 First (WP01)\n- [x] T002 Second (WP01)\n"
)


def test_unasserted_flag_blocks_on_silent_snapshot(tmp_path: Path) -> None:
    """No assertion + authored roster + silent snapshot must fail closed.

    The checked ``tasks.md`` rows are an opposite-state decoy: checkbox bytes
    cannot satisfy the event-sourced gate after #2816.
    """
    repo_root = _seed_mission(tmp_path, tasks_md=_CHECKED_TASKS_MD)
    result = _run_transition(repo_root)

    assert result.exit_code != 0, result.output
    payload = json.loads(result.output)
    assert payload["success"] is False
    assert payload["error_code"] == "TRANSITION_REJECTED"


def test_unasserted_flag_allows_when_snapshot_marks_all_done(tmp_path: Path) -> None:
    """Snapshot completion wins even when the legacy checkbox decoy is unchecked."""
    from specify_cli.status.models import Lane

    repo_root = _seed_mission(
        tmp_path,
        tasks_md=_UNCHECKED_TASKS_MD,
        snapshot_subtasks={"T001": Lane.DONE, "T002": Lane.DONE},
    )
    result = _run_transition(repo_root, ["--implementation-evidence-present"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["success"] is True
    assert payload["data"]["from_lane"] == "in_progress"
    assert payload["data"]["to_lane"] == "for_review"


def test_explicit_caller_assertion_cannot_bypass_snapshot_gate(tmp_path: Path) -> None:
    """Compatibility input is ignored for normal review transitions.

    A silent snapshot remains incomplete even when the caller asserts
    ``--subtasks-complete``; only the explicit force-with-reason path bypasses.
    """
    repo_root = _seed_mission(tmp_path, tasks_md=_UNCHECKED_TASKS_MD)
    result = _run_transition(
        repo_root, ["--subtasks-complete", "--implementation-evidence-present"]
    )

    assert result.exit_code != 0, result.output
    payload = json.loads(result.output)
    assert payload["success"] is False
    assert payload["error_code"] == "TRANSITION_REJECTED"


def test_force_bypasses_the_subtask_guard_entirely(tmp_path: Path) -> None:
    """--force (with reason) bypasses the gate despite a silent snapshot."""
    repo_root = _seed_mission(tmp_path, tasks_md=_UNCHECKED_TASKS_MD)
    result = _run_transition(repo_root, ["--force", "--note", "forced advance"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["success"] is True
