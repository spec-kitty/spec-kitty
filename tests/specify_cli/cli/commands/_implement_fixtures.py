"""Shared mission builders for ``spec-kitty implement`` tests: the single import point.

Test modules must not import helpers from other test modules: when a test
module is retired its helpers vanish with it and every importer breaks (the
#1615 oracle in ``tests/specify_cli/regression/test_issue_1615_1616_1617_1618.py``
lost its builders exactly that way when ``tests/agent/test_implement_command.py``
was rewritten). The builders such tests share are imported from here instead.

The repository and mission builders are still *defined* in
``test_implement_characterization.py``, which is frozen (SC-003) and may not
change. They are re-exported here so no other test module imports that test
module directly. When the freeze lifts, invert the arrangement: move the
definitions into this module and have the characterization suite import them.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.specify_cli.cli.commands.test_implement_characterization import (
    ARGS,
    LANE_BRANCH,
    LANE_WORKTREE,
    LATE,
    MISSION_ID,
    SLUG,
    Mission,
    activate_repo,
    build_mission,
    flat,
    git,
    implement_cli,
    init_repo,
    snapshot,
    underlying,
)
from tests.utils import _seed_canonical_wp_state

__all__ = [
    "ARGS",
    "COORDINATION_BRANCH",
    "LANE_BRANCH",
    "LANE_WORKTREE",
    "LATE",
    "MISSION_ID",
    "SLUG",
    "Mission",
    "activate_repo",
    "activated_repo",
    "build_mission",
    "create_meta_json",
    "flat",
    "git",
    "implement_cli",
    "init_repo",
    "seed_planned",
    "snapshot",
    "underlying",
]

#: The coordination branch name of the shared ``SLUG`` / ``MISSION_ID`` mission.
COORDINATION_BRANCH = f"kitty/mission-{SLUG}-{MISSION_ID[:8].lower()}"


def activated_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A seeded repository at ``tmp_path / "repo"`` that the ``implement`` command is pointed at."""
    root = init_repo(tmp_path / "repo")
    activate_repo(root, monkeypatch, tmp_path)
    return root


def create_meta_json(mission_dir: Path, vcs: str = "git") -> Path:
    """Write a minimal software-dev ``meta.json`` for *mission_dir* and return its path."""
    meta_path = mission_dir / "meta.json"
    mission_dir.mkdir(parents=True, exist_ok=True)
    meta_content = {
        "feature_number": mission_dir.name.split("-")[0],
        "mission_slug": mission_dir.name,
        "created_at": "2026-01-17T00:00:00Z",
        "friendly_name": mission_dir.name,
        "mission_type": "software-dev",
        "slug": mission_dir.name,
        "target_branch": "main",
    }
    if vcs:
        meta_content["vcs"] = vcs
    meta_path.write_text(json.dumps(meta_content, indent=2))
    return meta_path


def seed_planned(mission_dir: Path, wp_id: str) -> None:
    """Seed *wp_id* out of the non-display ``genesis`` state into ``planned``.

    *mission_dir* is ``<checkout>/kitty-specs/<slug>``; the checkout may be the repository root or a
    coordination worktree.
    """
    _seed_canonical_wp_state(
        mission_dir.parent.parent,
        mission_dir.name,
        wp_id,
        "planned",
        actor="system",
        assignee="Owner",
        shell_pid="1234",
        timestamp="2026-01-17T00:00:00Z",
    )
