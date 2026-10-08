"""Scope: git ops integration tests — creates real git repositories."""

import subprocess
from pathlib import Path

import pytest

from specify_cli.core.git_ops import (
    exclude_from_git_index,
    get_current_branch,
    has_remote,
    is_git_repo,
    resolve_primary_branch,
    resolve_target_branch,
    run_command,
)
from specify_cli.core.paths import MissionMetaReadError

pytestmark = pytest.mark.git_repo


# ============================================================================
# get_current_branch tests (Bug 1: unborn branch / detached HEAD)
# ============================================================================


@pytest.mark.usefixtures("_git_identity")
def test_get_current_branch_unborn(tmp_path):
    """get_current_branch returns branch name for a fresh repo with no commits."""
    repo = tmp_path / "repo"
    repo.mkdir()
    run_command(["git", "init", "--initial-branch=main"], cwd=repo)
    # No commits — unborn branch
    branch = get_current_branch(repo)
    assert branch == "main"


@pytest.mark.usefixtures("_git_identity")
def test_get_current_branch_detached_head(tmp_path):
    """get_current_branch returns None for detached HEAD."""
    repo = tmp_path / "repo"
    repo.mkdir()
    run_command(["git", "init", "--initial-branch=main"], cwd=repo)
    (repo / "file.txt").write_text("hello", encoding="utf-8")
    run_command(["git", "add", "."], cwd=repo)
    run_command(["git", "commit", "-m", "Initial"], cwd=repo)
    run_command(["git", "checkout", "--detach"], cwd=repo)

    branch = get_current_branch(repo)
    assert branch is None


@pytest.mark.usefixtures("_git_identity")
def test_get_current_branch_normal(tmp_path):
    """get_current_branch returns branch name for normal branch with commits."""
    repo = tmp_path / "repo"
    repo.mkdir()
    run_command(["git", "init", "--initial-branch=develop"], cwd=repo)
    (repo / "file.txt").write_text("hello", encoding="utf-8")
    run_command(["git", "add", "."], cwd=repo)
    run_command(["git", "commit", "-m", "Initial"], cwd=repo)

    branch = get_current_branch(repo)
    assert branch == "develop"


@pytest.mark.usefixtures("_git_identity")
def test_git_repo_lifecycle(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "README.md").write_text("hello", encoding="utf-8")

    assert is_git_repo(project) is False
    subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "add", "--", "README.md"], cwd=project, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-m", "Initial commit", "--", "README.md"],
        cwd=project,
        check=True,
        capture_output=True,
    )
    assert is_git_repo(project) is True

    branch = get_current_branch(project)
    assert branch


@pytest.fixture(name="_git_identity")
def git_identity_fixture(monkeypatch):
    """Ensure git commands can commit even if the user has no global config."""
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Spec Kitty")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "spec@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Spec Kitty")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "spec@example.com")


@pytest.mark.usefixtures("_git_identity")
def test_has_remote_with_origin(tmp_path):
    """Test has_remote returns True when origin exists."""
    # Setup git repo with remote
    repo = tmp_path / "repo"
    repo.mkdir()
    run_command(["git", "init"], cwd=repo)
    run_command(["git", "remote", "add", "origin", "https://example.com/repo.git"], cwd=repo)

    assert has_remote(repo) is True


@pytest.mark.usefixtures("_git_identity")
def test_has_remote_without_origin(tmp_path):
    """Test has_remote returns False when no remote exists."""
    # Setup git repo without remote
    repo = tmp_path / "repo"
    repo.mkdir()
    run_command(["git", "init"], cwd=repo)

    assert has_remote(repo) is False


@pytest.mark.usefixtures("_git_identity")
def test_exclude_from_git_index(tmp_path):
    """Test exclude_from_git_index adds patterns to .git/info/exclude."""
    # Setup git repo
    repo = tmp_path / "repo"
    repo.mkdir()
    run_command(["git", "init"], cwd=repo)

    # Add exclusions
    exclude_from_git_index(repo, [".worktrees/", ".build/"])

    # Verify exclusions were added
    exclude_file = repo / ".git" / "info" / "exclude"
    content = exclude_file.read_text()
    assert ".worktrees/" in content
    assert ".build/" in content
    assert "# Added by spec-kitty" in content


