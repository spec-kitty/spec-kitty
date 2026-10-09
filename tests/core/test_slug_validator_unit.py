"""Unit tests for slug validator in mission_creation.py (FR-017, FR-018, FR-019)."""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.core.mission_creation import KEBAB_CASE_PATTERN, MissionCreationError
from tests._factories import provision_test_charter


pytestmark = [pytest.mark.unit, pytest.mark.fast]


class TestKebabCasePattern:
    """Test the KEBAB_CASE_PATTERN regex directly."""

    @pytest.mark.parametrize(
        "slug",
        [
            "user-auth",  # letter-prefix (existing, must keep working)
            "fix-bug-123",  # letter-prefix with numbers
            "new-dashboard",  # multi-word
            "068-feature-name",  # digit-prefix (the fix)
            "001-foo",  # digit-prefix short
            "069-planning-pipeline-integrity",  # real spec-kitty slug
            "123",  # bare digit (intentionally permissive)
            "a",  # single letter
            "1",  # single digit
        ],
    )
    def test_valid_slugs(self, slug: str) -> None:
        assert KEBAB_CASE_PATTERN.match(slug) is not None, f"Expected {slug!r} to match"

    @pytest.mark.parametrize(
        "slug",
        [
            "",  # empty (FR-019)
            "User-Auth",  # uppercase (FR-018)
            "user_auth",  # underscore (FR-018)
            "user auth",  # space (FR-018)
            "-starts-with-hyphen",  # leading hyphen
            "ends-with-",  # trailing hyphen
            "double--hyphen",  # double hyphen
            "UPPER",  # all uppercase
        ],
    )
    def test_invalid_slugs(self, slug: str) -> None:
        assert KEBAB_CASE_PATTERN.match(slug) is None, f"Expected {slug!r} to NOT match"


class TestCreateMissionCoreSlugValidation:
    """Integration-level test through create_mission_core() entry point."""

    @staticmethod
    def _mission_summary(slug: str) -> dict[str, str]:
        title = slug.replace("-", " ").strip() or "test mission"
        return {
            "friendly_name": title.title(),
            "purpose_tldr": f"Deliver {title} cleanly for the team.",
            "purpose_context": (f"This mission delivers {title} so product and engineering can move forward with a clear outcome and shared understanding."),
        }

    @pytest.mark.git_repo
    def test_digit_prefix_slug_accepted(self, temp_repo: Path) -> None:
        """FR-017: digit-prefixed slug reaches creation through real git preflight."""
        from specify_cli.core.mission_creation import create_mission_core

        provision_test_charter(temp_repo)
        result = create_mission_core(
            repo_root=temp_repo,
            mission_slug="070-new-feature",
            allow_worktree_context=True,
            **self._mission_summary("070-new-feature"),
        )
        assert result is not None
        # The NNN- prefix is dropped and the real mint's mid8 names the mission.
        assert result.mission_slug == f"new-feature-{result.meta['mission_id'][:8]}"

    def test_uppercase_slug_still_rejected(self, tmp_path: Path) -> None:
        """FR-018: uppercase slugs are still rejected by slug validation."""
        from specify_cli.core.mission_creation import create_mission_core

        with pytest.raises(MissionCreationError, match="Invalid mission slug"):
            create_mission_core(
                repo_root=tmp_path,
                mission_slug="User-Auth",
                **self._mission_summary("User-Auth"),
            )

    def test_underscore_slug_still_rejected(self, tmp_path: Path) -> None:
        """FR-018: slugs with underscores are still rejected."""
        from specify_cli.core.mission_creation import create_mission_core

        with pytest.raises(MissionCreationError, match="Invalid mission slug"):
            create_mission_core(
                repo_root=tmp_path,
                mission_slug="user_auth",
                **self._mission_summary("user_auth"),
            )

    def test_error_message_contains_digit_prefix_example(self, tmp_path: Path) -> None:
        """T036: error message includes a digit-prefix valid example."""
        from specify_cli.core.mission_creation import create_mission_core

        with pytest.raises(MissionCreationError) as exc_info:
            create_mission_core(
                repo_root=tmp_path,
                mission_slug="User-Auth",
                **self._mission_summary("User-Auth"),
            )

        error_text = str(exc_info.value)
        assert "068-feature-name" in error_text, "Error message should include digit-prefix example"
        assert "starts with number" not in error_text, "Error message should not mention 'starts with number'"
