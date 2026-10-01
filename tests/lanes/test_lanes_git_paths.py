"""Real-git quoted / non-ASCII path cases for the lanes, watcher and gitignore sites.

Mission git-paths-are-data, WP04. Each site used to read git's display text
(``status --porcelain`` quotes a path with a space; a rename reads ``a -> b``)
or split ``-z`` output itself. These tests drive the migrated sites against
real temporary repositories (no git mocks).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.gitignore_manager import GitignorePathError, _tracked_git_paths
from specify_cli.lanes.auto_rebase import (
    _list_conflicted_files,
    _staged_status_artifact_dirs,
    _status_artifact_paths_from_ref,
)
from specify_cli.lanes.checkout_occupancy import dirty_paths
from specify_cli.lanes.consolidation import _make_merge_env, _unmerged_paths
from specify_cli.lanes.for_review_gate import _has_qualifying_commit_since_claim_base
from specify_cli.lanes.worktree_allocator import DirtyWorktreeError, _validate_worktree_clean
from specify_cli.live_work.models import FileOperation
from specify_cli.live_work.watcher import _collect_changes

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

QUOTED = "café notes.txt"
ARROW = "a -> b.txt"
SLUG = "001-café mission"
EVENTS = f"kitty-specs/{SLUG}/status.events.jsonl"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


def _write(root: Path, rel: str, text: str = "x\n") -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _commit_all(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD").strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "commit.gpgsign", "false")
    _write(root, "seed.txt", "seed\n")
    _commit_all(root, "seed")
    return root


class TestCheckoutOccupancyDirtyPaths:
    def test_quoted_path_is_reported_raw(self, repo: Path) -> None:
        _write(repo, QUOTED)
        assert dirty_paths(repo, owned_prefixes=()) == [QUOTED]

    def test_file_named_like_a_rename_is_one_path(self, repo: Path) -> None:
        _write(repo, ARROW)
        assert dirty_paths(repo, owned_prefixes=()) == [ARROW]

    def test_rename_reports_the_new_path_only(self, repo: Path) -> None:
        _write(repo, "old name é.txt", "same\n")
        _commit_all(repo, "add")
        _git(repo, "mv", "--", "old name é.txt", "new name é.txt")
        assert dirty_paths(repo, owned_prefixes=()) == ["new name é.txt"]

    def test_owned_file_prefix_is_excluded_even_with_quoted_siblings(self, repo: Path) -> None:
        # Track the mission directory first so status.json is listed individually
        # (git collapses a wholly-untracked directory into one ``dir/`` entry).
        _write(repo, f"kitty-specs/{SLUG}/meta.json")
        _commit_all(repo, "mission dir")
        _write(repo, f"kitty-specs/{SLUG}/status.json")
        _write(repo, QUOTED)
        owned = (f"kitty-specs/{SLUG}/status.json", ".kittify/")
        assert dirty_paths(repo, owned_prefixes=owned) == [QUOTED]

    def test_collapsed_owned_directory_is_excluded(self, repo: Path) -> None:
        _write(repo, ".kittify/runtime/state é.json")
        assert dirty_paths(repo, owned_prefixes=(".kittify/",)) == []

    def test_sibling_with_shared_string_prefix_is_not_owned(self, repo: Path) -> None:
        _write(repo, ".kittify-extra/file.txt")
        assert dirty_paths(repo, owned_prefixes=(".kittify/",)) == [".kittify-extra/"]

    def test_git_failure_propagates(self, tmp_path: Path) -> None:
        plain = tmp_path / "plain"
        plain.mkdir()
        with pytest.raises(RuntimeError):
            dirty_paths(plain, owned_prefixes=())


class TestValidateWorktreeClean:
    def test_quoted_untracked_path_blocks(self, repo: Path) -> None:
        _write(repo, QUOTED)
        with pytest.raises(DirtyWorktreeError):
            _validate_worktree_clean(repo, "a")

    def test_clean_checkout_passes(self, repo: Path) -> None:
        _validate_worktree_clean(repo, "a")


class TestForReviewGate:
    def test_quoted_implementation_path_counts(self, repo: Path) -> None:
        base = _git(repo, "rev-parse", "HEAD").strip()
        _write(repo, "src/café module.py")
        _commit_all(repo, "impl")
        assert _has_qualifying_commit_since_claim_base(repo, base, SLUG) is True

    def test_non_ascii_kittify_path_is_excluded(self, repo: Path) -> None:
        base = _git(repo, "rev-parse", "HEAD").strip()
        _write(repo, ".kittify/café.yaml")
        _commit_all(repo, "meta")
        assert _has_qualifying_commit_since_claim_base(repo, base, SLUG) is False

    def test_move_into_kittify_still_qualifies_via_origin(self, repo: Path) -> None:
        # ``--no-renames``: the deleted origin ``src/x.py`` is listed, so a pure
        # move into an excluded prefix is not mistaken for status-only work.
        _write(repo, "src/x.py", "def x() -> int:\n    return 1\n" * 3)
        base = _commit_all(repo, "add impl")
        (repo / ".kittify").mkdir(exist_ok=True)
        _git(repo, "mv", "src/x.py", ".kittify/x.py")
        _commit_all(repo, "move")
        assert _has_qualifying_commit_since_claim_base(repo, base, SLUG) is True

    def test_unresolvable_range_refuses(self, repo: Path) -> None:
        assert _has_qualifying_commit_since_claim_base(repo, "0" * 40, SLUG) is False


def _conflicting_merge(repo: Path, rel: str) -> None:
    _write(repo, rel, "base\n")
    _commit_all(repo, "base")
    _git(repo, "checkout", "-q", "-b", "side")
    _write(repo, rel, "side\n")
    _commit_all(repo, "side")
    _git(repo, "checkout", "-q", "main")
    _write(repo, rel, "main\n")
    _commit_all(repo, "main")
    merged = subprocess.run(["git", "-C", str(repo), "merge", "side"], capture_output=True, text=True, check=False)
    assert merged.returncode != 0


class TestMergeConflictListings:
    def test_list_conflicted_files_returns_quoted_path(self, repo: Path) -> None:
        rel = "local data/café conflict.txt"
        _conflicting_merge(repo, rel)
        assert _list_conflicted_files(repo) == [repo / rel]

    def test_list_conflicted_files_is_empty_when_git_fails(self, tmp_path: Path) -> None:
        plain = tmp_path / "plain"
        plain.mkdir()
        assert _list_conflicted_files(plain) == []

    def test_unmerged_paths_returns_quoted_path(self, repo: Path) -> None:
        rel = "local data/café conflict.txt"
        _conflicting_merge(repo, rel)
        assert _unmerged_paths(repo, _make_merge_env()) == (rel,)

    def test_unmerged_paths_raises_when_git_fails(self, tmp_path: Path) -> None:
        plain = tmp_path / "plain"
        plain.mkdir()
        with pytest.raises(RuntimeError, match="Could not inspect squash merge conflicts"):
            _unmerged_paths(plain, _make_merge_env())


class TestAutoRebaseStatusArtifacts:
    def test_status_artifacts_under_quoted_mission_dir_are_found(self, repo: Path) -> None:
        _write(repo, EVENTS)
        _write(repo, f"kitty-specs/{SLUG}/status.json")
        _write(repo, f"kitty-specs/{SLUG}/notes é.md")
        _commit_all(repo, "mission")
        paths, error = _status_artifact_paths_from_ref(repo, "HEAD")
        assert error is None
        assert paths == {EVENTS, f"kitty-specs/{SLUG}/status.json"}

    def test_unknown_ref_reports_an_error(self, repo: Path) -> None:
        paths, error = _status_artifact_paths_from_ref(repo, "no-such-ref")
        assert paths == set()
        assert error

    def test_staged_deletion_of_quoted_events_file_refuses(self, repo: Path) -> None:
        _write(repo, EVENTS)
        _commit_all(repo, "mission")
        _git(repo, "rm", "-q", "--", EVENTS)
        dirs, error = _staged_status_artifact_dirs(repo)
        assert dirs == set()
        assert error is not None and EVENTS in error

    def test_staged_modification_collects_the_quoted_feature_dir(self, repo: Path) -> None:
        _write(repo, EVENTS)
        _commit_all(repo, "mission")
        _write(repo, EVENTS, "changed\n")
        _git(repo, "add", "--", EVENTS)
        dirs, error = _staged_status_artifact_dirs(repo)
        assert error is None
        assert dirs == {repo / "kitty-specs" / SLUG}

    def test_staged_rename_away_from_events_file_refuses(self, repo: Path) -> None:
        _write(repo, EVENTS, "content that is long enough to be a rename\n" * 5)
        _commit_all(repo, "mission")
        _git(repo, "mv", "--", EVENTS, f"kitty-specs/{SLUG}/status.moved é.jsonl")
        dirs, error = _staged_status_artifact_dirs(repo)
        assert dirs == set()
        assert error is not None and "staged deletion" in error


class TestWatcherCollectChanges:
    def test_quoted_untracked_path_is_a_create(self, repo: Path) -> None:
        _write(repo, QUOTED)
        assert _collect_changes(repo) == [(FileOperation.CREATE, QUOTED, None, 0, 0)]

    def test_rename_with_spaces_reports_origin_path_and_destination(self, repo: Path) -> None:
        _write(repo, "old name é.txt", "same content\n" * 5)
        _commit_all(repo, "add")
        _git(repo, "mv", "--", "old name é.txt", "new name é.txt")
        assert _collect_changes(repo) == [(FileOperation.RENAME, "old name é.txt", "new name é.txt", 0, 0)]

    def test_numstat_deltas_attach_to_quoted_tracked_path(self, repo: Path) -> None:
        _write(repo, QUOTED, "one\n")
        _commit_all(repo, "add")
        _write(repo, QUOTED, "one\ntwo\nthree\n")
        assert _collect_changes(repo) == [(FileOperation.EDIT, QUOTED, None, 2, 0)]

    def test_non_repository_yields_nothing(self, tmp_path: Path) -> None:
        plain = tmp_path / "plain"
        plain.mkdir()
        assert _collect_changes(plain) == []

    def test_numstat_failure_keeps_operations_without_deltas(self, tmp_path: Path) -> None:
        # Unborn HEAD: ``git status`` works, ``git diff HEAD --numstat`` fails.
        unborn = tmp_path / "unborn"
        unborn.mkdir()
        _git(unborn, "init", "-q", "-b", "main")
        _write(unborn, "fresh.txt", "a\nb\n")
        assert _collect_changes(unborn) == [(FileOperation.CREATE, "fresh.txt", None, 0, 0)]


class TestGitignoreTrackedPaths:
    def test_tracked_quoted_path_under_root_is_found(self, repo: Path) -> None:
        _write(repo, ".kittify/café notes.txt")
        _commit_all(repo, "tracked")
        assert _tracked_git_paths(repo, ".kittify") == (".kittify/café notes.txt",)

    def test_nothing_tracked_under_root(self, repo: Path) -> None:
        assert _tracked_git_paths(repo, ".kittify") == ()

    def test_glob_characters_in_root_are_literal(self, repo: Path) -> None:
        _write(repo, "abc/file.txt")
        _commit_all(repo, "tracked")
        assert _tracked_git_paths(repo, "a*") == ()

    def test_git_failure_fails_closed(self, tmp_path: Path) -> None:
        plain = tmp_path / "plain"
        plain.mkdir()
        with pytest.raises(GitignorePathError, match="Could not inspect tracked paths"):
            _tracked_git_paths(plain, ".kittify")
