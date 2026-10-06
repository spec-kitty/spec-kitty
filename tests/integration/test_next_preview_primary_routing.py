"""SC-002 behavioral proof for FR-004 (#2197): `spec-kitty next` claimable-preview
primary routing (WP03).

The out-of-loop ``spec-kitty next`` query path builds a finalized-override Decision
via ``runtime_bridge_query._build_finalized_override_query_decision``.  When the override
step is ``implement`` it previews which WP ``agent action implement`` would claim.

Before WP03 the preview read used the *caller's* ``feature_dir`` directly, which —
under coordination topology — is the STATUS-only coord husk.  The husk carries NO
``tasks/`` directory, so ``preview_claimable_wp`` returned an empty
(``wp_id=None``, ``selection_reason="no_tasks_dir"``) preview and the loop reported
the mission as having no claimable WP even though PRIMARY held ``tasks/WP01.md``.

After WP03 the WP-selection leg asks the mission context for
``WORK_PACKAGE_TASK`` while the status-event leg asks for ``STATUS_STATE``.  A
coord-topology mission then previews ``WP01`` from the artifact context selected
by the resolver, without the control surface knowing PRIMARY/coord filesystem
details.

This is the ONLY gate on FR-004 — the static call-shape arm cannot see a
parameter-fed ``tasks/``-dir read.  The proof is therefore VALUE-EXACT and
EXECUTES the pre-fix wrong-leg so a reviewer reverting T011 watches the primary
assertion go RED:

* **Routed (post-fix)**: ``Decision.wp_id == "WP01"`` (PRIMARY surface).
* **Unrouted (pre-fix wrong leg)**: ``preview_claimable_wp(<coord husk>)`` — the
  exact pre-fix single-arg call — yields ``wp_id is None`` (no ``tasks/`` on the
  husk).
* The two outcomes DIFFER; reverting the routing collapses the routed result onto
  the husk → empty → the ``== "WP01"`` assertion fails.

Uses the shared ``coord_topology_mission`` fixture read-only (WP04 owns the
fixture file); no resolver is patched — real git + filesystem state.
"""

from __future__ import annotations

import json

import pytest

from mission_runtime import MissionArtifactKind, mission_context_for
from runtime.next.decision import Decision, DecisionKind
from runtime.next.discovery import preview_claimable_wp
from runtime.next.runtime_bridge import query_current_state
from runtime.next.runtime_bridge_query import _build_finalized_override_query_decision
from tests.integration.coord_topology_fixture import (
    CoordTopologyContext,
    coord_topology_mission,
)

# Re-export fixture so pytest discovers it in this module.
__all__ = ["coord_topology_mission"]

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# The fixture seeds exactly one WP task on the PRIMARY surface (tasks/WP01.md);
# the coord husk carries STATUS only (no tasks/).  The PRIMARY-surface claimable
# WP id is therefore the value-exact expectation for the routed preview.
_EXPECTED_PRIMARY_WP_ID = "WP01"

# A real-format (Crockford base32, 26-char) ULID for the seeded PLANNED event.
_COORD_PLANNED_EVENT_ID = "01KW2E7AFC0000000000000010"


def _seed_coord_planned_event(ctx: CoordTopologyContext) -> None:
    """Put WP01 at lane ``planned`` on the COORD husk via a parseable event.

    The fixture's default coord events use a string ``evidence`` field
    (unparseable → reducer fallback → WP01 GENESIS → not claimable).  This
    replaces them with a single valid, parseable ``genesis → planned`` event so
    the reducer yields WP01 at ``planned`` from the AUTHORITATIVE coord husk.
    WP01 has no dependencies (fixture frontmatter), so a planned WP01 is
    claimable — making the routed preview value-exact (``wp_id == "WP01"``).

    Writing through ``ctx.status_events_path`` (the coord husk events file the
    fixture exposes) mirrors the sibling ``test_coord_loop_tasks`` helpers; the
    fixture module itself is left untouched (WP04 owns it).
    """
    event = {
        "actor": "coord-fixture",
        "at": "2026-06-26T00:00:00+00:00",
        "event_id": _COORD_PLANNED_EVENT_ID,
        "evidence": None,
        "execution_mode": "code_change",
        "feature_slug": ctx.slug,
        "force": False,
        "from_lane": "genesis",
        "reason": None,
        "review_ref": None,
        "to_lane": "planned",
        "wp_id": _EXPECTED_PRIMARY_WP_ID,
    }
    ctx.status_events_path.write_text(json.dumps(event) + "\n", encoding="utf-8")


