"""FR-006 (WP08, mission upgrade-atomicity-recovery): retire the append-on-miss
frontmatter writer that once caused the #3372 dual-``review_feedback`` key.

Three guards land here:

1. ``set_scalar`` STILL updates an existing scalar key (the symbol is retained
   because ``task_utils/__init__.py`` and ``cli/commands/agent/workflow.py``
   re-export it — deleting it would break those unowned imports).
2. ``set_scalar`` FAILS CLOSED on the append-on-miss path: when the key is
   absent it raises instead of appending ``key: value`` inline, so no path can
   re-introduce the inline ``review_feedback`` key #3372 was born from.
3. SC-003 clause 1: two consecutive review cycles on one WP go through the real
   ``create_rejected_review_cycle`` path, which stores a ``review-cycle://``
   pointer — never an inline ``review_feedback`` frontmatter key. The WP file
   therefore never gains an inline ``review_feedback`` key (0, never 2).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.task_utils.support import TaskCliError, extract_scalar, set_scalar, split_frontmatter

# The tests and helpers shared with this suite's always-on lift live once, in
# ``tests/architectural/_lifted_task_utils.py`` (#5015); importing a test is what makes pytest collect it here.
from tests.architectural._lifted_task_utils import test_set_scalar_updates_existing_key as test_set_scalar_updates_existing_key
from tests.architectural._lifted_task_utils import test_set_scalar_refuses_append_on_miss as test_set_scalar_refuses_append_on_miss
from tests.architectural._lifted_task_utils import (
    test_set_scalar_never_appends_inline_review_feedback_key as test_set_scalar_never_appends_inline_review_feedback_key,
)

# [fast, unit] (not git_repo): the one review-cycle case does a light, isolated
# `git init` in tmp_path (<1s, parallel-safe), so these belong in the fast lane.
# tests/task_utils/ is a new top-level dir that only the fast-tests-core-misc
# catch-all covers; a git_repo marker would pull it into the legacy integration
# core-misc selector that the live integration lane does not scope for this dir
# (dropping it from the #3284 replacement-union guard), so git_repo is the wrong
# route here.
pytestmark = [pytest.mark.fast, pytest.mark.unit]


# ---------------------------------------------------------------------------
# FR-006 guard 1: update-existing behavior is PRESERVED
# ---------------------------------------------------------------------------


def test_set_scalar_update_preserves_trailing_comment() -> None:
    frontmatter = 'work_package_id: "WP01"\nlane: "planned"  # keep me\n'
    updated = set_scalar(frontmatter, "lane", "in_progress")
    assert extract_scalar(updated, "lane") == "in_progress"
    assert "# keep me" in updated


# ---------------------------------------------------------------------------
# FR-006 guard 2: append-on-miss is FAIL-CLOSED (never appends an inline key)
# ---------------------------------------------------------------------------


def test_set_scalar_refuses_append_even_with_history_anchor() -> None:
    """The retired branch had a ``history:`` insertion anchor — it must be
    fully neutralized, not merely the tail-append leg."""
    frontmatter = 'work_package_id: "WP01"\nhistory:\n  - action: created\n'
    with pytest.raises(TaskCliError):
        set_scalar(frontmatter, "review_feedback", "value")
    # And nothing was written before the raise.
    assert "review_feedback" not in frontmatter


# ---------------------------------------------------------------------------
# SC-003 clause 1: two review cycles never produce an inline review_feedback key
# ---------------------------------------------------------------------------


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@e.com"], cwd=repo, check=True, capture_output=True)
    (repo / ".kittify").mkdir()
    return repo


def test_two_review_cycles_never_write_inline_review_feedback_key(tmp_path: Path) -> None:
    from specify_cli.review.cycle import create_rejected_review_cycle

    repo = _init_repo(tmp_path)
    mission_slug = "001-test-mission"
    wp_id = "WP01"
    wp_slug = "WP01-test-task"

    tasks_dir = repo / "kitty-specs" / mission_slug / "tasks"
    tasks_dir.mkdir(parents=True)
    wp_path = tasks_dir / f"{wp_slug}.md"
    wp_path.write_text(
        '---\nwork_package_id: "WP01"\ntitle: "Test Task"\n---\n\n# WP01 Prompt\n',
        encoding="utf-8",
    )

    feedback_one = tmp_path / "feedback-1.md"
    feedback_one.write_text("**Issue**: first cycle problem\n", encoding="utf-8")
    cycle_one = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug=mission_slug,
        wp_id=wp_id,
        wp_slug=wp_slug,
        feedback_source=feedback_one,
        reviewer_agent="reviewer",
    )

    feedback_two = tmp_path / "feedback-2.md"
    feedback_two.write_text("**Issue**: second cycle problem\n", encoding="utf-8")
    cycle_two = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug=mission_slug,
        wp_id=wp_id,
        wp_slug=wp_slug,
        feedback_source=feedback_two,
        reviewer_agent="reviewer",
    )

    # The canonical writer stores review-cycle:// pointers, never inline keys.
    assert cycle_one.pointer.startswith("review-cycle://")
    assert cycle_two.pointer.startswith("review-cycle://")
    assert cycle_one.pointer != cycle_two.pointer

    # Two distinct cycles actually ran.
    artifacts = sorted(cycle_one.artifact_path.parent.glob("review-cycle-*.md"))
    assert [p.name for p in artifacts] == ["review-cycle-1.md", "review-cycle-2.md"]

    # The WP frontmatter never gains an inline review_feedback key (the #3372
    # dual-key can never form: not two, not even one).
    frontmatter, _body, _padding = split_frontmatter(wp_path.read_text(encoding="utf-8"))
    assert extract_scalar(frontmatter, "review_feedback") is None
    assert wp_path.read_text(encoding="utf-8").count("review_feedback:") == 0
