"""RED-first merge-cluster routing tests on the divergent sentinel-husk fixture.

Mission ``coord-read-residuals-merge-lanes-and-identity-routing-01KW2M8V`` —
Lane A (#2185), WP02. Proves the merge-cluster PRIMARY reads
(``merge/forecast.py``, ``merge/executor.py``, ``merge/resolve.py``,
``merge/done_bookkeeping.py``, ``cli/commands/merge.py``) resolve their domain
value off the PRIMARY checkout, NOT the STATUS-only ``-coord`` husk, on a fixture
whose husk carries a PRESENT-but-WRONG ``meta.json`` (the FR-009 sentinel:
``mission_id = 6KERGF2ZNFBPR91YEZMARG99KS``) and NO ``lanes.json`` / ``tasks/``,
distinct from PRIMARY (``mission_id = 01KW2E7AFC0000000000000001``).

Each assertion targets a RETURNED DOMAIN VALUE — the forecast WP set, the
resolved mission identity / canonical merge-state key, or the located WP-task
frontmatter — NOT a resolved-path equality and NOT the fixture's
``assert_reads_primary`` / ``assert_both_legs`` path-equality helpers (per T016).
Reverting any routed read to the coord-aware resolver surfaces the
sentinel/empty husk → the test goes RED.

**NFR-004 (no primary-dir stub):** every test drives the REAL merge functions
against a REAL ``git worktree`` coord fixture. No test hands a primary dir
directly to the function under test — the PRIMARY-vs-coord routing decision is
exercised inside production code; monkeypatches only CAPTURE returned domain
values (they never feed the resolved dir in).

================================================================================
WP02 ROUTE / KEEP map (re-resolved on the lane-b tree, verified)
================================================================================

| Site (re-resolved)                                          | Verdict | Kind            |
|-------------------------------------------------------------|---------|-----------------|
| forecast.py `require_lanes_json` (dry-run)                  | ROUTE   | LANE_STATE      |
| forecast.py review-artifact preflight `feature_dir_for_preview` | ROUTE | WORK_PACKAGE_TASK |
| executor.py `_run_lane_based_merge` preflight identity      | ROUTE   | PRIMARY_METADATA|
| executor.py `_run_lane_based_merge` `require_lanes_json`    | ROUTE   | LANE_STATE      |
| executor.py `_run_lane_based_merge` canonical identity      | ROUTE   | PRIMARY_METADATA|
| executor.py `_run_lane_based_merge_locked` `target_feature_dir` (:887) | KEEP (pre-routed) | PRIMARY |
| executor.py `_phase_baseline_and_surface` `baseline_mission_id` (:324) | ROUTE | PRIMARY_METADATA (#2186 cross-fn residual) |
| executor.py `run.feature_dir` / `status_feature_dir` STATUS legs | KEEP | coord-aware (C-001) |
| resolve.py `_merge_state_key_candidates` identity (:98)     | ROUTE   | PRIMARY_METADATA|
| resolve.py `_resolve_mission_slug` handle canon (:63)       | KEEP    | candidate_ (no-fallback boundary) |
| done_bookkeeping.py WP-path lookup                          | ROUTE   | WORK_PACKAGE_TASK |
| done_bookkeeping.py status-transactional legs               | KEEP    | meta-bearing primary |
| cli/commands/merge.py `--abort` teardown meta read          | ROUTE   | PRIMARY_METADATA|
"""

from __future__ import annotations

from typing import Any, NoReturn

import pytest

from specify_cli.merge.config import MergeStrategy
from specify_cli.merge.state import MergeState
from tests.integration.coord_topology_fixture import (
    SENTINEL_HUSK_MISSION_ID,
    CoordTopologyContext,
    coord_topology_mission_sentinel_meta,
)

# Re-export the fixture so pytest discovers it in this module.
__all__ = ["coord_topology_mission_sentinel_meta"]

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# The PRIMARY mission_id the fixture resolves (distinct from the husk sentinel).
_PRIMARY_MISSION_ID = "01KW2E7AFC0000000000000001"


