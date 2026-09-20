from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.cli.commands.agent import workflow
from specify_cli.frontmatter import write_frontmatter
from specify_cli.review.artifacts import AffectedFile, ReviewCycleArtifact
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event

pytestmark = pytest.mark.git_repo


def _init_repo(repo: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def review_pointer_repo(tmp_path: Path) -> tuple[Path, Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    mission_slug = "001-review-pointer"
    feature_dir = repo / "kitty-specs" / mission_slug
    wp_dir = feature_dir / "tasks" / "WP01-core"
    wp_dir.mkdir(parents=True)
    (feature_dir / "tasks.md").write_text("### WP01 - Core\n\n- [x] T001 Done\n", encoding="utf-8")
    write_frontmatter(
        feature_dir / "tasks" / "WP01-core.md",
        {
            "work_package_id": "WP01",
            "title": "Core",
            "subtasks": ["T001"],
            "dependencies": [],
            "review_status": "",
            "review_feedback": "",
        },
        "# WP01\n",
    )
    ReviewCycleArtifact(
        cycle_number=2,
        wp_id="WP01",
        mission_slug=mission_slug,
        reviewer_agent="codex",
        reviewed_at="2026-04-10T06:36:14Z",
        affected_files=[AffectedFile(path="src/app.py", line_range="10-20")],
        reproduction_command="pytest tests/agent -q",
        body="**Issue**: Persist canonical review feedback.\n",
    ).write(wp_dir / "review-cycle-2.md")
    return repo, feature_dir, mission_slug


def test_canonical_review_cycle_pointer_resolves_for_fix_context(
    review_pointer_repo: tuple[Path, Path, str],
) -> None:
    repo, feature_dir, mission_slug = review_pointer_repo
    pointer = f"review-cycle://{mission_slug}/WP01-core/review-cycle-2.md"
    append_event(
        feature_dir,
        StatusEvent(
            event_id="seed-reject",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.PLANNED,
            at="2026-01-01T00:00:00+00:00",
            actor="reviewer",
            force=False,
            execution_mode="worktree",
            review_ref=pointer,
        ),
    )

    has_feedback, ref, path, source = workflow._resolve_review_feedback_context(
        feature_dir,
        "WP01",
        "",
    )

    assert has_feedback is True
    assert source == "canonical"
    assert ref == pointer
    assert path == feature_dir / "tasks" / "WP01-core" / "review-cycle-2.md"
    assert ReviewCycleArtifact.from_file(path).body.startswith("**Issue**")


def test_fix_context_skips_action_review_claim_sentinel(
    review_pointer_repo: tuple[Path, Path, str],
) -> None:
    repo, feature_dir, mission_slug = review_pointer_repo
    pointer = f"review-cycle://{mission_slug}/WP01-core/review-cycle-2.md"
    append_event(
        feature_dir,
        StatusEvent(
            event_id="seed-claim",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane=Lane.FOR_REVIEW,
            to_lane=Lane.IN_REVIEW,
            at="2026-01-01T00:00:00+00:00",
            actor="reviewer",
            force=False,
            execution_mode="worktree",
            review_ref="action-review-claim",
        ),
    )
    append_event(
        feature_dir,
        StatusEvent(
            event_id="seed-reject",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.PLANNED,
            at="2026-01-01T00:00:01+00:00",
            actor="reviewer",
            force=False,
            execution_mode="worktree",
            review_ref=pointer,
        ),
    )

    ref, path, _ = workflow._latest_review_feedback_reference(feature_dir, "WP01")

    assert ref == pointer
    assert path is not None


def test_fix_context_skips_synthetic_approval_token(
    review_pointer_repo: tuple[Path, Path, str],
) -> None:
    """#4327 field-evidence regression (2026-09-19): an APPROVED work package
    whose newest ``review_ref`` is the synthetic ``auto-approval:<WP>:<date>``
    token must resolve to "no feedback present" -- the token is a verdict
    marker, not a path. Before the fix the token (or, earlier, the operator's
    ``--note`` prose that used to fill the slot) was resolved as a pointer,
    found no artifact, and made ``agent action implement`` refuse to re-claim
    the approved WP with a bogus "review feedback artifact is missing" error."""
    repo, feature_dir, mission_slug = review_pointer_repo
    append_event(
        feature_dir,
        StatusEvent(
            event_id="seed-approve",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.APPROVED,
            at="2026-01-01T00:00:00+00:00",
            actor="reviewer",
            force=False,
            execution_mode="worktree",
            review_ref="auto-approval:WP01:20260920",
            reason="Codex APPROVE after 3 review cycles: all findings closed; 41 tests; suite green.",
        ),
    )

    has_feedback, ref, path, source = workflow._resolve_review_feedback_context(
        feature_dir,
        "WP01",
        "",
    )

    assert has_feedback is False
    assert ref is None
    assert path is None
    assert source is None


def test_fix_context_skips_synthetic_rejection_token_and_falls_back_to_real_pointer(
    review_pointer_repo: tuple[Path, Path, str],
) -> None:
    """A synthetic ``review:<WP>`` token (a rejection that left no feedback
    artifact) is skipped like a sentinel; an OLDER real pointer still wins the
    scan, exactly as it does for ``action-review-claim``."""
    repo, feature_dir, mission_slug = review_pointer_repo
    pointer = f"review-cycle://{mission_slug}/WP01-core/review-cycle-2.md"
    append_event(
        feature_dir,
        StatusEvent(
            event_id="seed-reject",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.PLANNED,
            at="2026-01-01T00:00:00+00:00",
            actor="reviewer",
            force=False,
            execution_mode="worktree",
            review_ref=pointer,
        ),
    )
    append_event(
        feature_dir,
        StatusEvent(
            event_id="seed-reject-no-artifact",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.IN_PROGRESS,
            at="2026-01-01T00:00:01+00:00",
            actor="reviewer",
            force=False,
            execution_mode="worktree",
            review_ref="review:WP01",
        ),
    )

    ref, path, _ = workflow._latest_review_feedback_reference(feature_dir, "WP01")

    assert ref == pointer
    assert path is not None


def test_legacy_feedback_pointer_remains_readable_with_deprecated_kind(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    common_dir = repo / ".git"
    legacy = common_dir / "spec-kitty" / "feedback" / "001-review-pointer" / "WP01" / "feedback.md"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("legacy feedback", encoding="utf-8")

    resolved = workflow._resolve_review_feedback_pointer(
        repo,
        "feedback://001-review-pointer/WP01/feedback.md",
    )

    assert resolved == legacy.resolve()
