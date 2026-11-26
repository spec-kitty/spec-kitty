"""#7588: ``move-task --to planned --agent <reviewer>`` must not rebind the WP owner.

A move that hands a WP back for work (a review rejection into ``planned`` or
``in_progress``, an approved reopen, a bounce out of ``for_review``) names in
``--agent`` who acted (the transition's actor); it is not a reassignment. A move
into ``planned`` also releases the WP's runtime claim (#2512). Before the fix, a
reviewer whose identity differed from the current claim holder was stamped into
the reduced ``agent`` (ownership) slot, overriding the release, so a different
implementer's re-claim was refused with "Agent mismatch ... assigned to
<reviewer>" and needed ``--force``. Reassignment on such a move is explicit:
``--assignee``.

Every test drives the real ``agent tasks move-task`` entry point.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from specify_cli.status import wp_snapshot_state
from specify_cli.status.resolved_binding import RESOLVED_PROFILE_ABSENT
from tests.specify_cli.cli.commands.agent import _rework_loop_harness as h
from tests.specify_cli.cli.commands.agent.test_tasks_cli_contract_coord import (
    _build_coord_protected_tree,
    _invoke,
)
from tests.mocked_env import setup_mocked_env

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_PLANNED_ROUTES = ("for_review_to_planned", "in_review_to_planned")


def _owner(feature_dir: Path) -> Any:
    snapshot = wp_snapshot_state(feature_dir, h.WP) or {}
    return snapshot.get("agent")


@pytest.mark.parametrize("route", _PLANNED_ROUTES)
def test_rejection_to_planned_releases_the_claim_instead_of_rebinding_it(route: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)
    assert _owner(m.feature_dir) == h.IMPLEMENTER

    h.reject(m, route, h.REVIEWER)

    assert not _owner(m.feature_dir), f"--agent on a rejection rebound the WP owner to {_owner(m.feature_dir)!r}"


@pytest.mark.parametrize("route", _PLANNED_ROUTES)
def test_a_new_implementer_claims_a_rejected_wp_without_force(route: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The released WP is back in the pool: any implementer claims it unforced."""
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)
    h.reject(m, route, h.REVIEWER)

    claimed = h.move(m, h.WP, "claimed", h.THIRD)

    assert claimed.exit_code == 0, claimed.output
    assert "Agent mismatch" not in claimed.output
    assert _owner(m.feature_dir) == h.THIRD


def test_the_implementer_re_claims_a_rejected_wp_without_force(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)
    h.reject(m, "for_review_to_planned", h.REVIEWER)

    claimed = h.move(m, h.WP, "claimed", h.IMPLEMENTER)

    assert claimed.exit_code == 0, claimed.output
    assert _owner(m.feature_dir) == h.IMPLEMENTER


def test_assignee_on_a_rejection_reassigns_the_wp_explicitly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reassignment on a move into ``planned`` is the explicit ``--assignee`` flag."""
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)
    feedback = m.repo / "feedback.md"
    feedback.write_text("## Issues\n\nFix this thing.\n", encoding="utf-8")

    rejected = h.move(m, h.WP, "planned", h.REVIEWER, "--review-feedback-file", str(feedback), "--assignee", h.THIRD)

    assert rejected.exit_code == 0, rejected.output
    snapshot = wp_snapshot_state(m.feature_dir, h.WP) or {}
    assert snapshot.get("agent") == h.THIRD
    assert snapshot.get("assignee") == h.THIRD
    # The reviewer's binding does not describe the assignee: it is recorded absent.
    assert snapshot.get("role") == "implementer"
    assert snapshot.get("agent_profile") == RESOLVED_PROFILE_ABSENT
    assert h.move(m, h.WP, "claimed", h.THIRD).exit_code == 0


def test_agent_on_a_non_planned_move_still_records_the_owner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control: a review claim is not a hand-back, so ``--agent`` binds (#3029 stays)."""
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)

    claimed = h.move(m, h.WP, "in_review", h.REVIEWER)

    assert claimed.exit_code == 0, claimed.output
    assert _owner(m.feature_dir) == h.REVIEWER


