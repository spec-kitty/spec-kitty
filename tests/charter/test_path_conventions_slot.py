"""Unit tests for the ``path_conventions`` doctrine slot (WP02, FR-004/FR-009).

These tests pin the WP02 contract for mission
``mission-type-canonical-source-01M302V9``:

* :class:`charter.offering.missions.models.MissionType` carries an optional
  ``path_conventions`` field. A mission type that declares none (``None``,
  the default) is a pure no-op for downstream consumers — not an error and
  not a fallback to another type's shape.
* :data:`charter.offering.missions.models.VALID_PATH_KEYS` is the canonical,
  charter-side home for the frozenset of valid path-convention keys
  (relocated from ``specify_cli.mission.VALID_PATH_KEYS`` — that copy is
  untouched here; WP04 retires it and repoints importers).
* :func:`charter.offering.missions.models.validate_path_conventions`
  accepts a mapping whose keys are all members of ``VALID_PATH_KEYS`` and
  raises ``ValueError`` when any key is unknown.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from charter.offering.missions.models import (
    VALID_PATH_KEYS,
    MissionType,
    validate_path_conventions,
)


pytestmark = pytest.mark.fast


class TestValidPathKeysCanonicalHome:
    """``VALID_PATH_KEYS`` is charter-canonical and matches the historical value."""

    def test_valid_path_keys_is_a_frozenset(self) -> None:
        assert isinstance(VALID_PATH_KEYS, frozenset)

    def test_valid_path_keys_matches_historical_specify_cli_value(self) -> None:
        """Pinned verbatim, and the two dual-home copies must not drift.

        ``VALID_PATH_KEYS`` is dual-homed (charter canonical + the surviving
        ``specify_cli.mission`` copy) until the #2652 convergence deletes the
        legacy one. This test imports BOTH copies and asserts they carry the
        identical value, so editing either side is caught — the ``specify_cli``
        → ``charter`` import direction is allowed, so the test may reach both.
        """
        from specify_cli.mission import VALID_PATH_KEYS as SPECIFY_CLI_VALID_PATH_KEYS

        historical = frozenset({"workspace", "tests", "deliverables", "documentation", "data"})
        assert historical == VALID_PATH_KEYS
        assert SPECIFY_CLI_VALID_PATH_KEYS == VALID_PATH_KEYS


class TestValidatePathConventionsFunction:
    """Direct unit coverage of the standalone validator (mirrors ``validate_action_sequence``)."""

    def test_none_is_a_no_op(self) -> None:
        validate_path_conventions(None)  # must not raise

    def test_empty_mapping_is_a_no_op(self) -> None:
        validate_path_conventions({})  # must not raise

    @pytest.mark.parametrize("key", sorted(VALID_PATH_KEYS))
    def test_each_valid_key_accepted_individually(self, key: str) -> None:
        validate_path_conventions({key: "some/dir"})  # must not raise

    def test_all_valid_keys_together_accepted(self) -> None:
        mapping = {key: f"path/{key}" for key in VALID_PATH_KEYS}
        validate_path_conventions(mapping)  # must not raise

    def test_unknown_key_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unknown path-convention keys"):
            validate_path_conventions({"bogus": "some/dir"})

    def test_mix_of_known_and_unknown_keys_rejected(self) -> None:
        with pytest.raises(ValueError, match="bogus"):
            validate_path_conventions({"workspace": "src/", "bogus": "x"})

    def test_error_message_names_the_unknown_key(self) -> None:
        with pytest.raises(ValueError, match=r"\['bogus'\]"):
            validate_path_conventions({"bogus": "some/dir"})


class TestMissionTypePathConventionsField:
    """``MissionType.path_conventions`` slot behaviour (FR-004)."""

    def test_defaults_to_none(self) -> None:
        mission_type = MissionType(id="software-dev", display_name="Software Development")
        assert mission_type.path_conventions is None

    def test_none_is_a_no_op_declaration(self) -> None:
        """A type declaring no conventions must not raise and must stay ``None``.

        Downstream consumers treat ``None`` as "no conventions to enforce" —
        never as "fall back to another type's path shape" (FR-004 acceptance).
        """
        mission_type = MissionType(
            id="research",
            display_name="Research",
            action_sequence=["research"],
        )
        assert mission_type.path_conventions is None

    def test_valid_path_conventions_accepted(self) -> None:
        mission_type = MissionType(
            id="software-dev",
            display_name="Software Development",
            path_conventions={"workspace": "src/", "tests": "tests/"},
        )
        assert mission_type.path_conventions == {"workspace": "src/", "tests": "tests/"}

    def test_all_valid_keys_accepted_together(self) -> None:
        mapping = {key: f"{key}/" for key in VALID_PATH_KEYS}
        mission_type = MissionType(
            id="software-dev",
            display_name="Software Development",
            path_conventions=mapping,
        )
        assert mission_type.path_conventions == mapping

    def test_unknown_path_convention_key_rejected_at_construction(self) -> None:
        with pytest.raises(ValidationError, match="Unknown path-convention keys"):
            MissionType(
                id="software-dev",
                display_name="Software Development",
                path_conventions={"not-a-real-key": "src/"},
            )

    def test_empty_mapping_accepted(self) -> None:
        mission_type = MissionType(
            id="software-dev",
            display_name="Software Development",
            path_conventions={},
        )
        assert mission_type.path_conventions == {}

    def test_model_is_frozen(self) -> None:
        mission_type = MissionType(id="software-dev", display_name="Software Development")
        with pytest.raises(ValidationError):
            mission_type.path_conventions = {"workspace": "src/"}  # type: ignore[misc]

    def test_unknown_top_level_field_still_rejected(self) -> None:
        """``extra="forbid"`` is unaffected by the new field (SC-002 guard)."""
        with pytest.raises(ValidationError):
            MissionType.model_validate(
                {
                    "id": "software-dev",
                    "display_name": "Software Development",
                    "template_set": {"spec": "spec-template.md"},
                }
            )
