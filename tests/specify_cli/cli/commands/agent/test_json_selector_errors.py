"""Regression tests for JSON selector error contracts on agent commands."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer as typer_module
from typer.testing import CliRunner

from specify_cli.cli.commands.agent import status
from specify_cli.cli.commands.agent.tasks import app as tasks_app
from specify_cli.cli.commands.agent.status import app as status_app

pytestmark = pytest.mark.fast

runner = CliRunner()


@patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
def test_agent_tasks_status_missing_mission_returns_json_error(
    mock_locate_project_root: MagicMock,
    tmp_path: Path,
) -> None:
    """Missing selector errors must stay machine-readable under ``--json``."""

    mock_locate_project_root.return_value = tmp_path

    result = runner.invoke(tasks_app, ["status", "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert "error" in payload
    assert payload["ok"] is False
    assert "--mission <slug>" in payload["error"]["message"]


def test_agent_status_ambiguous_handle_maps_to_shared_json_envelope(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """#241: ``agent status``'s sibling ``_find_mission_slug`` short-circuit

    (same shape as tasks_shared.py's) must also map an ambiguous handle onto
    the shared ``{"success": False, "error_code": ...}`` envelope instead of
    an untyped ``{"error": ...}`` dict.
    """
    from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous

    exc = MissionSelectorAmbiguous(handle="charter", candidates=["020-charter", "030-charter"])
    seam_mock = MagicMock()
    seam_mock.read_dir.side_effect = exc
    with (
        patch(
            "specify_cli.cli.commands.agent.status.get_main_repo_root",
            return_value=tmp_path,
        ),
        patch(
            "specify_cli.cli.commands.agent.status.placement_seam",
            return_value=seam_mock,
        ),
        pytest.raises(typer_module.Exit) as exc_info,
    ):
        status._find_mission_slug("charter", json_output=True, repo_root=tmp_path)

    assert exc_info.value.exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "success": False,
        "error_code": "MISSION_AMBIGUOUS_SELECTOR",
        "error": str(exc),
        "handle": "charter",
        "candidates": ["020-charter", "030-charter"],
    }


def test_agent_status_validate_feature_option_rejected() -> None:
    """After alias removal ``--feature`` must be an unknown option (exit 2)."""

    result = runner.invoke(
        status_app,
        [
            "validate",
            "--mission",
            "077-alpha",
            "--feature",
            "077-beta",
            "--json",
        ],
    )

    # Typer exits 2 for unknown options; the --feature alias was removed in WP01.
    assert result.exit_code == 2