def test_coord_skip_arm_rejection_leaves_the_owner_untouched(tmp_path: Path) -> None:
    """The coordination skip arm (protected primary) never rebinds on a rejection.

    Since #7861 (operator ruling DM-01M89KDT5DZQ4DX6ZFX54HY3J3) the hand-back's
    review-cycle verdict is committed to the coordination branch (its
    COORD-partition home), so the rejection succeeds; the reviewer's ``--agent``
    still never takes the ownership slot. The envelope's
    ``frontmatter_fields_skipped`` keys off the same ``_mt_agent_binds_owner``
    predicate the emit uses (pinned by the predicate tests below).
    """
    ctx = _build_coord_protected_tree(tmp_path / "coord")
    owner_before = (wp_snapshot_state(ctx.coord_feature_dir, "WP01") or {}).get("agent")
    feedback = tmp_path / "feedback.md"
    feedback.write_text("**Issue**: rework requested.\n", encoding="utf-8")
    with setup_mocked_env(ctx.repo, mission_slug=ctx.slug, workspace_resolution=None, auto_commit_default=True):
        code, text, _ = _invoke(
            [
                "move-task",
                "WP01",
                "--to",
                "planned",
                "--review-feedback-file",
                str(feedback),
                "--mission",
                ctx.slug,
                "--agent",
                "reviewer-renata",
                "--force",
                "--json",
            ]
        )

    assert code == 0, text
    assert (wp_snapshot_state(ctx.coord_feature_dir, "WP01") or {}).get("lane") == "planned"
    assert (wp_snapshot_state(ctx.coord_feature_dir, "WP01") or {}).get("agent") == owner_before


def test_coord_skip_arm_still_reports_the_agent_on_a_binding_move(tmp_path: Path) -> None:
    """Positive control for the envelope: a non-planned move still lists ``agent``."""
    ctx = _build_coord_protected_tree(tmp_path / "coord")
    with setup_mocked_env(ctx.repo, mission_slug=ctx.slug, workspace_resolution=None, auto_commit_default=True):
        code, text, payload = _invoke(["move-task", "WP01", "--to", "for_review", "--mission", ctx.slug, "--agent", "implementer-ivan", "--force", "--json"])

    assert code == 0, text
    assert payload is not None
    assert payload.get("frontmatter_fields_skipped") == ["agent"], payload


