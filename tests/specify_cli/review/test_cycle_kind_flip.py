"""WP11 / FR-017 (#3563) — narrow review-cycle write-side kind opt-in lock.

**This WP was deliberately NARROWED by a post-tasks adversarial squad.** The
original ambition (flip the GLOBAL write-side default of
``review/cycle.py::_review_cycle_wp_dir`` to ``REVIEW_CYCLE``) is disclosed
IN CODE (``review/cycle.py:106-158``, the "WP13 finding") as NOT yet safe: it
moves the PHYSICAL write into the coordination worktree and breaks
``tests/coordination/test_analysis_report_rehome.py``. That full flip needs a
physical-write / git-staging separation rework + routing three unrouted sites,
tracked separately. It is EXPLICITLY out of scope here.

What this file does instead is **lock the narrow opt-in that is already in
effect on base**, and record — as runnable, empirically-grounded assertions —
exactly why no *further* owned-file opt-in is safe:

* **The write-side already persists the review cycle under ``REVIEW_CYCLE``.**
  ``review/cycle.py::_commit_review_cycle_artifact`` already passes
  ``kind=MissionArtifactKind.REVIEW_CYCLE`` (landed by prior missions 191 /
  WP10), and ``commit_for_mission``'s per-file, path-derived partition
  classification lands ``review-cycle-N.md`` on the COORD partition regardless.
  The PHYSICAL write stays in the PRIMARY ``tasks/<wp>/`` home (write-in-home) —
  so the narrow opt-in "writes under ``REVIEW_CYCLE`` where the physical-write
  location does NOT move" is satisfied *today*. :func:`test_narrow_opt_in_...`
  pins both halves (COORD placement + PRIMARY physical write) so a regression of
  the commit-kind, or an accidental default flip, reds here.

* **The verdict-facts reader is read-tolerant of the write-side kind.**
  ``resolve_review_verdict_facts`` (``tasks_verdict_persistence.py:404``) was
  ALREADY repointed onto the event authority (``event_sourced_review_result``
  via ``_resolve_verdict_read_feature_dir`` → ``STATUS_STATE``) by mission
  ``verdict-seam-write-unification-01KZ9Q35``. Its read authority is therefore
  DECOUPLED from ``_review_cycle_wp_dir``'s write-side directory kind:
  :func:`test_verdict_reader_authority_is_decoupled_...` proves the reader
  resolves the COORD status husk while the write-side ``tasks/<wp>/`` home stays
  PRIMARY — so the write-side kind cannot disturb verdict resolution (T037,
  verification only — no reader migration is performed).

**Why no further owned-file flip is shipped (empirically established, see this
WP's report):** every remaining ``_review_cycle_wp_dir`` consumer in the owned
files (the write seam, the pointer read seam, and ``_resolve_verdict_wp_dir``)
is pinned to the PRIMARY home by the green sentinel
``tests/coordination/test_verdict_dir_co_resolution.py`` (multi-consumer
co-resolution). Flipping the write seam's default reds
``test_analysis_report_rehome`` (the physical write moves into the coord
worktree); flipping ``_resolve_verdict_wp_dir`` (or the pointer read seam) reds
the co-resolution sentinel (NFR-004 forbids manufacturing a red by regressing a
green sentinel). The single safe consumer the disclosure names — the merge-time
gate in ``post_merge/review_artifact_consistency.py`` — is NOT in this WP's
``owned_files`` and does not route through ``_review_cycle_wp_dir`` at all.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionArtifactKind, placement_seam

from tests.integration.coord_topology_fixture import _build_coord_topology

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_ISSUE = "#3563"  # FR-017 deferral D1, epic #3044


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


def test_narrow_opt_in_review_cycle_persists_under_review_cycle_kind_without_moving_the_write(
    tmp_path: Path,
) -> None:
    """FR-017 (#3563): the review-cycle write PERSISTS under the review-cycle
    kind (COORD partition) while its PHYSICAL write stays in the PRIMARY
    ``tasks/<wp>/`` home — the narrow opt-in, already in effect on base.

    Committed-tree proof (non-fakeable), on a real coord-topology fixture:

    * ``created.artifact_path`` is the PRIMARY ``kitty-specs/<slug>/tasks/WP01/
      review-cycle-1.md`` (write-in-home did NOT move into the coord worktree),
      and
    * ``git show <coord_ref>:.../review-cycle-1.md`` SUCCEEDS while
      ``git show main:.../review-cycle-1.md`` FAILS — the persisted artifact
      lands under the ``REVIEW_CYCLE`` (COORD) partition.

    A regression of the commit-kind, OR an accidental flip of the write-side
    default (which would move ``created.artifact_path`` into the coord
    worktree), reds this test.
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

    # (1) PHYSICAL write did NOT move — still the PRIMARY tasks home.
    # ``as_posix`` because ``str(Path)`` yields backslash separators on Windows,
    # which can never equal the forward-slash git tree path below (#3834).
    rel = created.artifact_path.relative_to(ctx.repo).as_posix()
    assert rel == f"kitty-specs/{ctx.slug}/tasks/WP01/review-cycle-1.md", (
        f"{_ISSUE}: the physical write must stay in the PRIMARY tasks home; a write-side default flip would move it into the coord worktree. Got {rel!r}."
    )

    # (2) Commit through the REAL router — even with the caller's plainest kind
    # argument, path-derived classification lands review-cycle under COORD.
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

    coord_rel = f"kitty-specs/{ctx.slug}/tasks/WP01/review-cycle-1.md"
    coord_show = _git(ctx.repo, "show", f"{ctx.coord_branch}:{coord_rel}")
    assert coord_show.returncode == 0, (
        f"{_ISSUE}: review-cycle-1.md must be persisted under the REVIEW_CYCLE (COORD) partition {ctx.coord_branch!r}: {coord_show.stderr}"
    )
    assert "Reviewer feedback:" in coord_show.stdout

    primary_show = _git(ctx.repo, "show", f"main:{rel}")
    assert primary_show.returncode != 0, f"{_ISSUE}: review-cycle-1.md must NOT be left as a stale PRIMARY copy:\n{primary_show.stdout}"


def test_verdict_reader_authority_is_decoupled_from_write_side_kind(
    tmp_path: Path,
) -> None:
    """T037 (read-tolerance, verification only): the event-authority verdict
    reader is UNAFFECTED by the write-side artifact kind.

    ``resolve_review_verdict_facts`` reads the verdict via
    ``_resolve_verdict_read_feature_dir`` (the ``STATUS_STATE`` authority — the
    COORD status husk under a coordination topology), which is a DIFFERENT
    resolution from ``_resolve_verdict_wp_dir`` (the write-side
    ``WORK_PACKAGE_TASK`` / PRIMARY ``tasks/<wp>/`` home). Because the two are
    decoupled, the write-side kind cannot disturb verdict resolution — so no
    reader migration is needed (it was already repointed onto the event
    authority by ``verdict-seam-write-unification-01KZ9Q35``).
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

    # The write-side ``tasks/<wp>/`` home stays PRIMARY (WORK_PACKAGE_TASK) —
    # decoupled from the reader authority above, so the write-side kind is
    # invisible to verdict resolution.
    assert write_side_dir == ctx.primary_feature_dir / "tasks" / "WP01", write_side_dir
    assert reader_authority != write_side_dir, (
        f"{_ISSUE}: reader authority and write-side home must be decoupled so the write-side kind cannot disturb verdict resolution"
    )


def test_physical_write_home_is_primary_so_rehome_guard_stays_green(
    tmp_path: Path,
) -> None:
    """T038 companion: independently guard, in this file, the invariant
    ``test_analysis_report_rehome`` protects — the review-cycle's PHYSICAL write
    home is the PRIMARY ``tasks/<wp>/`` tree, not the coord worktree.

    This is the property the narrow opt-in must not disturb: opting a consumer
    into ``REVIEW_CYCLE`` is only safe where it does NOT relocate this physical
    write. If a future change moves it, both this test and the rehome guard red.
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

    primary_home = ctx.primary_feature_dir / "tasks" / "WP01"
    assert created.artifact_path.parent == primary_home, created.artifact_path
    # The shared write-side resolver still anchors PRIMARY (default kind) — the
    # single fact ``test_analysis_report_rehome`` depends on.
    assert _review_cycle_wp_dir(ctx.repo, ctx.slug, "WP01") == primary_home
