"""Unit tests for path resolution utilities."""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.core import paths as paths_module
from specify_cli.core.paths import (
    get_main_repo_root,
    locate_project_root,
    is_worktree_context,
    require_explicit_feature,
)


pytestmark = [pytest.mark.unit, pytest.mark.fast]

def test_locate_project_root_from_main(mock_main_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test path resolution from main repository."""
    # Change to main repo directory
    monkeypatch.chdir(mock_main_repo)

    # Call path resolution
    repo_root = locate_project_root()

    # Assert correct root found
    assert repo_root == mock_main_repo
    assert (repo_root / ".kittify").exists()


def test_locate_project_root_from_worktree(mock_worktree: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """Test path resolution from worktree directory."""
    # Change to worktree directory
    monkeypatch.chdir(mock_worktree["worktree_path"])

    # Call path resolution
    repo_root = locate_project_root()

    # Assert walks up to main repo root
    assert repo_root == mock_worktree["repo_root"]
    assert (repo_root / ".kittify").exists()


def test_locate_project_root_with_env_var(mock_main_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test path resolution using SPECIFY_REPO_ROOT environment variable."""
    # Set environment variable
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(mock_main_repo))

    # Change to a different directory
    different_dir = mock_main_repo / "some" / "nested" / "dir"
    different_dir.mkdir(parents=True)
    monkeypatch.chdir(different_dir)

    # Call path resolution - should use env var
    repo_root = locate_project_root()

    # Assert env var was used
    assert repo_root == mock_main_repo


def test_locate_project_root_env_var_worktree_resolves_main_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SPECIFY_REPO_ROOT may point at a lane worktree; callers still need the main repo."""
    main_repo = tmp_path / "repo"
    worktree = main_repo / ".worktrees" / "feature-lane-a"
    gitdir = main_repo / ".git" / "worktrees" / "feature-lane-a"
    gitdir.mkdir(parents=True)
    (main_repo / ".kittify").mkdir(parents=True)
    worktree.mkdir(parents=True)
    (worktree / ".kittify").mkdir()
    (worktree / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")

    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(worktree))

    assert locate_project_root() == main_repo


def test_locate_project_root_from_nested_dir(mock_main_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test path resolution from deeply nested directory."""
    # Create nested directory structure
    nested = mock_main_repo / "kitty-specs" / "001-feature" / "deep" / "nested"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)

    # Call path resolution
    repo_root = locate_project_root()

    # Assert walks up to root
    assert repo_root == mock_main_repo


def test_is_worktree_context(mock_worktree: dict[str, Path]) -> None:
    """Test worktree context detection via .worktrees path heuristic."""
    # Test worktree path
    assert is_worktree_context(mock_worktree["worktree_path"]) is True

    # Test repo root (not in worktree)
    assert is_worktree_context(mock_worktree["repo_root"]) is False

    # Test feature dir (within worktree)
    assert is_worktree_context(mock_worktree["feature_dir"]) is True


def test_is_worktree_context_external_worktree(tmp_path: Path) -> None:
    """Test worktree context detection via .git file with gitdir pointer.

    Simulates an external worktree (e.g. under /tmp) where .git is a file
    pointing to the main repo, NOT under a .worktrees directory.
    """
    # Create a fake external worktree directory (no .worktrees in path)
    external_wt = tmp_path / "external-worktree"
    external_wt.mkdir()

    # Write .git file with gitdir pointer (what git worktree add creates)
    git_file = external_wt / ".git"
    git_file.write_text("gitdir: /some/repo/.git/worktrees/external-worktree\n")

    assert is_worktree_context(external_wt) is True

    # A subdirectory inside the external worktree should also be detected
    nested = external_wt / "src" / "deep"
    nested.mkdir(parents=True)
    assert is_worktree_context(nested) is True


def test_locate_project_root_from_external_worktree_pointer(tmp_path: Path) -> None:
    """locate_project_root should resolve external worktree pointers to main repo root."""
    main_repo = tmp_path / "main-repo"
    main_repo.mkdir()
    (main_repo / ".kittify").mkdir()

    external_wt = tmp_path / "external-wt"
    external_wt.mkdir()
    (external_wt / ".git").write_text(
        f"gitdir: {main_repo}/.git/worktrees/external-wt\n",
        encoding="utf-8",
    )

    assert locate_project_root(external_wt) == main_repo