@pytest.mark.usefixtures("_git_identity")
def test_exclude_from_git_index_duplicate(tmp_path):
    """Test exclude_from_git_index doesn't duplicate existing patterns."""
    # Setup git repo
    repo = tmp_path / "repo"
    repo.mkdir()
    run_command(["git", "init"], cwd=repo)

    # Add exclusions twice
    exclude_from_git_index(repo, [".worktrees/"])
    exclude_from_git_index(repo, [".worktrees/"])

    # Verify pattern appears only once
    exclude_file = repo / ".git" / "info" / "exclude"
    content = exclude_file.read_text()
    assert content.count(".worktrees/") == 1


@pytest.mark.usefixtures("_git_identity")
def test_resolve_target_branch_branches_match(tmp_path):
    """Test T032: resolve_target_branch when current == target."""
    import json

    # Setup repo
    repo = tmp_path / "repo"
    repo.mkdir()
    run_command(["git", "init"], cwd=repo)

    (repo / "README.md").write_text("test", encoding="utf-8")
    run_command(["git", "add", "."], cwd=repo)
    run_command(["git", "commit", "-m", "Initial"], cwd=repo)

    # Create feature targeting main
    feature_dir = repo / "kitty-specs" / "001-test"
    feature_dir.mkdir(parents=True)
    meta = {"feature_id": "001-test", "target_branch": "main"}
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    # Resolve from main to main
    resolution = resolve_target_branch("001-test", repo, "main", respect_current=True)

    assert resolution.target == "main"
    assert resolution.current == "main"
    assert resolution.should_notify is False
    assert resolution.action == "proceed"


@pytest.mark.usefixtures("_git_identity")
def test_resolve_target_branch_branches_differ_respect_current(tmp_path):
    """Test T033: resolve_target_branch when current != target with respect_current=True."""
    import json

    # Setup repo
    repo = tmp_path / "repo"
    repo.mkdir()
    run_command(["git", "init"], cwd=repo)

    (repo / "README.md").write_text("test", encoding="utf-8")
    run_command(["git", "add", "."], cwd=repo)
    run_command(["git", "commit", "-m", "Initial"], cwd=repo)

    # Create develop branch
    run_command(["git", "checkout", "-b", "develop"], cwd=repo)

    # Create feature targeting main
    feature_dir = repo / "kitty-specs" / "002-test"
    feature_dir.mkdir(parents=True)
    meta = {"feature_id": "002-test", "target_branch": "main"}
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    # Resolve from develop (current) when target is main
    resolution = resolve_target_branch("002-test", repo, "develop", respect_current=True)

    assert resolution.target == "main"
    assert resolution.current == "develop"
    assert resolution.should_notify is True  # Branches differ
    assert resolution.action == "stay_on_current"


@pytest.mark.usefixtures("_git_identity")
def test_resolve_target_branch_fallback_to_main(tmp_path):
    """Test T034: resolve_target_branch fallbacks to 'main' when meta.json missing."""
    # Setup repo with explicit main branch (CI may default to master)
    repo = tmp_path / "repo"
    repo.mkdir()
    run_command(["git", "init", "--initial-branch=main"], cwd=repo)

    (repo / "README.md").write_text("test", encoding="utf-8")
    run_command(["git", "add", "."], cwd=repo)
    run_command(["git", "commit", "-m", "Initial"], cwd=repo)

    # Create feature WITHOUT meta.json
    feature_dir = repo / "kitty-specs" / "003-test"
    feature_dir.mkdir(parents=True)

    # Resolve should fallback to "main"
    resolution = resolve_target_branch("003-test", repo, "main", respect_current=True)

    assert resolution.target == "main"  # Fallback
    assert resolution.current == "main"
    assert resolution.should_notify is False
    assert resolution.action == "proceed"


