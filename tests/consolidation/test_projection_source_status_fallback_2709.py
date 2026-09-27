"""Focused coverage for the #2709 projection source-status fallback branch.

Un-marked ``@pytest.mark.regression`` (landing fold: make
``@pytest.mark.regression`` mean exactly one thing). This is a permanent
branch-coverage test, not a red-first P0 reproduction — it is expected to
stay green.

``_project_status_bookkeeping_to_target`` unions the coord and target event logs
and rematerializes ``status.json`` from the union. When BOTH event logs are
absent (union is ``None``) but the coordination worktree still carries a
``status.json`` snapshot, the projection falls back to copying that snapshot to
the target surface (the ``elif source_status_bytes is not None`` branch). The
end-to-end #2709 tests always have an event log, so this fast fallback branch is
pinned here by reusing the proven coord-topology worktree bootstrap.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import specify_cli.status  # noqa: F401  # import-order guard (see #2711 harness)

from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.consolidation.bookkeeping_projection import _project_status_bookkeeping_to_target
from tests.consolidation.test_issue_2711_merge_rollback_resume_coherence import (
    MID8,
    MISSION_SLUG,
    _bootstrap_coord_mission,
    _init_git_repo,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]


def test_projection_copies_source_status_when_no_event_logs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    primary_feature_dir = _bootstrap_coord_mission(repo)

    coord_worktree = CoordinationWorkspace.worktree_path(repo, MISSION_SLUG, MID8)
    coord_feature_dir = coord_worktree / "kitty-specs" / MISSION_SLUG

    # Drive the union to ``None``: remove BOTH the coord (source) and primary
    # (target) event logs, leaving only a coord ``status.json`` snapshot.
    (coord_feature_dir / "status.events.jsonl").unlink(missing_ok=True)
    (primary_feature_dir / "status.events.jsonl").unlink(missing_ok=True)
    snapshot = '{"snapshot": "source-only"}\n'
    (coord_feature_dir / "status.json").write_text(snapshot, encoding="utf-8")

    _events_path, status_path = _project_status_bookkeeping_to_target(
        main_repo=repo,
        mission_slug=MISSION_SLUG,
        status_feature_dir=coord_feature_dir,
    )

    # The elif fallback copied the coord snapshot verbatim onto the target surface.
    assert status_path.read_text(encoding="utf-8") == snapshot
