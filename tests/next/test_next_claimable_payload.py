"""Regression tests for ``next --json`` claimability parity (issue #988).

Before this fix, ``spec-kitty next --json`` could emit
``mission_state: implement`` with ``wp_id: null`` even though the explicit
``spec-kitty agent action implement`` would auto-claim a concrete WP.
After the fix, the JSON payload exposes the same WP that the explicit
action would claim, or a structured ``selection_reason`` token when no
claim is possible.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from runtime.next.decision import DecisionKind, _state_to_action
from runtime.next.discovery import ClaimablePreview, preview_claimable_wp
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event
from specify_cli.status_lanes import OPERATOR_REASON_SOURCE
from tests.lane_test_utils import write_single_lane_manifest

pytestmark = pytest.mark.git_repo


def _init_repo(repo: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True)


def _scaffold(
    repo: Path,
    wps: dict[str, Lane],
    *,
    dependencies: dict[str, list[str]] | None = None,
    reason_sources: dict[str, str] | None = None,
) -> tuple[Path, str]:
    _init_repo(repo)
    (repo / ".kittify").mkdir()
    mission_slug = "claimable-payload-mission-01KRKTT5"
    feature_dir = repo / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_type": "software-dev", "mission_id": "01KRKTT58XC5KR0HF523333R9S"}),
        encoding="utf-8",
    )
    (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    write_single_lane_manifest(feature_dir, wp_ids=tuple(wps.keys()))
    for wp_id, lane in wps.items():
        deps = dependencies.get(wp_id, []) if dependencies else []
        (tasks_dir / f"{wp_id}.md").write_text(
            f"---\nwork_package_id: {wp_id}\ndependencies: {json.dumps(deps)}\ntitle: {wp_id}\n---\n# {wp_id}\n",
            encoding="utf-8",
        )
        reason_source = reason_sources.get(wp_id) if reason_sources else None
        append_event(
            feature_dir,
            StatusEvent(
                event_id=f"seed-{wp_id}-{lane}",
                mission_slug=mission_slug,
                wp_id=wp_id,
                from_lane=Lane.PLANNED,
                to_lane=lane,
                at="2026-05-14T12:00:00+00:00",
                actor="fixture",
                force=True,
                execution_mode="worktree",
                reason=("replan" if reason_source else None),
                reason_source=reason_source,
            ),
        )
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "seed claimable payload mission"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return feature_dir, mission_slug


def test_preview_claimable_wp_returns_first_planned_wp(tmp_path: Path) -> None:
    """``preview_claimable_wp`` returns the first claimable planned WP in candidate order."""
    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir, _ = _scaffold(repo, {"WP01": Lane.PLANNED, "WP02": Lane.PLANNED})

    preview = preview_claimable_wp(feature_dir)

    assert isinstance(preview, ClaimablePreview)
    assert preview.wp_id == "WP01"
    assert preview.selection_reason is None
    assert preview.candidates == ("WP01", "WP02")


def test_preview_claimable_wp_returns_selection_reason_when_all_in_progress(
    tmp_path: Path,
) -> None:
    """When no WP is planned, the helper emits ``all_wps_in_progress``."""
    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir, _ = _scaffold(repo, {"WP01": Lane.IN_PROGRESS})

    preview = preview_claimable_wp(feature_dir)

    assert preview.wp_id is None
    assert preview.selection_reason == "all_wps_in_progress"
    assert preview.candidates == ("WP01",)


def test_preview_claimable_wp_handles_missing_tasks_dir(tmp_path: Path) -> None:
    """A feature_dir with no tasks/ returns ``no_tasks_dir`` without raising."""
    feature_dir = tmp_path / "no-tasks-dir"
    feature_dir.mkdir()

    preview = preview_claimable_wp(feature_dir)

    assert preview.wp_id is None
    assert preview.selection_reason == "no_tasks_dir"
    assert preview.candidates == ()


def test_preview_claimable_wp_distinguishes_terminal_from_active(
    tmp_path: Path,
) -> None:
    """All-done missions return ``no_planned_wps``, not ``all_wps_in_progress``.

    Spec correctness: the latter token implies "wait for the active WP to
    finish"; the former implies "this mission is essentially complete from
    the implement-loop's perspective". Conflating the two would mislead
    operators.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir, _ = _scaffold(repo, {"WP01": Lane.DONE, "WP02": Lane.APPROVED})

    preview = preview_claimable_wp(feature_dir)

    assert preview.wp_id is None
    assert preview.selection_reason == "no_planned_wps"
    assert preview.candidates == ("WP01", "WP02")


