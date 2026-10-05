"""Executor coord-reconcile marker/heal integration tests (WP03, #2786 + #2367-B).

Un-marked ``@pytest.mark.regression`` (landing fold: make
``@pytest.mark.regression`` mean exactly one thing). This module is a
PERMANENT integration test suite for the WP03 executor wiring, not a
red-first P0 reproduction — it is expected to stay green.

These cover the executor wiring WP03 adds on top of WP02's coordination
primitives:

* the ``pending_coord_reconcile`` marker is written at BOTH strand sites (the
  #2367-B bake-mid-write-set failure and the #2786 revert-failure) via the
  ``_restore_and_guard_coord_coherence`` restore primitive — mark-not-raise, so
  the original fault still propagates and the leg-b byte-restore still runs;
* the marker's ``stranded_wp_ids`` names the SPECIFIC stranded WP on a >=2-WP
  fixture (the coherent, only-``approved`` WP excluded) AND excludes a
  genuinely-pre-existing-``done`` WP — falsifying both a hardcoded list and
  ``run.all_wp_ids`` (the derivation contract, data-model);
* ``_heal_pending_coord_reconcile`` reconciles the committed coord ref back to
  the byte-restored working tree and clears the marker atomically; a second
  resume is a strand-gated no-op leaving the committed ``status.events.jsonl``
  byte-stable (NFR-002).

Re-pinned for #5385 (single rollback door): the driver now restores the
coordination branch after the phase-level byte restore + mark, so a strand only
survives the run when the door CANNOT restore that branch. The phase-level
marker is observed at the failing phase's exit (``on_phase_failure``); the
heal cases make another actor move the coordination branch before the door
runs (``foreign_coord_commit``), the successor of the retired forced
``git revert`` failure.

The heavy coord-topology full-merge harnesses (fixture bootstrap + failure
injection + git-reducible committed/working readers) are REUSED verbatim from
the WP01 red-first repros so this module never re-authors them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

# Import the status package before any coordination submodule (production import
# order; see the #2711 harness docstring).
import specify_cli.status  # noqa: F401  # import-order guard

from specify_cli.consolidation import executor as ex
from specify_cli.consolidation.state import ConsolidationState, load_state
from specify_cli.status import Lane

# --- Reused bake-strand (#2367-B) harness -----------------------------------
# (relocated from tests/regression/ in the 2026-08 landing fold, once the
# defect closed and this became a permanent guard living with its siblings
# in tests/merge/)
from tests.consolidation.test_issue_2367_bake_strand import (
    COHERENT_WP,
    COORD_BRANCH,
    MISSION_ID,
    MISSION_SLUG,
    STRANDED_WP,
    _bootstrap_two_wp_coord_mission,
    _committed_coord_events,
    _git,
    _init_git_repo,
    _lane_on,
    _run_bake_failing_merge,
    _working_coord_events,
    foreign_coord_commit,
    marker_wps,
    on_phase_failure,
)
from tests.consolidation.test_issue_2367_bake_strand import MID8
from specify_cli.consolidation import done_bookkeeping

# --- Reused revert-failure (#2786) harness ----------------------------------
# (relocated from tests/regression/ in the same landing fold)
from tests.consolidation.test_issue_2786_revert_failure_split_brain import (
    _reduce_coord_lanes,
    _run_merge_with_target_failing,
)
from tests.consolidation.test_issue_2711_merge_rollback_resume_coherence import (
    MISSION_ID as REVERT_MISSION_ID,
    WP_ID as REVERT_WP_ID,
    _bootstrap_coord_mission as _bootstrap_revert_mission,
    _init_git_repo as _init_revert_repo,
)
from specify_cli.consolidation import (
    coord_strand,
    phase_advance,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]


def _committed_status_events_blob(repo: Path) -> str:
    """Raw committed ``status.events.jsonl`` on the coordination branch."""
    return _git(
        repo, "show", f"{COORD_BRANCH}:kitty-specs/{MISSION_SLUG}/status.events.jsonl"
    ).stdout


def _marker(repo: Path, mission_id: str) -> dict[str, object] | None:
    state = load_state(repo, mission_id)
    assert state is not None, "merge state.json must exist after a strand pass"
    return state.pending_coord_reconcile


# ---------------------------------------------------------------------------
# T011 — bake strand: marker names the SPECIFIC WP; mark-not-raise; leg-b ran
# ---------------------------------------------------------------------------


def test_bake_strand_marks_specific_wp_and_excludes_coherent(tmp_path: Path) -> None:
    """A #2367-B bake-mid-write-set failure marks EXACTLY the stranded WP.

    The >=2-WP fixture strands ``STRANDED_WP`` (its ``done`` committed before the
    abort) while ``COHERENT_WP`` is only ever ``approved``. The marker's
    ``stranded_wp_ids`` must name only the stranded WP — a hardcoded ``["WP01"]``
    happens to match here, but the exclusion of the coherent WP is the load-bearing
    half (the ``all_wp_ids`` falsification is pinned separately below).
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _bootstrap_two_wp_coord_mission(repo)
    at_phase_exit: dict[str, dict[str, object] | None] = {}

    def observe() -> None:
        at_phase_exit["marker"] = _marker(repo, MISSION_ID)

    with on_phase_failure("_phase_bake_and_pre_target_done", observe):
        exc, _calls = _run_bake_failing_merge(repo)

    # Mark-not-raise: the ORIGINAL bake fault propagated (the mark did not swallow
    # it nor raise a different error).
    assert isinstance(exc, RuntimeError), f"expected the injected bake fault; got {exc!r}"

    # #5385: observed at the bake phase's exit, before the driver's rollback door.
    marker = at_phase_exit["marker"]
    assert marker is not None, "the bake strand must write a pending_coord_reconcile marker"
    assert marker["stranded_wp_ids"] == [STRANDED_WP], marker["stranded_wp_ids"]
    assert COHERENT_WP not in marker["stranded_wp_ids"]  # type: ignore[operator]
    assert marker["revert_error"], "the marker should carry the swallowed fault text"
    assert marker["captured_sha"], "the marker must carry the pre-bake coord tip"
    assert marker_wps(repo) is None, "#5385: the door restored the coordination branch and cleared the marker"


