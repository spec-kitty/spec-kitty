"""``agent status doctor/lifecycle/validate/materialize`` refuse a status surface cleanly (WP06, FR-004).

Mission lane-worktree-model-hardening; ADR ``2026-11-06-2-one-status-read-contract``.

* An unreadable coordination ref (the branch exists, its tip commit cannot be read) is never read
  as an empty history: each command exits 1 with a structured error, a ``{"error": ...}`` envelope
  under ``--json``, and never lets ``StatusSurfaceRefUnreadable`` escape as a traceback.
* A readable ref source (the coordination worktree is absent) has no file to inspect: the
  path-based checks refuse and name a remedy that gives the Mission a checkout.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import Result
from typer.testing import CliRunner

from tests.status.test_status_read_matrix import (
    COORD_BRANCH,
    LANES_WITH_COORD,
    SLUG,
    UNMATERIALIZED,
    build_matrix_mission,
    git,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

COMMANDS = ("doctor", "lifecycle", "validate", "materialize")
PATH_CHECKS = ("doctor", "lifecycle", "validate")


def _break_coordination_ref(repo: Path) -> None:
    """Delete the coordination branch tip's commit object: the branch exists, its commit cannot be read."""
    tip = git(repo, "rev-parse", f"refs/heads/{COORD_BRANCH}")
    loose_object = repo / ".git" / "objects" / tip[:2] / tip[2:]
    loose_object.chmod(0o644)
    loose_object.unlink()


def _invoke(command: str, *, json_output: bool) -> Result:
    from specify_cli.cli.commands.agent.status import app

    args = [command, "--mission", SLUG] + (["--json"] if json_output else [])
    return CliRunner().invoke(app, args)


def _first_json(output: str) -> dict[str, object]:
    for line in output.splitlines():
        if line.strip().startswith("{"):
            payload: dict[str, object] = json.loads(line)
            return payload
    raise AssertionError(f"no JSON envelope in output:\n{output}")


@pytest.mark.parametrize("json_output", [True, False], ids=["json", "human"])
@pytest.mark.parametrize("command", COMMANDS)
def test_unreadable_coordination_ref_is_a_structured_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str, json_output: bool) -> None:
    mission = build_matrix_mission(tmp_path, LANES_WITH_COORD, UNMATERIALIZED)
    _break_coordination_ref(mission.repo)
    monkeypatch.chdir(mission.repo)

    result = _invoke(command, json_output=json_output)

    assert isinstance(result.exception, SystemExit), repr(result.exception)
    assert result.exit_code == 1, result.output
    if json_output:
        payload = _first_json(result.output)
        assert payload["error_code"] == "status_surface_unavailable"
        assert COORD_BRANCH in str(payload["error"])
    else:
        assert "Error:" in result.output


@pytest.mark.parametrize("command", PATH_CHECKS)
def test_path_check_on_a_ref_source_names_a_remedy_that_leads_to_a_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str) -> None:
    """The refusal no longer sends the operator to ``agent status materialize`` (which refuses there too)."""
    mission = build_matrix_mission(tmp_path, LANES_WITH_COORD, UNMATERIALIZED)
    monkeypatch.chdir(mission.repo)

    result = _invoke(command, json_output=True)

    assert result.exit_code == 1, result.output
    payload = _first_json(result.output)
    assert payload["error_code"] == "status_surface_on_ref"
    assert f"spec-kitty materialize --mission {SLUG}" in str(payload["remedy"])
    assert "agent status materialize" not in str(payload["error"])
