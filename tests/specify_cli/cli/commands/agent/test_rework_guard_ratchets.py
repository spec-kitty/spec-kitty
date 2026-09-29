"""Ratchets pinning review-loop behaviour that is already correct on the base.

Mission ``rework-is-not-an-override`` (#5196). These pass with no product change
and must keep passing after WP02/WP03.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.specify_cli.cli.commands.agent import _rework_loop_harness as h

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _forced_override_from_planned(m: h.ReworkMission) -> h.Result:
    return h.move(m, h.WP, "approved", h.REVIEWER, "--force", "--note", h.ARBITER_NOTE)


def test_genuine_for_review_override_lights_all_five_probes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control: a real arbiter override is visible on every probe."""
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)
    h.reject(m, "for_review_to_planned", allow_force=True)
    assert not any(h.override_probes(m).values()), "no probe may fire before the override"

    result = _forced_override_from_planned(m)

    assert result.exit_code == 0, result.output
    probes = h.override_probes(m, move_output=result.output)
    assert probes == dict.fromkeys(probes, True), probes
    assert len(probes) == 5


def _refused(m: h.ReworkMission, to: str, agent: str, *extra: str) -> None:
    before = len(h.events(m))
    result = h.move(m, h.WP, to, agent, *extra)
    assert result.exit_code != 0, result.output
    assert "Agent mismatch" in result.output, result.output
    assert len(h.events(m)) == before, "a refused move must append 0 raw log lines"


def test_unrelated_agent_refused_on_occupied_in_progress_slot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    m = h.build_mission(tmp_path, monkeypatch)
    for target in ("claimed", "in_progress"):
        assert h.move(m, h.WP, target, h.IMPLEMENTER).exit_code == 0
    _refused(m, "for_review", h.THIRD)


def test_unrelated_agent_refused_on_slot_left_by_forced_rejection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Base: a for_review rejection leaves the slot with the reviewer; a third tool cannot claim it.

    By design (not tested): after an ``in_review -> planned`` rejection the slot is
    released (#4673), so an unclaimed WP is claimable by anyone.
    """
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)
    h.reject(m, "for_review_to_planned", allow_force=True)
    _refused(m, "claimed", h.THIRD)


def test_unrelated_agent_refused_on_in_review_verdict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)
    # Setup, not the behaviour under test: the review claim is forced so this
    # ratchet also held on the pre-#5196 base, where the reviewer's own
    # ``for_review -> in_review`` claim was refused unforced. The refusals
    # below are all unforced.
    assert h.move(m, h.WP, "in_review", h.REVIEWER, "--force").exit_code == 0
    _refused(m, "approved", h.THIRD)
    feedback = m.repo / "third-feedback.md"
    feedback.write_text("## Issues\n\nNope.\n", encoding="utf-8")
    _refused(m, "planned", h.THIRD, "--review-feedback-file", str(feedback))


def test_intervening_annotation_does_not_hide_genuine_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.status import WPInnerStateDelta, emit_inner_state_changed

    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)
    h.reject(m, "for_review_to_planned", allow_force=True)
    emit_inner_state_changed(
        m.feature_dir,
        h.WP,
        WPInnerStateDelta(note="unrelated annotation between rejection and override"),
        actor=h.IMPLEMENTER,
        mission_slug=m.mission_slug,
    )

    result = h.move(m, h.WP, "approved", h.REVIEWER, "--force", "--note", h.ARBITER_NOTE)

    assert result.exit_code == 0, result.output
    probes = h.override_probes(m, move_output=result.output)
    assert probes == dict.fromkeys(probes, True), probes


def test_action_implement_rework_after_in_review_rejection_is_unforced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-008: canonical rework via ``agent action implement`` needs no override.

    Uses the production ``workflow`` Typer app (the ``agent action implement``
    entry point), in-process, against the harness mission. This pins the
    ``in_review -> planned`` route; the ``in_review -> in_progress`` route (the
    former research R-07 residual) is covered by
    ``test_rework_unforced_loop.test_action_implement_resumes_after_in_progress_rejection``
    (#5377).
    """
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)
    rejection_idx = h.reject(m, "in_review_to_planned", allow_force=True)

    result = h.implement(m, h.IMPLEMENTER, monkeypatch)

    assert result.exit_code == 0, result.output
    after = h.lane_events_after(m, rejection_idx)
    assert [e["to_lane"] for e in after] == ["claimed", "in_progress"], after
    assert h.forced_after(m, rejection_idx) == 0
    assert all("--force" not in argv for argv in h.argv_log(m)[-1:])
    probes = h.override_probes(m, move_output=result.output)
    assert not any(probes.values()), probes


def test_unrelated_agent_refused_by_action_implement_after_in_progress_rejection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A third tool cannot take over a WP the reviewer rejected back to ``in_progress`` (#5377 FR-002)."""
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)
    h.reject(m, "in_review_to_in_progress")
    before = len(h.events(m))

    result = h.implement(m, h.THIRD, monkeypatch)

    assert result.exit_code == 1, result.output
    assert "already claimed for implementation" in result.output, result.output
    assert len(h.events(m)) == before, "a refused implement must append 0 raw log lines"
