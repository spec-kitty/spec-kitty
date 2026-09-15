"""Tests for ProfileRegistry."""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.invocation.errors import ProfileNotFoundError
from specify_cli.invocation.registry import ProfileRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.unit, pytest.mark.fast]

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "profiles"


def _make_registry_with_fixtures(tmp_path: Path) -> ProfileRegistry:
    """Create a registry pointing at the test fixture profiles directory."""
    # Copy fixture files to a simulated project .kittify/profiles/ directory.
    project_profiles = tmp_path / ".kittify" / "profiles"
    project_profiles.mkdir(parents=True)
    import shutil

    for yaml_file in FIXTURES_DIR.glob("*.agent.yaml"):
        shutil.copy(yaml_file, project_profiles / yaml_file.name)
    return ProfileRegistry(tmp_path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRegistryListsShippedProfiles:
    def test_list_all_returns_profiles(self, tmp_path: Path) -> None:
        """list_all() returns at least one profile (shipped profiles always available)."""
        # Use a directory with no .kittify/profiles/ — falls back to shipped
        registry = ProfileRegistry(tmp_path)
        profiles = registry.list_all()
        # Shipped profiles always include at least 'implementer'
        assert len(profiles) >= 1

    def test_list_all_with_fixtures_returns_fixture_profiles(self, tmp_path: Path) -> None:
        registry = _make_registry_with_fixtures(tmp_path)
        profile_ids = [p.profile_id for p in registry.list_all()]
        assert "implementer-fixture" in profile_ids
        assert "reviewer-fixture" in profile_ids


class TestRegistryGet:
    def test_get_existing_profile_returns_agent_profile(self, tmp_path: Path) -> None:
        registry = _make_registry_with_fixtures(tmp_path)
        profile = registry.get("implementer-fixture")
        assert profile is not None
        assert profile.profile_id == "implementer-fixture"
        assert profile.name == "Implementer (fixture)"

    def test_get_missing_profile_returns_none(self, tmp_path: Path) -> None:
        registry = ProfileRegistry(tmp_path)
        result = registry.get("does-not-exist")
        assert result is None


class TestRegistryResolve:
    def test_resolve_missing_raises_profile_not_found_error(self, tmp_path: Path) -> None:
        registry = ProfileRegistry(tmp_path)
        with pytest.raises(ProfileNotFoundError) as exc_info:
            registry.resolve("no-such-profile")
        assert "no-such-profile" in str(exc_info.value)
        assert isinstance(exc_info.value.available, list)

    def test_resolve_existing_returns_profile(self, tmp_path: Path) -> None:
        registry = _make_registry_with_fixtures(tmp_path)
        profile = registry.resolve("reviewer-fixture")
        assert profile.profile_id == "reviewer-fixture"


class TestRegistryResolveLocal:
    """#4120/#4114: local and routing resolution admit project doctrine.

    ``resolve_local`` remains the explicit operator-facing seam for profiles
    passed to ``agent action implement/review --profile``. Since #4114, the
    dispatch routing catalog also admits the doctrine project layer, so both
    paths share the same activation gate and currently resolve the same
    project-local charter-activated profiles.
    """

    _PROJECT_PROFILE_ID = "seeker-implementer"

    @staticmethod
    def _make_project_doctrine_repo(tmp_path: Path) -> Path:
        """A repo with one charter-activated project-local doctrine profile."""
        profiles_dir = tmp_path / ".kittify" / "doctrine" / "agent_profiles"
        profiles_dir.mkdir(parents=True)
        (profiles_dir / "seeker-implementer.agent.yaml").write_text(
            "\n".join(
                [
                    "profile-id: seeker-implementer",
                    "name: 'Seeker Implementer'",
                    "role: implementer",
                    "purpose: 'Implement mission WPs'",
                    "specialization:",
                    "  primary-focus: 'Code implementation'",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (tmp_path / ".kittify" / "config.yaml").write_text(
            "activated_agent_profiles:\n  - seeker-implementer\n",
            encoding="utf-8",
        )
        return tmp_path

    def test_routing_and_local_resolve_admit_project_doctrine_profile(
        self,
        tmp_path: Path,
    ) -> None:
        """The #4114 routing expansion agrees with the #4120 local seam."""
        repo = self._make_project_doctrine_repo(tmp_path)
        registry = ProfileRegistry(repo)
        routed = registry.resolve(self._PROJECT_PROFILE_ID)
        local = registry.resolve_local(self._PROJECT_PROFILE_ID)

        assert routed.profile_id == self._PROJECT_PROFILE_ID
        assert local == routed

    def test_resolve_local_resolves_project_doctrine_profile(self, tmp_path: Path) -> None:
        repo = self._make_project_doctrine_repo(tmp_path)
        profile = ProfileRegistry(repo).resolve_local(self._PROJECT_PROFILE_ID)
        assert profile.profile_id == self._PROJECT_PROFILE_ID
        assert profile.schema_version  # the version the claim binding records

    def test_resolve_local_honours_the_activation_gate(self, tmp_path: Path) -> None:
        """A project profile NOT in ``activated_agent_profiles`` stays absent.

        ``resolve_local`` is a wider LAYER set, not a weaker gate: the same
        three-state ``activated_agent_profiles`` contract applies.
        """
        repo = self._make_project_doctrine_repo(tmp_path)
        (repo / ".kittify" / "config.yaml").write_text(
            "activated_agent_profiles:\n  - some-other-profile\n",
            encoding="utf-8",
        )
        with pytest.raises(ProfileNotFoundError):
            ProfileRegistry(repo).resolve_local(self._PROJECT_PROFILE_ID)

    def test_resolve_local_missing_names_local_catalog(self, tmp_path: Path) -> None:
        """The not-found error lists what IS locally available, never a bare []."""
        repo = self._make_project_doctrine_repo(tmp_path)
        with pytest.raises(ProfileNotFoundError) as exc_info:
            ProfileRegistry(repo).resolve_local("no-such-profile")
        assert self._PROJECT_PROFILE_ID in exc_info.value.available
        assert str(exc_info.value) == (f"Profile 'no-such-profile' not found. Available: ['{self._PROJECT_PROFILE_ID}']")

    def test_resolve_local_still_resolves_builtin_profiles(self, tmp_path: Path) -> None:
        """Routing-layer ids (built-ins) keep resolving through the local seam."""
        registry = ProfileRegistry(tmp_path)
        profile = registry.resolve_local("python-pedro")
        assert profile.profile_id == "python-pedro"


class TestRegistryFallbackNoProjectDir:
    def test_no_kittify_profiles_dir_does_not_raise(self, tmp_path: Path) -> None:
        """When .kittify/profiles/ does not exist, ProfileRegistry should not raise."""
        assert not (tmp_path / ".kittify" / "profiles").exists()
        registry = ProfileRegistry(tmp_path)
        # Should fall back to shipped profiles gracefully
        assert isinstance(registry.list_all(), list)

    def test_has_profiles_returns_true_with_shipped(self, tmp_path: Path) -> None:
        registry = ProfileRegistry(tmp_path)
        # Shipped profiles always present — has_profiles() should return True
        assert registry.has_profiles() is True
