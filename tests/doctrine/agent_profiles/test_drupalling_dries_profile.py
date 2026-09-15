"""WP01/T004 — failing verification for the drupalling-dries agent profile.

Mission ``drupalling-dries-profile-01M28X69``. This is the RED half of
red-first discipline (CLAUDE.md, DIRECTIVE_030): the profile does not exist
yet, so every positive-case assertion below must fail *now* with a clean
"profile not found"-shaped absence, never with an import or collection
error -- an erroring test proves nothing.

Covers contract C-P1 (``contracts/profile-contract.md``): the profile loads,
is selectable, is not skipped, has role ``implementer`` and declares
``php`` in ``applies_to_languages``. The negative clause is the guard that
makes C-P1 non-vacuous: FR-013 is about load failure being *observable*, so
a happy-path-only test would pass against a loader that silently swallows
everything. That half uses a fixture copy -- never the shipped pack -- per
the WP01 prompt's explicit prohibition on mutating shipped content.

Fixture/loading idiom follows ``tests/doctrine/agent_profiles/
test_profile_resolution.py`` and ``tests/doctrine/test_profile_diagnostics.py``
(the real ``AgentProfileRepository`` loading pipeline, not a raw YAML read).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.agent_profiles.repository import AgentProfileRepository

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]

_PROFILE_ID = "drupalling-dries"


# ---------------------------------------------------------------------------
# C-P1 positive clause -- the shipped profile loads and is selectable.
# ---------------------------------------------------------------------------


class TestDrupallingDriesProfileLoads:
    """The real shipped built-in pack, loaded through the production seam."""

    @pytest.fixture(scope="class")
    def repo(self) -> AgentProfileRepository:
        # Arrange: no built_in_dir override -- the same shipped-pack seam
        # tests/doctrine/test_shipped_profiles.py's peers use.
        return AgentProfileRepository()

    def test_profile_is_present(self, repo: AgentProfileRepository) -> None:
        # Assumption-check: the artifact does not exist on disk yet (WP02
        # ships it), so this must fail for absence, not error.
        profile = repo.get(_PROFILE_ID)

        # Act: get() is itself the action under test -- no further step.

        # Assert
        assert profile is not None, f"profile {_PROFILE_ID!r} not found"

    def test_profile_is_not_skipped(self, repo: AgentProfileRepository) -> None:
        # Arrange / Assumption-check: none beyond the shared fixture.
        # Act
        skipped_ids = {s.profile_id for s in repo.skipped_profiles()}
        # Assert
        assert _PROFILE_ID not in skipped_ids

    def test_profile_role_includes_implementer(self, repo: AgentProfileRepository) -> None:
        # Arrange
        profile = repo.get(_PROFILE_ID)
        # Assumption-check
        assert profile is not None, f"profile {_PROFILE_ID!r} not found"
        # Act
        role_values = {str(role) for role in profile.roles}
        # Assert
        assert "implementer" in role_values

    def test_profile_applies_to_php(self, repo: AgentProfileRepository) -> None:
        # Arrange
        profile = repo.get(_PROFILE_ID)
        # Assumption-check
        assert profile is not None, f"profile {_PROFILE_ID!r} not found"
        # Act
        languages = profile.applies_to_languages
        # Assert
        assert "php" in languages, f"expected 'php' in applies_to_languages, got {languages}"

    def test_doctor_doctrine_reports_zero_skipped_profiles(self, repo: AgentProfileRepository) -> None:
        """NFR-002: the shipped pack has no skipped profiles, drupalling-dries included."""
        # Arrange / Act
        skipped = repo.skipped_profiles()
        # Assert
        assert skipped == [], f"expected zero skipped profiles, got {skipped}"


# ---------------------------------------------------------------------------
# C-P1 negative clause -- a broken profile is observable, never swallowed.
#
# FR-013 is about failure being *visible*. Uses a fixture copy under
# tmp_path -- the shipped pack is never mutated.
# ---------------------------------------------------------------------------


class TestMalformedProfileIsObservable:
    def test_malformed_profile_appears_in_skipped_profiles(self, tmp_path: Path) -> None:
        # Arrange: a deliberately malformed profile in an isolated fixture dir.
        built_in = tmp_path / "built-in"
        built_in.mkdir()
        (built_in / "good.agent.yaml").write_text(
            "profile-id: good\nname: Good\nroles:\n  - implementer\npurpose: a valid fixture profile\nspecialization:\n  primary-focus: fixture work\n",
            encoding="utf-8",
        )
        (built_in / "broken-drupalling-dries.agent.yaml").write_text("this: is: not: valid: yaml: {", encoding="utf-8")

        # Assumption-check: two files on disk, one deliberately unparseable.
        assert len(list(built_in.glob("*.agent.yaml"))) == 2

        # Act
        repo = AgentProfileRepository(built_in_dir=built_in, project_dir=None)
        skipped = repo.skipped_profiles()
        loaded = repo.list_all()

        # Assert: the malformed file is recorded, not silently dropped, and
        # the loader still surfaces the valid sibling.
        assert len(skipped) == 1
        assert skipped[0].layer == "builtin"
        assert skipped[0].error_summary
        assert [p.profile_id for p in loaded] == ["good"]

    def test_malformed_pack_is_not_reported_healthy(self, tmp_path: Path) -> None:
        # Arrange: same fixture shape as above, isolated per-test.
        built_in = tmp_path / "built-in"
        built_in.mkdir()
        (built_in / "good.agent.yaml").write_text(
            "profile-id: good\nname: Good\nroles:\n  - implementer\npurpose: a valid fixture profile\nspecialization:\n  primary-focus: fixture work\n",
            encoding="utf-8",
        )
        (built_in / "broken-drupalling-dries.agent.yaml").write_text("this: is: not: valid: yaml: {", encoding="utf-8")

        # Assumption-check
        repo = AgentProfileRepository(built_in_dir=built_in, project_dir=None)
        skipped = repo.skipped_profiles()
        assert skipped, "fixture sanity: expected at least one skipped profile"

        # Act: derive health the same way ``doctor doctrine`` does (I-H1,
        # src/specify_cli/cli/commands/_doctrine_health.py) --
        # healthy iff every discovered profile loaded AND no invalid diagnostics.
        from specify_cli.cli.commands._doctrine_health import build_pack_health_by_layer

        packs = build_pack_health_by_layer(
            provenance_by_layer={"builtin": len(repo.list_all())},
            skipped_profiles=skipped,
        )

        # Assert
        builtin_pack = next(pack for pack in packs if pack.layer == "builtin")
        assert builtin_pack.healthy is False, "a pack with an invalid profile must never be reported healthy, even though the one valid profile loaded correctly"
