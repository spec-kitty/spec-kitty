"""Scope: merge done recording unit tests — no real git or subprocesses."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest
import typer

from specify_cli.status import (
    InnerStateChanged,
    ReviewOverride,
    WPInnerStateDelta,
)
from specify_cli.status._unsafe import append_annotations_atomic_verified

from specify_cli.cli.commands.consolidate import (
    BaselineMergeCommitError,
    _assert_baseline_merge_commit_on_target,
    _assert_merged_wps_reached_done,
    _mark_wp_merged_done,
    _project_status_bookkeeping_to_target,
    _record_baseline_merge_commit,
)

# WP09 (T048 / TAO-3): the merge-side restore compensator was retired to the single
# owner compensator; the byte-restore/unlink round-trip below re-points onto it.
from specify_cli.coordination.atomic_write import restore_generated_artifact_snapshots

pytestmark = pytest.mark.fast


def _write_minimal_meta(feature_dir: Path) -> None:
    """Write a minimal meta.json (no coord branch) so resolve_status_surface can read it."""
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_id": "01TEST00000000000000000000", "mission_slug": "021-test"}),
        encoding="utf-8",
    )


def _write_wp(path: Path) -> None:
    """Write a minimal WP file. Lane is tracked via event log, not frontmatter."""
    lines = [
        "---",
        'work_package_id: "WP01"',
        'title: "Test WP"',
        "dependencies: []",
        "subtasks: []",
        "---",
        "# WP01",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _seed_runtime(
    feature_dir: Path,
    *,
    review_actor: str | None = None,
    agent: str | None = None,
) -> None:
    review = None
    if review_actor is not None:
        review = ReviewOverride(
            at="2026-07-21T00:00:00+00:00",
            actor=review_actor,
            wp_id="WP01",
            reason="approved",
        )
    append_annotations_atomic_verified(
        feature_dir,
        [
            InnerStateChanged(
                event_id="01H11111111111111111111111",
                wp_id="WP01",
                at="2026-07-21T00:00:00+00:00",
                actor=agent or review_actor or "merge-test",
                delta=WPInnerStateDelta(agent=agent, review=review),
            )
        ],
    )


def test_mark_wp_merged_done_emits_done_transition(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path
    feature_dir = repo_root / "kitty-specs" / "021-test"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    _write_minimal_meta(feature_dir)
    _write_wp(tasks_dir / "WP01-test.md")
    _seed_runtime(feature_dir, review_actor="reviewer-1")

    emit_mock = Mock()
    monkeypatch.setattr("specify_cli.coordination.status_transition.emit_status_transition_transactional", emit_mock)
    # Lane is event-log-driven; seed it as "approved" via lane_reader
    monkeypatch.setattr(
        "specify_cli.status.lane_reader.get_wp_lane",
        lambda *_a, **_kw: "approved",
    )

    _mark_wp_merged_done(repo_root, "021-test", "WP01", "main")

    emit_mock.assert_called_once()
    request = emit_mock.call_args.args[0]
    assert request.to_lane == "done"
    assert request.actor == "merge"
    assert request.reason == "Merged WP01 into main"
    assert request.evidence["review"]["reviewer"] == "reviewer-1"


def test_mark_wp_merged_done_approved_without_review_metadata_synthesizes_evidence(tmp_path: Path, monkeypatch) -> None:
    """WPs in approved lane without review_status/reviewed_by should still transition to done."""
    repo_root = tmp_path
    feature_dir = repo_root / "kitty-specs" / "021-test"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    _write_minimal_meta(feature_dir)
    _write_wp(tasks_dir / "WP01-test.md")

    emit_mock = Mock()
    monkeypatch.setattr("specify_cli.coordination.status_transition.emit_status_transition_transactional", emit_mock)
    monkeypatch.setattr(
        "specify_cli.status.lane_reader.get_wp_lane",
        lambda *_a, **_kw: "approved",
    )

    _mark_wp_merged_done(repo_root, "021-test", "WP01", "main")

    emit_mock.assert_called_once()
    request = emit_mock.call_args.args[0]
    assert request.to_lane == "done"
    assert request.actor == "merge"
    assert request.evidence["review"]["verdict"] == "approved"
    assert request.evidence["review"]["reference"] == "lane-approved:WP01"


def test_mark_wp_merged_done_for_review_without_metadata_skips(tmp_path: Path, monkeypatch) -> None:
    """WPs in for_review lane without approval metadata should NOT transition to done."""
    repo_root = tmp_path
    feature_dir = repo_root / "kitty-specs" / "021-test"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    _write_minimal_meta(feature_dir)
    _write_wp(tasks_dir / "WP01-test.md")

    emit_mock = Mock()
    monkeypatch.setattr("specify_cli.coordination.status_transition.emit_status_transition_transactional", emit_mock)
    monkeypatch.setattr(
        "specify_cli.status.lane_reader.get_wp_lane",
        lambda *_a, **_kw: "for_review",
    )

    _mark_wp_merged_done(repo_root, "021-test", "WP01", "main")

    emit_mock.assert_not_called()


def test_mark_wp_merged_done_records_approved_before_done_for_legacy_for_review(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path
    feature_dir = repo_root / "kitty-specs" / "021-test"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    _write_minimal_meta(feature_dir)
    _write_wp(tasks_dir / "WP01-test.md")
    _seed_runtime(feature_dir, review_actor="reviewer-1")

    emit_mock = Mock()
    monkeypatch.setattr("specify_cli.coordination.status_transition.emit_status_transition_transactional", emit_mock)
    monkeypatch.setattr(
        "specify_cli.status.lane_reader.get_wp_lane",
        lambda *_a, **_kw: "for_review",
    )

    _mark_wp_merged_done(repo_root, "021-test", "WP01", "main")

    assert emit_mock.call_count == 2
    first_request = emit_mock.call_args_list[0].args[0]
    second_request = emit_mock.call_args_list[1].args[0]
    assert first_request.to_lane == "approved"
    assert second_request.to_lane == "done"


@pytest.mark.parametrize("lane_name", ["planned", "claimed", "in_progress"])
def test_mark_wp_merged_done_recovers_reviewed_wps_from_pre_review_lanes(
    tmp_path: Path,
    monkeypatch,
    lane_name: str,
) -> None:
    repo_root = tmp_path
    feature_dir = repo_root / "kitty-specs" / "021-test"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    _write_minimal_meta(feature_dir)
    _write_wp(tasks_dir / "WP01-test.md")
    _seed_runtime(feature_dir, review_actor="reviewer-1")

    emit_mock = Mock()
    monkeypatch.setattr("specify_cli.coordination.status_transition.emit_status_transition_transactional", emit_mock)
    monkeypatch.setattr(
        "specify_cli.status.lane_reader.get_wp_lane",
        lambda *_a, **_kw: lane_name,
    )

    _mark_wp_merged_done(repo_root, "021-test", "WP01", "main")

    assert emit_mock.call_count == 2
    assert emit_mock.call_args_list[0].args[0].to_lane == "approved"
    assert emit_mock.call_args_list[1].args[0].to_lane == "done"


def test_mark_wp_merged_done_replays_approved_before_done_for_primary_fallback(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Primary fallback must replay conforming approved history before done."""
    from specify_cli.status.models import CurrentWpState, Lane

    repo_root = tmp_path
    mission_slug = "021-test"
    feature_dir = repo_root / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01TEST00000000000000000000",
                "mid8": "01TEST00",
                "mission_slug": mission_slug,
                "coordination_branch": "kitty/mission-021-test-01TEST00",
            }
        ),
        encoding="utf-8",
    )
    _write_wp(tasks_dir / "WP01-test.md")
    _seed_runtime(feature_dir, review_actor="reviewer-1")

    emit_mock = Mock()
    monkeypatch.setattr("specify_cli.coordination.status_transition.emit_status_transition_transactional", emit_mock)
    monkeypatch.setattr(
        "specify_cli.coordination.status_transition.read_current_wp_state_transactional",
        lambda **_kw: CurrentWpState(Lane.PLANNED, None, None),
    )
    monkeypatch.setattr(
        "specify_cli.coordination.status_transition.has_transition_to_transactional",
        lambda **_kw: False,
    )
    monkeypatch.setattr(
        "specify_cli.status.lane_reader.get_wp_lane",
        lambda *_a, **_kw: "approved",
    )

    _mark_wp_merged_done(repo_root, mission_slug, "WP01", "main")

    assert emit_mock.call_count == 2
    approved_request = emit_mock.call_args_list[0].args[0]
    done_request = emit_mock.call_args_list[1].args[0]
    assert approved_request.to_lane == "approved"
    assert done_request.to_lane == "done"
    assert done_request.force is False