class _StopProbe(BaseException):
    """Short-circuit a deep merge flow once the domain value is captured.

    Subclasses ``BaseException`` (not ``Exception``) so it propagates THROUGH any
    defensive ``except Exception`` in the production code — the capture has already
    happened; we only want to stop before the real (heavy) merge work.
    """


# ---------------------------------------------------------------------------
# Pre-condition sanity (re-states the falsifiability premise the fixture asserts)
# ---------------------------------------------------------------------------


def test_sentinel_husk_diverges_from_primary(
    coord_topology_mission_sentinel_meta: CoordTopologyContext,
) -> None:
    """Husk lacks lanes.json + tasks/ and carries a sentinel identity ≠ PRIMARY."""
    ctx = coord_topology_mission_sentinel_meta
    assert not (ctx.coord_feature_dir / "lanes.json").exists()
    assert not (ctx.coord_feature_dir / "tasks").exists()
    assert ctx.coord_husk_meta_path is not None and ctx.coord_husk_meta_path.exists()
    assert ctx.mission_id == _PRIMARY_MISSION_ID
    assert SENTINEL_HUSK_MISSION_ID != _PRIMARY_MISSION_ID


# ---------------------------------------------------------------------------
# forecast.py — dry-run lanes (LANE_STATE) + review-artifact preflight (WP-task)
# ---------------------------------------------------------------------------


