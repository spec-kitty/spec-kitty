"""FR-007 / US4 (#2939): ``move-task`` leaves a CLEAN tree after emitting a
post-transition ``InnerStateChanged`` annotation on a coord-topology mission.

The bug: on a coordination topology the lane transition is committed (via the
``BookkeepingTransaction`` inside ``emit_status_transition_transactional``), but
the post-transition annotation ``_mt_emit_runtime_state`` emits — the rejected-
review claim-release / review-override (and, on a ``->for_review`` hop, a note) —
was written and materialized to the coord ``status.events.jsonl`` / ``status.json``
yet NEVER committed. So ``move-task`` returned with a dirty coord status tree.

These are RED-before / GREEN-after e2e tests driven through the REAL
``_do_move_task`` orchestrator against the REAL coord worktree built by
``tests/integration/coord_topology_fixture.py`` (``_build_coord_topology``) — no
resolver is patched; the topology dimension is genuine. The ``commit_status`` leg
uses the REAL ``RealCoordCommitRouter`` (wrapped by ``_FaultInjectableCoordRouter``
in non-failing mode), so "committed" / "dirty" is proven via ``git status`` on the
coord worktree, never a mock.

A non-coord (flat) control asserts the annotation still lands (no behaviour change
where there is no coord surface to commit to).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.cli.commands.agent.tasks import _do_move_task, _MoveTaskArgs
from specify_cli.status import materialize as _materialize
from tests.integration.coord_topology_fixture import (
    CoordTopologyContext,
    FlatTopologyContext,
    _build_coord_topology,
    flat_topology_mission,
)
from tests.integration.test_review_durability_matrix import (
    _REVIEW_GATE_BYPASS,
    _coord_cell_ports,
    _disable_branch_protection_for_coord_cell,
    _seed_coord_wp_in_review,
)
from tests.mocked_env import setup_mocked_env
from tests.specify_cli.cli.commands.agent.test_move_task_durability import (
    _FaultInjectableCoordRouter,
    _seed_wp_event,
)

# Re-export the flat fixture so pytest discovers it in this module.
__all__ = ["flat_topology_mission"]

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_WP_ID = "WP01"
# The two coord STATUS files the annotation dirties when it is not committed.
_STATUS_FILES = ("status.events.jsonl", "status.json")


# ---------------------------------------------------------------------------
# Coord-worktree git helpers (scoped to the coord husk working tree)
# ---------------------------------------------------------------------------


def _coord_worktree_root(ctx: CoordTopologyContext) -> Path:
    """The coord worktree root (``coord_feature_dir`` = ``<root>/kitty-specs/<slug>``)."""
    return ctx.coord_feature_dir.parents[1]


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _commit_coord_baseline(ctx: CoordTopologyContext, message: str) -> None:
    """Materialize + commit everything on the coord worktree so it starts CLEAN.

    The fixture leaves the coord husk ``status.events.jsonl`` UNTRACKED; without
    this the clean-tree assertion could never be meaningful. Materializing
    ``status.json`` first mirrors production's post-write snapshot so the baseline
    is a realistic committed state.
    """
    _materialize(ctx.coord_feature_dir)
    root = _coord_worktree_root(ctx)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", message)


def _coord_status_porcelain(ctx: CoordTopologyContext) -> str:
    """``git status --porcelain`` on the coord worktree, scoped to the STATUS files."""
    root = _coord_worktree_root(ctx)
    rels = [f"kitty-specs/{ctx.slug}/{name}" for name in _STATUS_FILES]
    return _git(root, "status", "--porcelain", "--", *rels)


# ---------------------------------------------------------------------------
# Drivers through the real command surface
# ---------------------------------------------------------------------------


def _run_move(
    ctx: CoordTopologyContext,
    router: _FaultInjectableCoordRouter,
    *,
    to: str,
    review_feedback_file: Path | None = None,
    note: str | None = None,
) -> None:
    with setup_mocked_env(
        ctx.repo,
        mission_slug=ctx.slug,
        target_branch="main",
        extra_patches=dict(_REVIEW_GATE_BYPASS),
    ):
        _do_move_task(
            _MoveTaskArgs(
                task_id=_WP_ID,
                to=to,
                mission=ctx.slug,
                agent=None,
                assignee=None,
                shell_pid=None,
                note=note,
                review_feedback_file=review_feedback_file,
                approval_ref=None,
                reviewer=None,
                self_review_fallback=False,
                intended_reviewer=None,
                reviewer_failure_reason=None,
                done_override_reason=None,
                force=False,
                tracker_ref=None,
                skip_review_artifact_check=False,
                auto_commit=True,
                json_output=True,
            ),
            ports=_coord_cell_ports(ctx, router),
        )


# ---------------------------------------------------------------------------
# FR-007: rejected review leaves a clean coord tree
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.git_repo
def test_rejected_review_move_task_leaves_clean_coord_tree(tmp_path: Path) -> None:
    """A rejected-review ``in_review -> planned`` hop emits the claim-release /
    review-override annotation; after the fix it is committed atomically on the
    coord ref so the coord status tree is clean.

    RED before the fix: the annotation dirties ``status.events.jsonl`` /
    ``status.json`` on the coord worktree (written + materialized, never
    committed) — the porcelain scope is NON-empty.
    """
    ctx = _build_coord_topology(tmp_path, write_husk_meta=False)
    _disable_branch_protection_for_coord_cell(ctx.repo)
    _seed_coord_wp_in_review(ctx, _WP_ID)
    _commit_coord_baseline(ctx, "test: commit coord in_review baseline")

    # Sanity: the coord status tree is CLEAN before the move.
    assert _coord_status_porcelain(ctx) == "", (
        "precondition failed: coord status tree must be clean before the move"
    )

    feedback = tmp_path / "feedback.md"
    feedback.write_text("**Issue**: needs another pass.\n", encoding="utf-8")

    router = _FaultInjectableCoordRouter(write_dir=ctx.coord_feature_dir)
    _run_move(ctx, router, to="planned", review_feedback_file=feedback)

    porcelain = _coord_status_porcelain(ctx)
    assert porcelain == "", (
        "move-task left the coord status tree DIRTY after a rejected review — the "
        "post-transition InnerStateChanged annotation was written+materialized but "
        f"never committed (#2939):\n{porcelain}"
    )


@pytest.mark.integration
@pytest.mark.git_repo
def test_for_review_move_task_with_note_leaves_clean_coord_tree(tmp_path: Path) -> None:
    """A non-rejection ``in_progress -> for_review`` hop that carries a user note
    emits a ``note`` annotation; after the fix it is committed atomically on the
    coord ref so the coord status tree is clean (the second annotation-riding path
    named by the WP prompt).
    """
    ctx = _build_coord_topology(tmp_path, write_husk_meta=False)
    _disable_branch_protection_for_coord_cell(ctx.repo)
    # Seed WP01 currently in_progress on the coord husk (fresh, single event).
    ctx.status_events_path.unlink()
    _seed_wp_event(ctx.coord_feature_dir, _WP_ID, "in_progress", seq=0)
    _commit_coord_baseline(ctx, "test: commit coord in_progress baseline")

    assert _coord_status_porcelain(ctx) == "", (
        "precondition failed: coord status tree must be clean before the move"
    )

    router = _FaultInjectableCoordRouter(write_dir=ctx.coord_feature_dir)
    _run_move(ctx, router, to="for_review", note="Ready for review — please look.")

    porcelain = _coord_status_porcelain(ctx)
    assert porcelain == "", (
        "move-task left the coord status tree DIRTY after a ->for_review hop that "
        "carried a note annotation — the annotation was written+materialized but "
        f"never committed (#2939):\n{porcelain}"
    )


# ---------------------------------------------------------------------------
# #2959 sibling: the merge escape-hatch skip evidence is committed on coord
# (same emit_inner_state_changed_transactional durability seam as #2939 above).
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.git_repo
def test_skip_review_artifact_evidence_is_committed_on_coord(tmp_path: Path) -> None:
    """``--skip-review-artifact-check`` records "durable override evidence"; on a
    coord mission that ReviewOverride must be COMMITTED, not merely written, so it
    survives even if the merge aborts downstream (squad architect-alphonso, #2959).

    The gate runs at a clean preflight point BEFORE any merge-state / branch-
    integration git mutation, so committing the coord STATUS surface here is safe.

    RED before the fix: ``_record_review_artifact_skip_evidence`` emitted via the
    non-transactional ``emit_inner_state_changed``, leaving the coord status tree
    dirty (evidence written + materialized, never committed) — porcelain NON-empty.
    """
    from specify_cli.consolidation.preflight import _record_review_artifact_skip_evidence
    from specify_cli.post_merge.review_artifact_consistency import (
        ReviewArtifactFinding,
    )

    ctx = _build_coord_topology(tmp_path, write_husk_meta=False)
    _disable_branch_protection_for_coord_cell(ctx.repo)
    _seed_coord_wp_in_review(ctx, _WP_ID)
    _commit_coord_baseline(ctx, "test: commit coord in_review baseline")

    assert _coord_status_porcelain(ctx) == "", (
        "precondition failed: coord status tree must be clean before recording evidence"
    )

    finding = ReviewArtifactFinding(
        wp_id=_WP_ID,
        lane="in_review",
        artifact_path=None,
        cycle_number=1,
        verdict="changes_requested",
    )
    _record_review_artifact_skip_evidence(
        repo_root=ctx.repo,
        feature_dir=ctx.coord_feature_dir,
        mission_slug=ctx.slug,
        findings=[finding],
        note="Operator override: gate false-positive on a stale rejection (#2959).",
    )

    porcelain = _coord_status_porcelain(ctx)
    assert porcelain == "", (
        "skip-evidence left the coord status tree DIRTY — the ReviewOverride was "
        "written+materialized but never committed, so the '--skip-review-artifact-"
        f"check' escape hatch's 'durable override evidence' claim fails on coord:\n{porcelain}"
    )


# ---------------------------------------------------------------------------
# Non-coord control (edge case: no coord surface → no behaviour change)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.git_repo
def test_flat_topology_annotation_still_lands(
    flat_topology_mission: FlatTopologyContext,
) -> None:
    """On a flat (single-branch) mission the transactional annotation emitter
    delegates to the uncommitted ``emit_inner_state_changed`` — the annotation
    still lands in the primary event log (no coord surface to commit to, no
    behaviour change vs. the transition's own coord-less path).
    """
    from specify_cli.coordination.status_transition import (
        emit_inner_state_changed_transactional,
    )
    from specify_cli.status.models import WPInnerStateDelta

    ctx = flat_topology_mission

    def _event_line_count() -> int:
        return len(
            [
                line
                for line in ctx.status_events_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        )

    before = _event_line_count()

    emit_inner_state_changed_transactional(
        ctx.primary_feature_dir,
        _WP_ID,
        WPInnerStateDelta(note="flat control note"),
        actor="tester",
        mission_slug=ctx.slug,
        repo_root=ctx.repo,
    )

    # Coord-less: the emitter delegates to the uncommitted ``emit_inner_state_changed``
    # so the annotation still lands in the PRIMARY event log (surface unchanged).
    assert _event_line_count() == before + 1, (
        "flat-topology annotation was not persisted to the primary event log"
    )
