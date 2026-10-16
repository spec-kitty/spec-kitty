"""An unforced ``move-task`` out of ``done`` is refused before anything is recorded (#5447).

``done`` is a terminal lane. Leaving it needs an explicit ``--force``. Without
it, ``spec-kitty agent tasks move-task`` must exit 1 and leave the event log,
the review-cycle artifacts, the git index/HEAD and ``status validate`` exactly
as they were, and the refusal must name the forced command for the requested
target plus ``spec-kitty mission reopen`` for a merged mission.

Forced exits from ``done`` are unchanged, ``done -> blocked|canceled`` keep
today's pipeline refusal, and non-done backward moves keep today's behaviour.

Every test drives the real ``move-task`` Typer app on a real git repository
through ``_rework_loop_harness``. The move under test is sent WITHOUT
``--agent``: the harness's own ``move`` always passes one, and a non-owning
``--agent`` is refused first by the agent-ownership guard.
"""

from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner, Result

from kernel.clock import now_utc_iso
from specify_cli.cli.commands.agent.status import app as status_app
from specify_cli.cli.commands.agent.tasks import app as tasks_app
from specify_cli.status import Lane
from specify_cli.status.models import StatusEvent
from specify_cli.status.store import append_event
from tests.specify_cli.cli.commands.agent import _rework_loop_harness as h

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_DONE_SEED_EVENT_ID = "01J9Z0D0NE0000000000000000"  # a valid Crockford ULID
_REFUSAL = "Cannot move WP01 from 'done'"
_WHY = "rework after hotfix"
_SUGGESTED_PREFIX = "spec-kitty agent tasks move-task"


def _done_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, latest_verdict_rejected: bool = False) -> h.ReworkMission:
    """A lanes mission whose WP01 sits in ``done``.

    By default the WP walks the real CLI to ``approved`` and the final
    ``approved -> done`` hop is appended directly (the rule depends only on
    the current lane). With ``latest_verdict_rejected`` the WP is rejected and
    a forced ``planned -> done`` is appended, so the latest review verdict
    stays ``rejected`` (any CLI approval would write an approved artifact).
    """
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)
    from_lane, force, reason = Lane.APPROVED, False, None
    if latest_verdict_rejected:
        h.reject(m, "in_review_to_planned")  # an in_review exit records the verdict
        from_lane, force, reason = Lane.PLANNED, True, "fixture: forced to done over a rejected review"
    else:
        for target in ("in_review", "approved"):
            r = h.move(m, h.WP, target, h.REVIEWER)
            assert r.exit_code == 0, r.output
    append_event(
        m.feature_dir,
        StatusEvent(
            event_id=_DONE_SEED_EVENT_ID,
            mission_slug=m.mission_slug,
            wp_id=h.WP,
            from_lane=from_lane,
            to_lane=Lane.DONE,
            at=now_utc_iso(),
            actor=h.REVIEWER,
            force=force,
            reason=reason,
            execution_mode="worktree",
        ),
    )
    return m


def _move(m: h.ReworkMission, *argv: str) -> Result:
    """``move-task WP01 --mission <slug> ...`` with NO ``--agent``."""
    return CliRunner().invoke(tasks_app, ["move-task", h.WP, "--mission", m.mission_slug, *argv])


def _git(m: h.ReworkMission, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=m.repo, check=True, capture_output=True, text=True).stdout


def _validate_errors(m: h.ReworkMission) -> list[Any]:
    """The parsed ``errors`` list of ``agent status validate --json``.

    The harness fixture already fails validate before any move (non-ULID
    genesis seed, a done without evidence), so the faithful oracle is "the same
    errors before and after", not "passes".
    """
    result = CliRunner().invoke(status_app, ["validate", "--mission", m.mission_slug, "--json"])
    payload = json.loads(result.stdout)
    errors = payload["errors"]
    assert isinstance(errors, list)
    return errors


def _snapshot(m: h.ReworkMission) -> tuple[Any, ...]:
    return (
        len(h.events(m)),
        h.review_cycle_files(m),
        _git(m, "status", "--porcelain"),
        _git(m, "rev-parse", "HEAD"),
        _validate_errors(m),
    )


def _last_lane_event(m: h.ReworkMission) -> dict[str, Any]:
    lane_events = [e for e in h.events(m) if "to_lane" in e and "from_lane" in e]
    return lane_events[-1]


def _flat(text: str) -> str:
    """Collapse whitespace so console line-wrapping cannot split a phrase."""
    return " ".join(text.split())


def _feedback_file(tmp_path: Path) -> Path:
    """A non-empty review feedback file OUTSIDE the repo (keeps the repo clean)."""
    path = tmp_path / "fb.md"
    path.write_text("## Issues\n\nRework after the hotfix.\n", encoding="utf-8")
    return path


