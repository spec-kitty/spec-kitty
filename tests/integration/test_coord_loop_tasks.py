"""Integration tests for WP03: tasks.py loop reads routed to planning seam.

Per-site RED-first tests proving the coord-topology routing invariant for each
routed site in ``tasks.py``:

- **PRIMARY leg**: ``tasks/`` and ``tasks.md`` are read from the PRIMARY checkout.
- **STATUS leg**: event log reads stay on the coord husk (C-001 per-leg split).

RED-first proof (documented inline per site): before WP03, the routed sites used
coord-aware resolvers (``resolve_feature_dir_for_mission``,
``resolve_feature_dir_for_slug``) for ``tasks/`` reads.  The coord husk carries NO
``tasks/`` directory — STATUS-only invariant — so all five commands would fail with
"Tasks directory not found" (or "tasks.md not found") when the session topology is
``coord``.  After WP03, ``resolve_planning_read_dir(kind=WORK_PACKAGE_TASK)``
routes the PRIMARY leg to the primary checkout, preserving the STATUS leg on its
original coord-aware resolver (C-001 mixed-read discipline).

Fixture layout (from ``coord_topology_mission``):

* ``primary_feature_dir/``      — meta.json, tasks/WP01.md, lanes.json, DECOY events
* ``coord_feature_dir/``        — status.events.jsonl ONLY (coord marker)
* ``status_events_path``        — coord husk authoritative events file
* ``decoy_events_path``         — primary DECOY events file (distinct content)

**Note on event parseability:** The fixture's ``status.events.jsonl`` events use a
string ``evidence`` field (a marker string), which causes ``StatusEvent.from_dict``
to raise ``TypeError`` when parsed by the real reducer.  CLI tests that need the
reducer to produce a non-default lane replace the coord events file with valid,
parseable events (``evidence=null``).  This is intentional: the fixture is designed
for resolver-level smoke tests, not for full reducer round-trips.

See ``tests/integration/coord_topology_fixture.py`` for fixture details.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from tests.integration.coord_topology_fixture import (
    CoordTopologyContext,
    coord_topology_mission,
)
from tests.mocked_env import setup_mocked_env

# Re-export fixture so pytest discovers it in this module.
__all__ = ["coord_topology_mission"]

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# ---------------------------------------------------------------------------
# ULIDs for test events — real Crockford base32 format (26 chars)
# ---------------------------------------------------------------------------

# Two status-transition events put WP01 at in_progress on the COORD husk.
# The primary DECOY file retains unparseable events (string evidence) from the
# fixture, so a wrong-leg STATUS read yields lane=planned (reducer fallback),
# while the correct coord read produces in_progress.
_COORD_EVENT_ID_1 = "01KW2E7AFC0000000000000001"  # planned → claimed
_COORD_EVENT_ID_2 = "01KW2E7AFC0000000000000002"  # claimed → in_progress


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_coord_in_progress_events(ctx: CoordTopologyContext) -> None:
    """Replace coord husk events with valid parseable events for CLI tests.

    After this call:
    - Coord husk: WP01 at ``in_progress`` (planned→claimed + claimed→in_progress).
    - Primary DECOY: unparseable (string evidence → StoreError → reducer fallback
      ``planned``).  Wrong-leg STATUS reads produce lane=``planned``, correct coord
      reads produce lane=``in_progress`` — a clear per-leg distinction.

    The fixture's original event IDs use non-Crockford characters; the new events
    here use real-format ULID event_ids (per the testing-principles styleguide
    for tests that feed events through the real reducer).
    """
    events = [
        {
            "actor": "coord-fixture",
            "at": "2026-06-26T00:00:00+00:00",
            "event_id": _COORD_EVENT_ID_1,
            "evidence": None,
            "execution_mode": "code_change",
            "feature_slug": ctx.slug,
            "force": False,
            "from_lane": "planned",
            "reason": None,
            "review_ref": None,
            "to_lane": "claimed",
            "wp_id": "WP01",
        },
        {
            "actor": "coord-fixture",
            "at": "2026-06-26T01:00:00+00:00",
            "event_id": _COORD_EVENT_ID_2,
            "evidence": None,
            "execution_mode": "code_change",
            "feature_slug": ctx.slug,
            "force": False,
            "from_lane": "claimed",
            "reason": None,
            "review_ref": None,
            "to_lane": "in_progress",
            "wp_id": "WP01",
        },
    ]
    with ctx.status_events_path.open("w", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event) + "\n")


def _write_tasks_md(feature_dir: Path) -> None:
    """Write a minimal tasks.md with a WP01 section to *feature_dir*.

    ``validate_wp_coverage`` requires every WP file in ``tasks/`` to appear
    as a section in ``tasks.md``.  The fixture creates ``tasks/WP01.md`` but
    NOT ``tasks.md``; this helper provides the required counterpart.
    """
    content = (
        "# Work Packages\n\n"
        "## WP01 - Fixture task\n\n"
        "No dependencies.\n"
    )
    (feature_dir / "tasks.md").write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Site 1 — _map_requirements_feature_dir (T010)
# ---------------------------------------------------------------------------


class TestMapRequirementsRoutesToPrimary:
    """T010: _map_requirements_feature_dir routes tasks-dir leg to PRIMARY."""

    def test_returns_primary_feature_dir(
        self,
        coord_topology_mission: CoordTopologyContext,
    ) -> None:
        """Route via resolve_planning_read_dir(kind=WORK_PACKAGE_TASK) → primary.

        RED-first proof: before WP03, _map_requirements_feature_dir returned
        ``resolve_feature_dir_for_mission(repo_root, slug)`` which, for a
        coord-topology mission, resolves to the STATUS-only coord husk.
        ``husk / "tasks" / "WP01.md"`` does not exist — demonstrating that the
        existence guard on the returned path would correctly fire a
        "Mission directory not found" message for any call site that checks
        ``(resolved / "tasks" / wp_id).exists()``.

        After WP03 the function delegates to
        ``resolve_planning_read_dir(kind=WORK_PACKAGE_TASK)``, which is
        topology-blind (returns PRIMARY regardless of coord worktree state).
        """
        from specify_cli.cli.commands.agent.tasks import _map_requirements_feature_dir

        ctx = coord_topology_mission

        # PRE-FIX behaviour (prove the test was red): the coord-aware resolver
        # returns the husk — no tasks/ on the husk.
        from specify_cli.missions._read_path_resolver import candidate_feature_dir_for_mission

        pre_fix_path = candidate_feature_dir_for_mission(ctx.repo, ctx.slug)
        assert pre_fix_path == ctx.coord_feature_dir, (
            "Pre-fix resolver must return the coord husk (RED anchor)"
        )
        assert not (pre_fix_path / "tasks" / "WP01.md").exists(), (
            "tasks/WP01.md must be absent from coord husk (RED anchor proves test was red)"
        )

        # POST-FIX (current code): must resolve to PRIMARY where tasks/ exists.
        resolved = _map_requirements_feature_dir(ctx.repo, ctx.slug)

        assert resolved == ctx.primary_feature_dir, (
            f"_map_requirements_feature_dir must return primary dir.\n"
            f"  Expected : {ctx.primary_feature_dir}\n"
            f"  Got      : {resolved}"
        )
        assert (resolved / "tasks" / "WP01.md").exists(), (
            "tasks/WP01.md must be present at the resolved primary dir"
        )


# ---------------------------------------------------------------------------
# Site 2 — list_tasks (T010)
# ---------------------------------------------------------------------------


class TestListTasksRoutesToPrimary:
    """T010: ``tasks list`` reads tasks/ from PRIMARY; status lane from COORD."""

    def test_list_tasks_primary_leg_reads_primary_tasks(
        self,
        coord_topology_mission: CoordTopologyContext,
    ) -> None:
        """tasks list --json: WP01 found (primary tasks/) and at in_progress (coord events).

        RED-first proof: before WP03, ``list_tasks`` used
        ``resolve_feature_dir_for_mission(...) / "tasks"`` for the tasks-dir
        read.  For a coord-topology mission this resolves to the STATUS-only
        coord husk, which carries no ``tasks/`` directory.  The command
        exited 1 with "Tasks directory not found: <husk>/tasks".

        After WP03, tasks/ is read from PRIMARY via the kind-aware
        ``placement_seam(...).read_dir(WORK_PACKAGE_TASK)``, while the STATUS
        leg reads ``placement_seam(...).read_dir(STATUS_STATE)`` — the coord
        husk.  Both legs go through the SAME seam, so neither is stubbed: the
        un-stubbed git fixture routes them apart on its own, and the per-leg
        split is proven purely by the returned domain values below (WP01 from
        the PRIMARY ``tasks/``; lane ``in_progress`` from the COORD events).

        Coord events are replaced with valid parseable events (see
        ``_set_coord_in_progress_events``) so the reducer produces WP01 at
        ``in_progress`` from the COORD surface.  The primary DECOY events remain
        unparseable (string evidence) — a wrong-leg read produces lane=``planned``
        (reducer fallback), making the per-leg distinction observable in output.
        """
        from typer.testing import CliRunner

        from specify_cli.cli.commands.agent.tasks import app

        ctx = coord_topology_mission

        # Replace coord events with valid parseable events: WP01 → in_progress.
        _set_coord_in_progress_events(ctx)

        # read-surface-ssot-closeout WP08 / FR-001: BOTH the tasks/ leg and the
        # STATUS leg now route through the SAME kind-aware
        # ``placement_seam(...).read_dir(<kind>)`` in ``tasks.py``. A kind-BLIND
        # seam stub (a single ``read_dir.return_value``) therefore no longer
        # isolates the STATUS leg — it drags the tasks/ read onto the coord husk
        # too, reproducing the very "Tasks directory not found" failure this test
        # exists to forbid. The seam is left UN-stubbed: the real fixture routes
        # ``WORK_PACKAGE_TASK`` → primary and ``STATUS_STATE`` → coord husk, so the
        # per-leg split is exercised inside production code (NFR-004).
        runner = CliRunner()
        with setup_mocked_env(
            ctx.repo,
            mission_slug=ctx.slug,
            workspace_resolution=None,
        ):
            result = runner.invoke(
                app, ["list-tasks", "--mission", ctx.slug, "--json"]
            )

        # PRIMARY leg: exit 0 — tasks/ found on primary; WP01.md readable.
        assert result.exit_code == 0, (
            f"list-tasks must succeed when tasks/ exists on primary checkout.\n"
            f"Output: {result.output}\n"
            f"Exception: {result.exception}"
        )

        data = json.loads(result.output)
        tasks = data["tasks"]
        wp_ids = [t["work_package_id"] for t in tasks]
        assert "WP01" in wp_ids, (
            f"WP01 must appear in list-tasks output (from primary tasks/).\n"
            f"Got wp_ids: {wp_ids}"
        )

        # STATUS leg: lane must be in_progress (from COORD events), not planned
        # (primary DECOY fallback) or genesis (no events).
        wp01 = next(t for t in tasks if t["work_package_id"] == "WP01")
        assert wp01["lane"] == "in_progress", (
            f"WP01 lane must be 'in_progress' (from COORD events, not primary decoy).\n"
            f"Got: {wp01['lane']!r}\n"
            "If 'planned', the STATUS leg is reading the primary DECOY events "
            "(unparseable → reducer fallback) or no events at all."
        )


# ---------------------------------------------------------------------------
# Site 3 — finalize_tasks (T011)
# ---------------------------------------------------------------------------


class TestFinalizeTasksRoutesToPrimary:
    """T011: ``tasks finalize-tasks`` reads tasks.md and tasks/ from PRIMARY."""

    def test_finalize_tasks_primary_leg_reads_primary_tasks_md(
        self,
        coord_topology_mission: CoordTopologyContext,
    ) -> None:
        """tasks finalize-tasks --validate-only: succeeds; WP01 in dependencies.

        RED-first proof: before WP03, ``finalize_tasks`` used
        ``resolve_feature_dir_for_mission(...)`` for the primary leg, resolving
        to the coord husk.  ``husk / "tasks.md"`` does not exist → exit 1 with
        "tasks.md not found: <husk>/tasks.md".

        After WP03, the primary leg uses
        ``resolve_planning_read_dir(kind=WORK_PACKAGE_TASK)`` which returns the
        PRIMARY checkout.  ``primary / "tasks.md"`` exists (created below) and
        ``primary / "tasks"`` has WP01.md → validation passes (exit 0) with
        WP01 present in the dependencies map.

        The STATUS leg (``bootstrap_canonical_state``) stays on the coord-aware
        ``resolve_feature_dir_for_mission``, mocked here to return the coord
        husk.  The husk has no tasks/ → ``total_wps = 0`` in bootstrap output
        (validate-only dry run, no writes).
        """
        from typer.testing import CliRunner

        from specify_cli.cli.commands.agent.tasks import app

        ctx = coord_topology_mission

        # Provide tasks.md on PRIMARY so finalize_tasks can parse dependencies.
        # validate_wp_coverage requires every tasks/WP*.md file to appear as a
        # section in tasks.md; WP01.md exists in the fixture → tasks.md needs
        # a ## WP01 section.
        _write_tasks_md(ctx.primary_feature_dir)

        # read-surface-ssot-closeout WP08 / FR-001: the historical
        # ``placement_seam(...).read_dir(STATUS_STATE)`` seam (replacing the
        # retired kind-blind ``resolve_feature_dir_for_mission``).
        # coord-artifact-single-home-01M3V4BE WP15/T080 (cycle 2, B2/NFR-002):
        # the WRITE leg (``_ft_emit_status_events``) now resolves
        # ``write_dir(STATUS_STATE)`` ONLY when NOT ``--validate-only`` (a
        # mutation — materialize/seed/commit — write_dir must never run in
        # validate-only mode). This fixture runs ``--validate-only``, so
        # ``placement_seam`` must NEVER be called at all; the stub exists only
        # to fail loudly (via the assertion below) if that invariant regresses.
        mock_seam = MagicMock()
        mock_seam.write_dir.return_value = SimpleNamespace(path=ctx.coord_feature_dir)

        runner = CliRunner()
        with (
            setup_mocked_env(
                ctx.repo,
                mission_slug=ctx.slug,
                workspace_resolution=None,
            ),
            patch(
                "specify_cli.cli.commands.agent.tasks_finalize.placement_seam",
                return_value=mock_seam,
            ) as seam_mock,
        ):
            result = runner.invoke(
                app,
                ["finalize-tasks", "--mission", ctx.slug, "--json", "--validate-only"],
            )

        # PRIMARY leg: exit 0 — tasks.md and tasks/ found on primary checkout.
        assert result.exit_code == 0, (
            f"finalize-tasks --validate-only must succeed on a valid primary checkout.\n"
            f"Output: {result.output}\n"
            f"Exception: {result.exception}"
        )

        data = json.loads(result.output)
        assert data.get("result") == "validation_passed", (
            f"Expected result='validation_passed'; got: {data.get('result')!r}"
        )

        # PRIMARY leg: WP01 in dependencies map (parsed from primary tasks.md).
        deps = data.get("dependencies", {})
        assert "WP01" in deps, (
            f"WP01 must appear in dependencies map (parsed from primary tasks.md).\n"
            f"Got dependencies: {deps}"
        )

        # B2/NFR-002: --validate-only must never establish the coordination
        # surface (write_dir materializes/seeds/commits).
        seam_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Site 4 — tasks status (T009)
# ---------------------------------------------------------------------------


class TestTasksStatusRoutesToPrimary:
    """T009: ``tasks status`` reads tasks/ from PRIMARY; events from COORD."""

    def test_tasks_status_primary_leg_reads_primary_tasks(
        self,
        coord_topology_mission: CoordTopologyContext,
    ) -> None:
        """tasks status --json: WP01 found (primary tasks/) and at in_progress (coord events).

        RED-first proof: before WP03, ``status`` used ``feature_dir / "tasks"``
        where ``feature_dir = resolve_handle_to_read_path(...)`` resolves to the
        coord husk for a coord-topology mission.  The coord husk has no ``tasks/``
        → exit 1 with "Tasks directory not found: <husk>/tasks".

        After WP03, the tasks-dir read uses
        ``resolve_planning_read_dir(kind=WORK_PACKAGE_TASK)`` which returns the
        PRIMARY checkout.  The STATUS leg stays on ``resolve_handle_to_read_path``
        (the real topology-aware seam) — unpatched, operating on the real fixture
        git repo so that the coord routing is tested end-to-end.

        ``check_doing_wps_for_staleness`` is patched at the source module to
        return an empty result; without this patch the function calls
        ``get_normalized_wp`` which uses ``resolve_feature_dir_for_slug``
        (coord-routing) → coord husk → no tasks/ → ValueError propagates out of
        the ``MissingLanesError`` handler and exits 1.  The stale-check routing is
        not in scope for WP03 (C-009: do not touch coord_topology, stale_detection
        indirectly affected by the same coord-routing class).

        Coord events are replaced with valid parseable events (see
        ``_set_coord_in_progress_events``) so the reducer produces WP01 at
        ``in_progress`` from the COORD surface.
        """
        from typer.testing import CliRunner

        from specify_cli.cli.commands.agent.tasks import app

        ctx = coord_topology_mission

        # Replace coord events with valid parseable events: WP01 → in_progress.
        _set_coord_in_progress_events(ctx)

        runner = CliRunner()
        with setup_mocked_env(
            ctx.repo,
            mission_slug=ctx.slug,
            workspace_resolution=None,
        ), patch(
            "specify_cli.core.stale_detection.check_doing_wps_for_staleness",
            return_value={},
        ):
            result = runner.invoke(
                app, ["status", "--mission", ctx.slug, "--json"]
            )

        # PRIMARY leg: exit 0 — tasks/ found on primary checkout.
        assert result.exit_code == 0, (
            f"tasks status must succeed when tasks/ exists on primary checkout.\n"
            f"Output: {result.output}\n"
            f"Exception: {result.exception}"
        )

        data = json.loads(result.output)
        wps = data.get("work_packages", [])
        wp_ids = [wp["id"] for wp in wps]
        assert "WP01" in wp_ids, (
            f"WP01 must appear in status output (from primary tasks/).\n"
            f"Got wp_ids: {wp_ids}"
        )

        # STATUS leg: lane must be in_progress (from COORD events), not genesis
        # (no events) or planned (primary DECOY fallback).
        wp01 = next(wp for wp in wps if wp["id"] == "WP01")
        assert wp01["lane"] == "in_progress", (
            f"WP01 lane must be 'in_progress' (from COORD events, not primary decoy).\n"
            f"Got: {wp01['lane']!r}\n"
            "If 'genesis' or 'planned', the STATUS leg is not reading COORD events."
        )


# ---------------------------------------------------------------------------
# Site 5 — list_dependents / build_dependency_graph caller (T012)
# ---------------------------------------------------------------------------


class TestListDependentsRoutesToPrimary:
    """T012: ``tasks list-dependents`` passes primary planning dir to build_dependency_graph."""

    def test_list_dependents_primary_leg_reads_primary_tasks(
        self,
        coord_topology_mission: CoordTopologyContext,
    ) -> None:
        """tasks list-dependents WP01 --json: WP02 (which depends on WP01) detected.

        RED-first proof: before WP03, ``list_dependents`` used
        ``resolve_feature_dir_for_mission(...)`` → coord husk for the
        ``build_dependency_graph`` caller.  The coord husk has no ``tasks/``
        directory; ``build_dependency_graph`` returns ``{}`` (no WPs) →
        ``get_dependents("WP01", {})`` returns ``[]`` → no dependents reported.

        After WP03, ``feature_dir = resolve_planning_read_dir(kind=WORK_PACKAGE_TASK)``
        → PRIMARY.  ``primary / "tasks"`` has WP01.md and WP02.md (added below
        with ``dependencies: [WP01]``); ``build_dependency_graph(primary)``
        returns ``{"WP01": [], "WP02": ["WP01"]}`` → WP02 appears in dependents.

        ``build_dependency_graph``'s signature is unchanged (T012 constraint):
        only the caller in ``list_dependents`` is routed; WP06 owns other callers.
        """
        from typer.testing import CliRunner

        from specify_cli.cli.commands.agent.tasks import app

        ctx = coord_topology_mission

        # Add WP02.md to PRIMARY tasks/ declaring WP01 as a dependency.
        # Without this, WP01 has no dependents and the pre/post-fix output is
        # identical ("no dependents" in both cases).
        wp02_content = (
            "---\n"
            "work_package_id: WP02\n"
            "title: WP02 fixture dependency task\n"
            "dependencies:\n"
            "- WP01\n"
            "---\n"
            "# WP02\n\n"
            "Depends on WP01.\n"
        )
        (ctx.primary_feature_dir / "tasks" / "WP02.md").write_text(
            wp02_content, encoding="utf-8"
        )

        runner = CliRunner()
        with setup_mocked_env(
            ctx.repo,
            mission_slug=ctx.slug,
            workspace_resolution=None,
        ):
            result = runner.invoke(
                app, ["list-dependents", "WP01", "--mission", ctx.slug, "--json"]
            )

        # PRIMARY leg: exit 0 — feature_dir exists (primary dir).
        assert result.exit_code == 0, (
            f"list-dependents must succeed when primary tasks/ has WP01.md.\n"
            f"Output: {result.output}\n"
            f"Exception: {result.exception}"
        )

        data = json.loads(result.output)
        dependents = data.get("dependents", [])
        assert "WP02" in dependents, (
            f"WP02 must appear as a dependent of WP01 (from primary tasks/).\n"
            f"Got dependents: {dependents}\n"
            "If empty, build_dependency_graph read the coord husk (no tasks/) "
            "and returned an empty graph (RED case before WP03)."
        )
