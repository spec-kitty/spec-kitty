"""#4786 (WP04, T015/T020) — the accept gate must not block on a released live claim.

Root cause: ``agent`` is a *live-claim* slot that legitimately changes hands
(implementer -> reviewer) and is correctly RELEASED on a review-rejection
rollback (#4673's ``release_runtime_claim`` annotation) — that release is
correct and stays untouched. But nothing else owned durable *implementer*
provenance once the live claim was released, so an ORDINARY
claim -> for_review -> reject -> re-review -> approve cycle (no fresh
``--agent`` on the return legs) reached ``accept`` reporting
"missing agent in canonical runtime state" even though the WP was, in fact,
implemented and approved.

Pinned regression: issue #4786.

This drives the real lane state machine end-to-end through
``emit_status_transition``/``emit_inner_state_changed`` (the same public seam
``spec-kitty agent tasks move-task`` uses) against a real git-backed mission
fixture, then calls ``acceptance.collect_feature_summary`` — the function
``spec-kitty accept`` itself calls — and asserts on its ``metadata_issues``.

The compressed forward hops after the rollback (planned -> claimed ->
in_progress -> for_review, each an individually-legal transition) stand in
for a single ``move-task --to for_review`` CLI invocation walking the same
chain; the event-log shape they produce is identical either way, and the
regression is scoped entirely to whether the SECOND claim carries a fresh
``--agent`` (it deliberately does not, per the pinned repro).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from specify_cli.acceptance import collect_feature_summary
from specify_cli.status.emit import (
    build_claim_policy_metadata,
    emit_inner_state_changed,
    emit_status_transition,
)
from specify_cli.status.models import ReviewResult, TransitionRequest, WPInnerStateDelta

if TYPE_CHECKING:
    from tests.integration.coord_topology_fixture import FlatTopologyContext

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_WP_ID = "WP01"
_REPAIR_HINT = "spec-kitty doctor mission-state --fix --mission"


def _missing_agent_issues(issues: list[str]) -> list[str]:
    return [issue for issue in issues if "missing agent" in issue]


def _drive_rejection_cycle(ctx: FlatTopologyContext) -> None:
    """Claim -> for_review -> reject -> re-review -> approve, no --agent on the return legs.

    The fixture's own seed event is discarded first so this function owns the
    WP's entire lifecycle from ``planned``.
    """
    feature_dir = ctx.primary_feature_dir
    slug = ctx.slug

    # The fixture seeds a single planned -> claimed event with an unrelated
    # marker; start this WP's history fresh from genesis -> planned instead so
    # the sequence below fully controls it.
    import json

    seed = {
        "event_id": "01M04SEEDPLANNEDGENESIS001",
        "mission_slug": slug,
        "wp_id": _WP_ID,
        "from_lane": "genesis",
        "to_lane": "planned",
        "at": "2026-09-20T00:00:00+00:00",
        "actor": "seed",
        "force": True,
        "execution_mode": "worktree",
        "evidence": None,
        "reason": "seed",
        "review_ref": None,
        "feature_slug": slug,
    }
    ctx.status_events_path.write_text(json.dumps(seed) + "\n", encoding="utf-8")

    # 1. planned -> claimed: the ORIGINAL implementer claim — carries --agent.
    emit_status_transition(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug=slug,
            wp_id=_WP_ID,
            to_lane="claimed",
            actor="impl-alice",
            policy_metadata=build_claim_policy_metadata(11111, "2026-09-20T00:00:01+00:00", "impl-alice"),
        )
    )
    # 2. claimed -> in_progress
    emit_status_transition(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug=slug,
            wp_id=_WP_ID,
            to_lane="in_progress",
            actor="impl-alice",
            workspace_context="worktree",
        )
    )
    # 3. in_progress -> for_review
    emit_status_transition(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug=slug,
            wp_id=_WP_ID,
            to_lane="for_review",
            actor="impl-alice",
            implementation_evidence_present=True,
        )
    )
    # 4. for_review -> in_review: the reviewer claims it.
    emit_status_transition(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug=slug,
            wp_id=_WP_ID,
            to_lane="in_review",
            actor="reviewer-carl",
        )
    )
    # 5. in_review -> planned: REJECT with review feedback (a real, forced rollback).
    emit_status_transition(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug=slug,
            wp_id=_WP_ID,
            to_lane="planned",
            actor="reviewer-carl",
            force=True,
            reason="review-feedback: needs rework before approval",
            review_result=ReviewResult(
                reviewer="reviewer-carl",
                verdict="rejected",
                reference="review-ref-4786-a",
            ),
        )
    )
    # 5b. The rollback ALSO releases the claim triple (#4673's exact mechanism —
    # move-task's _mt_rollback_additions / _build_claim_review_override, emitted
    # here directly since this test bypasses the move-task CLI wrapper).
    emit_inner_state_changed(
        feature_dir,
        _WP_ID,
        WPInnerStateDelta(release_runtime_claim=True),
        actor="reviewer-carl",
        mission_slug=slug,
    )
    # 6. Re-review: planned -> claimed -> in_progress -> for_review, NO --agent
    # this time (no policy_metadata carries a claimant — the pinned repro).
    emit_status_transition(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug=slug,
            wp_id=_WP_ID,
            to_lane="claimed",
            actor="impl-alice",
        )
    )
    emit_status_transition(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug=slug,
            wp_id=_WP_ID,
            to_lane="in_progress",
            actor="impl-alice",
            workspace_context="worktree",
        )
    )
    emit_status_transition(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug=slug,
            wp_id=_WP_ID,
            to_lane="for_review",
            actor="impl-alice",
            implementation_evidence_present=True,
        )
    )
    emit_status_transition(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug=slug,
            wp_id=_WP_ID,
            to_lane="in_review",
            actor="reviewer-carl",
        )
    )
    # 7. Approve: in_review -> approved, NO --agent.
    emit_status_transition(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug=slug,
            wp_id=_WP_ID,
            to_lane="approved",
            actor="reviewer-carl",
            review_result=ReviewResult(
                reviewer="reviewer-carl",
                verdict="approved",
                reference="review-ref-4786-b",
            ),
        )
    )


class TestAcceptGateRejectionCycle:
    """T015 (red, pinned #4786) / T020 (green via the read-root projection)."""

    def test_ordinary_rejection_cycle_reaches_accept_with_no_missing_agent(self, flat_topology_mission: FlatTopologyContext) -> None:
        """GREEN (post-fix): the derived implementer-of-record clears the block.

        Before WP04's read-root projection this asserted the OPPOSITE — the
        summary carried a "missing agent in canonical runtime state" entry for
        an approved WP that had, in fact, been fully implemented and reviewed.
        That was the RED baseline pinned by #4786; see this test's git history
        / the WP04 PR description for the red-run evidence.
        """
        _drive_rejection_cycle(flat_topology_mission)

        summary = collect_feature_summary(
            flat_topology_mission.repo,
            flat_topology_mission.slug,
            strict_metadata=True,
            mutate_matrix=False,
        )

        assert _missing_agent_issues(summary.metadata_issues) == []

    def test_never_owned_wp_still_refuses_honestly_with_a_named_repair(self, flat_topology_mission: FlatTopologyContext) -> None:
        """A WP that was never claimed at all must still refuse — no fabrication.

        The read-root projection derives NOTHING for a WP with no claim event,
        so the accept gate's "missing agent" refusal still fires — and, per
        FR-006/SC-003, now names its repair instead of leaving the operator to
        guess.
        """
        summary = collect_feature_summary(
            flat_topology_mission.repo,
            flat_topology_mission.slug,
            strict_metadata=True,
            mutate_matrix=False,
        )

        missing = _missing_agent_issues(summary.metadata_issues)
        assert missing, "a never-claimed WP must still be refused, not silently passed"
        assert any(_REPAIR_HINT in issue for issue in missing)


class TestMergeMissionOptionGuard:
    """T019 (#4786 FR-008) — ``merge.py``'s ``--mission`` OptionInfo guard.

    ``mission: str = typer.Option(None, "--mission", ...)`` resolves its
    default at CLI-runtime only. A caller that invokes the ``merge`` command's
    helpers directly as plain Python functions without supplying ``mission=``
    gets the raw, truthy, non-``str`` ``OptionInfo`` sentinel back — and
    ``(mission or "").strip()`` used to raise ``AttributeError`` instead of
    falling through to mission auto-detection / the clean "Use --mission"
    diagnostic. Co-located with the rest of WP04's #4786 read-side coverage
    per this WP's file-scope allowlist.
    """

    def test_clean_mission_option_treats_unresolved_optioninfo_as_unset(self) -> None:
        import typer

        from specify_cli.cli.commands.merge import _clean_mission_option

        unresolved = typer.Option(None, "--mission")
        assert _clean_mission_option(unresolved) is None
        assert _clean_mission_option("034-real-slug") == "034-real-slug"
        assert _clean_mission_option(None) is None

    def test_resolve_slug_or_exit_does_not_crash_on_unresolved_optioninfo(self, tmp_path: Path) -> None:
        """The exact crash site (merge.py:259): no ``AttributeError``, ever."""
        import subprocess

        import typer

        from specify_cli.cli.commands.merge import _resolve_slug_or_exit

        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

        unresolved = typer.Option(None, "--mission")
        # Falls through to auto-detection (no mission dirs, detached/unnamed
        # branch) and returns None/raw-handle — never raises.
        result = _resolve_slug_or_exit(repo, unresolved)
        assert result is None or isinstance(result, str)

    def test_dispatch_resume_does_not_crash_on_unresolved_optioninfo(self, tmp_path: Path) -> None:
        """The second crash site (merge.py:456): same guard, same non-crash contract."""
        import subprocess

        import typer

        from specify_cli.cli.commands.merge import _dispatch_resume

        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

        unresolved = typer.Option(None, "--mission")
        with pytest.raises(typer.Exit):
            # No interrupted merge state exists — a clean typer.Exit, not an
            # AttributeError from the old unguarded ``.strip()``.
            _dispatch_resume(repo, unresolved)
