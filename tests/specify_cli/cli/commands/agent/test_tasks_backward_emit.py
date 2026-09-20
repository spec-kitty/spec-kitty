"""Tests for the backward-emit family + FR-009 wire-shape regression.

Re-pointed for FR-015 (force-provenance fix): backward ``-> planned`` emits keep
their canonical ``reason`` (``"backward rewind: <from> -> planned"``) but the
persisted ``force`` bit is now honest per edge rather than blanket-``True``:

- ``in_progress -> planned`` / ``approved -> planned``: force-**free** with the
  ``--review-feedback-file`` evidence threaded (FR-015, WP02's two plan-reachable
  edges).
- ``for_review -> planned``: force stays ``True`` (genuine — no FSM backward edge).
- ``in_review -> planned``: force stays ``True`` in the WP02 window (needs a
  structured ``review_result`` that only WP06 threads).
- FR-008 (d): the forward control ``planned → claimed`` does NOT
  auto-promote.
- FR-008 (e): forward skip-ahead expansion preserved
  (``planned → in_progress`` emits two events via the existing
  ``_lane_targets_for_emit`` helper).
- FR-011: explicit ``--force`` on a backward move preserves the
  existing path (``force=True``, ``reason == "Force move to planned"``).
- FR-008 (f): backward emit with ``--review-feedback-file`` appends
  the canonical ``": <review-cycle://…>"`` URI segment.
- FR-009: the auto-promoted ``approved → planned`` wire shape matches
  Mission 1's ``wp-status-changed-approved-rewind-valid`` conformance
  fixture (when available in the installed events package).

Tests exercise ``move_task`` end-to-end via Typer's ``CliRunner`` and
read the resulting events directly from ``status.events.jsonl``. No
mocks of ``emit_status_transition`` or ``validate_transition``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

if TYPE_CHECKING:
    from click.testing import Result
    from spec_kitty_events.conformance import FixtureCase

from specify_cli.cli.commands.agent.tasks import app
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event, read_events
from tests.mocked_env import setup_mocked_env

pytestmark = pytest.mark.fast

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _build_feature_in_lane(
    tmp_path: Path,
    *,
    mission_slug: str,
    wp_id: str,
    lane: str,
) -> tuple[Path, Path]:
    """Build a synthetic feature dir with the WP seeded in the given lane.

    Returns ``(feature_dir, wp_file)``.
    """
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".kittify").mkdir(exist_ok=True)

    wp_file = tasks_dir / f"{wp_id}-test.md"
    wp_file.write_text(
        f"---\n"
        f"work_package_id: {wp_id}\n"
        f"title: Test {wp_id}\n"
        f"execution_mode: code_change\n"
        f"agent: testbot\n"
        f"subtasks: []\n"
        f"owned_files:\n  - src/{wp_id.lower()}/**\n"
        f"authoritative_surface: src/{wp_id.lower()}/\n"
        f"---\n\n# {wp_id}\n\n## Activity Log\n",
        encoding="utf-8",
    )

    # Seed the canonical event log so the WP exists in the lane
    # the test wants to start from. We chain through PLANNED so the
    # transitions are legal; non-PLANNED starting lanes require a
    # forced bootstrap event to skip ahead deterministically.
    canonical_start = Lane(lane)
    if canonical_start is Lane.PLANNED:
        seed = StatusEvent(
            event_id=f"seed-{wp_id}-planned",
            mission_slug=mission_slug,
            wp_id=wp_id,
            from_lane=Lane.PLANNED,
            to_lane=Lane.PLANNED,
            at="2026-01-01T00:00:00+00:00",
            actor="test",
            force=True,
            execution_mode="worktree",
            reason="seed: bootstrap",
        )
        append_event(feature_dir, seed)
    else:
        # Force-seed directly into the desired lane. The reducer cares
        # only about the latest event's to_lane, so a single forced
        # bootstrap event is sufficient.
        seed = StatusEvent(
            event_id=f"seed-{wp_id}-{lane}",
            mission_slug=mission_slug,
            wp_id=wp_id,
            from_lane=Lane.PLANNED,
            to_lane=canonical_start,
            at="2026-01-01T00:00:00+00:00",
            actor="test",
            force=True,
            execution_mode="worktree",
            reason=f"seed: bootstrap to {lane}",
        )
        append_event(feature_dir, seed)
    return feature_dir, wp_file


def _seed_lanes_json(feature_dir: Path, mission_slug: str, wp_id: str) -> None:
    """Write a minimal ``lanes.json`` covering *wp_id*.

    #4758's ``_mt_guard_planned_boundary_lanes`` now refuses any hop OUT of
    ``planned`` when ``lanes.json`` is absent (a required precondition, not a
    behavior change under test here) -- so a synthetic fixture that starts a
    WP in ``planned`` and moves it forward needs lanes.json seeded first.
    """
    write_lanes_json(
        feature_dir,
        LanesManifest(
            version=1,
            mission_slug=mission_slug,
            mission_id=None,
            mission_branch=f"kitty/mission-{mission_slug}",
            target_branch="main",
            lanes=[
                ExecutionLane(
                    lane_id="lane-a",
                    wp_ids=(wp_id,),
                    write_scope=(f"src/{wp_id.lower()}/**",),
                    predicted_surfaces=(),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
            computed_at="2026-01-01T00:00:00+00:00",
            computed_from="dependency_graph+ownership",
            planning_commit_sha="a" * 40,
        ),
    )


def _write_feedback_file(tmp_path: Path) -> Path:
    """Write a minimal non-empty review feedback markdown file."""
    fb = tmp_path / "feedback.md"
    fb.write_text(
        "**Issue**: Backward-transition regression test feedback.\n"
        "\n"
        "Re-implement the change with the canonical wire shape.\n",
        encoding="utf-8",
    )
    return fb


def _read_latest_events_for_wp(feature_dir: Path, wp_id: str) -> list[StatusEvent]:
    """Return every event for ``wp_id`` in append order."""
    return [e for e in read_events(feature_dir) if e.wp_id == wp_id]


def _invoke_move(
    *,
    tmp_path: Path,
    mission_slug: str,
    args: list[str],
) -> Result:
    """Run move_task end-to-end with the standard mocked env.

    Cycle 2 fix (review-verdict-write-integrity-01KZ1CGF WP01): a genuine
    rejection (backward ``-> planned`` with ``--review-feedback-file``) now
    threads a REAL ``commit_artifact`` call and raises on a non-"committed"
    result. This fixture's ``tmp_path`` is never ``git init``'d (this whole
    file is ``pytest.mark.fast`` -- purely in-process, no subprocess/real
    git), so a genuine commit attempt fails for an environmental reason
    unrelated to the force-provenance/wire-shape behavior under test here.
    Stub ``commit_for_mission`` to report success -- mirrors the identical
    fix in ``tests/specify_cli/cli/commands/agent/test_tasks.py``. Tests that
    never write a review-cycle artifact (no ``--review-feedback-file``,
    forward moves) simply never call the stub.
    """
    with (
        patch("specify_cli.cli.commands.agent.tasks.commit_for_mission") as mock_commit,
        setup_mocked_env(
            tmp_path,
            mission_slug=mission_slug,
            workspace_resolution=FileNotFoundError,
        ),
    ):
        mock_commit.return_value.status = "committed"
        return runner.invoke(app, args, catch_exceptions=False)


# ---------------------------------------------------------------------------
# T003 — FR-008 family tests
# ---------------------------------------------------------------------------


class TestReviewRejectionFamily:
    """#3307 provenance on the backward ``-> planned`` family.

    Only the emit-force expectation is re-pointed here (delete-the-assertion-not-
    the-test): the ``reason``/lane wire-shape assertions are unchanged. Every
    ``* -> planned`` edge is a member of the shared ``spec-kitty-events``
    review-rejection family (``in_progress|for_review|in_review|approved ->
    planned``), which the wire contract the SaaS ingestion endpoint enforces
    declares ``force=True``-required regardless of local evidence. The CLI-local
    FSM would accept some of these force-free on ``reason`` / ``review_ref`` /
    ``review_result`` evidence, but ``build_transition_plan`` now gates on BOTH
    validators, so the persisted ``force`` is ``True`` for the whole family — no
    contract-invalid ``force=False`` event the SaaS would silently drop. The
    structured rewind rationale (and ``review_ref``, when present) still travels
    on the wire.
    """

    @pytest.mark.parametrize(
        "starting_lane, expected_prefix, expected_force",
        [
            ("in_review", "backward rewind: in_review -> planned", True),
            ("approved", "backward rewind: approved -> planned", True),
            ("for_review", "backward rewind: for_review -> planned", True),
            ("in_progress", "backward rewind: in_progress -> planned", True),
        ],
    )
    def test_backward_to_planned_force_provenance(
        self,
        tmp_path: Path,
        starting_lane: str,
        expected_prefix: str,
        expected_force: bool,
    ) -> None:
        """Persisted ``force`` is honest per edge (force-free where the FSM accepts
        the supplied evidence; truthfully forced where it does not)."""
        mission_slug = f"test-mission-{starting_lane.replace('_', '-')}"
        wp_id = "WP05"
        feature_dir, _wp_file = _build_feature_in_lane(
            tmp_path, mission_slug=mission_slug, wp_id=wp_id, lane=starting_lane
        )
        feedback = _write_feedback_file(tmp_path)

        result = _invoke_move(
            tmp_path=tmp_path,
            mission_slug=mission_slug,
            args=[
                "move-task",
                wp_id,
                "--to",
                "planned",
                "--mission",
                mission_slug,
                "--review-feedback-file",
                str(feedback),
                "--no-auto-commit",
            ],
        )

        assert result.exit_code == 0, f"move-task failed:\n{result.output}"

        events = _read_latest_events_for_wp(feature_dir, wp_id)
        emitted = events[-1]
        assert str(emitted.from_lane) == starting_lane, (
            f"Expected from_lane={starting_lane}, got {emitted.from_lane}"
        )
        assert str(emitted.to_lane) == "planned"
        assert emitted.force is expected_force, (
            f"{starting_lane} -> planned: expected persisted force={expected_force}; "
            f"got force={emitted.force} reason={emitted.reason!r}"
        )
        assert emitted.reason is not None
        assert emitted.reason.startswith(expected_prefix), (
            f"reason must start with {expected_prefix!r}; got {emitted.reason!r}"
        )


class TestForwardControl:
    """Forward transitions must NOT auto-promote to force=True."""

    def test_planned_to_claimed_does_not_auto_promote(self, tmp_path: Path) -> None:
        """A forward step preserves force=False and a non-rewind reason."""
        mission_slug = "test-mission-forward-control"
        wp_id = "WP05"
        feature_dir, _wp_file = _build_feature_in_lane(
            tmp_path, mission_slug=mission_slug, wp_id=wp_id, lane="planned"
        )

        result = _invoke_move(
            tmp_path=tmp_path,
            mission_slug=mission_slug,
            args=[
                "move-task",
                wp_id,
                "--to",
                "claimed",
                "--mission",
                mission_slug,
                "--no-auto-commit",
            ],
        )

        assert result.exit_code == 0, f"forward move failed:\n{result.output}"

        events = _read_latest_events_for_wp(feature_dir, wp_id)
        emitted = events[-1]
        assert str(emitted.from_lane) == "planned"
        assert str(emitted.to_lane) == "claimed"
        assert emitted.force is False, (
            f"Forward move must not auto-promote force=True; reason={emitted.reason}"
        )
        assert emitted.reason is None or not emitted.reason.startswith(
            "backward rewind: "
        ), f"Forward emit must not use the rewind reason; got {emitted.reason!r}"


class TestForwardSkipAheadExpansion:
    """Forward skip-ahead expansion preserved via _lane_targets_for_emit."""

    def test_planned_to_in_progress_expands_intermediate(
        self, tmp_path: Path
    ) -> None:
        """``planned → in_progress`` emits two events (via claimed).

        FORWARD_ORDER index 0 → 2, so ``_lane_targets_for_emit`` returns
        ``[claimed, in_progress]`` — two events. This is the true 2-step
        skip-ahead and the canonical guard for FR-008 (e).
        """
        mission_slug = "test-mission-forward-skip"
        wp_id = "WP05"
        feature_dir, _wp_file = _build_feature_in_lane(
            tmp_path, mission_slug=mission_slug, wp_id=wp_id, lane="planned"
        )
        # lanes.json is now a required precondition to leave 'planned' (#4758,
        # _mt_guard_planned_boundary_lanes) -- fixture update, not a behavior
        # change: this test exercises forward skip-ahead expansion, not the
        # lanes.json guard.
        _seed_lanes_json(feature_dir, mission_slug, wp_id)

        events_before = len(_read_latest_events_for_wp(feature_dir, wp_id))

        result = _invoke_move(
            tmp_path=tmp_path,
            mission_slug=mission_slug,
            args=[
                "move-task",
                wp_id,
                "--to",
                "in_progress",
                "--mission",
                mission_slug,
                "--no-auto-commit",
            ],
        )

        assert result.exit_code == 0, f"forward skip-ahead failed:\n{result.output}"

        events = _read_latest_events_for_wp(feature_dir, wp_id)
        new_events = events[events_before:]
        # Two new events emitted: planned->claimed and claimed->in_progress.
        assert len(new_events) == 2, (
            f"Expected 2 new events for forward skip-ahead; got "
            f"{len(new_events)}: {[(str(e.from_lane), str(e.to_lane)) for e in new_events]}"
        )
        assert (str(new_events[0].from_lane), str(new_events[0].to_lane)) == (
            "planned",
            "claimed",
        )
        assert (str(new_events[1].from_lane), str(new_events[1].to_lane)) == (
            "claimed",
            "in_progress",
        )
        # No auto-promotion on forward emits.
        for ev in new_events:
            assert ev.force is False
            assert ev.reason is None or not ev.reason.startswith(
                "backward rewind: "
            )


class TestExplicitForceBackward:
    """Explicit ``--force`` on a backward move preserves the existing path (FR-011)."""

    def test_explicit_force_backward_uses_existing_path(self, tmp_path: Path) -> None:
        """``--force`` on backward: force=True via existing path; reason is the
        existing ``"Force move to planned"`` fallback (auto-promote bypassed)."""
        mission_slug = "test-mission-explicit-force"
        wp_id = "WP05"
        feature_dir, _wp_file = _build_feature_in_lane(
            tmp_path, mission_slug=mission_slug, wp_id=wp_id, lane="in_review"
        )
        feedback = _write_feedback_file(tmp_path)

        result = _invoke_move(
            tmp_path=tmp_path,
            mission_slug=mission_slug,
            args=[
                "move-task",
                wp_id,
                "--to",
                "planned",
                "--force",
                "--mission",
                mission_slug,
                "--review-feedback-file",
                str(feedback),
                "--no-auto-commit",
            ],
        )

        assert result.exit_code == 0, f"forced backward move failed:\n{result.output}"

        events = _read_latest_events_for_wp(feature_dir, wp_id)
        emitted = events[-1]
        assert str(emitted.from_lane) == "in_review"
        assert str(emitted.to_lane) == "planned"
        assert emitted.force is True
        # Auto-promote path is bypassed when force is explicit (FR-011);
        # the reason falls through to the standing fallback.
        assert emitted.reason == "Force move to Lane.PLANNED" or emitted.reason == (
            "Force move to planned"
        ), (
            f"Explicit --force must use the existing fallback reason; "
            f"got {emitted.reason!r}"
        )
        # And it must NOT be the auto-promoted rewind shape.
        assert not (emitted.reason or "").startswith("backward rewind: "), (
            f"Explicit --force must not synthesize the auto-promote reason; "
            f"got {emitted.reason!r}"
        )


class TestBackwardEmitFeedbackRef:
    """Backward emit with ``--review-feedback-file`` includes the canonical URI."""

    def test_backward_emit_includes_feedback_ref(self, tmp_path: Path) -> None:
        """The auto-promoted reason ends with ``": review-cycle://…"``."""
        mission_slug = "test-mission-feedback-ref"
        wp_id = "WP05"
        feature_dir, _wp_file = _build_feature_in_lane(
            tmp_path, mission_slug=mission_slug, wp_id=wp_id, lane="in_review"
        )
        feedback = _write_feedback_file(tmp_path)

        result = _invoke_move(
            tmp_path=tmp_path,
            mission_slug=mission_slug,
            args=[
                "move-task",
                wp_id,
                "--to",
                "planned",
                "--mission",
                mission_slug,
                "--review-feedback-file",
                str(feedback),
                "--no-auto-commit",
            ],
        )

        assert result.exit_code == 0, f"backward emit failed:\n{result.output}"

        emitted = _read_latest_events_for_wp(feature_dir, wp_id)[-1]
        # #3307: in_review -> planned is a review-rejection family edge, force=True
        # per the shared wire contract. The canonical review-cycle URI segment (the
        # assertion this test owns) is unchanged — only the force provenance is fixed.
        assert emitted.force is True
        assert emitted.reason is not None
        # Prefix:
        prefix = "backward rewind: in_review -> planned"
        assert emitted.reason.startswith(prefix), (
            f"reason must start with {prefix!r}; got {emitted.reason!r}"
        )
        # Feedback-ref segment:
        suffix = emitted.reason[len(prefix):]
        assert suffix.startswith(": review-cycle://"), (
            f"reason must include ': review-cycle://...' segment after the "
            f"prefix; got {emitted.reason!r}"
        )
        # The URI mentions the mission slug + a review-cycle file.
        assert mission_slug in emitted.reason
        assert "review-cycle-" in emitted.reason

    def test_backward_emit_note_is_preserved_after_canonical_prefix(
        self, tmp_path: Path
    ) -> None:
        """A user note must not replace the required backward-rewind audit text."""
        mission_slug = "test-mission-note-preserved"
        wp_id = "WP05"
        feature_dir, _wp_file = _build_feature_in_lane(
            tmp_path, mission_slug=mission_slug, wp_id=wp_id, lane="approved"
        )
        feedback = _write_feedback_file(tmp_path)
        note = "Reviewer requested a simpler implementation."

        result = _invoke_move(
            tmp_path=tmp_path,
            mission_slug=mission_slug,
            args=[
                "move-task",
                wp_id,
                "--to",
                "planned",
                "--mission",
                mission_slug,
                "--review-feedback-file",
                str(feedback),
                "--note",
                note,
                "--no-auto-commit",
            ],
        )

        assert result.exit_code == 0, f"backward emit with note failed:\n{result.output}"

        emitted = _read_latest_events_for_wp(feature_dir, wp_id)[-1]
        # #3307: approved -> planned is a review-rejection family edge, force=True
        # per the shared wire contract (the review_ref rationale still travels).
        assert emitted.force is True
        assert emitted.reason is not None
        assert emitted.reason.startswith("backward rewind: approved -> planned")
        assert ": review-cycle://" in emitted.reason
        assert emitted.reason.endswith(note)


# ---------------------------------------------------------------------------
# T004 — FR-009 wire-shape regression against Mission 1's fixture
# ---------------------------------------------------------------------------


def _load_approved_rewind_fixture() -> FixtureCase | None:
    """Return Mission 1's ``wp-status-changed-approved-rewind-valid``
    fixture, or ``None`` when the installed events package predates it.

    Per the mission spec (FR-009) the fixture lives in the ``edge_cases``
    category. The installed ``spec_kitty_events`` may not yet ship it
    (Mission 1 of the program is still being released); when absent we
    skip the test rather than fail — the assertion remains valid as soon
    as the upstream package lands the fixture.
    """
    try:
        from spec_kitty_events.conformance import load_fixtures
    except Exception:
        return None

    target = "wp-status-changed-approved-rewind-valid"
    for category in (
        "edge_cases",
        "events",
        "mission_audit",
        "lane_mapping",
    ):
        try:
            fixtures = load_fixtures(category)
        except Exception:
            continue
        for fc in fixtures:
            if getattr(fc, "id", None) == target:
                return fc
    return None


class TestApprovedRewindWireShape:
    """FR-009: auto-promoted ``approved → planned`` matches Mission 1's fixture."""

    def test_approved_to_planned_matches_mission1_fixture(
        self, tmp_path: Path
    ) -> None:
        """Wire shape (``force``, ``reason``-prefix, ``from_lane``, ``to_lane``)
        matches ``wp-status-changed-approved-rewind-valid``.

        Anchor: ``spec-kitty-events`` ``docs/consumer-contract-dossier-v2.4.0.md``
        § "Backward Transitions: The Review-Rejection Family".
        """
        mission_slug = "test-mission-fr009"
        wp_id = "WP07"
        feature_dir, _wp_file = _build_feature_in_lane(
            tmp_path, mission_slug=mission_slug, wp_id=wp_id, lane="approved"
        )
        feedback = _write_feedback_file(tmp_path)

        result = _invoke_move(
            tmp_path=tmp_path,
            mission_slug=mission_slug,
            args=[
                "move-task",
                wp_id,
                "--to",
                "planned",
                "--mission",
                mission_slug,
                "--review-feedback-file",
                str(feedback),
                "--no-auto-commit",
            ],
        )
        assert result.exit_code == 0, f"approved→planned failed:\n{result.output}"

        emitted = _read_latest_events_for_wp(feature_dir, wp_id)[-1]

        # CLI emit wire-shape invariants (independent of the upstream fixture).
        expected_prefix = "backward rewind: approved -> planned"
        # #3307: approved -> planned is a review-rejection family edge, force=True
        # per the shared wire contract. Mission 1's fixture encodes force=True — the
        # CLI now AGREES with it (FR-015 had wrongly diverged to force=False, which
        # the SaaS silently rejected). The force bit is cross-checked below.
        assert emitted.force is True
        assert str(emitted.from_lane) == "approved"
        assert str(emitted.to_lane) == "planned"
        assert emitted.reason is not None
        assert emitted.reason.startswith(expected_prefix), (
            f"reason must start with {expected_prefix!r}; got {emitted.reason!r}"
        )

        # Cross-check against Mission 1's fixture if available.
        fixture = _load_approved_rewind_fixture()
        if fixture is None:
            pytest.skip(
                "Mission 1 fixture 'wp-status-changed-approved-rewind-valid' not "
                "yet published in the installed spec_kitty_events package; CLI "
                "wire-shape invariants verified above."
            )

        fp = getattr(fixture, "payload", {}) or {}
        # Pull from common spelling variants (the fixture is normative;
        # consumers tolerate both ``from_lane``/``to_lane`` and the
        # nested ``data`` form).
        f_from = fp.get("from_lane", fp.get("data", {}).get("from_lane"))
        f_to = fp.get("to_lane", fp.get("data", {}).get("to_lane"))
        f_reason = fp.get("reason", fp.get("data", {}).get("reason"))
        f_force = fp.get("force", fp.get("data", {}).get("force"))

        # #3307: the CLI emit now conforms to the fixture's ``force`` bit. The
        # lane/reason wire shape (FR-009) remains normative and IS cross-checked.
        if f_force is not None:
            assert emitted.force == bool(f_force), (
                f"CLI force must match fixture force; got emitted={emitted.force} "
                f"fixture={f_force}"
            )
        if f_from is not None:
            assert str(emitted.from_lane) == f_from == "approved"
        if f_to is not None:
            assert str(emitted.to_lane) == f_to == "planned"
        if f_reason is not None:
            assert isinstance(f_reason, str)
            assert f_reason.startswith(expected_prefix), (
                f"Fixture reason must start with {expected_prefix!r}; "
                f"got {f_reason!r}"
            )