def test_preview_claimable_wp_uses_frontmatter_id_not_filename(
    tmp_path: Path,
) -> None:
    """WP id source is YAML ``work_package_id``, the canonical claim source (FR-003)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir, _ = _scaffold(repo, {"WP01": Lane.PLANNED})

    # Rename the file to a slug-suffixed form (``WP01-foo.md``) and bake a
    # mismatched filename stem to prove the helper reads frontmatter, not filename.
    tasks_dir = feature_dir / "tasks"
    original = tasks_dir / "WP01.md"
    renamed = tasks_dir / "WP01-some-slug.md"
    original.rename(renamed)

    preview = preview_claimable_wp(feature_dir)

    # Discovery must still pick WP01 because the frontmatter says
    # ``work_package_id: WP01``, regardless of the slug-suffixed filename.
    assert preview.wp_id == "WP01"
    assert preview.selection_reason is None
    assert preview.candidates == ("WP01",)


def test_preview_claimable_wp_skips_dep_blocked_planned_wp(tmp_path: Path) -> None:
    """Planned WPs are not claimable until every dependency is approved or done."""
    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir, _ = _scaffold(
        repo,
        {"WP01": Lane.IN_PROGRESS, "WP02": Lane.PLANNED},
        dependencies={"WP02": ["WP01"]},
    )

    preview = preview_claimable_wp(feature_dir)

    assert preview.wp_id is None
    assert preview.selection_reason == "dependencies_not_satisfied"
    assert preview.candidates == ("WP01", "WP02")


def test_preview_claimable_wp_allows_dep_after_done(tmp_path: Path) -> None:
    """A dependent planned WP becomes claimable once upstream is ``done``."""
    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir, _ = _scaffold(
        repo,
        {"WP01": Lane.DONE, "WP02": Lane.PLANNED},
        dependencies={"WP02": ["WP01"]},
    )

    preview = preview_claimable_wp(feature_dir)

    assert preview.wp_id == "WP02"
    assert preview.selection_reason is None
    assert preview.candidates == ("WP01", "WP02")


def test_preview_claimable_wp_allows_dep_after_approved(tmp_path: Path) -> None:
    """A dependent planned WP becomes claimable once upstream is ``approved``.

    ``done`` is only reached at whole-mission merge time, so an ``approved``
    dependency (review passed, merge pending) must unblock the dependent WP;
    otherwise every same-mission dependency chain deadlocks.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir, _ = _scaffold(
        repo,
        {"WP01": Lane.APPROVED, "WP02": Lane.PLANNED},
        dependencies={"WP02": ["WP01"]},
    )

    preview = preview_claimable_wp(feature_dir)

    assert preview.wp_id == "WP02"
    assert preview.selection_reason is None
    assert preview.candidates == ("WP01", "WP02")


def test_preview_claimable_wp_allows_dep_after_operator_cancel(tmp_path: Path) -> None:
    """FR-009: a dependent becomes claimable once its dependency is
    canceled *with operator provenance*.

    The next-loop preview threads the reduced snapshot's provenance into the
    readiness authority, so a documented cancellation reads as an acceptable
    ending — parity with the primary claim gates rather than a strand.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir, _ = _scaffold(
        repo,
        {"WP01": Lane.CANCELED, "WP02": Lane.PLANNED},
        dependencies={"WP02": ["WP01"]},
        reason_sources={"WP01": OPERATOR_REASON_SOURCE},
    )

    preview = preview_claimable_wp(feature_dir)

    assert preview.wp_id == "WP02"
    assert preview.selection_reason is None
    assert preview.candidates == ("WP01", "WP02")


def test_preview_claimable_wp_gates_dep_after_synthetic_cancel(tmp_path: Path) -> None:
    """FR-009: a synthetic (no-provenance) cancellation stays blocking.

    Without operator provenance the cancellation is not an acceptable ending,
    so the dependent must remain suppressed with ``dependencies_not_satisfied``
    — the preview fails closed exactly like the claim gates.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir, _ = _scaffold(
        repo,
        {"WP01": Lane.CANCELED, "WP02": Lane.PLANNED},
        dependencies={"WP02": ["WP01"]},
        reason_sources={"WP01": "synthetic"},
    )

    preview = preview_claimable_wp(feature_dir)

    assert preview.wp_id is None
    assert preview.selection_reason == "dependencies_not_satisfied"
    assert preview.candidates == ("WP01", "WP02")


def test_preview_claimable_wp_preserves_independent_fanout(tmp_path: Path) -> None:
    """An independent planned WP remains claimable while another WP is active."""
    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir, _ = _scaffold(repo, {"WP01": Lane.IN_PROGRESS, "WP02": Lane.PLANNED})

    preview = preview_claimable_wp(feature_dir)

    assert preview.wp_id == "WP02"
    assert preview.selection_reason is None
    assert preview.candidates == ("WP01", "WP02")


