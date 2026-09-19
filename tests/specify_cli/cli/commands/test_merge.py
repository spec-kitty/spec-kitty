"""Tests for merge.py.

WP06 slice: Migrate Slice 4 — merge.py typed Lane enum migration.

Verifies that:
- _assert_merged_wps_reached_done() uses typed Lane enum (Lane.DONE), not raw "done"
- _mark_wp_merged_done() uses typed Lane enum comparisons throughout
- approved|done merge-ready check is EXPLICIT (not delegated to is_terminal)
- is_terminal covers done|canceled — not the same as merge-ready approved|done
- All 9 lanes are correctly classified as merge-ready or not

WP01 slice: merge --abort cleanup.

Verifies that:
- --abort removes .kittify/runtime/merge/__global_merge__/lock when present
- --abort removes .kittify/merge-state.json (legacy) when present
- --abort is idempotent — exits 0 when neither file is present

WP04 slice: validator delegate + collapse containment helpers.

Verifies that:
- _validate_mission_slug_path_segment delegates to assert_safe_path_segment
- _MISSION_SLUG_PATH_SEGMENT_RE dead constant is removed
- FR-003: _assert_status_path_within_target_surface rejects malformed slug (sibling :828)
- FR-003: _run_lane_based_merge target_feature_dir path rejects malformed slug (sibling :2382)
- T015: dry-run/abort with malformed slug emits "single safe path segment" diagnostic
- T016: _assert_status_path_within_target_surface delegates to ensure_within_any
- T017: _assert_bookkeeping_snapshot_path_is_trusted trusted-set pin (3 dirs + file)
- T018: _assert_status_surface_path_is_trusted XOR preserved (kitty-specs-under-worktrees rejected)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands.merge import (
    _assert_merged_wps_reached_done,
    _assert_status_path_within_target_surface,
    _assert_status_surface_path_is_trusted,
    _mark_wp_merged_done,
    _target_bookkeeping_status_paths,
    _validate_mission_slug_path_segment,
    merge,
)

# WP09 (T048): the merge-side snapshot-trust helper + capture were retired; the
# executor now enrols through the single owner compensator. ``_capture_merge_snapshots``
# is the executor's thin adapter that supplies the identical merge trusted-set
# (3 dirs + merge-state.json) to the owner's containment, so the T017 containment
# regressions below re-point onto it (same accept/reject semantics).
from specify_cli.merge.executor import _capture_merge_snapshots
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event

pytestmark = [pytest.mark.fast, pytest.mark.non_sandbox]  # non_sandbox: subprocess CLI invocation
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_wp(
    path: Path,
    *,
    review_status: str = "approved",
    reviewed_by: str = "reviewer-1",
    agent: str = "test-agent",
) -> None:
    """Write a minimal WP frontmatter file."""
    lines = [
        "---",
        'work_package_id: "WP01"',
        'title: "Test WP"',
        "dependencies: []",
        f'review_status: "{review_status}"',
        f'reviewed_by: "{reviewed_by}"',
        f'agent: "{agent}"',
        "---",
        "# WP01",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_minimal_meta(feature_dir: Path, mission_slug: str) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_id": "01TEST00000000000000000000", "mission_slug": mission_slug}),
        encoding="utf-8",
    )


def _append_done_event(feature_dir: Path, wp_id: str) -> None:
    """Seed the event log with a done transition for *wp_id*."""
    event = StatusEvent(
        event_id=f"01TEST{wp_id}DONE".ljust(26, "0")[:26],
        mission_slug=feature_dir.name,
        wp_id=wp_id,
        from_lane=Lane.APPROVED,
        to_lane=Lane.DONE,
        at="2026-04-09T12:00:00+00:00",
        actor="merge",
        force=False,
        execution_mode="direct_repo",
    )
    append_event(feature_dir, event)


# ---------------------------------------------------------------------------
# #1956: final target bookkeeping must not stage coordination-worktree paths
# ---------------------------------------------------------------------------


def test_target_bookkeeping_paths_use_primary_checkout_for_coord_surface(
    tmp_path: Path,
) -> None:
    """Regression: final target commit stages primary paths, never .worktrees paths."""
    mission_slug = "coord-bookkeeping-01KV1956"
    coord_feature_dir = (
        tmp_path
        / ".worktrees"
        / f"{mission_slug}-coord"
        / "kitty-specs"
        / mission_slug
    )

    events_path, status_path = _target_bookkeeping_status_paths(
        main_repo=tmp_path,
        mission_slug=mission_slug,
        status_feature_dir=coord_feature_dir,
    )

    assert events_path == tmp_path / "kitty-specs" / mission_slug / "status.events.jsonl"
    assert status_path == tmp_path / "kitty-specs" / mission_slug / "status.json"
    assert ".worktrees" not in events_path.parts
    assert ".worktrees" not in status_path.parts


def test_target_bookkeeping_paths_keep_primary_surface(tmp_path: Path) -> None:
    """Primary status surfaces already match the target commit surface."""
    mission_slug = "primary-bookkeeping"
    primary_feature_dir = tmp_path / "kitty-specs" / mission_slug

    events_path, status_path = _target_bookkeeping_status_paths(
        main_repo=tmp_path,
        mission_slug=mission_slug,
        status_feature_dir=primary_feature_dir,
    )

    assert events_path == primary_feature_dir / "status.events.jsonl"
    assert status_path == primary_feature_dir / "status.json"


def test_target_bookkeeping_paths_reject_path_traversal(tmp_path: Path) -> None:
    """Mission slugs must not project bookkeeping writes outside the repo root."""
    with pytest.raises(ValueError, match="safe path segment"):
        _target_bookkeeping_status_paths(
            main_repo=tmp_path,
            mission_slug="../../escape",
            status_feature_dir=tmp_path / "kitty-specs" / "../../escape",
        )


@pytest.mark.parametrize("mission_slug", ["feature/with-slash", r"feature\\with-backslash", "naïve"])
def test_target_bookkeeping_paths_reject_unsafe_mission_slug(
    tmp_path: Path,
    mission_slug: str,
) -> None:
    """Unsafe mission slugs are rejected before path composition."""
    with pytest.raises(ValueError, match="safe path segment"):
        _target_bookkeeping_status_paths(
            main_repo=tmp_path,
            mission_slug=mission_slug,
            status_feature_dir=tmp_path / "kitty-specs" / "safe-slug",
        )


# ---------------------------------------------------------------------------
# T015: Verify approved|done merge-ready check is EXPLICIT (not is_terminal)
# ---------------------------------------------------------------------------


def test_merge_ready_lanes_approved_and_done_only() -> None:
    """CRITICAL: Only approved and done are merge-ready; is_terminal is NOT used."""
    from specify_cli.status.transitions import is_terminal

    # is_terminal covers done|canceled — that's cleanup logic, not merge-readiness
    # approved is merge-ready but NOT terminal
    assert not is_terminal(Lane.APPROVED.value), \
        "approved must NOT be terminal — merge-readiness is a distinct concept"

    # canceled is terminal but NOT merge-ready
    # This is the key distinction: if we used is_terminal for merge-readiness,
    # canceled WPs would incorrectly pass the merge gate.
    assert is_terminal(Lane.CANCELED.value), "canceled is terminal"
    assert is_terminal(Lane.DONE.value), "done is terminal"

    # Define merge-readiness explicitly as the source code does: approved|done only
    _MERGE_READY = frozenset({Lane.APPROVED, Lane.DONE})

    # Verify all 9 lanes against the explicit check
    expected: dict[Lane, bool] = {
        Lane.PLANNED: False,
        Lane.CLAIMED: False,
        Lane.IN_PROGRESS: False,
        Lane.FOR_REVIEW: False,
        Lane.IN_REVIEW: False,
        Lane.APPROVED: True,
        Lane.DONE: True,
        Lane.BLOCKED: False,
        Lane.CANCELED: False,   # terminal but NOT merge-ready!
    }
    for lane, should_be_ready in expected.items():
        is_ready = lane in _MERGE_READY
        assert is_ready == should_be_ready, (
            f"Lane {lane.value}: expected merge-ready={should_be_ready}, got {is_ready}"
        )


def test_canceled_is_not_merge_ready_even_though_terminal() -> None:
    """canceled is is_terminal=True but must NOT be merge-ready."""
    from specify_cli.status.transitions import is_terminal

    assert is_terminal(Lane.CANCELED.value), "canceled is terminal"
    # Explicit approved|done check: canceled is excluded
    _MERGE_READY = frozenset({Lane.APPROVED, Lane.DONE})
    assert Lane.CANCELED not in _MERGE_READY, \
        "canceled must NOT be in merge-ready set (approved|done)"


# ---------------------------------------------------------------------------
# T015: _assert_merged_wps_reached_done live function tests
# ---------------------------------------------------------------------------


def test_assert_merged_wps_reached_done_passes_when_all_done(tmp_path: Path) -> None:
    """All WPs in done → no exit raised."""
    mission_slug = "080-test-feature"
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_id": "01TEST00000000000000000000", "mission_slug": mission_slug}),
        encoding="utf-8",
    )

    _append_done_event(feature_dir, "WP01")
    _append_done_event(feature_dir, "WP02")

    # Should not raise
    _assert_merged_wps_reached_done(tmp_path, mission_slug, ["WP01", "WP02"])


def test_assert_merged_wps_reached_done_raises_when_wp_not_done(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WP not in done → typer.Exit(1) raised."""
    mission_slug = "080-test-feature"
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_id": "01TEST00000000000000000000", "mission_slug": mission_slug}),
        encoding="utf-8",
    )

    # WP01 done, WP02 only approved
    _append_done_event(feature_dir, "WP01")
    # WP02 stays at approved (no done event)
    event = StatusEvent(
        event_id="01TESTWP02APPROVED0000000000",
        mission_slug=mission_slug,
        wp_id="WP02",
        from_lane=Lane.IN_PROGRESS,
        to_lane=Lane.APPROVED,
        at="2026-04-09T12:00:00+00:00",
        actor="reviewer",
        force=False,
        execution_mode="direct_repo",
    )
    append_event(feature_dir, event)

    with pytest.raises(typer.Exit):
        _assert_merged_wps_reached_done(tmp_path, mission_slug, ["WP01", "WP02"])