def test_dry_run_forecast_reads_primary_lane_set(
    coord_topology_mission_sentinel_meta: CoordTopologyContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The dry-run forecast forecasts the PRIMARY lane WP set (``{WP01}``).

    Domain value: the WP set the forecast derives from ``lanes.json`` and hands to
    the review-artifact preflight. The preflight is faked to CAPTURE that set and
    short-circuit (the full status materialize is skipped — the fixture's PRIMARY
    decoy ``status.events.jsonl`` is an intentionally wrong-leg STATUS probe, not a
    production-shaped log, so materializing it is not representative).

    Routed → ``require_lanes_json`` reads PRIMARY → the WP set is ``{WP01}``.
    RED-first: reverting the lanes read to the coord-aware resolver lands on the
    husk (no ``lanes.json``) → ``MissingLanesError`` → ``typer.Exit(1)`` BEFORE the
    preflight, so the set is never captured and ``_StopProbe`` is never raised.
    """
    from specify_cli.merge import forecast

    ctx = coord_topology_mission_sentinel_meta
    captured: dict[str, Any] = {}

    def _fake_preflight(feature_dir: Any, *, wp_ids: Any) -> NoReturn:
        captured["wp_ids"] = list(wp_ids)
        raise _StopProbe

    monkeypatch.setattr(
        forecast, "run_review_artifact_consistency_preflight", _fake_preflight
    )

    with pytest.raises(_StopProbe):
        forecast.run_dry_run_forecast(
            repo_root=ctx.repo,
            resolved_feature=ctx.slug,
            resolved_target_branch="main",
            resolved_strategy=MergeStrategy.SQUASH,
            delete_branch=False,
            remove_worktree=False,
            push=False,
            json_output=True,
        )

    assert set(captured.get("wp_ids", [])) == {"WP01"}, (
        "dry-run forecast must read the PRIMARY lanes.json and forecast its WP set.\n"
        f"  Expected : {{'WP01'}}\n  Got      : {captured.get('wp_ids')}\n"
        "An empty/other set means the lanes read regressed to the coord husk."
    )


# ---------------------------------------------------------------------------
# executor.py — _run_lane_based_merge preflight identity (PRIMARY_METADATA)
# ---------------------------------------------------------------------------


def test_executor_preflight_identity_reads_primary_mission_id(
    coord_topology_mission_sentinel_meta: CoordTopologyContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The sparse-checkout preflight receives the PRIMARY ``mission_id``.

    ``require_no_sparse_checkout`` is faked to CAPTURE the ``mission_id`` it is
    handed (the preflight identity read off ``primary_meta_dir``) and short-circuit.
    Routed → PRIMARY id. RED-first: reverting the preflight identity read to the
    coord-aware ``feature_dir`` surfaces the husk sentinel id.
    """
    from specify_cli.merge import executor

    ctx = coord_topology_mission_sentinel_meta
    captured: dict[str, Any] = {}

    def _fake_require_no_sparse_checkout(**kwargs: Any) -> NoReturn:
        captured["mission_id"] = kwargs.get("mission_id")
        raise _StopProbe

    monkeypatch.setattr(
        executor, "require_no_sparse_checkout", _fake_require_no_sparse_checkout
    )

    with pytest.raises(_StopProbe):
        executor._run_lane_based_merge(
            ctx.repo,
            ctx.slug,
            push=False,
            delete_branch=False,
            remove_worktree=False,
        )

    assert captured.get("mission_id") == _PRIMARY_MISSION_ID, (
        "the merge preflight identity read must resolve the PRIMARY meta.json.\n"
        f"  Expected : {_PRIMARY_MISSION_ID}\n  Got      : {captured.get('mission_id')!r}\n"
        "Got the husk sentinel — the identity read regressed to the coord-aware resolver."
    )
    assert captured["mission_id"] != SENTINEL_HUSK_MISSION_ID


# ---------------------------------------------------------------------------
# executor.py — _run_lane_based_merge lanes (LANE_STATE) + canonical id (META)
# ---------------------------------------------------------------------------


def test_executor_lanes_and_canonical_id_read_primary(
    coord_topology_mission_sentinel_meta: CoordTopologyContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The lanes read succeeds off PRIMARY and the canonical id is the PRIMARY id.

    ``require_no_sparse_checkout`` is neutralised so the flow reaches
    ``require_lanes_json(lanes_read_dir)`` (LANE_STATE) and the canonical
    ``resolve_mission_identity(primary_meta_dir)`` read; ``_effective_push_requested``
    is faked to CAPTURE the ``canonical_id`` and short-circuit.

    Routed → lanes resolve PRIMARY (no ``MissingLanesError``) AND ``canonical_id`` is
    the PRIMARY id. RED-first: reverting the lanes leg raises ``MissingLanesError``
    (husk has no ``lanes.json``) before capture; reverting the identity leg captures
    the husk sentinel id.
    """
    from specify_cli.merge import executor

    ctx = coord_topology_mission_sentinel_meta
    captured: dict[str, Any] = {}

    monkeypatch.setattr(
        executor, "require_no_sparse_checkout", lambda **kwargs: None
    )

    def _fake_effective_push_requested(
        main_repo: object, canonical_id: str, push: bool
    ) -> NoReturn:
        captured["canonical_id"] = canonical_id
        raise _StopProbe

    monkeypatch.setattr(
        executor, "_effective_push_requested", _fake_effective_push_requested
    )

    with pytest.raises(_StopProbe):
        executor._run_lane_based_merge(
            ctx.repo,
            ctx.slug,
            push=False,
            delete_branch=False,
            remove_worktree=False,
        )

    assert captured.get("canonical_id") == _PRIMARY_MISSION_ID, (
        "the merge canonical identity (and the lanes read that precedes it) must "
        "resolve PRIMARY.\n"
        f"  Expected : {_PRIMARY_MISSION_ID}\n  Got      : {captured.get('canonical_id')!r}\n"
        "Got the husk sentinel — the canonical identity read regressed to coord-aware."
    )
    assert captured["canonical_id"] != SENTINEL_HUSK_MISSION_ID


# ---------------------------------------------------------------------------
# resolve.py — _merge_state_key_candidates identity (PRIMARY_METADATA)
# ---------------------------------------------------------------------------


def test_merge_state_key_candidates_use_primary_mission_id(
    coord_topology_mission_sentinel_meta: CoordTopologyContext,
) -> None:
    """The merge-state key candidates carry the PRIMARY ``mission_id``.

    Domain value: the returned key list. Routed → ``[PRIMARY_id, slug]``. RED-first:
    reverting the identity read to ``candidate_feature_dir_for_mission`` lands on the
    husk and returns ``[SENTINEL_id, slug]``.
    """
    from specify_cli.merge.resolve import _merge_state_key_candidates

    ctx = coord_topology_mission_sentinel_meta

    keys = _merge_state_key_candidates(ctx.repo, ctx.slug)

    assert _PRIMARY_MISSION_ID in keys, (
        "the canonical merge-state key must be the PRIMARY mission_id.\n"
        f"  Expected to contain : {_PRIMARY_MISSION_ID}\n  Got keys : {keys}"
    )
    assert SENTINEL_HUSK_MISSION_ID not in keys, (
        "the husk SENTINEL id leaked into the merge-state keys — the identity read "
        "regressed to the coord-aware resolver."
    )


# ---------------------------------------------------------------------------
# done_bookkeeping.py — WP-path lookup (WORK_PACKAGE_TASK)
# ---------------------------------------------------------------------------


def test_mark_wp_merged_done_locates_primary_wp_task(
    coord_topology_mission_sentinel_meta: CoordTopologyContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The WP markdown is located on PRIMARY before merge bookkeeping.

    ``_resolve_wp_path`` is wrapped to CAPTURE the resolved path and short-circuit
    before the status-transaction machinery. Routed → the WP-path lookup resolves
    PRIMARY ``tasks/WP01.md``.
    RED-first: reverting the lookup to the coord-aware resolver lands on the husk
    (no ``tasks/``) → ``_resolve_wp_path`` returns ``None`` → the function returns
    early, the spy observes ``None``, and no primary WP path is captured.
    """
    from specify_cli.merge import done_bookkeeping

    ctx = coord_topology_mission_sentinel_meta
    real_resolve = done_bookkeeping._resolve_wp_path
    captured: dict[str, Any] = {}

    def _spy_resolve(feature_dir: Any, wp_id: str) -> NoReturn:
        captured["wp_path"] = real_resolve(feature_dir, wp_id)
        raise _StopProbe

    monkeypatch.setattr(done_bookkeeping, "_resolve_wp_path", _spy_resolve)

    with pytest.raises(_StopProbe):
        done_bookkeeping._mark_wp_merged_done(ctx.repo, ctx.slug, "WP01", "main")

    assert captured.get("wp_path") == ctx.primary_feature_dir / "tasks" / "WP01.md", (
        "the WP-path lookup must locate tasks/WP01.md on the PRIMARY checkout.\n"
        f"  Got path : {captured.get('wp_path')!r}\n"
        "If absent, the lookup regressed to the STATUS-only coord husk (no tasks/)."
    )


# ---------------------------------------------------------------------------
# cli/commands/merge.py — --abort teardown meta read (PRIMARY_METADATA)
# ---------------------------------------------------------------------------


def test_abort_teardown_reads_primary_meta_not_husk_sentinel(
    coord_topology_mission_sentinel_meta: CoordTopologyContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ``--abort`` coordination teardown reads identity off PRIMARY, never the husk.

    The husk meta carries no ``mid8`` (so the teardown ``mid8`` is identical either
    way on this fixture); the falsifiable domain value is therefore the SET of
    ``mission_id``s observed by ``load_meta`` during the teardown path. Routed → only
    the PRIMARY id is read for identity. RED-first: reverting the meta read to the
    coord-aware resolver reads the husk sentinel id → it appears in the observed set.

    ``load_meta`` is wrapped (pass-through spy — it delegates to the real reader, so
    the routing decision still happens in production code) and the real teardown is
    neutralised to avoid filesystem side-effects.
    """
    from specify_cli import mission_metadata
    from specify_cli.cli.commands.merge import _teardown_coordination_for_abort

    ctx = coord_topology_mission_sentinel_meta
    real_load = mission_metadata.load_meta
    seen_ids: set[str] = set()

    def _spy_load(feature_dir: Any, **kwargs: Any) -> Any:
        meta = real_load(feature_dir, **kwargs)
        if isinstance(meta, dict):
            mission_id = meta.get("mission_id")
            if isinstance(mission_id, str) and mission_id:
                seen_ids.add(mission_id)
        return meta

    monkeypatch.setattr(mission_metadata, "load_meta", _spy_load)
    monkeypatch.setattr(
        "specify_cli.coordination.teardown.teardown_coordination_topology",
        lambda *args, **kwargs: None,
    )

    state = MergeState(
        mission_id=ctx.mission_id,
        mission_slug=ctx.slug,
        target_branch="main",
        wp_order=[],
    )
    _teardown_coordination_for_abort(ctx.repo, ctx.slug, (ctx.mission_id, state))

    assert _PRIMARY_MISSION_ID in seen_ids, (
        "the --abort teardown must read the PRIMARY meta.json identity.\n"
        f"  Observed mission_ids : {seen_ids}"
    )
    assert SENTINEL_HUSK_MISSION_ID not in seen_ids, (
        "the husk SENTINEL id was read during --abort teardown — the meta read "
        "regressed to the coord-aware resolver (the STATUS-only husk)."
    )


# ---------------------------------------------------------------------------
# executor.py — _phase_baseline_and_surface baseline_mission_id (PRIMARY_METADATA)
#
# Cross-function residual the census + same-function call-shape arm MISSED
# (#2186): ``run.feature_dir`` is the coord-aware STATUS dir bound in
# ``_run_lane_based_merge`` (one function up) and threaded onto the run; the
# baseline phase consumed it for an IDENTITY read. Same-function-binding checks
# never flagged it. BEHAVIORAL backstop with an executed RED-on-revert.
# ---------------------------------------------------------------------------


def test_executor_baseline_identity_reads_primary_mission_id(
    coord_topology_mission_sentinel_meta: CoordTopologyContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_phase_baseline_and_surface`` captures the PRIMARY ``baseline_mission_id``.

    ``run.baseline_mission_id`` is a PRIMARY_METADATA read (#2186). The gate +
    lane-merge phases that precede the baseline phase are neutralised so the flow
    reaches it with a PRODUCTION-constructed ``run`` whose ``target_feature_dir`` is
    the real ``primary_feature_dir_for_mission`` anchor resolved at :889 (NFR-004:
    the PRIMARY-vs-coord choice runs in production; we only capture). We capture the
    resolved id in the next phase and short-circuit.

    Routed → the PRIMARY id. RED-on-revert (structurally guaranteed by the divergent
    sentinel fixture, and confirmed by an executed source revert of :324 back to
    ``run.feature_dir``): reading off the coord-aware STATUS leg lands on the husk
    sentinel meta → the captured id is ``6KERGF2ZNFBPR91YEZMARG99KS`` ≠ the PRIMARY id.
    """
    from specify_cli.merge import executor

    ctx = coord_topology_mission_sentinel_meta
    captured: dict[str, Any] = {}

    # Neutralise the heavy phases that precede the baseline phase. The run is still
    # CONSTRUCTED by production ``_run_lane_based_merge_locked`` (so target_feature_dir
    # is the real primary anchor); only the gate/merge work is skipped.
    monkeypatch.setattr(executor, "require_no_sparse_checkout", lambda **kwargs: None)
    # The review-artifact preflight (run BEFORE the phases) materializes the coord
    # husk STATUS log, which the shared fixture seeds as a deliberately non-reducible
    # wrong-leg probe — not under test here. Neutralise it so the flow reaches the
    # baseline phase; the STATUS partition is exercised by the NFR-001 tests.
    monkeypatch.setattr(
        executor, "_enforce_review_artifact_consistency", lambda **kwargs: None
    )
    monkeypatch.setattr(executor, "_phase_gates_and_state", lambda run: None)
    monkeypatch.setattr(executor, "_phase_merge_lanes", lambda run: None)

    def _capture_after_baseline(run: Any) -> NoReturn:
        captured["baseline_mission_id"] = run.baseline_mission_id
        raise _StopProbe

    monkeypatch.setattr(
        executor, "_phase_bake_and_pre_target_done", _capture_after_baseline
    )

    with pytest.raises(_StopProbe):
        executor._run_lane_based_merge(
            ctx.repo,
            ctx.slug,
            push=False,
            delete_branch=False,
            remove_worktree=False,
        )

    assert captured.get("baseline_mission_id") == _PRIMARY_MISSION_ID, (
        "the merge baseline identity read must resolve the PRIMARY meta.json.\n"
        f"  Expected : {_PRIMARY_MISSION_ID}\n"
        f"  Got      : {captured.get('baseline_mission_id')!r}\n"
        "Got the husk sentinel — the baseline read regressed to the coord-aware "
        "run.feature_dir STATUS leg."
    )
    assert captured["baseline_mission_id"] != SENTINEL_HUSK_MISSION_ID