def test_assignee_on_the_re_implement_edge_reassigns_explicitly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``in_review -> in_progress`` is a rejection too: ``--assignee`` reassigns, ``--agent`` does not."""
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)
    assert h.move(m, h.WP, "in_review", h.REVIEWER).exit_code == 0
    feedback = m.repo / "feedback.md"
    feedback.write_text("## Issues\n\nFix this thing.\n", encoding="utf-8")

    rejected = h.move(m, h.WP, "in_progress", h.REVIEWER, "--review-feedback-file", str(feedback), "--assignee", h.IMPLEMENTER)

    assert rejected.exit_code == 0, rejected.output
    assert _owner(m.feature_dir) == h.IMPLEMENTER


# --- Pure predicates (tasks_move_task_hops) --------------------------------------------------

_HANDS_BACK = [
    ("for_review", "planned"),
    ("in_review", "planned"),
    ("approved", "planned"),
    ("in_progress", "planned"),
    ("in_review", "in_progress"),
    ("approved", "in_progress"),
    ("for_review", "in_progress"),
]
_BINDING = [
    ("planned", "claimed"),
    ("for_review", "claimed"),
    ("claimed", "in_progress"),
    ("in_progress", "for_review"),
    ("for_review", "in_review"),
    ("in_review", "approved"),
    ("approved", "done"),
]


def _st(old: str, target: str, agent: str | None = "reviewer", assignee: str | None = None) -> Any:
    from types import SimpleNamespace

    from specify_cli.status import Lane

    return SimpleNamespace(old_lane=Lane(old), target_lane=Lane(target), agent=agent, assignee=assignee, resolved_binding=None, implementer_identity=None)


@pytest.mark.parametrize(("old", "target"), _HANDS_BACK)
def test_agent_never_binds_the_owner_when_work_is_handed_back(old: str, target: str) -> None:
    from specify_cli.cli.commands.agent.tasks_move_task_hops import _mt_agent_binds_owner, _mt_ownership_fields

    assert not _mt_agent_binds_owner(_st(old, target))
    assert _mt_ownership_fields(_st(old, target)) == {}
    reassigned = _mt_ownership_fields(_st(old, target, assignee="next-implementer"))
    assert reassigned["agent"] == "next-implementer"
    assert reassigned["role"] == "implementer"
    assert reassigned["agent_profile"] == RESOLVED_PROFILE_ABSENT


@pytest.mark.parametrize(("old", "target"), _BINDING)
def test_agent_binds_the_owner_on_every_other_move(old: str, target: str) -> None:
    from specify_cli.cli.commands.agent.tasks_move_task_hops import _mt_agent_binds_owner, _mt_ownership_fields

    assert _mt_agent_binds_owner(_st(old, target))
    assert _mt_ownership_fields(_st(old, target, assignee="someone-else"))["agent"] == "reviewer"
    assert not _mt_agent_binds_owner(_st(old, target, agent=None))
    assert _mt_ownership_fields(_st(old, target, agent=None, assignee="someone-else")) == {}


def test_a_reviewer_bounce_out_of_for_review_keeps_the_implementer_as_owner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``for_review -> in_progress`` by the reviewer is a hand-back: the slot keeps the implementer."""
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)

    bounced = h.move(m, h.WP, "in_progress", h.REVIEWER, "--force")

    assert bounced.exit_code == 0, bounced.output
    assert _owner(m.feature_dir) == h.IMPLEMENTER
    resubmitted = h.move(m, h.WP, "for_review", h.IMPLEMENTER)
    assert resubmitted.exit_code == 0, resubmitted.output


def test_a_forced_claim_out_of_for_review_binds_the_claimant_with_its_shell_pid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``for_review -> claimed`` is a claim, not a hand-back: ``--agent`` and ``--shell-pid`` are the new owner's."""
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)

    claimed = h.move(m, h.WP, "claimed", h.REVIEWER, "--force", "--shell-pid", "4242")

    assert claimed.exit_code == 0, claimed.output
    assert _owner(m.feature_dir) == h.REVIEWER


def test_a_rejection_does_not_plant_the_reviewers_shell_pid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)
    feedback = m.repo / "feedback.md"
    feedback.write_text("## Issues\n\nFix this thing.\n", encoding="utf-8")

    rejected = h.move(m, h.WP, "planned", h.REVIEWER, "--review-feedback-file", str(feedback), "--shell-pid", "4242")

    assert rejected.exit_code == 0, rejected.output
    snapshot = wp_snapshot_state(m.feature_dir, h.WP) or {}
    assert not snapshot.get("agent")
    assert not snapshot.get("shell_pid"), snapshot.get("shell_pid")


# --- Operator ruling on #7588 follow-up: a hand-back into in_progress returns ownership --------
# to the implementer of record (``status.latest_implementer_identity``), not the reviewer who
# held the review claim. A move into ``planned`` still releases; ``--assignee`` still wins.


def _reject_to_in_progress(m: h.ReworkMission, *extra: str) -> h.Result:
    assert h.move(m, h.WP, "in_review", h.REVIEWER).exit_code == 0
    assert _owner(m.feature_dir) == h.REVIEWER
    feedback = m.repo / "feedback-ip.md"
    feedback.write_text("## Issues\n\nFix this thing.\n", encoding="utf-8")
    return h.move(m, h.WP, "in_progress", h.REVIEWER, "--review-feedback-file", str(feedback), *extra)


