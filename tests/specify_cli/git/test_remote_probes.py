"""Unit coverage for the single canonical tri-state remote-branch primitive.

``remote_branch_lookup`` (``src/specify_cli/git/remote_probes.py``) is the ONE
shared probe #4979's C-001 mandates: both ``coordination.surface_resolver.
_coord_branch_exists`` and ``cli.commands.mission_type._branch_resolvable``
consume it (WP01 T003/T004) instead of each hand-rolling a ``git remote`` +
``git ls-remote`` loop.

The ``git remote`` / ``git ls-remote`` subprocess boundary is mocked here so
every outcome (HIT / CLEAN_MISS / ERROR / NO_REMOTE, plus the timeout/OSError
edges) is exercised deterministically and fast, without a real network or
even a real git repo; :mod:`tests.specify_cli.coordination.
test_coord_branch_remote_probe_4979` covers the real-git end-to-end vector
this primitive backs.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.git.remote_probes import (
    RemoteLookup,
    remote_branch_lookup,
    reset_remote_branch_lookup_cache,
)

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    reset_remote_branch_lookup_cache()


def _completed(returncode: int, stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


# ---------------------------------------------------------------------------
# NO_REMOTE
# ---------------------------------------------------------------------------


def test_no_remote_when_zero_remotes_configured(tmp_path: Path) -> None:
    with patch("specify_cli.git.remote_probes.subprocess.run") as mock_run:
        mock_run.return_value = _completed(0, stdout="")
        result = remote_branch_lookup(tmp_path, "kitty/mission-x")
    assert result is RemoteLookup.NO_REMOTE
    # Only the `git remote` enumeration call — no ls-remote fired with nothing
    # to iterate.
    mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# ERROR — git-remote enumeration failures
# ---------------------------------------------------------------------------


def test_error_when_git_remote_nonzero_exit(tmp_path: Path) -> None:
    with patch("specify_cli.git.remote_probes.subprocess.run") as mock_run:
        mock_run.return_value = _completed(128, stdout="")
        result = remote_branch_lookup(tmp_path, "kitty/mission-x")
    assert result is RemoteLookup.ERROR


def test_error_when_git_remote_oserror(tmp_path: Path) -> None:
    with patch("specify_cli.git.remote_probes.subprocess.run", side_effect=OSError("no git")):
        result = remote_branch_lookup(tmp_path, "kitty/mission-x")
    assert result is RemoteLookup.ERROR


def test_error_when_git_remote_times_out(tmp_path: Path) -> None:
    with patch(
        "specify_cli.git.remote_probes.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=["git", "remote"], timeout=5),
    ):
        result = remote_branch_lookup(tmp_path, "kitty/mission-x")
    assert result is RemoteLookup.ERROR


# ---------------------------------------------------------------------------
# HIT / CLEAN_MISS / ERROR across ls-remote outcomes
# ---------------------------------------------------------------------------


def test_hit_when_single_remote_lists_branch(tmp_path: Path) -> None:
    with patch("specify_cli.git.remote_probes.subprocess.run") as mock_run:
        mock_run.side_effect = [
            _completed(0, stdout="origin\n"),
            _completed(0, stdout="abc123\trefs/heads/kitty/mission-x\n"),
        ]
        result = remote_branch_lookup(tmp_path, "kitty/mission-x")
    assert result is RemoteLookup.HIT


def test_clean_miss_when_every_remote_reachable_and_empty(tmp_path: Path) -> None:
    with patch("specify_cli.git.remote_probes.subprocess.run") as mock_run:
        mock_run.side_effect = [
            _completed(0, stdout="origin\nupstream\n"),
            _completed(0, stdout=""),
            _completed(0, stdout=""),
        ]
        result = remote_branch_lookup(tmp_path, "kitty/mission-x")
    assert result is RemoteLookup.CLEAN_MISS


def test_hit_short_circuits_without_probing_every_remote(tmp_path: Path) -> None:
    """A HIT on the first remote must not require probing the second."""
    with patch("specify_cli.git.remote_probes.subprocess.run") as mock_run:
        mock_run.side_effect = [
            _completed(0, stdout="origin\nupstream\n"),
            _completed(0, stdout="abc123\trefs/heads/kitty/mission-x\n"),
        ]
        result = remote_branch_lookup(tmp_path, "kitty/mission-x")
    assert result is RemoteLookup.HIT
    assert mock_run.call_count == 2  # `git remote` + ONE ls-remote, not two


def test_error_on_ls_remote_nonzero_exit(tmp_path: Path) -> None:
    with patch("specify_cli.git.remote_probes.subprocess.run") as mock_run:
        mock_run.side_effect = [
            _completed(0, stdout="origin\n"),
            _completed(128, stdout=""),
        ]
        result = remote_branch_lookup(tmp_path, "kitty/mission-x")
    assert result is RemoteLookup.ERROR


def test_error_on_ls_remote_timeout(tmp_path: Path) -> None:
    with patch("specify_cli.git.remote_probes.subprocess.run") as mock_run:
        mock_run.side_effect = [
            _completed(0, stdout="origin\n"),
            subprocess.TimeoutExpired(cmd=["git", "ls-remote"], timeout=5),
        ]
        result = remote_branch_lookup(tmp_path, "kitty/mission-x")
    assert result is RemoteLookup.ERROR


def test_error_on_ls_remote_oserror(tmp_path: Path) -> None:
    with patch("specify_cli.git.remote_probes.subprocess.run") as mock_run:
        mock_run.side_effect = [_completed(0, stdout="origin\n"), OSError("boom")]
        result = remote_branch_lookup(tmp_path, "kitty/mission-x")
    assert result is RemoteLookup.ERROR


def test_error_from_one_remote_wins_over_clean_miss_from_another(tmp_path: Path) -> None:
    """FR-003: an ERROR from any remote must never be shadowed by a
    CLEAN_MISS from a different remote — never fabricate absence from a
    partial answer."""
    with patch("specify_cli.git.remote_probes.subprocess.run") as mock_run:
        mock_run.side_effect = [
            _completed(0, stdout="origin\nupstream\n"),
            _completed(0, stdout=""),  # origin: clean miss
            _completed(1, stdout=""),  # upstream: error
        ]
        result = remote_branch_lookup(tmp_path, "kitty/mission-x")
    assert result is RemoteLookup.ERROR


# ---------------------------------------------------------------------------
# NFR-001 — per-process memoization keyed (repo_root, branch)
# ---------------------------------------------------------------------------


def test_memoized_per_process_by_repo_and_branch(tmp_path: Path) -> None:
    with patch("specify_cli.git.remote_probes.subprocess.run") as mock_run:
        mock_run.side_effect = [
            _completed(0, stdout="origin\n"),
            _completed(0, stdout="abc123\trefs/heads/kitty/mission-x\n"),
        ]
        first = remote_branch_lookup(tmp_path, "kitty/mission-x")
        second = remote_branch_lookup(tmp_path, "kitty/mission-x")
    assert first is second is RemoteLookup.HIT
    assert mock_run.call_count == 2, "second call must be served from cache, no new subprocess calls"


def test_distinct_branch_is_not_served_from_the_other_branchs_cache_entry(tmp_path: Path) -> None:
    with patch("specify_cli.git.remote_probes.subprocess.run") as mock_run:
        mock_run.side_effect = [
            _completed(0, stdout="origin\n"),
            _completed(0, stdout="abc\trefs/heads/kitty/mission-a\n"),
            _completed(0, stdout="origin\n"),
            _completed(0, stdout=""),
        ]
        a = remote_branch_lookup(tmp_path, "kitty/mission-a")
        b = remote_branch_lookup(tmp_path, "kitty/mission-b")
    assert a is RemoteLookup.HIT
    assert b is RemoteLookup.CLEAN_MISS
    assert mock_run.call_count == 4


def test_reset_cache_forces_a_fresh_lookup(tmp_path: Path) -> None:
    with patch("specify_cli.git.remote_probes.subprocess.run") as mock_run:
        mock_run.side_effect = [
            _completed(0, stdout="origin\n"),
            _completed(0, stdout="abc\trefs/heads/kitty/mission-x\n"),
            _completed(0, stdout="origin\n"),
            _completed(0, stdout="abc\trefs/heads/kitty/mission-x\n"),
        ]
        remote_branch_lookup(tmp_path, "kitty/mission-x")
        reset_remote_branch_lookup_cache()
        remote_branch_lookup(tmp_path, "kitty/mission-x")
    assert mock_run.call_count == 4


# ---------------------------------------------------------------------------
# NFR-002 — no hang, no credential prompt, bounded timeout
# ---------------------------------------------------------------------------


def test_ls_remote_disables_terminal_prompt_and_uses_ssh_batchmode(tmp_path: Path) -> None:
    with patch("specify_cli.git.remote_probes.subprocess.run") as mock_run:
        mock_run.side_effect = [
            _completed(0, stdout="origin\n"),
            _completed(0, stdout=""),
        ]
        remote_branch_lookup(tmp_path, "kitty/mission-x")

    ls_remote_call = mock_run.call_args_list[1]
    env = ls_remote_call.kwargs["env"]
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert "BatchMode=yes" in env["GIT_SSH_COMMAND"]


def test_ls_remote_and_remote_enumeration_pass_a_bounded_timeout(tmp_path: Path) -> None:
    with patch("specify_cli.git.remote_probes.subprocess.run") as mock_run:
        mock_run.side_effect = [
            _completed(0, stdout="origin\n"),
            _completed(0, stdout=""),
        ]
        remote_branch_lookup(tmp_path, "kitty/mission-x")

    for call in mock_run.call_args_list:
        timeout = call.kwargs.get("timeout")
        assert timeout is not None and 0 < timeout <= 10