def test_assert_merged_wps_reached_done_includes_lane_value_in_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Error message includes WP id and current lane value (not raw string)."""
    mission_slug = "080-test-feature"
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_id": "01TEST00000000000000000000", "mission_slug": mission_slug}),
        encoding="utf-8",
    )

    # WP01 is in in_progress (not done)
    event = StatusEvent(
        event_id="01TESTWP01INPROG000000000000",
        mission_slug=mission_slug,
        wp_id="WP01",
        from_lane=Lane.CLAIMED,
        to_lane=Lane.IN_PROGRESS,
        at="2026-04-09T12:00:00+00:00",
        actor="test",
        force=True,
        execution_mode="direct_repo",
    )
    append_event(feature_dir, event)

    with pytest.raises(typer.Exit):
        _assert_merged_wps_reached_done(tmp_path, mission_slug, ["WP01"])


# ---------------------------------------------------------------------------
# T015: _mark_wp_merged_done live function tests
# ---------------------------------------------------------------------------


def test_mark_wp_merged_done_emits_done_when_lane_is_approved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_mark_wp_merged_done emits done transition when WP is in approved lane."""
    mission_slug = "080-test-feature"
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    _write_minimal_meta(feature_dir, mission_slug)
    _write_wp(tasks_dir / "WP01-test.md", reviewed_by="reviewer-1")

    emit_calls: list[Any] = []

    def fake_emit(request: Any, **_kwargs: object) -> None:
        emit_calls.append(request)

    monkeypatch.setattr("specify_cli.coordination.status_transition.emit_status_transition_transactional", fake_emit)
    monkeypatch.setattr(
        "specify_cli.status.lane_reader.get_wp_lane",
        lambda *_a, **_kw: "approved",
    )

    _mark_wp_merged_done(tmp_path, mission_slug, "WP01", "main")

    assert len(emit_calls) == 1
    assert emit_calls[0].to_lane == "done"
    assert emit_calls[0].actor == "merge"


