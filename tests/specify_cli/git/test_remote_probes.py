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
from unittest.mock import MagicMock, patch

import pytest

from kernel.git.remote import RemoteUnreachable
from kernel.git.runner import GitCommandError, GitResult
from specify_cli.git.remote_probes import (
    RemoteLookup,
    remote_branch_lookup,
    _reset_remote_branch_lookup_cache,
)

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    _reset_remote_branch_lookup_cache()


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
#
# The ``git remote`` enumeration is mocked at the subprocess boundary; the
# ls-remote arm is the kernel owner (``kernel.git.remote.remote_heads``), so
# its outcomes are scripted at that seam (a mapping = answered, a raised
# ``RemoteUnreachable`` = could not ask).
# ---------------------------------------------------------------------------

_BRANCH = "kitty/mission-x"


def _unreachable(remote: str = "origin", *, timed_out: bool = False) -> RemoteUnreachable:
    cause = GitCommandError(argv=("ls-remote",), cwd=Path("."), returncode=-1 if timed_out else 128, stderr="", timed_out=timed_out)
    return RemoteUnreachable(remote, cause)


def _lookup(tmp_path: Path, remotes_out: str, heads: list[object], branch: str = _BRANCH) -> tuple[RemoteLookup, MagicMock, MagicMock]:
    """Run one lookup with ``git remote`` printing *remotes_out* and ``remote_heads`` scripted by *heads*."""
    with (
        patch("specify_cli.git.remote_probes.subprocess.run", return_value=_completed(0, stdout=remotes_out)) as mock_run,
        patch("specify_cli.git.remote_probes.remote_heads", side_effect=heads) as mock_heads,
    ):
        result = remote_branch_lookup(tmp_path, branch)
    return result, mock_run, mock_heads


def test_hit_when_single_remote_lists_branch(tmp_path: Path) -> None:
    result, _, _ = _lookup(tmp_path, "origin\n", [{_BRANCH: "abc123"}])
    assert result is RemoteLookup.HIT


def test_clean_miss_when_every_remote_reachable_and_empty(tmp_path: Path) -> None:
    result, _, mock_heads = _lookup(tmp_path, "origin\nupstream\n", [{}, {}])
    assert result is RemoteLookup.CLEAN_MISS
    assert mock_heads.call_count == 2


def test_hit_short_circuits_without_probing_every_remote(tmp_path: Path) -> None:
    """A HIT on the first remote must not require probing the second."""
    result, mock_run, mock_heads = _lookup(tmp_path, "origin\nupstream\n", [{_BRANCH: "abc123"}])
    assert result is RemoteLookup.HIT
    assert mock_run.call_count == 1  # `git remote` once
    assert mock_heads.call_count == 1  # ONE ls-remote, not two


def test_error_on_ls_remote_unreachable(tmp_path: Path) -> None:
    result, _, _ = _lookup(tmp_path, "origin\n", [_unreachable()])
    assert result is RemoteLookup.ERROR


def test_error_on_ls_remote_timeout(tmp_path: Path) -> None:
    result, _, _ = _lookup(tmp_path, "origin\n", [_unreachable(timed_out=True)])
    assert result is RemoteLookup.ERROR


def test_a_returned_empty_mapping_is_a_miss_never_an_error(tmp_path: Path) -> None:
    result, _, _ = _lookup(tmp_path, "origin\n", [{}])
    assert result is RemoteLookup.CLEAN_MISS


def test_error_from_one_remote_wins_over_clean_miss_from_another(tmp_path: Path) -> None:
    """FR-003: an ERROR from any remote must never be shadowed by a
    CLEAN_MISS from a different remote — never fabricate absence from a
    partial answer."""
    result, _, _ = _lookup(tmp_path, "origin\nupstream\n", [{}, _unreachable("upstream")])
    assert result is RemoteLookup.ERROR


# ---------------------------------------------------------------------------
# NFR-001 — per-process memoization keyed (repo_root, branch)
# ---------------------------------------------------------------------------


def test_memoized_per_process_by_repo_and_branch(tmp_path: Path) -> None:
    with (
        patch("specify_cli.git.remote_probes.subprocess.run", return_value=_completed(0, stdout="origin\n")) as mock_run,
        patch("specify_cli.git.remote_probes.remote_heads", return_value={_BRANCH: "abc123"}) as mock_heads,
    ):
        first = remote_branch_lookup(tmp_path, _BRANCH)
        second = remote_branch_lookup(tmp_path, _BRANCH)
    assert first is second is RemoteLookup.HIT
    assert mock_run.call_count + mock_heads.call_count == 2, "second call must be served from cache, no new subprocess calls"


