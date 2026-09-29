"""Unit pins for :func:`specify_cli.lanes.worktree_allocator.predict_lane_worktree`.

The predict seam is the ONE lane-worktree placement decision (path + branch):
the write authority (``allocate_lane_worktree``) and the read-only mirrors
(``orchestrator-api resolve-workspace``, its transition guard) all consume it,
so the mid8 cutover — when it comes — is a single edit. These tests pin:

1. parity with the canonical naming seams it wraps (``code_lane_branch_name`` +
   ``worktree_path``, keyed on the creation input alone), and
2. read-only purity — composing a placement must never touch the filesystem.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.lanes.branch_naming import code_lane_branch_name, worktree_path
from specify_cli.lanes.worktree_allocator import predict_lane_worktree

pytestmark = [pytest.mark.unit, pytest.mark.fast]

MISSION_SLUG = "demo-feature-01J6XW9K"


def test_predict_matches_canonical_naming_seams(tmp_path: Path) -> None:
    """predict == (worktree_path(...), code_lane_branch_name(...)) byte-for-byte."""
    predicted_path, predicted_branch = predict_lane_worktree(tmp_path, MISSION_SLUG, "lane-a")
    assert predicted_path == worktree_path(tmp_path, MISSION_SLUG, lane_id="lane-a")
    assert predicted_branch == code_lane_branch_name(MISSION_SLUG, "lane-a")


def test_predict_uses_legacy_no_mid8_grammar(tmp_path: Path) -> None:
    """The composed dir name is ``{slug}-{lane}`` — no mid8 segment is appended.

    Lane naming takes no Mission identity input (FR-002); a mid8
    segment appears only when the slug itself already embeds one.
    """
    predicted_path, _ = predict_lane_worktree(tmp_path, MISSION_SLUG, "lane-a")
    assert predicted_path.name == f"{MISSION_SLUG}-lane-a"


def test_predict_is_read_only(tmp_path: Path) -> None:
    """Composing a placement creates nothing on disk (no .worktrees/, no dirs)."""
    before = sorted(tmp_path.rglob("*"))
    predict_lane_worktree(tmp_path, MISSION_SLUG, "lane-b")
    assert sorted(tmp_path.rglob("*")) == before
    assert not (tmp_path / ".worktrees").exists()