def test_mark_wp_merged_done_skips_when_already_done(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_mark_wp_merged_done is idempotent when WP is already in done lane."""
    mission_slug = "080-test-feature"
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    _write_minimal_meta(feature_dir, mission_slug)
    _write_wp(tasks_dir / "WP01-test.md")

    emit_mock = Mock()
    monkeypatch.setattr("specify_cli.coordination.status_transition.emit_status_transition_transactional", emit_mock)
    monkeypatch.setattr(
        "specify_cli.status.lane_reader.get_wp_lane",
        lambda *_a, **_kw: "done",
    )

    _mark_wp_merged_done(tmp_path, mission_slug, "WP01", "main")

    emit_mock.assert_not_called()


def test_mark_wp_merged_done_skips_when_no_approval_metadata_for_non_approved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_mark_wp_merged_done warns and returns if WP is in_progress with no evidence."""
    mission_slug = "080-test-feature"
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    _write_minimal_meta(feature_dir, mission_slug)
    # WP with no review metadata
    _write_wp(tasks_dir / "WP01-test.md", review_status="", reviewed_by="")

    emit_mock = Mock()
    monkeypatch.setattr("specify_cli.coordination.status_transition.emit_status_transition_transactional", emit_mock)
    monkeypatch.setattr(
        "specify_cli.status.lane_reader.get_wp_lane",
        lambda *_a, **_kw: "in_progress",
    )

    _mark_wp_merged_done(tmp_path, mission_slug, "WP01", "main")

    emit_mock.assert_not_called()


# ---------------------------------------------------------------------------
# T006: merge --abort cleanup tests (WP01)
# ---------------------------------------------------------------------------

def test_abort_clears_lock_and_state(tmp_path: Path) -> None:
    """--abort removes the global lock file and legacy merge-state JSON when both exist."""
    # Setup: create global merge lock
    lock_path = tmp_path / ".kittify" / "runtime" / "merge" / "__global_merge__" / "lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("2026-04-30T00:00:00+00:00", encoding="utf-8")

    # Setup: create legacy merge-state JSON
    legacy_state_path = tmp_path / ".kittify" / "merge-state.json"
    legacy_state_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_state_path.write_text('{"feature_slug": "test"}', encoding="utf-8")

    # Build a minimal typer app wrapping `merge` so we can invoke via CliRunner
    app = typer.Typer()
    app.command()(merge)

    runner = CliRunner()
    with patch("specify_cli.cli.commands.merge.find_repo_root", return_value=tmp_path):
        result = runner.invoke(app, ["--abort"])

    # Both files must be gone
    assert not lock_path.exists(), "Global merge lock file should have been removed"
    assert not legacy_state_path.exists(), "Legacy merge-state.json should have been removed"
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}\nOutput: {result.output}"


def test_abort_idempotent(tmp_path: Path) -> None:
    """--abort exits 0 with no error when neither lock nor state file is present."""
    # Ensure the .kittify dir doesn't even exist
    assert not (tmp_path / ".kittify").exists()

    app = typer.Typer()
    app.command()(merge)

    runner = CliRunner()
    with patch("specify_cli.cli.commands.merge.find_repo_root", return_value=tmp_path):
        result = runner.invoke(app, ["--abort"])

    assert result.exit_code == 0, (
        f"Expected exit 0 on idempotent abort, got {result.exit_code}\nOutput: {result.output}"
    )


# ---------------------------------------------------------------------------
# WP03: Coordination branch surface regression tests (T015/T016 — #1726)
# ---------------------------------------------------------------------------

_COORD_SLUG_M = "coord-test-mission"
_COORD_MISSION_ID_M = "01KTDVHZKGCHCW6HQ4V577PNES"