def _advancing_implement_wp(feature_dir: Path, mission_slug: str, repo: Path) -> str | None:
    """Return the WP selected by advancing ``next``'s state-to-action path."""
    fake_workspace = SimpleNamespace(worktree_path=repo / ".worktrees" / "selected")
    with patch(
        "runtime.next.decision.resolve_workspace_for_wp",
        return_value=fake_workspace,
    ):
        action, wp_id, _ = _state_to_action(
            "implement",
            mission_slug,
            feature_dir,
            repo,
            "software-dev",
        )
    assert action == "implement"
    return wp_id


def test_advancing_next_skips_lower_numbered_dependency_blocked_wp(
    tmp_path: Path,
) -> None:
    """#4860: advancing selection agrees with query/action claimability."""
    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir, mission_slug = _scaffold(
        repo,
        {"WP01": Lane.PLANNED, "WP02": Lane.PLANNED},
        dependencies={"WP01": ["WP02"]},
    )

    preview = preview_claimable_wp(feature_dir)

    assert preview.wp_id == "WP02"
    assert _advancing_implement_wp(feature_dir, mission_slug, repo) == preview.wp_id


def test_advancing_next_rechecks_dependency_that_was_reopened(tmp_path: Path) -> None:
    """A formerly satisfied dependency cannot be cached by filename order."""
    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir, mission_slug = _scaffold(
        repo,
        {"WP01": Lane.PLANNED, "WP02": Lane.DONE},
        dependencies={"WP01": ["WP02"]},
    )

    assert preview_claimable_wp(feature_dir).wp_id == "WP01"
    assert _advancing_implement_wp(feature_dir, mission_slug, repo) == "WP01"

    append_event(
        feature_dir,
        StatusEvent(
            event_id="reopen-WP02-to-planned",
            mission_slug=mission_slug,
            wp_id="WP02",
            from_lane=Lane.DONE,
            to_lane=Lane.PLANNED,
            at="2026-05-15T12:00:00+00:00",
            actor="operator",
            force=True,
            execution_mode="worktree",
            reason="follow-up work required",
            reason_source=OPERATOR_REASON_SOURCE,
        ),
    )

    preview = preview_claimable_wp(feature_dir)
    assert preview.wp_id == "WP02"
    assert _advancing_implement_wp(feature_dir, mission_slug, repo) == preview.wp_id


def test_next_json_payload_serializes_claimable_wp_id(tmp_path: Path) -> None:
    """``next --json`` mission_state=implement now serializes the claimable wp_id.

    This is the canonical regression for issue #988: before the fix, this same
    mission state would return ``wp_id: null``; after the fix it returns the
    concrete WP that ``agent action implement`` would auto-claim.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _, mission_slug = _scaffold(repo, {"WP01": Lane.PLANNED})

    from runtime.next.runtime_bridge import query_current_state

    decision = query_current_state("codex", mission_slug, repo)

    assert decision.kind == DecisionKind.query
    assert decision.mission_state == "implement"
    assert decision.preview_step == "implement"
    assert decision.wp_id == "WP01"

    payload = decision.to_dict()
    assert payload["wp_id"] == "WP01"
    assert payload["mission_state"] == "implement"
    assert payload["preview_step"] == "implement"


def test_next_json_payload_surfaces_selection_reason_when_no_planned_wp(
    tmp_path: Path,
) -> None:
    """When no WP is claimable, the payload's ``reason`` exposes the structured token."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _, mission_slug = _scaffold(repo, {"WP01": Lane.IN_PROGRESS})

    from runtime.next.runtime_bridge import query_current_state

    decision = query_current_state("codex", mission_slug, repo)

    assert decision.kind == DecisionKind.query
    assert decision.mission_state == "implement"
    assert decision.preview_step == "implement"
    # No planned WP → wp_id remains None and reason carries the stable token.
    assert decision.wp_id is None
    assert decision.reason == "all_wps_in_progress"


def test_next_json_payload_wire_shape_unchanged_for_non_implement_state(
    tmp_path: Path,
) -> None:
    """Spec C-001: non-implement states keep their existing payload shape (wp_id null)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _, mission_slug = _scaffold(repo, {"WP01": Lane.FOR_REVIEW})

    from runtime.next.runtime_bridge import query_current_state

    decision = query_current_state("codex", mission_slug, repo)

    assert decision.kind == DecisionKind.query
    assert decision.mission_state == "review"
    assert decision.preview_step == "review"
    # For the review state we did NOT introduce wp_id serialization; the
    # existing wire shape (wp_id=None) is preserved.
    assert decision.wp_id is None