def test_mark_wp_merged_done_synthesized_evidence_uses_typed_agent(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Lane-approved fallback uses the event-sourced runtime agent."""
    repo_root = tmp_path
    feature_dir = repo_root / "kitty-specs" / "021-test"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    _write_minimal_meta(feature_dir)
    _write_wp(tasks_dir / "WP01-test.md")
    _seed_runtime(feature_dir, agent="gemini-cli")

    emit_mock = Mock()
    monkeypatch.setattr("specify_cli.coordination.status_transition.emit_status_transition_transactional", emit_mock)
    monkeypatch.setattr(
        "specify_cli.status.lane_reader.get_wp_lane",
        lambda *_a, **_kw: "approved",
    )

    _mark_wp_merged_done(repo_root, "021-test", "WP01", "main")

    emit_mock.assert_called_once()
    request = emit_mock.call_args.args[0]
    assert request.evidence["review"]["reviewer"] == "gemini-cli"


def test_mark_wp_merged_done_does_not_read_runtime_frontmatter(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Merge bookkeeping sources all mutable evidence from the event stream.

    WP08 (#2057): _mark_wp_merged_done moved to the ``done_bookkeeping`` seam, so
    the typed-frontmatter import now lives there (not on the command shim).
    """
    import specify_cli.consolidation.done_bookkeeping as db_mod

    assert not hasattr(db_mod, "read_frontmatter")
    assert not hasattr(db_mod, "read_wp_frontmatter")


def test_assert_merged_wps_reached_done_allows_done_snapshot(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    feature_dir = tmp_path / "kitty-specs" / "021-test"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_id": "01TEST00000000000000000000", "mission_slug": "021-test"}),
        encoding="utf-8",
    )

    # Patch the re-exported binding _assert_merged_wps_reached_done actually
    # imports (`from specify_cli.status import get_wp_lane`, resolved at call
    # time) — patching the lane_reader original would not intercept it.
    monkeypatch.setattr(
        "specify_cli.status.get_wp_lane",
        lambda *_a, **_kw: "done",
    )

    _assert_merged_wps_reached_done(tmp_path, "021-test", ["WP01", "WP02"])


def test_assert_merged_wps_reached_done_fails_when_wp_not_done(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    feature_dir = tmp_path / "kitty-specs" / "021-test"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_id": "01TEST00000000000000000000", "mission_slug": "021-test"}),
        encoding="utf-8",
    )

    lanes = {"WP01": "done", "WP02": "planned"}
    # Same call-time re-export binding as the allows_done_snapshot test above;
    # with the lane_reader target this passed for the WRONG reason (the real
    # get_wp_lane raised CanonicalStatusNotFoundError -> Exit, not the lane check).
    monkeypatch.setattr(
        "specify_cli.status.get_wp_lane",
        lambda _feature_dir, wp_id: lanes[wp_id],
    )

    with pytest.raises(typer.Exit):
        _assert_merged_wps_reached_done(tmp_path, "021-test", ["WP01", "WP02"])


# ---------------------------------------------------------------------------
# baseline_merge_commit invariants (Finding 5): modern lane missions must
# land baseline_merge_commit on the target branch or the merge fails loudly.
# ---------------------------------------------------------------------------


_MODERN_MISSION_ID = "01KTESTMISSIONID00000000000"


def _write_meta(feature_dir: Path, mission_slug: str, **overrides: object) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {
        "created_at": "2026-04-07T00:00:00+00:00",
        "friendly_name": mission_slug.replace("-", " "),
        "mission_id": _MODERN_MISSION_ID,
        "mission_number": None,
        "mission_slug": mission_slug,
        "mission_type": "software-dev",
        "slug": mission_slug,
        "target_branch": "main",
    }
    meta.update(overrides)
    (feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_record_baseline_merge_commit_modern_mission_missing_meta_raises(tmp_path: Path) -> None:
    """A modern lane mission with no meta.json is a HARD failure (Finding 5 (b))."""
    feature_dir = tmp_path / "kitty-specs" / "021-test"
    feature_dir.mkdir(parents=True)
    # No meta.json on disk.

    with pytest.raises(BaselineMergeCommitError):
        _record_baseline_merge_commit(
            feature_dir,
            "base123",
            mission_id=_MODERN_MISSION_ID,
        )


def test_record_baseline_merge_commit_modern_mission_empty_baseline_raises(tmp_path: Path) -> None:
    """A modern lane mission with an empty captured baseline is a HARD failure."""
    feature_dir = tmp_path / "kitty-specs" / "021-test"
    _write_meta(feature_dir, "021-test", baseline_merge_commit=None)

    with pytest.raises(BaselineMergeCommitError):
        _record_baseline_merge_commit(
            feature_dir,
            "   ",
            mission_id=_MODERN_MISSION_ID,
        )


def test_record_baseline_merge_commit_modern_mission_invalid_meta_raises(tmp_path: Path) -> None:
    """A modern lane mission with corrupt meta.json is a HARD failure."""
    feature_dir = tmp_path / "kitty-specs" / "021-test"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text("{not valid json", encoding="utf-8")

    with pytest.raises(BaselineMergeCommitError):
        _record_baseline_merge_commit(
            feature_dir,
            "base123",
            mission_id=_MODERN_MISSION_ID,
        )


def test_record_baseline_merge_commit_legacy_missing_meta_soft_returns_none(tmp_path: Path) -> None:
    """A legacy mission (no mission_id) preserves the soft skip behavior."""
    feature_dir = tmp_path / "kitty-specs" / "021-test"
    feature_dir.mkdir(parents=True)
    # No meta.json, no mission_id → legacy soft path returns None, no raise.

    result = _record_baseline_merge_commit(feature_dir, "base123", mission_id=None)

    assert result is None


def test_record_baseline_merge_commit_modern_mission_fills_field(tmp_path: Path) -> None:
    """A modern lane mission with valid meta records baseline and returns the path."""
    feature_dir = tmp_path / "kitty-specs" / "021-test"
    _write_meta(feature_dir, "021-test", baseline_merge_commit=None)

    result = _record_baseline_merge_commit(
        feature_dir,
        "base123",
        mission_id=_MODERN_MISSION_ID,
    )

    assert result == feature_dir / "meta.json"
    data = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert data["baseline_merge_commit"] == "base123"


def test_assert_baseline_on_target_passes_when_committed_meta_matches(tmp_path: Path) -> None:
    """Finding 5 (a)/(c): target meta.json carrying the matching baseline passes."""
    feature_dir = tmp_path / "kitty-specs" / "021-test"
    _write_meta(feature_dir, "021-test")
    committed_meta = json.dumps({"baseline_merge_commit": "base123"})

    with patch(
        "specify_cli.consolidation.baseline.run_command",
        return_value=(0, committed_meta, ""),
    ):
        # Must not raise.
        _assert_baseline_merge_commit_on_target(
            tmp_path,
            "021-test",
            "main",
            "base123",
            mission_id=_MODERN_MISSION_ID,
        )


def test_assert_baseline_on_target_raises_when_baseline_absent(tmp_path: Path) -> None:
    """Finding 5 (c): target meta.json lacking baseline_merge_commit fails loudly."""
    feature_dir = tmp_path / "kitty-specs" / "021-test"
    _write_meta(feature_dir, "021-test")
    committed_meta = json.dumps({"mission_slug": "021-test"})  # no baseline_merge_commit

    with patch(
        "specify_cli.consolidation.baseline.run_command",
        return_value=(0, committed_meta, ""),
    ), pytest.raises(BaselineMergeCommitError):
        _assert_baseline_merge_commit_on_target(
            tmp_path,
            "021-test",
            "main",
            "base123",
            mission_id=_MODERN_MISSION_ID,
        )


def test_assert_baseline_on_target_raises_when_baseline_mismatches(tmp_path: Path) -> None:
    """Target meta.json carrying a DIFFERENT baseline fails loudly."""
    feature_dir = tmp_path / "kitty-specs" / "021-test"
    _write_meta(feature_dir, "021-test")
    committed_meta = json.dumps({"baseline_merge_commit": "other999"})

    with patch(
        "specify_cli.consolidation.baseline.run_command",
        return_value=(0, committed_meta, ""),
    ), pytest.raises(BaselineMergeCommitError):
        _assert_baseline_merge_commit_on_target(
            tmp_path,
            "021-test",
            "main",
            "base123",
            mission_id=_MODERN_MISSION_ID,
        )


def test_assert_baseline_on_target_raises_when_git_show_fails(tmp_path: Path) -> None:
    """A failed `git show <target>:meta.json` (e.g. path absent) fails loudly."""
    feature_dir = tmp_path / "kitty-specs" / "021-test"
    _write_meta(feature_dir, "021-test")

    with patch(
        "specify_cli.consolidation.baseline.run_command",
        return_value=(128, "", "fatal: path does not exist"),
    ), pytest.raises(BaselineMergeCommitError):
        _assert_baseline_merge_commit_on_target(
            tmp_path,
            "021-test",
            "main",
            "base123",
            mission_id=_MODERN_MISSION_ID,
        )


def test_assert_baseline_on_target_skips_legacy_mission(tmp_path: Path) -> None:
    """Legacy missions (no mission_id) skip the target baseline assertion entirely."""
    feature_dir = tmp_path / "kitty-specs" / "021-test"
    feature_dir.mkdir(parents=True)

    # run_command would raise if called — assert it is never invoked for legacy.
    def _boom(*_a: Any, **_kw: Any):
        raise AssertionError("run_command must not be called for legacy missions")

    with patch("specify_cli.consolidation.baseline.run_command", side_effect=_boom):
        _assert_baseline_merge_commit_on_target(
            tmp_path,
            "021-test",
            "main",
            "base123",
            mission_id=None,
        )


def test_assert_baseline_on_target_resume_uses_recorded_baseline_not_live_head(
    tmp_path: Path,
) -> None:
    """Resume safety (Finding 5): the invariant compares the COMMITTED target
    baseline against the RECORDED working-meta value, not a freshly re-derived
    target HEAD.

    On ``spec-kitty merge --resume`` a prior run already landed the
    mission/bookkeeping commits, so the live target HEAD (the value
    ``expected_baseline`` is captured from on each invocation) has advanced past
    the original baseline. Comparing the committed value against that advanced
    HEAD would spuriously fail an otherwise-correct resume. Passing
    ``feature_dir`` makes the assertion read the originally-recorded baseline,
    which is stable across resume.
    """
    feature_dir = tmp_path / "kitty-specs" / "021-test"
    # Run 1 recorded the original pre-merge baseline into the working meta and
    # committed the same value to the target branch.
    _write_meta(feature_dir, "021-test", baseline_merge_commit="original_sha_a")
    committed_meta = json.dumps({"baseline_merge_commit": "original_sha_a"})

    with patch(
        "specify_cli.consolidation.baseline.run_command",
        return_value=(0, committed_meta, ""),
    ):
        # expected_baseline is the RE-DERIVED, now-advanced target HEAD on
        # resume; it must be ignored in favor of the recorded value.
        _assert_baseline_merge_commit_on_target(
            tmp_path,
            "021-test",
            "main",
            "advanced_sha_b_from_live_head",
            feature_dir=feature_dir,
            mission_id=_MODERN_MISSION_ID,
        )


def test_assert_baseline_on_target_raises_when_committed_differs_from_recorded(
    tmp_path: Path,
) -> None:
    """A genuine drift (committed target baseline != recorded value) still fails
    loudly even when ``feature_dir`` supplies the recorded baseline."""
    feature_dir = tmp_path / "kitty-specs" / "021-test"
    _write_meta(feature_dir, "021-test", baseline_merge_commit="recorded_sha_a")
    committed_meta = json.dumps({"baseline_merge_commit": "drifted_sha_c"})

    with patch(
        "specify_cli.consolidation.baseline.run_command",
        return_value=(0, committed_meta, ""),
    ), pytest.raises(BaselineMergeCommitError):
        _assert_baseline_merge_commit_on_target(
            tmp_path,
            "021-test",
            "main",
            "recorded_sha_a",
            feature_dir=feature_dir,
            mission_id=_MODERN_MISSION_ID,
        )


# ---------------------------------------------------------------------------
# ATDD anchor (T000) — RED until WP02 wires resolve_status_surface
# ---------------------------------------------------------------------------


def test_assert_merged_wps_reads_coord_surface_when_coord_branch_set(
    tmp_path: Path,
) -> None:
    """ATDD anchor [RED]: _assert_merged_wps_reached_done must read from the
    coordination worktree when coordination_branch is set in meta.json.

    Current code reads from the primary checkout (no events there) and raises
    CanonicalStatusNotFoundError. After WP02 wires resolve_status_surface this
    test becomes GREEN.

    Relates-to: #1726
    """
    mission_slug = "my-mission"
    mission_id = "01KTDVHZKGCHCW6HQ4V577PNES"
    mid8 = mission_id[:8]

    # Primary checkout: meta.json present, NO status.events.jsonl
    primary_dir = tmp_path / "kitty-specs" / mission_slug
    primary_dir.mkdir(parents=True)
    (primary_dir / "meta.json").write_text(
        json.dumps({
            "mission_id": mission_id,
            "mission_slug": mission_slug,
            "coordination_branch": f"kitty/mission-{mission_slug}-{mid8}",
        }),
        encoding="utf-8",
    )

    # Coordination worktree: status.events.jsonl with a done event for WP01
    coord_dir = (
        tmp_path / ".worktrees"
        / f"{mission_slug}-{mid8}-coord"
        / "kitty-specs"
        / f"{mission_slug}-{mid8}"
    )
    coord_dir.mkdir(parents=True)
    done_event = {
        "event_id": "01KTDVHZ000000000000000001",
        "mission_slug": mission_slug,
        "wp_id": "WP01",
        "from_lane": "approved",
        "to_lane": "done",
        "at": "2026-06-06T00:00:00+00:00",
        "actor": "merge",
        "force": False,
        "execution_mode": "worktree",
        "reason": "Merged WP01 into main",
        "review_ref": None,
        "evidence": None,
        "policy_metadata": None,
    }
    (coord_dir / "status.events.jsonl").write_text(
        json.dumps(done_event) + "\n", encoding="utf-8"
    )

    # The primary checkout has meta.json but NO status.events.jsonl, while the
    # coordination worktree carries the done event. _assert_merged_wps_reached_done
    # must read the coord surface (via resolve_status_surface): if it read the
    # primary checkout instead, get_wp_lane would raise CanonicalStatusNotFoundError.
    _assert_merged_wps_reached_done(tmp_path, mission_slug, ["WP01"])


# ---------------------------------------------------------------------------
# WP03: Coordination branch surface regression tests (parity ratchet — #1726)
# ---------------------------------------------------------------------------

_COORD_SLUG = "test-coord-mission"
_COORD_MISSION_ID = "01KTDVHZKGCHCW6HQ4V577PNES"


@pytest.fixture
def coord_branch_mission(tmp_path: Path) -> dict:
    """Minimal coord-branch fixture: meta.json + coord worktree stub on disk.

    The slug does NOT end in mid8, so surface_resolver adds the suffix:
      worktree: .worktrees/test-coord-mission-01KTDVHZ-coord/
      events:   kitty-specs/test-coord-mission-01KTDVHZ/status.events.jsonl
    """
    mid8 = _COORD_MISSION_ID[:8]  # "01KTDVHZ"
    coord_branch = f"kitty/mission-{_COORD_SLUG}-{mid8}"

    primary_dir = tmp_path / "kitty-specs" / _COORD_SLUG
    primary_dir.mkdir(parents=True)
    (primary_dir / "meta.json").write_text(
        json.dumps({
            "mission_id": _COORD_MISSION_ID,
            "mission_slug": _COORD_SLUG,
            "slug": _COORD_SLUG,
            "coordination_branch": coord_branch,
            "target_branch": "main",
        }),
        encoding="utf-8",
    )

    # Coord worktree path matches what surface_resolver.py derives:
    #   .worktrees/<slug>-<mid8>-coord/kitty-specs/<slug>-<mid8>/
    coord_dir_name = f"{_COORD_SLUG}-{mid8}"
    coord_specs = (
        tmp_path / ".worktrees" / f"{coord_dir_name}-coord"
        / "kitty-specs" / coord_dir_name
    )
    coord_specs.mkdir(parents=True)
    coord_events = coord_specs / "status.events.jsonl"
    coord_events.write_text("", encoding="utf-8")

    return {
        "repo_root": tmp_path,
        "mission_slug": _COORD_SLUG,
        "mid8": mid8,
        "primary_dir": primary_dir,
        "coord_specs": coord_specs,
        "coord_events": coord_events,
    }


def _seed_done_event(feature_dir: Path, mission_slug: str, wp_id: str) -> None:
    from specify_cli.status.models import Lane, StatusEvent
    from specify_cli.status.store import append_event

    event = StatusEvent(
        event_id=f"01TESTREGRWP{wp_id[-2:]}DONE0000000"[:26],
        mission_slug=mission_slug,
        wp_id=wp_id,
        from_lane=Lane.APPROVED,
        to_lane=Lane.DONE,
        at="2026-06-06T12:00:00+00:00",
        actor="merge",
        force=False,
        execution_mode="worktree",
    )
    append_event(feature_dir, event)


def test_coord_branch_assert_reads_from_coord_surface(
    coord_branch_mission: dict,
) -> None:
    """With coord branch set, _assert_merged_wps_reached_done reads coord surface.

    Parity ratchet: done event on coord surface → assertion passes.
    Proves the read path uses resolve_status_surface (not primary checkout).

    Relates-to: #1726
    """
    repo_root = coord_branch_mission["repo_root"]
    coord_specs = coord_branch_mission["coord_specs"]

    # Write done event to coord surface only (not primary checkout)
    _seed_done_event(coord_specs, _COORD_SLUG, "WP01")

    # Must NOT raise — reads from coord surface
    _assert_merged_wps_reached_done(repo_root, _COORD_SLUG, ["WP01"])


def test_coord_branch_assert_ignores_primary_checkout(
    coord_branch_mission: dict,
) -> None:
    """With coord branch set, done event on primary checkout does not satisfy assertion.

    Parity ratchet (inverse): done on primary + approved on coord → assertion fails.
    Proves the coord surface and primary checkout are isolated: the reader must
    not fall back to primary when coordination_branch is set.

    Relates-to: #1726
    """
    from specify_cli.status.models import Lane, StatusEvent
    from specify_cli.status.store import append_event

    repo_root = coord_branch_mission["repo_root"]
    primary_dir = coord_branch_mission["primary_dir"]
    coord_specs = coord_branch_mission["coord_specs"]

    # Write done event to PRIMARY ONLY
    _seed_done_event(primary_dir, _COORD_SLUG, "WP01")

    # Write only an approved event to coord surface (not done)
    approved_event = StatusEvent(
        event_id="01TESTCOORDSURFAPPRV00000000"[:26],
        mission_slug=_COORD_SLUG,
        wp_id="WP01",
        from_lane=Lane.IN_PROGRESS,
        to_lane=Lane.APPROVED,
        at="2026-06-06T12:00:00+00:00",
        actor="claude",
        force=False,
        execution_mode="worktree",
    )
    append_event(coord_specs, approved_event)

    # Must RAISE — coord surface only has approved, not done
    with pytest.raises(typer.Exit):
        _assert_merged_wps_reached_done(repo_root, _COORD_SLUG, ["WP01"])


def test_project_status_bookkeeping_unions_coord_surface_into_primary_target(
    coord_branch_mission: dict,
) -> None:
    """Final merge bookkeeping stages primary paths and UNIONS the event log.

    FR-005 (#2709): the coord->target projection must union
    ``source ∪ original`` (via ``merge_event_payloads``) and rematerialize
    ``status.json`` from ``reduce(union)`` — never blind-overwrite the target
    with the coord copy. A target-newer event the coord worktree lacks survives.
    """
    from specify_cli.status import (
        materialize_to_json,
        merge_event_log_texts,
        read_events_from_text,
        reduce,
    )

    repo_root = coord_branch_mission["repo_root"]
    primary_dir = coord_branch_mission["primary_dir"]
    coord_specs = coord_branch_mission["coord_specs"]

    # Target (primary) carries a NEWER done event the coord worktree lacks.
    _seed_done_event(primary_dir, _COORD_SLUG, "WP02")
    # Coord worktree carries the WP01 done event.
    _seed_done_event(coord_specs, _COORD_SLUG, "WP01")

    coord_events_text = (coord_specs / "status.events.jsonl").read_text(encoding="utf-8")
    target_events_text = (primary_dir / "status.events.jsonl").read_text(encoding="utf-8")

    target_events, target_status = _project_status_bookkeeping_to_target(
        main_repo=repo_root,
        mission_slug=_COORD_SLUG,
        status_feature_dir=coord_specs,
    )

    assert target_events == primary_dir / "status.events.jsonl"
    assert target_status == primary_dir / "status.json"
    assert ".worktrees" not in target_events.parts
    assert ".worktrees" not in target_status.parts

    merged_events = target_events.read_text(encoding="utf-8")
    assert "WP02" in merged_events, "target-newer WP02 event must survive the union"
    assert "WP01" in merged_events, "coord-side WP01 event must survive the union"

    expected_snapshot = materialize_to_json(
        reduce(
            read_events_from_text(
                primary_dir,
                merge_event_log_texts(coord_events_text, target_events_text),
            )
        )
    )
    assert target_status.read_text(encoding="utf-8") == expected_snapshot


def test_project_status_bookkeeping_restores_primary_on_projection_failure(
    coord_branch_mission: dict,
) -> None:
    """Projection failure must not leave split-brain primary bookkeeping."""
    repo_root = coord_branch_mission["repo_root"]
    primary_dir = coord_branch_mission["primary_dir"]
    coord_specs = coord_branch_mission["coord_specs"]

    primary_events = primary_dir / "status.events.jsonl"
    primary_status = primary_dir / "status.json"
    primary_events.write_text("old-event\n", encoding="utf-8")
    primary_status.write_text('{"WP01": "approved"}\n', encoding="utf-8")
    (coord_specs / "status.events.jsonl").write_text("new-done-event\n", encoding="utf-8")
    (coord_specs / "status.json").mkdir()

    with pytest.raises(IsADirectoryError):
        _project_status_bookkeeping_to_target(
            main_repo=repo_root,
            mission_slug=_COORD_SLUG,
            status_feature_dir=coord_specs,
        )

    assert primary_events.read_text(encoding="utf-8") == "old-event\n"
    assert primary_status.read_text(encoding="utf-8") == '{"WP01": "approved"}\n'


def test_project_status_bookkeeping_rejects_paths_outside_primary_surface(
    tmp_path: Path,
) -> None:
    """Projected bookkeeping must stay under kitty-specs/<slug>/ in primary checkout."""
    repo_root = tmp_path
    mission_slug = "outside-surface"
    escaped_coord_specs = (
        tmp_path
        / ".worktrees"
        / "outside-surface-coord"
        / "kitty-specs"
        / ".."
        / ".."
        / ".."
    )

    # The claimed topology (``.worktrees`` segment) does not match the resolved
    # location (escapes above the worktrees root), so the topology guard rejects
    # it before containment delegation.
    with pytest.raises(ValueError, match="Untrusted status surface path"):
        _project_status_bookkeeping_to_target(
            main_repo=repo_root,
            mission_slug=mission_slug,
            status_feature_dir=escaped_coord_specs,
        )


def test_project_status_bookkeeping_rejects_wrong_primary_mission_surface(
    tmp_path: Path,
) -> None:
    """Primary bookkeeping paths under kitty-specs must still match the mission slug."""
    with pytest.raises(ValueError, match="outside trusted roots"):
        _project_status_bookkeeping_to_target(
            main_repo=tmp_path,
            mission_slug="expected-mission",
            status_feature_dir=tmp_path / "kitty-specs" / "other-mission",
        )


def test_project_status_bookkeeping_rejects_tainted_status_file_symlink(
    coord_branch_mission: dict,
) -> None:
    """Coord status reads must stay pinned to the exact two trusted filenames."""
    repo_root = coord_branch_mission["repo_root"]
    coord_specs = coord_branch_mission["coord_specs"]

    outside = repo_root / "outside.json"
    outside.write_text('{"WP01": "stolen"}\n', encoding="utf-8")
    (coord_specs / "status.events.jsonl").write_text("new-done-event\n", encoding="utf-8")
    status_path = coord_specs / "status.json"
    if status_path.exists() or status_path.is_symlink():
        status_path.unlink()
    status_path.symlink_to(outside)

    with pytest.raises(ValueError, match="symlinked status surface path"):
        _project_status_bookkeeping_to_target(
            main_repo=repo_root,
            mission_slug=_COORD_SLUG,
            status_feature_dir=coord_specs,
        )


def test_final_bookkeeping_rollback_restores_status_meta_and_state(tmp_path: Path) -> None:
    """Final bookkeeping rollback restores every mutable surface it snapshots."""
    coord_events = tmp_path / ".worktrees" / "m-coord" / "kitty-specs" / "m" / "status.events.jsonl"
    coord_status = coord_events.parent / "status.json"
    target_events = tmp_path / "kitty-specs" / "m" / "status.events.jsonl"
    target_status = target_events.parent / "status.json"
    target_meta = target_events.parent / "meta.json"
    state_path = tmp_path / ".kittify" / "runtime" / "merge" / "01TESTSTATE" / "state.json"
    for path, body in {
        coord_events: b"approved-event\n",
        coord_status: b'{"WP01": "approved"}\n',
        target_meta: b'{"mission_slug": "m"}\n',
        state_path: b'{"completed_wps": []}\n',
    }.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)

    snapshots = {
        coord_events: coord_events.read_bytes(),
        coord_status: coord_status.read_bytes(),
        target_events: None,
        target_status: None,
        target_meta: target_meta.read_bytes(),
        state_path: state_path.read_bytes(),
    }

    coord_events.write_text("approved-event\ndone-event\n", encoding="utf-8")
    coord_status.write_text('{"WP01": "done"}\n', encoding="utf-8")
    target_events.parent.mkdir(parents=True, exist_ok=True)
    target_events.write_text("approved-event\ndone-event\n", encoding="utf-8")
    target_status.write_text('{"WP01": "done"}\n', encoding="utf-8")
    target_meta.write_text('{"mission_slug": "m", "baseline_merge_commit": "HEAD~1"}\n', encoding="utf-8")
    state_path.write_text('{"completed_wps": ["WP01"]}\n', encoding="utf-8")

    restore_generated_artifact_snapshots(snapshots)

    assert coord_events.read_bytes() == b"approved-event\n"
    assert coord_status.read_bytes() == b'{"WP01": "approved"}\n'
    assert not target_events.exists()
    assert not target_status.exists()
    assert target_meta.read_bytes() == b'{"mission_slug": "m"}\n'
    assert state_path.read_bytes() == b'{"completed_wps": []}\n'


def test_final_bookkeeping_rollback_trusts_legacy_merge_state_path(tmp_path: Path) -> None:
    """Legacy merge state remains a trusted rollback snapshot target."""
    legacy_state_path = tmp_path / ".kittify" / "merge-state.json"

    restore_generated_artifact_snapshots({legacy_state_path: b'{"completed_wps": []}\n'})

    assert legacy_state_path.read_bytes() == b'{"completed_wps": []}\n'
