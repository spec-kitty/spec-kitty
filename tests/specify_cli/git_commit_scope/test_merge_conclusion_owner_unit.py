"""Argument refusal of the merge-conclusion owner, decided before any git call (#5443, FR-013)."""

from __future__ import annotations

import dataclasses
import subprocess
from pathlib import Path
from typing import NoReturn

import pytest

from specify_cli.git import merge_conclusion
from specify_cli.git.merge_conclusion import (
    COMMITTING_OPS,
    FreshWorktree,
    MergeConclusionRefused,
    conclude_in_progress_op,
    run_committing_op,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

WT = Path("/nonexistent/worktree")


@pytest.fixture(autouse=True)
def _no_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError(f"subprocess.run was called: {args!r}")

    monkeypatch.setattr(subprocess, "run", _fail)


@pytest.mark.parametrize(
    "bad",
    ["--no-verify", "--no-commit", "-n", "--squash", "--continue", "core.hooksPath=/dev/null", "core.hookspath=hooks"],
)
@pytest.mark.parametrize("op", sorted(COMMITTING_OPS))
def test_refused_argument_never_reaches_git(op: str, bad: str) -> None:
    with pytest.raises(MergeConclusionRefused) as excinfo:
        run_committing_op(WT, op, ["--no-edit", bad, "side"], env=None, disable_gpgsign=False)
    assert str(WT) in str(excinfo.value)
    assert bad in str(excinfo.value)


@pytest.mark.parametrize("op", ["cherry-pick", "commit", "rebase", ""])
def test_unknown_op_is_refused(op: str) -> None:
    with pytest.raises(MergeConclusionRefused, match="unsupported operation"):
        run_committing_op(WT, op, ["side"], env=None, disable_gpgsign=False)


@pytest.mark.parametrize("args", [[], (), "side"])
def test_empty_or_string_args_are_refused(args: list[str] | tuple[str, ...] | str) -> None:
    with pytest.raises(MergeConclusionRefused, match="non-empty argument list"):
        run_committing_op(WT, "merge", args, env=None, disable_gpgsign=False)


@pytest.mark.parametrize("message", ["", "   ", "\n"])
def test_empty_explicit_message_is_refused(message: str) -> None:
    with pytest.raises(MergeConclusionRefused, match="must not be empty"):
        conclude_in_progress_op(WT, env=None, message=message)


def test_gpg_prefix_is_plumbed_from_the_flag() -> None:
    assert merge_conclusion._gpg_prefix(True) == ["-c", "commit.gpgsign=false"]
    assert merge_conclusion._gpg_prefix(False) == []


def test_fresh_worktree_is_frozen() -> None:
    proof = FreshWorktree(worktree=WT, head="abc", _minted=merge_conclusion._MINTED)
    with pytest.raises(dataclasses.FrozenInstanceError):
        proof.head = "def"  # type: ignore[misc]


def test_fresh_worktree_cannot_be_forged() -> None:
    with pytest.raises(TypeError, match="minted only by"):
        FreshWorktree(worktree=WT, head="abc")


def test_refusal_names_the_worktree_and_reason() -> None:
    exc = MergeConclusionRefused(WT, "the reason")
    assert exc.worktree == WT
    assert exc.reason == "the reason"
    assert str(exc) == f"merge conclusion refused in {WT}: the reason"
    assert isinstance(exc, RuntimeError), "callers already treat RuntimeError as merge failure"
