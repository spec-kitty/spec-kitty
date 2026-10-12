"""#5879 CI remediation: the native ``next`` completion gate must not raise on a
path with no resolvable git repository (the API-authoring marker lives in the git
common dir, so a non-git path cannot carry one — nothing to enforce)."""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.cli.commands.next_cmd import _enforce_api_authoring_completion_gate

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_completion_gate_noop_outside_git_repository(tmp_path: Path) -> None:
    # tmp_path is a bare directory, not a git repository: the marker probe
    # (git_common_dir) raises NotAGitRepositoryError, which the gate must swallow
    # and skip rather than surface as a completion failure.
    _enforce_api_authoring_completion_gate("no-such-mission", tmp_path, True, owned=None)
