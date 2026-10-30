"""``spec-kitty agent release prep`` fails cleanly on an unreadable status log (#6612).

The changelog reader's loud failures (a corrupt ``status.events.jsonl``, a
deleted coordination branch) must surface as a clean one-line error and
exit 1 — like every other status reader — never a raw traceback.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

pytestmark = [pytest.mark.integration]


def test_agent_release_prep_corrupt_log_exits_clean(tmp_path: Path) -> None:
    """A corrupt status log fails prep with the mission named, exit 1."""
    from specify_cli import app

    repo = tmp_path / "repo"
    (repo / "kitty-specs" / "012-corrupt" / "tasks").mkdir(parents=True)
    (repo / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "4.0.0"\n', encoding="utf-8")
    mission_dir = repo / "kitty-specs" / "012-corrupt"
    (mission_dir / "meta.json").write_text("{}", encoding="utf-8")
    (mission_dir / "tasks" / "WP01.md").write_text(
        "---\nwork_package_id: WP01\nstatus: in_progress\n---\n\n## WP01\n",
        encoding="utf-8",
    )
    (mission_dir / "status.events.jsonl").write_text(
        json.dumps(
            {
                "event_id": "e1",
                "mission_slug": "012-corrupt",
                "wp_id": "WP01",
                "from_lane": "planned",
                "to_lane": "in_review",
                "at": "2026-05-01T09:00:00Z",
                "actor": "codex",
                "force": False,
                "execution_mode": "worktree",
                "evidence": None,
                "reason": None,
                "review_ref": None,
            }
        )
        + "\nnot json\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["agent", "release", "prep", "--channel", "alpha", "--repo", str(repo)])

    assert result.exit_code == 1
    output = (result.stdout or "") + (result.stderr or "")
    assert "012-corrupt" in output, output
    assert "line 2" in output, output
    assert "Traceback" not in output, output
