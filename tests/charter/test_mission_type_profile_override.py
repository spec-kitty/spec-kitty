"""WP05 — per-type governance override channel (overlay-ridden).

Pins the FR-011 / C-005 contract: a project overrides a mission type's
governance by dropping
``.kittify/charter-packs/mission_types/<type>/governance-profile.yaml`` — resolved
through the *existing* ``doctrine/base.py`` builtin → org → project overlay
(field-merge + :class:`~charter.offering.base.DoctrineLayerCollisionWarning`), **not** a
bespoke second merge.  Covers:

* the ``id == mission_type`` overlay invariant (model + shipped profiles);
* precedence (project override of a field wins over shipped baseline);
* fall-through (fields absent from the override inherit the shipped value);
* collision visibility (the shadow emits ``DoctrineLayerCollisionWarning``);
* the org layer (project > org > builtin, #832 support comes free);
* the end-to-end ride through ``resolve_mission_type_context``.
"""

from __future__ import annotations

import subprocess
import warnings
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.activation.mission_type_profile_repository import MissionTypeProfileRepository
from charter.activation.mission_type_profiles import (
    MissionTypeProfile,
    resolve_mission_type_context,
)
from charter.offering.base import DoctrineLayerCollisionWarning
from charter.offering.missions.mission_type_repository import builtin_mission_type_ids

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_SHIPPED_MISSIONS_ROOT = (
    Path(__file__).resolve().parents[2] / "packs" / "built-in" / "missions"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_profile(profile_dir: Path, data: dict) -> None:
    """Write a ``governance-profile.yaml`` into a per-type subdirectory."""
    profile_dir.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    with (profile_dir / "governance-profile.yaml").open("w") as fh:
        yaml.dump(data, fh)


def _git_init_minimal(repo_root: Path) -> None:
    for args in (
        ["git", "init", "--initial-branch=main"],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "Test"],
        ["git", "config", "commit.gpgsign", "false"],
    ):
        subprocess.run(args, cwd=repo_root, check=True, capture_output=True)
    # WP04 (C-A1): existing_mission_types() -> PackContext.from_config()
    # fail-closes without mission_type_activations. resolve_mission_type_context
    # in this module always resolves "software-dev", so that's the type
    # provisioned here -- unrelated to the project/org/builtin override stack
    # under test.
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# T025 — the id == mission_type overlay invariant (model level)
# ---------------------------------------------------------------------------


class TestIdMissionTypeInvariant:
    """``id`` is bound to ``mission_type`` so the base.py overlay keys correctly."""

    def test_id_defaults_to_mission_type_when_absent(self) -> None:
        profile = MissionTypeProfile(mission_type="software-dev")
        assert profile.id == "software-dev"

    def test_id_may_be_stated_explicitly_when_equal(self) -> None:
        profile = MissionTypeProfile(mission_type="research", id="research")
        assert profile.id == "research"

    def test_mismatched_id_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="must equal mission_type"):
            MissionTypeProfile(mission_type="software-dev", id="documentation")


# ---------------------------------------------------------------------------
# T029 — every shipped governance-profile.yaml carries id == mission_type
# ---------------------------------------------------------------------------


class TestShippedProfilesHonourInvariant:
    """WP06/07/08 inherit this: shipped profiles must key on id == mission_type."""

    def test_all_shipped_profiles_have_id_equal_to_mission_type(self) -> None:
        repo = MissionTypeProfileRepository()
        for mission_type in builtin_mission_type_ids():
            profile = repo.get(mission_type)
            assert profile is not None, (
                f"shipped profile for {mission_type!r} did not load — the "
                "governance-profile.yaml is missing or mis-keyed."
            )
            assert profile.id == profile.mission_type == mission_type

    def test_software_dev_yaml_carries_raw_id(self) -> None:
        """The shipped software-dev YAML must carry a *raw* ``id`` field.

        Overlay keying reads the raw ``id`` (base.py:249); a profile whose YAML
        omits it cannot be shadowed by a project override.  software-dev is the
        template WP06/07/08 mirror.
        """
        raw = YAML(typ="safe").load(
            (_SHIPPED_MISSIONS_ROOT / "software-dev" / "governance-profile.yaml").read_text(
                encoding="utf-8"
            )
        )
        assert raw["id"] == "software-dev"


# ---------------------------------------------------------------------------
# T028 — precedence + fall-through + collision (synthetic layers)
# ---------------------------------------------------------------------------


