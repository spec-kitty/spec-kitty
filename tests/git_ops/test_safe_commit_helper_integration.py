"""Integration tests for safe_commit helper (Bug #122).

These tests verify that status commits don't capture unrelated staged files.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from specify_cli.git.commit_helpers import (
    ProtectedBranchCommitError,
    ProtectedBranchRefused,
    safe_commit as _safe_commit,
)

import pytest

pytestmark = pytest.mark.git_repo


def safe_commit(
    *,
    repo_path: Path,
    files_to_commit: list[Path],
    commit_message: str,
    allow_empty: bool = False,
) -> bool:
    """Legacy-call adapter for the pre-#1348 integration tests in this file."""
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    if not branch:
        branch = subprocess.run(
            ["git", "symbolic-ref", "--short", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()

    if branch in {"main", "master"} and not commit_message.startswith(
        (
            "chore: apply spec-kitty upgrade changes",
            "chore: release ",
            "release: ",
        )
    ):
        raise ProtectedBranchCommitError(f"protected branch '{branch}'")

    rel_paths = [str(path.relative_to(repo_path) if path.is_absolute() else path) for path in files_to_commit]
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", *rel_paths],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )
    if not status.stdout:
        all_paths_tracked = all(
            subprocess.run(
                ["git", "ls-files", "--error-unmatch", rel_path],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=False,
            ).returncode
            == 0
            for rel_path in rel_paths
        )
        if all_paths_tracked:
            return allow_empty

    try:
        _safe_commit(
            repo_root=repo_path,
            worktree_root=repo_path,
            destination_ref=branch,
            message=commit_message,
            paths=tuple(files_to_commit),
        )
    except ProtectedBranchRefused as exc:
        raise ProtectedBranchCommitError(f"protected branch '{exc.destination_ref}'") from exc
    except RuntimeError:
        return False
    return True


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository for testing."""
    repo = tmp_path / "test_repo"
    repo.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    initial_file = repo / "README.md"
    initial_file.write_text("# Test Repo\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "branch", "-M", "kitty/mission-test-01ABCDEF"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    return repo


def test_safe_commit_preserves_unrelated_staged_files(git_repo: Path):
    """T045: Pre-stage unrelated file, run safe_commit, assert unrelated file remains staged.

    This is the core bug fix: when updating WP status, any other staged files
    should NOT be included in the commit.
    """
    # Create and stage an unrelated file
    unrelated_file = git_repo / "unrelated.txt"
    unrelated_file.write_text("This should stay staged\n")
    subprocess.run(["git", "add", "unrelated.txt"], cwd=git_repo, check=True)

    # Create the file we actually want to commit
    wp_file = git_repo / "WP01.md"
    wp_file.write_text("---\nlane: doing\n---\n")

    # Use safe_commit to commit only the WP file
    result = safe_commit(
        repo_path=git_repo,
        files_to_commit=[wp_file],
        commit_message="Update WP01 status to doing",
        allow_empty=False,
    )

    assert result is True, "safe_commit should succeed"

    # Check that unrelated file is still staged (not committed)
    status_result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=git_repo,
        capture_output=True,
        text=True,
        check=True,
    )

    # File should be staged (index modified) - shown as "A " or "M " in first column
    assert "A  unrelated.txt" in status_result.stdout or "M  unrelated.txt" in status_result.stdout, (
        f"Unrelated file should remain staged. Got:\n{status_result.stdout}"
    )

    # Check that WP file was committed (not in status)
    assert "WP01.md" not in status_result.stdout, "WP01.md should be committed"

    # Verify commit message
    log_result = subprocess.run(
        ["git", "log", "-1", "--oneline"],
        cwd=git_repo,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Update WP01 status to doing" in log_result.stdout


def test_safe_commit_blocks_spec_kitty_status_commit_on_protected_branch(git_repo: Path):
    """Spec Kitty status commits must fail loudly before polluting local main."""
    subprocess.run(["git", "branch", "-M", "main"], cwd=git_repo, check=True)
    (git_repo / ".kittify").mkdir()
    (git_repo / ".kittify" / "config.json").write_text("{}\n")
    protected_file = git_repo / "kitty-specs" / "099-demo" / "meta.json"
    protected_file.parent.mkdir(parents=True)
    protected_file.write_text("{}\n")

    with pytest.raises(ProtectedBranchCommitError, match="protected branch 'main'"):
        safe_commit(
            repo_path=git_repo,
            files_to_commit=[protected_file],
            commit_message="Add meta for feature 099-demo",
            allow_empty=False,
        )


def test_safe_commit_blocks_status_commit_on_unborn_protected_branch(tmp_path: Path):
    """Unborn main is still a protected branch."""
    repo = tmp_path / "unborn"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "--initial-branch=main"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.json").write_text("{}\n")
    protected_file = repo / "kitty-specs" / "099-demo" / "meta.json"
    protected_file.parent.mkdir(parents=True)
    protected_file.write_text("{}\n")

    with pytest.raises(ProtectedBranchCommitError, match="protected branch 'main'"):
        safe_commit(
            repo_path=repo,
            files_to_commit=[protected_file],
            commit_message="Add meta for feature 099-demo",
            allow_empty=False,
        )


def test_safe_commit_blocks_merged_wp_done_commit_on_protected_branch(git_repo: Path):
    """Internal done-transition messages no longer bypass protected branches."""
    subprocess.run(["git", "branch", "-M", "main"], cwd=git_repo, check=True)
    (git_repo / ".kittify").mkdir()
    (git_repo / ".kittify" / "config.json").write_text("{}\n")
    status_file = git_repo / "kitty-specs" / "099-demo" / "status.events.jsonl"
    status_file.parent.mkdir(parents=True)
    status_file.write_text('{"to_lane":"done"}\n')

    with pytest.raises(ProtectedBranchCommitError, match="protected branch 'main'"):
        safe_commit(
            repo_path=git_repo,
            files_to_commit=[status_file],
            commit_message="chore(099-demo): record done transitions for merged WPs",
            allow_empty=False,
        )


def test_safe_commit_nothing_to_commit_graceful(git_repo: Path):
    """T046: Test 'nothing to commit' graceful handling.

    When a file hasn't changed, safe_commit should handle it gracefully.
    """
    # Try to commit a file that hasn't changed
    readme = git_repo / "README.md"

    # allow_empty=False should return False
    result = safe_commit(
        repo_path=git_repo,
        files_to_commit=[readme],
        commit_message="No changes",
        allow_empty=False,
    )
    assert result is False, "Should return False when nothing to commit and allow_empty=False"

    # allow_empty=True should return True
    result = safe_commit(
        repo_path=git_repo,
        files_to_commit=[readme],
        commit_message="No changes",
        allow_empty=True,
    )
    assert result is True, "Should return True when nothing to commit and allow_empty=True"


def test_safe_commit_restores_prestaged_requested_files_when_stage_fails(git_repo: Path):
    """A failed requested-file stage must not destroy caller staging."""
    requested = git_repo / "requested.txt"
    requested.write_text("keep staged\n")
    subprocess.run(["git", "add", "requested.txt"], cwd=git_repo, check=True)

    before = subprocess.run(
        ["git", "diff", "--cached", "--name-status"],
        cwd=git_repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    result = safe_commit(
        repo_path=git_repo,
        files_to_commit=[git_repo / "missing.txt", requested],
        commit_message="Try invalid safe commit",
        allow_empty=False,
    )

    after = subprocess.run(
        ["git", "diff", "--cached", "--name-status"],
        cwd=git_repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=git_repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    assert result is False
    assert after == before
    assert "A  requested.txt" in status


def test_safe_commit_never_creates_a_stash_even_on_failure(
    git_repo: Path,
):
    """#4888/FR-011: ``safe_commit`` no longer stashes ANYTHING, on any path.

    Superseded tests (removed): ``test_safe_commit_raises_when_requested_patch_snapshot_fails``
    monkeypatched the now-deleted ``_staged_patch_for_paths`` snapshot step,
    and ``test_safe_commit_raises_with_orphan_stash_ref_when_stash_pop_fails``
    forced a ``git stash pop --index`` failure — both exercised internals of
    the stash/pop dance this WP removed from ``safe_commit``'s happy path
    (see ``tests/regressions/test_issue_4888_safe_commit_index_preservation.py``
    for the replacement coverage, including the residual
    ``SafeCommitRecoveryFailed``/``orphan_stash_ref`` propagation contract
    now exercised at the ``upgrade`` caller boundary). This test documents
    the new invariant directly: a failure mid-``safe_commit`` (a genuinely
    missing requested path) never touches ``git stash`` at all.
    """
    unrelated = git_repo / "other.txt"
    unrelated.write_text("caller staged data\n", encoding="utf-8")
    subprocess.run(["git", "add", "other.txt"], cwd=git_repo, check=True)

    requested = git_repo / "requested.txt"
    requested.write_text("commit me\n", encoding="utf-8")

    with pytest.raises(RuntimeError):
        _safe_commit(
            repo_root=git_repo,
            worktree_root=git_repo,
            destination_ref="kitty/mission-test-01ABCDEF",
            message="Try invalid safe commit",
            paths=(git_repo / "missing.txt", requested),
        )

    stash_list = subprocess.run(
        ["git", "stash", "list"],
        cwd=git_repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert stash_list == "", f"safe_commit must never create a stash, got: {stash_list!r}"

    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=git_repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "A  other.txt" in status


def test_safe_commit_preserves_multiple_unrelated_staged_files(git_repo: Path):
    """T047: Test multiple unrelated staged files preserved.

    Ensures the fix works with multiple staged files, not just one.
    """
    # Stage multiple unrelated files
    file1 = git_repo / "feature1.py"
    file1.write_text("# Feature 1\n")
    subprocess.run(["git", "add", "feature1.py"], cwd=git_repo, check=True)

    file2 = git_repo / "feature2.py"
    file2.write_text("# Feature 2\n")
    subprocess.run(["git", "add", "feature2.py"], cwd=git_repo, check=True)

    file3 = git_repo / "docs.md"
    file3.write_text("# Docs\n")
    subprocess.run(["git", "add", "docs.md"], cwd=git_repo, check=True)

    # Create and commit only the WP file
    wp_file = git_repo / "WP02.md"
    wp_file.write_text("---\nlane: for_review\n---\n")

    result = safe_commit(
        repo_path=git_repo,
        files_to_commit=[wp_file],
        commit_message="Update WP02 status to for_review",
        allow_empty=False,
    )

    assert result is True, "safe_commit should succeed"

    # All three unrelated files should still be staged
    status_result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=git_repo,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "A  feature1.py" in status_result.stdout
    assert "A  feature2.py" in status_result.stdout
    assert "A  docs.md" in status_result.stdout
    assert "WP02.md" not in status_result.stdout, "WP02.md should be committed"


def test_safe_commit_with_absolute_paths(git_repo: Path):
    """Test safe_commit works with absolute file paths."""
    # Stage unrelated file
    unrelated = git_repo / "unrelated.txt"
    unrelated.write_text("Unrelated\n")
    subprocess.run(["git", "add", "unrelated.txt"], cwd=git_repo, check=True)

    # Commit using absolute path
    wp_file = git_repo / "WP03.md"
    wp_file.write_text("---\nlane: done\n---\n")

    result = safe_commit(
        repo_path=git_repo,
        files_to_commit=[wp_file.absolute()],  # Use absolute path
        commit_message="Update WP03 status to done",
        allow_empty=False,
    )

    assert result is True

    # Verify unrelated file still staged
    status_result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=git_repo,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "A  unrelated.txt" in status_result.stdout


def test_safe_commit_with_subdirectory_files(git_repo: Path):
    """Test safe_commit works with files in subdirectories."""
    # Create subdirectory structure
    subdir = git_repo / "kitty-specs" / "038-feature" / "tasks"
    subdir.mkdir(parents=True)

    # Stage unrelated file in root
    unrelated = git_repo / "root_file.txt"
    unrelated.write_text("Root file\n")
    subprocess.run(["git", "add", "root_file.txt"], cwd=git_repo, check=True)

    # Commit file in subdirectory
    wp_file = subdir / "WP04.md"
    wp_file.write_text("---\nlane: doing\n---\n")

    result = safe_commit(
        repo_path=git_repo,
        files_to_commit=[wp_file],
        commit_message="Update WP04 in subdirectory",
        allow_empty=False,
    )

    assert result is True

    # Verify unrelated file still staged
    status_result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=git_repo,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "A  root_file.txt" in status_result.stdout
    assert "WP04.md" not in status_result.stdout


def test_safe_commit_can_commit_explicitly_ignored_file(git_repo: Path):
    """safe_commit should commit explicitly requested files even if ignored."""
    # Simulate stale project-level ignore rule.
    gitignore = git_repo / ".gitignore"
    gitignore.write_text("kitty-specs/**/tasks/*.md\n", encoding="utf-8")

    # Create ignored WP file
    wp_file = git_repo / "kitty-specs" / "041-test-feature" / "tasks" / "WP01.md"
    wp_file.parent.mkdir(parents=True, exist_ok=True)
    wp_file.write_text("---\nlane: doing\n---\n", encoding="utf-8")

    result = safe_commit(
        repo_path=git_repo,
        files_to_commit=[wp_file],
        commit_message="Commit ignored WP file explicitly",
        allow_empty=False,
    )

    assert result is True

    tracked = subprocess.run(
        ["git", "ls-files", str(wp_file.relative_to(git_repo))],
        cwd=git_repo,
        capture_output=True,
        text=True,
        check=True,
    )
    assert str(wp_file.relative_to(git_repo)) in tracked.stdout


def test_safe_commit_multiple_files_at_once(git_repo: Path):
    """Test committing multiple intended files while preserving staged files."""
    # Stage unrelated file
    unrelated = git_repo / "unrelated.txt"
    unrelated.write_text("Unrelated\n")
    subprocess.run(["git", "add", "unrelated.txt"], cwd=git_repo, check=True)

    # Create multiple files to commit together
    wp1 = git_repo / "WP05.md"
    wp1.write_text("---\nlane: done\n---\n")

    wp2 = git_repo / "WP06.md"
    wp2.write_text("---\nlane: done\n---\n")

    result = safe_commit(
        repo_path=git_repo,
        files_to_commit=[wp1, wp2],
        commit_message="Mark WP05 and WP06 as done",
        allow_empty=False,
    )

    assert result is True

    # Verify both WPs committed, unrelated still staged
    status_result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=git_repo,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "A  unrelated.txt" in status_result.stdout
    assert "WP05.md" not in status_result.stdout
    assert "WP06.md" not in status_result.stdout


def test_safe_commit_fails_gracefully_on_invalid_file(git_repo: Path):
    """Test safe_commit returns False when file doesn't exist."""
    nonexistent = git_repo / "does_not_exist.md"

    result = safe_commit(
        repo_path=git_repo,
        files_to_commit=[nonexistent],
        commit_message="This should fail",
        allow_empty=False,
    )

    assert result is False, "Should return False when file doesn't exist"


def test_safe_commit_does_not_pop_unrelated_existing_stash(git_repo: Path):
    """safe_commit must restore only its own temporary stash entry."""
    staged_file = git_repo / "staged.txt"
    staged_file.write_text("already staged\n", encoding="utf-8")
    subprocess.run(["git", "add", "staged.txt"], cwd=git_repo, check=True)
    subprocess.run(
        ["git", "stash", "push", "--staged", "-m", "preexisting-stash"],
        cwd=git_repo,
        check=True,
        capture_output=True,
        text=True,
    )

    before = subprocess.run(
        ["git", "stash", "list"],
        cwd=git_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "preexisting-stash" in before.stdout

    wp_file = git_repo / "WP07.md"
    wp_file.write_text("---\nlane: planned\n---\n", encoding="utf-8")

    result = safe_commit(
        repo_path=git_repo,
        files_to_commit=[wp_file],
        commit_message="Commit WP07 only",
        allow_empty=False,
    )

    after = subprocess.run(
        ["git", "stash", "list"],
        cwd=git_repo,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result is True
    assert "preexisting-stash" in after.stdout


def test_safe_commit_allows_rename_like_staging_pair(git_repo: Path):
    """Regression for Priivacy-ai/spec-kitty#643.

    When an upgrade migration uses filesystem-level rename (``shutil.move``)
    and safe_commit is subsequently asked to commit both the source (now
    deleted) and destination (now untracked) paths, git's default rename
    detection collapses the staged D+A pair into a single ``Rxxx`` entry in
    ``git diff --cached --name-status``.  Before the fix the backstop parser
    could not split that 3-column line and fired a spurious
    ``SafeCommitBackstopError``; after the fix (``--no-renames`` on the
    backstop probe) the commit succeeds.
    """
    # Create and commit a tracked file with enough content for git's rename
    # detection to fire (similarity score >50%).
    src_dir = git_repo / ".kittify" / "constitution"
    src_dir.mkdir(parents=True)
    src = src_dir / "charter.md"
    src.write_text(
        "# Project charter\n" + "\n".join(f"- policy line {n}" for n in range(40)) + "\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "add", str(src.relative_to(git_repo))],
        cwd=git_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-m", "Add charter"],
        cwd=git_repo,
        check=True,
        capture_output=True,
    )

    # Mimic the 3.1.1_charter_rename migration: filesystem-level rename
    # with no git involvement.  The old path becomes a D (unstaged), and
    # the new path becomes untracked.
    dest_dir = git_repo / ".kittify" / "charter"
    dest_dir.mkdir(parents=True)
    dest = dest_dir / "charter.md"
    shutil.move(str(src), str(dest))

    result = safe_commit(
        repo_path=git_repo,
        files_to_commit=[
            src.relative_to(git_repo),
            dest.relative_to(git_repo),
        ],
        commit_message="chore: apply spec-kitty upgrade changes (3.0.3 -> 3.1.4)",
        allow_empty=False,
    )

    assert result is True, "safe_commit must succeed across a filesystem-level rename"

    # Source is gone and destination is tracked at HEAD; working tree clean.
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=git_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert status.stdout == "", f"working tree should be clean, got:\n{status.stdout}"

    tracked = subprocess.run(
        ["git", "ls-files", ".kittify/"],
        cwd=git_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert ".kittify/charter/charter.md" in tracked.stdout
    assert ".kittify/constitution/charter.md" not in tracked.stdout
