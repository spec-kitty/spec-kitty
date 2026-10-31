"""#6514: the forced-rewind refusal is one rule, so every write door answers identically.

WP01 put the ``review_ref`` requirement in the work-package state machine and read it from
the auditor via one predicate. This module proves the *parity* half of that claim: the same
invalid request is refused through the second generic door (``orchestrator-api transition``)
with zero bytes written, while ``move-task``'s own forced rewind — which supplies its
``force-override`` sentinel — keeps working, and every other forced edge is untouched.

Every door here is driven through the REAL production route
(``orchestrator_api.commands.app`` -> ``emit_status_transition_transactional``), not a
helper, so a pass proves the wiring rather than the rule alone.
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

_MISSION_SLUG = "forced-rewind-parity"
_MISSION_ID = "01M68J8B3G2N6W1D4Y1FADR15Z"
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
    """Neutralize the fire-and-forget fan-out: this module tests the refusal only."""
    import specify_cli.status.emit as status_emit

    monkeypatch.setattr(status_emit, "_status_fan_out", lambda *args, **kwargs: None)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _event(wp_id: str, from_lane: str, to_lane: str, event_id: str, *, force: bool = False, reason: str | None = None, review_ref: str | None = None) -> dict:
    return {
        "event_id": event_id,
        "mission_slug": _MISSION_SLUG,
        "mission_id": _MISSION_ID,
        "wp_id": wp_id,
        "from_lane": from_lane,
        "to_lane": to_lane,
        "at": "2026-10-31T09:00:00+00:00",
        "actor": "test-orch",
        "force": force,
        "execution_mode": "worktree",
        "evidence": None,
        "reason": reason,
        "review_ref": review_ref,
    }


@pytest.fixture
def repo_with_wp_in_review(tmp_path: Path) -> Path:
    """A flat mission (no coordination branch) whose WP01 sits in ``for_review``.

    The slug deliberately does not end in the mission's mid8, so the transaction-dir
    probe does not collapse this onto a coordination surface and the transition runs
    through the shared emit layer's flat route.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True, text=True)
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / ".kittify").mkdir()
    (repo / "README.md").write_text("test repo\n", encoding="utf-8")

    primary = repo / "kitty-specs" / _MISSION_SLUG
    tasks_dir = primary / "tasks"
    tasks_dir.mkdir(parents=True)
    primary.joinpath("meta.json").write_text(
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
    primary.joinpath("tasks.md").write_text("# Tasks\n\n## WP01 — Forced rewind\n- [x] T001 Seed (WP01)\n", encoding="utf-8")
    (tasks_dir / "WP01.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Forced rewind\ndependencies: []\nsubtasks:\n- T001\n---\n\nbody\n",
        encoding="utf-8",
    )
    primary.joinpath("status.events.jsonl").write_text(
        "\n".join(
            json.dumps(event)
            for event in [
                _event("WP01", "genesis", "planned", "01HXYZ0123456789ABCDEFGH30"),
                _event("WP01", "planned", "claimed", "01HXYZ0123456789ABCDEFGH31"),
                _event("WP01", "claimed", "in_progress", "01HXYZ0123456789ABCDEFGH32"),
                _event("WP01", "in_progress", "for_review", "01HXYZ0123456789ABCDEFGH33"),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "seed mission")
    return repo


def _transition(repo: Path, *extra: str):
    """Invoke the real orchestrator transition door: WP01 -> in_progress, forced."""
    with (
        patch("specify_cli.orchestrator_api._common._get_main_repo_root", return_value=repo),
        patch("specify_cli.orchestrator_api.wp_lifecycle._enforce_for_review_commit_gate", return_value=None),
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
                "in_progress",
                "--actor",
                "test-orch",
                "--policy",
                _POLICY,
                "--force",
                "--note",
                "source boundary changed",
                *extra,
            ],
        )


def _log(repo: Path) -> Path:
    return repo / "kitty-specs" / _MISSION_SLUG / "status.events.jsonl"


def _lane_rows(repo: Path) -> list[dict]:
    return [row for row in (json.loads(line) for line in _log(repo).read_text().splitlines() if line.strip()) if "from_lane" in row]


def test_orchestrator_door_refuses_the_pointerless_forced_rewind(repo_with_wp_in_review: Path) -> None:
    """T006: the second generic door refuses, and writes nothing (SC-004)."""
    before = _log(repo_with_wp_in_review).read_bytes()
    rows_before = len(_lane_rows(repo_with_wp_in_review))

    result = _transition(repo_with_wp_in_review)

    assert result.exit_code != 0, f"the pointerless rewind was accepted: {result.stdout}"
    assert _log(repo_with_wp_in_review).read_bytes() == before, "the refused door wrote to the log"
    assert len(_lane_rows(repo_with_wp_in_review)) == rows_before

    payload = json.loads(result.stdout) if result.stdout.strip().startswith("{") else None
    error_text = json.dumps(payload) if payload is not None else result.stdout
    assert "requires review_ref" in error_text, f"refused for a different reason: {error_text}"
    assert "for_review -> in_progress" in error_text, error_text
    assert "--review-ref" in error_text, "the refusal must name the flag that supplies the pointer"


def test_orchestrator_door_accepts_the_same_rewind_with_a_pointer(repo_with_wp_in_review: Path) -> None:
    """T006 positive control on the same fixture: force + pointer still appends."""
    before = len(_lane_rows(repo_with_wp_in_review))

    result = _transition(repo_with_wp_in_review, "--review-ref", "review-cycle://WP01/1")

    assert result.exit_code == 0, result.stdout
    rows = _lane_rows(repo_with_wp_in_review)
    assert len(rows) == before + 1
    appended = rows[-1]
    assert (appended["from_lane"], appended["to_lane"]) == ("for_review", "in_progress")
    assert appended["review_ref"] == "review-cycle://WP01/1"


@pytest.mark.parametrize(
    ("from_lane", "to_lane"),
    [
        ("done", "in_progress"),
        ("canceled", "planned"),
        ("planned", "in_progress"),
        ("for_review", "planned"),
        ("in_review", "in_progress"),
        ("approved", "in_progress"),
    ],
)
def test_force_elsewhere_is_unchanged(from_lane: str, to_lane: str) -> None:
    """T008: every forced edge outside the requirement set still admits actor + reason."""
    from specify_cli.status.models import GuardContext, Lane
    from specify_cli.status.wp_state import requires_review_ref, wp_state_for

    target = Lane(to_lane)
    assert requires_review_ref(from_lane, to_lane) is False
    ctx = GuardContext(force=True, actor="admin", reason="operator override")

    ok, error = wp_state_for(from_lane).check_transition(target, ctx)

    assert (ok, error) == (True, None), f"{from_lane} -> {to_lane} changed: {error}"


@pytest.mark.parametrize("target", ["planned", "blocked", "canceled"])
def test_forced_exits_from_done_still_work(target: str) -> None:
    """The terminal-exit ratchet: ``done`` stays force-only and force still admits it."""
    from specify_cli.status.models import GuardContext, Lane
    from specify_cli.status.wp_state import wp_state_for

    ok, error = wp_state_for("done").check_transition(Lane(target), GuardContext(force=True, actor="admin", reason="reopen"))

    assert (ok, error) == (True, None), error
    # ... and still refuses without force, as before.
    assert wp_state_for("done").check_transition(Lane(target), GuardContext(actor="admin", reason="reopen"))[0] is False


def _move_task(m: object, *extra: str):
    """Invoke the real ``move-task`` app for WP01 -> in_progress."""
    from specify_cli.cli.commands.agent.tasks import app as tasks_app

    return CliRunner().invoke(
        tasks_app,
        ["move-task", "WP01", "--to", "in_progress", "--mission", m.mission_slug, "--json", *extra],  # type: ignore[attr-defined]
    )


def test_move_task_forced_rewind_still_lands_with_its_sentinel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T007: the surface that already conformed keeps working, and says why.

    ``move-task`` auto-promotes this backward move to a forced rewind; the point of the
    assertion is that the row it writes carries the ``force-override`` sentinel rather
    than the ``review_ref: null`` it wrote before #6514.
    """
    from tests.specify_cli.cli.commands.agent import _rework_loop_harness as h

    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)

    result = _move_task(m)

    assert result.exit_code == 0, result.output
    last = [event for event in h.events(m) if "from_lane" in event][-1]
    assert (last["from_lane"], last["to_lane"]) == ("for_review", "in_progress")
    assert last["force"] is True
    assert last["review_ref"] == "force-override", "a forced rewind must cite the sentinel, not null"


def test_move_task_explicit_force_rewind_also_carries_the_sentinel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T007 control: the explicit-``--force`` form of the same move is unchanged in shape."""
    from tests.specify_cli.cli.commands.agent import _rework_loop_harness as h

    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)

    result = _move_task(m, "--force", "--note", "source boundary changed")

    assert result.exit_code == 0, result.output
    last = [event for event in h.events(m) if "from_lane" in event][-1]
    assert (last["from_lane"], last["to_lane"]) == ("for_review", "in_progress")
    assert last["review_ref"] == "force-override"