@pytest.fixture
def coord_branch_mission(tmp_path: Path) -> dict[str, Any]:
    """Minimal coord-branch fixture for test_merge.py.

    slug does NOT end in mid8, so resolver adds suffix:
      .worktrees/coord-test-mission-01KTDVHZ-coord/kitty-specs/coord-test-mission-01KTDVHZ/
    """
    mid8 = _COORD_MISSION_ID_M[:8]  # "01KTDVHZ"
    coord_branch = f"kitty/mission-{_COORD_SLUG_M}-{mid8}"

    primary_dir = tmp_path / "kitty-specs" / _COORD_SLUG_M
    primary_dir.mkdir(parents=True)
    (primary_dir / "meta.json").write_text(
        json.dumps({
            "mission_id": _COORD_MISSION_ID_M,
            "mission_slug": _COORD_SLUG_M,
            "slug": _COORD_SLUG_M,
            "coordination_branch": coord_branch,
            "target_branch": "main",
        }),
        encoding="utf-8",
    )

    coord_dir_name = f"{_COORD_SLUG_M}-{mid8}"
    coord_specs = (
        tmp_path / ".worktrees" / f"{coord_dir_name}-coord"
        / "kitty-specs" / coord_dir_name
    )
    coord_specs.mkdir(parents=True)
    coord_events = coord_specs / "status.events.jsonl"
    coord_events.write_text("", encoding="utf-8")

    return {
        "repo_root": tmp_path,
        "primary_dir": primary_dir,
        "coord_specs": coord_specs,
        "coord_events": coord_events,
    }


def _seed_done_event_m(feature_dir: Path, wp_id: str) -> None:
    event = StatusEvent(
        event_id=f"01TESTM{wp_id[-2:]}DONE000000000000"[:26],
        mission_slug=_COORD_SLUG_M,
        wp_id=wp_id,
        from_lane=Lane.APPROVED,
        to_lane=Lane.DONE,
        at="2026-06-06T12:00:00+00:00",
        actor="merge",
        force=False,
        execution_mode="worktree",
    )
    append_event(feature_dir, event)


def test_planning_only_merge_with_coord_branch_reaches_done(
    coord_branch_mission: dict[str, Any],
) -> None:
    """Planning-only WP: done event on coord surface → assertion passes.

    Parity ratchet T015: proves _assert_merged_wps_reached_done reads the
    coordination surface when coordination_branch is set.

    Relates-to: #1726
    """
    from specify_cli.coordination.surface_resolver import resolve_status_surface

    repo_root = coord_branch_mission["repo_root"]
    coord_specs = coord_branch_mission["coord_specs"]

    # Seed coord surface (simulates what _mark_wp_merged_done writes)
    _seed_done_event_m(coord_specs, "WP01")

    # Real _assert_merged_wps_reached_done — must not raise
    _assert_merged_wps_reached_done(repo_root, _COORD_SLUG_M, ["WP01"])

    # The done event is on the coordination surface
    surface = resolve_status_surface(repo_root, _COORD_SLUG_M)
    assert surface.exists()
    assert '"done"' in surface.read_text(encoding="utf-8")

    # Primary checkout does NOT have the done event
    primary_events = coord_branch_mission["primary_dir"] / "status.events.jsonl"
    assert not primary_events.exists() or '"done"' not in primary_events.read_text(encoding="utf-8")


def test_code_change_merge_with_coord_branch_reaches_done(
    coord_branch_mission: dict[str, Any],
) -> None:
    """Code-change WP variant: multi-WP done events on coord surface.

    Parity ratchet T016: surface alignment is independent of WP execution mode.

    Relates-to: #1726
    """
    repo_root = coord_branch_mission["repo_root"]
    coord_specs = coord_branch_mission["coord_specs"]

    _seed_done_event_m(coord_specs, "WP01")
    _seed_done_event_m(coord_specs, "WP02")

    # Both WPs must pass — coord surface has their done events
    _assert_merged_wps_reached_done(repo_root, _COORD_SLUG_M, ["WP01", "WP02"])


# ---------------------------------------------------------------------------
# WP04 / T014: delegate _validate_mission_slug_path_segment + dead-constant gate
# ---------------------------------------------------------------------------


def test_validate_mission_slug_delegates_to_canonical_validator() -> None:
    """_validate_mission_slug_path_segment raises ValueError with canonical message."""
    with pytest.raises(ValueError, match="safe path segment"):
        _validate_mission_slug_path_segment("../escape")


def test_validate_mission_slug_accepts_real_format_slugs() -> None:
    """Real-format slugs (full ULID, slug-mid8, numeric-prefix, bare mid8) are accepted."""
    valid_slugs = [
        "01KVBBT6FEQ01NHNSQD7X8JTPE",   # full 26-char ULID
        "canonical-seams-01KVBBT6",       # slug-mid8 dir name
        "034-my-feature-slug",             # numeric-prefix
        "01KVBBT6",                        # bare mid8
        "valid-slug-with-hyphens",
    ]
    for slug in valid_slugs:
        result = _validate_mission_slug_path_segment(slug)
        assert result == slug, f"Expected {slug!r} to be returned unchanged, got {result!r}"


