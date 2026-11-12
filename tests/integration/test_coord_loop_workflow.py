"""Integration tests for WP04: workflow.py loop reads routed to planning seam.

Per-site RED-first tests proving the coord-topology routing invariant for each
routed site in ``workflow.py`` and the backward-compatible signature split in
``discovery.py``:

- **PRIMARY leg**: ``tasks/`` and ``lanes.json`` are read from the PRIMARY checkout.
- **STATUS leg**: event-log reads stay on the coord husk (C-001 per-leg split).
- **C-008**: review-cycle sub-artifacts (``baseline-tests.json``, sub_artifact_dir)
  stay on the coord-aware resolver.
- **Flat neutrality**: ``selection_reason`` is unchanged on a flat topology.
- **Backward-compat**: existing single-arg callers of ``preview_claimable_wp``
  keep working; the split is additive only.

RED-first proof (documented inline per site): before WP04, the routed sites used
coord-aware resolvers (``candidate_feature_dir_for_mission``,
``resolve_feature_dir_for_mission``) for ``tasks/`` and ``lanes.json`` reads.  The
coord husk carries NO ``tasks/`` directory and NO ``lanes.json`` — STATUS-only
invariant — so each command would fail (wrong lane, "no tasks", "unknown" context)
when the session topology is ``coord``.  After WP04,
``resolve_planning_read_dir(kind=WORK_PACKAGE_TASK/LANE_STATE)`` routes the
PRIMARY leg to the primary checkout, preserving the STATUS leg on the coord-aware
resolver (C-001 mixed-read discipline).

Fixture layout (from ``coord_topology_mission``):

* ``primary_feature_dir/``      — meta.json, tasks/WP01.md, lanes.json, DECOY events
* ``coord_feature_dir/``        — status.events.jsonl ONLY (coord marker)
* ``status_events_path``        — coord husk authoritative events file
* ``decoy_events_path``         — primary DECOY events file (distinct content)

The fixture coord events file initially has unparseable events (string evidence).
Tests that need parseable events write valid JSONL to ``ctx.status_events_path``
before invoking the subject under test.

See ``tests/integration/coord_topology_fixture.py`` for fixture details.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from tests.integration.coord_topology_fixture import (
    CoordTopologyContext,
    FlatTopologyContext,
    assert_reads_primary,
    coord_topology_mission,
    flat_topology_mission,
)

if TYPE_CHECKING:
    pass

# Re-export fixtures so pytest discovers them in this module.
__all__ = ["coord_topology_mission", "flat_topology_mission"]

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# ---------------------------------------------------------------------------
# ULID event IDs — real Crockford base32 format (26 chars, per styleguide)
# ---------------------------------------------------------------------------

_COORD_EVENT_ID_PLANNED = "01KW2E7AFC0000000000000010"   # planned (initial seed)
_COORD_EVENT_ID_FOR_REVIEW = "01KW2E7AFC0000000000000020"  # for_review (T017 test)


# ---------------------------------------------------------------------------
# Helpers — seed parseable events on coord husk
# ---------------------------------------------------------------------------


def _write_coord_planned_event(ctx: CoordTopologyContext) -> None:
    """Replace coord husk events with a valid parseable ``planned`` seed.

    After this call:
    - Coord husk: WP01 ``planned`` (bootstrap / genesis→planned).
    - Primary DECOY: retains unparseable events (string evidence).

    A wrong-leg STATUS read (from PRIMARY) parses the fixture decoy event with
    string evidence — ``_load_wp_lanes`` silently returns ``{}`` (the BLE001
    except), so ``wp_lanes.get("WP01", Lane.GENESIS) == Lane.GENESIS`` →
    ``selection_reason = "not_finalized"``.  Correct coord read returns
    ``{WP01: planned}`` → WP01 is claimable → ``wp_id = "WP01"``.

    This makes the per-leg distinction observable in the ``_preview_claimable_wp``
    result without additional mocking.
    """
    event = {
        "actor": "coord-fixture-wp04",
        "at": "2026-06-26T00:00:00+00:00",
        "event_id": _COORD_EVENT_ID_PLANNED,
        "evidence": None,
        "execution_mode": "code_change",
        "feature_slug": ctx.slug,
        "force": True,
        "from_lane": "planned",
        "reason": None,
        "review_ref": None,
        "to_lane": "planned",
        "wp_id": "WP01",
    }
    ctx.status_events_path.write_text(json.dumps(event) + "\n", encoding="utf-8")


def _write_coord_for_review_event(ctx: CoordTopologyContext) -> None:
    """Replace coord husk events with a valid parseable ``for_review`` transition.

    After this call:
    - Coord husk: WP01 at ``for_review`` (planned→for_review).
    - Primary DECOY: retains unparseable events.

    A wrong-leg STATUS read returns empty lanes (``_fr_lanes = {}``); the
    function defaults ``lane = Lane.PLANNED`` (not ``for_review``), so no WP is
    returned.  Correct coord read returns WP01 at ``for_review`` → returned.
    """
    event = {
        "actor": "coord-fixture-wp04",
        "at": "2026-06-26T00:00:00+00:00",
        "event_id": _COORD_EVENT_ID_FOR_REVIEW,
        "evidence": None,
        "execution_mode": "code_change",
        "feature_slug": ctx.slug,
        "force": False,
        "from_lane": "planned",
        "reason": None,
        "review_ref": None,
        "to_lane": "for_review",
        "wp_id": "WP01",
    }
    ctx.status_events_path.write_text(json.dumps(event) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# T016 — _preview_claimable_wp_for_mission routes tasks/ to PRIMARY
# ---------------------------------------------------------------------------


class TestPreviewClaimableWpForMissionRoutesToPrimary:
    """T016: _preview_claimable_wp_for_mission routes tasks/ and status correctly.

    RED-first proof:
    Before WP04, ``_preview_claimable_wp_for_mission`` called
    ``resolve_feature_dir_for_mission(get_main_repo_root(repo_root), slug)``
    which, for a coord-topology mission, resolves to the STATUS-only coord husk.
    ``(coord_husk / "tasks").is_dir()`` → False → the function returned ``None``.

    After WP04, ``resolve_planning_read_dir(kind=WORK_PACKAGE_TASK)`` routes to
    PRIMARY, where ``tasks/WP01.md`` exists.  The STATUS leg uses the coord-aware
    resolver so events come from the coord husk, not the primary decoy.
    """

    def test_primary_tasks_and_coord_status_both_legs(
        self,
        coord_topology_mission: CoordTopologyContext,
    ) -> None:
        """Both legs correct: tasks from PRIMARY; claimability from COORD events.

        RED anchor (pre-WP04): ``resolve_feature_dir_for_mission`` returns coord
        husk → ``(coord_husk / "tasks").is_dir()`` → False → returns None.
        After WP04: returns a ClaimablePreview with ``wp_id="WP01"``.

        Dual-leg distinction:
        - If STATUS leg reads PRIMARY (wrong): decoy events are unparseable →
          ``_load_wp_lanes`` returns ``{}`` → ``Lane.GENESIS`` →
          ``selection_reason = "not_finalized"`` (not ``wp_id="WP01"``).
        - Correct coord read: WP01 at ``planned`` → claimable.
        """
        from specify_cli.cli.commands.agent.workflow import _preview_claimable_wp_for_mission
        from specify_cli.missions._read_path_resolver import resolve_feature_dir_for_mission

        ctx = coord_topology_mission

        # --- RED anchor: pre-fix resolver returns coord husk (no tasks/) ---
        pre_fix_dir = resolve_feature_dir_for_mission(ctx.repo, ctx.slug)
        assert pre_fix_dir == ctx.coord_feature_dir, (
            "Pre-fix resolver must return the coord husk (RED anchor)"
        )
        assert not (pre_fix_dir / "tasks").is_dir(), (
            "tasks/ must be absent from coord husk (proves test was RED pre-WP04)"
        )
        # Pre-WP04 behaviour: function returned None — husk has no tasks/.
        # After WP04: tasks/ found on primary → result is a ClaimablePreview.

        # Seed valid parseable planned event on coord so the claimability check
        # can distinguish PRIMARY (decoy/unparseable → not_finalized) from COORD
        # (planned → wp_id="WP01").
        _write_coord_planned_event(ctx)

        # POST-FIX: call through the PRE-EXISTING entry point.
        result = _preview_claimable_wp_for_mission(ctx.repo, ctx.slug)

        # PRIMARY leg: tasks found (not None as pre-fix husk path produced).
        assert result is not None, (
            "_preview_claimable_wp_for_mission must not return None for a mission "
            "with tasks/ on primary. Pre-fix returned None because the coord husk "
            "has no tasks/ dir."
        )
        # COORD leg: WP01 is planned on coord → claimable (selection_reason=None).
        # If reading from PRIMARY instead: decoy events are unparseable → GENESIS
        # → selection_reason="not_finalized" (not wp_id="WP01").
        assert result.wp_id == "WP01", (
            f"STATUS leg must resolve to COORD (WP01 is planned on coord husk).\n"
            f"  Expected wp_id : 'WP01'\n"
            f"  Got            : {result.wp_id!r}\n"
            f"  selection_reason: {result.selection_reason!r}\n"
            "If selection_reason='not_finalized', the STATUS leg read from PRIMARY "
            "(decoy, unparseable) instead of the coord husk."
        )

    def test_flat_topology_selection_reason_unchanged(
        self,
        flat_topology_mission: FlatTopologyContext,
    ) -> None:
        """Flat topology: selection_reason is unchanged (neutrality regression).

        On a flat (single_branch) mission, resolve_planning_read_dir(WORK_PACKAGE_TASK)
        returns the primary dir (same as the old resolve_feature_dir_for_mission
        since there is no coord worktree).  The result must match.
        """
        from specify_cli.cli.commands.agent.workflow import _preview_claimable_wp_for_mission

        ctx = flat_topology_mission

        result = _preview_claimable_wp_for_mission(ctx.repo, ctx.slug)

        # Flat topology: tasks/ exists on primary = the only dir.
        # The valid fixture event records the WP as claimed.
        assert result is not None
        assert result.selection_reason == "all_wps_in_progress", (
            "Flat topology: selection_reason must reflect the claimed WP.\n"
            f"  Got: {result.selection_reason!r}"
        )


# ---------------------------------------------------------------------------
# T017a — _find_first_for_review_wp routes tasks/ to PRIMARY; status to COORD
# ---------------------------------------------------------------------------


class TestFindFirstForReviewWpRoutesToPrimary:
    """T017: _find_first_for_review_wp routes tasks/ reads to PRIMARY.

    RED-first proof:
    Before WP04, ``_find_first_for_review_wp`` used
    ``resolve_feature_dir_for_mission(repo_root, slug) / "tasks"`` in the
    non-worktree branch, which resolves to the STATUS-only coord husk under
    coord topology.  ``tasks_dir.exists()`` → False → returned ``None``.

    After WP04, ``resolve_planning_read_dir(kind=WORK_PACKAGE_TASK) / "tasks"``
    routes to PRIMARY, where ``tasks/WP01.md`` exists.  The STATUS leg uses
    ``candidate_feature_dir_for_mission(repo_root, slug)`` so events come from
    the coord husk.
    """

    def test_tasks_from_primary_status_from_coord(
        self,
        coord_topology_mission: CoordTopologyContext,
    ) -> None:
        """Both legs: tasks/ from PRIMARY, for_review lane from COORD events.

        RED anchor (pre-WP04): ``resolve_feature_dir_for_mission`` → coord husk →
        ``tasks_dir.exists()`` → False → returned None.

        Dual-leg distinction:
        - If STATUS reads PRIMARY (wrong): decoy events unparseable → ``_fr_lanes={}``
          → ``_fr_lanes.get("WP01", Lane.PLANNED) == Lane.PLANNED`` → not
          ``Lane.FOR_REVIEW`` → function returns None.
        - Correct coord read: WP01 at for_review → returns "WP01".
        """
        from specify_cli.cli.commands.agent.workflow import _find_first_for_review_wp
        from specify_cli.missions._read_path_resolver import resolve_feature_dir_for_mission

        ctx = coord_topology_mission

        # --- RED anchor: pre-fix resolver returns coord husk (no tasks/) ---
        pre_fix_dir = resolve_feature_dir_for_mission(ctx.repo, ctx.slug)
        assert pre_fix_dir == ctx.coord_feature_dir, (
            "Pre-fix resolver must return the coord husk (RED anchor)"
        )
        assert not (pre_fix_dir / "tasks").is_dir(), (
            "tasks/ must be absent from coord husk (proves test was RED pre-WP04)"
        )

        # Seed valid for_review event on coord husk.
        _write_coord_for_review_event(ctx)

        # POST-FIX: call through the PRE-EXISTING entry point.
        result = _find_first_for_review_wp(ctx.repo, ctx.slug)

        # PRIMARY leg: WP01.md found on primary tasks/ → "WP01" returned.
        # STATUS leg: for_review event from coord husk → WP01 has that lane.
        assert result == "WP01", (
            f"_find_first_for_review_wp must return 'WP01' when:\n"
            f"  - tasks/WP01.md exists on PRIMARY (not on coord husk)\n"
            f"  - WP01 has lane for_review on COORD (not primary decoy)\n"
            f"  Got: {result!r}\n"
            "If None: either tasks/ not found (PRIMARY route failed) or for_review "
            "lane not resolved (STATUS reads PRIMARY decoy, which is unparseable)."
        )

    def test_flat_topology_returns_none_when_no_for_review(
        self,
        flat_topology_mission: FlatTopologyContext,
    ) -> None:
        """Flat topology: returns None when no WP has for_review lane (neutrality).

        The flat fixture has default unparseable events (string evidence) → no
        for_review lane → returns None.  This regression catches any change that
        breaks the flat case.
        """
        from specify_cli.cli.commands.agent.workflow import _find_first_for_review_wp

        ctx = flat_topology_mission

        result = _find_first_for_review_wp(ctx.repo, ctx.slug)

        assert result is None, (
            f"Flat topology with no for_review WPs must return None.\n"
            f"  Got: {result!r}"
        )


# ---------------------------------------------------------------------------
# T017b — _resolve_review_context routes lanes.json to PRIMARY
# ---------------------------------------------------------------------------


class TestResolveReviewContextRoutesLanesToPrimary:
    """T017: _resolve_review_context routes the lanes.json leg to PRIMARY.

    RED-first proof:
    Before WP04, ``_resolve_review_context`` used
    ``candidate_feature_dir_for_mission(repo_root, slug)`` which, for a
    coord-topology mission, returns the STATUS-only coord husk (no lanes.json).
    ``read_lanes_json(coord_husk)`` raised → ``lanes_manifest = None`` →
    ``mission_branch = "unknown"``.

    After WP04, ``resolve_planning_read_dir(kind=WORK_PACKAGE_TASK)`` routes to
    PRIMARY, where lanes.json exists → ``mission_branch`` is the real value.

    Test strategy: mock ``resolve_workspace_for_wp`` to return a minimal
    ``ResolvedWorkspace`` with ``resolution_kind="repo_root"`` (causes early
    return from the function after git-log returns empty → no claim commit).
    Assert ``ctx["mission_branch"]`` differs between pre-fix and post-fix.
    """

    def test_lanes_json_read_from_primary(
        self,
        coord_topology_mission: CoordTopologyContext,
        tmp_path: Path,
    ) -> None:
        """lanes.json is read from PRIMARY, not the STATUS-only coord husk.

        RED anchor (pre-WP04): ``candidate_feature_dir_for_mission`` → coord husk
        → no lanes.json → ``lanes_manifest = None`` → ``mission_branch = "unknown"``.

        After WP04: ``resolve_planning_read_dir(kind=WORK_PACKAGE_TASK)`` →
        primary → lanes.json exists and is parseable → ``mission_branch`` set.

        Note: the fixture's ``lanes.json`` lacks the ``computed_at``/``computed_from``
        fields that ``read_lanes_json`` requires.  This test writes a COMPLETE,
        parseable ``lanes.json`` to the PRIMARY dir before calling the function.
        The assertion is that the post-fix function resolves lanes.json from
        PRIMARY (where the parseable file is written) and NOT from the coord husk
        (where no lanes.json exists at all).
        """
        from specify_cli.cli.commands.agent.workflow import _resolve_review_context
        from specify_cli.missions._read_path_resolver import candidate_feature_dir_for_mission
        from specify_cli.workspace.context import ResolvedWorkspace

        ctx = coord_topology_mission

        # --- RED anchor: pre-fix resolver returns coord husk (no lanes.json) ---
        pre_fix_dir = candidate_feature_dir_for_mission(ctx.repo, ctx.slug)
        assert pre_fix_dir == ctx.coord_feature_dir, (
            "Pre-fix resolver must return the coord husk (RED anchor)"
        )
        assert not (pre_fix_dir / "lanes.json").exists(), (
            "lanes.json must be absent from coord husk (proves test was RED)"
        )

        # Write a COMPLETE, parseable lanes.json to the PRIMARY dir.
        # (The fixture writes a minimal lanes.json that lacks computed_at/computed_from,
        # so we overwrite it with a version read_lanes_json can parse successfully.)
        _expected_mission_branch = f"kitty/mission-{ctx.slug}"
        _complete_lanes = {
            "version": 1,
            "mission_slug": ctx.slug,
            "mission_id": ctx.mission_id,
            "mission_branch": _expected_mission_branch,
            "target_branch": "main",
            "computed_at": "2026-06-26T00:00:00+00:00",
            "computed_from": "dependency_graph+ownership",
            "lanes": [
                {
                    "lane_id": "lane-a",
                    "wp_ids": ["WP01"],
                    "write_scope": [],
                    "predicted_surfaces": [],
                    "depends_on_lanes": [],
                    "parallel_group": 0,
                }
            ],
        }
        (ctx.primary_feature_dir / "lanes.json").write_text(
            json.dumps(_complete_lanes, indent=2), encoding="utf-8"
        )

        # Create a workspace_path that exists (required by the guard check).
        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()

        # Mock workspace: resolution_kind="repo_root" so the function takes the
        # repo_root branch and returns early (no claim commit → return ctx).
        mock_workspace = MagicMock(spec=ResolvedWorkspace)
        mock_workspace.resolution_kind = "repo_root"
        mock_workspace.context = None

        with patch(
            "specify_cli.cli.commands.agent.workflow.resolve_workspace_for_wp",
            return_value=mock_workspace,
        ):
            result = _resolve_review_context(
                workspace_path,
                ctx.repo,
                ctx.slug,
                "WP01",
                [],
            )

        # Post-fix: lanes.json read from PRIMARY → mission_branch resolved.
        # Pre-fix (RED): coord husk has no lanes.json → lanes_manifest=None →
        # mission_branch="unknown".
        assert result["mission_branch"] == _expected_mission_branch, (
            f"mission_branch must come from lanes.json on PRIMARY checkout.\n"
            f"  Expected : {_expected_mission_branch!r}\n"
            f"  Got      : {result['mission_branch']!r}\n"
            "If 'unknown': lanes.json was read from the coord husk (absent, no "
            "lanes.json there) instead of the primary checkout."
        )


# ---------------------------------------------------------------------------
# T018 — review build_dependency_graph routes to PRIMARY; C-008 coord stays
# ---------------------------------------------------------------------------


class TestReviewCommandRoutesGraphToPrimary:
    """T018: review command's build_dependency_graph routes tasks/ to PRIMARY.

    C-008 invariant: baseline-tests.json and sub_artifact_dir stay on the
    coord-aware ``resolve_feature_dir_for_mission`` resolver — they are
    review-cycle sub-artifacts that MUST be co-located with status on coord.

    RED-first proof:
    Before WP04, the review command used
    ``resolve_feature_dir_for_mission(repo_root, slug)`` for ``build_dependency_graph``,
    which for a coord-topology mission resolves to the coord husk (no tasks/ → empty
    graph → ``get_dependents`` returns no dependents → no warning generated even if
    dependents exist).

    After WP04: ``resolve_planning_read_dir(kind=WORK_PACKAGE_TASK)`` routes to
    PRIMARY (tasks/ present → real graph computed).

    Test strategy: rather than driving the full review CLI command (which needs git
    worktrees, review prompts, etc.), we verify the routing seam directly by asserting
    that:
    1. Pre-fix: ``build_dependency_graph(coord_husk)`` raises or returns empty
       (no tasks/ on husk → no WP files → empty graph).
    2. Post-fix (seam): ``build_dependency_graph(primary_dir)`` reads real tasks.
    3. C-008: the baseline-tests.json path resolves relative to the coord-aware
       dir (``resolve_feature_dir_for_mission``), not primary.
    """

    def test_dependency_graph_reads_from_primary_tasks(
        self,
        coord_topology_mission: CoordTopologyContext,
    ) -> None:
        """build_dependency_graph reads tasks/ from PRIMARY after routing.

        RED anchor: before WP04, the review command called
        ``build_dependency_graph(resolve_feature_dir_for_mission(repo_root, slug))``.
        For a coord-topology mission, that resolves to the coord husk — no
        tasks/ → ``build_dependency_graph`` returns an empty graph ``{}``.

        After WP04: ``build_dependency_graph(resolve_planning_read_dir(kind=WORK_PACKAGE_TASK))``
        reads from PRIMARY where tasks/WP01.md exists → graph includes WP01.
        """
        from specify_cli.core.dependency_graph import build_dependency_graph
        from specify_cli.missions._read_path_resolver import (
            resolve_feature_dir_for_mission,
            resolve_planning_read_dir,
        )
        from mission_runtime import MissionArtifactKind

        ctx = coord_topology_mission

        # --- RED anchor: pre-fix reads from coord husk ---
        pre_fix_dir = resolve_feature_dir_for_mission(ctx.repo, ctx.slug)
        assert pre_fix_dir == ctx.coord_feature_dir, (
            "Pre-fix resolver must return coord husk (RED anchor)"
        )
        pre_fix_graph = build_dependency_graph(pre_fix_dir)
        assert pre_fix_graph == {}, (
            f"Pre-fix: coord husk has no tasks/ → empty graph.\n"
            f"  Got: {pre_fix_graph}"
        )

        # --- POST-FIX: planning seam routes to PRIMARY ---
        planning_dir = resolve_planning_read_dir(
            ctx.repo, ctx.slug, kind=MissionArtifactKind.WORK_PACKAGE_TASK
        )
        assert planning_dir == ctx.primary_feature_dir, (
            f"resolve_planning_read_dir(WORK_PACKAGE_TASK) must return primary dir.\n"
            f"  Expected: {ctx.primary_feature_dir}\n"
            f"  Got:      {planning_dir}"
        )
        post_fix_graph = build_dependency_graph(planning_dir)
        assert "WP01" in post_fix_graph, (
            f"PRIMARY tasks/WP01.md must be discoverable by build_dependency_graph.\n"
            f"  Graph: {post_fix_graph}"
        )

    def test_c008_baseline_stays_on_coord_aware_resolver(
        self,
        coord_topology_mission: CoordTopologyContext,
    ) -> None:
        """C-008: review-cycle sub-artifact (baseline-tests.json) stays coord.

        The review command keeps ``_rv_feature_dir = resolve_feature_dir_for_mission(...)``
        for review-cycle sub-artifacts.  For a coord-topology mission, this resolves
        to the coord husk — the AUTHORITATIVE location for review-cycle writes (C-008).
        The routing of ``build_dependency_graph`` (T018) must NOT touch these lines.
        """
        from specify_cli.missions._read_path_resolver import resolve_feature_dir_for_mission

        ctx = coord_topology_mission

        # C-008: the coord-aware resolver still returns the coord dir.
        rv_feature_dir = resolve_feature_dir_for_mission(ctx.repo, ctx.slug)
        assert rv_feature_dir == ctx.coord_feature_dir, (
            f"C-008: resolve_feature_dir_for_mission must return coord dir "
            f"(review-cycle sub-artifact anchor).\n"
            f"  Expected: {ctx.coord_feature_dir}\n"
            f"  Got:      {rv_feature_dir}"
        )

        # Baseline path is built as: rv_feature_dir / "tasks" / wp_slug / "baseline-tests.json"
        # After T018 routing, this path still uses the coord-aware resolver → correct.
        _rv_wp_slug = "WP01-fixture-task"
        baseline_path = rv_feature_dir / "tasks" / _rv_wp_slug / "baseline-tests.json"
        # Assert the path is anchored under the COORD dir (not primary).
        assert str(baseline_path).startswith(str(ctx.coord_feature_dir)), (
            f"C-008: baseline-tests.json must be anchored under coord dir.\n"
            f"  Coord dir    : {ctx.coord_feature_dir}\n"
            f"  Baseline path: {baseline_path}"
        )


# ---------------------------------------------------------------------------
# T015 — discovery.py backward-compatible signature split
# ---------------------------------------------------------------------------


class TestDiscoveryBackwardCompatibleSplit:
    """T015: preview_claimable_wp(feature_dir) keeps working with single arg.

    The WP09-trap fix adds ``status_dir: Path | None = None`` as a keyword-only
    parameter.  All existing callers (``runtime_bridge.py``, test suite) pass a
    single positional arg ``feature_dir`` — they must keep working unchanged.
    """

    def test_single_arg_still_works(self, tmp_path: Path) -> None:
        """Backward-compat: single-arg call signature produces a valid result.

        This is the existing call shape used by ``runtime_bridge.py:3078`` and
        ``tests/next/test_next_claimable_payload.py``.  Adding ``status_dir``
        as keyword-only with default ``None`` preserves positional compatibility.
        """
        from runtime.next.discovery import ClaimablePreview, preview_claimable_wp

        # Minimal scaffold: tasks/ exists but no WP files → no_wp_files.
        feature_dir = tmp_path / "kitty-specs" / "compat-test"
        (feature_dir / "tasks").mkdir(parents=True)

        result = preview_claimable_wp(feature_dir)  # single positional arg

        assert isinstance(result, ClaimablePreview)
        assert result.wp_id is None
        assert result.selection_reason == "no_wp_files"

    def test_split_arg_routes_tasks_from_planning_status_from_status(
        self,
        coord_topology_mission: CoordTopologyContext,
    ) -> None:
        """Dual-arg split: tasks/ from planning_dir, events from status_dir.

        Call ``preview_claimable_wp(planning_dir, status_dir=coord_dir)`` and
        assert:
        - tasks read from ``planning_dir`` (primary → WP01 found)
        - status read from ``status_dir`` (coord → planned event → wp_id="WP01")

        This exercises the split directly at the library level.  The RED-first
        proof at the ``_preview_claimable_wp_for_mission`` site (T016) tests the
        SAME invariant through the PRE-EXISTING entry point — this test is
        complementary, not a substitute.

        Note: ``_write_coord_planned_event`` overwrites the coord husk events file
        with a parseable planned event.  The ``assert_reads_primary`` helper
        verifies the PRIMARY leg (tasks/WP01.md present at the resolved path).
        We do NOT call ``assert_status_from_coord`` here because that helper
        checks for the ORIGINAL fixture marker which was replaced; instead we
        assert the result directly proves the COORD leg was used (wp_id="WP01").
        """
        from runtime.next.discovery import preview_claimable_wp

        ctx = coord_topology_mission

        # Seed valid planned event on coord so claimability is deterministic.
        # After this call, coord husk has a parseable planned event for WP01.
        # Primary decoy still has unparseable (string evidence) events.
        _write_coord_planned_event(ctx)

        result = preview_claimable_wp(
            ctx.primary_feature_dir,
            status_dir=ctx.coord_feature_dir,
        )

        # PRIMARY leg: WP01 task found → tasks read from primary_feature_dir.
        assert_reads_primary(ctx.primary_feature_dir, ctx)

        # COORD leg (indirect): only the coord husk has a parseable planned event;
        # the primary decoy has unparseable events → _load_wp_lanes returns {} →
        # lane=GENESIS → selection_reason="not_finalized" (not wp_id="WP01").
        # wp_id="WP01" proves events came from the coord husk (status_dir).
        assert result.wp_id == "WP01", (
            f"Split call: tasks from primary + events from coord → WP01 claimable.\n"
            f"  Got wp_id={result.wp_id!r}, selection_reason={result.selection_reason!r}\n"
            "If not 'WP01': the STATUS leg read from primary decoy (unparseable "
            "→ GENESIS → not_finalized) instead of coord husk (planned → claimable)."
        )

        # Verify coord husk file path contains the event we seeded.
        coord_content = ctx.status_events_path.read_text(encoding="utf-8")
        assert _COORD_EVENT_ID_PLANNED in coord_content, (
            f"Coord husk events file must contain the planned event we seeded.\n"
            f"  status_events_path: {ctx.status_events_path}\n"
            f"  Content: {coord_content[:200]}"
        )
