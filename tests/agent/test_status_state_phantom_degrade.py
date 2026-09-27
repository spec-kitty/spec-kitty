"""#5180: the render and verdict STATUS_STATE reads must degrade on a phantom partition.

The #154 ambient-ancestor layout: the canonical-root walk from the mission dir
finds a git checkout that is NOT the mission's own (``<tmp>/ambient`` above
``<tmp>/ambient/repo/kitty-specs/<slug>``), so the placement seam recomposes the
STATUS_STATE partition against that foreign anchor and hands back a directory
that does not exist. Reading the event log there yields nothing, and the
reader swallows the absence -- the rejected-review feedback silently vanishes
from the next implement prompt. The handed mission dir provably holds the
mission, so it is its own STATUS_STATE home.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.cli.commands.agent import tasks_verdict_persistence, workflow_cores
from specify_cli.frontmatter import write_frontmatter
from specify_cli.review.artifacts import AffectedFile, ReviewCycleArtifact
from specify_cli.status.models import Lane, ReviewResult, StatusEvent
from specify_cli.status.store import append_event

pytestmark = pytest.mark.git_repo

_SLUG = "001-phantom-status-home"
_WP_SLUG = "WP01-core"


def _foreign_anchor_mission(tmp_path: Path) -> tuple[Path, str]:
    """A mission dir under an ambient checkout that is not its own repo, with a
    rejection event whose ``review_ref`` resolves to a real feedback artifact."""
    ambient = tmp_path / "ambient-checkout"
    ambient.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(ambient)], check=True)
    feature_dir = ambient / "repo" / "kitty-specs" / _SLUG
    (feature_dir / "tasks" / _WP_SLUG).mkdir(parents=True)
    write_frontmatter(
        feature_dir / "tasks" / f"{_WP_SLUG}.md",
        {"work_package_id": "WP01", "title": "Core", "subtasks": [], "dependencies": []},
        "# WP01\n",
    )
    ReviewCycleArtifact(
        cycle_number=1,
        wp_id="WP01",
        mission_slug=_SLUG,
        reviewer_agent="reviewer",
        reviewed_at="2026-09-27T10:00:00Z",
        affected_files=[AffectedFile(path="src/app.py", line_range="1-5")],
        reproduction_command="pytest tests/agent -q",
        body="**Issue**: #5180 feedback must survive a phantom status partition.\n",
    ).write(feature_dir / "tasks" / _WP_SLUG / "review-cycle-1.md")
    pointer = f"review-cycle://{_SLUG}/{_WP_SLUG}/review-cycle-1.md"
    append_event(
        feature_dir,
        StatusEvent(
            event_id="01PHANTOM5180000000000001",
            mission_slug=_SLUG,
            wp_id="WP01",
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.PLANNED,
            at="2026-09-27T10:00:00+00:00",
            actor="reviewer",
            force=False,
            execution_mode="worktree",
            review_ref=pointer,
            review_result=ReviewResult(
                reviewer="reviewer",
                verdict="changes_requested",
                reference=pointer,
            ),
        ),
    )
    return feature_dir, pointer


@pytest.mark.regression
def test_render_feedback_context_reads_handed_dir_under_phantom_partition(tmp_path: Path) -> None:
    """Public render entry (``workflow.py`` fix-mode handoff): feedback is present."""
    feature_dir, pointer = _foreign_anchor_mission(tmp_path)

    has_feedback, ref, feedback_file, source = workflow_cores.resolve_review_feedback_context(feature_dir, "WP01", "")

    assert has_feedback is True, "rejection feedback was silently masked by a phantom STATUS_STATE read"
    assert source == "canonical"
    assert ref == pointer
    assert feedback_file == feature_dir / "tasks" / _WP_SLUG / "review-cycle-1.md"


@pytest.mark.regression
def test_move_task_verdict_facts_read_handed_dir_under_phantom_partition(tmp_path: Path) -> None:
    """Move-task verdict read: the recorded rejection is found, not treated as absent."""
    feature_dir, _ = _foreign_anchor_mission(tmp_path)
    wp_path = feature_dir / "tasks" / f"{_WP_SLUG}.md"

    review_verdict, _artifact_path, artifact_name = tasks_verdict_persistence.resolve_review_verdict_facts(wp_path)

    assert review_verdict == "rejected", "recorded verdict was treated as absent under a phantom STATUS_STATE read"
    assert artifact_name is not None