@pytest.mark.usefixtures("_git_identity")
def test_resolve_target_branch_auto_detect_current(tmp_path):
    """Test T035: resolve_target_branch auto-detects current branch when not provided."""
    import json

    # Setup repo
    repo = tmp_path / "repo"
    repo.mkdir()
    run_command(["git", "init"], cwd=repo)

    (repo / "README.md").write_text("test", encoding="utf-8")
    run_command(["git", "add", "."], cwd=repo)
    run_command(["git", "commit", "-m", "Initial"], cwd=repo)

    # Create develop branch
    run_command(["git", "checkout", "-b", "develop"], cwd=repo)

    # Create feature targeting main
    feature_dir = repo / "kitty-specs" / "004-test"
    feature_dir.mkdir(parents=True)
    meta = {"feature_id": "004-test", "target_branch": "main"}
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    # Resolve WITHOUT providing current_branch (should auto-detect)
    resolution = resolve_target_branch("004-test", repo, current_branch=None, respect_current=True)

    assert resolution.current == "develop"  # Auto-detected
    assert resolution.target == "main"
    assert resolution.should_notify is True
    assert resolution.action == "stay_on_current"


@pytest.mark.usefixtures("_git_identity")
def test_resolve_target_branch_invalid_meta_json_fails_closed(tmp_path):
    """Test T036: resolve_target_branch raises MissionMetaReadError on corrupt meta.json (FR-005)."""
    # Setup repo with explicit main branch (CI may default to master)
    repo = tmp_path / "repo"
    repo.mkdir()
    run_command(["git", "init", "--initial-branch=main"], cwd=repo)

    (repo / "README.md").write_text("test", encoding="utf-8")
    run_command(["git", "add", "."], cwd=repo)
    run_command(["git", "commit", "-m", "Initial"], cwd=repo)

    # Create feature with INVALID meta.json
    feature_dir = repo / "kitty-specs" / "005-test"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text("{ invalid json }", encoding="utf-8")

    # Corrupt meta.json must fail closed — not silently fall back
    with pytest.raises(MissionMetaReadError):
        resolve_target_branch("005-test", repo, "main", respect_current=True)


# ============================================================================
# resolve_primary_branch tests
# ============================================================================


def _init_repo_with_branch(path: Path, branch_name: str) -> Path:
    """Helper: create a git repo whose initial branch is `branch_name`."""
    repo = path / "repo"
    repo.mkdir()
    run_command(["git", "init", f"--initial-branch={branch_name}"], cwd=repo)
    (repo / "README.md").write_text("init", encoding="utf-8")
    run_command(["git", "add", "."], cwd=repo)
    run_command(["git", "commit", "-m", "Initial"], cwd=repo)
    return repo


@pytest.mark.usefixtures("_git_identity")
def test_resolve_primary_branch_detects_main(tmp_path):
    """resolve_primary_branch returns 'main' for a standard repo."""
    repo = _init_repo_with_branch(tmp_path, "main")
    assert resolve_primary_branch(repo) == "main"


@pytest.mark.usefixtures("_git_identity")
def test_resolve_primary_branch_detects_master(tmp_path):
    """resolve_primary_branch returns 'master' when that is the only primary branch."""
    repo = _init_repo_with_branch(tmp_path, "master")
    assert resolve_primary_branch(repo) == "master"


@pytest.mark.usefixtures("_git_identity")
def test_resolve_primary_branch_detects_develop(tmp_path):
    """resolve_primary_branch returns 'develop' when that is the only branch."""
    repo = _init_repo_with_branch(tmp_path, "develop")
    assert resolve_primary_branch(repo) == "develop"


