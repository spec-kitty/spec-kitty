"""#2879 regression: an unsafe ``--mission`` value must stay machine-readable.

The orchestrator-api surface is a **JSON-first machine contract** — external
orchestrators parse its stdout. The read-side seam's traversal guard
(``assert_safe_path_segment``, the FIRST step of
``resolve_handle_to_read_path``, before any ``kitty-specs/`` join) raises a
bare ``ValueError`` for an unsafe handle. Pre-fix, ``_resolve_mission_dir_or_fail``
caught only ``StatusReadPathNotFound``, so the ``ValueError`` escaped to the
top level and was rendered as a raw Python traceback — NOT valid JSON — on
every mission-scoped verb (mission-state, list-ready, resolve-workspace,
transition, ...). A programmatic consumer that does ``json.loads(stdout)``
then fails to parse and may mishandle the error.

Post-fix the ONE seam every mission-scoped endpoint routes through (see
``test_resolve_mission_dir_or_fail_invariant.py``) maps the guard's
``ValueError`` to the structured ``INVALID_MISSION`` envelope: non-zero exit,
parseable JSON, ``success: false`` — never a traceback.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.orchestrator_api import _common
from specify_cli.orchestrator_api.commands import app

pytestmark = [pytest.mark.fast]

runner = CliRunner()

# Unsafe --mission values, one per guard arm in assert_safe_path_segment
# (core/paths.py): literal "..", dotted-traversal prefix, path separator,
# leading dot. All must fail CLOSED — no traversal ever occurs; only the
# error SURFACE (traceback -> JSON envelope) changes.
_UNSAFE_MISSIONS = ["../traversal", "..", "a/b", ".hidden"]

# One CLI invocation per verb shape: a read (mission-state), a listing
# (list-ready), a read-companion (resolve-workspace), and a MUTATING verb
# (transition) — the invariant test proves every mission-scoped verb routes
# through the same seam, so these four stand in for the whole surface.
_VERB_ARGV = [
    ["mission-state", "--mission", "{mission}"],
    ["list-ready", "--mission", "{mission}"],
    ["resolve-workspace", "--mission", "{mission}", "--wp", "WP01"],
    # "blocked" needs no --policy (not a run-affecting lane), so the mission
    # resolve is the first failure point reached.
    ["transition", "--mission", "{mission}", "--wp", "WP01", "--to", "blocked", "--actor", "orch"],
]


def _seed_repo(tmp_path: Path) -> Path:
    """A repo root with an empty ``kitty-specs/`` (no mission needs to exist —
    the traversal guard fires BEFORE any existence probe)."""
    repo_root = tmp_path / "repo"
    (repo_root / "kitty-specs").mkdir(parents=True)
    return repo_root


@pytest.mark.parametrize("mission", _UNSAFE_MISSIONS)
@pytest.mark.parametrize("argv_template", _VERB_ARGV)
def test_unsafe_mission_returns_json_envelope_not_traceback(tmp_path: Path, mission: str, argv_template: list[str]) -> None:
    repo_root = _seed_repo(tmp_path)
    argv = [a.format(mission=mission) for a in argv_template]

    with patch.object(_common, "_get_main_repo_root", return_value=repo_root):
        result = runner.invoke(app, argv)

    # Non-zero exit, and — the contract — stdout is a single parseable JSON
    # object, never a traceback.
    assert result.exit_code != 0, result.output
    payload = json.loads(result.output)
    assert payload["success"] is False
    assert payload["error_code"] == "INVALID_MISSION"
    data = payload["data"]
    assert data["mission_slug"] == mission
    assert "not a safe path segment" in data["message"]
    # The guard's own diagnostic (which arm fired) is preserved for the
    # orchestrator under a distinct key — _fail() writes the canonical
    # message into data["message"] last-wins.
    assert data["reason"].startswith("Not a safe path segment")


def test_mission_state_envelope_shape_matches_contract(tmp_path: Path) -> None:
    """The #2879 expected envelope, field for field (contract_version +
    command naming included) — pins the exact machine-contract shape the
    issue reports as broken."""
    from specify_cli.core.contract_gate import is_allowed_error_code

    repo_root = _seed_repo(tmp_path)
    with patch.object(_common, "_get_main_repo_root", return_value=repo_root):
        result = runner.invoke(app, ["mission-state", "--mission", "../traversal"])

    payload = json.loads(result.output)
    assert payload["command"] == "orchestrator-api.mission-state"
    assert payload["success"] is False
    assert payload["error_code"] == "INVALID_MISSION"
    assert payload["data"]["message"] == "Mission slug is not a safe path segment: '../traversal'"
    # The new code is registered in the vendored contract allow-list (the
    # static TestAllowedErrorCodes guard requires this for literal _fail sites).
    assert is_allowed_error_code("orchestrator_api", "INVALID_MISSION")


def test_safe_mission_still_resolves_mission_not_found(tmp_path: Path) -> None:
    """A SAFE but absent handle keeps the historical MISSION_NOT_FOUND
    envelope — the new ValueError arm must not swallow the absence path."""
    repo_root = _seed_repo(tmp_path)
    with patch.object(_common, "_get_main_repo_root", return_value=repo_root):
        result = runner.invoke(app, ["mission-state", "--mission", "999-does-not-exist"])

    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["error_code"] == "MISSION_NOT_FOUND"
