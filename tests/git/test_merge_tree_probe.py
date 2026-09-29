"""The shared ``git merge-tree --write-tree`` availability probe (#5100 / #5115).

One implementation serves both ``consolidation.git_probes`` and
``lanes.lane_tip``; the version arithmetic is exercised against faked
``git --version`` output, and the two consumers are pinned to the SAME object.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.consolidation import git_probes
from specify_cli.git import merge_tree_probe
from specify_cli.lanes import lane_tip

pytestmark = [pytest.mark.unit]


def _fake_git_version(monkeypatch: pytest.MonkeyPatch, *, stdout: str, returncode: int = 0) -> None:
    def _run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr="")

    monkeypatch.setattr(merge_tree_probe.subprocess, "run", _run)


@pytest.mark.parametrize(
    ("stdout", "expected"),
    [
        ("git version 2.38.0\n", True),
        ("git version 2.43.0\n", True),
        ("git version 3.0.1\n", True),
        ("git version 2.37.9\n", False),
        ("git version 1.99.0\n", False),
        ("git version 2.38.0.windows.1\n", True),
        ("not a version at all\n", False),
        ("", False),
    ],
)
def test_availability_follows_the_parsed_version(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, stdout: str, expected: bool) -> None:
    _fake_git_version(monkeypatch, stdout=stdout)

    assert merge_tree_probe.merge_tree_write_tree_available(tmp_path) is expected


def test_a_failing_git_version_is_unavailable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _fake_git_version(monkeypatch, stdout="git version 2.43.0\n", returncode=1)

    assert merge_tree_probe.merge_tree_write_tree_available(tmp_path) is False


def test_consolidation_and_lanes_share_the_one_implementation() -> None:
    assert git_probes.merge_tree_write_tree_available is merge_tree_probe.merge_tree_write_tree_available
    assert lane_tip.merge_tree_write_tree_available is merge_tree_probe.merge_tree_write_tree_available
