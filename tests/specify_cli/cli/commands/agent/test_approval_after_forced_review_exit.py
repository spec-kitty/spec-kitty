"""Forced review exits (#5446): approval must work after one, and none may go unnoted on any surface.

A forced ``in_review -> in_progress`` with no verdict makes the status reducer
write ``review_result: null`` into the WP state and carry it through later
``for_review`` / ``in_review`` events. The approval guard used to read that
cleared slot as a damaged verdict record and refused every later approval
(neither ``--force`` nor ``--skip-review-artifact-check`` bypassed it).

Drives the real ``move-task`` path; identities sit on DISTINCT tools.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import Result
from typer.testing import CliRunner

from kernel.clock import now_utc_iso
from specify_cli.status import Lane
from specify_cli.status.models import StatusEvent
from tests._support.status_seed import seed_status_event
from tests.specify_cli.cli.commands.agent import _rework_loop_harness as h

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _forced_review_exit(m: h.ReworkMission) -> None:
    """``for_review -> in_review -> in_progress`` forced, with no review verdict."""
    claim = h.move(m, h.WP, "in_review", h.REVIEWER)
    assert claim.exit_code == 0, claim.output
    # ``move-task --to in_progress`` demands feedback even with --force, so the
    # verdict-less exit is written to the event log as a forced transition (the
    # shape ``agent action implement --force --note`` records).
    seed_status_event(
        m.feature_dir,
        StatusEvent(
            event_id="01FORCEDEXIT000000000000AA",
            mission_slug=m.mission_slug,
            wp_id=h.WP,
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.IN_PROGRESS,
            at=now_utc_iso(),
            actor=h.IMPLEMENTER,
            force=True,
            execution_mode="worktree",
            reason="operator: pulled out of review",
        ),
    )


@pytest.mark.regression
def test_approval_succeeds_after_a_forced_review_exit_with_no_verdict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#5446: forced exit, resubmit, new review claim, normal approval must succeed."""
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)
    _forced_review_exit(m)
    for target, agent in (("for_review", h.IMPLEMENTER), ("in_review", h.REVIEWER)):
        step = h.move(m, h.WP, target, agent)
        assert step.exit_code == 0, f"{target}: {step.output}"

    approved = h.move(m, h.WP, "approved", h.REVIEWER)

    assert approved.exit_code == 0, approved.output
    assert "no parseable review verdict" not in approved.output
    lane_events = [e for e in h.events(m) if "to_lane" in e]
    assert lane_events[-1]["to_lane"] == "approved"
    approval = lane_events[-1]
    assert isinstance(approval.get("review_result"), dict), "approval event carries no populated review_result"
    assert approval["review_result"]["verdict"] == "approved"


@pytest.mark.regression
def test_approval_after_a_forced_review_exit_writes_its_review_artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#5446: the cleared slot is not damage, so the approval gets its review-cycle artifact."""
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)
    _forced_review_exit(m)
    for target, agent in (("for_review", h.IMPLEMENTER), ("in_review", h.REVIEWER)):
        assert h.move(m, h.WP, target, agent).exit_code == 0
    assert h.review_cycle_files(m) == []

    approved = h.move(m, h.WP, "approved", h.REVIEWER)

    assert approved.exit_code == 0, approved.output
    files = h.review_cycle_files(m)
    assert len(files) == 1, files
    assert files[0].startswith("review-cycle-")


def _force_out_of_review(surface: str, m: h.ReworkMission, monkeypatch: pytest.MonkeyPatch, *note: str) -> Result:
    """Force WP01 to ``blocked`` through one transition surface; ``note`` is the surface's own note flag."""
    if surface == "move-task":
        return h.move(m, h.WP, "blocked", h.THIRD, "--force", *([] if not note else ["--note", *note]))
    if surface == "status-emit":
        from specify_cli.cli.commands.agent import status as status_module

        monkeypatch.setattr(status_module, "locate_project_root", lambda *_a, **_k: m.repo)
        monkeypatch.setattr(status_module, "get_main_repo_root", lambda *_a, **_k: m.repo)
        argv = ["emit", h.WP, "--to", "blocked", "--actor", "operator", "--mission", m.mission_slug, "--force", "--json"]
        return CliRunner().invoke(status_module.app, [*argv, *([] if not note else ["--reason", *note])])
    from specify_cli.orchestrator_api import _common
    from specify_cli.orchestrator_api.commands import app as orchestrator_app

    monkeypatch.setattr(_common, "_get_main_repo_root", lambda: m.repo)
    argv = ["transition", "--mission", m.mission_slug, "--wp", h.WP, "--to", "blocked", "--actor", "operator", "--force"]
    return CliRunner().invoke(orchestrator_app, [*argv, *([] if not note else ["--note", *note])])


@pytest.mark.parametrize("surface", ["move-task", "status-emit", "orchestrator-api"])
@pytest.mark.parametrize("lane", ["in_review", "approved"])
def test_unnoted_force_out_of_review_is_refused_on_every_surface(surface: str, lane: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#5446: the transition pipeline refuses a verdict-less force out of in_review/approved on every surface."""
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)
    for target in {"in_review": ("in_review",), "approved": ("in_review", "approved")}[lane]:
        assert h.move(m, h.WP, target, h.REVIEWER).exit_code == 0
    before = h.events(m)

    refused = _force_out_of_review(surface, m, monkeypatch)

    assert refused.exit_code != 0, refused.output
    assert "--force requires a non-blank --note" in refused.output
    assert h.events(m) == before

    noted = _force_out_of_review(surface, m, monkeypatch, "reviewer unavailable")

    assert noted.exit_code == 0, noted.output
    last = [e for e in h.events(m) if "to_lane" in e][-1]
    assert last["to_lane"] == "blocked"
    assert "reviewer unavailable" in str(last["reason"])
