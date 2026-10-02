"""Two-partition consolidation-readiness preview (WP07, FR-006 / SC-002 / #2885).

The review-artifact consistency gate needs two facts that live in two different
partitions of a coord-topology mission:

* a WP's **lane state** — ``STATUS_STATE``, authoritative on the coordination
  husk's ``status.events.jsonl``; and
* its **review-cycle artifacts** — ``WORK_PACKAGE_TASK``, PRIMARY-partition,
  tracked under ``kitty-specs/<slug>/tasks/<wp>/`` on the primary checkout.

Before the fix, ``find_rejected_review_artifact_conflicts`` judged BOTH off a
single caller-supplied directory. Whichever surface it was handed was correct
for at most one fact and empty (or a stale stray) for the other — so the dry-run
preview (handed the PRIMARY dir) read an empty status log, every WP looked
stateless, and it passed a rejected review by default, while the real
consolidation (handed the coord husk) refused. Preview and consolidation
disagreed (#2885). The gate now resolves each fact from its own declared home,
so both callers resolve the same two surfaces and AGREE (SC-002).

Test harvest & attribution (mission constraint C-007)
-----------------------------------------------------
The two coord-topology scenarios below — a genuine terminal-WP rejection that
MUST be caught, and a stale stray review-cycle file on the coordination husk that
MUST NOT shadow the real tracked artifact on PRIMARY — are harvested from the
kept-for-reference pull request **#2834** by **@rayjohnson** (Ray Johnson),
"fix(merge): split lane-state and review-cycle reads to their real partitions".
They are reproduced here rather than rewritten from scratch, and adapted to this
mission's signature-preserving API (the gate re-resolves both partitions from the
mission identity internally, so a caller may hand it EITHER surface). The SC-002
agreement assertion — that the preview leg and the real-consolidation leg return
the identical verdict — is added on top of @rayjohnson's originals.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.integration.coord_topology_fixture import (  # noqa: F401
    CoordTopologyContext,
    FlatTopologyContext,
    coord_topology_mission,
    flat_topology_mission,
)

if TYPE_CHECKING:
    from specify_cli.post_merge.review_artifact_consistency import (
        RejectedReviewArtifactFinding,
    )
    from specify_cli.status.models import ReviewResult

# Re-export the fixtures so pytest discovers them in this module.
__all__ = ["coord_topology_mission", "flat_topology_mission"]

# New git-shelling integration file (C-006): the coord fixture drives real git.
pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _seed_terminal_wp01(
    ctx: CoordTopologyContext,
    *,
    event_id: str,
    review_result: ReviewResult | None = None,
) -> None:
    """Drive WP01 to a terminal (approved) lane on the REAL coord-husk status log.

    The fixture pre-seeds a raw-text marker line (a wrong-leg probe) that is not a
    schema-valid ``StatusEvent`` and is never meant to survive ``materialize`` — so
    replace it with a real, well-formed terminal transition and exercise production
    materialization end to end. (Idiom harvested from @rayjohnson's PR #2834.)

    ``review_result`` (WP05, verdict-seam-write-unification-01KZ9Q35,
    T028/FR-013): the merge gate is now pure-event -- it never reads
    ``review-cycle-N.md`` frontmatter at all, so a caller that needs the gate
    to see a genuine CURRENT verdict must seed it here, on the SAME terminal
    transition, not merely write the on-disk artifact.
    """
    from specify_cli.status.models import Lane, StatusEvent
    from specify_cli.status.store import append_event

    ctx.status_events_path.write_text("", encoding="utf-8")
    append_event(
        ctx.coord_feature_dir,
        StatusEvent(
            event_id=event_id,
            mission_slug=ctx.slug,
            mission_id=ctx.mission_id,
            wp_id="WP01",
            from_lane=Lane.FOR_REVIEW,
            to_lane=Lane.APPROVED,
            at="2026-06-26T01:00:00+00:00",
            actor="reviewer-renata",
            force=False,
            execution_mode="worktree",
            reason="approved for merge",
            review_result=review_result,
        ),
    )


def _write_review_cycle(
    ctx: CoordTopologyContext,
    *,
    base_dir: Path,
    reviewed_at: str,
    body: str,
) -> None:
    """Write a review-cycle-1 artifact for WP01 under ``base_dir/tasks/WP01``.

    T057 note: this directory name MUST match the slug ``_resolve_wp_slug``
    actually derives for ``wp_id="WP01"`` against this fixture's real
    ``tasks/WP01.md`` (an EXACT-stem match -> slug ``"WP01"``). An earlier
    revision of this helper hard-coded ``tasks/WP01-fixture`` — a directory
    name with no corresponding ``tasks/WP01-fixture.md`` file — which
    T058/T059's routing of this gate through the SAME owner-function slug
    resolution the writer uses now correctly detects as a second, DISTINCT
    candidate alongside the real ``tasks/WP01.md`` (both match task id
    ``WP01`` under T057's separator rule) and refuses as ambiguous
    (``WpSlugAmbiguous``, US3 AC3) — exactly the "silently degrade" failure
    mode T057 exists to close, now correctly surfaced instead of silently
    tolerated by the pre-T059 fan-out.
    """
    from specify_cli.review.artifacts import ReviewCycleArtifact

    ReviewCycleArtifact(
        cycle_number=1,
        wp_id="WP01",
        mission_slug=ctx.slug,
        reviewer_agent="reviewer-renata",
        reviewed_at=reviewed_at,
        body=body,
    ).write(base_dir / "tasks" / "WP01" / "review-cycle-1.md")


def _rejected_finding(
    finding: object,
) -> RejectedReviewArtifactFinding:
    """Narrow a ``ReviewArtifactFinding`` union member to the rejected-verdict
    variant for ``.verdict`` access (mypy --strict: ``ReviewArtifactFinding``
    is ``RejectedReviewArtifactFinding | ReviewArtifactSchemaFinding``, and
    only the former carries ``.verdict``)."""
    from specify_cli.post_merge.review_artifact_consistency import (
        RejectedReviewArtifactFinding,
    )

    assert isinstance(finding, RejectedReviewArtifactFinding), (
        f"Expected a rejected-verdict finding, got a schema finding instead: {finding}"
    )
    return finding


def test_review_artifact_gate_catches_genuine_rejection_on_coord_topology(
    coord_topology_mission: CoordTopologyContext,
) -> None:
    """A genuine rejection on a terminal WP is caught (US2.1) under coord topology.

    Harvested from @rayjohnson's PR #2834, REPOINTED by WP05
    (verdict-seam-write-unification-01KZ9Q35, T028/FR-013/D-PLAN-8): the gate
    is now pure-event -- it consults ONLY the coord husk's real status log
    (``STATUS_STATE``), never the PRIMARY-partition ``review-cycle-N.md``
    frontmatter this test used to also write. The lane read must still
    correctly reach the coord husk (that partition concern is unchanged and
    still the thing this test exercises), but the verdict now comes from the
    SAME terminal transition's ``review_result`` slot. The on-disk artifact
    is still written to prove it is genuinely never opened -- if it were,
    the still-``rejected``-typed frontmatter would agree by coincidence, not
    prove anything; the DISTINCT ``changes_requested`` event-domain value
    below is what actually pins the pure-event read.
    """
    from specify_cli.post_merge.review_artifact_consistency import (
        find_rejected_review_artifact_conflicts,
    )
    from specify_cli.status.models import ReviewResult

    ctx = coord_topology_mission
    _seed_terminal_wp01(
        ctx,
        event_id="01KW2E7A0TERMINAL00000001",
        review_result=ReviewResult(
            reviewer="reviewer-renata", verdict="changes_requested", reference="x"
        ),
    )
    _write_review_cycle(
        ctx,
        base_dir=ctx.primary_feature_dir,
        reviewed_at="2026-06-26T00:30:00+00:00",
        body="# Review\n\nVerdict: rejected.\n",
    )

    findings = find_rejected_review_artifact_conflicts(ctx.primary_feature_dir, ["WP01"])

    assert len(findings) == 1, (
        "Expected the genuine rejection to be caught. An empty result means "
        f"the lane/verdict read missed the coord husk's real status log. Got: {findings}"
    )
    assert findings[0].wp_id == "WP01"
    assert _rejected_finding(findings[0]).verdict == "changes_requested"


def test_review_artifact_gate_ignores_stray_artifact_on_coord_husk(
    coord_topology_mission: CoordTopologyContext,
) -> None:
    """A stray husk review-cycle must not shadow PRIMARY's real content (US2.2).

    Harvested from @rayjohnson's PR #2834 (field-report regression). The
    coordination worktree carries a STALE rejected review-cycle artifact, as if
    left over from an earlier cycle never forwarded there; the PRIMARY checkout
    carries the real, correct APPROVED artifact. WP01's lane (approved) is read from
    the coord husk's real status log. Before the fix, review-cycle content was ALSO
    read from the husk, so the stale rejected artifact falsely blocked an
    already-approved WP. After the fix, review-cycle content resolves to PRIMARY
    (``WORK_PACKAGE_TASK``) — the husk's stray copy is never opened — so a stale
    leftover review file does NOT cause a false not-ready (SC-002 / US2.2).

    **T062 re-pin note (NOT inverted — disclosed, not silently skipped):**
    ADR 2026-08-03-1 designates review-cycle artifacts COORD-partition under a
    coordination topology, which -- read literally -- would invert this
    test's polarity (a genuine COORD record should be authoritative over a
    stale PRIMARY one). This WP investigated that inversion and found it
    empirically UNSAFE to ship: opting only the merge gate into
    ``kind=REVIEW_CYCLE`` while the WRITE seam
    (``review/cycle.py::_review_cycle_wp_dir``) stays PRIMARY-anchored (a
    separate, disclosed WP13 safety finding — see that function's own
    docstring) makes the writer and this gate resolve to DIFFERENT
    directories for a coord-topology mission whose coordination worktree is
    materialised, reproducing C-001's own fail-open class of defect as a NEW
    regression (verified via a throwaway probe driving the REAL production
    writer, :func:`~specify_cli.review.cycle.create_rejected_review_cycle`,
    then this gate — see :func:`test_c001_merge_gate_agrees_with_real_writer_
    under_coord_topology` below, which pins the agreement this inversion
    would have broken). This test's PRIMARY-wins assertion therefore stays
    UNCHANGED, matching this WP's actual, safety-preserved implementation —
    the ADR's COORD-wins conflict rule remains an open, tracked follow-up
    gated on the WRITE-side flip becoming safe (see this WP's final report).

    **WP05 repoint (verdict-seam-write-unification-01KZ9Q35, T028/FR-013):**
    the gate no longer reads EITHER on-disk artifact at all -- both
    ``_write_review_cycle`` calls below are now inert clutter, kept only to
    prove neither is ever opened. The real, current verdict is the terminal
    transition's own event-sourced ``review_result`` (seeded ``approved``,
    matching this test's "real state" narrative), which is what the
    assertion below now actually exercises.
    """
    from specify_cli.post_merge.review_artifact_consistency import (
        find_rejected_review_artifact_conflicts,
    )
    from specify_cli.status.models import ReviewResult

    ctx = coord_topology_mission
    _seed_terminal_wp01(
        ctx,
        event_id="01KW2E7A0TERMINAL00000002",
        review_result=ReviewResult(
            reviewer="reviewer-renata", verdict="approved", reference="x"
        ),
    )
    # The real, correct artifact on PRIMARY: approved.
    _write_review_cycle(
        ctx,
        base_dir=ctx.primary_feature_dir,
        reviewed_at="2026-06-26T00:30:00+00:00",
        body="# Review\n\nVerdict: approved.\n",
    )
    # A stale, stray artifact on the COORD HUSK: rejected. Must never be read.
    _write_review_cycle(
        ctx,
        base_dir=ctx.coord_feature_dir,
        reviewed_at="2026-06-25T00:00:00+00:00",
        body="# Review\n\nVerdict: rejected (stale, never forwarded).\n",
    )

    findings = find_rejected_review_artifact_conflicts(ctx.primary_feature_dir, ["WP01"])

    assert findings == [], (
        "The coord husk's stray rejected artifact must not shadow PRIMARY's real "
        f"approved one — a stale leftover must not cause a false not-ready. Got: {findings}"
    )


def test_preview_and_consolidation_agree_on_rejected_review_case(
    coord_topology_mission: CoordTopologyContext,
) -> None:
    """SC-002: preview and real consolidation AGREE on the case that once disagreed.

    This is the #2885 reproduction turned into a regression. The dry-run preview
    hands the gate the PRIMARY mission dir (see ``forecast.py`` —
    ``feature_dir_for_preview`` is the ``WORK_PACKAGE_TASK`` surface); the real
    consolidation hands it the coordination husk (see ``executor.py`` — the STATUS
    leg's ``feature_dir``). Before the split those two inputs produced DIFFERENT
    verdicts on a genuinely-rejected terminal WP: preview said ready, consolidation
    refused. After the split, each input re-resolves both partitions from the
    mission identity, so the two legs return the IDENTICAL finding.

    **WP05 repoint (verdict-seam-write-unification-01KZ9Q35, T028/FR-013):**
    the gate is now pure-event, so the "verdict" leg of both preview and
    consolidation resolves the SAME event-sourced ``review_result`` off the
    coord husk's status log regardless of which directory the caller hands
    in (:func:`~specify_cli.post_merge.review_artifact_consistency.
    _resolve_lane_state_read_dir` always re-resolves ``STATUS_STATE``). The
    on-disk artifact write below is now inert clutter, kept only to prove it
    is never opened by either leg.
    """
    from specify_cli.post_merge.review_artifact_consistency import (
        find_rejected_review_artifact_conflicts,
    )
    from specify_cli.status.models import ReviewResult

    ctx = coord_topology_mission
    _seed_terminal_wp01(
        ctx,
        event_id="01KW2E7A0TERMINAL00000003",
        review_result=ReviewResult(
            reviewer="reviewer-renata", verdict="changes_requested", reference="x"
        ),
    )
    _write_review_cycle(
        ctx,
        base_dir=ctx.primary_feature_dir,
        reviewed_at="2026-06-26T00:30:00+00:00",
        body="# Review\n\nVerdict: rejected.\n",
    )

    # The preview leg (forecast): resolved through the PRIMARY WORK_PACKAGE_TASK dir.
    preview_findings = find_rejected_review_artifact_conflicts(
        ctx.primary_feature_dir, ["WP01"]
    )
    # The real-consolidation leg (executor): the coord-husk STATUS surface.
    consolidation_findings = find_rejected_review_artifact_conflicts(
        ctx.coord_feature_dir, ["WP01"]
    )

    assert preview_findings == consolidation_findings, (
        "SC-002: the preview and the real consolidation must return the identical "
        "verdict on the rejected-review case. They disagreed under #2885 because the "
        "preview read lane state from PRIMARY (empty) while consolidation read the "
        f"coord husk. preview={preview_findings} consolidation={consolidation_findings}"
    )
    # Non-vacuity: both legs actually caught the rejection (not both-empty agreement).
    assert len(preview_findings) == 1
    assert preview_findings[0].wp_id == "WP01"
    assert _rejected_finding(preview_findings[0]).verdict == "changes_requested"


# ---------------------------------------------------------------------------
# T057 — slug-derivation separator symmetry (US3 AC1/AC3). This is WP13's only
# owned test file, so T057's own coverage (`tasks_materialization.py` has no
# test file among this WP's `owned_files`) lives here rather than going
# uncovered (Sonar/NFR-004: every new branch/helper needs a test in the same
# PR).
# ---------------------------------------------------------------------------


def test_t057_resolve_wp_slug_separator_symmetry(
    flat_topology_mission: FlatTopologyContext,
) -> None:
    """US3 AC1: ``-``, ``_``, ``.``, and no separator all resolve correctly —
    not just the historical hyphen-prefix/exact-match cases."""
    from specify_cli.cli.commands.agent.tasks_materialization import _resolve_wp_slug

    ctx = flat_topology_mission
    tasks_dir = ctx.primary_feature_dir / "tasks"
    (tasks_dir / "WP02_durable_writer.md").write_text("# WP02\n", encoding="utf-8")
    (tasks_dir / "WP03.v2.md").write_text("# WP03\n", encoding="utf-8")

    # Existing hyphen/exact-match cases stay byte-for-byte unchanged.
    assert _resolve_wp_slug(ctx.repo, ctx.slug, "WP01") == "WP01"
    # New: underscore and dot separators (previously silently degraded to the
    # bare id).
    assert _resolve_wp_slug(ctx.repo, ctx.slug, "WP02") == "WP02_durable_writer"
    assert _resolve_wp_slug(ctx.repo, ctx.slug, "WP03") == "WP03.v2"


def test_t057_resolve_wp_slug_prefix_id_does_not_collide(
    flat_topology_mission: FlatTopologyContext,
) -> None:
    """Edge case: a task id that is a PREFIX of another (``WP1`` vs ``WP10``)
    must not let the separator anchor match the longer id's file."""
    from specify_cli.cli.commands.agent.tasks_materialization import _resolve_wp_slug

    ctx = flat_topology_mission
    (ctx.primary_feature_dir / "tasks" / "WP10-something.md").write_text(
        "# WP10\n", encoding="utf-8"
    )

    assert _resolve_wp_slug(ctx.repo, ctx.slug, "WP1") == "WP1"


def test_t057_resolve_wp_slug_ambiguous_match_refuses(
    flat_topology_mission: FlatTopologyContext,
) -> None:
    """US3 AC3: two ``tasks/`` files resolving the same task id to DIFFERENT
    slugs refuse with a diagnostic rather than silently picking one."""
    from specify_cli.cli.commands.agent.tasks_materialization import (
        WpSlugAmbiguous,
        _resolve_wp_slug,
    )

    ctx = flat_topology_mission
    tasks_dir = ctx.primary_feature_dir / "tasks"
    (tasks_dir / "WP04-foo.md").write_text("# WP04 foo\n", encoding="utf-8")
    (tasks_dir / "WP04_bar.md").write_text("# WP04 bar\n", encoding="utf-8")

    with pytest.raises(WpSlugAmbiguous):
        _resolve_wp_slug(ctx.repo, ctx.slug, "WP04")


# ---------------------------------------------------------------------------
# T060 — discharge the REWRITTEN C-001 against the unified resolver.
#
# spec.md:264's rewrite (already landed at planning time, verbatim): the
# fail-closed rejected-verdict refusal is not reinstated -- "once, for every
# accepted filename, the merge gate reaches a verdict for the work package
# that the writer wrote." This is a claim about which artifact's CONTENT
# backs the gate's finding, not about directory equality (the voided
# predicate) -- see plan.md's "Constraint notes" section.
# ---------------------------------------------------------------------------


def test_c001_merge_gate_agrees_with_real_writer_single_branch_two_separators(
    flat_topology_mission: FlatTopologyContext,
) -> None:
    """T060: discharges rewritten C-001 under SINGLE_BRANCH, for two accepted
    separators (US3 AC1) -- the fixture's own ``WP01.md`` (no separator) and a
    freshly-added ``WP02_second_wp.md`` (underscore). Drives the REAL
    production writer (:func:`create_rejected_review_cycle`), not a
    hand-seeded fixture file, so this is an end-to-end writer-to-gate proof.

    **WP05 repoint (verdict-seam-write-unification-01KZ9Q35, T028/FR-013):**
    the gate is now pure-event, so "agrees with the real writer" is proven by
    appending the SAME :class:`~specify_cli.status.models.ReviewResult` the
    writer's own return value (``created.review_result``) carries -- the
    exact value the production ``move-task`` caller would emit -- rather than
    by the gate re-reading the ``.md`` file the writer produced. The writer
    still runs for real (the slug-resolution/writer-agreement concern this
    test's name declares is unchanged); only the gate's read mechanism moved.
    """
    from specify_cli.cli.commands.agent.tasks_materialization import _resolve_wp_slug
    from specify_cli.post_merge.review_artifact_consistency import (
        find_rejected_review_artifact_conflicts,
    )
    from specify_cli.review.cycle import create_rejected_review_cycle
    from specify_cli.status.models import Lane, StatusEvent
    from specify_cli.status.store import append_event

    ctx = flat_topology_mission
    (ctx.primary_feature_dir / "tasks" / "WP02_second_wp.md").write_text(
        "---\nwork_package_id: WP02\ntitle: second\nsubtasks: []\n---\n# WP02\n",
        encoding="utf-8",
    )

    for wp_id, event_id in (
        ("WP01", "01KW2E7B0TERMC00100001A"),
        ("WP02", "01KW2E7B0TERMC00100001B"),
    ):
        wp_slug = _resolve_wp_slug(ctx.repo, ctx.slug, wp_id)
        created = create_rejected_review_cycle(
            main_repo_root=ctx.repo,
            mission_slug=ctx.slug,
            wp_id=wp_id,
            wp_slug=wp_slug,
            body=f"# Review\n\nVerdict: rejected for {wp_id}.\n",
            reviewer_agent="reviewer-renata",
            verdict="rejected",
        )
        append_event(
            ctx.primary_feature_dir,
            StatusEvent(
                event_id=event_id,
                mission_slug=ctx.slug,
                mission_id=ctx.mission_id,
                wp_id=wp_id,
                from_lane=Lane.FOR_REVIEW,
                to_lane=Lane.APPROVED,
                at="2026-06-26T01:00:00+00:00",
                actor="reviewer-renata",
                force=False,
                execution_mode="worktree",
                reason="approved for merge",
                review_result=created.review_result,
            ),
        )

    findings = find_rejected_review_artifact_conflicts(
        ctx.primary_feature_dir, ["WP01", "WP02"]
    )

    assert {finding.wp_id for finding in findings} == {"WP01", "WP02"}, (
        "C-001: the merge gate must reach a verdict for every WP the writer "
        f"actually wrote, for both accepted separators. Got: {findings}"
    )
    assert all(
        _rejected_finding(finding).verdict == "changes_requested" for finding in findings
    )


def test_c001_merge_gate_agrees_with_real_writer_under_coord_topology(
    coord_topology_mission: CoordTopologyContext,
) -> None:
    """T060: discharges rewritten C-001 under a coord topology too.

    This is ALSO the regression tripwire the T062 re-pin's docstring (above)
    cites: if this gate is ever changed to resolve
    ``kind=MissionArtifactKind.REVIEW_CYCLE`` (COORD-aware) without ALSO
    fixing the WRITE seam (``review/cycle.py::_review_cycle_wp_dir``'s own
    disclosed WP13 finding), this test goes red FIRST -- proving writer and
    gate have drifted apart, which is exactly the fail-open class of defect
    C-001 exists to prevent.

    **WP05 repoint (verdict-seam-write-unification-01KZ9Q35, T028/FR-013):**
    same treatment as this file's single-branch sibling above -- the
    terminal transition now carries the writer's own ``created.review_result``
    (constructed AFTER the real writer call, since that's what production's
    ``move-task`` does too), and the gate's finding always reports
    ``artifact_path=None`` (the pure-event gate never resolves an on-disk
    path at all), not ``created.artifact_path``.
    """
    from specify_cli.cli.commands.agent.tasks_materialization import _resolve_wp_slug
    from specify_cli.post_merge.review_artifact_consistency import (
        find_rejected_review_artifact_conflicts,
    )
    from specify_cli.review.cycle import create_rejected_review_cycle
    from specify_cli.status.models import Lane, StatusEvent
    from specify_cli.status.store import append_event

    ctx = coord_topology_mission
    ctx.status_events_path.write_text("", encoding="utf-8")
    wp_slug = _resolve_wp_slug(ctx.repo, ctx.slug, "WP01")
    created = create_rejected_review_cycle(
        main_repo_root=ctx.repo,
        mission_slug=ctx.slug,
        wp_id="WP01",
        wp_slug=wp_slug,
        body="# Review\n\nVerdict: rejected.\n",
        reviewer_agent="reviewer-renata",
        verdict="rejected",
    )
    append_event(
        ctx.coord_feature_dir,
        StatusEvent(
            event_id="01KW2E7A0TERMC0010000001",
            mission_slug=ctx.slug,
            mission_id=ctx.mission_id,
            wp_id="WP01",
            from_lane=Lane.FOR_REVIEW,
            to_lane=Lane.APPROVED,
            at="2026-06-26T01:00:00+00:00",
            actor="reviewer-renata",
            force=False,
            execution_mode="worktree",
            reason="approved for merge",
            review_result=created.review_result,
        ),
    )

    findings = find_rejected_review_artifact_conflicts(ctx.primary_feature_dir, ["WP01"])

    assert len(findings) == 1, (
        "C-001: the merge gate must reach a verdict for the WP the REAL "
        f"writer wrote, even under coord topology. writer wrote to "
        f"{created.artifact_path}; got findings={findings}"
    )
    assert _rejected_finding(findings[0]).verdict == "changes_requested"
    assert findings[0].artifact_path is None


def test_c001_merge_gate_reports_no_verdict_for_wp_with_no_artifact(
    flat_topology_mission: FlatTopologyContext,
) -> None:
    """T060 edge case: a WP with no review-cycle artifact at all degrades to
    "no verdict, no finding" — not a crash — under the rewritten C-001."""
    from specify_cli.post_merge.review_artifact_consistency import (
        find_rejected_review_artifact_conflicts,
    )

    ctx = flat_topology_mission
    findings = find_rejected_review_artifact_conflicts(ctx.primary_feature_dir, ["WP01"])

    assert findings == []


# ---------------------------------------------------------------------------
# Operator-directed scope addition (DM-01KZ75GBNXC73Q38M43GBH38W7):
# tasks_verdict_persistence.py::revert_committed_verdict_write's revert-commit
# destination must track the SAME ref the original write actually committed
# to. `safe_commit` is called DIRECTLY here (bypassing `commit_artifact`'s
# path-based kind override that makes the analogous kind argument
# self-correcting elsewhere in this mission), so a stale `kind` argument is a
# live bug, not cosmetic drift.
# ---------------------------------------------------------------------------


def _unprotect_main(repo: Path) -> None:
    """Disable branch protection so a real commit lands on the target branch.

    Mirrors ``tests/specify_cli/cli/commands/agent/test_move_task_durability.
    py``'s own ``_unprotect_main`` helper.
    """
    import subprocess

    kittify_dir = repo / ".kittify"
    kittify_dir.mkdir(parents=True, exist_ok=True)
    (kittify_dir / "config.yaml").write_text(
        "protection:\n  protected_branches: []\n", encoding="utf-8"
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "test: unprotect main"],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def test_revert_committed_verdict_write_targets_coord_ref_under_coord_topology(
    coord_topology_mission: CoordTopologyContext,
) -> None:
    """DM-01KZ75GBNXC73Q38M43GBH38W7: the revert-compensator must delete the
    artifact from the SAME ref the original write committed it to.

    ``review-cycle-N.md`` is ADR 2026-08-03-1's ``REVIEW_CYCLE`` kind
    (COORD-partition under a coordination topology); the writer's commit
    (via ``commit_artifact``'s path-based classification) lands there
    regardless of caller kind. ``revert_committed_verdict_write`` used to
    resolve its OWN commit destination via ``placement_seam(...).write_target(
    kind=MissionArtifactKind.WORK_PACKAGE_TASK)`` -- always PRIMARY -- calling
    ``safe_commit`` DIRECTLY (no path-based override to self-correct it, unlike
    ``_commit_review_cycle_artifact``). Under a coord topology this reverted
    nothing on the ref that actually held the commit: the deletion committed
    to PRIMARY while the orphan verdict remained readable on COORD -- exactly
    the shape FR-002 exists to prevent. A single-branch fixture cannot
    reproduce this (both kinds resolve to the same ref there); this test
    requires a topology where they genuinely differ.
    """
    import subprocess

    from specify_cli.agent_tasks_ports import RealCoordCommitRouter
    from specify_cli.cli.commands.agent.tasks_move_task import _MoveTaskState
    from specify_cli.cli.commands.agent.tasks_verdict_persistence import (
        VerdictDurabilitySignal,
        revert_committed_verdict_write,
    )
    from specify_cli.review.cycle import create_rejected_review_cycle

    ctx = coord_topology_mission
    _unprotect_main(ctx.repo)

    router = RealCoordCommitRouter()
    created = create_rejected_review_cycle(
        main_repo_root=ctx.repo,
        mission_slug=ctx.slug,
        wp_id="WP01",
        wp_slug="WP01",
        body="# Review\n\nVerdict: rejected.\n",
        reviewer_agent="reviewer-renata",
        verdict="rejected",
        commit_router=router,
    )
    # coord-artifact-single-home-01M3V4BE WP08: the review-cycle artifact's
    # physical write home is the coordination worktree for a coord-routed
    # Mission -- never ``ctx.repo`` directly (single-home: no PRIMARY
    # staging copy).
    coord_worktree_root = ctx.coord_feature_dir.parents[1]
    rel_path = created.artifact_path.relative_to(coord_worktree_root)

    # Precondition: the writer's own commit really did land on the COORD ref
    # (this is what makes the bug reproducible at all).
    coord_show = subprocess.run(
        ["git", "show", f"{ctx.coord_branch}:{rel_path.as_posix()}"],
        cwd=ctx.repo,
        capture_output=True,
        text=True,
    )
    assert coord_show.returncode == 0, (
        "Precondition failed: the writer's own commit did not land on the "
        f"coord ref {ctx.coord_branch!r}. stderr={coord_show.stderr}"
    )

    st = _MoveTaskState(
        task_id="WP01",
        to="approved",
        mission=None,
        agent=None,
        assignee=None,
        shell_pid=None,
        note=None,
        review_feedback_file=None,
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
        json_output=False,
        main_repo_root=ctx.repo,
        mission_slug=ctx.slug,
    )
    signal = VerdictDurabilitySignal(
        outcome=created.persistence,
        artifact_path=created.artifact_path,
        cycle_number=created.artifact.cycle_number,
    )

    revert_committed_verdict_write(st, signal)

    coord_show_after = subprocess.run(
        ["git", "show", f"{ctx.coord_branch}:{rel_path.as_posix()}"],
        cwd=ctx.repo,
        capture_output=True,
        text=True,
    )
    assert coord_show_after.returncode != 0, (
        "The revert must delete the artifact from the SAME (coord) ref the "
        "writer committed it to, not from PRIMARY. It is still readable on "
        f"the coord ref: {coord_show_after.stdout!r}"
    )


# ---------------------------------------------------------------------------
# Operator-directed scope addition (DM-01KZ77DS4F1PZ92MK6V8ATCJWW):
# tasks_verdict_persistence.py::resolve_review_verdict_facts's directory
# resolution now routes through review/cycle.py::_review_cycle_wp_dir (the
# T058 owner function) instead of an independent ``wp_path.parent /
# wp_path.stem`` join. Mirrors the T057 slug-vs-bare tests above.
# ---------------------------------------------------------------------------


def test_resolve_review_verdict_facts_routes_through_owner_function(
    flat_topology_mission: FlatTopologyContext,
) -> None:
    """Uses an underscore-separated WP file (``WP02_second_wp.md``) whose
    review-cycle content lives at ``tasks/WP02_second_wp/`` -- a directory a
    naive ``tasks/<bare_id>`` join (``tasks/WP02``) would never find. Proves
    the routed resolution (via ``_review_cycle_wp_dir``) agrees with the
    already-correct ``wp_path.stem``-based answer (this call site was traced
    "unconsolidated, not actively buggy" -- see this WP's final report), and
    guards against a future regression that reintroduces a bare-id-based join
    here (which a pre-T057-style resolver WOULD get wrong for this exact
    separator).

    **WP05 repoint (verdict-seam-write-unification-01KZ9Q35, T023):**
    ``resolve_review_verdict_facts`` no longer parses ``review-cycle-N.md``
    frontmatter at all -- it resolves ``event_sourced_review_result`` and
    threads ``ReviewResult.feedback_path`` back as ``artifact_path``. The
    underscore-separator concern this test pins is now about
    ``feedback_path`` carrying the SAME correctly-resolved directory a
    real writer would have produced, not about a frontmatter re-parse; the
    on-disk artifact is still written (as a real writer would leave one) but
    is no longer itself the source of the returned facts.
    """
    from specify_cli.cli.commands.agent.tasks_verdict_persistence import (
        resolve_review_verdict_facts,
    )
    from specify_cli.review.artifacts import ReviewCycleArtifact
    from specify_cli.status.models import Lane, ReviewResult, StatusEvent
    from specify_cli.status.store import append_event

    ctx = flat_topology_mission
    wp_path = ctx.primary_feature_dir / "tasks" / "WP02_second_wp.md"
    wp_path.write_text(
        "---\nwork_package_id: WP02\ntitle: second\nsubtasks: []\n---\n# WP02\n",
        encoding="utf-8",
    )
    correct_dir = ctx.primary_feature_dir / "tasks" / "WP02_second_wp"
    correct_path = correct_dir / "review-cycle-1.md"
    ReviewCycleArtifact(
        cycle_number=1,
        wp_id="WP02",
        mission_slug=ctx.slug,
        reviewer_agent="reviewer-renata",
        reviewed_at="2026-06-26T00:30:00+00:00",
        body="# Review\n\nVerdict: rejected.\n",
    ).write(correct_path)
    append_event(
        ctx.primary_feature_dir,
        StatusEvent(
            event_id="01KW2E7B0RVFROUTE0000001",
            mission_slug=ctx.slug,
            mission_id=ctx.mission_id,
            wp_id="WP02",
            from_lane=Lane.FOR_REVIEW,
            to_lane=Lane.APPROVED,
            at="2026-06-26T00:30:00+00:00",
            actor="reviewer-renata",
            force=False,
            execution_mode="worktree",
            reason="rejected on review",
            review_result=ReviewResult(
                reviewer="reviewer-renata",
                verdict="changes_requested",
                reference=f"feedback://{ctx.slug}/WP02_second_wp/review-cycle-1.md",
                feedback_path=str(correct_path),
            ),
        ),
    )

    # Sanity: a naive bare-id join would look at a DIFFERENT, empty directory.
    naive_bare_dir = ctx.primary_feature_dir / "tasks" / "WP02"
    assert not naive_bare_dir.exists()

    verdict, artifact_path, artifact_name = resolve_review_verdict_facts(wp_path)

    assert verdict == "rejected"
    assert artifact_path == correct_path
    assert artifact_name == "review-cycle-1.md"
