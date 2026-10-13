"""#5879: the native ``next`` completion gate's git-topology contract.

The API-authoring marker lives in the git common dir, so a path with no git
repository cannot carry one (nothing to enforce), but a git that is present and
unusable must refuse rather than fail open.
"""

from __future__ import annotations

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