def test_bake_strand_leg_b_byte_restore_still_runs(tmp_path: Path) -> None:
    """Mark-not-raise (FR-005): the working tree byte-restore still rolls back.

    The stranded WP's committed coord ``done`` survives (the strand), but the
    coordination worktree's WORKING event log is byte-restored to ``approved`` —
    proving the mark did not short-circuit the leg-b restore.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _bootstrap_two_wp_coord_mission(repo)
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    at_phase_exit: dict[str, Lane] = {}

    def observe() -> None:
        at_phase_exit["working"] = _lane_on(_working_coord_events(repo), STRANDED_WP)
        at_phase_exit["committed"] = _lane_on(_committed_coord_events(repo, feature_dir), STRANDED_WP)

    with on_phase_failure("_phase_bake_and_pre_target_done", observe):
        _run_bake_failing_merge(repo)

    # #5385: observed at the bake phase's exit, before the driver's rollback door.
    assert at_phase_exit["working"] == Lane.APPROVED, "leg-b restore must run"
    assert at_phase_exit["committed"] == Lane.DONE, "the strand must exist before the door"
    # After the door: the coordination branch is restored, both legs agree.
    assert _lane_on(_committed_coord_events(repo, feature_dir), STRANDED_WP) == Lane.APPROVED
    assert _lane_on(_working_coord_events(repo), STRANDED_WP) == Lane.APPROVED


# ---------------------------------------------------------------------------
# T011 — pre-existing-done exclusion (falsifies an ``all_wp_ids`` candidate set)
# ---------------------------------------------------------------------------


def test_write_set_excludes_pre_existing_done_wp(tmp_path: Path) -> None:
    """The marker candidate set is THIS merge's write-set, NOT ``all_wp_ids``.

    After a bake strand, ``STRANDED_WP`` is durably ``done`` on the committed coord
    ref. A *subsequent* merge over ``[STRANDED_WP, "WPZZ"]`` must treat
    ``STRANDED_WP`` as pre-existing-``done`` and DROP it from the write-set — so a
    strand of ``WPZZ`` would never re-revert the legitimately-done ``STRANDED_WP``.
    This is the case a naive ``run.all_wp_ids`` candidate set fails (data-model
    non-fakeable derivation contract).
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _bootstrap_two_wp_coord_mission(repo)
    # #5385: a failed merge no longer leaves a committed ``done`` behind (the door
    # restores the coordination branch), so commit STRANDED_WP's ``done`` through
    # the REAL per-WP done emit (a legitimately-done WP from an earlier merge).
    done_bookkeeping._mark_wp_merged_done(repo, MISSION_SLUG, STRANDED_WP, "main")

    # STRANDED_WP is now durably done on the committed coord ref (pre-existing for
    # any subsequent merge). Build a minimal run over [STRANDED_WP, WPZZ].
    state = ConsolidationState(
        mission_id=MISSION_ID,
        mission_slug=MISSION_SLUG,
        target_branch="main",
        wp_order=[STRANDED_WP, "WPZZ"],
    )
    run = _make_min_run(repo, all_wp_ids=[STRANDED_WP, "WPZZ"], state=state)
    run.pre_target_coord_ref = COORD_BRANCH

    coord_strand._capture_pre_target_done_write_set(run)

    assert STRANDED_WP not in run.pre_target_done_write_set, (
        "a genuinely-pre-existing-done WP must be excluded from the write-set — "
        f"got {run.pre_target_done_write_set}"
    )
    assert run.pre_target_done_write_set == ["WPZZ"], run.pre_target_done_write_set