def test_distinct_branch_is_not_served_from_the_other_branchs_cache_entry(tmp_path: Path) -> None:
    with (
        patch("specify_cli.git.remote_probes.subprocess.run", return_value=_completed(0, stdout="origin\n")) as mock_run,
        patch("specify_cli.git.remote_probes.remote_heads", side_effect=[{"kitty/mission-a": "abc"}, {}]) as mock_heads,
    ):
        a = remote_branch_lookup(tmp_path, "kitty/mission-a")
        b = remote_branch_lookup(tmp_path, "kitty/mission-b")
    assert a is RemoteLookup.HIT
    assert b is RemoteLookup.CLEAN_MISS
    assert mock_run.call_count + mock_heads.call_count == 4


def test_reset_cache_forces_a_fresh_lookup(tmp_path: Path) -> None:
    with (
        patch("specify_cli.git.remote_probes.subprocess.run", return_value=_completed(0, stdout="origin\n")) as mock_run,
        patch("specify_cli.git.remote_probes.remote_heads", return_value={_BRANCH: "abc"}) as mock_heads,
    ):
        remote_branch_lookup(tmp_path, _BRANCH)
        _reset_remote_branch_lookup_cache()
        remote_branch_lookup(tmp_path, _BRANCH)
    assert mock_run.call_count + mock_heads.call_count == 4


# ---------------------------------------------------------------------------
# NFR-002 — no hang, no credential prompt, bounded timeout
# ---------------------------------------------------------------------------


def test_ls_remote_disables_terminal_prompt_and_uses_ssh_batchmode(tmp_path: Path) -> None:
    """End to end through the kernel owner: the real ``remote_heads`` builds the no-prompt env."""
    with (
        patch("specify_cli.git.remote_probes.subprocess.run", return_value=_completed(0, stdout="origin\n")),
        patch("kernel.git.remote.run_git", return_value=GitResult(returncode=0, stdout=b"", stderr=b"")) as kernel_run,
    ):
        remote_branch_lookup(tmp_path, _BRANCH)

    env = kernel_run.call_args.kwargs["env"]
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert "BatchMode=yes" in env["GIT_SSH_COMMAND"]


def test_ls_remote_and_remote_enumeration_pass_a_bounded_timeout(tmp_path: Path) -> None:
    with (
        patch("specify_cli.git.remote_probes.subprocess.run", return_value=_completed(0, stdout="origin\n")) as mock_run,
        patch("kernel.git.remote.run_git", return_value=GitResult(returncode=0, stdout=b"", stderr=b"")) as kernel_run,
    ):
        remote_branch_lookup(tmp_path, _BRANCH)

    for call in [*mock_run.call_args_list, *kernel_run.call_args_list]:
        timeout = call.kwargs.get("timeout")
        assert timeout is not None and 0 < timeout <= 10


# ---------------------------------------------------------------------------
# Exact-ref matching — real git, no subprocess mocking (a suffix-collision
# false HIT can only be reproduced through git's own ls-remote pattern
# matching, not a mocked boundary).
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)


def _init_repo(repo: Path) -> None:
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "seed")


def _bare_origin(tmp_path: Path, name: str = "origin.git") -> Path:
    bare = tmp_path / name
    subprocess.run(["git", "init", "--bare", "-q", str(bare)], check=True)
    return bare


def _push(repo: Path, bare: Path, local_branch: str, remote_ref: str) -> None:
    _git(repo, "push", "-q", str(bare), f"{local_branch}:{remote_ref}")


def test_suffix_collision_branch_is_a_clean_miss_not_a_hit(tmp_path: Path) -> None:
    """A pattern of bare ``coord`` would suffix-match ``refs/heads/team/coord``
    under git's own ls-remote pattern matching. Only ``refs/heads/coord``
    exists here — ``refs/heads/team/coord`` must never be mistaken for it."""
    repo = tmp_path / "work"
    _init_repo(repo)
    bare = _bare_origin(tmp_path)
    _push(repo, bare, "main", "refs/heads/team/coord")
    _git(repo, "remote", "add", "origin", str(bare))

    result = remote_branch_lookup(repo, "coord")

    assert result is RemoteLookup.CLEAN_MISS


def test_exact_branch_match_is_a_hit(tmp_path: Path) -> None:
    repo = tmp_path / "work"
    _init_repo(repo)
    bare = _bare_origin(tmp_path)
    _push(repo, bare, "main", "refs/heads/coord")
    _git(repo, "remote", "add", "origin", str(bare))

    result = remote_branch_lookup(repo, "coord")

    assert result is RemoteLookup.HIT
