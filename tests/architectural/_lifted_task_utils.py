"""Single home of the set_scalar append-on-miss retirement tests (#5015).

``tests/task_utils/test_set_scalar_retired.py`` (out of matrix) and its always-on lift
``tests/architectural/test_lifted_task_utils.py`` both import these, so the per-PR gate runs
exactly what the source suite runs and the two cannot drift apart.
"""

from __future__ import annotations

import pytest

from specify_cli.task_utils.support import TaskCliError, extract_scalar, set_scalar


def test_set_scalar_updates_existing_key() -> None:
    frontmatter = 'work_package_id: "WP01"\nlane: "planned"\n'
    updated = set_scalar(frontmatter, "lane", "in_progress")
    assert extract_scalar(updated, "lane") == "in_progress"
    # No duplicate key is introduced by the update.
    assert updated.count("lane:") == 1


def test_set_scalar_refuses_append_on_miss() -> None:
    frontmatter = 'work_package_id: "WP01"\n'
    with pytest.raises(TaskCliError):
        set_scalar(frontmatter, "lane", "planned")


def test_set_scalar_never_appends_inline_review_feedback_key() -> None:
    """The exact #3372 shape: an absent ``review_feedback`` key must NOT be
    appended inline. Fail closed instead."""
    frontmatter = 'work_package_id: "WP01"\ntitle: "Test"\n'
    with pytest.raises(TaskCliError):
        set_scalar(frontmatter, "review_feedback", "review-cycle://x/y/review-cycle-1.md")
    assert "review_feedback" not in frontmatter