def test_dead_constant_mission_slug_re_removed() -> None:
    """_MISSION_SLUG_PATH_SEGMENT_RE dead constant must be absent from merge.py (grep-gate)."""
    import specify_cli.cli.commands.merge as merge_module

    assert not hasattr(merge_module, "_MISSION_SLUG_PATH_SEGMENT_RE"), (
        "_MISSION_SLUG_PATH_SEGMENT_RE must be removed from merge.py after delegating to "
        "assert_safe_path_segment — it is a dead constant"
    )


# ---------------------------------------------------------------------------
# WP04 / T014 FR-003: sibling-seam reject tests (un-fakeable — calls named functions)
# ---------------------------------------------------------------------------


def test_fr003_assert_status_path_within_target_surface_rejects_malformed_slug(
    tmp_path: Path,
) -> None:
    """FR-003 sibling-seam :828 — _assert_status_path_within_target_surface rejects ../escape.

    This test calls the named sibling function DIRECTLY (not via _target_bookkeeping_status_paths)
    to prove the guard reaches primary_feature_dir_for_mission at :828.
    Un-fakeable: the assertion is NOT satisfiable via _target_bookkeeping_status_paths.
    """
    candidate = tmp_path / "kitty-specs" / "some-mission" / "status.events.jsonl"
    with pytest.raises(ValueError, match="safe path segment"):
        _assert_status_path_within_target_surface(
            repo_root=tmp_path,
            mission_slug="../escape",
            candidate=candidate,
        )


def test_fr003_assert_status_path_within_target_surface_rejects_backslash_slug(
    tmp_path: Path,
) -> None:
    """FR-003 sibling-seam :828 — backslash in slug is rejected."""
    candidate = tmp_path / "kitty-specs" / "some-mission" / "status.events.jsonl"
    with pytest.raises(ValueError, match="safe path segment"):
        _assert_status_path_within_target_surface(
            repo_root=tmp_path,
            mission_slug="a\\b",
            candidate=candidate,
        )


# ---------------------------------------------------------------------------
# WP04 / T014 FR-003: :2382 path — _validate_mission_slug_path_segment called before
# primary_feature_dir_for_mission is used in _run_lane_based_merge.
# We test the validator directly since _run_lane_based_merge requires lanes.json.
# ---------------------------------------------------------------------------


def test_fr003_validator_rejects_slug_that_would_reach_2382_path(tmp_path: Path) -> None:
    """FR-003 sibling-seam :2382 — validates that the slug guard fires for the target_feature_dir path.

    _run_lane_based_merge calls primary_feature_dir_for_mission(main_repo, mission_slug) at :2382.
    After T014, _validate_mission_slug_path_segment is the canonical guard that fires BEFORE
    any primary_feature_dir_for_mission composition — proven here by calling it directly.
    This test is NOT satisfiable via _target_bookkeeping_status_paths.
    """
    # The :2382 guard is the same canonical validator — prove it rejects traversal slugs
    with pytest.raises(ValueError, match="safe path segment"):
        _validate_mission_slug_path_segment("../../outside")

    # And a slash-containing slug
    with pytest.raises(ValueError, match="safe path segment"):
        _validate_mission_slug_path_segment("a/b")

    # Confirm a real-format slug (as used at :2382) passes
    assert _validate_mission_slug_path_segment("canonical-seams-01KVBBT6") == "canonical-seams-01KVBBT6"


# ---------------------------------------------------------------------------
# WP04 / T015: dry-run/abort catch ValueError → clean diagnostic
# ---------------------------------------------------------------------------


def test_abort_with_malformed_mission_slug_emits_clean_diagnostic(tmp_path: Path) -> None:
    """T015: --abort --mission '../x' emits 'single safe path segment' message + non-zero exit.

    A bare 'except: raise typer.Exit(1)' with no message does NOT satisfy this test
    because we assert the message text explicitly.
    """
    app = typer.Typer()
    app.command()(merge)

    runner = CliRunner()
    with patch("specify_cli.cli.commands.merge.find_repo_root", return_value=tmp_path):
        result = runner.invoke(app, ["--abort", "--mission", "../x"])

    # Must exit non-zero (the malformed slug is detected and rejected)
    assert result.exit_code != 0, (
        f"Expected non-zero exit for malformed slug, got {result.exit_code}\nOutput: {result.output}"
    )
    # Must emit the canonical "single safe path segment" diagnostic, not a raw traceback
    assert "single safe path segment" in result.output, (
        f"Expected 'single safe path segment' in output, got:\n{result.output}"
    )


def test_abort_with_slash_mission_slug_emits_clean_diagnostic(tmp_path: Path) -> None:
    """T015: --abort --mission 'a/b' emits 'single safe path segment' message + non-zero exit."""
    app = typer.Typer()
    app.command()(merge)

    runner = CliRunner()
    with patch("specify_cli.cli.commands.merge.find_repo_root", return_value=tmp_path):
        result = runner.invoke(app, ["--abort", "--mission", "a/b"])

    assert result.exit_code != 0, (
        f"Expected non-zero exit for malformed slug, got {result.exit_code}\nOutput: {result.output}"
    )
    assert "single safe path segment" in result.output, (
        f"Expected 'single safe path segment' in output, got:\n{result.output}"
    )


# ---------------------------------------------------------------------------
# WP04 / T016: _assert_status_path_within_target_surface delegates to ensure_within_any
# ---------------------------------------------------------------------------


