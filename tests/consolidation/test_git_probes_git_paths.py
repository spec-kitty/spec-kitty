"""Merge-seam git probes read paths as data (mission git-paths-are-data, WP03).

Real temporary repositories, no git mocks. Every case uses a path git would
quote in display text (a space in ``git status``; a non-ASCII name in ``diff``,
``show`` and ``ls-tree``), which the former line-based parsing mangled.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kernel.git import GitCommandError
from specify_cli.consolidation import git_probes
from specify_cli.consolidation.bookkeeping_projection import (
    _post_checkpoint_commit_shas,
    _post_checkpoint_mission_paths,
    project_post_checkpoint_commits_to_target,
)

pytestmark = pytest.mark.git_repo

_SPACED = "src/local data/f.txt"
_ACCENTED = "é/g.txt"


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return done.stdout.strip()


def _write(repo: Path, rel: str, text: str = "x\n") -> None:
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _write(repo, "README.md", "init\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


def _commit_all(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


class TestPorcelainInvariant:
    """``_raw_porcelain_status`` + ``_classify_porcelain_lines`` over typed entries."""

    def test_expected_quoted_path_is_not_offending(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        _write(repo, _SPACED, "one\n")
        _commit_all(repo, "add")
        _write(repo, _SPACED, "two\n")

        rc, entries = git_probes._raw_porcelain_status(repo)
        offending, skipped = git_probes._classify_porcelain_lines(entries, {_SPACED})

        assert rc == 0
        assert offending == []
        assert skipped == 0

    def test_unexpected_quoted_path_is_offending_with_its_real_path(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        _write(repo, _SPACED, "one\n")
        _commit_all(repo, "add")
        _write(repo, _SPACED, "two\n")

        _rc, entries = git_probes._raw_porcelain_status(repo)
        offending, _skipped = git_probes._classify_porcelain_lines(entries, set())

        assert [str(entry.path) for entry in offending] == [_SPACED]

    def test_residue_predicate_sees_the_unquoted_path(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        _write(repo, _ACCENTED, "one\n")
        _commit_all(repo, "add")
        _write(repo, _ACCENTED, "two\n")
        seen: list[str] = []

        _rc, entries = git_probes._raw_porcelain_status(repo)
        offending, _skipped = git_probes._classify_porcelain_lines(entries, set(), residue_predicate=lambda p: seen.append(p) is None)

        assert seen == [_ACCENTED]
        assert offending == []

    def test_first_modified_entry_keeps_its_leading_status_column(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        _write(repo, "README.md", "changed\n")

        _rc, entries = git_probes._raw_porcelain_status(repo)

        assert [(entry.xy, str(entry.path)) for entry in entries] == [(" M", "README.md")]

    def test_untracked_quoted_directory_is_skipped_and_counted(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        _write(repo, "new dir/x.txt")

        _rc, entries = git_probes._raw_porcelain_status(repo)
        offending, skipped = git_probes._classify_porcelain_lines(entries, set())

        assert offending == []
        assert skipped == 1

    def test_rename_into_an_expected_path_still_offends_for_its_source(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        _write(repo, "src/core.py", "code\n" * 20)
        _commit_all(repo, "add")
        (repo / "kitty-specs/m").mkdir(parents=True)
        _git(repo, "mv", "src/core.py", "kitty-specs/m/meta.json")

        _rc, entries = git_probes._raw_porcelain_status(repo)
        offending, _skipped = git_probes._classify_porcelain_lines(entries, {"kitty-specs/m/meta.json"})

        # The destination is expected, but the source deletion is real divergence.
        assert [(str(e.orig_path), str(e.path)) for e in offending] == [("src/core.py", "kitty-specs/m/meta.json")]

    def test_rename_is_exempt_when_both_sides_are_expected(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        _write(repo, "docs/a.md", "text\n" * 20)
        _commit_all(repo, "add")
        _git(repo, "mv", "docs/a.md", "docs/b.md")

        _rc, entries = git_probes._raw_porcelain_status(repo)
        offending, _skipped = git_probes._classify_porcelain_lines(entries, {"docs/a.md", "docs/b.md"})

        assert [e.orig_path for e in entries] != [None]
        assert offending == []

    def test_a_file_literally_named_with_an_arrow_is_one_path(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        _write(repo, "a -> b", "one\n")
        _commit_all(repo, "add")
        _write(repo, "a -> b", "two\n")

        _rc, entries = git_probes._raw_porcelain_status(repo)
        exempt, _ = git_probes._classify_porcelain_lines(entries, {"a -> b"})
        not_exempt, _ = git_probes._classify_porcelain_lines(entries, {"b"})

        assert [(str(e.path), e.orig_path) for e in entries] == [("a -> b", None)]
        assert exempt == []
        assert [str(e.path) for e in not_exempt] == ["a -> b"]

    def test_a_failed_status_reports_git_exit_code_and_no_entries(self, tmp_path: Path) -> None:
        plain = tmp_path / "plain"
        plain.mkdir()

        rc, entries = git_probes._raw_porcelain_status(plain)

        assert rc != 0
        assert entries == ()


class TestPathsHaveStatusChanges:
    def test_dirty_quoted_path_is_seen(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        _write(repo, _SPACED)

        assert git_probes._paths_have_status_changes(repo, [repo / _SPACED]) is True

    def test_clean_quoted_path_is_not_dirty(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        _write(repo, _SPACED)
        _commit_all(repo, "add")

        assert git_probes._paths_have_status_changes(repo, [repo / _SPACED]) is False

    def test_only_the_requested_paths_count(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        _write(repo, _SPACED)
        _write(repo, "other.txt")
        _git(repo, "add", _SPACED)
        _git(repo, "commit", "-q", "-m", "spaced")

        assert git_probes._paths_have_status_changes(repo, [repo / _SPACED]) is False
        assert git_probes._paths_have_status_changes(repo, [repo / "other.txt"]) is True

    def test_unreadable_status_fails_closed_as_changed(self, tmp_path: Path) -> None:
        plain = tmp_path / "plain"
        plain.mkdir()

        assert git_probes._paths_have_status_changes(plain, [plain / "a.txt"]) is True


class TestSquashContentProbes:
    def test_changed_paths_in_range_returns_real_paths_with_status(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        base = _git(repo, "rev-parse", "HEAD")
        _write(repo, _SPACED)
        _write(repo, _ACCENTED)
        tip = _commit_all(repo, "quoted")

        changes = git_probes.changed_paths_in_range(repo, base, tip)

        assert sorted(changes) == sorted([("A", _SPACED), ("A", _ACCENTED)])

    def test_changed_paths_in_range_lists_a_rename_as_delete_plus_add(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        _write(repo, _SPACED, "content\n" * 20)
        base = _commit_all(repo, "add")
        _git(repo, "mv", _SPACED, "src/local data/renamed.txt")
        tip = _commit_all(repo, "rename")

        changes = git_probes.changed_paths_in_range(repo, base, tip)

        assert sorted(changes) == [("A", "src/local data/renamed.txt"), ("D", _SPACED)]

    def test_changed_paths_in_range_raises_probe_error_on_a_bad_revision(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)

        with pytest.raises(git_probes.GitProbeError):
            git_probes.changed_paths_in_range(repo, "no-such-ref", "HEAD")

    def test_changed_paths_of_returns_real_paths(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        _write(repo, _SPACED)
        _write(repo, _ACCENTED)
        sha = _commit_all(repo, "quoted")

        assert sorted(git_probes.changed_paths_of(repo, sha)) == sorted([_SPACED, _ACCENTED])

    def test_changed_paths_of_raises_probe_error_on_a_bad_commit(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)

        with pytest.raises(git_probes.GitProbeError):
            git_probes.changed_paths_of(repo, "0" * 40)

    def test_path_state_at_finds_a_quoted_path_and_reports_an_absent_one(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        _write(repo, _SPACED, "one\n")
        _commit_all(repo, "add")
        blob = _git(repo, "rev-parse", f"HEAD:{_SPACED}")

        assert git_probes.path_state_at(repo, "HEAD", _SPACED) == blob
        assert git_probes.path_state_at(repo, "HEAD", "src/local data/nope.txt") is None

    def test_path_state_at_does_not_treat_a_prefix_as_the_path(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        _write(repo, "src/store/local.txt")
        _commit_all(repo, "add")

        assert git_probes.path_state_at(repo, "HEAD", "src/store/loc") is None

    def test_path_state_at_raises_probe_error_on_a_bad_ref_and_on_a_non_relative_path(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)

        with pytest.raises(git_probes.GitProbeError):
            git_probes.path_state_at(repo, "no-such-ref", "README.md")
        with pytest.raises(git_probes.GitProbeError):
            git_probes.path_state_at(repo, "HEAD", "/abs/path")


class TestBookkeepingProjectionPaths:
    def _coord(self, tmp_path: Path) -> tuple[Path, str]:
        repo = _repo(tmp_path)
        checkpoint = _git(repo, "rev-parse", "HEAD")
        _git(repo, "branch", "coord")
        _git(repo, "checkout", "-q", "coord")
        _write(repo, "kitty-specs/m1/notes/é note.md")
        _write(repo, "kitty-specs/m1/notes/two words.md")
        _write(repo, "kitty-specs/m1/meta.json", "{}\n")  # primary-partition: never projected
        _write(repo, "kitty-specs/other/notes/x.md")  # another mission: outside the prefix
        _commit_all(repo, "coord work")
        return repo, checkpoint

    def test_projects_quoted_coord_paths_with_their_real_names(self, tmp_path: Path) -> None:
        repo, checkpoint = self._coord(tmp_path)

        paths = _post_checkpoint_mission_paths(repo, "m1", checkpoint, "coord")

        assert sorted(paths) == ["kitty-specs/m1/notes/two words.md", "kitty-specs/m1/notes/é note.md"]

    def test_an_unreadable_diff_propagates_instead_of_projecting_nothing(self, tmp_path: Path) -> None:
        repo, _checkpoint = self._coord(tmp_path)

        # Guard (FR-013): "could not list" must never read as "nothing to project".
        with pytest.raises(GitCommandError):
            _post_checkpoint_mission_paths(repo, "m1", "0" * 40, "coord")

    def test_an_unreadable_commit_window_propagates_instead_of_skipping_projection(self, tmp_path: Path) -> None:
        repo, checkpoint = self._coord(tmp_path)

        assert _post_checkpoint_commit_shas(repo, checkpoint, "coord") == [_git(repo, "rev-parse", "coord")]
        # Guard (FR-013): an empty window skips the projection, so a failed
        # rev-list must raise rather than read as "no coord commits".
        with pytest.raises(GitCommandError):
            _post_checkpoint_commit_shas(repo, "0" * 40, "coord")
        with pytest.raises(GitCommandError):
            project_post_checkpoint_commits_to_target(main_repo=repo, mission_slug="m1", coord_ref="coord", checkpoint_sha="0" * 40)
