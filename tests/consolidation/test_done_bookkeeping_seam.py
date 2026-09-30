"""Seam test for ``specify_cli.consolidation.done_bookkeeping`` (mission #2057, WP08).

Exercises the decomposed helpers of the CC22 ``_mark_wp_merged_done`` (PLANNED
fallback, force-done, approved replay, dedup) and the CC16
``_assert_merged_wps_done_on_target`` split (in-branch path resolution + event
parsing). The re-export-identity and one-way-import guards (FR-003, FR-005,
FR-006, INV-2) live in the consolidated
``tests/merge/test_merge_compat_surface.py`` (WP04,
dev-assist-retire-path-hardening-01KXAVR0 / #2565) — this file keeps only the
functional coverage.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from specify_cli.consolidation import done_bookkeeping as db
from specify_cli.status import (
    CurrentWpState,
    EventStream,
    InnerStateChanged,
    Lane,
    ReviewOverride,
    WPInnerStateDelta,
)

pytestmark = pytest.mark.fast


# --- _resolve_merge_actor ---------------------------------------------------


def test_resolve_merge_actor_prefers_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPEC_KITTY_AGENT", "claude")
    assert db._resolve_merge_actor(Path("/r")) == "claude"


def test_resolve_merge_actor_falls_back_to_git_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPEC_KITTY_AGENT", raising=False)
    with patch.object(db, "run_command", return_value=(0, "Jane Dev", "")):
        assert db._resolve_merge_actor(Path("/r")) == "Jane Dev"


def test_resolve_merge_actor_unknown_when_all_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("SPEC_KITTY_AGENT", "GIT_AUTHOR_NAME", "USER", "USERNAME"):
        monkeypatch.delenv(var, raising=False)
    with patch.object(db, "run_command", return_value=(1, "", "")):
        assert db._resolve_merge_actor(Path("/r")) == "<unknown>"


# --- _resolve_lane_with_planned_fallback (split branch) ---------------------


def test_planned_fallback_returns_coord_lane_when_not_planned() -> None:
    lane, force = db._resolve_lane_with_planned_fallback(
        coord_lane=Lane.APPROVED, primary_feature_dir=Path("/r"), wp_id="WP01"
    )
    assert lane == Lane.APPROVED
    assert force is False


def test_planned_fallback_reads_primary_and_forces_done() -> None:
    with patch("specify_cli.status.get_wp_lane", return_value="approved"):
        lane, force = db._resolve_lane_with_planned_fallback(
            coord_lane=Lane.PLANNED, primary_feature_dir=Path("/r"), wp_id="WP01"
        )
    assert lane == Lane.APPROVED
    assert force is True


def test_planned_fallback_unparseable_primary_keeps_planned() -> None:
    with patch("specify_cli.status.get_wp_lane", return_value="uninitialized"):
        lane, force = db._resolve_lane_with_planned_fallback(
            coord_lane=Lane.PLANNED, primary_feature_dir=Path("/r"), wp_id="WP01"
        )
    assert lane == Lane.PLANNED
    assert force is False


# --- _parse_target_lanes_by_wp (split helper) -------------------------------


def test_parse_target_lanes_by_wp_keeps_latest() -> None:
    import json

    # Object events + a blank line + a malformed (non-JSON) line — the shapes a
    # real status.events.jsonl on a target branch actually contains.
    text = "\n".join(
        [
            json.dumps({"wp_id": "WP01", "to_lane": "approved"}),
            json.dumps({"wp_id": "WP01", "to_lane": "done"}),
            json.dumps({"wp_id": "WP02", "to_lane": "claimed"}),
            json.dumps({"garbage": True}),
            "",
            "{not valid json",
        ]
    )
    result = db._parse_target_lanes_by_wp(text)
    assert result == {"WP01": "done", "WP02": "claimed"}


# --- _assert_merged_wps_done_on_target (split) ------------------------------


def test_assert_done_on_target_noop_without_mission_id(tmp_path: Path) -> None:
    # mission_id None -> early return, no git invoked.
    db._assert_merged_wps_done_on_target(
        tmp_path, "m", "main", ["WP01"], feature_dir=tmp_path, mission_id=None
    )


def test_assert_done_on_target_raises_when_git_show_fails(tmp_path: Path) -> None:
    with (
        patch.object(db, "run_command", return_value=(1, "", "no such path")),
        pytest.raises(typer.Exit) as exc,
    ):
        db._assert_merged_wps_done_on_target(
            tmp_path, "m", "main", ["WP01"], feature_dir=tmp_path / "kitty-specs" / "m", mission_id="01ID"
        )
    assert exc.value.exit_code == 1


def test_assert_done_on_target_raises_when_wp_not_done(tmp_path: Path) -> None:
    import json

    events = json.dumps({"wp_id": "WP01", "to_lane": "approved"})
    with (
        patch.object(db, "run_command", return_value=(0, events, "")),
        pytest.raises(typer.Exit) as exc,
    ):
        db._assert_merged_wps_done_on_target(
            tmp_path, "m", "main", ["WP01"], feature_dir=tmp_path / "kitty-specs" / "m", mission_id="01ID"
        )
    assert exc.value.exit_code == 1


def test_assert_done_on_target_passes_when_all_done(tmp_path: Path) -> None:
    import json

    events = json.dumps({"wp_id": "WP01", "to_lane": "done"})
    with patch.object(db, "run_command", return_value=(0, events, "")):
        db._assert_merged_wps_done_on_target(
            tmp_path, "m", "main", ["WP01"], feature_dir=tmp_path / "kitty-specs" / "m", mission_id="01ID"
        )


# --- _reconcile_completed_wps_for_resume ------------------------------------


def test_reconcile_drops_stale_completions(tmp_path: Path) -> None:
    from specify_cli.consolidation.state import ConsolidationState

    state = ConsolidationState(mission_id="01ID", mission_slug="m", target_branch="main", wp_order=["WP01", "WP02"])
    state.completed_wps = ["WP01", "WP02"]
    saved: list[ConsolidationState] = []
    # WP01 has on-disk done evidence, WP02 does not.
    with (
        patch.object(db, "_has_transition_to", side_effect=lambda *a, **k: a[2] == "WP01"),
        patch.object(db, "save_state", side_effect=lambda s, _r: saved.append(s)),
    ):
        confirmed = db._reconcile_completed_wps_for_resume(
            feature_dir=tmp_path, mission_slug="m", merge_state=state, repo_root=tmp_path
        )
    assert confirmed == {"WP01"}
    assert state.completed_wps == ["WP01"]
    assert saved == [state]


def test_reconcile_empty_when_no_completions(tmp_path: Path) -> None:
    from specify_cli.consolidation.state import ConsolidationState

    state = ConsolidationState(mission_id="01ID", mission_slug="m", target_branch="main", wp_order=["WP01"])
    assert db._reconcile_completed_wps_for_resume(
        feature_dir=tmp_path, mission_slug="m", merge_state=state, repo_root=tmp_path
    ) == set()


# --- _durable_done_wps_on_coordination_ref (#2711 FR-007) -------------------


def test_durable_done_empty_when_placement_unresolvable(tmp_path: Path) -> None:
    # An unresolvable placement (non-coord / legacy) yields no durable-done set,
    # so the caller falls back to the transactional on-disk check.
    with patch.object(db, "resolve_placement_only", side_effect=RuntimeError("no mission")):
        assert (
            db._durable_done_wps_on_coordination_ref(
                repo_root=tmp_path, mission_slug="m", candidate_wps=["WP01"]
            )
            == set()
        )


def test_durable_done_reduces_committed_coordination_ref(tmp_path: Path) -> None:
    from types import SimpleNamespace

    lanes = {"WP01": Lane.DONE, "WP02": Lane.APPROVED}
    with (
        patch.object(
            db, "resolve_placement_only", return_value=SimpleNamespace(ref="kitty/mission-m")
        ),
        patch(
            "specify_cli.coordination.status_service.read_event_log",
            return_value=[object()],
        ),
        patch(
            "specify_cli.coordination.status_service.wp_lane_actor_from_events",
            side_effect=lambda _events, wp_id: CurrentWpState(lanes[wp_id], None, None),
        ),
    ):
        assert db._durable_done_wps_on_coordination_ref(
            repo_root=tmp_path, mission_slug="m", candidate_wps=["WP01", "WP02"]
        ) == {"WP01"}


def test_durable_done_empty_when_committed_log_empty(tmp_path: Path) -> None:
    from types import SimpleNamespace

    with (
        patch.object(
            db, "resolve_placement_only", return_value=SimpleNamespace(ref="kitty/mission-m")
        ),
        patch("specify_cli.coordination.status_service.read_event_log", return_value=[]),
    ):
        assert (
            db._durable_done_wps_on_coordination_ref(
                repo_root=tmp_path, mission_slug="m", candidate_wps=["WP01"]
            )
            == set()
        )


def test_reconcile_confirms_via_durable_log_when_on_disk_absent(tmp_path: Path) -> None:
    # FR-007: the committed coordination ref is authoritative — a WP confirmed
    # there survives even when the transactional on-disk check would drop it.
    from specify_cli.consolidation.state import ConsolidationState

    state = ConsolidationState(
        mission_id="01ID", mission_slug="m", target_branch="main", wp_order=["WP01", "WP02"]
    )
    state.completed_wps = ["WP01", "WP02"]
    saved: list[ConsolidationState] = []
    with (
        patch.object(
            db, "_durable_coordination_lanes", return_value={"WP01": Lane.DONE, "WP02": ""}
        ),
        patch.object(db, "_has_transition_to", return_value=False),
        patch.object(db, "save_state", side_effect=lambda s, _r: saved.append(s)),
    ):
        confirmed = db._reconcile_completed_wps_for_resume(
            feature_dir=tmp_path, mission_slug="m", merge_state=state, repo_root=tmp_path
        )
    assert confirmed == {"WP01"}
    assert state.completed_wps == ["WP01"]
    assert saved == [state]


def test_reconcile_drops_wp_reopened_after_done_even_with_done_in_history(tmp_path: Path) -> None:
    # #5046 landing (FR-011 recovery): a WP recorded ``done`` by a consolidation
    # whose gate then FAILed, and reopened for rework, is no longer done on the
    # durable ref — its historical ``done`` event must NOT confirm it, or the
    # re-merge skips its done record and post-merge validation fails forever.
    from specify_cli.consolidation.state import ConsolidationState

    state = ConsolidationState(mission_id="01ID", mission_slug="m", target_branch="main", wp_order=["WP01"])
    state.completed_wps = ["WP01"]
    with (
        patch.object(db, "_durable_coordination_lanes", return_value={"WP01": Lane.APPROVED}),
        patch.object(db, "_has_transition_to", return_value=True),
        patch.object(db, "save_state"),
    ):
        confirmed = db._reconcile_completed_wps_for_resume(feature_dir=tmp_path, mission_slug="m", merge_state=state, repo_root=tmp_path)
    assert confirmed == set()
    assert state.completed_wps == []


def test_reconcile_falls_back_to_on_disk_check_when_durable_ref_unreadable(tmp_path: Path) -> None:
    from specify_cli.consolidation.state import ConsolidationState

    state = ConsolidationState(mission_id="01ID", mission_slug="m", target_branch="main", wp_order=["WP01", "WP02"])
    state.completed_wps = ["WP01", "WP02"]
    with (
        patch.object(db, "_durable_coordination_lanes", return_value=None),
        patch.object(db, "_has_transition_to", side_effect=lambda _f, _m, wp, _l, _r: wp == "WP02"),
        patch.object(db, "save_state"),
    ):
        confirmed = db._reconcile_completed_wps_for_resume(feature_dir=tmp_path, mission_slug="m", merge_state=state, repo_root=tmp_path)
    assert confirmed == {"WP02"}


# --- _resolve_wp_path -------------------------------------------------------


def test_resolve_wp_path_finds_first_match(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    (tasks / "WP01-foo.md").write_text("x", encoding="utf-8")
    assert db._resolve_wp_path(tmp_path, "WP01") == tasks / "WP01-foo.md"


def test_resolve_wp_path_returns_none_when_absent(tmp_path: Path) -> None:
    (tmp_path / "tasks").mkdir()
    assert db._resolve_wp_path(tmp_path, "WP99") is None


# --- _resolve_snapshot_done_evidence ---------------------------------------


def _review_stream(actor: str = "reviewer-renata") -> EventStream:
    review = ReviewOverride(
        at="2026-07-21T00:00:00+00:00",
        actor=actor,
        wp_id="WP01",
        reason="approved",
    )
    annotation = InnerStateChanged(
        event_id="01H11111111111111111111111",
        wp_id="WP01",
        at=review.at,
        actor=actor,
        delta=WPInnerStateDelta(review=review),
    )
    return EventStream(annotations=[annotation])


def test_resolve_snapshot_done_evidence_approved() -> None:
    evidence = db._resolve_snapshot_done_evidence(_review_stream(), "WP01")
    assert evidence is not None
    assert evidence.review.reviewer == "reviewer-renata"


def test_resolve_snapshot_done_evidence_none_when_review_absent_or_actor_empty() -> None:
    assert db._resolve_snapshot_done_evidence(EventStream(), "WP01") is None
    assert db._resolve_snapshot_done_evidence(_review_stream(actor=""), "WP01") is None


# --- _resolve_lane_with_planned_fallback: status-not-found branch -----------


def test_planned_fallback_status_not_found_keeps_planned() -> None:
    from specify_cli.status import CanonicalStatusNotFoundError

    with patch(
        "specify_cli.status.get_wp_lane",
        side_effect=CanonicalStatusNotFoundError("no log"),
    ):
        lane, force = db._resolve_lane_with_planned_fallback(
            coord_lane=Lane.PLANNED, primary_feature_dir=Path("/r"), wp_id="WP01"
        )
    # "uninitialized" sentinel is unparseable -> keeps coord PLANNED, no force.
    assert lane == Lane.PLANNED
    assert force is False


# --- _emit_approved_replay_if_needed ----------------------------------------


def _evidence() -> object:
    from specify_cli.status import DoneEvidence, ReviewApproval

    return DoneEvidence(
        review=ReviewApproval(reviewer="r", verdict="approved", reference="x")
    )


def test_approved_replay_skipped_when_not_pre_approved() -> None:
    # An in_review lane is neither pre-approved nor a planned->approved replay.
    result = db._emit_approved_replay_if_needed(
        feature_dir=Path("/r"),
        mission_slug="m",
        wp_id="WP01",
        target_branch="main",
        repo_root=Path("/r"),
        lane=Lane.IN_REVIEW,
        coord_lane=Lane.IN_REVIEW,
        force_done=False,
        evidence=_evidence(),
    )
    assert result == (Lane.IN_REVIEW, False)


def test_approved_replay_dedup_skips_emit() -> None:
    with patch.object(db, "_has_transition_to", return_value=True):
        result = db._emit_approved_replay_if_needed(
            feature_dir=Path("/r"),
            mission_slug="m",
            wp_id="WP01",
            target_branch="main",
            repo_root=Path("/r"),
            lane=Lane.FOR_REVIEW,
            coord_lane=Lane.FOR_REVIEW,
            force_done=False,
            evidence=_evidence(),
        )
    assert result == (Lane.APPROVED, False)


def test_approved_replay_emits_transition() -> None:
    with (
        patch.object(db, "_has_transition_to", return_value=False),
        patch(
            "specify_cli.coordination.status_transition.emit_status_transition_transactional"
        ) as emit_mock,
    ):
        result = db._emit_approved_replay_if_needed(
            feature_dir=Path("/r"),
            mission_slug="m",
            wp_id="WP01",
            target_branch="main",
            repo_root=Path("/r"),
            lane=Lane.FOR_REVIEW,
            coord_lane=Lane.FOR_REVIEW,
            force_done=False,
            evidence=_evidence(),
        )
    emit_mock.assert_called_once()
    assert result == (Lane.APPROVED, False)


def test_approved_replay_returns_none_on_transition_error() -> None:
    from specify_cli.status import TransitionError

    with (
        patch.object(db, "_has_transition_to", return_value=False),
        patch(
            "specify_cli.coordination.status_transition.emit_status_transition_transactional",
            side_effect=TransitionError("rejected"),
        ),
    ):
        result = db._emit_approved_replay_if_needed(
            feature_dir=Path("/r"),
            mission_slug="m",
            wp_id="WP01",
            target_branch="main",
            repo_root=Path("/r"),
            lane=Lane.FOR_REVIEW,
            coord_lane=Lane.FOR_REVIEW,
            force_done=False,
            evidence=_evidence(),
        )
    assert result is None


# --- _mark_wp_merged_done: early-exit branches ------------------------------
#
# The WP-file lookup goes through ``placement_seam(...).read_dir(
# MissionArtifactKind.WORK_PACKAGE_TASK)``, so these tests patch that seam entry
# point. Each early exit is pinned by its observable effect: the done transition
# is never emitted, and the operator sees the exit's own warning (or none).

_EMIT_TRANSACTIONAL = "specify_cli.coordination.status_transition.emit_status_transition_transactional"
_READ_STREAM_TRANSACTIONAL = "specify_cli.coordination.status_transition.read_event_stream_transactional"
_READ_STATE_TRANSACTIONAL = "specify_cli.coordination.status_transition.read_current_wp_state_transactional"


def _primary_seam(tmp_path: Path) -> MagicMock:
    return MagicMock(read_dir=MagicMock(return_value=tmp_path))


def test_mark_wp_merged_done_warns_when_wp_file_missing(tmp_path: Path) -> None:
    with (
        patch.object(db, "placement_seam", return_value=_primary_seam(tmp_path)),
        patch.object(db, "_resolve_wp_path", return_value=None),
        patch(_READ_STREAM_TRANSACTIONAL) as read_stream_mock,
        patch(_EMIT_TRANSACTIONAL) as emit_mock,
        db.console.capture() as captured,
    ):
        db._mark_wp_merged_done(tmp_path, "m", "WP01", "main")
    assert "Could not locate WP file for WP01" in captured.get()
    read_stream_mock.assert_not_called()
    emit_mock.assert_not_called()


def test_mark_wp_merged_done_noop_when_already_done(tmp_path: Path) -> None:
    """Retry idempotence: a WP already ``done`` is skipped silently.

    Without the dedup the flow still emits nothing here (no approval evidence),
    so the silence is the oracle: a fall-through prints a spurious warning.
    """
    wp_file = tmp_path / "WP01.md"
    with (
        patch.object(db, "placement_seam", return_value=_primary_seam(tmp_path)),
        patch.object(db, "_resolve_wp_path", return_value=wp_file),
        patch.object(db, "resolve_status_surface"),
        patch(_READ_STREAM_TRANSACTIONAL, return_value=EventStream()),
        patch(_READ_STATE_TRANSACTIONAL, return_value=CurrentWpState(Lane.DONE, "merge", None)),
        patch(_EMIT_TRANSACTIONAL) as emit_mock,
        db.console.capture() as captured,
    ):
        db._mark_wp_merged_done(tmp_path, "m", "WP01", "main")
    assert "Warning" not in captured.get()
    emit_mock.assert_not_called()


def test_mark_wp_merged_done_re_records_done_for_a_wp_reopened_after_done(tmp_path: Path) -> None:
    """#5046 landing (FR-011 recovery; Refs #4967 (partial)): the dedup keys on the
    CURRENT lane. A WP whose history carries an earlier ``done`` (a FAILed run's
    bookkeeping) but which was reopened and is ``approved`` again is re-recorded."""
    wp_file = tmp_path / "WP01.md"
    with (
        patch.object(db, "placement_seam", return_value=_primary_seam(tmp_path)),
        patch.object(db, "_resolve_wp_path", return_value=wp_file),
        patch.object(db, "resolve_status_surface"),
        patch(_READ_STREAM_TRANSACTIONAL, return_value=_review_stream()),
        patch(_READ_STATE_TRANSACTIONAL, return_value=CurrentWpState(Lane.APPROVED, "merge", None)),
        patch.object(db, "_has_transition_to", return_value=True),  # a done exists in history
        patch.object(db, "_resolve_lane_with_planned_fallback", return_value=(Lane.APPROVED, False)),
        patch.object(db, "_emit_approved_replay_if_needed", return_value=(Lane.APPROVED, False)),
        patch(_EMIT_TRANSACTIONAL) as emit_mock,
    ):
        db._mark_wp_merged_done(tmp_path, "m", "WP01", "main")
    emit_mock.assert_called_once()
    assert emit_mock.call_args.args[0].to_lane == Lane.DONE


def test_mark_wp_merged_done_warns_on_final_transition_error(tmp_path: Path) -> None:
    """A rejected final done emit is reported as a warning and leaves the WP approved.

    Drives the real mission dir and event log; only the git-transactional write
    (the boundary) is replaced, so it can reject the done move.
    """
    import json

    from specify_cli.status import StatusEvent, TransitionError, get_wp_lane
    from specify_cli.status.store import append_event

    mission_slug = "080-test-feature"
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_id": "01TEST00000000000000000000", "mission_slug": mission_slug}),
        encoding="utf-8",
    )
    (feature_dir / "tasks" / "WP01-test.md").write_text(
        '---\nwork_package_id: "WP01"\ntitle: "Test WP"\ndependencies: []\n---\n# WP01\n',
        encoding="utf-8",
    )
    append_event(
        feature_dir,
        StatusEvent(
            event_id="01TESTWP01APPROVED00000000",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane=Lane.FOR_REVIEW,
            to_lane=Lane.APPROVED,
            at="2026-04-09T12:00:00+00:00",
            actor="reviewer",
            force=True,
            execution_mode="direct_repo",
        ),
    )

    with (
        patch(_EMIT_TRANSACTIONAL, side_effect=TransitionError("rejected done jump")) as emit_mock,
        db.console.capture() as captured,
    ):
        db._mark_wp_merged_done(tmp_path, mission_slug, "WP01", "main")

    assert emit_mock.call_args.args[0].to_lane == "done"
    assert "Failed to mark WP01 done after merge: rejected done jump" in captured.get()
    assert get_wp_lane(feature_dir, "WP01") == Lane.APPROVED.value


def test_mark_wp_merged_done_warns_when_lane_not_approved(tmp_path: Path) -> None:
    """A non-approved post-replay lane skips the done move with a warning."""
    wp_file = tmp_path / "WP01.md"
    with (
        patch.object(db, "placement_seam", return_value=_primary_seam(tmp_path)),
        patch.object(db, "_resolve_wp_path", return_value=wp_file),
        patch.object(db, "resolve_status_surface"),
        patch(_READ_STREAM_TRANSACTIONAL, return_value=_review_stream()),
        patch(_READ_STATE_TRANSACTIONAL, return_value=CurrentWpState(Lane.IN_REVIEW, "merge", None)),
        patch.object(db, "_has_transition_to", return_value=False),
        patch.object(
            db, "_resolve_lane_with_planned_fallback", return_value=(Lane.IN_REVIEW, False)
        ),
        patch.object(
            db, "_emit_approved_replay_if_needed", return_value=(Lane.IN_REVIEW, False)
        ),
        patch(_EMIT_TRANSACTIONAL) as emit_mock,
        db.console.capture() as captured,
    ):
        db._mark_wp_merged_done(tmp_path, "m", "WP01", "main")
    assert "WP01 is in lane 'in_review', not approved" in captured.get()
    emit_mock.assert_not_called()


def test_mark_wp_merged_done_aborts_when_replay_returns_none(tmp_path: Path) -> None:
    """A failed approved-replay (None) aborts the done emission.

    The resolved lane is APPROVED, so the not-approved guard downstream cannot
    stop the emit: only the abort-on-None does.
    """
    wp_file = tmp_path / "WP01.md"
    with (
        patch.object(db, "placement_seam", return_value=_primary_seam(tmp_path)),
        patch.object(db, "_resolve_wp_path", return_value=wp_file),
        patch.object(db, "resolve_status_surface"),
        patch(_READ_STREAM_TRANSACTIONAL, return_value=_review_stream()),
        patch(_READ_STATE_TRANSACTIONAL, return_value=CurrentWpState(Lane.FOR_REVIEW, "merge", None)),
        patch.object(db, "_has_transition_to", return_value=False),
        patch.object(
            db, "_resolve_lane_with_planned_fallback", return_value=(Lane.APPROVED, False)
        ),
        patch.object(db, "_emit_approved_replay_if_needed", return_value=None),
        patch(_EMIT_TRANSACTIONAL) as emit_mock,
    ):
        db._mark_wp_merged_done(tmp_path, "m", "WP01", "main")
    emit_mock.assert_not_called()


# --- _assert_merged_wps_reached_done ----------------------------------------


def test_assert_reached_done_passes_when_all_done(tmp_path: Path) -> None:
    surface = tmp_path / "kitty-specs" / "m" / "status.events.jsonl"
    with (
        patch.object(db, "resolve_status_surface", return_value=surface),
        patch("specify_cli.status.get_wp_lane", return_value="done"),
        patch("specify_cli.status.resolve_lane_alias", side_effect=lambda x: x),
    ):
        db._assert_merged_wps_reached_done(tmp_path, "m", ["WP01"])


def test_assert_reached_done_raises_when_wp_not_done(tmp_path: Path) -> None:
    surface = tmp_path / "kitty-specs" / "m" / "status.events.jsonl"
    with (
        patch.object(db, "resolve_status_surface", return_value=surface),
        patch("specify_cli.status.get_wp_lane", return_value="approved"),
        patch("specify_cli.status.resolve_lane_alias", side_effect=lambda x: x),
        pytest.raises(typer.Exit) as exc,
    ):
        db._assert_merged_wps_reached_done(tmp_path, "m", ["WP01"])
    assert exc.value.exit_code == 1


def test_assert_reached_done_unrecognized_sentinel_is_incomplete(tmp_path: Path) -> None:
    surface = tmp_path / "kitty-specs" / "m" / "status.events.jsonl"
    with (
        patch.object(db, "resolve_status_surface", return_value=surface),
        patch("specify_cli.status.get_wp_lane", return_value="uninitialized"),
        patch("specify_cli.status.resolve_lane_alias", side_effect=lambda x: x),
        pytest.raises(typer.Exit) as exc,
    ):
        db._assert_merged_wps_reached_done(tmp_path, "m", ["WP01"])
    assert exc.value.exit_code == 1


def test_assert_reached_done_raises_on_missing_event_log(tmp_path: Path) -> None:
    from specify_cli.status import CanonicalStatusNotFoundError

    surface = tmp_path / "kitty-specs" / "m" / "status.events.jsonl"
    with (
        patch.object(db, "resolve_status_surface", return_value=surface),
        patch(
            "specify_cli.status.get_wp_lane",
            side_effect=CanonicalStatusNotFoundError("absent"),
        ),
        pytest.raises(typer.Exit) as exc,
    ):
        db._assert_merged_wps_reached_done(tmp_path, "m", ["WP01"])
    assert exc.value.exit_code == 1


def test_assert_reached_done_raises_on_store_error(tmp_path: Path) -> None:
    from specify_cli.status import StoreError

    surface = tmp_path / "kitty-specs" / "m" / "status.events.jsonl"
    with (
        patch.object(db, "resolve_status_surface", return_value=surface),
        patch("specify_cli.status.get_wp_lane", side_effect=StoreError("corrupt")),
        pytest.raises(typer.Exit) as exc,
    ):
        db._assert_merged_wps_reached_done(tmp_path, "m", ["WP01"])
    assert exc.value.exit_code == 1


# --- _resolve_in_branch_status_events_path ----------------------------------


def test_resolve_in_branch_path_under_repo(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "m"
    rel = db._resolve_in_branch_status_events_path(
        repo_root=tmp_path, feature_dir=feature_dir, mission_slug="m"
    )
    assert rel == Path("kitty-specs") / "m" / "status.events.jsonl"


def test_resolve_in_branch_path_outside_repo_falls_back(tmp_path: Path) -> None:
    # feature_dir not under repo_root -> ValueError branch -> canonical fallback.
    rel = db._resolve_in_branch_status_events_path(
        repo_root=tmp_path, feature_dir=Path("/somewhere/else/m"), mission_slug="m"
    )
    assert rel == Path("kitty-specs") / "m" / "status.events.jsonl"


def test_resolve_in_branch_path_under_worktrees_falls_back(tmp_path: Path) -> None:
    feature_dir = tmp_path / ".worktrees" / "m-coord" / "kitty-specs" / "m"
    rel = db._resolve_in_branch_status_events_path(
        repo_root=tmp_path, feature_dir=feature_dir, mission_slug="m"
    )
    assert rel == Path("kitty-specs") / "m" / "status.events.jsonl"


# --- _record_merged_wps_done_for_merge --------------------------------------


def test_record_merged_wps_skips_completed_and_marks_rest(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from specify_cli.consolidation.state import ConsolidationState

    state = ConsolidationState(
        mission_id="01ID", mission_slug="m", target_branch="main",
        wp_order=["WP01", "WP02"],
    )
    lanes_manifest = SimpleNamespace(
        lanes=[SimpleNamespace(wp_ids=["WP01", "WP02"])]
    )
    marked: list[str] = []
    with (
        patch.object(db, "_reconcile_completed_wps_for_resume", return_value={"WP01"}),
        patch.object(db, "save_state"),
        patch.object(db, "_mark_wp_merged_done", side_effect=lambda *a: marked.append(a[2])),
        patch.object(db, "_assert_merged_wps_reached_done") as assert_mock,
    ):
        db._record_merged_wps_done_for_merge(
            main_repo=tmp_path,
            feature_dir=tmp_path,
            mission_slug="m",
            lanes_manifest=lanes_manifest,
            target_branch="main",
            merge_state=state,
            all_wp_ids=["WP01", "WP02"],
        )
    # WP01 was already completed -> skipped; WP02 marked done.
    assert marked == ["WP02"]
    assert_mock.assert_called_once()