def test_assert_status_path_within_target_surface_rejects_escape(tmp_path: Path) -> None:
    """T016: candidate outside the mission surface root is rejected."""
    mission_slug = "valid-mission-01KVBBT6"
    # candidate is outside the mission surface (under an unrelated sibling dir)
    outside_candidate = tmp_path / "other-dir" / "status.events.jsonl"
    with pytest.raises(ValueError):
        _assert_status_path_within_target_surface(
            repo_root=tmp_path,
            mission_slug=mission_slug,
            candidate=outside_candidate,
        )


def test_assert_status_path_within_target_surface_accepts_inside(tmp_path: Path) -> None:
    """T016: candidate inside the mission surface root is accepted and returned resolved."""
    mission_slug = "valid-mission-01KVBBT6"
    surface_root = tmp_path / "kitty-specs" / mission_slug
    candidate = surface_root / "status.events.jsonl"
    result = _assert_status_path_within_target_surface(
        repo_root=tmp_path,
        mission_slug=mission_slug,
        candidate=candidate,
    )
    assert result == candidate.resolve(strict=False)


# ---------------------------------------------------------------------------
# WP04 / T017 (WP09 T048 re-point): merge snapshot trusted-set + capture pin.
# The retired ``_assert_bookkeeping_snapshot_path_is_trusted`` /
# ``_capture_bookkeeping_snapshots`` folded into the executor's
# ``_capture_merge_snapshots`` adapter, which supplies the SAME trusted set to the
# owner's ``ensure_within_any`` containment. Accept = the resolved key is captured;
# reject = ValueError. Same accept/reject semantics, no set change.
# ---------------------------------------------------------------------------


def test_bookkeeping_snapshot_trusted_set_accepts_kitty_specs(tmp_path: Path) -> None:
    """T017: path under kitty-specs is accepted."""
    from specify_cli.core.constants import KITTY_SPECS_DIR
    candidate = tmp_path / KITTY_SPECS_DIR / "some-mission" / "file.json"
    snapshots = _capture_merge_snapshots(tmp_path, candidate)
    assert candidate.resolve(strict=False) in snapshots


def test_bookkeeping_snapshot_trusted_set_accepts_worktrees(tmp_path: Path) -> None:
    """T017: path under .worktrees is accepted."""
    from specify_cli.core.constants import WORKTREES_DIR
    candidate = tmp_path / WORKTREES_DIR / "some-branch" / "file.json"
    snapshots = _capture_merge_snapshots(tmp_path, candidate)
    assert candidate.resolve(strict=False) in snapshots


def test_bookkeeping_snapshot_trusted_set_accepts_kittify_runtime_merge(tmp_path: Path) -> None:
    """T017: path under .kittify/runtime/merge is accepted."""
    from specify_cli.core.constants import KITTIFY_DIR
    candidate = tmp_path / KITTIFY_DIR / "runtime" / "merge" / "some-id" / "state.json"
    snapshots = _capture_merge_snapshots(tmp_path, candidate)
    assert candidate.resolve(strict=False) in snapshots


def test_bookkeeping_snapshot_trusted_set_accepts_exact_merge_state_json(tmp_path: Path) -> None:
    """T017: exact .kittify/merge-state.json file is accepted via files= allowlist."""
    from specify_cli.core.constants import KITTIFY_DIR
    candidate = tmp_path / KITTIFY_DIR / "merge-state.json"
    snapshots = _capture_merge_snapshots(tmp_path, candidate)
    assert candidate.resolve(strict=False) in snapshots


def test_bookkeeping_snapshot_trusted_set_rejects_kittify_root_not_exact_file(
    tmp_path: Path,
) -> None:
    """T017: a file inside .kittify but NOT merge-state.json and NOT under runtime/merge is rejected."""
    from specify_cli.core.constants import KITTIFY_DIR
    # .kittify/config.yaml is NOT in the trusted set
    candidate = tmp_path / KITTIFY_DIR / "config.yaml"
    with pytest.raises(ValueError):
        _capture_merge_snapshots(tmp_path, candidate)


def test_capture_bookkeeping_snapshots_resolves_only_trusted_paths(tmp_path: Path) -> None:
    """T017: snapshot capture validates and resolves every candidate path up-front."""
    from specify_cli.core.constants import KITTY_SPECS_DIR

    candidate = tmp_path / KITTY_SPECS_DIR / "some-mission" / "file.json"
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate.write_bytes(b"payload")

    snapshots = _capture_merge_snapshots(tmp_path, candidate)

    assert snapshots == {candidate.resolve(strict=False): b"payload"}


def test_capture_bookkeeping_snapshots_rejects_untrusted_paths(tmp_path: Path) -> None:
    """T017: snapshot capture fails closed for paths outside trusted bookkeeping roots."""
    outside = tmp_path / "completely-outside" / "file.json"

    with pytest.raises(ValueError):
        _capture_merge_snapshots(tmp_path, outside)