def _create_remote_with_branch(tmp_path: Path, branch_name: str) -> tuple[Path, Path]:
    """Helper: create a bare remote + clone where origin/HEAD points at branch_name.

    Returns (repo_path, bare_path).
    """
    bare = tmp_path / "bare"
    bare.mkdir()
    run_command(["git", "init", "--bare", f"--initial-branch={branch_name}"], cwd=bare)

    # Seed the bare repo so clone gets a non-empty default branch
    seed = tmp_path / "seed"
    seed.mkdir()
    run_command(["git", "init", f"--initial-branch={branch_name}"], cwd=seed)
    (seed / "README.md").write_text("init", encoding="utf-8")
    run_command(["git", "add", "."], cwd=seed)
    run_command(["git", "commit", "-m", "Initial"], cwd=seed)
    run_command(["git", "remote", "add", "origin", str(bare)], cwd=seed)
    run_command(["git", "push", "-u", "origin", branch_name], cwd=seed)

    # Now clone — origin/HEAD will be set correctly
    repo = tmp_path / "repo"
    run_command(["git", "clone", str(bare), str(repo)])
    return repo, bare


@pytest.mark.usefixtures("_git_identity")
def test_resolve_primary_branch_prefers_origin_head(tmp_path):
    """resolve_primary_branch prefers origin/HEAD over branch existence check."""
    repo, _ = _create_remote_with_branch(tmp_path, "ticket_nr_4_branch")
    assert resolve_primary_branch(repo) == "ticket_nr_4_branch"


@pytest.mark.usefixtures("_git_identity")
def test_resolve_primary_branch_custom_branch_via_origin(tmp_path):
    """resolve_primary_branch detects a completely custom branch name via origin/HEAD."""
    repo, _ = _create_remote_with_branch(tmp_path, "my-custom-trunk")
    assert resolve_primary_branch(repo) == "my-custom-trunk"


@pytest.mark.usefixtures("_git_identity")
def test_resolve_primary_branch_fallback_no_branches(tmp_path):
    """resolve_primary_branch returns current branch when no remote and no common branches."""
    # Create a repo with a non-standard branch and no remote
    repo = _init_repo_with_branch(tmp_path, "some_random_branch")

    # No origin/HEAD, but current branch is "some_random_branch" → current branch wins
    assert resolve_primary_branch(repo) == "some_random_branch"


# ============================================================================
# resolve_primary_branch: current branch wins over hardcoded list
# ============================================================================


@pytest.mark.usefixtures("_git_identity")
def test_resolve_primary_branch_detects_2x_branch(tmp_path):
    """resolve_primary_branch returns '2.x' when that's the only branch."""
    repo = _init_repo_with_branch(tmp_path, "2.x")
    assert resolve_primary_branch(repo) == "2.x"


@pytest.mark.usefixtures("_git_identity")
def test_resolve_primary_branch_detects_2x_even_when_main_exists(tmp_path):
    """resolve_primary_branch returns '2.x' when user is on 2.x, even if main also exists.

    THIS IS THE CRITICAL BUG FIX TEST — the exact scenario that was broken.
    """
    repo = _init_repo_with_branch(tmp_path, "main")
    # Create 2.x branch and switch to it
    run_command(["git", "branch", "2.x"], cwd=repo)
    run_command(["git", "checkout", "2.x"], cwd=repo)
    # Current branch is 2.x, main also exists → 2.x should win
    assert resolve_primary_branch(repo) == "2.x"


@pytest.mark.usefixtures("_git_identity")
def test_resolve_primary_branch_detects_release_branch(tmp_path):
    """resolve_primary_branch returns a release branch name."""
    repo = _init_repo_with_branch(tmp_path, "release/v3")
    assert resolve_primary_branch(repo) == "release/v3"


@pytest.mark.usefixtures("_git_identity")
def test_resolve_primary_branch_origin_head_wins_over_current(tmp_path):
    """resolve_primary_branch prefers origin/HEAD over current branch."""
    repo, _ = _create_remote_with_branch(tmp_path, "2.x")
    # Clone is on 2.x, origin/HEAD points to 2.x — create and switch to another branch
    run_command(["git", "checkout", "-b", "some-other-branch"], cwd=repo)
    # origin/HEAD should win even though current is some-other-branch
    assert resolve_primary_branch(repo) == "2.x"


@pytest.mark.usefixtures("_git_identity")
def test_resolve_primary_branch_current_branch_wins_over_hardcoded_list(tmp_path):
    """resolve_primary_branch returns current branch over hardcoded main/master/develop."""
    repo = _init_repo_with_branch(tmp_path, "2.x")
    # Also create a "main" branch (but stay on 2.x)
    run_command(["git", "branch", "main"], cwd=repo)
    # Should still return 2.x since that's where we are
    assert resolve_primary_branch(repo) == "2.x"


