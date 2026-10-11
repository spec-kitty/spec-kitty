"""Scope: git_repo integration tests for ExcludeSpecKittyMigration — real git repos.

#5434: mirrors ``test_exclude_worktrees_migration`` for the ``.spec-kitty/``
common-dir exclude backfill. Assertions are on real ``.git/info/exclude``
content and real ``git status --porcelain`` output, never on "a file was
written".
"""

import pytest

from specify_cli.core.git_ops import run_command
from specify_cli.upgrade.migrations.m_4_0_0rc7_exclude_spec_kitty import ExcludeSpecKittyMigration

pytestmark = pytest.mark.git_repo


@pytest.fixture(name="_git_identity")
def git_identity_fixture(monkeypatch):
    """Ensure git commands can commit even if the user has no global config."""
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Spec Kitty")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "spec@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Spec Kitty")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "spec@example.com")


@pytest.fixture
def git_project(tmp_path, _git_identity):
    """Create a git project for testing."""
    repo = tmp_path / "project"
    repo.mkdir()

    # Initialize git repo
    run_command(["git", "init"], cwd=repo)
    run_command(["git", "commit", "--allow-empty", "-m", "Initial commit"], cwd=repo)

    # Create .kittify directory
    kittify = repo / ".kittify"
    kittify.mkdir()

    return repo


@pytest.fixture
def non_git_project(tmp_path):
    """Create a non-git project for testing."""
    repo = tmp_path / "project"
    repo.mkdir()

    # Create .kittify directory (but no git repo)
    kittify = repo / ".kittify"
    kittify.mkdir()

    return repo


def _porcelain(repo) -> list[str]:
    _rc, stdout, _stderr = run_command(["git", "status", "--porcelain"], cwd=repo, capture=True)
    return [line for line in stdout.splitlines() if line.strip()]


class TestExcludeSpecKittyMigration:
    """Tests for ExcludeSpecKittyMigration."""

    def test_detect_returns_true_when_exclusion_missing(self, git_project):
        """detect returns True when .spec-kitty/ is not in .git/info/exclude."""
        migration = ExcludeSpecKittyMigration()
        assert (git_project / ".git").exists()
        assert migration.detect(git_project) is True

    def test_detect_returns_false_when_exclusion_exists(self, git_project):
        """detect flips to False once .spec-kitty/ is in exclude."""
        migration = ExcludeSpecKittyMigration()
        exclude_file = git_project / ".git" / "info" / "exclude"
        assert migration.detect(git_project) is True
        with exclude_file.open("a") as f:
            f.write("\n.spec-kitty/\n")
        assert migration.detect(git_project) is False

    def test_detect_returns_false_for_non_git_repo(self, non_git_project):
        """detect returns False for non-git repositories."""
        migration = ExcludeSpecKittyMigration()
        assert not (non_git_project / ".git").exists()
        assert migration.detect(non_git_project) is False

    def test_can_apply_succeeds_for_git_repo(self, git_project):
        """can_apply returns (True, '') for valid git repositories."""
        migration = ExcludeSpecKittyMigration()
        assert (git_project / ".git").exists()
        can_apply, reason = migration.can_apply(git_project)
        assert can_apply is True
        assert reason == ""

    def test_can_apply_fails_for_non_git_repo(self, non_git_project):
        """can_apply returns (False, reason) for non-git repositories."""
        migration = ExcludeSpecKittyMigration()
        assert not (non_git_project / ".git").exists()
        can_apply, reason = migration.can_apply(non_git_project)
        assert can_apply is False
        assert "Not a git repository" in reason

    def test_apply_adds_exclusion(self, git_project):
        """apply adds .spec-kitty/ to .git/info/exclude and status stays clean."""
        migration = ExcludeSpecKittyMigration()

        result = migration.apply(git_project, dry_run=False)

        assert result.success is True
        assert len(result.errors) == 0

        exclude_file = git_project / ".git" / "info" / "exclude"
        content = exclude_file.read_text()
        assert ".spec-kitty/" in content

        assert any("Added .spec-kitty/" in change for change in result.changes_made)

        # The exclude lives in .git/ (never tracked), so writing it leaves the
        # working tree clean.
        assert _porcelain(git_project) == []

    def test_apply_excludes_review_lock_residue(self, git_project):
        """After apply, a .spec-kitty/ residue file is invisible to git status."""
        migration = ExcludeSpecKittyMigration()
        migration.apply(git_project, dry_run=False)

        lock = git_project / ".spec-kitty" / "review-lock.json"
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text('{"wp_id": "WP01"}\n', encoding="utf-8")

        assert _porcelain(git_project) == [], (
            f"a .spec-kitty/ residue must not dirty the tree after the migration; git status --porcelain: {_porcelain(git_project)!r}"
        )

    def test_apply_dry_run(self, git_project):
        """dry run doesn't modify files."""
        migration = ExcludeSpecKittyMigration()

        exclude_file = git_project / ".git" / "info" / "exclude"
        initial_content = exclude_file.read_text()

        result = migration.apply(git_project, dry_run=True)

        assert result.success is True

        final_content = exclude_file.read_text()
        assert final_content == initial_content

        assert any("Would add" in change for change in result.changes_made)

    def test_apply_skips_non_git_repo(self, non_git_project):
        """apply skips non-git repositories."""
        migration = ExcludeSpecKittyMigration()

        result = migration.apply(non_git_project, dry_run=False)

        assert result.success is True
        assert any("Skipped" in change for change in result.changes_made)

    def test_apply_idempotent(self, git_project):
        """applying the migration multiple times adds no duplicate line."""
        migration = ExcludeSpecKittyMigration()

        result1 = migration.apply(git_project, dry_run=False)
        result2 = migration.apply(git_project, dry_run=False)

        assert result1.success is True
        assert result2.success is True

        exclude_file = git_project / ".git" / "info" / "exclude"
        content = exclude_file.read_text()
        assert content.count(".spec-kitty/") == 1

    def test_migration_metadata(self):
        """migration carries the expected metadata."""
        migration = ExcludeSpecKittyMigration()

        assert migration.migration_id == "4.0.0rc7_exclude_spec_kitty"
        assert migration.target_version == "4.0.0rc7"
        assert "exclude" in migration.description.lower()