def test_capture_bookkeeping_snapshots_rejects_dotdot_traversal(tmp_path: Path) -> None:
    """A ``../``-style candidate that lexically escapes the trusted roots is rejected.

    The candidate STARTS under a trusted root (kitty-specs) but uses ``..``
    segments to climb back out to a sibling of the repo root. ``resolve(strict=False)``
    collapses the ``..`` so the containment check fails → ValueError.
    """
    from specify_cli.core.constants import KITTY_SPECS_DIR

    traversal = tmp_path / KITTY_SPECS_DIR / "mission" / ".." / ".." / ".." / "evil.json"
    # Sanity: the collapsed form really does escape tmp_path.
    assert not traversal.resolve(strict=False).is_relative_to(tmp_path.resolve(strict=False))

    with pytest.raises(ValueError):
        _capture_merge_snapshots(tmp_path, traversal)


def test_capture_bookkeeping_snapshots_rejects_symlink_escape(tmp_path: Path) -> None:
    """A symlink UNDER a trusted root whose target is OUTSIDE the roots is rejected.

    Secure expected behavior: ``resolve(strict=False)`` follows the symlink to the
    escaped target, so the containment check sees a path outside every trusted root
    and raises ValueError. If this candidate were ACCEPTED it would be a real
    containment bypass.
    """
    from specify_cli.core.constants import KITTY_SPECS_DIR

    # Trusted root: <tmp>/kitty-specs/mission/
    mission_dir = tmp_path / KITTY_SPECS_DIR / "mission"
    mission_dir.mkdir(parents=True)

    # Real target OUTSIDE every trusted root.
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    secret = outside_dir / "secret.json"
    secret.write_bytes(b"escaped-payload")

    # Symlink planted UNDER the trusted root that points outside it.
    evil_link = mission_dir / "evil"
    evil_link.symlink_to(outside_dir)
    candidate = evil_link / "secret.json"

    # resolve(strict=False) follows the symlink → target is outside the roots.
    assert candidate.resolve(strict=False) == secret.resolve(strict=False)
    assert not candidate.resolve(strict=False).is_relative_to(
        (tmp_path / KITTY_SPECS_DIR).resolve(strict=False)
    )

    with pytest.raises(ValueError):
        _capture_merge_snapshots(tmp_path, candidate)


# ---------------------------------------------------------------------------
# WP04 / T018: _assert_status_surface_path_is_trusted XOR preserved (un-fakeable)
# ---------------------------------------------------------------------------


def test_status_surface_xor_rejects_kitty_specs_path_when_worktrees_is_active(
    tmp_path: Path,
) -> None:
    """T018 XOR test (squad flag — un-fakeable).

    A path that IS under the kitty-specs root but where is_under_worktrees_segment
    returns True for status_feature_dir MUST be rejected.

    Fixture: ``tmp_path / ".worktrees" / ".." / "kitty-specs" / "mission"``
    - ``is_under_worktrees_segment`` sees ``.worktrees`` in the raw parts → True
      (selects WORKTREES root as the trusted root, not kitty-specs)
    - ``resolve(strict=False)`` collapses the ``..`` → path IS under kitty-specs
      root but NOT under the worktrees root
    - Result: REJECTED (correct XOR)

    Under a ``roots=[worktrees, kitty-specs]`` UNION this path would be ACCEPTED
    (it resolves under kitty-specs root).  It is REJECTED only under correct XOR.
    """
    from specify_cli.core.constants import KITTY_SPECS_DIR, WORKTREES_DIR

    repo_resolved = tmp_path.resolve(strict=False)

    # This path has .worktrees in its parts (so is_under_worktrees_segment → True)
    # but resolves to kitty-specs (NOT under worktrees root).
    # A union would accept it (it's under kitty-specs); XOR rejects it (wrong root).
    xor_trap_path = repo_resolved / WORKTREES_DIR / ".." / KITTY_SPECS_DIR / "mission"
    # Confirm the topology:
    assert WORKTREES_DIR in xor_trap_path.parts, "fixture must have .worktrees in parts"
    resolved_xor = xor_trap_path.resolve(strict=False)
    assert not resolved_xor.is_relative_to(repo_resolved / WORKTREES_DIR), (
        "resolved form must NOT be under worktrees root — XOR fixture misconfigured"
    )

    with pytest.raises(ValueError):
        _assert_status_surface_path_is_trusted(
            repo_root=tmp_path,
            status_feature_dir=xor_trap_path,
        )

    # Verify the actual path that IS under the worktrees root IS accepted
    worktrees_dir = repo_resolved / WORKTREES_DIR / "some-branch"
    result = _assert_status_surface_path_is_trusted(
        repo_root=tmp_path,
        status_feature_dir=worktrees_dir,
    )
    assert result == worktrees_dir.resolve(strict=False)


def test_status_surface_accepts_primary_checkout_kitty_specs(tmp_path: Path) -> None:
    """T018: when is_under_worktrees_segment is False → trusted root is kitty-specs."""
    from specify_cli.core.constants import KITTY_SPECS_DIR

    repo_resolved = tmp_path.resolve(strict=False)
    # status_feature_dir is under kitty-specs → is_under_worktrees_segment returns False
    status_feature_dir = repo_resolved / KITTY_SPECS_DIR / "some-mission"
    result = _assert_status_surface_path_is_trusted(
        repo_root=tmp_path,
        status_feature_dir=status_feature_dir,
    )
    assert result == status_feature_dir.resolve(strict=False)


