"""Tests for pack_id identity and immutability (T008–T010).

Tests the stable, immutable ULID pack_id model as the sole runtime identity
for packs, mirroring the mission-identity model. Covers:

- PackDescriptor model validation (T008)
- OrgPackConfig pack_id field and backfill (T009)
- DRG boundary tolerance (T010)
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError
from ulid import ULID

from charter.offering.pack_paths import built_in_root
from specify_cli.doctrine.pack_descriptor import PackDescriptor
from charter.offering.drg.org_pack_config import (
    _BUILTIN_PACK_ID,
    OrgPackConfig,
    PackRegistry,
    ensure_pack_identity,
    save_pack_registry,
    load_pack_registry,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.doctrine]


# =============================================================================
# T008: PackDescriptor model validation
# =============================================================================


class TestPackDescriptorModel:
    """Pack descriptor model creation and validation."""

    def test_pack_descriptor_with_all_fields(self) -> None:
        """Create a PackDescriptor with all fields set."""
        pack_id = str(ULID())
        parent_id = str(ULID())
        doctrine_id = str(ULID())

        descriptor = PackDescriptor(
            pack_id=pack_id,
            pack_version="1.0.0",
            parent_pack=parent_id,
            accompanies_doctrine_pack=doctrine_id,
            name="my-pack",
        )

        assert descriptor.pack_id == pack_id
        assert descriptor.pack_version == "1.0.0"
        assert descriptor.parent_pack == parent_id
        assert descriptor.accompanies_doctrine_pack == doctrine_id
        assert descriptor.name == "my-pack"

    def test_pack_descriptor_minimal(self) -> None:
        """Create a PackDescriptor with required fields only."""
        pack_id = str(ULID())

        descriptor = PackDescriptor(
            pack_id=pack_id,
            pack_version="1.0.0",
            name="minimal-pack",
        )

        assert descriptor.pack_id == pack_id
        assert descriptor.pack_version == "1.0.0"
        assert descriptor.parent_pack is None
        assert descriptor.accompanies_doctrine_pack is None
        assert descriptor.name == "minimal-pack"

    def test_pack_descriptor_frozen(self) -> None:
        """PackDescriptor is immutable once created."""
        descriptor = PackDescriptor(
            pack_id=str(ULID()),
            pack_version="1.0.0",
            name="immutable-pack",
        )

        with pytest.raises(ValidationError, match="frozen"):
            descriptor.pack_id = str(ULID())

    def test_pack_descriptor_pack_id_required(self) -> None:
        """pack_id is a required field."""
        with pytest.raises(ValidationError, match="pack_id"):
            PackDescriptor(  # type: ignore[call-arg]
                pack_version="1.0.0",
                name="no-id-pack",
            )

    def test_pack_descriptor_pack_version_required(self) -> None:
        """pack_version is a required field."""
        with pytest.raises(ValidationError, match="pack_version"):
            PackDescriptor(  # type: ignore[call-arg]
                pack_id=str(ULID()),
                name="no-version-pack",
            )

    def test_pack_descriptor_name_required(self) -> None:
        """name is a required field."""
        with pytest.raises(ValidationError, match="name"):
            PackDescriptor(  # type: ignore[call-arg]
                pack_id=str(ULID()),
                pack_version="1.0.0",
            )

    def test_pack_descriptor_extra_fields_rejected(self) -> None:
        """Extra fields are rejected."""
        with pytest.raises(ValidationError, match="extra"):
            PackDescriptor(  # type: ignore[call-arg]
                pack_id=str(ULID()),
                pack_version="1.0.0",
                name="no-extras",
                extra_field="not allowed",
            )


# =============================================================================
# T009: OrgPackConfig pack_id field and idempotent backfill
# =============================================================================


class TestOrgPackConfigPackId:
    """OrgPackConfig pack_id field validation and backfill."""

    def test_org_pack_config_with_pack_id(self) -> None:
        """Create OrgPackConfig with pack_id."""
        pack_id = str(ULID())
        config = OrgPackConfig(
            name="test-pack",
            pack_id=pack_id,
            local_path=Path("/path/to/pack"),
        )

        assert config.pack_id == pack_id
        assert config.name == "test-pack"

    def test_org_pack_config_pack_id_optional(self) -> None:
        """pack_id is optional during backfill."""
        config = OrgPackConfig(
            name="legacy-pack",
            local_path=Path("/path/to/pack"),
        )

        assert config.pack_id is None
        assert config.name == "legacy-pack"

    def test_org_pack_config_pack_id_validation_valid_ulid(self) -> None:
        """A valid ULID pack_id passes validation."""
        valid_ulid = str(ULID())
        config = OrgPackConfig(
            name="valid-pack",
            pack_id=valid_ulid,
            local_path=Path("/path/to/pack"),
        )

        assert config.pack_id == valid_ulid
        # Verify it's still a valid ULID
        ULID.from_str(config.pack_id)

    def test_org_pack_config_pack_id_validation_invalid(self) -> None:
        """An invalid pack_id is rejected."""
        with pytest.raises(ValidationError, match="pack_id must be a valid"):
            OrgPackConfig(
                name="invalid-pack",
                pack_id="not-a-ulid",
                local_path=Path("/path/to/pack"),
            )

    def test_org_pack_config_pack_id_validation_wrong_length(self) -> None:
        """A ULID with wrong length is rejected."""
        with pytest.raises(ValidationError, match="pack_id must be a valid"):
            OrgPackConfig(
                name="short-pack",
                pack_id="01ARZ3NDEKTSV4R",  # 15 chars, not 26
                local_path=Path("/path/to/pack"),
            )

    def test_ensure_pack_identity_idempotent(self) -> None:
        """ensure_pack_identity is idempotent for built-in pack."""
        config1 = OrgPackConfig(
            name="default",
            local_path=Path("/path/to/builtin"),
        )

        # First call mints the built-in pack_id
        result1 = ensure_pack_identity(config1)
        assert result1.pack_id is not None
        id1 = result1.pack_id

        # Second call with a pack that already has pack_id returns it unchanged
        result2 = ensure_pack_identity(result1)
        assert result2.pack_id == id1

        # Creating a new instance and calling again yields the same stable id
        config3 = OrgPackConfig(
            name="default",
            local_path=Path("/path/to/builtin"),
        )
        result3 = ensure_pack_identity(config3)
        assert result3.pack_id == id1

    def test_ensure_pack_identity_stable_builtin_ulid(self) -> None:
        """Built-in pack_id is deterministic across multiple runs."""
        config1 = OrgPackConfig(
            name="default",
            local_path=Path("/path/to/builtin"),
        )
        config2 = OrgPackConfig(
            name="default",
            local_path=Path("/path/to/builtin"),
        )

        result1 = ensure_pack_identity(config1)
        result2 = ensure_pack_identity(config2)

        assert result1.pack_id == result2.pack_id
        assert result1.pack_id is not None
        assert len(result1.pack_id) == 26
        ULID.from_str(result1.pack_id)  # Parses as valid ULID

    def test_ensure_pack_identity_noop_for_non_builtin(self) -> None:
        """ensure_pack_identity is a no-op for non-builtin packs without pack_id."""
        config = OrgPackConfig(
            name="org-pack",
            local_path=Path("/path/to/org"),
        )

        result = ensure_pack_identity(config)
        assert result.pack_id is None
        assert result.name == "org-pack"

    def test_ensure_pack_identity_preserves_existing(self) -> None:
        """ensure_pack_identity preserves existing pack_id."""
        existing_id = str(ULID())
        config = OrgPackConfig(
            name="org-pack",
            pack_id=existing_id,
            local_path=Path("/path/to/org"),
        )

        result = ensure_pack_identity(config)
        assert result.pack_id == existing_id


# =============================================================================
# T009 (continued): Registry round-trip and persistence
# =============================================================================


class TestPackRegistryPersistence:
    """PackRegistry serialization and idempotent backfill."""

    def test_pack_registry_roundtrip_with_pack_id(self, tmp_path: Path) -> None:
        """PackRegistry with pack_id persists and reloads correctly."""
        pack_id = str(ULID())
        registry = PackRegistry(
            packs=[
                OrgPackConfig(
                    name="test-pack",
                    pack_id=pack_id,
                    local_path=Path("./local/pack"),
                )
            ]
        )

        repo_root = tmp_path
        save_pack_registry(repo_root, registry)
        loaded = load_pack_registry(repo_root)

        assert len(loaded.packs) == 1
        assert loaded.packs[0].pack_id == pack_id
        assert loaded.packs[0].name == "test-pack"

    def test_pack_registry_roundtrip_without_pack_id(self, tmp_path: Path) -> None:
        """PackRegistry without pack_id persists as None."""
        registry = PackRegistry(
            packs=[
                OrgPackConfig(
                    name="legacy-pack",
                    local_path=Path("./local/legacy"),
                )
            ]
        )

        repo_root = tmp_path
        save_pack_registry(repo_root, registry)
        loaded = load_pack_registry(repo_root)

        assert len(loaded.packs) == 1
        assert loaded.packs[0].pack_id is None
        assert loaded.packs[0].name == "legacy-pack"

    def test_pack_registry_yaml_structure(self, tmp_path: Path) -> None:
        """Saved PackRegistry YAML includes pack_id when present."""
        pack_id = str(ULID())
        registry = PackRegistry(
            packs=[
                OrgPackConfig(
                    name="test-pack",
                    pack_id=pack_id,
                    local_path=Path("./local/pack"),
                )
            ]
        )

        repo_root = tmp_path
        save_pack_registry(repo_root, registry)

        config_path = repo_root / ".kittify" / "config.yaml"
        assert config_path.exists()
        content = config_path.read_text(encoding="utf-8")

        # YAML should contain both name and pack_id
        assert "test-pack" in content
        assert pack_id in content

    def test_pack_registry_multiple_packs_distinct_ids(
        self, tmp_path: Path
    ) -> None:
        """Multiple packs with distinct pack_ids persist correctly."""
        id1 = str(ULID())
        id2 = str(ULID())

        registry = PackRegistry(
            packs=[
                OrgPackConfig(
                    name="pack1",
                    pack_id=id1,
                    local_path=Path("./local/pack1"),
                ),
                OrgPackConfig(
                    name="pack2",
                    pack_id=id2,
                    local_path=Path("./local/pack2"),
                ),
            ]
        )

        repo_root = tmp_path
        save_pack_registry(repo_root, registry)
        loaded = load_pack_registry(repo_root)

        assert len(loaded.packs) == 2
        ids = {pack.pack_id for pack in loaded.packs}
        assert ids == {id1, id2}


# =============================================================================
# T009: No silent fallback on ambiguous lookup
# =============================================================================


class TestNoSilentFallback:
    """Resolver requires pack_id; no silent fallback to name lookup."""

    def test_pack_id_sole_identity(self) -> None:
        """pack_id is the sole runtime identity; name is a handle only."""
        pack_id = str(ULID())
        config = OrgPackConfig(
            name="my-pack",
            pack_id=pack_id,
            local_path=Path("/path/to/pack"),
        )

        # The identity is the pack_id, not the name
        assert config.pack_id == pack_id
        assert config.name == "my-pack"
        # In resolver code (not tested here, but enforced by contract),
        # lookups MUST use pack_id, never name as a fallback.

    def test_multiple_packs_same_name_different_ids(self) -> None:
        """Multiple packs with the same name but different pack_ids are distinct."""
        id1 = str(ULID())
        id2 = str(ULID())

        config1 = OrgPackConfig(
            name="pack-name",
            pack_id=id1,
            local_path=Path("/path/to/pack1"),
        )
        config2 = OrgPackConfig(
            name="pack-name",
            pack_id=id2,
            local_path=Path("/path/to/pack2"),
        )

        # Different pack_ids make them distinct, despite identical name
        assert config1.pack_id != config2.pack_id
        assert config1.name == config2.name


class TestBuiltinPackIdBinding:
    """Bind the two authorities for the built-in pack_id so they cannot drift.

    The well-known built-in ULID lives in two places: the Python constant
    ``_BUILTIN_PACK_ID`` (org_pack_config.py) and the authored
    ``packs/built-in/pack.yaml``. Nothing else enforces they agree, so a future
    edit to one could silently diverge from the other. This binding test makes
    that divergence a red test.
    """

    def test_authored_pack_yaml_pack_id_equals_constant(self) -> None:
        """packs/built-in/pack.yaml ``pack_id`` must equal ``_BUILTIN_PACK_ID``."""
        pack_yaml = built_in_root() / "pack.yaml"
        assert pack_yaml.is_file(), "packs/built-in/pack.yaml must exist (authored)"

        data = yaml.safe_load(pack_yaml.read_text(encoding="utf-8"))
        assert isinstance(data, dict), "pack.yaml must parse to a mapping"

        authored_pack_id = data.get("pack_id")
        assert authored_pack_id == _BUILTIN_PACK_ID, (
            "built-in pack_id drift: packs/built-in/pack.yaml pack_id "
            f"{authored_pack_id!r} != _BUILTIN_PACK_ID {_BUILTIN_PACK_ID!r}. "
            "The Python constant and the authored descriptor are the two "
            "authorities for one identity and must stay byte-identical."
        )
