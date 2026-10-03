"""Fast unit tests for :mod:`kernel.git.listing`.

The parser fixtures below are bytes captured from real git 2.43 (``core.quotePath
= true``) on a repository holding ``a b/f``, ``é/g``, a file literally named
``p -> q`` renamed to ``r s``, an untracked file named ``?? odd``, a new
directory, an ignored ``.venv/`` and an ignored ``src/store/local.txt``. They
are not hand-written: rename record order differs between ``status`` (new
first) and ``diff --name-status`` (old first), and only real output pins that.
Query tests mock :func:`kernel.git.listing.run_git` to pin the argv; the
real-git round trip lives in ``tests/git/test_kernel_git_real.py``.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from kernel.git import listing
from kernel.git.listing import (
    IndexEntry,
    NameStatusEntry,
    NumstatEntry,
    StatusEntry,
    TreeEntry,
    parse_index_z,
    parse_name_status_z,
    parse_numstat_z,
    parse_paths_z,
    parse_status_z,
    parse_tree_z,
)
from kernel.git.paths import GitPath
from kernel.git.runner import GitCommandError, GitResult

pytestmark = pytest.mark.fast

P = GitPath.parse

STATUS_IGNORED = b" M a b/f\x00R  r s\x00p -> q\x00?? ?? odd\x00?? newdir/\x00!! .venv/\x00!! src/store/local.txt\x00"
STATUS_ALL = b" M a b/f\x00R  r s\x00p -> q\x00?? ?? odd\x00?? newdir/n\x00"
LS_TREE = b".gitignore\x00a b/f\x00p -> q\x00src/store/default.txt\x00\xc3\xa9/g\x00"
NAME_STATUS_RENAMES = b"R100\x00p -> q\x00r s\x00"
NAME_STATUS_NO_RENAMES = b"D\x00p -> q\x00A\x00r s\x00"
STAGE = (
    b"100644 23e023c63f96eaf89ce256bca8eeac4c6b323161 0\t.gitignore\x00"
    b"100644 587be6b4c3f93f93c489c0111bba5596147a26cb 0\ta b/f\x00"
    b"100644 975fbec8256d3e8a3797e7a3611380f27c49f4ac 0\t\xc3\xa9/g\x00"
)


def test_parse_status_with_renames_ignored_and_collapsed_directories() -> None:
    entries = parse_status_z(STATUS_IGNORED)
    assert entries == (
        StatusEntry(xy=" M", path=P("a b/f")),
        StatusEntry(xy="R ", path=P("r s"), orig_path=P("p -> q")),
        StatusEntry(xy="??", path=P("?? odd")),
        StatusEntry(xy="??", path=P("newdir"), is_directory=True),
        StatusEntry(xy="!!", path=P(".venv"), is_directory=True),
        StatusEntry(xy="!!", path=P("src/store/local.txt")),
    )
    rename = entries[1]
    assert (rename.index, rename.worktree) == ("R", " ")
    assert entries[2].is_untracked and not entries[2].is_ignored
    assert entries[4].is_ignored


def test_parse_status_untracked_all_lists_files() -> None:
    assert parse_status_z(STATUS_ALL)[-1] == StatusEntry(xy="??", path=P("newdir/n"))


def test_truncated_rename_record_is_a_value_error() -> None:
    with pytest.raises(ValueError, match="second path record"):
        parse_status_z(b"R  r s\x00")
    with pytest.raises(ValueError, match="second path record"):
        parse_name_status_z(b"R100\x00p -> q\x00")


def test_parse_status_empty() -> None:
    assert parse_status_z(b"") == ()


def test_parse_status_non_utf8_is_lossless() -> None:
    (entry,) = parse_status_z(b"?? bad\xff\x00")
    assert str(entry.path).encode("utf-8", "surrogateescape") == b"bad\xff"


@pytest.mark.parametrize("xy", ["UU", "AA", "DD", "AU", "UA", "DU", "UD"])
def test_conflict_codes(xy: str) -> None:
    assert StatusEntry(xy=xy, path=P("f")).is_conflicted
    assert not StatusEntry(xy="M ", path=P("f")).is_conflicted


def test_display_is_for_humans() -> None:
    assert StatusEntry(xy="!!", path=P(".venv"), is_directory=True).display() == "!! .venv/"
    assert StatusEntry(xy="R ", path=P("r s"), orig_path=P("p -> q")).display() == "R  p -> q -> r s"
    assert StatusEntry(xy="??", path=P("src/local data/notes.txt")).display() == "?? src/local data/notes.txt"


def test_display_keeps_ordinary_non_ascii() -> None:
    assert StatusEntry(xy="??", path=P("src/café.txt")).display() == "?? src/café.txt"


def test_display_escapes_undecodable_bytes() -> None:
    [entry] = parse_status_z(b"?? src/bad\xff.txt\0")
    # Would pass wrongly if the surrogate escape leaked into the message as a lone surrogate.
    assert entry.display() == "?? src/bad\\xff.txt"
    entry.display().encode("utf-8")


def test_display_escapes_control_characters() -> None:
    entry = StatusEntry(xy="??", path=P("a\nb\x1b[31m"), orig_path=P("o\tp"))
    # Would pass wrongly if a raw newline or ESC reached the terminal.
    assert entry.display() == "?? o\\tp -> a\\nb\\x1b[31m"


def test_parse_paths_keeps_spaces_non_ascii_and_arrows() -> None:
    assert parse_paths_z(LS_TREE) == (P(".gitignore"), P("a b/f"), P("p -> q"), P("src/store/default.txt"), P("é/g"))


def test_parse_name_status_rename_order_is_old_then_new() -> None:
    assert parse_name_status_z(NAME_STATUS_RENAMES) == (NameStatusEntry(status="R100", path=P("r s"), orig_path=P("p -> q")),)
    assert parse_name_status_z(NAME_STATUS_NO_RENAMES) == (
        NameStatusEntry(status="D", path=P("p -> q")),
        NameStatusEntry(status="A", path=P("r s")),
    )


def test_parse_index() -> None:
    entries = parse_index_z(STAGE)
    assert entries[1] == IndexEntry(mode="100644", oid="587be6b4c3f93f93c489c0111bba5596147a26cb", stage=0, path=P("a b/f"))
    assert entries[2].path == P("é/g")


def test_parse_index_with_tags() -> None:
    raw = b"S 100644 587be6b4c3f93f93c489c0111bba5596147a26cb 0\ta b/f\x00"
    (entry,) = parse_index_z(raw, tags=True)
    assert (entry.tag, entry.mode, entry.path) == ("S", "100644", P("a b/f"))
    assert parse_index_z(STAGE)[0].tag is None


def test_parse_numstat_counts_and_binary() -> None:
    assert parse_numstat_z(b"3\t1\ta b/f\x00-\t-\tlogo.png\x00") == (
        NumstatEntry(added=3, deleted=1, path=P("a b/f")),
        NumstatEntry(added=None, deleted=None, path=P("logo.png")),
    )


def test_parse_tree_entries() -> None:
    raw = b"040000 tree 1f2e3d4c5b6a79881f2e3d4c5b6a79881f2e3d4c\ta b\x00"
    assert parse_tree_z(raw) == (TreeEntry(mode="040000", type="tree", oid="1f2e3d4c5b6a79881f2e3d4c5b6a79881f2e3d4c", path=P("a b")),)


# ---------------------------------------------------------------------------
# Query argv (run_git mocked)
# ---------------------------------------------------------------------------


def _stub(stdout: bytes = b""):
    return patch.object(listing, "run_git", return_value=GitResult(returncode=0, stdout=stdout, stderr=b""))


def _argv(run) -> tuple[str, ...]:
    return run.call_args.args[1:]


def test_status_entries_argv_and_env(tmp_path: Path) -> None:
    with _stub(STATUS_IGNORED) as run:
        entries = listing.status_entries(tmp_path, ignored=True, env={"E": "1"})
    assert _argv(run) == ("status", "--porcelain=v1", "-z", "--untracked-files=normal", "--ignored", "--")
    assert run.call_args.kwargs["env"] == {"E": "1"}
    assert len(entries) == 6


def test_status_entries_literal_pathspecs_and_no_optional_locks(tmp_path: Path) -> None:
    with _stub() as run:
        listing.status_entries(tmp_path, pathspecs=("a b", "*"), untracked="all", optional_locks=False)
    assert _argv(run) == (
        "--literal-pathspecs",
        "--no-optional-locks",
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--",
        "a b",
        "*",
    )


def test_status_entries_glob_pathspecs(tmp_path: Path) -> None:
    with _stub() as run:
        listing.status_entries(tmp_path, pathspecs=("*.py",), glob=True)
    assert _argv(run)[0] == "status"
    assert _argv(run)[-2:] == ("--", "*.py")


def test_status_entries_rejects_unknown_untracked_mode(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="untracked"):
        listing.status_entries(tmp_path, untracked="yes")


def test_tree_paths(tmp_path: Path) -> None:
    with _stub(LS_TREE) as run:
        paths = listing.tree_paths(tmp_path, "HEAD", pathspecs=("src",))
    assert _argv(run) == ("--literal-pathspecs", "ls-tree", "--full-tree", "-r", "--name-only", "-z", "HEAD", "--", "src")
    assert P("a b/f") in paths and isinstance(paths, frozenset)


def test_changed_paths(tmp_path: Path) -> None:
    with _stub(b"a b/f\x00") as run:
        assert listing.changed_paths(tmp_path, "A", "B", cached=True, diff_filter="U") == (P("a b/f"),)
    assert _argv(run) == ("-c", "diff.relative=false", "diff", "--name-only", "-z", "--no-renames", "--cached", "--diff-filter=U", "A", "B", "--")


def test_changed_entries_with_renames(tmp_path: Path) -> None:
    with _stub(NAME_STATUS_RENAMES) as run:
        (entry,) = listing.changed_entries(tmp_path, "HEAD", renames=True)
    assert _argv(run) == ("-c", "diff.relative=false", "diff", "--name-status", "-z", "-M", "HEAD", "--")
    assert entry.orig_path == P("p -> q")


def test_commit_paths(tmp_path: Path) -> None:
    with _stub(b"x\x00") as run:
        assert listing.commit_paths(tmp_path, "abc") == (P("x"),)
    assert _argv(run) == ("-c", "diff.relative=false", "show", "--name-only", "--format=", "-z", "--no-renames", "abc", "--")


def test_log_paths_dedups_in_first_seen_order(tmp_path: Path) -> None:
    with _stub(b"b\x00a\x00\x00b\x00") as run:
        assert listing.log_paths(tmp_path, "main..HEAD") == (P("b"), P("a"))
    assert _argv(run) == ("-c", "diff.relative=false", "log", "-z", "--name-only", "--format=", "--no-renames", "main..HEAD", "--")


def test_tracked_paths_and_index_entries(tmp_path: Path) -> None:
    with _stub(b"a b/f\x00") as run:
        assert listing.tracked_paths(tmp_path, pathspecs=("a b",)) == (P("a b/f"),)
    assert _argv(run) == ("--literal-pathspecs", "ls-files", "--full-name", "-z", "--", "a b")
    with _stub(STAGE) as run:
        assert len(listing.index_entries(tmp_path)) == 3
    assert _argv(run) == ("ls-files", "--full-name", "--stage", "-z", "--")


@pytest.mark.parametrize(("returncode", "expected"), [(0, True), (1, False)])
def test_is_tracked(tmp_path: Path, returncode: int, expected: bool) -> None:
    with patch.object(listing, "run_git", return_value=GitResult(returncode=returncode, stdout=b"", stderr=b"")) as run:
        assert listing.is_tracked(tmp_path, "a b") is expected
    assert _argv(run) == ("--literal-pathspecs", "ls-files", "--error-unmatch", "--", "a b")
    assert run.call_args.kwargs["check"] is False


def test_is_tracked_raises_on_real_failure(tmp_path: Path) -> None:
    failed = GitResult(returncode=128, stdout=b"", stderr=b"fatal: bad")
    with patch.object(listing, "run_git", return_value=failed), pytest.raises(GitCommandError, match="fatal: bad"):
        listing.is_tracked(tmp_path, "x")


def test_query_failure_propagates(tmp_path: Path) -> None:
    error = GitCommandError(argv=("status",), cwd=tmp_path, returncode=128, stderr="fatal")
    with patch.object(listing, "run_git", side_effect=error), pytest.raises(GitCommandError):
        listing.status_entries(tmp_path)


def test_status_entries_untracked_none_omits_flag(tmp_path: Path) -> None:
    with _stub() as run:
        listing.status_entries(tmp_path, untracked=None)
    assert _argv(run) == ("status", "--porcelain=v1", "-z", "--")


def test_timeout_is_passed_through(tmp_path: Path) -> None:
    with _stub() as run:
        listing.tracked_paths(tmp_path, timeout=2.5)
    assert run.call_args.kwargs["timeout"] == 2.5


def test_changed_paths_with_renames(tmp_path: Path) -> None:
    with _stub() as run:
        listing.changed_paths(tmp_path, "HEAD", renames=True)
    assert _argv(run) == ("-c", "diff.relative=false", "diff", "--name-only", "-z", "-M", "HEAD", "--")


def test_numstat_entries_argv(tmp_path: Path) -> None:
    with _stub(b"1\t0\tx\x00") as run:
        (entry,) = listing.numstat_entries(tmp_path, cached=True)
    assert _argv(run) == ("-c", "diff.relative=false", "diff", "--numstat", "-z", "--no-renames", "--cached", "--")
    assert entry.added == 1


def test_tree_entry_matches_exact_path_only(tmp_path: Path) -> None:
    raw = b"100644 blob 587be6b4c3f93f93c489c0111bba5596147a26cb\tsrc/a\x00"
    with _stub(raw) as run:
        assert listing.tree_entry(tmp_path, "HEAD", "src/a") == TreeEntry(
            mode="100644", type="blob", oid="587be6b4c3f93f93c489c0111bba5596147a26cb", path=P("src/a")
        )
    assert _argv(run) == ("--literal-pathspecs", "ls-tree", "--full-tree", "-z", "HEAD", "--", "src/a")
    with _stub(b"") as run:
        assert listing.tree_entry(tmp_path, "HEAD", "missing") is None
    with _stub(b"") as run:
        listing.tree_entry(tmp_path, "HEAD", "dir/")
    assert _argv(run)[-1] == "dir"


def test_tree_entries_batches_literal_pathspecs(tmp_path: Path) -> None:
    raw = b"100644 blob 587be6b4c3f93f93c489c0111bba5596147a26cb\tsrc/a\x00100755 blob 0000000000000000000000000000000000000001\tsrc/b\x00"
    with _stub(raw) as run:
        entries = listing.tree_entries(tmp_path, "HEAD", pathspecs=("src/a", "src/b", "src/missing"))
    assert [(str(e.path), e.mode) for e in entries] == [("src/a", "100644"), ("src/b", "100755")]
    assert _argv(run) == ("--literal-pathspecs", "ls-tree", "--full-tree", "-z", "HEAD", "--", "src/a", "src/b", "src/missing")
    with _stub(b"") as run:
        assert listing.tree_entries(tmp_path, "HEAD", pathspecs=("nope",)) == ()


def test_index_entries_with_tags_argv(tmp_path: Path) -> None:
    with _stub(b"H 100644 587be6b4c3f93f93c489c0111bba5596147a26cb 0\tx\x00") as run:
        (entry,) = listing.index_entries(tmp_path, tags=True)
    assert _argv(run) == ("ls-files", "--full-name", "-v", "--stage", "-z", "--")
    assert entry.tag == "H"


def test_commit_paths_first_parent(tmp_path: Path) -> None:
    with _stub() as run:
        listing.commit_paths(tmp_path, "abc", first_parent=True)
    assert _argv(run) == ("-c", "diff.relative=false", "show", "--name-only", "--format=", "-z", "--no-renames", "--first-parent", "-m", "abc", "--")
