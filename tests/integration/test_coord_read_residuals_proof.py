"""SC-001 / SC-002 headline coord-topology integration proof (WP04, FR-009).

Mission ``coord-read-residuals-merge-lanes-and-identity-routing-01KW2M8V`` —
Lane A (#2185). This is the **headline acceptance** and the squad's CRITICAL
false-green guard: the load-bearing behavioral backstop for the whole #2185
reframe. Where WP02/WP03 prove each routed *site* in isolation, this file drives
the REAL production functions END-TO-END against the **already-divergent**
sentinel-husk coord fixture and asserts on **returned DOMAIN VALUES**:

* ``materialize_worktree_topology`` → the materialized worktree entries (WP set)
  and resolved identity (the "materialized worktrees" SC-001 output);
* ``run_dry_run_forecast`` → the forecast lane/WP set printed by the merge
  dry-run (the "forecast WP set" SC-001 output);
* ``scan_recovery_state`` → the recovery lane→WP membership.

Three teeth (per FR-009 / SC-001 / SC-002 / NFR-001 / NFR-003 / NFR-004):

1. **HARD divergence triad precondition** — re-asserted BEFORE any routed drive
   (and proven *load-bearing* by :func:`test_divergence_triad_is_falsifiable`):
   the husk lacks ``lanes.json`` + ``tasks/`` AND its ``meta.json`` carries the
   sentinel ``mission_id`` (``6KERGF2ZNFBPR91YEZMARG99KS``) ≠ the resolved
   PRIMARY id. A future non-divergent fixture trips this guard and fails loudly.
2. **Routed PRIMARY reads return PRIMARY domain values, and reverting any routed
   read to the coord-aware resolver makes the domain-value assertion go RED**
   (demonstrated by an *executed* revert, not a comment) — the #2185 regression
   backstop. NO path-equality, NO ``assert_reads_primary`` / ``assert_both_legs``
   helpers as the terminal, NO primary-dir stub (NFR-004): every drive exercises
   the PRIMARY-vs-coord routing decision inside production code against a REAL
   ``git worktree``.
3. **NFR-001 STATUS-from-husk** — the STATUS legs (event log via ``read_events``;
   the executor ``feature_dir`` / ``status_feature_dir`` leg) STILL resolve the
   coord husk, never PRIMARY; a silent STATUS→PRIMARY re-route is caught by an
   executed revert.

Plus **NFR-003 flat-topology parity**: the same reads succeed identically on a
flat (single-branch) mission, where the routing is a structural no-op.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, NoReturn

import pytest
import typer

from tests.integration.coord_topology_fixture import (
    SENTINEL_HUSK_MISSION_ID,
    SENTINEL_HUSK_MISSION_TYPE,
    CoordTopologyContext,
    FlatTopologyContext,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# The PRIMARY values the divergent fixture resolves (distinct from the husk
# sentinel). Bound to the reused implement-loop sibling fixture's primary id
# (NOT this Mission's ``01KW2M8V…``) — see FR-009.
_PRIMARY_MISSION_ID = "01KW2E7AFC0000000000000001"
_PRIMARY_MISSION_TYPE = "software-dev"


class _StopProbe(BaseException):
    """Short-circuit a deep flow once the domain value is captured.

    Subclasses ``BaseException`` (not ``Exception``) so it propagates THROUGH any
    defensive ``except Exception`` in production code — the capture has already
    happened; we only want to stop before the real (heavy) merge work.
    """


# ---------------------------------------------------------------------------
# HARD divergence triad — the false-green guard (re-asserted before every drive)
# ---------------------------------------------------------------------------


def _assert_divergence_triad(ctx: CoordTopologyContext) -> None:
    """Re-assert the HARD divergence triad (FR-009 / T001) BEFORE driving.

    The whole proof is non-falsifiable unless the husk genuinely diverges from
    PRIMARY. This is asserted FIRST on every routed-drive test so that pointing
    the fixture at a non-divergent husk fails LOUDLY here rather than producing a
    silent false-green downstream.
    """
    assert not (ctx.coord_feature_dir / "lanes.json").exists(), (
        "divergence triad violated: coord husk must NOT carry lanes.json (else a husk-landing LANE_STATE read is non-falsifiable)."
    )
    assert not (ctx.coord_feature_dir / "tasks").exists(), (
        "divergence triad violated: coord husk must NOT carry tasks/ (else a husk-landing WORK_PACKAGE_TASK read is non-falsifiable)."
    )
    assert ctx.coord_husk_meta_path is not None and ctx.coord_husk_meta_path.exists(), (
        "divergence triad violated: the sentinel husk meta.json must be present (a present-but-wrong identity, not a missing file)."
    )
    husk_meta = json.loads(ctx.coord_husk_meta_path.read_text(encoding="utf-8"))
    assert husk_meta["mission_id"] == SENTINEL_HUSK_MISSION_ID, (
        f"divergence triad violated: husk meta mission_id must be the sentinel {SENTINEL_HUSK_MISSION_ID!r}, got {husk_meta['mission_id']!r}."
    )
    assert husk_meta["mission_id"] != ctx.mission_id, (
        f"divergence triad violated: husk meta mission_id must DIFFER from the resolved PRIMARY id {ctx.mission_id!r} (else identity proof is non-falsifiable)."
    )
    assert ctx.mission_id == _PRIMARY_MISSION_ID


def test_divergence_triad_precondition(
    coord_topology_mission_sentinel_meta: CoordTopologyContext,
) -> None:
    """The fixture genuinely diverges — the hard precondition for every drive."""
    _assert_divergence_triad(coord_topology_mission_sentinel_meta)


def test_divergence_triad_is_falsifiable(
    coord_topology_mission_sentinel_meta: CoordTopologyContext,
) -> None:
    """Prove the triad is LOAD-BEARING: a non-divergent husk trips the guard.

    Demonstrates (not merely reasons) that :func:`_assert_divergence_triad` fails
    loudly the moment the husk stops diverging — here by copying the PRIMARY
    ``lanes.json`` + ``tasks/`` into the husk (so the husk would shadow primary).
    If a future fixture refactor silently made the husk mirror primary, this guard
    goes RED instead of letting the whole proof pass vacuously.
    """
    ctx = coord_topology_mission_sentinel_meta
    # Sanity: the triad holds on the pristine fixture.
    _assert_divergence_triad(ctx)

    # Make the husk NON-divergent (the false-green scenario the guard must catch).
    shutil.copy2(
        ctx.primary_feature_dir / "lanes.json",
        ctx.coord_feature_dir / "lanes.json",
    )
    shutil.copytree(
        ctx.primary_feature_dir / "tasks",
        ctx.coord_feature_dir / "tasks",
    )

    with pytest.raises(AssertionError, match="divergence triad violated"):
        _assert_divergence_triad(ctx)


# ---------------------------------------------------------------------------
# Revert helper — simulate "revert a routed read to the coord-aware resolver"
# ---------------------------------------------------------------------------


def _revert_resolver_to_coord_aware(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch the placement seam's read projection back to the coord-aware resolver.

    This is the EXECUTED "revert": a kind-BLIND read that always returns the
    topology-aware candidate dir (the STATUS-only ``-coord`` husk for a coord
    mission), exactly as the pre-#2185 code did. Driving a routed PRIMARY read
    under this patch must surface the husk sentinel / empty artifact and flip the
    routed domain-value assertion RED.

    Patched at the SEAM boundary — :meth:`mission_runtime.PlacementSeam.read_dir`,
    the one projection every migrated read site now calls via
    ``placement_seam(...).read_dir(<kind>)``. Patching the class method (rather
    than a per-module ``placement_seam`` binding) reverts every routed site
    uniformly, whether the module imported the factory at module scope
    (``specify_cli.consolidation.forecast``, ``specify_cli.lanes.recovery``) or
    function-locally (``materialize_worktree_topology``) — so the helper needs no
    per-call-site targeting argument.

    The fake's signature MATCHES the real callee ``read_dir(self, kind)``
    exactly; it deliberately does NOT swallow extras with ``**kwargs``, so a
    future signature change on the seam fails LOUDLY here instead of drifting
    silently past this guard.
    """
    from mission_runtime import MissionArtifactKind, PlacementSeam
    from specify_cli.missions._read_path_resolver import (
        candidate_feature_dir_for_mission,
    )

    def _coord_aware(self: PlacementSeam, kind: MissionArtifactKind) -> Path:
        # Kind-BLIND by construction — the pre-#2185 resolver ignored ``kind``.
        _ = kind
        resolved: Path = candidate_feature_dir_for_mission(self.repo_root, self.mission_slug)
        return resolved

    monkeypatch.setattr(PlacementSeam, "read_dir", _coord_aware)