def _make_min_run(
    repo: Path, *, all_wp_ids: list[str], state: ConsolidationState
) -> ex._MergeRunState:
    from types import SimpleNamespace

    lanes_manifest = SimpleNamespace(
        target_branch="main",
        mission_branch=COORD_BRANCH,
        lanes=[SimpleNamespace(lane_id="lane-a", wp_ids=all_wp_ids)],
    )
    return ex._MergeRunState(
        main_repo=repo,
        mission_slug=MISSION_SLUG,
        canonical_id=MISSION_ID,
        canonical_mission_id=MISSION_ID,
        feature_dir=repo / "kitty-specs" / MISSION_SLUG,
        target_feature_dir=repo / "kitty-specs" / MISSION_SLUG,
        lanes_manifest=lanes_manifest,
        all_wp_ids=all_wp_ids,
        push=False,
        delete_branch=False,
        remove_worktree=False,
        strategy=ex.MergeStrategy.SQUASH,
        assume_yes=True,
        planning_artifact_only=False,
        state=state,
        is_resume=False,
    )


# ---------------------------------------------------------------------------
# T011 — resume heal: committed == working + marker cleared; byte-stable resume
# ---------------------------------------------------------------------------


def test_bake_strand_resume_heals_and_clears(tmp_path: Path) -> None:
    """A ``merge --resume`` heals the bake strand and clears the marker (FR-006)."""
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _bootstrap_two_wp_coord_mission(repo)

    # #5385: another actor moves the coordination branch before the door runs, so
    # the door cannot restore it and the strand + marker survive for the heal.
    with on_phase_failure("_phase_bake_and_pre_target_done", lambda: foreign_coord_commit(repo, MISSION_SLUG, MID8)):
        _run_bake_failing_merge(repo)
    assert _marker(repo, MISSION_ID) is not None, "pass 1 must strand + mark"

    # Resume: the same injected fault re-raises, but the heal reconciles the strand.
    _run_bake_failing_merge(repo)

    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    committed = _lane_on(_committed_coord_events(repo, feature_dir), STRANDED_WP)
    working = _lane_on(_working_coord_events(repo), STRANDED_WP)
    assert committed == working == Lane.APPROVED, (
        f"heal must reconcile committed=={working}; got committed={committed}"
    )
    assert _marker(repo, MISSION_ID) is None, "the marker must be cleared after the heal"


