"""CLI-shard coverage for `spec-kitty agent status validate` event filtering."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.status import app

pytestmark = pytest.mark.fast

runner = CliRunner()


def _extract_json(output: str) -> dict[str, object]:
    for line in output.strip().splitlines():
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return cast(dict[str, object], data)
    raise AssertionError(f"No JSON object found in output:\n{output}")


def test_validate_ignores_retrospective_events_in_shared_status_log(tmp_path: Path) -> None:
    mission_slug = "034-test-feature"
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)

    lane_event = {
        "actor": "claude-opus",
        "at": "2026-02-08T12:00:00Z",
        "event_id": "01HXYZ0123456789ABCDEFGHJK",
        "execution_mode": "worktree",
        "force": False,
        "from_lane": "planned",
        "mission_slug": mission_slug,
        "to_lane": "claimed",
        "wp_id": "WP01",
    }
    retrospective_event = {
        "actor": {"kind": "agent", "id": "agent", "profile_id": None},
        "at": "2026-02-08T12:01:00Z",
        "event_id": "01HXYZ0123456789ABCDEFGHJM",
        "event_name": "retrospective.proposal.applied",
        "mid8": "01HXYZ01",
        "mission_id": "01HXYZ0123456789ABCDEFGHJK",
        "mission_slug": mission_slug,
        "payload": {
            "applied_by": {"kind": "agent", "id": "agent", "profile_id": None},
            "kind": "synthesize_directive",
            "proposal_id": "01HXYZ0123456789ABCDEFGHJN",
            "provenance_ref": ".kittify/charter-packs/directive/.provenance/example.yaml",
            "target_urn": "doctrine:directive:example",
        },
    }
    (feature_dir / "status.events.jsonl").write_text(
        json.dumps(lane_event, sort_keys=True) + "\n"
        + json.dumps(retrospective_event, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    from specify_cli.status.reducer import materialize

    materialize(feature_dir)

    with (
        patch("specify_cli.cli.commands.agent.status.locate_project_root", return_value=tmp_path),
        patch("specify_cli.cli.commands.agent.status.get_main_repo_root", return_value=tmp_path),
    ):
        result = runner.invoke(app, ["validate", "--mission", mission_slug, "--json"])

    assert result.exit_code == 0
    data = _extract_json(result.output)
    assert data["passed"] is True
    assert data["error_count"] == 0