def _build_implement_override_decision(ctx: CoordTopologyContext) -> Decision:
    """Drive the real finalized-override builder for the ``implement`` step.

    Mirrors the single production call site
    (``runtime_bridge_query.query_current_state`` → ``_build_finalized_override_query_decision``)
    with ``finalized_override="implement"`` so the routed preview leg executes.
    """
    return _build_finalized_override_query_decision(
        agent="claude",
        mission_slug=ctx.slug,
        mission_type="software-dev",
        now="2026-06-27T00:00:00+00:00",
        progress=None,
        emitted_run_id=None,
        repo_root=ctx.repo,
        finalized_override="implement",
    )


def _mark_primary_task_board_finalized(ctx: CoordTopologyContext) -> None:
    """Create the primary ``tasks.md`` marker required by finalized-board override."""
    (ctx.primary_feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")


class TestNextPreviewRoutesToPrimary:
    """FR-004 / SC-002: claimable-preview previews from PRIMARY under coord topology."""

    def test_mission_context_routes_by_artifact_kind(
        self,
        coord_topology_mission: CoordTopologyContext,
    ) -> None:
        """Mission context hides primary/status filesystem concerns from callers."""
        ctx = coord_topology_mission

        mission_context = mission_context_for(ctx.repo, ctx.slug)
        task_artifact = mission_context.artifact(MissionArtifactKind.WORK_PACKAGE_TASK)
        status_artifact = mission_context.artifact(MissionArtifactKind.STATUS_STATE)

        assert mission_context.mission_slug == ctx.slug
        assert mission_context.mission_type == "software-dev"
        assert task_artifact.read_dir.resolve() == ctx.primary_feature_dir.resolve()
        assert task_artifact.write_dir.resolve() == ctx.primary_feature_dir.resolve()
        assert task_artifact.commit_target is not None
        assert status_artifact.read_dir.resolve() == ctx.coord_feature_dir.resolve()
        assert status_artifact.write_dir.resolve() == ctx.coord_feature_dir.resolve()
        assert status_artifact.commit_target is not None
        assert task_artifact.commit_target.ref != status_artifact.commit_target.ref

    def test_routed_decision_previews_primary_wp_id(
        self,
        coord_topology_mission: CoordTopologyContext,
    ) -> None:
        """Routed Decision.wp_id equals the PRIMARY-seeded WP id (value-exact).

        Post-fix: the WP-selection leg reads PRIMARY via
        ``WORK_PACKAGE_TASK`` artifact context where ``tasks/WP01.md`` lives, so
        the override Decision previews ``WP01``.  Reverting T011 routes this read
        back onto the caller's coord husk (STATUS-only) → empty preview → ``wp_id``
        becomes ``None`` → this assertion goes RED.
        """
        ctx = coord_topology_mission
        _mark_primary_task_board_finalized(ctx)
        _seed_coord_planned_event(ctx)

        decision = _build_implement_override_decision(ctx)

        assert decision.kind is DecisionKind.query
        # VALUE-EXACT (not `is not None`, not a path equality): the routed preview
        # must select the WP the PRIMARY surface actually seeds.
        assert decision.wp_id == _EXPECTED_PRIMARY_WP_ID, (
            "Routed claimable preview must select the PRIMARY-surface WP id "
            f"{_EXPECTED_PRIMARY_WP_ID!r}; got {decision.wp_id!r}. "
            "If None, the WP-selection leg is reading the STATUS-only coord husk "
            "(the #2197 regression) instead of the WORK_PACKAGE_TASK artifact context."
        )

    def test_revert_leg_executes_and_differs_from_routed(
        self,
        coord_topology_mission: CoordTopologyContext,
    ) -> None:
        """EXECUTE the pre-fix wrong leg and prove it differs from the routed result.

        Non-fakeable SC-002 DoD: rather than documenting "revert would be empty",
        this drives the EXACT pre-fix single-arg call
        ``preview_claimable_wp(<coord husk>)`` — the caller's ``feature_dir`` under
        coord topology — and asserts it yields an empty ``wp_id`` that DIFFERS from
        the routed Decision.  Both outcomes live in the test body; a reviewer
        reverting T011 collapses the routed result onto this empty unrouted one.
        """
        ctx = coord_topology_mission
        _mark_primary_task_board_finalized(ctx)
        _seed_coord_planned_event(ctx)

        # ROUTED (post-fix): PRIMARY surface → WP01.
        routed = _build_implement_override_decision(ctx)

        # UNROUTED (pre-fix wrong leg): the coord husk is the caller's feature_dir
        # under coord topology.  preview_claimable_wp(<husk>) is byte-for-byte the
        # pre-fix call shape — the husk has no tasks/ → empty preview.
        unrouted = preview_claimable_wp(ctx.coord_feature_dir)

        # Husk invariant guard: the wrong leg must genuinely lack tasks/ so the
        # emptiness is a real wrong-leg read, not an accident of the fixture.
        assert not (ctx.coord_feature_dir / "tasks").is_dir(), (
            "Coord husk must be STATUS-only (no tasks/) for the revert proof to "
            "exercise the real #2197 wrong-leg behaviour."
        )

        assert unrouted.wp_id is None, (
            "Pre-fix wrong-leg preview (coord husk, no tasks/) must yield no "
            f"claimable WP; got {unrouted.wp_id!r}."
        )
        assert unrouted.selection_reason == "no_tasks_dir", (
            "Coord-husk preview must report 'no_tasks_dir'; got "
            f"{unrouted.selection_reason!r}."
        )

        # The routed and unrouted outcomes MUST differ — this is the behavioural
        # delta the routing fix creates.  Reverting T011 makes them equal (both
        # empty), so this inequality + the value-exact assertion above both fail.
        assert routed.wp_id != unrouted.wp_id, (
            "Routed PRIMARY preview and unrouted coord-husk preview must differ.\n"
            f"  routed   : {routed.wp_id!r} (expected {_EXPECTED_PRIMARY_WP_ID!r})\n"
            f"  unrouted : {unrouted.wp_id!r} (expected None)\n"
            "Equal values mean the routing fix is absent (T011 reverted)."
        )
        assert routed.wp_id == _EXPECTED_PRIMARY_WP_ID

    def test_query_current_state_uses_primary_tasks_and_coord_status(
        self,
        coord_topology_mission: CoordTopologyContext,
    ) -> None:
        """Full production path: query mode reaches implement/WP01 under coord topology.

        This guards the pre-builder leg too. A helper-only test can pass while
        ``query_current_state`` still computes finalized progress from the STATUS-only
        coord husk (no ``tasks/``) and returns ``not_started``.
        """
        ctx = coord_topology_mission
        _mark_primary_task_board_finalized(ctx)
        _seed_coord_planned_event(ctx)

        decision = query_current_state("claude", ctx.slug, ctx.repo)

        assert decision.kind is DecisionKind.query
        assert decision.mission_state == "implement"
        assert decision.wp_id == _EXPECTED_PRIMARY_WP_ID
        assert decision.progress is not None
        assert decision.progress["total_wps"] == 1
        assert decision.progress["planned_wps"] == 1

    def test_advance_first_contact_matches_query_under_coord_topology_5310(
        self,
        coord_topology_mission: CoordTopologyContext,
    ) -> None:
        """#5310 advance-side analog: with no persisted run, advancing ``next``
        reads PRIMARY tasks + COORD status (never the STATUS-only coord husk) and
        resolves the same board step/WP query mode previews, instead of booting a
        discovery run."""
        from runtime.next.runtime_bridge import decide_next_via_runtime

        ctx = coord_topology_mission
        _mark_primary_task_board_finalized(ctx)
        _seed_coord_planned_event(ctx)
        # Advance (unlike query) opens the durable decision log, whose coordination
        # seed refuses a root status log that forks from the coordination copy. The
        # fixture's DECOY primary log is exactly such a fork, so drop it here: the
        # primary-task / coord-status split is still proven (tasks/ exist only on
        # PRIMARY, the planned event only on COORD).
        ctx.decoy_events_path.unlink()

        query = query_current_state("claude", ctx.slug, ctx.repo)
        advance = decide_next_via_runtime("claude", ctx.slug, "success", ctx.repo)

        assert query.preview_step == "implement"
        assert advance.kind is DecisionKind.step, advance.reason
        assert advance.action == query.preview_step
        assert advance.mission_state == query.mission_state
        assert advance.wp_id == _EXPECTED_PRIMARY_WP_ID