class TestProjectOverrideRidesTheOverlay:
    """Project override wins field-wise, absent fields fall through, shadow warns."""

    def _shipped_profile(self, built_in: Path) -> None:
        _write_profile(
            built_in / "software-dev",
            {
                "id": "software-dev",
                "mission_type": "software-dev",
                "template_set": "software-dev-default",
                "selected_directives": ["DIRECTIVE_001"],
                "selected_tactics": ["language-driven-design"],
            },
        )

    def test_project_field_wins_and_absent_fields_fall_through(
        self, tmp_path: Path
    ) -> None:
        built_in = tmp_path / "built-in"
        project = tmp_path / "project"
        self._shipped_profile(built_in)
        # Override *only* template_set + selected_directives; leave selected_tactics absent.
        _write_profile(
            project / "software-dev",
            {
                "id": "software-dev",
                "mission_type": "software-dev",
                "template_set": "project-custom",
                "selected_directives": ["DIRECTIVE_099"],
            },
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DoctrineLayerCollisionWarning)
            repo = MissionTypeProfileRepository(
                built_in_dir=built_in, project_dir=project
            )

        profile = repo.get("software-dev")
        assert profile is not None
        # Project field wins.
        assert profile.template_set == "project-custom"
        assert profile.selected_directives == ["DIRECTIVE_099"]
        # Absent field falls through from the shipped baseline (field-merge).
        assert profile.selected_tactics == ["language-driven-design"]
        # The winning layer is the project layer.
        assert repo.get_provenance("software-dev") == "project"

    def test_shadow_emits_collision_warning(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in"
        project = tmp_path / "project"
        self._shipped_profile(built_in)
        _write_profile(
            project / "software-dev",
            {
                "id": "software-dev",
                "mission_type": "software-dev",
                "template_set": "project-custom",
            },
        )

        with pytest.warns(DoctrineLayerCollisionWarning, match="software-dev"):
            MissionTypeProfileRepository(built_in_dir=built_in, project_dir=project)

    def test_id_less_project_override_is_skipped(self, tmp_path: Path) -> None:
        """An override YAML without ``id`` cannot key onto the shipped profile.

        base.py:249 skips id-less overlay files with a UserWarning; the shipped
        baseline survives untouched (provenance stays ``builtin``).
        """
        built_in = tmp_path / "built-in"
        project = tmp_path / "project"
        self._shipped_profile(built_in)
        _write_profile(
            project / "software-dev",
            {"mission_type": "software-dev", "template_set": "ignored"},
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            repo = MissionTypeProfileRepository(
                built_in_dir=built_in, project_dir=project
            )

        profile = repo.get("software-dev")
        assert profile is not None
        assert profile.template_set == "software-dev-default"
        assert repo.get_provenance("software-dev") == "builtin"


class TestOrgLayerPrecedence:
    """project > org > builtin — the org layer rides the same stack (#832 free)."""

    def test_project_beats_org_beats_builtin(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in"
        org = tmp_path / "org"
        project = tmp_path / "project"
        _write_profile(
            built_in / "software-dev",
            {
                "id": "software-dev",
                "mission_type": "software-dev",
                "template_set": "builtin",
            },
        )
        _write_profile(
            org / "software-dev",
            {
                "id": "software-dev",
                "mission_type": "software-dev",
                "template_set": "org",
            },
        )
        _write_profile(
            project / "software-dev",
            {
                "id": "software-dev",
                "mission_type": "software-dev",
                "template_set": "project",
            },
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DoctrineLayerCollisionWarning)
            repo = MissionTypeProfileRepository(
                built_in_dir=built_in, org_dirs=[org], project_dir=project
            )

        profile = repo.get("software-dev")
        assert profile is not None
        assert profile.template_set == "project"
        assert repo.get_provenance("software-dev") == "project"

    def test_org_overrides_builtin_when_no_project(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in"
        org = tmp_path / "org"
        _write_profile(
            built_in / "software-dev",
            {
                "id": "software-dev",
                "mission_type": "software-dev",
                "template_set": "builtin",
            },
        )
        _write_profile(
            org / "software-dev",
            {
                "id": "software-dev",
                "mission_type": "software-dev",
                "template_set": "org",
            },
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DoctrineLayerCollisionWarning)
            repo = MissionTypeProfileRepository(built_in_dir=built_in, org_dirs=[org])

        profile = repo.get("software-dev")
        assert profile is not None
        assert profile.template_set == "org"
        assert repo.get_provenance("software-dev") == "org"


# ---------------------------------------------------------------------------
# T027 — the override rides resolve_mission_type_context end-to-end
# ---------------------------------------------------------------------------


class TestOverrideRidesResolverEndToEnd:
    """A real project override at .kittify/... wins through the resolver seam."""

    @pytest.mark.git_repo
    def test_project_override_wins_and_warns_through_resolver(
        self, tmp_path: Path
    ) -> None:
        _git_init_minimal(tmp_path)
        override_dir = tmp_path / ".kittify" / "charter-packs" / "mission_types" / "software-dev"
        _write_profile(
            override_dir,
            {
                "id": "software-dev",
                "mission_type": "software-dev",
                "template_set": "project-only-template",
            },
        )

        with pytest.warns(DoctrineLayerCollisionWarning, match="software-dev"):
            bundle = resolve_mission_type_context(tmp_path, mission_type="software-dev")

        assert bundle.mission_type == "software-dev"
        # Provenance reflects the winning (project) layer.
        assert bundle.provenance == "project"
        # The rendered payload carries the project override, not the shipped default.
        assert "project-only-template" in bundle.governance_text
        assert "software-dev-default" not in bundle.governance_text

    @pytest.mark.git_repo
    def test_no_override_keeps_shipped_baseline(self, tmp_path: Path) -> None:
        _git_init_minimal(tmp_path)

        bundle = resolve_mission_type_context(tmp_path, mission_type="software-dev")

        assert bundle.mission_type == "software-dev"
        assert bundle.provenance == "builtin"
        assert "software-dev-default" in bundle.governance_text