# ============================================================================
# resolve_primary_branch: bias / current_branch params (FR-007 fold)
#
# WP04 (primary-merge-vocabulary) folds ``_resolve_primary_branch_for_recommendation``
# into this canonical resolver via a keyword-only ``bias`` flag (and a
# ``current_branch`` override). ``test_git_ops.py`` is the canonical home for
# ``resolve_primary_branch`` behavior and is unowned by any other WP, so the new
# parameters are pinned here alongside the historical feature-bias contract.
# ============================================================================


@pytest.mark.usefixtures("_git_identity")
def test_resolve_primary_branch_bias_false_ignores_feature_branch(tmp_path):
    """FR-007 no-feature-bias: ``bias=False`` must NOT return the checked-out
    ticket branch; the common-branch ladder (main) wins instead. This is the
    deliberate divergence the branch-context recommender relies on and that the
    fold must preserve — contrasted here against the default feature bias."""
    repo = _init_repo_with_branch(tmp_path, "main")
    run_command(["git", "branch", "feat/ticket-123"], cwd=repo)
    run_command(["git", "checkout", "feat/ticket-123"], cwd=repo)
    # Default (feature bias) returns the ticket branch ...
    assert resolve_primary_branch(repo) == "feat/ticket-123"
    # ... but no-feature-bias falls through to the common ladder.
    assert resolve_primary_branch(repo, bias=False) == "main"


@pytest.mark.usefixtures("_git_identity")
def test_resolve_primary_branch_bias_false_honors_current_when_common(tmp_path):
    """``bias=False`` still honors the current branch when it is itself a common
    primary name (main/master/develop)."""
    repo = _init_repo_with_branch(tmp_path, "develop")
    assert resolve_primary_branch(repo, current_branch="develop", bias=False) == "develop"


@pytest.mark.usefixtures("_git_identity")
def test_resolve_primary_branch_accepts_explicit_current_branch(tmp_path):
    """The ``current_branch`` kwarg lets a caller pass the already-known checked-out
    branch (avoiding a second git call); with the default feature bias it wins
    exactly like the auto-detected value would."""
    repo = _init_repo_with_branch(tmp_path, "main")
    run_command(["git", "branch", "2.x"], cwd=repo)
    assert resolve_primary_branch(repo, current_branch="2.x") == "2.x"


# ============================================================================
# resolve_target_branch with non-"main" primary branch
# ============================================================================


@pytest.mark.usefixtures("_git_identity")
def test_resolve_target_branch_fallback_to_master(tmp_path):
    """When meta.json is missing and repo primary is 'master', fallback is 'master'."""

    repo = _init_repo_with_branch(tmp_path, "master")

    # Create feature WITHOUT meta.json
    feature_dir = repo / "kitty-specs" / "010-test"
    feature_dir.mkdir(parents=True)

    resolution = resolve_target_branch("010-test", repo, "master", respect_current=True)

    assert resolution.target == "master"  # Dynamic fallback, not hardcoded "main"
    assert resolution.current == "master"
    assert resolution.should_notify is False
    assert resolution.action == "proceed"


@pytest.mark.usefixtures("_git_identity")
def test_resolve_target_branch_fallback_uses_origin_head(tmp_path):
    """When meta.json has no target_branch, fallback uses origin/HEAD detection."""
    import json

    repo, _ = _create_remote_with_branch(tmp_path, "ticket_nr_4_branch")

    # Create feature with meta.json that has NO target_branch field
    feature_dir = repo / "kitty-specs" / "020-feature"
    feature_dir.mkdir(parents=True)
    meta = {"feature_number": "020", "slug": "020-feature"}
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    resolution = resolve_target_branch("020-feature", repo, "ticket_nr_4_branch", respect_current=True)

    assert resolution.target == "ticket_nr_4_branch"  # Detected from origin/HEAD
    assert resolution.should_notify is False
    assert resolution.action == "proceed"


