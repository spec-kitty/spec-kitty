"""Fast unit tests for :mod:`kernel.git.runner` (subprocess mocked) plus the C-007 purity check."""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from kernel.git.runner import GitCommandError, GitResult, decode_path, run_git

pytestmark = pytest.mark.fast

_KERNEL_GIT = Path(__file__).resolve().parents[2] / "src" / "kernel" / "git"


def _completed(returncode: int, stdout: bytes = b"", stderr: bytes = b"") -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess(args=["git"], returncode=returncode, stdout=stdout, stderr=stderr)


def test_decode_path_is_lossless() -> None:
    raw = "a b/é".encode() + b"/\xff"
    text = decode_path(raw)
    assert text.startswith("a b/é/")
    assert text.encode("utf-8", "surrogateescape") == raw


def test_run_git_returns_bytes_and_passes_argv_env_timeout(tmp_path: Path) -> None:
    with patch("kernel.git.runner.subprocess.run", return_value=_completed(0, b"out\0")) as run:
        result = run_git(tmp_path, "status", "-z", env={"A": "1"}, timeout=5.0)
    assert result == GitResult(returncode=0, stdout=b"out\0", stderr=b"")
    args, kwargs = run.call_args
    assert args[0] == ["git", "status", "-z"]
    assert kwargs["cwd"] == str(tmp_path)
    assert kwargs["env"] == {"A": "1"}
    assert kwargs["timeout"] == 5.0
    assert kwargs["capture_output"] is True
    assert "text" not in kwargs


def test_run_git_inherits_environment_when_env_is_none(tmp_path: Path) -> None:
    with patch("kernel.git.runner.subprocess.run", return_value=_completed(0)) as run:
        run_git(tmp_path, "status")
    assert run.call_args.kwargs["env"] is None


def test_non_zero_exit_raises_with_subcommand_and_stderr(tmp_path: Path) -> None:
    failed = _completed(128, stderr=b"fatal: not a git repository\nmore")
    with patch("kernel.git.runner.subprocess.run", return_value=failed), pytest.raises(GitCommandError) as excinfo:
        run_git(tmp_path, "ls-tree", "HEAD")
    error = excinfo.value
    assert error.returncode == 128
    assert error.argv == ("ls-tree", "HEAD")
    assert "git ls-tree HEAD failed" in str(error)
    assert "fatal: not a git repository" in str(error)
    assert "more" not in str(error)


def test_undecodable_stderr_is_replaced_in_the_message(tmp_path: Path) -> None:
    with patch("kernel.git.runner.subprocess.run", return_value=_completed(1, stderr=b"bad \xff")), pytest.raises(GitCommandError) as excinfo:
        run_git(tmp_path, "status")
    assert "bad \ufffd" in str(excinfo.value)
    str(excinfo.value).encode("utf-8")


def test_check_false_returns_non_zero_result(tmp_path: Path) -> None:
    with patch("kernel.git.runner.subprocess.run", return_value=_completed(1, stderr=b"nope")):
        result = run_git(tmp_path, "ls-files", check=False)
    assert result.returncode == 1


@pytest.mark.parametrize(
    ("exc", "timed_out"),
    [(FileNotFoundError("git"), False), (subprocess.TimeoutExpired(["git"], 1.0), True)],
)
def test_unrunnable_git_raises(tmp_path: Path, exc: Exception, timed_out: bool) -> None:
    with patch("kernel.git.runner.subprocess.run", side_effect=exc), pytest.raises(GitCommandError) as excinfo:
        run_git(tmp_path, "status")
    assert excinfo.value.returncode == -1
    assert excinfo.value.timed_out is timed_out
    # ``not_run`` means git never started; a timeout started it, so it is not "not run".
    assert excinfo.value.not_run is (not timed_out)


def test_not_run_is_false_for_a_git_that_ran_and_failed(tmp_path: Path) -> None:
    with patch("kernel.git.runner.subprocess.run", return_value=_completed(2)), pytest.raises(GitCommandError) as excinfo:
        run_git(tmp_path, "status")
    assert excinfo.value.not_run is False


def test_empty_stderr_message(tmp_path: Path) -> None:
    with patch("kernel.git.runner.subprocess.run", return_value=_completed(2)), pytest.raises(GitCommandError, match="no error output"):
        run_git(tmp_path, "status")


_DESTRUCTIVE = {"reset", "--hard", "update-ref", "worktree", "stash", "clean", "rm", "checkout", "restore"}


def _destructive_literals(source: str, name: str) -> list[str]:
    """Every non-docstring string constant in *source* that is a destructive git argv word."""
    tree = ast.parse(source)
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) and node.body and isinstance(node.body[0], ast.Expr)
    }
    return [
        f"{name}:{node.lineno}: {node.value!r}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings and node.value in _DESTRUCTIVE
    ]


def test_kernel_git_contains_no_destructive_literal() -> None:
    """C-007: the owner runs listings only; destructive argv stays at guarded call sites."""
    found: list[str] = []
    for source in sorted(_KERNEL_GIT.glob("*.py")):
        found.extend(_destructive_literals(source.read_text(encoding="utf-8"), source.name))
    assert len(list(_KERNEL_GIT.glob("*.py"))) >= 4
    assert not found, found


@pytest.mark.parametrize(
    ("planted", "expected"),
    [
        ('def reset(cwd):\n    """Docstring mentioning reset --hard is fine."""\n    run_git(cwd, "reset", "--hard")\n', ["'reset'", "'--hard'"]),
        ('ARGS = ("stash", "push")\n', ["'stash'"]),
        ('def f():\n    """clean"""\n    return "clean"\n', ["'clean'"]),
    ],
)
def test_destructive_literal_scan_detects_a_planted_call(planted: str, expected: list[str]) -> None:
    """Positive control: the same AST walk flags a destructive argv planted in kernel source."""
    found = _destructive_literals(planted, "planted.py")
    assert [hit.split(": ", 1)[1] for hit in found] == expected
