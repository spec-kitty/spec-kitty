"""#7588: ``move-task --to planned --agent <reviewer>`` must not rebind the WP owner.

A move into ``planned`` (a review rejection, an approved reopen, a rollback)
releases the WP's runtime claim (#2512). ``--agent`` on that move names who
acted (the transition's actor); it is not a reassignment. Before the fix, a
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
    refused = h.move(m, h.WP, "claimed", h.IMPLEMENTER)
    assert refused.exit_code != 0
    assert "Agent mismatch" in refused.output
    assert h.move(m, h.WP, "claimed", h.THIRD).exit_code == 0


def test_agent_on_a_non_planned_move_still_records_the_owner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control: the fix is scoped to moves into ``planned`` (#3029 stays)."""
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)

    claimed = h.move(m, h.WP, "in_review", h.REVIEWER)

    assert claimed.exit_code == 0, claimed.output
    assert _owner(m.feature_dir) == h.REVIEWER


def test_coord_skip_arm_does_not_rebind_or_report_the_agent_as_skipped_metadata(tmp_path: Path) -> None:
    """The coordination skip arm (protected primary) releases the claim too.

    ``frontmatter_fields_skipped`` names WP metadata the move would have bound;
    on a move into ``planned`` ``--agent`` binds nothing, so it is not listed.
    """
    ctx = _build_coord_protected_tree(tmp_path / "coord")
    with setup_mocked_env(ctx.repo, mission_slug=ctx.slug, workspace_resolution=None, auto_commit_default=True):
        code, text, payload = _invoke(["move-task", "WP01", "--to", "planned", "--mission", ctx.slug, "--agent", "reviewer-renata", "--force", "--json"])

    assert code == 0, text
    assert payload is not None
    assert payload["wp_file_update"] == "skipped"
    assert "frontmatter_fields_skipped" not in payload, payload
    snapshot = wp_snapshot_state(ctx.coord_feature_dir, "WP01") or {}
    assert snapshot.get("agent") != "reviewer-renata", snapshot


def test_coord_skip_arm_still_reports_the_agent_on_a_binding_move(tmp_path: Path) -> None:
    """Positive control for the envelope: a non-planned move still lists ``agent``."""
    ctx = _build_coord_protected_tree(tmp_path / "coord")
    with setup_mocked_env(ctx.repo, mission_slug=ctx.slug, workspace_resolution=None, auto_commit_default=True):
        code, text, payload = _invoke(["move-task", "WP01", "--to", "for_review", "--mission", ctx.slug, "--agent", "implementer-ivan", "--force", "--json"])

    assert code == 0, text
    assert payload is not None
    assert payload.get("frontmatter_fields_skipped") == ["agent"], payload
