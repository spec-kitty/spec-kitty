"""The window predicates bound to one lane tip (pre-PR fold M2, FR-022, contract R-4).

``bind_lane_predicates`` gives the window opener reader its two git questions. A recorded SHA
that is not in this clone is a ``not on lane`` gap (R-4); a git failure on a SHA that IS in
the clone is a probe error the approved bound refuses on, never a silent gap that would let
the work package be judged by its weaker degraded window.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

import specify_cli.consolidation.git_probes as git_probes
from specify_cli.consolidation.git_probes import GitProbeError
from specify_cli.consolidation.write_branch_bound import bind_lane_predicates

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_NOT_IN_CLONE = "f" * 40


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    _git(tmp_path, "commit", "-q", "--allow-empty", "-m", "first")
    _git(tmp_path, "commit", "-q", "--allow-empty", "-m", "second")
    return tmp_path


def _fail_merge_base(monkeypatch: pytest.MonkeyPatch, code: int) -> None:
    real = git_probes.run_command

    def _fake(cmd: Any, **kwargs: Any) -> tuple[int, str, str]:
        if list(cmd[:3]) == ["git", "merge-base", "--is-ancestor"]:
            return code, "", "fatal: unable to read object"
        return real(cmd, **kwargs)

    monkeypatch.setattr(git_probes, "run_command", _fake)


def test_sha_not_in_clone_is_off_the_lane_and_never_an_ancestor(repo: Path) -> None:
    on_lane, is_ancestor = bind_lane_predicates(repo, _git(repo, "rev-parse", "HEAD"))
    head, first = _git(repo, "rev-parse", "HEAD"), _git(repo, "rev-parse", "HEAD~1")

    assert on_lane(first) and on_lane(head)
    assert not on_lane(_NOT_IN_CLONE)
    assert is_ancestor(first, head) and not is_ancestor(head, first)
    assert not is_ancestor(_NOT_IN_CLONE, head) and not is_ancestor(head, _NOT_IN_CLONE)


def test_git_failure_on_an_in_clone_sha_raises_instead_of_reading_as_off_the_lane(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    head, first = _git(repo, "rev-parse", "HEAD"), _git(repo, "rev-parse", "HEAD~1")
    on_lane, is_ancestor = bind_lane_predicates(repo, head)
    _fail_merge_base(monkeypatch, 128)

    with pytest.raises(GitProbeError):
        on_lane(first)
    with pytest.raises(GitProbeError):
        is_ancestor(first, head)
