"""Slice F WP09 — monorepo CharterScope integration tests.

ATDD anchors per atdd-coverage.md:
  - Scenario 2 (happy path): test_nearest_enclosing_charter_resolves_from_deep_subdirectory
  - Scenario 2 (exception path): test_malformed_monorepo_config_reports_conflicting_paths
  - AC-3 (single-project byte-stability): test_default_scope_is_byte_identical_to_today

covers: Scenario 2, Scenario 2 exception, AC-3 — expected GREEN at: WP09 final commit
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration]

import yaml


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_monorepo(tmp_path: Path) -> Path:
    """Build a monorepo layout with two well-formed charter scopes.

    Layout:
        <tmp>/
          .kittify/
            config.yaml          # charter_scopes: [packages/auth, packages/web]
            charter/             # default root charter (unused after resolve)
          packages/
            auth/.kittify/charter/charter.md
            auth/some/deep/dir/
            web/.kittify/charter/charter.md
    """
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "charter").mkdir()

    config = {
        "charter_scopes": [
            {"root": "packages/auth", "name": "auth"},
            {"root": "packages/web", "name": "web"},
        ]
    }
    (tmp_path / ".kittify" / "config.yaml").write_text(yaml.safe_dump(config))

    auth_root = tmp_path / "packages" / "auth"
    (auth_root / ".kittify" / "charter").mkdir(parents=True)
    (auth_root / ".kittify" / "charter" / "charter.md").write_text(
        "# Auth charter\n"
    )
    (auth_root / "some" / "deep" / "dir").mkdir(parents=True)

    web_root = tmp_path / "packages" / "web"
    (web_root / ".kittify" / "charter").mkdir(parents=True)
    (web_root / ".kittify" / "charter" / "charter.md").write_text("# Web charter\n")

    return tmp_path


@pytest.fixture
def tmp_malformed_monorepo(tmp_path: Path) -> Path:
    """Build a malformed monorepo: two scopes at incompatible nesting depths.

    `packages/auth` is configured AND `packages/auth/sub` is configured.
    Any feature_dir under packages/auth/sub/... is ambiguous: both scopes
    claim it.
    """
    (tmp_path / ".kittify").mkdir()

    config = {
        "charter_scopes": [
            {"root": "packages/auth", "name": "auth"},
            {"root": "packages/auth/sub", "name": "auth-sub"},
        ]
    }
    (tmp_path / ".kittify" / "config.yaml").write_text(yaml.safe_dump(config))

    (tmp_path / "packages" / "auth" / "sub").mkdir(parents=True)
    (tmp_path / "packages" / "ambiguous" / "deep").mkdir(parents=True)

    return tmp_path


@pytest.fixture
def tmp_single_project(tmp_path: Path) -> Path:
    """Build a single-project repo with NO charter_scopes config.

    This is the NFR-001 byte-stability path.
    """
    (tmp_path / ".kittify").mkdir()
    # No config.yaml; the absence is itself the signal for default scope.
    return tmp_path


# ---------------------------------------------------------------------------
# Scenario 2 — Monorepo charter scoping (happy path)
# ---------------------------------------------------------------------------


def test_nearest_enclosing_charter_resolves_from_deep_subdirectory(
    tmp_monorepo: Path,
) -> None:
    """From packages/auth/some/deep/dir/, scope resolves to packages/auth."""
    from charter.activation.scope import CharterScope

    feature_dir = tmp_monorepo / "packages" / "auth" / "some" / "deep" / "dir"
    scope = CharterScope.resolve(tmp_monorepo, feature_dir)

    assert scope.name == "auth"
    assert scope.root == (tmp_monorepo / "packages" / "auth").resolve()
    assert scope.config_source == "monorepo_config"


def test_resolve_distinguishes_sibling_scopes(tmp_monorepo: Path) -> None:
    """Sibling scopes (auth, web) are correctly disambiguated by feature_dir."""
    from charter.activation.scope import CharterScope

    web_feature = tmp_monorepo / "packages" / "web"
    scope = CharterScope.resolve(tmp_monorepo, web_feature)

    assert scope.name == "web"
    assert scope.root == (tmp_monorepo / "packages" / "web").resolve()


# ---------------------------------------------------------------------------
# Scenario 2 — Monorepo charter scoping (exception path)
# ---------------------------------------------------------------------------


def test_malformed_monorepo_config_reports_conflicting_paths(
    tmp_malformed_monorepo: Path,
) -> None:
    """Two scopes at incompatible nesting depths raise CharterScopeConflict
    naming both offending paths."""
    from charter.activation.scope import CharterScope, CharterScopeConflict

    feature_dir = tmp_malformed_monorepo / "packages" / "auth" / "sub"

    with pytest.raises(CharterScopeConflict) as exc_info:
        CharterScope.resolve(tmp_malformed_monorepo, feature_dir)

    message = str(exc_info.value)
    assert "packages/auth" in message
    assert "packages/auth/sub" in message


# ---------------------------------------------------------------------------
# AC-3 — Single-project repos behave identically
# ---------------------------------------------------------------------------


def test_default_scope_is_byte_identical_to_today(tmp_single_project: Path) -> None:
    """NFR-001: single-project repos (no charter_scopes:) take the default
    path and produce a CharterScope with config_source == 'repo_root_default'.
    """
    from charter.activation.scope import CharterScope

    scope = CharterScope.resolve(tmp_single_project, tmp_single_project)

    assert scope.config_source == "repo_root_default"
    assert scope.root == tmp_single_project
    assert scope.name is None


def test_default_scope_matches_explicit_default_constructor(
    tmp_single_project: Path,
) -> None:
    """CharterScope.resolve(no-config) returns the same shape as
    CharterScope.default(repo_root) — verifies the byte-stable invariant."""
    from charter.activation.scope import CharterScope

    resolved = CharterScope.resolve(tmp_single_project, tmp_single_project)
    default = CharterScope.default(tmp_single_project)

    assert resolved == default
