"""Regression test for the ``git branch -D`` option-injection hardening.

Alert #49 (SonarCloud S6350): ``_force_delete_branch_if_exists`` passed an
internally-derived branch name to ``git branch -D``. A value starting with
``-`` could be parsed as an option instead of the branch positional. The delete
now routes through ``guarded_branch_delete`` and the entry point refuses a
leading-dash name outright. This test pins that through a monkeypatched
``subprocess.run`` seam so a regression fails loudly.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from specify_cli.cli.commands import mission_type

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_force_delete_branch_never_passes_option_shaped_name_to_git(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An option-shaped name is refused before any ``git branch`` call (S6350).

    The delete itself now runs inside ``guarded_branch_delete``; the hardening that
    used to be a ``--`` separator is a leading-dash refusal at this entry point.
    """
    calls: list[list[str]] = []

    class _FakeResult:
        returncode = 0
        stdout = ""
        stderr = ""

    def _fake_run(argv: list[str], **_kwargs: Any) -> _FakeResult:
        calls.append(argv)
        return _FakeResult()

    monkeypatch.setattr(subprocess, "run", _fake_run)

    deleted = mission_type._force_delete_branch_if_exists(Path("/fake/repo"), "--upload-pack=touch /pwned-marker")

    assert deleted is False
    assert calls == [], "a hostile branch name must not reach git at all"


def test_force_delete_branch_noop_when_branch_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No delete call is issued when the existence pre-check fails (unchanged behavior)."""
    calls: list[list[str]] = []

    class _FakeResult:
        def __init__(self, returncode: int) -> None:
            self.returncode = returncode
            self.stdout = ""
            self.stderr = ""

    def _fake_run(argv: list[str], **_kwargs: Any) -> _FakeResult:
        calls.append(argv)
        return _FakeResult(returncode=1)  # branch does not exist

    monkeypatch.setattr(subprocess, "run", _fake_run)

    mission_type._force_delete_branch_if_exists(Path("/fake/repo"), "some-branch")

    assert all(argv[:2] != ["git", "branch"] for argv in calls)
