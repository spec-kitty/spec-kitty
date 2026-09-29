"""Unforced review loop across the three rejection routes (#5196).

Mission ``rework-is-not-an-override``. The ordinary reject -> rework -> resubmit
-> review -> approve loop must pass ``move-task``'s agent-ownership guard with
no ``--force`` on any hop, while unrelated agents stay refused (see the
ratchets in ``test_rework_guard_ratchets.py``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.specify_cli.cli.commands.agent import _rework_loop_harness as h

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _ok(m: h.ReworkMission, to: str, agent: str, *extra: str) -> h.Result:
    result = h.move(m, h.WP, to, agent, *extra)
    assert result.exit_code == 0, f"{to} as {agent}: {result.output}"
    return result


def _reject_unforced(m: h.ReworkMission, route: str) -> int:
    return h.reject(m, route, h.REVIEWER, allow_force=False)


def _resume_and_resubmit(m: h.ReworkMission, route: str) -> None:
    if route == "in_review_to_in_progress":
        _ok(m, "for_review", h.IMPLEMENTER)
        return
    for target in ("claimed", "in_progress", "for_review"):
        _ok(m, target, h.IMPLEMENTER)


def _assert_no_force_and_no_override(m: h.ReworkMission, rejection_idx: int, last_output: str) -> None:
    assert h.forced_after(m, rejection_idx) == 0
    for argv in h.argv_log(m):
        assert "--force" not in argv, argv
    probes = h.override_probes(m, move_output=last_output)
    assert not any(probes.values()), probes


@pytest.mark.parametrize("route", h.ROUTES)
def test_two_cycle_loop_needs_no_force(route: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)
    rejection_idx = _reject_unforced(m, route)

    _resume_and_resubmit(m, route)
    _ok(m, "in_review", h.REVIEWER)
    approved = _ok(m, "approved", h.REVIEWER)

    _assert_no_force_and_no_override(m, rejection_idx, approved.output)
    assert h.review_cycle_files(m) == ["review-cycle-1.md", "review-cycle-2.md"]


@pytest.mark.parametrize("route", h.ROUTES)
def test_single_hop_approval_after_resubmit_needs_no_force(route: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)
    rejection_idx = _reject_unforced(m, route)

    _resume_and_resubmit(m, route)
    approved = _ok(m, "approved", h.REVIEWER)

    _assert_no_force_and_no_override(m, rejection_idx, approved.output)


def test_role_read_failure_fails_closed_to_the_old_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If the latest-implementer read fails, the guard behaves exactly as before #5196.

    Same fixture, both halves: with the projection raising, the reviewer's
    unforced review claim is refused ("Agent mismatch"); with it restored, the
    identical move succeeds -- so the refusal is caused by the fail-closed
    branch, not by the fixture.
    """
    from specify_cli.cli.commands.agent import tasks_move_task

    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)

    def _boom(*_a: object, **_k: object) -> str:
        raise RuntimeError("simulated event-log read failure")

    with monkeypatch.context() as patched:
        patched.setattr(tasks_move_task, "latest_implementer_actor", _boom)
        refused = h.move(m, h.WP, "in_review", h.REVIEWER)
    assert refused.exit_code != 0
    assert "Agent mismatch" in refused.output

    allowed = h.move(m, h.WP, "in_review", h.REVIEWER)
    assert allowed.exit_code == 0, allowed.output


def test_implementer_resume_read_failure_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#5377: if the implementer-of-record read fails, ``action implement`` keeps refusing.

    Same fixture, both halves: with the transactional event read raising, the
    implementer is refused (exit 1); with it restored, the identical resume succeeds.
    """
    import specify_cli.coordination.status_transition as status_transition

    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)
    h.reject(m, "in_review_to_in_progress")

    def _boom(*_a: object, **_k: object) -> list[object]:
        raise RuntimeError("simulated event-log read failure")

    with monkeypatch.context() as patched:
        patched.setattr(status_transition, "read_events_transactional", _boom)
        refused = h.implement(m, h.IMPLEMENTER, monkeypatch)
    assert refused.exit_code == 1, refused.output

    allowed = h.implement(m, h.IMPLEMENTER, monkeypatch)
    assert allowed.exit_code == 0, allowed.output


def test_action_implement_resumes_after_in_progress_rejection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#5377: the implementer of record resumes via ``agent action implement``, unforced.

    After ``in_review -> in_progress`` the slot occupant is the reviewer. The
    resume is an idempotent no-op on the lane (no event), and the rework then
    resubmits through the ordinary unforced move.
    """
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)
    rejection_idx = h.reject(m, "in_review_to_in_progress")

    resumed = h.implement(m, h.IMPLEMENTER, monkeypatch)

    assert resumed.exit_code == 0, resumed.output
    assert h.lane_events_after(m, rejection_idx) == []
    resubmitted = _ok(m, "for_review", h.IMPLEMENTER)
    _assert_no_force_and_no_override(m, rejection_idx, resubmitted.output)
