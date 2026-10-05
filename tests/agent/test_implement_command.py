"""The ``--json`` error guard of ``implement`` when called directly, as ``agent action implement`` calls it.

The end-to-end claim behaviours live in ``tests/specify_cli/cli/commands/test_implement_phases.py``
and ``test_implement_characterization.py`` (WP10).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer

from specify_cli.cli.commands.implement import implement
from tests.specify_cli.cli.commands._implement_fixtures import MISSION_ID, SLUG, activate_repo, build_mission, init_repo

pytestmark = pytest.mark.git_repo


@pytest.fixture(autouse=True)
def _bypass_charter_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bypass the charter preflight gate for these implement-flow tests.

    None of these fixtures stage a charter; without the bypass the gate
    returns ``Error: charter_source missing`` before reaching the
    lane-workspace creation / JSON-output paths the tests exercise.
    Patch the hook boundary directly instead of relying on a production
    environment bypass.
    """
    from specify_cli.charter_runtime.preflight.result import CharterPreflightResult

    result = CharterPreflightResult(passed=True, checks=[])
    # Fixtures run implement on a protected ``main`` branch; the documented
    # operator escape hatch is the ONE sanctioned waiver (SPEC_KITTY_TEST_MODE
    # no longer waives the pre-check — PR #1850 guard-bypass fix).
    monkeypatch.setenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", "1")
    monkeypatch.setattr(
        "specify_cli.charter_runtime.preflight.hook.run_preflight_or_abort",
        lambda *_args, **_kwargs: result,
    )


class TestImplementCommand:
    """The --json error guard for a missing lanes.json, through a direct Python call.

    The characterization suite pins the same refusal through the Typer command
    (``test_missing_lanes_manifest_is_refused``) and the JSON error envelope through the CLI; this
    case keeps the direct-call surface: ``implement(..., json_output=True)`` prints exactly one JSON
    document and exits 1.
    """

    def test_implement_json_error_output_is_clean(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        repo = init_repo(tmp_path / "repo")
        activate_repo(repo, monkeypatch, tmp_path)
        build_mission(repo, SLUG, MISSION_ID, write_lanes=False)

        with pytest.raises(typer.Exit) as excinfo:
            implement("WP01", mission=SLUG, json_output=True, recover=False)

        assert excinfo.value.exit_code == 1

        payload = json.loads(capsys.readouterr().out.strip())
        assert payload["status"] == "error"
        assert payload["wp_id"] == "WP01"
        assert payload["error"] != "implement command failed"
        assert "lanes.json is required" in payload["error"]