def test_resume_twice_is_byte_stable(tmp_path: Path) -> None:
    """Resuming twice yields a byte-identical committed coord ``status.events.jsonl``.

    NFR-002 idempotency: the ``stranded+marked -> coherent`` and
    ``already-coherent -> no-op clear`` edges converge — a second resume is a
    strand-gated no-op, so the committed event-log bytes do not churn.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _bootstrap_two_wp_coord_mission(repo)

    # #5385: pass 1 strands only when the door cannot restore the coordination branch.
    with on_phase_failure("_phase_bake_and_pre_target_done", lambda: foreign_coord_commit(repo, MISSION_SLUG, MID8)):
        _run_bake_failing_merge(repo)  # pass 1: strand
    assert _marker(repo, MISSION_ID) is not None, "pass 1 must strand + mark"
    _run_bake_failing_merge(repo)  # pass 2: heal
    blob_after_first_resume = _committed_status_events_blob(repo)

    _run_bake_failing_merge(repo)  # pass 3: idempotent no-op heal
    blob_after_second_resume = _committed_status_events_blob(repo)

    assert blob_after_second_resume == blob_after_first_resume, (
        "a second resume must leave the committed coord status.events.jsonl "
        "byte-identical (idempotent heal, NFR-002)"
    )


# ---------------------------------------------------------------------------
# T011 — revert-failure strand (#2786): marks, then a resume heals
# ---------------------------------------------------------------------------


def test_unrestorable_coordination_strand_marks_and_resume_reconciles(tmp_path: Path) -> None:
    """The #2786 strand site's successor: the door cannot restore the coordination branch.

    Exercises the OTHER strand site (the target-advance failure after the pre-target
    ``done`` commit), driven through the same restore primitive. Pre-#5385 the
    trigger was a forced ``git revert`` failure; that revert no longer exists. Now
    another actor moves the coordination branch before the door runs, so the door
    reports it NOT restored, the marker stays, and the resume-start heal reconciles
    the strand (``committed == working``) and clears the marker.
    """
    repo = tmp_path / "repo"
    _init_revert_repo(repo)
    feature_dir = _bootstrap_revert_mission(repo)

    _run_merge_with_target_failing(repo, coord_moved_by_another_actor=True)  # pass 1: strand
    marker = _marker(repo, REVERT_MISSION_ID)
    assert marker is not None, "an unrestorable coordination branch must keep the marker"
    assert marker["stranded_wp_ids"] == [REVERT_WP_ID], marker["stranded_wp_ids"]

    _run_merge_with_target_failing(repo, coord_moved_by_another_actor=False)  # pass 2: resume heal
    committed_lane, working_lane = _reduce_coord_lanes(repo, feature_dir)
    assert committed_lane == working_lane == Lane.APPROVED, (
        "resume must reconcile the strand to a coherent committed==working; "
        f"got committed={committed_lane} working={working_lane}"
    )
    assert _marker(repo, REVERT_MISSION_ID) is None, "the heal clears the marker once the strand is reconciled"


def test_resume_preserves_marker_when_coord_worktree_pruned(tmp_path: Path) -> None:
    """A pruned coord worktree must PRESERVE the marker on resume (debugger-debbie HIGH).

    ``repair_coord_strand`` short-circuits ``worktree_missing`` BEFORE its strand
    gate, so its empty ``stranded_wp_ids`` means "strand UNCHECKED", NOT "coherent".
    Clearing the marker on that empty set (the pre-fix ``not outcome.stranded_wp_ids``
    condition) would erase an UNRESOLVED committed split-brain — invisible to a later
    doctor/resume once the worktree is re-materialized. The heal must leave the marker.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    (repo / "kitty-specs" / MISSION_SLUG).mkdir(parents=True)
    marker = {
        "coord_ref": COORD_BRANCH,
        "captured_sha": "deadbeef",
        "coord_worktree": str(tmp_path / "pruned-coord-wt"),  # does NOT exist
        "stranded_wp_ids": [STRANDED_WP],
        "revert_error": "injected",
        "detected_at": "2026-07-18T10:00:00+00:00",
    }
    state = ConsolidationState(
        mission_id=MISSION_ID,
        mission_slug=MISSION_SLUG,
        target_branch="main",
        wp_order=[STRANDED_WP],
        current_wp=STRANDED_WP,
        pending_coord_reconcile=marker,
    )
    run = _make_min_run(repo, all_wp_ids=[STRANDED_WP], state=state)
    run.is_resume = True

    ex._heal_pending_coord_reconcile(run)

    assert run.state.pending_coord_reconcile is not None, (
        "a pruned coord worktree must PRESERVE the marker (worktree_missing is NOT "
        "coherence) — clearing it erases an unresolved committed split-brain"
    )


