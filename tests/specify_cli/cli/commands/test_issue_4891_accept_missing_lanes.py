"""CLI-level standing test pinning the behaviour of #4891.

``spec-kitty accept`` must fail closed -- never silently skip the entire
acceptance-matrix gate -- when a mission's ``lanes.json`` is absent. The
underlying fix already lives on ``main`` (``gates_core.py`` routes through
``require_lanes_json``); this is the CLI-level pin so a regression can never
again ship unnoticed: it drives the REAL ``spec-kitty accept`` CLI end to
end (not just the domain-level ``collect_feature_summary`` surface
``tests/specify_cli/acceptance/test_acceptance_support.py::test_accept_fails_closed_when_lanes_json_is_absent``
already covers).

This is a standing test, expected GREEN on ``main`` by design (the fix is
already merged); its job is to catch a future regression, not to prove one
exists today.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import typer
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.acceptance.matrix import write_acceptance_matrix
from specify_cli.cli.commands import accept as accept_module
from tests.lane_test_utils import derive_mission_id, write_single_lane_manifest
from tests.specify_cli.test_acceptance_regressions import (
    _create_test_feature,
    _passing_acceptance_matrix,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.integration]

_MISSION_SLUG = "wp04-4891-cli-pin-mission"

#: A dedicated, never-protected work branch used as BOTH the checked-out
#: branch and the mission's ``target_branch`` for the positive control --
#: mirrors ``test_issue_4974_accept_concurrent_verdict.py``'s ``_WORK_BRANCH``
#: convention, sidestepping ``ProtectionPolicy``'s default-protected ``main``
#: so the acceptance commit takes the simple direct-commit path.
_WORK_BRANCH = "wp04-4891-accept-work"


def _run_accept(repo_root: Path, mission_slug: str, monkeypatch: pytest.MonkeyPatch) -> Result:
    cli = typer.Typer()
    cli.command(name="accept")(accept_module.accept)
    monkeypatch.setattr(accept_module, "find_repo_root", lambda: repo_root)
    return CliRunner().invoke(
        cli,
        ["--mission", mission_slug, "--json"],
        catch_exceptions=False,
    )


def _meta(feature_dir: Path) -> dict[str, object]:
    payload: dict[str, object] = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    return payload


def test_accept_cli_fails_closed_when_lanes_json_is_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No ``lanes.json`` -> the real CLI exits non-zero, stamps nothing, and
    names the blocked ``lanes_manifest`` check in its JSON envelope."""
    repo_root, feature_dir = _create_test_feature(tmp_path, _MISSION_SLUG)
    monkeypatch.chdir(repo_root)

    assert not (feature_dir / "lanes.json").exists()

    result = _run_accept(repo_root, _MISSION_SLUG, monkeypatch)

    assert result.exit_code != 0, result.output
    assert "accepted_at" not in _meta(feature_dir)

    payload = json.loads(result.output)
    assert "accepted_at" not in payload
    blocked_checks = {item["check"] for item in payload.get("blocked_checks", [])}
    assert "lanes_manifest" in blocked_checks, f"the JSON envelope must name the blocked lanes_manifest check. Got: {payload.get('blocked_checks')}"
    assert payload.get("ok") is False


def test_accept_cli_positive_control_with_lanes_json_and_passing_matrix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Same fixture, but WITH ``lanes.json`` and a passing acceptance matrix:
    accept succeeds and stamps ``accepted_at`` -- proves the negative test
    above is exercising the ``lanes.json``-absence path specifically, not
    some other unrelated blocker in the shared fixture."""
    repo_root, feature_dir = _create_test_feature(tmp_path, _MISSION_SLUG)

    # Move onto a dedicated, never-protected work branch and repoint
    # target_branch at it (see ``_WORK_BRANCH`` docstring above).
    subprocess.run(
        ["git", "-C", str(repo_root), "branch", "-M", _WORK_BRANCH],
        check=True,
        capture_output=True,
    )
    meta_path = feature_dir / "meta.json"
    meta = _meta(feature_dir)
    mission_id = derive_mission_id(_MISSION_SLUG)
    meta["mission_id"] = mission_id
    meta["mid8"] = mission_id[:8]
    meta["target_branch"] = _WORK_BRANCH
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    write_single_lane_manifest(feature_dir, wp_ids=("WP01",), target_branch=_WORK_BRANCH)
    write_acceptance_matrix(feature_dir, _passing_acceptance_matrix(_MISSION_SLUG))

    subprocess.run(["git", "-C", str(repo_root), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo_root), "commit", "-m", "seed lanes.json + passing matrix"],
        check=True,
        capture_output=True,
    )
    monkeypatch.chdir(repo_root)

    assert (feature_dir / "lanes.json").exists()

    result = _run_accept(repo_root, _MISSION_SLUG, monkeypatch)

    assert result.exit_code == 0, result.output
    assert "accepted_at" in _meta(feature_dir), result.output