def test_an_in_review_rejection_into_in_progress_returns_the_wp_to_its_implementer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.status import _actor_key

    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)

    rejected = _reject_to_in_progress(m)

    assert rejected.exit_code == 0, rejected.output
    owner = _owner(m.feature_dir)
    assert _actor_key(owner) == _actor_key(h.IMPLEMENTER), f"slot still held by {owner!r}"
    snapshot = wp_snapshot_state(m.feature_dir, h.WP) or {}
    assert snapshot.get("role") == "implementer"
    # The returned owner is enforced: an unrelated tool is refused, the implementer resubmits.
    third = h.move(m, h.WP, "for_review", h.THIRD)
    assert third.exit_code != 0 and "Agent mismatch" in third.output
    assert h.move(m, h.WP, "for_review", h.IMPLEMENTER).exit_code == 0


def test_assignee_still_wins_over_the_returning_implementer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)

    rejected = _reject_to_in_progress(m, "--assignee", h.THIRD)

    assert rejected.exit_code == 0, rejected.output
    assert _owner(m.feature_dir) == h.THIRD


@pytest.mark.parametrize(("old", "target"), [("in_review", "in_progress"), ("approved", "in_progress"), ("for_review", "in_progress")])
def test_a_non_planned_hand_back_returns_ownership_to_the_implementer_of_record(old: str, target: str) -> None:
    from specify_cli.cli.commands.agent.tasks_move_task_hops import _mt_ownership_fields

    st = _st(old, target)
    st.implementer_identity = "claude:opus:implementer-ivan"
    fields = _mt_ownership_fields(st)
    assert fields["agent"] == "claude:opus:implementer-ivan"
    assert fields["role"] == "implementer"
    assert fields["agent_profile"] == RESOLVED_PROFILE_ABSENT


def test_a_move_into_planned_still_releases_rather_than_returning_ownership() -> None:
    from specify_cli.cli.commands.agent.tasks_move_task_hops import _mt_ownership_fields

    st = _st("in_review", "planned")
    st.implementer_identity = "claude:opus:implementer-ivan"
    assert _mt_ownership_fields(st) == {}


def test_a_hand_back_to_the_current_holder_leaves_the_slot_alone() -> None:
    """The slot already holds the implementer (a bounce out of ``for_review``): no re-stamp."""
    from specify_cli.cli.commands.agent.tasks_move_task_hops import _mt_ownership_fields

    st = _st("for_review", "in_progress")
    st.implementer_identity = "claude:opus:implementer-ivan"
    st.current_agent = "claude:opus:implementer-ivan:implementer"
    assert _mt_ownership_fields(st) == {}


@pytest.mark.parametrize("identity", [None, "", "implement-command", "user"])
def test_an_unknown_or_generic_implementer_leaves_the_slot_alone(identity: str | None) -> None:
    from specify_cli.cli.commands.agent.tasks_move_task_hops import _mt_ownership_fields

    st = _st("in_review", "in_progress")
    st.implementer_identity = identity
    assert _mt_ownership_fields(st) == {}


def test_a_hand_back_to_the_implementer_clears_the_reviewers_shell_pid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The returned claim never pairs the implementer with the reviewer's shell (landing fold)."""
    from specify_cli.status import _actor_key

    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)
    assert h.move(m, h.WP, "in_review", h.REVIEWER, "--shell-pid", "4242").exit_code == 0
    assert (wp_snapshot_state(m.feature_dir, h.WP) or {}).get("shell_pid") == 4242
    feedback = m.repo / "feedback-pid.md"
    feedback.write_text("## Issues\n\nFix this thing.\n", encoding="utf-8")

    rejected = h.move(m, h.WP, "in_progress", h.REVIEWER, "--review-feedback-file", str(feedback))

    assert rejected.exit_code == 0, rejected.output
    snapshot = wp_snapshot_state(m.feature_dir, h.WP) or {}
    assert _actor_key(_owner(m.feature_dir)) == _actor_key(h.IMPLEMENTER)
    assert not snapshot.get("shell_pid"), snapshot.get("shell_pid")
    assert not snapshot.get("shell_pid_created_at"), snapshot.get("shell_pid_created_at")
