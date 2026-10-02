"""WP11 / FR-017 (#3563) — superseded by WP08's full write-side flip.

**Re-pinned (coord-artifact-single-home-01M3V4BE WP08, Standing Order 4:
stale -> re-pin with rationale).** This file originally locked a NARROW
opt-in: ``review/cycle.py::_review_cycle_wp_dir`` committed review-cycle
artifacts under the ``REVIEW_CYCLE`` (COORD) partition while its PHYSICAL
write stayed in the PRIMARY ``tasks/<wp>/`` home — "write-in-home,
stage-in-root-then-copy." That shape is gone: WP08 ships the FULL write-side
flip the original WP11 docstring disclosed as "not yet safe" — the write seam
(:func:`~specify_cli.review.cycle.create_rejected_review_cycle`) now resolves
its directory through :func:`~specify_cli.review.cycle._review_cycle_write_location`
(:meth:`~mission_runtime.resolution.PlacementSeam.write_dir`), and the shared
READ-mode resolver (:func:`~specify_cli.review.cycle._review_cycle_wp_dir`)
defaults to ``kind=REVIEW_CYCLE`` so every reader (the arbiter, the safety
verdict reader, the fix-mode / prior-rejection probes) co-resolves the SAME
coordination-worktree directory the writer now uses.

What stays true, and is still pinned here:

* **The commit still lands under the ``REVIEW_CYCLE`` (COORD) partition** —
  unchanged by WP08 (:func:`test_review_cycle_persists_under_review_cycle_kind_and_now_physically_lands_on_coordination`).
* **The verdict-facts reader's authority (STATUS_STATE) is decoupled from the
  review-cycle write-side directory (REVIEW_CYCLE)** — they are different
  ``MissionArtifactKind`` values, so they resolve to DIFFERENT directories
  even though both are now COORD-partition
  (:func:`test_verdict_reader_authority_is_decoupled_from_write_side_kind`).
* **The physical write home is a single, observable fact**
  (:func:`test_physical_write_home_is_coordination_so_rehome_guard_stays_green`)
  — now the coordination worktree, mirroring
  ``tests/coordination/test_analysis_report_rehome.py``'s own re-pin.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionArtifactKind, placement_seam

from tests.integration.coord_topology_fixture import _build_coord_topology

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_ISSUE = "#3563"  # FR-017 deferral D1, epic #3044; superseded by coord-artifact-single-home-01M3V4BE WP08


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def _disable_branch_protection(repo: Path) -> None:
    """Commit an empty ``protected_branches`` so the PRIMARY-partition commit can land.

    Mirrors ``test_analysis_report_rehome.py``'s only config touch — the actual
    proof is on the committed git trees below, not this config.
    """
    config = repo / ".kittify" / "config.yaml"
    config.write_text("protection:\n  protected_branches: []\n", encoding="utf-8")
    assert _git(repo, "add", ".kittify/config.yaml").returncode == 0
    assert _git(repo, "commit", "-m", "test: unprotect main for kind-flip proof").returncode == 0


def test_review_cycle_persists_under_review_cycle_kind_and_now_physically_lands_on_coordination(
    tmp_path: Path,
) -> None:
    """FR-003/FR-007 (WP08): the review-cycle write persists under the
    review-cycle kind (COORD partition) AND its PHYSICAL write now lands in
    the coordination worktree -- the single-home rule this Mission ships.

    Committed-tree proof (non-fakeable), on a real coord-topology fixture:

    * ``created.artifact_path`` is the COORDINATION worktree's
      ``kitty-specs/<slug>/tasks/WP01/review-cycle-1.md`` (single-home: no
      PRIMARY staging copy ever exists), and
    * ``git show <coord_ref>:.../review-cycle-1.md`` SUCCEEDS while
      ``git show main:.../review-cycle-1.md`` FAILS -- the persisted artifact
      lands under the ``REVIEW_CYCLE`` (COORD) partition only.

    A regression back to the PRIMARY physical-write home, or away from the
    ``REVIEW_CYCLE`` commit kind, reds this test.
    """
    from specify_cli.coordination.commit_router import commit_for_mission
    from specify_cli.git.protection_policy import ProtectionPolicy
    from specify_cli.review.cycle import create_rejected_review_cycle

    ctx = _build_coord_topology(tmp_path, write_husk_meta=False)
    _disable_branch_protection(ctx.repo)

    feedback = tmp_path / "review-feedback.md"
    feedback.write_text(
        "Reviewer feedback: WP01 needs the missing regression test before approval.\n",
        encoding="utf-8",
    )

    created = create_rejected_review_cycle(
        main_repo_root=ctx.repo,
        mission_slug=ctx.slug,
        wp_id="WP01",
        wp_slug="WP01",
        feedback_source=feedback,
        reviewer_agent="reviewer-renata",
    )

    # (1) PHYSICAL write now lands in the coordination worktree (single-home).
    # ``as_posix`` because ``str(Path)`` yields backslash separators on Windows,
    # which can never equal the forward-slash git tree path below (#3834).
    assert created.artifact_path.parent == ctx.coord_feature_dir / "tasks" / "WP01", created.artifact_path
    coord_worktree_path = ctx.coord_feature_dir.parent.parent
    coord_rel = f"kitty-specs/{ctx.slug}/tasks/WP01/review-cycle-1.md"
    rel = created.artifact_path.relative_to(coord_worktree_path).as_posix()
    assert rel == coord_rel, f"{_ISSUE}: the physical write must land under the coordination worktree's {coord_rel!r}. Got {rel!r}."

    # (2) Commit through the REAL router — path-derived classification lands
    # review-cycle under COORD, and the physical write is already in place.
    result = commit_for_mission(
        repo_root=ctx.repo,
        mission_slug=ctx.slug,
        files=(created.artifact_path,),
        message=f"Add review-cycle-1 for {ctx.slug} WP01",
        policy=ProtectionPolicy.resolve(ctx.repo),
        kind=MissionArtifactKind.REVIEW_CYCLE,
        target_branch="main",
    )
    assert result.status == "committed", result
    assert result.placement_ref == ctx.coord_branch, result

    coord_show = _git(ctx.repo, "show", f"{ctx.coord_branch}:{coord_rel}")
    assert coord_show.returncode == 0, (
        f"{_ISSUE}: review-cycle-1.md must be persisted under the REVIEW_CYCLE (COORD) partition {ctx.coord_branch!r}: {coord_show.stderr}"
    )
    assert "Reviewer feedback:" in coord_show.stdout

    primary_rel = f"kitty-specs/{ctx.slug}/tasks/WP01/review-cycle-1.md"
    primary_show = _git(ctx.repo, "show", f"main:{primary_rel}")
    assert primary_show.returncode != 0, (
        f"{_ISSUE}: review-cycle-1.md must NEVER exist as a PRIMARY copy (single-home, no transient staging):\n{primary_show.stdout}"
    )


def test_verdict_reader_authority_is_decoupled_from_write_side_kind(
    tmp_path: Path,
) -> None:
    """T037 (read-tolerance, verification only; re-pinned WP08): the
    event-authority verdict reader is UNAFFECTED by the review-cycle
    write-side directory kind, even though BOTH now resolve under the
    coordination worktree.

    ``resolve_review_verdict_facts`` reads the verdict via
    ``_resolve_verdict_read_feature_dir`` (the ``STATUS_STATE`` authority — the
    COORD status husk under a coordination topology), which is a DIFFERENT
    ``MissionArtifactKind`` from ``_resolve_verdict_wp_dir`` (the write-side
    ``REVIEW_CYCLE`` ``tasks/<wp>/`` home — WP08 flipped this reader's default
    from ``WORK_PACKAGE_TASK`` to ``REVIEW_CYCLE`` along with every other
    review-cycle consumer). The two kinds resolve to DIFFERENT directories
    (the STATUS_STATE husk has no ``tasks/<wp>`` suffix) even though both are
    now COORD-partition — so the write-side kind still cannot disturb verdict
    resolution (no reader migration is needed for THIS reader; it was already
    repointed onto the event authority by
    ``verdict-seam-write-unification-01KZ9Q35``).
    """
    from specify_cli.cli.commands.agent.tasks_verdict_persistence import (
        _resolve_verdict_read_feature_dir,
        _resolve_verdict_wp_dir,
    )

    ctx = _build_coord_topology(tmp_path, write_husk_meta=False)
    wp_path = ctx.primary_feature_dir / "tasks" / "WP01.md"

    reader_authority = _resolve_verdict_read_feature_dir(wp_path)
    write_side_dir = _resolve_verdict_wp_dir(wp_path)

    # The reader's authority is the COORD status husk (STATUS_STATE) — exactly
    # where ``emit_status_transition`` writes the ``review_result`` slot.
    status_state_dir = placement_seam(ctx.repo, ctx.slug).read_dir(MissionArtifactKind.STATUS_STATE)
    assert reader_authority == status_state_dir == ctx.coord_feature_dir, (
        f"{_ISSUE}: the verdict reader must resolve the STATUS_STATE (coord husk) authority, got {reader_authority}"
    )

    # WP08: the write-side ``tasks/<wp>/`` home now also resolves under the
    # coordination worktree (REVIEW_CYCLE, not WORK_PACKAGE_TASK) — but it is
    # STILL a DIFFERENT directory from the STATUS_STATE authority above (a
    # kind-level decoupling, not a topology-level one).
    assert write_side_dir == ctx.coord_feature_dir / "tasks" / "WP01", write_side_dir
    assert reader_authority != write_side_dir, (
        f"{_ISSUE}: reader authority and write-side home must be decoupled so the write-side kind cannot disturb verdict resolution"
    )


def test_physical_write_home_is_coordination_so_rehome_guard_stays_green(
    tmp_path: Path,
) -> None:
    """T038 companion (re-pinned WP08): independently guard, in this file, the
    invariant ``test_analysis_report_rehome`` protects — the review-cycle's
    PHYSICAL write home is the coordination worktree's ``tasks/<wp>/`` tree,
    with NO stale PRIMARY copy.

    This is the property WP08 established and that must not regress: a future
    change moving the physical write back to PRIMARY (or anywhere else) reds
    both this test and the rehome guard.
    """
    from specify_cli.review.cycle import _review_cycle_wp_dir, create_rejected_review_cycle

    ctx = _build_coord_topology(tmp_path, write_husk_meta=False)
    feedback = tmp_path / "review-feedback.md"
    feedback.write_text("Reviewer feedback: WP01 regression missing.\n", encoding="utf-8")

    created = create_rejected_review_cycle(
        main_repo_root=ctx.repo,
        mission_slug=ctx.slug,
        wp_id="WP01",
        wp_slug="WP01",
        feedback_source=feedback,
        reviewer_agent="reviewer-renata",
    )

    coord_home = ctx.coord_feature_dir / "tasks" / "WP01"
    assert created.artifact_path.parent == coord_home, created.artifact_path
    # The shared read-mode resolver (default kind, now REVIEW_CYCLE) agrees
    # with the write — the single fact ``test_analysis_report_rehome`` depends on.
    assert _review_cycle_wp_dir(ctx.repo, ctx.slug, "WP01") == coord_home
    primary_home = ctx.primary_feature_dir / "tasks" / "WP01"
    assert not (primary_home / "review-cycle-1.md").exists(), f"{_ISSUE}: no stale PRIMARY copy may exist (single-home, no transient staging)"
