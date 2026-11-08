"""#3763 — the orchestrator-api claim path fails structured on a self-heal failure.

``start-implementation`` enforces the post-materialize claim-ancestry gate
through ``wp_lifecycle._enforce_claim_ancestry``. Before #3763, a failure of
the gate's recheck self-heal escaped as a raw exception (no JSON envelope).
The gate now translates it to ``AncestryNotEstablishedError``; this seam
turns that into the same structured ``ANCESTRY_NOT_ESTABLISHED`` failure
envelope every other claim-time refusal here already provides.

Driven through the real ``orchestrator-api`` Typer app; only the gate's two
collaborators are replaced (see
``tests/specify_cli/cli/commands/agent/test_implement_ancestry_gate_envelope.py``
for the CLI seam's twin).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

import specify_cli.lanes.implement_support as implement_support
from specify_cli.lanes.implement_support import AncestryCheckResult
from specify_cli.orchestrator_api.commands import app
from tests.agent.test_orchestrator_commands_integration import _make_mission, _valid_policy_json

pytestmark = pytest.mark.git_repo

runner = CliRunner()

_SLUG = "099-test-mission"


def _fail_the_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the ancestry gate's recheck self-heal raise."""

    def _fail_heal(*args: object, **kwargs: object) -> None:
        raise RuntimeError("self-heal exploded")

    monkeypatch.setattr(
        implement_support,
        "check_claim_ancestry",
        lambda *args, **kwargs: AncestryCheckResult(ok=False, missing_refs=("bogus-ref",)),
    )
    monkeypatch.setattr(implement_support, "reenter_lane_self_heal", _fail_heal)


def test_start_implementation_fails_structured_when_self_heal_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root, _mission_dir = _make_mission(tmp_path, _SLUG)
    _fail_the_gate(monkeypatch)

    with patch("specify_cli.orchestrator_api._common._get_main_repo_root", return_value=repo_root):
        result = runner.invoke(
            app,
            [
                "start-implementation",
                "--mission",
                _SLUG,
                "--wp",
                "WP01",
                "--actor",
                "claude",
                "--policy",
                _valid_policy_json(),
            ],
        )

    assert result.exit_code != 0, result.output
    envelope: dict[str, Any] = json.loads(result.output)
    assert envelope["success"] is False
    assert envelope["error_code"] == "ANCESTRY_NOT_ESTABLISHED", envelope
    assert "self-heal exploded" in envelope["data"]["message"]


def test_transition_to_claimed_fails_structured_when_self_heal_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The raw ``transition --to claimed`` claim path shares the seam."""
    repo_root, _mission_dir = _make_mission(tmp_path, _SLUG)
    _fail_the_gate(monkeypatch)

    with patch("specify_cli.orchestrator_api._common._get_main_repo_root", return_value=repo_root):
        result = runner.invoke(
            app,
            [
                "transition",
                "--mission",
                _SLUG,
                "--wp",
                "WP01",
                "--to",
                "claimed",
                "--actor",
                "claude",
                "--policy",
                _valid_policy_json(),
            ],
        )

    assert result.exit_code != 0, result.output
    envelope: dict[str, Any] = json.loads(result.output)
    assert envelope["success"] is False
    assert envelope["error_code"] == "ANCESTRY_NOT_ESTABLISHED", envelope