def test_completed_mission_resume_keeps_primary_events_path(tmp_path: Path) -> None:
    """R1d: a completed coordination Mission's resume keeps the PRIMARY events path.

    Characterization of today's ``_phase_baseline_and_surface`` answer. The
    completed-Mission case (``merged_at`` on the repository-root checkout) is
    the sanctioned exception that later steps must preserve: the events path
    is whatever ``resolve_status_surface`` returns, not a re-derived location.
    """
    import json
    from types import SimpleNamespace

    from mission_runtime import MissionTopology

    from specify_cli.consolidation._constants import _STATUS_FILENAME
    from specify_cli.coordination.surface_resolver import is_under_worktrees_segment, resolve_status_surface
    from specify_cli.lanes.single_branch_landing import lands_mission_branch
    from tests._factories.coord_mission import make_prefix_coord_mission

    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    meta_path = coord.root_mission_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["merged_at"] = "2026-10-02T12:00:00+00:00"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    state = ConsolidationState(
        mission_id=coord.mid8,
        mission_slug=coord.mission_slug,
        target_branch=coord.target_branch,
        wp_order=["WP01"],
    )
    lanes_manifest = SimpleNamespace(
        mission_slug=coord.mission_slug,
        target_branch=coord.target_branch,
        mission_branch=coord.coordination_branch,
        lanes=[SimpleNamespace(lane_id="lane-a", wp_ids=["WP01"])],
    )
    run = ex._MergeRunState(
        main_repo=coord.repo_root,
        mission_slug=coord.mission_slug,
        canonical_id=coord.mid8,
        canonical_mission_id=coord.mid8,
        feature_dir=coord.root_mission_dir,
        target_feature_dir=coord.root_mission_dir,
        lanes_manifest=lanes_manifest,
        all_wp_ids=["WP01"],
        push=False,
        delete_branch=False,
        remove_worktree=False,
        strategy=ex.MergeStrategy.SQUASH,
        assume_yes=True,
        planning_artifact_only=False,
        state=state,
        is_resume=True,
    )

    expected = resolve_status_surface(coord.repo_root, coord.mission_slug)
    ex._phase_baseline_and_surface(run)

    assert run.canonical_events_path == expected
    assert expected == coord.root_mission_dir / "status.events.jsonl"
    assert ".worktrees" not in run.canonical_events_path.parts
    assert run.canonical_status_path == expected.parent / _STATUS_FILENAME
    in_worktree = is_under_worktrees_segment(expected) and not run.planning_artifact_only
    assert run.done_marked_before_target is (in_worktree or lands_mission_branch(coord.repo_root, lanes_manifest))


# --- WP18 (ruling Q4): the run's single status authority -------------------


