"""Tests for ``ProtectionPolicy.is_protected_target`` (WP08 / #5100 T034).

Coverage map (per the #5100 operator decision, option E, "primary plus
configured" -- research.md R-5):

* a primary branch named ``trunk`` with no ``origin/HEAD`` -- unprotected
  under ``is_protected`` alone (no default union, no configured entry), but
  protected under ``is_protected_target`` (the primary-branch arm);
* a configured ``[release]`` list still protects the primary branch (the
  configured list REPLACES the defaults for ``is_protected``, but
  ``is_protected_target`` adds the primary branch back unconditionally);
* an explicit empty ``[]`` configured list still protects the primary branch,
  for the same reason;
* an unrelated feature branch is never protected by either method;
* the operator hatch (``SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS``) disables
  ``is_protected_target`` exactly as it disables ``is_protected`` (#1828
  hatch-symmetry).

All tests use ``tmp_path`` -- no mocks, no network. Hermetic git repos are
created where a ``.kittify/config.yaml`` needs to be read from disk.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.git.protection_policy import ProtectionPolicy


pytestmark = pytest.mark.git_repo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_kittify_config(repo: Path, content: str) -> None:
    """Write ``.kittify/config.yaml`` to *repo* with the given YAML *content*."""
    kittify = repo / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(content, encoding="utf-8")


def _build_git_repo(base: Path, *, branch: str = "trunk") -> Path:
    """Initialise a bare-minimum git repo under *base* and return its root."""
    repo = base / "repo"
    repo.mkdir(parents=True)

    def _git(*args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=repo,
            check=True,
            capture_output=True,
        )

    _git("init", "--initial-branch", branch)
    _git("config", "user.email", "test@example.com")
    _git("config", "user.name", "Test User")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    _git("add", "README.md")
    _git("commit", "-m", "initial commit")
    return repo


# ---------------------------------------------------------------------------
# Case 1: primary `trunk`, no origin/HEAD, no config -- unprotected under
# is_protected alone, PROTECTED under is_protected_target.
# ---------------------------------------------------------------------------


def test_primary_branch_with_no_origin_head_protected_as_target(tmp_path: Path) -> None:
    repo = _build_git_repo(tmp_path, branch="trunk")
    policy = ProtectionPolicy.resolve(repo)

    # Control: is_protected alone does NOT protect a non-default-named
    # primary with no origin/HEAD (research.md R-5's documented gap).
    assert policy.is_protected("trunk") is False

    # is_protected_target closes the gap: the primary branch is always
    # protected under the #5100 "primary plus configured" rule.
    assert policy.is_protected_target("trunk", primary_branch="trunk") is True


def test_primary_branch_argument_mismatch_is_not_protected(tmp_path: Path) -> None:
    """A branch that is NOT the caller-supplied primary_branch, and not
    configured, stays unprotected -- the primary arm is exact-match only."""
    repo = _build_git_repo(tmp_path, branch="trunk")
    policy = ProtectionPolicy.resolve(repo)

    assert policy.is_protected_target("trunk", primary_branch="main") is False


# ---------------------------------------------------------------------------
# Case 2: configured `[release]` still protects the primary branch.
# ---------------------------------------------------------------------------


def test_configured_list_still_protects_primary(tmp_path: Path) -> None:
    repo = _build_git_repo(tmp_path, branch="trunk")
    _write_kittify_config(
        repo,
        "protection:\n  protected_branches:\n    - release\n",
    )
    policy = ProtectionPolicy.resolve(repo)

    # Control: the configured list REPLACES the defaults -- trunk is not in
    # it, so is_protected alone says unprotected.
    assert policy.is_protected("trunk") is False
    assert policy.is_protected("release") is True

    # is_protected_target: trunk (the primary) is still protected, and the
    # configured entry stays protected too.
    assert policy.is_protected_target("trunk", primary_branch="trunk") is True
    assert policy.is_protected_target("release", primary_branch="trunk") is True
    # An unrelated branch, present in neither the config nor as primary, is
    # not protected.
    assert policy.is_protected_target("feature-x", primary_branch="trunk") is False


# ---------------------------------------------------------------------------
# Case 3: explicit `[]` still protects the primary branch.
# ---------------------------------------------------------------------------


def test_empty_configured_list_still_protects_primary(tmp_path: Path) -> None:
    repo = _build_git_repo(tmp_path, branch="main")
    _write_kittify_config(repo, "protection:\n  protected_branches: []\n")
    policy = ProtectionPolicy.resolve(repo)

    # Control: an explicit empty list opts out of ALL protection under
    # is_protected alone (contracts/protection-config.md row 3).
    assert policy.is_protected("main") is False

    # is_protected_target still protects the primary branch unconditionally.
    assert policy.is_protected_target("main", primary_branch="main") is True


# ---------------------------------------------------------------------------
# Case 4: an unrelated feature branch is never protected.
# ---------------------------------------------------------------------------


def test_unrelated_feature_branch_is_not_protected(tmp_path: Path) -> None:
    repo = _build_git_repo(tmp_path, branch="main")
    policy = ProtectionPolicy.resolve(repo)

    assert policy.is_protected_target("issue-123-my-feature", primary_branch="main") is False


# ---------------------------------------------------------------------------
# Hatch symmetry (#1828-style): the operator hatch disables is_protected_target
# exactly as it disables is_protected.
# ---------------------------------------------------------------------------


def test_operator_hatch_disables_protected_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _build_git_repo(tmp_path, branch="main")
    monkeypatch.setenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", "1")
    policy = ProtectionPolicy.resolve(repo)

    assert policy.is_protected("main") is False
    assert policy.is_protected_target("main", primary_branch="main") is False