def test_get_main_repo_root_ignores_non_worktree_git_file(tmp_path: Path) -> None:
    """Separate-git-dir and submodule-style .git files are not worktree roots."""
    repo = tmp_path / "repo"
    repo.mkdir()
    gitdir = tmp_path / "external-git-dir"
    gitdir.mkdir()
    (repo / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")

    assert get_main_repo_root(repo) == repo.resolve()


def test_is_worktree_context_bare_repo_worktree(tmp_path: Path) -> None:
    """Bare-repo worktree (gitdir: /path/repo.git/worktrees/<wt>) IS a worktree."""
    bare_wt = tmp_path / "bare-worktree"
    bare_wt.mkdir()

    # Write .git file with gitdir pointer to a bare repo topology
    git_file = bare_wt / ".git"
    git_file.write_text("gitdir: /srv/repos/myproject.git/worktrees/bare-worktree\n")

    assert is_worktree_context(bare_wt) is True

    # Nested path inside the bare-repo worktree
    nested = bare_wt / "src" / "lib"
    nested.mkdir(parents=True)
    assert is_worktree_context(nested) is True


def test_is_worktree_context_main_repo(tmp_path: Path) -> None:
    """Test that a main repo with .git directory is NOT detected as worktree."""
    # Create a fake main repo with .git directory
    main_repo = tmp_path / "main-repo"
    main_repo.mkdir()
    (main_repo / ".git").mkdir()

    assert is_worktree_context(main_repo) is False

    # Nested path inside main repo
    nested = main_repo / "src" / "lib"
    nested.mkdir(parents=True)
    assert is_worktree_context(nested) is False


def test_is_worktree_context_submodule_gitdir(tmp_path: Path) -> None:
    """Submodule .git file (gitdir: ../.git/modules/foo) must NOT be a worktree."""
    sub = tmp_path / "parent-repo" / "sub"
    sub.mkdir(parents=True)

    git_file = sub / ".git"
    git_file.write_text("gitdir: ../.git/modules/sub\n")

    assert is_worktree_context(sub) is False

    # Nested path inside the submodule
    nested = sub / "src" / "lib"
    nested.mkdir(parents=True)
    assert is_worktree_context(nested) is False


def test_is_worktree_context_separate_git_dir(tmp_path: Path) -> None:
    """Separate-git-dir clone (gitdir: /some/external/dir) must NOT be a worktree."""
    repo = tmp_path / "my-clone"
    repo.mkdir()

    external_gitdir = tmp_path / "external-gitdirs" / "my-clone.git"
    external_gitdir.mkdir(parents=True)

    git_file = repo / ".git"
    git_file.write_text(f"gitdir: {external_gitdir}\n")

    assert is_worktree_context(repo) is False

    nested = repo / "src"
    nested.mkdir()
    assert is_worktree_context(nested) is False


def test_is_worktree_context_handles_gitfile_read_oserror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Should return False when .git pointer cannot be read."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git_file = repo / ".git"
    git_file.write_text("gitdir: /some/repo/.git/worktrees/wt\n", encoding="utf-8")

    original_read_text = Path.read_text

    def _broken_read_text(self: Path, *args, **kwargs):  # type: ignore[no-untyped-def]
        if self == git_file:
            raise OSError("simulated read failure")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _broken_read_text)
    assert is_worktree_context(repo) is False


@pytest.mark.non_sandbox
def test_locate_project_root_no_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test path resolution when no marker exists anywhere up the tree.

    Hermetic against stray ancestor markers (e.g. a developer's `.kittify`
    scratch dir left somewhere under the OS temp directory): the walk-up
    searches for ``KITTIFY_DIR`` in every parent up to the filesystem root, so
    a real ``.kittify`` above ``tmp_path`` would make the real marker match and
    return a non-None root. We point the marker name at a guaranteed-absent
    sentinel so the "no marker found → None" path is tested deterministically
    regardless of the host's temp-directory contents.
    """
    monkeypatch.setattr(paths_module, "KITTIFY_DIR", ".kittify-absent-sentinel-xyz")
    # Create directory without the (sentinel) marker
    no_marker = tmp_path / "no-marker-dir"
    no_marker.mkdir()
    monkeypatch.chdir(no_marker)

    # Call path resolution
    repo_root = locate_project_root()

    # Should return None
    assert repo_root is None


def test_locate_project_root_with_broken_symlink_kittify(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test path resolution gracefully handles broken .kittify symlink."""
    # Create directory with broken .kittify symlink
    test_dir = tmp_path / "test-dir"
    test_dir.mkdir()
    kittify_link = test_dir / ".kittify"
    kittify_link.symlink_to(tmp_path / "nonexistent")

    monkeypatch.chdir(test_dir)

    # Should skip the broken symlink and return None (or continue searching)
    repo_root = locate_project_root()
    assert repo_root is None or repo_root != test_dir


# ---------------------------------------------------------------------------
# Regression tests for require_explicit_feature error messages (T031, T033)
# ---------------------------------------------------------------------------

def test_require_explicit_feature_error_uses_mission_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Error message must say --mission, not --feature (T033 regression)."""
    # Default command_hint should be --mission <slug>
    with pytest.raises(ValueError) as exc_info:
        require_explicit_feature(None)
    assert "--mission" in str(exc_info.value)
    assert "--feature" not in str(exc_info.value)


def test_require_explicit_feature_error_has_complete_example(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Error message must include two complete, copy-pasteable commands (T031)."""
    with pytest.raises(ValueError) as exc_info:
        require_explicit_feature(None)
    error_msg = str(exc_info.value)
    assert "spec-kitty agent context resolve" in error_msg
    assert "spec-kitty agent mission finalize-tasks" in error_msg


def test_require_explicit_feature_error_uses_custom_hint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Custom command_hint overrides default in error message (T031)."""
    with pytest.raises(ValueError) as exc_info:
        require_explicit_feature(None, command_hint="--mission <slug>")
    assert "--mission" in str(exc_info.value)


def test_require_explicit_feature_error_uses_real_slug(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Error example uses the first real slug when kitty-specs is available (T031)."""
    (tmp_path / ".kittify").mkdir()
    kitty_specs = tmp_path / "kitty-specs"
    kitty_specs.mkdir()
    (kitty_specs / "001-alpha-feature").mkdir()
    (kitty_specs / "002-beta-feature").mkdir()

    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))

    with pytest.raises(ValueError) as exc_info:
        require_explicit_feature(None)
    assert "001-alpha-feature" in str(exc_info.value)


def test_require_explicit_feature_raises_for_empty_string() -> None:
    """Empty string is treated the same as None."""
    with pytest.raises(ValueError):
        require_explicit_feature("")


def test_require_explicit_feature_returns_stripped_slug() -> None:
    """A valid slug is returned stripped."""
    result = require_explicit_feature("  065-my-feature  ")
    assert result == "065-my-feature"