class _RaisingSeam:
    """A ``PlacementSeam`` stand-in whose ``write_dir`` raises *exc* (the refusal under test)."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def write_dir(self, kind: object) -> object:
        raise self._exc


def _branch_refusal_kwargs(tmp_path: Path) -> dict[str, Any]:
    return {
        "repo_root": tmp_path,
        "mission_slug": "m-01ABCDEF",
        "mid8": "01ABCDEF",
        "coordination_branch": "kitty/mission-m-01ABCDEF",
        "coord_candidate": tmp_path / ".worktrees" / "m-coord",
        "primary_candidate": tmp_path / "kitty-specs" / "m-01ABCDEF",
    }


def _status_dir_refusals(tmp_path: Path) -> list[tuple[Exception, str]]:
    from specify_cli.coordination.coord_seed import CoordSeedForkRefused
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted, CoordinationWorktreeUnmaterialized
    from specify_cli.status.locking import FeatureStatusLockTimeoutError

    return [
        (CoordinationBranchDeleted(**_branch_refusal_kwargs(tmp_path)), "Recover the mission's status authority"),
        (CoordinationWorktreeUnmaterialized(**_branch_refusal_kwargs(tmp_path)), "Create the local coordination branch from its remote"),
        (
            CoordSeedForkRefused(
                root_path=tmp_path / "root.jsonl",
                coord_path="kitty-specs/m/status.events.jsonl",
                coord_ref="kitty/mission-m",
                first_divergence_root="01A",
                first_divergence_coord="01B",
                reconcile_steps=("reconcile the logs",),
            ),
            "spec-kitty doctor decisions",
        ),
        (FeatureStatusLockTimeoutError("status lock held", lock_path=tmp_path / "lock"), "Wait for the other status writer"),
    ]


@pytest.mark.parametrize("index", range(4))
def test_resolve_run_status_dir_aborts_cleanly_on_every_write_location_refusal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], index: int
) -> None:
    """Each refusal renders its own message plus the clean-no-op notice and exits 1 -- no traceback."""
    import typer

    exc, hint = _status_dir_refusals(tmp_path)[index]
    seam: Any = _RaisingSeam(exc)

    with pytest.raises(typer.Exit) as raised:
        ex._resolve_run_status_dir(seam)

    assert raised.value.exit_code == 1
    output = " ".join(capsys.readouterr().out.split())
    assert str(exc).split()[0] in output
    assert "Merge aborted before any state change." in output
    assert hint in output
    assert raised.value.__cause__ is exc


def test_resolve_run_status_dir_returns_the_write_location_path(tmp_path: Path) -> None:
    from types import SimpleNamespace

    class _Seam:
        def write_dir(self, kind: object) -> object:
            return SimpleNamespace(path=tmp_path / "kitty-specs" / "m", seed=None)

    seam: Any = _Seam()
    assert ex._resolve_run_status_dir(seam) == tmp_path / "kitty-specs" / "m"


def test_primary_mission_is_merged_reads_the_merge_marker_and_never_raises(tmp_path: Path) -> None:
    import json

    assert phase_advance._primary_mission_is_merged(tmp_path) is False  # no meta.json
    (tmp_path / "meta.json").write_text("{not json", encoding="utf-8")
    assert phase_advance._primary_mission_is_merged(tmp_path) is False  # corrupt meta reads as not merged
    (tmp_path / "meta.json").write_text(json.dumps({"mission_slug": "m"}), encoding="utf-8")
    assert phase_advance._primary_mission_is_merged(tmp_path) is False
    (tmp_path / "meta.json").write_text(
        json.dumps({"mission_slug": "m", "merged_at": "2026-10-02T12:00:00+00:00"}), encoding="utf-8"
    )
    assert phase_advance._primary_mission_is_merged(tmp_path) is True


def test_resolve_run_status_surface_uses_run_feature_dir_unless_completed(tmp_path: Path) -> None:
    """Not completed: the run's own ``feature_dir`` is the only authority (no resolver is consulted)."""
    from types import SimpleNamespace

    feature_dir = tmp_path / "coord-wt" / "kitty-specs" / "m"
    run: Any = SimpleNamespace(
        main_repo=tmp_path,
        mission_slug="m",
        feature_dir=feature_dir,
        target_feature_dir=tmp_path / "kitty-specs" / "m",  # no meta.json -> not completed
    )

    assert phase_advance._completed_mission_projected_events_path(run) is None
    assert phase_advance._resolve_run_status_surface(run) == feature_dir / "status.events.jsonl"
