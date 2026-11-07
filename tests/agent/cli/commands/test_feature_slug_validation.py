"""Scope: CLI integration tests for feature slug kebab-case validation — real git subprocess."""

import subprocess
import pytest
from typer.testing import CliRunner
from specify_cli.cli.commands.agent.mission import app

pytestmark = pytest.mark.git_repo

runner = CliRunner()


def test_mission_slug_with_spaces_rejected():
    """Feature slugs with spaces should be rejected."""
    # Arrange
    slug = "Invalid Feature Name"
    # Assumption check
    assert " " in slug
    # Act
    result = runner.invoke(app, ["create", slug, "--json"])
    # Assert
    assert result.exit_code != 0, "Should reject slug with spaces"
    output = result.stdout
    assert "kebab-case" in output.lower(), "Error should mention kebab-case requirement"
    assert "examples:" in output.lower() or "example" in output.lower(), "Should show examples"


def test_mission_slug_with_underscores_rejected():
    """Feature slugs with underscores should be rejected."""
    # Arrange
    slug = "user_authentication"
    # Assumption check
    assert "_" in slug
    # Act
    result = runner.invoke(app, ["create", slug, "--json"])
    # Assert
    assert result.exit_code != 0, "Should reject slug with underscores"
    assert "kebab-case" in result.stdout.lower()


def test_mission_slug_starting_with_number_accepted(tmp_path, monkeypatch):
    """Feature slugs may start with a digit (e.g. '068-feature-name' convention)."""
    # Arrange — digit-prefix slugs are now valid per FR-017
    slug = "123-test-feature"
    # Assumption check
    assert slug[0].isdigit()
    # Run outside the repository so this acceptance check cannot create and commit
    # a real test mission in the shared checkout.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    # The slug itself is valid; the CLI may reject for other reasons (not in a git repo,
    # worktree context, etc.) but NOT for the slug format.
    result = runner.invoke(app, ["create", slug, "--json"])
    # Assert: error must NOT be about the slug format
    assert "Invalid feature slug" not in result.stdout, (
        "Digit-prefixed slug '123-test-feature' must no longer be rejected for slug format"
    )


def test_mission_slug_with_uppercase_rejected():
    """Feature slugs must be lowercase only."""
    # Arrange
    slug = "UserAuth"
    # Assumption check
    assert any(c.isupper() for c in slug)
    # Act
    result = runner.invoke(app, ["create", slug, "--json"])
    # Assert
    assert result.exit_code != 0, "Should reject slug with uppercase"
    assert "lowercase" in result.stdout.lower()


def _init_protected_main_repo(root):
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "checkout", "-b", "main"], cwd=root, check=True, capture_output=True)
    kittify_dir = root / ".kittify"
    kittify_dir.mkdir()
    (kittify_dir / "config.yaml").write_text(
        "agents:\n  available: []\nmission_type_activations:\n  - software-dev\n"
    )
    (kittify_dir / "metadata.yaml").write_text("project_name: test\n")
    (root / "kitty-specs").mkdir()
    subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=root, check=True, capture_output=True)


def test_valid_kebab_case_slugs_accepted(tmp_path, monkeypatch):
    """Valid kebab-case slugs should be accepted."""
    # The repo is created on ``main`` (protected). The operator-owned-repo escape
    # hatch is the ONE sanctioned waiver (#3673 made the protected-branch refusal
    # fail loud rather than the pre-fix contextlib.suppress that let create
    # silently no-op).
    monkeypatch.setenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", "1")
    valid_slugs = ["user-auth", "fix-bug-123", "new-dashboard", "a", "test-feature-2"]
    # Act / Assert. Each slug gets its own repository: since #7276/#7282 (ADR
    # 2026-11-06-3) a default create checks out its Mission topic branch and
    # leaves the spec scaffold uncommitted, so a second create in the same write
    # checkout refuses WRITE_CHECKOUT_DIRTY (#5676) -- unrelated to slug grammar.
    for index, slug in enumerate(valid_slugs):
        repo = tmp_path / f"repo-{index}"
        _init_protected_main_repo(repo)
        monkeypatch.chdir(repo)
        result = runner.invoke(app, ["create", slug, "--json"])
        assert result.exit_code == 0, f"Valid slug '{slug}' should be accepted. Output: {result.stdout}"


# TODO(conventions): retrofit remaining test bodies
