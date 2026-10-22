"""Fast unit tests for :mod:`kernel.git.blame` (#6309).

The parser fixtures are bytes captured from real git 2.43: a two-commit file
blamed over ``HEAD~1..HEAD`` (so the first commit is a ``boundary``), and the
zero-context diff between the two. Query tests mock :func:`kernel.git.blame.run_git`
to pin the argv; the real-git round trip is exercised by
``tests/consolidation/test_canceled_line_attribution_6309.py``.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from kernel.git import blame
from kernel.git.blame import BlameLine, DiffHunk, parse_blame_porcelain, parse_zero_context_diff
from kernel.git.runner import GitResult

pytestmark = pytest.mark.fast

_ONE = "e02c47790bb6e81deea74ded59dd80b7e200f85f"
_TWO = "1eba98d40a0502586e7bf35d4e6c73881a0967ed"
_BLAME = (
    f"{_ONE} 1 1 1\nauthor t\nauthor-mail <t@x>\nauthor-time 1767225600\nauthor-tz +0000\ncommitter t\n"
    "committer-mail <t@x>\ncommitter-time 1767225600\ncommitter-tz +0000\nsummary one\nboundary\nfilename f\n\tbase\n"
    f"{_TWO} 2 2 1\nauthor t\nauthor-mail <t@x>\nauthor-time 1767312000\nauthor-tz +0000\ncommitter t\n"
    f"committer-mail <t@x>\ncommitter-time 1767312000\ncommitter-tz +0000\nsummary two\nprevious {_ONE} f\nfilename f\n\tadded\n"
    f"{_ONE} 2 3 1\n\tkeep\n"
).encode()
_DIFF = b"diff --git a/f b/f\nindex c20e572..d4c2d83 100644\n--- a/f\n+++ b/f\n@@ -1,0 +2 @@ base\n+added\n"


def test_parse_blame_porcelain_remembers_boundary_per_commit() -> None:
    assert parse_blame_porcelain(_BLAME) == (
        BlameLine(_ONE, 1, 1, True, b"base"),
        BlameLine(_TWO, 2, 2, False, b"added"),
        BlameLine(_ONE, 2, 3, True, b"keep"),
    )


def test_parse_blame_porcelain_keeps_line_bytes_and_sha256_headers() -> None:
    sha256 = "ab" * 32
    raw = f"{sha256} 1 1 1\nfilename f\n\t\tindented\r\n".encode() + b"\n"
    assert parse_blame_porcelain(raw) == (BlameLine(sha256, 1, 1, False, b"\tindented\r"),)


def test_parse_blame_porcelain_of_an_empty_file_is_empty() -> None:
    assert parse_blame_porcelain(b"") == ()


@pytest.mark.parametrize("raw", [b"\torphan content\n", f"{_ONE} 1 1 1\nfilename f\n".encode()])
def test_parse_blame_porcelain_refuses_truncated_output(raw: bytes) -> None:
    with pytest.raises(ValueError, match="git blame --porcelain"):
        parse_blame_porcelain(raw)


def test_parse_zero_context_diff_reads_an_insertion() -> None:
    assert parse_zero_context_diff(_DIFF) == (DiffHunk(1, 0, 2, 1, (), (b"added",)),)


def test_parse_zero_context_diff_reads_replacements_and_deletions() -> None:
    raw = b"--- a/f\n+++ b/f\n@@ -3,2 +3 @@\n--- not a header\n-gone\n+new\n\\ No newline at end of file\n@@ -9 +8,0 @@\n-tail\n"
    assert parse_zero_context_diff(raw) == (
        DiffHunk(3, 2, 3, 1, (b"-- not a header", b"gone"), (b"new",)),
        DiffHunk(9, 1, 8, 0, (b"tail",), ()),
    )


def test_parse_zero_context_diff_of_no_change_is_empty() -> None:
    assert parse_zero_context_diff(b"") == ()


def test_blame_lines_pins_the_argv() -> None:
    with patch.object(blame, "run_git", return_value=GitResult(0, _BLAME, b"")) as run:
        lines = blame.blame_lines(Path("/repo"), "f", revs=["a..b"], reverse=True, first_parent=True, ignore_whitespace=True, detect_moves=True, timeout=5)
    assert len(lines) == 3
    args = run.call_args.args
    assert args[1:] == (
        "-c",
        "diff.algorithm=myers",
        "-c",
        "diff.relative=false",
        "blame",
        "--porcelain",
        "--no-textconv",
        "--ignore-revs-file",
        "",
        "--reverse",
        "--first-parent",
        "-w",
        "-M",
        "a..b",
        "--",
        "f",
    )
    assert run.call_args.kwargs == {"env": None, "timeout": 5}


def test_diff_hunks_pins_the_argv() -> None:
    with patch.object(blame, "run_git", return_value=GitResult(0, _DIFF, b"")) as run:
        assert blame.diff_hunks(Path("/repo"), "old", "new", "f", ignore_whitespace=True) == (DiffHunk(1, 0, 2, 1, (), (b"added",)),)
        blame.diff_hunks(Path("/repo"), "old", "new", "f")
    with_ws, without_ws = (call.args[1:] for call in run.call_args_list)
    assert with_ws[-4:] == ("old", "new", "--", "f") and "-w" in with_ws
    assert "-w" not in without_ws and "--no-ext-diff" in without_ws and "--no-renames" in without_ws
