"""Shared mission builders for ``spec-kitty implement`` tests.

Test modules must not import helpers from other test modules: when a test
module is retired its helpers vanish with it and every importer breaks (the
#1615 oracle in ``tests/specify_cli/regression/test_issue_1615_1616_1617_1618.py``
lost its builders exactly that way when ``tests/agent/test_implement_command.py``
was rewritten). The builders such tests share live here instead.
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.status.conftest import seed_wp_to_planned


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
    """Seed *wp_id* out of the non-display ``genesis`` state into ``planned``."""
    seed_wp_to_planned(mission_dir, wp_id, slug=mission_dir.name)
