"""#5879: the native ``next`` completion gate's git-topology contract.

The API-authoring marker lives in the git common dir, so a path with no git
repository cannot carry one (nothing to enforce), but a git that is present and
unusable must refuse rather than fail open.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from kernel.git_topology import GitTopologyUnavailableError

from specify_cli.cli.commands.next_cmd import _api_authoring_completion_gate

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_completion_gate_noop_outside_git_repository(tmp_path: Path) -> None:
    # tmp_path is a bare directory, not a git repository: the lock probe raises
    # NotAGitRepositoryError, which the gate must treat as "no marker" and skip.
    with _api_authoring_completion_gate("no-such-mission", tmp_path, True, result="success", owned=None):
        pass


def test_completion_gate_never_locks_an_unmarked_mission(tmp_path: Path) -> None:
    # A healthy git repo whose Mission has no API-authoring marker must not touch
    # the authoring lock, validate, or refuse: only API-authored Missions are bound.
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    with (
        patch("specify_cli.design.validation.authoring_lock", side_effect=AssertionError("lock must not be taken")),
        _api_authoring_completion_gate("unmarked-mission", tmp_path, True, result="success", owned=None),
    ):
        pass


def test_completion_gate_refuses_when_git_topology_unavailable(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # git missing, corrupt .git, dubious ownership: the old orchestrator path
    # failed closed here; the native gate must not fail open.
    with (
        patch("specify_cli.design.receipts.git_common_dir", side_effect=GitTopologyUnavailableError(tmp_path, "git unusable")),
        pytest.raises(typer.Exit) as caught,
        _api_authoring_completion_gate("any-mission", tmp_path, True, result="success", owned=None),
    ):
        pytest.fail("the gate body must not run")
    assert caught.value.exit_code == 1
    assert '"reason": "DESIGN_IO_FAILED"' in capsys.readouterr().out


def test_completion_gate_refuses_when_issued_state_unavailable(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Marker present, tasks not finalized, but the runtime cannot name the issued
    # step: the gate must refuse (not skip the proof) and never run the body.
    from runtime.next.runtime_bridge_query import MissionNotFoundError

    with (
        patch("specify_cli.design.validation.api_authoring_enabled", return_value=True),
        patch("specify_cli.design.validation.authoring_lock"),
        patch("specify_cli.design.validation._tasks_finalized", return_value=False),
        patch("runtime.next.runtime_bridge_query.issued_step_id_for_mission", side_effect=MissionNotFoundError("gone")),
        pytest.raises(typer.Exit) as caught,
        _api_authoring_completion_gate("any-mission", tmp_path, True, result="success", owned=None),
    ):
        pytest.fail("the gate body must not run")
    assert caught.value.exit_code == 1
    assert '"reason": "DESIGN_PREREQUISITES_FAILED"' in capsys.readouterr().out


def test_native_finalization_scope_skips_an_already_finalized_mission(tmp_path: Path) -> None:
    from specify_cli.design import validation

    with (
        patch.object(validation, "api_authoring_enabled", return_value=True),
        patch.object(validation, "authoring_lock"),
        patch.object(validation, "_tasks_finalized", return_value=True),
        patch.object(validation, "finalization_scope", side_effect=AssertionError("must not enter finalization_scope")),
        validation.native_finalization_scope(tmp_path, "m") as scope,
    ):
        assert scope is None


def test_marker_gated_lock_rereads_the_marker_inside_the_lock(tmp_path: Path) -> None:
    # Marker visible before the lock, withdrawn by the time the lock is held:
    # the double-check must report "not enabled" so nothing is proved or stamped.
    from specify_cli.design import validation

    with (
        patch.object(validation, "api_authoring_enabled", side_effect=[True, False]),
        patch.object(validation, "authoring_lock") as lock,
        validation._marker_gated_lock(tmp_path, "m") as enabled,
    ):
        assert enabled is False
    lock.assert_called_once()