def _reroute_status_leg_to_primary(monkeypatch: pytest.MonkeyPatch, primary_feature_dir: Path) -> None:
    """Re-route ONLY the ``STATUS_STATE`` seam read to PRIMARY (NFR-001 guard).

    The kind-SELECTIVE counterpart of :func:`_revert_resolver_to_coord_aware`:
    it simulates a silent STATUS→PRIMARY re-route while leaving every other
    kind on the real seam, so the resulting domain-value flip is attributable
    to the STATUS leg alone. Every non-STATUS kind delegates to the real
    :meth:`~mission_runtime.PlacementSeam.read_dir` — no path is faked.
    """
    from mission_runtime import MissionArtifactKind, PlacementSeam

    real_read_dir = PlacementSeam.read_dir

    def _rerouted(self: PlacementSeam, kind: MissionArtifactKind) -> Path:
        if kind is MissionArtifactKind.STATUS_STATE:
            return primary_feature_dir
        resolved: Path = real_read_dir(self, kind)
        return resolved

    monkeypatch.setattr(PlacementSeam, "read_dir", _rerouted)


def _spy_seam_read_dir(monkeypatch: pytest.MonkeyPatch, captured: dict[Any, Path]) -> None:
    """Install a PASS-THROUGH spy over the seam's read projection.

    Records ``kind → resolved dir`` for every routed read while the real routing
    decision still happens inside production code (NFR-004: no primary-dir stub).
    """
    from mission_runtime import MissionArtifactKind, PlacementSeam

    real_read_dir = PlacementSeam.read_dir

    def _spy(self: PlacementSeam, kind: MissionArtifactKind) -> Path:
        resolved: Path = real_read_dir(self, kind)
        captured[kind] = resolved
        return resolved

    monkeypatch.setattr(PlacementSeam, "read_dir", _spy)


