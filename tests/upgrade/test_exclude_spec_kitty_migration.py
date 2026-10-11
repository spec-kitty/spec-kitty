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

    def test_detect_flips_once_the_entry_is_present(self, git_project):
        migration = ExcludeSpecKittyMigration()
        exclude_file = git_project / ".git" / "info" / "exclude"
        assert migration.detect(git_project) is True
        with exclude_file.open("a") as f:
            f.write("\n.spec-kitty/\n")
        assert migration.detect(git_project) is False

    def test_commented_entry_does_not_suppress_the_backfill(self, git_project):
        migration = ExcludeSpecKittyMigration()
        exclude_file = git_project / ".git" / "info" / "exclude"
        with exclude_file.open("a") as f:
            f.write("\n# .spec-kitty/\n")
        assert migration.detect(git_project) is True

    def test_missing_exclude_file_is_not_applicable(self, git_project):
        migration = ExcludeSpecKittyMigration()
        (git_project / ".git" / "info" / "exclude").unlink()
        assert migration.detect(git_project) is False
        can_apply, _reason = migration.can_apply(git_project)
        assert can_apply is False

    def test_apply_excludes_review_lock_residue_and_is_idempotent(self, git_project):
        migration = ExcludeSpecKittyMigration()

        assert migration.apply(git_project, dry_run=False).success is True
        assert migration.apply(git_project, dry_run=False).success is True

        content = (git_project / ".git" / "info" / "exclude").read_text()
        assert content.count(".spec-kitty/") == 1
        lock = git_project / ".spec-kitty" / "review-lock.json"
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text('{"wp_id": "WP01"}\n', encoding="utf-8")
        assert _porcelain(git_project) == []

    def test_linked_worktree_project_backfills_the_common_dir(self, git_project, tmp_path):
        migration = ExcludeSpecKittyMigration()
        linked = tmp_path / "linked"
        run_command(["git", "worktree", "add", "-q", "-b", "side", str(linked)], cwd=git_project)

        assert migration.detect(linked) is True
        assert migration.apply(linked, dry_run=False).success is True

        assert ".spec-kitty/" in (git_project / ".git" / "info" / "exclude").read_text().splitlines()
        assert migration.detect(linked) is False

    def test_dry_run_writes_nothing(self, git_project):
        exclude = git_project / ".git" / "info" / "exclude"
        before = exclude.read_text()
        assert ExcludeSpecKittyMigration().apply(git_project, dry_run=True).success is True
        assert exclude.read_text() == before

    def test_non_git_project_is_skipped(self, non_git_project):
        migration = ExcludeSpecKittyMigration()
        assert migration.detect(non_git_project) is False
        assert migration.can_apply(non_git_project)[0] is False
        assert migration.apply(non_git_project, dry_run=False).success is True
