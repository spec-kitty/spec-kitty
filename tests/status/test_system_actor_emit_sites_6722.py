"""Every system status writer records the structured system actor (#6722).

One table, one row per writer site, each driving the real production writer and
returning the actors it wrote. A site that regresses to a bare string or to the wrong
role fails its own row. Behaviour a site owns beyond its actor (lanes, ids, the
plain-string override slot, the attestation kind, seed tolerance) stays in that site's
own test module.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from specify_cli.status.actor import build_system_actor

pytestmark = [pytest.mark.git_repo]

Driver = Callable[[Path, pytest.MonkeyPatch], list[Any]]


def _bootstrap(tmp_path: Path, _mp: pytest.MonkeyPatch) -> list[Any]:
    from specify_cli.status.bootstrap import bootstrap_canonical_state
    from specify_cli.status.store import read_events

    _mp.setattr("specify_cli.status.emit._status_fan_out", lambda *a, **k: None)
    feature_dir = tmp_path / "kitty-specs" / "060-test-feature"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    for wp_id in ("WP01", "WP02"):
        (tasks_dir / f"{wp_id}.md").write_text(f"---\nwork_package_id: {wp_id}\ntitle: T\n---\n\n# T\n", encoding="utf-8")
    assert bootstrap_canonical_state(feature_dir, "060-test-feature").newly_seeded == 2
    return [e.actor for e in read_events(feature_dir)]


def _recovery(tmp_path: Path, _mp: pytest.MonkeyPatch) -> list[Any]:
    from specify_cli.lanes.recovery import RECOVERY_ACTOR, RecoveryState, reconcile_status
    from specify_cli.status.models import actor_identity_str
    from specify_cli.status.store import read_events
    from tests.lanes.test_implementation_recovery import _create_lane_branch_with_commits, _make_git_repo, _setup_feature

    repo = tmp_path / "repo"
    repo.mkdir()
    _make_git_repo(repo)
    _setup_feature(repo)
    _create_lane_branch_with_commits(repo)
    state = RecoveryState(
        wp_id="WP01",
        lane_id="lane-a",
        branch_name="kitty/mission-010-feat-lane-a",
        branch_exists=True,
        worktree_exists=True,
        context_exists=True,
        status_lane="planned",
        has_commits=True,
        recovery_action="emit_transitions",
    )
    assert reconcile_status(repo, "010-feat", state) == 2
    return [e.actor for e in read_events(repo / "kitty-specs" / "010-feat") if actor_identity_str(e.actor) == RECOVERY_ACTOR]


def _done_mark(tmp_path: Path, mp: pytest.MonkeyPatch) -> list[Any]:
    from specify_cli.consolidation.done_bookkeeping import _mark_wp_merged_done
    from tests.consolidation.test_system_actor_6722 import _mission, _seed_runtime

    repo_root, feature_dir = _mission(tmp_path)
    _seed_runtime(feature_dir)
    emit = Mock()
    mp.setattr("specify_cli.coordination.status_transition.emit_status_transition_transactional", emit)
    mp.setattr("specify_cli.status.lane_reader.get_wp_lane", lambda *_a, **_kw: "approved")
    _mark_wp_merged_done(repo_root, "021-test", "WP01", "main")
    return [emit.call_args.args[0].actor]


def _refusal_probe(tmp_path: Path, mp: pytest.MonkeyPatch) -> list[Any]:
    from specify_cli.consolidation import preflight
    from specify_cli.lanes.models import ExecutionLane, LanesManifest
    from tests.consolidation.test_system_actor_6722 import _mission, _seed_runtime

    repo_root, feature_dir = _mission(tmp_path)
    _seed_runtime(feature_dir)
    manifest = LanesManifest(
        version=1,
        mission_slug="021-test",
        mission_id="01TEST00000000000000000000",
        mission_branch="kitty/mission-021-test",
        target_branch="main",
        lanes=[ExecutionLane(lane_id="lane-a", wp_ids=("WP01",), write_scope=("src/**",), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)],
        computed_at="2026-10-30T00:00:00+00:00",
        computed_from="test",
    )
    seen: list[Any] = []
    mp.setattr("specify_cli.coordination.status_transition.status_write_refusal", lambda request: seen.append(request))
    assert preflight.refuse_protected_status_target(repo_root, "021-test", manifest) is None
    return [r.actor for r in seen]


def _skip_evidence(tmp_path: Path, mp: pytest.MonkeyPatch) -> list[Any]:
    from specify_cli.consolidation.preflight import _record_review_artifact_skip_evidence
    from specify_cli.post_merge.review_artifact_consistency import ReviewArtifactFinding
    from tests.consolidation.test_system_actor_6722 import _mission

    _, feature_dir = _mission(tmp_path)
    captured: list[Any] = []
    mp.setattr("specify_cli.coordination.status_transition.emit_inner_state_changed_transactional", lambda *a, **k: captured.append(k["actor"]))
    mp.setenv("SPEC_KITTY_AGENT", "operator-ivan")
    _record_review_artifact_skip_evidence(
        repo_root=tmp_path,
        feature_dir=feature_dir,
        mission_slug="021-test",
        findings=[ReviewArtifactFinding(wp_id="WP01", lane="approved", artifact_path=None, cycle_number=1, verdict="rejected")],
        note="reviewed",
    )
    return captured


def _attestation(kind: str) -> Driver:
    def drive(tmp_path: Path, mp: pytest.MonkeyPatch) -> list[Any]:
        from tests.consolidation.test_system_actor_6722 import _attestation_fixture

        feature_dir, emit = _attestation_fixture(tmp_path, mp)
        common: dict[str, Any] = {"repo_root": tmp_path, "feature_dir": feature_dir, "mission_slug": "021-test", "wp_id": "WP01", "actor": "operator-ivan"}
        if kind == "approved":
            from specify_cli.consolidation.approved_attestation import record_approved_reviewed_attestation

            record_approved_reviewed_attestation(**common, current_lane="approved", reason="reviewed")
        else:
            from specify_cli.consolidation.canceled_attestation import record_canceled_superseded_attestation

            record_canceled_superseded_attestation(**common, reason="superseded")
        return [emit.call_args.args[0].actor]

    return drive


def _wp_status_backfill(tmp_path: Path, _mp: pytest.MonkeyPatch) -> list[Any]:
    from specify_cli.migration import wp_status_backfill
    from tests.unit.migration.test_system_actor_6722 import _wp_mission

    return [e.actor for e in wp_status_backfill.plan_wp_status_backfill(_wp_mission(tmp_path)).events]


def _verdict_backfill(tmp_path: Path, _mp: pytest.MonkeyPatch) -> list[Any]:
    from specify_cli.migration import verdict_provenance_backfill
    from specify_cli.status.models import is_migration_actor
    from specify_cli.status.store import read_event_stream
    from tests.unit.migration.test_system_actor_6722 import _verdict_mission

    feature_dir = _verdict_mission(tmp_path)
    assert verdict_provenance_backfill.backfill_verdict_provenance(feature_dir).appended_count == 1
    return [e.actor for e in read_event_stream(feature_dir).transitions if is_migration_actor(e.actor)]


def _runtime_backfill(tmp_path: Path, _mp: pytest.MonkeyPatch) -> list[Any]:
    from specify_cli.migration import backfill_runtime_state
    from specify_cli.status.models import is_migration_actor
    from specify_cli.status.store import read_event_stream
    from tests.unit.migration._backfill_fixture import build_mission

    feature_dir = build_mission(tmp_path)
    result = backfill_runtime_state.backfill_runtime_state(feature_dir)
    stream = read_event_stream(feature_dir)
    seeds = [e.actor for e in [*stream.transitions, *stream.annotations] if is_migration_actor(e.actor)]
    assert len(seeds) == result.seeded_count > 0
    return seeds


_SITES = [
    pytest.param(_bootstrap, "finalize-tasks", id="bootstrap-seed"),
    pytest.param(_recovery, "recovery", id="recovery-catch-up"),
    pytest.param(_done_mark, "merge", id="merge-done-mark"),
    pytest.param(_refusal_probe, "merge", id="done-refusal-probe"),
    pytest.param(_skip_evidence, "operator-ivan", id="review-artifact-skip-override"),
    pytest.param(_attestation("approved"), "operator-ivan", id="approved-attestation"),
    pytest.param(_attestation("canceled"), "operator-ivan", id="canceled-attestation"),
    pytest.param(_wp_status_backfill, "migration:backfill_wp_status", id="wp-status-backfill"),
    pytest.param(_verdict_backfill, "migration:verdict_provenance_backfill", id="verdict-provenance-backfill"),
    pytest.param(_runtime_backfill, "migration:backfill_runtime_state", id="runtime-state-backfill"),
]


@pytest.mark.parametrize(("drive", "identity"), _SITES)
def test_writer_site_records_the_structured_system_actor(drive: Driver, identity: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    actors = drive(tmp_path, monkeypatch)
    assert actors, "the site must have written, or nothing is asserted"
    for actor in actors:
        assert actor == build_system_actor(identity)