def _assert_nothing_recorded(m: h.ReworkMission, before: tuple[Any, ...]) -> None:
    assert _snapshot(m) == before
    assert _last_lane_event(m)["to_lane"] == "done"


@pytest.mark.parametrize("target", ["approved", "in_progress", "for_review", "in_review", "claimed", "doing"])
def test_unforced_exit_from_done_is_refused_and_records_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str) -> None:
    m = _done_mission(tmp_path, monkeypatch)
    before = _snapshot(m)

    result = _move(m, "--to", target, "--note", "meant WP04")

    assert result.exit_code == 1, result.output
    output = _flat(result.output)
    assert _REFUSAL in output
    assert "--force" in output
    assert "mission reopen" in output
    assert "backward rewind" not in output
    _assert_nothing_recorded(m, before)


def test_unforced_planned_with_feedback_from_done_commits_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    m = _done_mission(tmp_path, monkeypatch)
    _git(m, "add", "-A")
    _git(m, "commit", "-qm", "fixture")
    head0 = _git(m, "rev-parse", "HEAD").strip()
    before = _snapshot(m)

    result = _move(m, "--to", "planned", "--review-feedback-file", str(_feedback_file(tmp_path)), "--note", "x", "--auto-commit")

    assert result.exit_code == 1, result.output
    assert _REFUSAL in _flat(result.output)
    # No "Record review-cycle-2" commit and no compensating revert commit.
    assert _git(m, "log", "--oneline", f"{head0}..HEAD") == ""
    _assert_nothing_recorded(m, before)


def test_unforced_skip_review_override_on_done_writes_no_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The review-override persist fires BEFORE the guard chain; the done-exit
    guard must gate it too, so a refused move appends no override delta."""
    m = _done_mission(tmp_path, monkeypatch, latest_verdict_rejected=True)
    before = _snapshot(m)

    result = _move(m, "--to", "approved", "--skip-review-artifact-check", "--note", "x")

    assert result.exit_code == 1, result.output
    assert _REFUSAL in _flat(result.output)
    _assert_nothing_recorded(m, before)


@pytest.mark.parametrize("target", ["approved", "in_progress", "planned"])
def test_suggested_forced_command_succeeds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str) -> None:
    """The forced command the refusal prints, run exactly as printed, succeeds."""
    m = _done_mission(tmp_path, monkeypatch)
    feedback = _feedback_file(tmp_path)
    extra = ["--review-feedback-file", str(feedback)] if target == "planned" else []

    # The JSON envelope carries the refusal text unwrapped by the console.
    refused = _move(m, "--to", target, *extra, "--json")
    assert refused.exit_code == 1, refused.output
    error = json.loads(refused.stdout)["error"]
    assert _REFUSAL in error
    suggested = [line.strip() for line in error.splitlines() if _SUGGESTED_PREFIX in line]
    assert len(suggested) == 1, error
    line = suggested[0]
    flags = "--review-feedback-file <file> --force --note" if target == "planned" else "--force --note"
    assert f"--to {target} {flags}" in line
    assert f"--mission {m.mission_slug}" in line

    tokens = shlex.split(line)
    assert tokens[:4] == ["spec-kitty", "agent", "tasks", "move-task"]
    argv = [{"<why>": _WHY, "<file>": str(feedback)}.get(tok, tok) for tok in tokens[3:]]
    result = CliRunner().invoke(tasks_app, argv)

    assert result.exit_code == 0, result.output
    last = _last_lane_event(m)
    assert (last["from_lane"], last["to_lane"]) == ("done", target)
    assert last["force"] is True
    assert _WHY in (last.get("reason") or "")


def test_refusal_json_envelope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    m = _done_mission(tmp_path, monkeypatch)
    before = _snapshot(m)

    result = _move(m, "--to", "in_progress", "--json")

    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    assert _REFUSAL in payload["error"]
    assert "new_lane" not in payload
    _assert_nothing_recorded(m, before)


@pytest.mark.parametrize("target", ["blocked", "canceled"])
def test_blocked_and_canceled_from_done_stay_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str) -> None:
    """Ratchet: ``done`` has no edge to blocked/canceled; the pipeline refuses
    them today and still does. Only "refused, nothing recorded" is pinned."""
    m = _done_mission(tmp_path, monkeypatch)
    before = _snapshot(m)

    result = _move(m, "--to", target, "--note", "meant WP04")

    assert result.exit_code == 1, result.output
    _assert_nothing_recorded(m, before)


def test_unforced_non_done_backward_move_is_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ratchet: a non-done backward move keeps today's forced rewind."""
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)

    result = _move(m, "--to", "in_progress")

    assert result.exit_code == 0, result.output
    last = _last_lane_event(m)
    assert (last["from_lane"], last["to_lane"]) == ("for_review", "in_progress")
    assert last["force"] is True
    assert str(last.get("reason") or "").startswith("backward rewind: for_review -> in_progress")