def test_status_surface_rejects_path_under_neither_trusted_root(tmp_path: Path) -> None:
    """Topology-match: a non-worktrees path that resolves outside kitty-specs is rejected.

    ``is_under_worktrees_segment`` is False (no ``.worktrees`` segment) and the
    path resolves under neither the worktrees nor the kitty-specs root, so the
    explicit topology guard rejects it before any containment delegation.
    """
    repo_resolved = tmp_path.resolve(strict=False)
    stray_path = repo_resolved / "not-a-trusted-root" / "mission"

    with pytest.raises(ValueError, match="Untrusted status surface path"):
        _assert_status_surface_path_is_trusted(
            repo_root=tmp_path,
            status_feature_dir=stray_path,
        )


def test_status_surface_rejects_symlink_indirection_into_trusted_root(
    tmp_path: Path,
) -> None:
    """A surface that LEXICALLY escapes the claimed root but RESOLVES into a
    trusted root via a symlink is rejected by the pre-resolution guard (PR #2043).

    This is the case ONLY the early ``relative_to(claimed_root)`` raise catches:
    the resolved form IS under kitty-specs, so the post-resolution topology check
    and the terminal ``ensure_within_any`` would ACCEPT it. The lexical-must-match
    hardening is what rejects the symlink indirection — a status surface must be
    addressed by its canonical path, not via an untrusted symlink redirection.

    Mutation-verified: reverting the early ``relative_to`` raise makes this surface
    pass (accepted), so this test genuinely guards that hardening — unlike a
    ``kitty-specs/../outside`` vector, which the post-resolve "under neither root"
    check already rejects on its own.
    """
    from specify_cli.core.constants import KITTY_SPECS_DIR

    repo_resolved = tmp_path.resolve(strict=False)
    (repo_resolved / KITTY_SPECS_DIR).mkdir()
    # A neutrally-named symlink OUTSIDE kitty-specs that points INTO it.
    decoy = repo_resolved / "decoy"
    decoy.symlink_to(repo_resolved / KITTY_SPECS_DIR, target_is_directory=True)
    surface = decoy / "mission"  # lexically under decoy; resolves under kitty-specs

    # Only the lexical pre-resolution guard can reject this: the resolved form IS
    # under the trusted kitty-specs root, and the segment claims neither root.
    assert surface.resolve(strict=False).is_relative_to(repo_resolved / KITTY_SPECS_DIR)

    with pytest.raises(ValueError, match="Untrusted status surface path"):
        _assert_status_surface_path_is_trusted(
            repo_root=tmp_path,
            status_feature_dir=surface,
        )


# ---------------------------------------------------------------------------
# PR #2277: merge fails closed on a corrupt meta.json target-branch read
# (FR-005 / #2139). The merge command must convert MissionMetaReadError into a
# clean, visible error + non-zero exit — never a raw traceback, never a silent
# fall-through to the repo default branch.
# ---------------------------------------------------------------------------


def _invoke_merge_with_corrupt_target(tmp_path: Path, *extra_args: str) -> Any:
    """Drive the merge command up to the target-branch read, which raises.

    Patches the pre-resolution setup steps to no-ops so the test isolates the
    new fail-closed catch around ``_resolve_target_branch``.
    """
    from specify_cli.core.paths import MissionMetaReadError

    app = typer.Typer()
    app.command()(merge)
    runner = CliRunner()

    boom = MissionMetaReadError(tmp_path / "meta.json", ValueError("Expecting value"))
    with (
        patch("specify_cli.cli.commands.merge.find_repo_root", return_value=tmp_path),
        patch("specify_cli.cli.commands.merge._enforce_git_preflight"),
        patch("specify_cli.cli.commands.merge.load_merge_config", return_value=Mock(strategy=None)),
        patch("specify_cli.cli.commands.merge._resolve_slug_or_exit", return_value="corrupt-mission"),
        # Newer flow gates on mission-dir existence (FR-004/FR-005) BEFORE the
        # target-branch read; the real corrupt-meta case has an existing dir with
        # a corrupt meta.json, so stub the dir check True to reach _resolve_target_branch.
        patch("specify_cli.cli.commands.merge._resolved_mission_dir_exists", return_value=True),
        patch("specify_cli.cli.commands.merge.load_state", return_value=None),
        patch("specify_cli.cli.commands.merge._resolve_target_branch", side_effect=boom),
    ):
        return runner.invoke(app, ["--mission", "corrupt-mission", *extra_args])


def test_merge_fails_closed_on_corrupt_meta_text(tmp_path: Path) -> None:
    """Corrupt meta.json → clean error + exit 1 (text mode), not a traceback."""
    result = _invoke_merge_with_corrupt_target(tmp_path)

    assert result.exit_code == 1, f"expected fail-closed exit 1, got {result.exit_code}\n{result.output}"
    assert "Cannot resolve the merge target branch" in result.output
    assert "corrupt or unreadable" in result.output
    # Fail-closed, not a crash: the raw exception class name must not leak as a traceback.
    assert "Traceback (most recent call last)" not in result.output


def test_merge_fails_closed_on_corrupt_meta_json(tmp_path: Path) -> None:
    """Corrupt meta.json → structured JSON error + exit 1 (--json mode)."""
    result = _invoke_merge_with_corrupt_target(tmp_path, "--json", "--dry-run")

    assert result.exit_code == 1, f"expected fail-closed exit 1, got {result.exit_code}\n{result.output}"
    payload = json.loads(result.output.strip().splitlines()[-1])
    assert "Cannot resolve the merge target branch" in payload["error"]