@pytest.mark.usefixtures("_git_identity")
def test_resolve_target_branch_meta_overrides_detected_primary(tmp_path):
    """meta.json target_branch takes priority over detected primary branch."""
    import json

    repo = _init_repo_with_branch(tmp_path, "master")

    # Create feature targeting "2.x" explicitly
    feature_dir = repo / "kitty-specs" / "025-feature"
    feature_dir.mkdir(parents=True)
    meta = {"target_branch": "2.x"}
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    resolution = resolve_target_branch("025-feature", repo, "master", respect_current=True)

    assert resolution.target == "2.x"  # meta.json wins over detected "master"
    assert resolution.should_notify is True  # master != 2.x


# ============================================================================
# get_feature_target_branch with non-"main" primary
# ============================================================================


@pytest.mark.usefixtures("_git_identity")
def test_get_feature_target_branch_master_repo_no_meta(tmp_path):
    """In a master-based repo with no meta.json, fallback should be 'master'."""
    from specify_cli.core.paths import get_feature_target_branch

    repo = _init_repo_with_branch(tmp_path, "master")

    feature_dir = repo / "kitty-specs" / "010-test"
    feature_dir.mkdir(parents=True)
    # No meta.json

    target = get_feature_target_branch(repo, "010-test")
    assert target == "master"


@pytest.mark.usefixtures("_git_identity")
def test_get_feature_target_branch_custom_primary_no_meta(tmp_path):
    """In a repo with a custom primary branch and no meta.json, fallback should match."""
    from specify_cli.core.paths import get_feature_target_branch

    repo, _ = _create_remote_with_branch(tmp_path, "ticket_nr_4_branch")

    feature_dir = repo / "kitty-specs" / "010-test"
    feature_dir.mkdir(parents=True)
    # No meta.json

    target = get_feature_target_branch(repo, "010-test")
    assert target == "ticket_nr_4_branch"


@pytest.mark.usefixtures("_git_identity")
def test_get_feature_target_branch_meta_overrides_custom_primary(tmp_path):
    """meta.json target_branch wins over custom primary branch detection."""
    import json
    from specify_cli.core.paths import get_feature_target_branch

    repo = _init_repo_with_branch(tmp_path, "master")

    feature_dir = repo / "kitty-specs" / "025-test"
    feature_dir.mkdir(parents=True)
    meta = {"target_branch": "2.x"}
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    target = get_feature_target_branch(repo, "025-test")
    assert target == "2.x"  # meta.json overrides "master" detection


# ============================================================================
# Integration: manifest WorktreeStatus with non-"main" primary
# ============================================================================


@pytest.mark.usefixtures("_git_identity")
def test_manifest_merged_check_uses_detected_primary(tmp_path):
    """WorktreeStatus.get_feature_status checks --merged against detected primary branch."""
    from specify_cli.manifest import WorktreeStatus

    repo = _init_repo_with_branch(tmp_path, "master")

    # Create a feature branch and merge it into master
    run_command(["git", "checkout", "-b", "001-my-feature"], cwd=repo)
    (repo / "feature.txt").write_text("feature work", encoding="utf-8")
    run_command(["git", "add", "."], cwd=repo)
    run_command(["git", "commit", "-m", "Feature work"], cwd=repo)
    run_command(["git", "checkout", "master"], cwd=repo)
    run_command(["git", "merge", "--no-ff", "001-my-feature", "-m", "Merge feature"], cwd=repo)

    # Create kitty-specs directory so it shows up (needs a file; git ignores empty dirs)
    feature_dir = repo / "kitty-specs" / "001-my-feature"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("# Feature spec\n", encoding="utf-8")
    run_command(["git", "add", "."], cwd=repo)
    run_command(["git", "commit", "-m", "Add kitty-specs"], cwd=repo)

    ws = WorktreeStatus(repo)
    status = ws.get_feature_status("001-my-feature")

    # Feature should be detected as merged into master (not fail because "main" doesn't exist)
    assert status["branch_merged"] is True
    assert status["state"] == "merged"
