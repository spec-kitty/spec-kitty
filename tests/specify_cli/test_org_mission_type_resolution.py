"""Regression repros for #3831 and #4088, flipped green by WP03 (T023).

``specify_cli.mission.get_mission_for_feature``/``get_mission_by_name`` used
to be the org-blind entry point identified in spec.md's "Consumer census &
brownfield seam notes" (``_packaged_missions_dir``/``_mission_path_by_name``,
mission-type-canonical-source-01M302V9). It resolved a feature's mission
purely from ``.kittify/missions/<type>/mission.yaml`` and the packaged
``specify_cli/missions/<type>/mission.yaml`` tree; it never looked at an
activated org pack's ``mission_types/<type>.yaml`` (#3831) and never
consulted ``.kittify/overrides/missions/<type>/`` (#4088).

WP03 (the re-scoped, targeted loader fix -- see spec.md's "Re-scope
(2026-09-21)" section) routes ``get_mission_by_name`` through
``specify_cli.runtime.resolver.resolve_mission`` (override -> legacy -> org
-> global-mission -> package) and, when no tier has a ``mission.yaml``,
builds a neutral in-memory ``Mission`` for a registered org mission type
from its sparse ``mission_types/<type>.yaml`` registration. Both repros
below now PASS -- the ``xfail(strict=True)`` markers are removed and their
bodies rewritten to the post-fix expectation.

Fixtures: ``tests/fixtures/mission_type_canonical/`` (see that directory's
README.md for provenance and the full fixture tree).
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from specify_cli.mission import MissionNotFoundError, get_mission_for_feature

pytestmark = [pytest.mark.regression]

_FIXTURES_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "mission_type_canonical"

_SOFTWARE_DEV_KITTY = "Software Dev Kitty"


class TestOrgActivatedCustomMissionType:
    """#3831 (SC-001): an org-activated custom mission type must resolve as itself."""

    def test_org_custom_type_resolves_to_its_own_identity(self) -> None:
        """A project with an org-activated ``docs-audit`` type and no
        ``.kittify/missions/`` must load the ``docs-audit`` identity, not
        silently substitute the built-in software-dev mission -- and no
        warning is emitted, since this is a genuine resolution, not a
        fallback (T021: a registered org type is never treated as "not
        found").
        """
        feature_dir = _FIXTURES_ROOT / "org_activated_custom_type" / "kitty-specs" / "001-audit-public-docs"

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            mission = get_mission_for_feature(feature_dir)

        assert not caught, f"unexpected warning(s) resolving a registered org mission type: {[str(w.message) for w in caught]}"

        assert mission.name != _SOFTWARE_DEV_KITTY, (
            "get_mission_for_feature fell back to the packaged software-dev mission instead of resolving the org-activated 'docs-audit' custom type (#3831)"
        )
        assert mission.name == "Docs Audit Kitty"

        # T021: neutral conventions -- an org type built from a sparse
        # mission_types/<type>.yaml registration never inherits
        # software-dev's path/artifact shape.
        assert mission.get_path_conventions() == {}
        assert mission.get_required_artifacts() == []
        assert mission.get_optional_artifacts() == []


class TestProjectMissionTypeOverride:
    """#4088 (SC-002): a pre-migration project mission override must win."""

    def test_legacy_override_directory_is_honoured(self) -> None:
        """A project-level ``.kittify/overrides/missions/software-dev/mission.yaml``
        override must take effect over the packaged ``software-dev`` mission
        (the OVERRIDE tier of ``resolve_mission``'s precedence chain).
        """
        feature_dir = _FIXTURES_ROOT / "project_override" / "legacy" / "kitty-specs" / "001-legacy-override-feature"

        mission = get_mission_for_feature(feature_dir)

        assert mission.name != _SOFTWARE_DEV_KITTY, (
            "get_mission_for_feature ignored .kittify/overrides/missions/software-dev/ and loaded the packaged software-dev mission instead (#4088)"
        )
        assert mission.name == "Override Kitty"


class TestTypedUnknownMissionTypeSurfacesVisibly:
    """T022 (FR-007/SC-003): a typed-but-unregistered mission type must raise."""

    def test_typed_unknown_mission_type_raises_not_found(self, tmp_path: Path) -> None:
        """A ``mission_type`` that matches neither a ``mission.yaml`` at any
        resolver tier nor a registered org mission type must surface a
        visible ``MissionNotFoundError`` -- never a silent warn-and-
        substitute to software-dev (the pre-fix #3831-adjacent defect on
        this same code path).
        """
        import json

        kittify_dir = tmp_path / ".kittify"
        kittify_dir.mkdir()
        feature_dir = tmp_path / "kitty-specs" / "001-typed-unknown"
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text(json.dumps({"mission_type": "totally-unregistered-type"}))

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with pytest.raises(MissionNotFoundError, match="totally-unregistered-type"):
                get_mission_for_feature(feature_dir)

        assert not caught, f"unexpected warning(s) for a typed-unknown mission type: {[str(w.message) for w in caught]}"


class TestTypelessMissionLoadsSoftwareDevTemplateSilently:
    """T022 (C-006/FR-003a): a typeless feature keeps the silent software-dev default."""

    def test_typeless_feature_loads_software_dev_with_no_warning(self, tmp_path: Path) -> None:
        """A feature whose ``meta.json`` records no ``mission_type`` at all
        must still load the software-dev *template* default, with zero
        warnings -- this is a template-file-selection convenience (C-006),
        not a governance fallback, and must not look like one.
        """
        import json

        kittify_dir = tmp_path / ".kittify"
        kittify_dir.mkdir()
        feature_dir = tmp_path / "kitty-specs" / "000-legacy"
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text(json.dumps({"slug": "000-legacy"}))

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            mission = get_mission_for_feature(feature_dir)

        assert not caught, f"unexpected warning(s) for a typeless feature: {[str(w.message) for w in caught]}"
        assert mission.domain == "software"