# ===========================================================================
# T023 — routed PRIMARY reads return PRIMARY domain values (end-to-end), and
#        reverting to coord-aware flips the domain value RED.
# ===========================================================================


def test_materialize_worktree_topology_returns_primary_worktrees(
    coord_topology_mission_sentinel_meta: CoordTopologyContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``materialize_worktree_topology`` returns PRIMARY worktrees + identity.

    Domain value: the materialized ``entries`` WP set and the resolved
    ``mission_type`` / ``mission_slug`` (the SC-001 "materialized worktrees"
    output) — NOT a path equality.

    Revert→RED (executed below): with the resolver reverted to coord-aware the
    single PRIMARY read lands on the husk → no ``tasks/`` (empty topology) and the
    sentinel ``meta.json`` (``mission_type='research'``). The same call then
    returns ``entries=[]`` + sentinel identity, flipping the assertion RED.
    """
    from specify_cli.core.worktree_topology import materialize_worktree_topology

    ctx = coord_topology_mission_sentinel_meta
    _assert_divergence_triad(ctx)

    topo = materialize_worktree_topology(ctx.repo, ctx.slug)

    assert {entry.wp_id for entry in topo.entries} == {"WP01"}, (
        "routed PRIMARY read must materialize WP01 from the PRIMARY tasks/lanes; an empty/other topology means the read regressed to the STATUS-only husk"
    )
    assert topo.mission_type == _PRIMARY_MISSION_TYPE
    assert topo.mission_type != SENTINEL_HUSK_MISSION_TYPE
    assert topo.mission_slug == ctx.slug

    # --- Executed revert→RED demonstration on the headline domain value. ---
    _revert_resolver_to_coord_aware(monkeypatch)  # seam-level (kind-blind read_dir)
    reverted = materialize_worktree_topology(ctx.repo, ctx.slug)
    assert {entry.wp_id for entry in reverted.entries} != {"WP01"}, (
        "REVERT GUARD FAILED: with the read reverted to coord-aware the topology must NOT still resolve WP01 — the routing is not load-bearing."
    )
    assert reverted.mission_type == SENTINEL_HUSK_MISSION_TYPE, (
        f"REVERT GUARD FAILED: the coord-aware read must surface the husk sentinel mission_type {SENTINEL_HUSK_MISSION_TYPE!r}, got {reverted.mission_type!r}"
    )


def test_dry_run_forecast_returns_primary_wp_set(
    coord_topology_mission_sentinel_meta: CoordTopologyContext,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The merge dry-run forecast prints the PRIMARY lane/WP set (``{WP01}``).

    Domain value: the ``lanes`` payload of the forecast JSON the merge dry-run
    emits (the SC-001 "forecast WP set" output), driven END-TO-END through the
    real ``run_dry_run_forecast`` — no faked preflight, no stub.

    Revert→RED (executed below): with the LANE_STATE read reverted to coord-aware
    the forecast lands on the husk (no ``lanes.json``) → ``MissingLanesError`` →
    ``typer.Exit(1)`` and an ``error`` payload, with NO ``lanes`` key — the WP set
    is never produced.
    """
    from specify_cli.consolidation import forecast
    from specify_cli.consolidation.config import MergeStrategy

    ctx = coord_topology_mission_sentinel_meta
    _assert_divergence_triad(ctx)
    # Neutralise the PRIMARY decoy event log: the dry-run review-artifact preflight
    # materialises the PRIMARY status events (WORK_PACKAGE_TASK leg), but the shared
    # fixture seeds a deliberately NON-reducible wrong-leg probe there. The STATUS
    # partition is not under test here (forecast asserts the LANE_STATE WP set), so
    # an empty (reducible) log lets the real preflight run end-to-end.
    (ctx.primary_feature_dir / "status.events.jsonl").write_text("", encoding="utf-8")

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
    payload = json.loads(capsys.readouterr().out.strip())
    forecast_wps = {wp for lane in payload.get("lanes", []) for wp in lane["wp_ids"]}

    assert forecast_wps == {"WP01"}, (
        f"the dry-run forecast must read the PRIMARY lanes.json and forecast its WP set; got {forecast_wps} (empty/other ⇒ the lanes read hit the coord husk)"
    )
    assert "error" not in payload

    # --- Executed revert→RED demonstration on the forecast WP set. ---
    _revert_resolver_to_coord_aware(monkeypatch)
    with pytest.raises(typer.Exit):
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
    reverted_payload = json.loads(capsys.readouterr().out.strip())
    assert "lanes" not in reverted_payload, f"REVERT GUARD FAILED: the coord-aware forecast must NOT still produce a lane/WP set; got {reverted_payload!r}"
    assert "error" in reverted_payload


def test_scan_recovery_state_returns_primary_lane_membership(
    coord_topology_mission_sentinel_meta: CoordTopologyContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``scan_recovery_state`` resolves lane→WP membership off the PRIMARY lanes.json.

    Domain value: the recovery states' ``wp_id`` set (read from the PRIMARY
    ``lanes.json`` / ``tasks/``).

    Revert→RED (executed below): with the PRIMARY leg reverted to coord-aware the
    husk has no ``lanes.json`` → ``_find_wp_ids_for_lane`` returns ``[]`` → the WP
    id falls back to ``'unknown'``, never the PRIMARY ``WP01``.
    """
    from specify_cli.lanes import recovery
    from specify_cli.lanes.branch_naming import code_lane_branch_name
    from specify_cli.lanes.recovery import scan_recovery_state

    ctx = coord_topology_mission_sentinel_meta
    _assert_divergence_triad(ctx)

    lane_branch = code_lane_branch_name(ctx.slug, "lane-a")
    _git_branch(ctx, lane_branch)

    states = scan_recovery_state(ctx.repo, ctx.slug)
    wp_ids = {rs.wp_id for rs in states}

    assert "WP01" in wp_ids, "routed LANE_STATE read must resolve lane-a → WP01 off the PRIMARY lanes.json"
    assert "unknown" not in wp_ids, "the husk fallback ('unknown') means the lanes read regressed to coord-aware"

    # --- Executed revert→RED demonstration on the recovery membership. ---
    _revert_resolver_to_coord_aware(monkeypatch)
    reverted_states = recovery.scan_recovery_state(ctx.repo, ctx.slug)
    reverted_wp_ids = {rs.wp_id for rs in reverted_states}
    assert "WP01" not in reverted_wp_ids, f"REVERT GUARD FAILED: the coord-aware lanes read must NOT still resolve lane-a → WP01; got {reverted_wp_ids}"


# ===========================================================================
# T024 — NFR-001 STATUS-from-husk: the STATUS legs STILL read the coord husk,
#        never PRIMARY; a silent STATUS→PRIMARY re-route is caught.
# ===========================================================================


def test_recovery_status_leg_reads_coord_husk_not_primary(
    coord_topology_mission_sentinel_meta: CoordTopologyContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``scan_recovery_state`` reads the STATUS event log from the COORD husk.

    NFR-001 primary evidence: ``read_events`` is invoked ONLY with the coord husk
    dir during the scan — NEVER the PRIMARY dir — and the resolved
    ``status_lane`` reflects the coord event (a returned domain value).

    Revert-fails guard (executed below): re-routing the STATUS leg to PRIMARY
    (kind-selectively, at the seam's ``read_dir(STATUS_STATE)`` projection) makes
    ``read_events`` read the PRIMARY decoy — whose event carries a non-reducible
    marker — so ``status_lane`` collapses to the ``planned`` default, flipping the
    domain value. A silent STATUS→PRIMARY re-route is caught.
    """
    from specify_cli import status as status_mod
    from specify_cli.lanes import recovery
    from specify_cli.lanes.branch_naming import code_lane_branch_name
    from specify_cli.lanes.recovery import scan_recovery_state

    ctx = coord_topology_mission_sentinel_meta
    _assert_divergence_triad(ctx)

    # Seed a reducible 'claimed' event on the COORD husk (the shared fixture stuffs
    # a non-reducible string marker into evidence — a wrong-leg probe — which the
    # real reducer rejects; the STATUS leg needs a reducible log to yield a lane).
    _seed_reducible_event(ctx.coord_feature_dir, ctx.slug, to_lane="claimed")
    lane_branch = code_lane_branch_name(ctx.slug, "lane-a")
    _git_branch(ctx, lane_branch)

    # Pass-through spy capturing every dir handed to read_events during the scan.
    real_read_events = status_mod.read_events
    seen_dirs: list[Any] = []

    def _spy_read_events(feature_dir: Any) -> Any:
        seen_dirs.append(feature_dir)
        return real_read_events(feature_dir)

    monkeypatch.setattr(status_mod, "read_events", _spy_read_events)

    states = scan_recovery_state(ctx.repo, ctx.slug)
    wp01 = next(rs for rs in states if rs.wp_id == "WP01")

    assert ctx.coord_feature_dir in seen_dirs, "NFR-001: the STATUS leg must read the event log from the COORD husk"
    assert ctx.primary_feature_dir not in seen_dirs, (
        "NFR-001 REGRESSION: a STATUS read was routed to PRIMARY — the event log must stay coord-aware (zero STATUS legs re-routed)"
    )
    assert wp01.status_lane == "claimed", f"the WP status_lane must reflect the COORD husk event (read coord-aware); got {wp01.status_lane!r}"

    # --- Executed revert-fails guard: re-route the STATUS leg to PRIMARY. ---
    seen_dirs.clear()
    _reroute_status_leg_to_primary(monkeypatch, ctx.primary_feature_dir)
    reverted_states = recovery.scan_recovery_state(ctx.repo, ctx.slug)
    reverted_wp01 = next(rs for rs in reverted_states if rs.wp_id == "WP01")
    assert ctx.primary_feature_dir in seen_dirs, "the revert must route the STATUS read to PRIMARY (guard setup sanity)"
    assert reverted_wp01.status_lane != "claimed", (
        "REVERT GUARD FAILED: a silent STATUS→PRIMARY re-route went undetected — the PRIMARY decoy event is non-reducible so status_lane must NOT be 'claimed'"
    )


def test_executor_status_feature_dir_stays_coord_aware(
    coord_topology_mission_sentinel_meta: CoordTopologyContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_run_lane_based_consolidation`` binds its STATUS ``feature_dir`` off the COORD husk.

    The executor threads ``feature_dir`` (the seam's kind-aware
    ``read_dir(STATUS_STATE)`` projection) into ``status_feature_dir`` (the C-001
    KEEP STATUS leg). We spy that projection (pass-through, so the routing decision
    still happens in production) and short-circuit just past the PRIMARY reads, then
    assert the STATUS feature_dir resolves the coord husk — NOT PRIMARY (NFR-001).

    The spy is kind-keyed, so it ALSO pins the per-leg split the executor depends
    on: the same seam hands back PRIMARY for ``LANE_STATE`` / ``PRIMARY_METADATA``
    in the very same call, which a kind-blind stub would have flattened away.
    """
    from mission_runtime import MissionArtifactKind
    from specify_cli.consolidation import executor

    ctx = coord_topology_mission_sentinel_meta
    _assert_divergence_triad(ctx)

    captured: dict[Any, Path] = {}
    _spy_seam_read_dir(monkeypatch, captured)
    monkeypatch.setattr(executor, "require_no_sparse_checkout", lambda **kwargs: None)

    def _stop(*_args: Any, **_kwargs: Any) -> NoReturn:
        raise _StopProbe

    monkeypatch.setattr(executor, "_effective_push_requested", _stop)

    with pytest.raises(_StopProbe):
        executor._run_lane_based_consolidation(
            ctx.repo,
            ctx.slug,
            push=False,
            delete_branch=False,
            remove_worktree=False,
        )

    status_dir = captured.get(MissionArtifactKind.STATUS_STATE)
    assert status_dir == ctx.coord_feature_dir, f"NFR-001: the executor STATUS feature_dir must resolve the COORD husk; got {status_dir!r}"
    assert status_dir != ctx.primary_feature_dir
    # The per-leg split, same call: the PRIMARY-partition kinds must NOT follow
    # the STATUS leg onto the husk (a kind-blind read would land all three there).
    assert captured[MissionArtifactKind.LANE_STATE] == ctx.primary_feature_dir
    assert captured[MissionArtifactKind.PRIMARY_METADATA] == ctx.primary_feature_dir


# ===========================================================================
# T025 — flat-topology parity: the routing is a structural NO-OP (NFR-003).
# ===========================================================================


def test_flat_topology_materialize_is_noop(
    flat_topology_mission: FlatTopologyContext,
) -> None:
    """On a flat mission ``materialize_worktree_topology`` resolves the only surface."""
    from specify_cli.core.worktree_topology import materialize_worktree_topology

    ctx = flat_topology_mission
    topo = materialize_worktree_topology(ctx.repo, ctx.slug)

    assert {entry.wp_id for entry in topo.entries} == {"WP01"}
    assert topo.mission_type == _PRIMARY_MISSION_TYPE
    assert topo.mission_slug == ctx.slug


def test_flat_topology_forecast_is_noop(
    flat_topology_mission: FlatTopologyContext,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On a flat mission the dry-run forecast reads the single-surface lanes.json."""
    from specify_cli.consolidation import forecast
    from specify_cli.consolidation.config import MergeStrategy

    ctx = flat_topology_mission
    # #5385: a flat (coordination-less) mission's done bookkeeping lands on its
    # target, and this fixture's target is the protected ``main``, so the dry-run
    # now reports PROTECTED_BRANCH_REFUSED up front. This test is about which
    # surface lanes.json is read from, so declare ``main`` unprotected.
    monkeypatch.setenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", "1")
    # See test_dry_run_forecast_returns_primary_wp_set: empty the (single-surface)
    # event log so the review-artifact preflight materialises cleanly.
    (ctx.primary_feature_dir / "status.events.jsonl").write_text("", encoding="utf-8")
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
    payload = json.loads(capsys.readouterr().out.strip())
    forecast_wps = {wp for lane in payload.get("lanes", []) for wp in lane["wp_ids"]}

    assert forecast_wps == {"WP01"}
    assert "error" not in payload


def test_flat_topology_recovery_is_noop(
    flat_topology_mission: FlatTopologyContext,
) -> None:
    """On a flat mission ``scan_recovery_state`` resolves lane→WP off the only surface."""
    from specify_cli.lanes.branch_naming import code_lane_branch_name
    from specify_cli.lanes.recovery import scan_recovery_state

    ctx = flat_topology_mission
    lane_branch = code_lane_branch_name(ctx.slug, "lane-a")
    _git_branch(ctx, lane_branch)

    states = scan_recovery_state(ctx.repo, ctx.slug)
    wp_ids = {rs.wp_id for rs in states}

    assert "WP01" in wp_ids
    assert "unknown" not in wp_ids


# ---------------------------------------------------------------------------
# Local helpers (no resolver patching — real git + filesystem)
# ---------------------------------------------------------------------------


def _git_branch(ctx: CoordTopologyContext | FlatTopologyContext, branch: str) -> None:
    """Create a local branch off ``main`` so the recovery live-branch scan runs."""
    import subprocess

    subprocess.run(
        ["git", "-C", str(ctx.repo), "branch", branch, "main"],
        check=True,
        capture_output=True,
        text=True,
    )


def _seed_reducible_event(feature_dir: Any, slug: str, *, to_lane: str) -> None:
    """Write a single reducible status event (``planned`` → *to_lane*) for WP01.

    The shared fixture stuffs a plain-string marker into ``evidence`` (a wrong-leg
    probe) which the real reducer rejects; a coord-aware STATUS read therefore
    needs a reducible log to yield a concrete lane. We overwrite the target dir's
    event log with a production-shaped ``claimed`` event for WP01 — exercising the
    STATUS leg legitimately while leaving the PRIMARY tasks/identity routing under
    test untouched.
    """
    event = {
        "actor": "claude",
        "at": "2026-06-26T00:00:00+00:00",
        "event_id": "01KW2E7AFC00000000000CLAIM",
        "evidence": None,
        "execution_mode": "code_change",
        "feature_slug": slug,
        "force": False,
        "from_lane": "planned",
        "reason": None,
        "review_ref": None,
        "to_lane": to_lane,
        "wp_id": "WP01",
    }
    (feature_dir / "status.events.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")
