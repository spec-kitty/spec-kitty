"""Tests for the ``CharterYaml`` pydantic model (WP01 / T001).

Contract: ``kitty-specs/consolidate-charter-bundle-01KXSYB9/contracts/
charter-yaml-schema.md``. Pins the structured shape of the git-tracked,
authorable ``charter.yaml``.

⚠ paula BLOCKER-1 (data-model.md): activation keys are FLAT AT THE ROOT,
NOT nested under an ``activation:`` mapping — ``test_rejects_nested_
activation_mapping`` is the structural regression guard for that.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from charter.activation.activations import ActivationEntry
from charter.activation.charter_yaml_io import apply_yaml_write, load_charter_yaml
from charter.activation.pack_manager import prepare_activation_write
from charter.activation.schemas import (
    CharterCatalog,
    CharterCatalogReference,
    CharterYaml,
    CharterYamlMetadata,
    Directive,
    DirectivesConfig,
    GovernanceConfig,
)


pytestmark = [pytest.mark.unit]


def _catalog() -> CharterCatalog:
    return CharterCatalog(
        mission="software-dev",
        template_set="software-dev-default",
        languages=["python"],
        references=[
            CharterCatalogReference(
                id="PARADIGM:atomic-design",
                kind="paradigm",
                title="Atomic Design",
                summary="Compose interfaces from a five-level hierarchy.",
                source_path="src/charter/offering/paradigms/built-in/atomic-design.paradigm.yaml",
                local_path="_LIBRARY/paradigm-atomic-design.md",
            )
        ],
    )


def _governance() -> GovernanceConfig:
    return GovernanceConfig(
        activations=[
            ActivationEntry(
                activation_context={"mission_type": "software-dev"},
                charter_pack_id="very-serious-developers",
                artifact_id="caveman-comments",
            )
        ]
    )


def _directives() -> DirectivesConfig:
    return DirectivesConfig(
        directives=[Directive(id="DIRECTIVE_001", title="Architectural Integrity Standard")]
    )


def _activation_yaml_keys() -> tuple[str, ...]:
    """The flat activation-key vocabulary, from its single authority.

    Function-scoped import: ``charter.activation.pack_manager`` imports this
    module's package on its own import path, so a module-level back-import
    here would be circular (the same reason ``charter_yaml_io`` uses lazy
    accessors).
    """
    from charter.activation.pack_manager import ACTIVATION_YAML_KEYS

    return tuple(ACTIVATION_YAML_KEYS)


class TestCharterYamlRoundTrip:
    def test_round_trips_governance_directives_catalog(self) -> None:
        governance = _governance()
        directives = _directives()
        catalog = _catalog()

        charter = CharterYaml(governance=governance, directives=directives, catalog=catalog)

        assert charter.governance == governance
        assert charter.directives == directives
        assert charter.catalog == catalog

    def test_governance_and_directives_deserialize_from_dumped_dict(self) -> None:
        """G1: governance/directives deserialize into the existing
        GovernanceConfig/DirectivesConfig models unchanged, round-tripped
        through a plain dict (as if read back from YAML)."""
        original = CharterYaml(governance=_governance(), directives=_directives(), catalog=_catalog())
        dumped = original.model_dump(mode="json")

        rebuilt = CharterYaml.model_validate(dumped)

        assert rebuilt.governance == original.governance
        assert rebuilt.directives == original.directives
        assert rebuilt.catalog == original.catalog

    def test_catalog_shape_mirrors_references_yaml_body(self) -> None:
        """G2: catalog carries mission/template_set/languages/references —
        the same keys as the retired references.yaml body."""
        catalog = _catalog()
        dumped = catalog.model_dump(mode="json")

        assert set(dumped.keys()) == {"mission", "template_set", "languages", "references"}
        assert dumped["references"][0]["id"] == "PARADIGM:atomic-design"


class TestActivationIsFlatAtRoot:
    def test_rejects_nested_activation_mapping(self) -> None:
        """paula BLOCKER-1: an ``activation:`` key nested under CharterYaml
        is not a declared field — extra="forbid" rejects it outright."""
        with pytest.raises(ValidationError):
            CharterYaml(
                governance=_governance(),
                directives=_directives(),
                catalog=_catalog(),
                activation={"activated_directives": ["001-x"]},  # type: ignore[call-arg]
            )

    @pytest.mark.parametrize("field_name", _activation_yaml_keys())
    def test_activation_field_is_flat_root_attribute(self, field_name: str) -> None:
        """Every key of the single vocabulary authority is a declared field.

        Parametrized over ``ACTIVATION_YAML_KEYS`` rather than a hand-written
        list (#6556): the literal this used to carry omitted three keys the
        activation writer itself writes, which is how the model drifted from
        the authority.
        """
        charter = CharterYaml(
            governance=_governance(),
            directives=_directives(),
            catalog=_catalog(),
            **{field_name: ["some-id"]},
        )
        assert getattr(charter, field_name) == ["some-id"]

    def test_document_carrying_every_authority_key_validates(self) -> None:
        """The all-keys combination case: set-level acceptance, not just per key."""
        document = CharterYaml(
            governance=_governance(), directives=_directives(), catalog=_catalog()
        ).model_dump(mode="json")
        document.update({key: ["some-id"] for key in _activation_yaml_keys()})

        charter = CharterYaml.model_validate(document)

        for key in _activation_yaml_keys():
            assert getattr(charter, key) == ["some-id"]

    def test_rejects_unknown_activated_key(self) -> None:
        """Accepting the authority must not degrade into accepting anything
        ``activated_*``: an undeclared key is still refused."""
        with pytest.raises(ValidationError):
            CharterYaml(
                governance=_governance(),
                directives=_directives(),
                catalog=_catalog(),
                **{"activated_not_a_kind": ["x"]},
            )

    def test_activation_field_defaults_to_none_absent_key_fallback(self) -> None:
        """G3: an absent key resolves the default-pack fallback (three-state:
        None is distinct from an explicit empty list)."""
        charter = CharterYaml(governance=_governance(), directives=_directives(), catalog=_catalog())
        assert charter.activated_directives is None
        assert charter.activated_kinds is None

    def test_activation_field_accepts_explicit_empty_list_fail_closed(self) -> None:
        """G3: an explicit empty list stays fail-closed — distinct from
        the absent-key (None) fallback case."""
        charter = CharterYaml(
            governance=_governance(),
            directives=_directives(),
            catalog=_catalog(),
            activated_directives=[],
        )
        assert charter.activated_directives == []
        assert charter.activated_directives is not None


class TestCharterYamlMetadata:
    def test_metadata_has_no_charter_hash_field(self) -> None:
        """G4 / Landmine 2: metadata MUST NOT carry a self-referential
        charter_hash — a hash of charter.yaml cannot live inside charter.yaml."""
        assert "charter_hash" not in CharterYamlMetadata.model_fields

    def test_metadata_carries_bundle_schema_version_2(self) -> None:
        metadata = CharterYamlMetadata()
        assert metadata.bundle_schema_version == 2

    def test_metadata_rejects_charter_hash_kwarg(self) -> None:
        with pytest.raises(ValidationError):
            CharterYamlMetadata(charter_hash="sha256:deadbeef")  # type: ignore[call-arg]


class TestCharterYamlOverridesAndSchemaVersion:
    def test_schema_version_defaults_to_2_0_0(self) -> None:
        charter = CharterYaml(governance=_governance(), directives=_directives(), catalog=_catalog())
        assert charter.schema_version == "2.0.0"

    def test_schema_version_regex_enforced(self) -> None:
        with pytest.raises(ValidationError):
            CharterYaml(
                schema_version="not-semver",
                governance=_governance(),
                directives=_directives(),
                catalog=_catalog(),
            )

    def test_overrides_defaults_to_empty_mapping(self) -> None:
        charter = CharterYaml(governance=_governance(), directives=_directives(), catalog=_catalog())
        assert charter.overrides == {}

    def test_overrides_accepts_forward_compatible_mapping(self) -> None:
        charter = CharterYaml(
            governance=_governance(),
            directives=_directives(),
            catalog=_catalog(),
            overrides={"some-future-key": {"nested": True}},
        )
        assert charter.overrides == {"some-future-key": {"nested": True}}

    def test_charter_yaml_is_frozen(self) -> None:
        charter = CharterYaml(governance=_governance(), directives=_directives(), catalog=_catalog())
        with pytest.raises(ValidationError):
            charter.schema_version = "9.9.9"  # type: ignore[misc]


#: A sound ``charter.yaml`` body — everything ``CharterYaml`` requires, and no
#: activation key (the state a freshly generated charter is in).
_SOUND_CHARTER_YAML = """\
schema_version: '2.0.0'
governance: {}
directives:
  directives: []
catalog:
  mission: software-dev
  template_set: software-dev-default
  languages: []
  references: []
metadata:
  generated_at: '2026-01-01T00:00:00Z'
  bundle_schema_version: 2
"""

#: An UNMIGRATED project's ``config.yaml``: the ``charter:`` pointer plus one
#: legacy activation key, which is what makes the ledger resolver answer
#: LEGACY and sends activation writes to ``charter.yaml`` itself.
_LEGACY_CONFIG_YAML = """\
charter: .kittify/charter/charter.yaml
activated_directives:
- DIRECTIVE_001
"""


def _legacy_project(root: Path) -> Path:
    """Write an unmigrated (legacy-surface) project under *root*."""
    charter_dir = root / ".kittify" / "charter"
    charter_dir.mkdir(parents=True)
    (charter_dir / "charter.yaml").write_text(_SOUND_CHARTER_YAML, encoding="utf-8")
    (root / ".kittify" / "config.yaml").write_text(_LEGACY_CONFIG_YAML, encoding="utf-8")
    return root


class TestWriterAndModelAgreeOnActivationKeys:
    """#6556: the model must accept what the activation writer writes.

    Red on ``main``: ``prepare_activation_write`` puts ``activated_skills``
    (and the glossary-pack / anti-pattern keys) on ``charter.yaml``, and
    ``CharterYaml.model_validate`` then refused the document with
    ``extra_forbidden``. These tests go through the real writer rather than a
    hand-built dict, so the two surfaces cannot silently diverge again.
    """

    @pytest.mark.parametrize(
        "key",
        # The three keys the model was missing, named as literals ON PURPOSE:
        # this pins the exact drift #6556 reported. The full-vocabulary
        # expectation lives in the parity gate
        # (tests/charter/test_activation_vocabulary_setequal.py), which derives
        # it from the authority and must never restate names.
        ["activated_skills", "activated_glossary_packs", "activated_anti_patterns"],
    )
    def test_written_activation_key_validates_through_the_model(
        self, tmp_path: Path, key: str
    ) -> None:
        project = _legacy_project(tmp_path)
        charter_yaml = project / ".kittify" / "charter" / "charter.yaml"

        prepared = prepare_activation_write(project, {key: ["some-id"]})
        # Self-guarding: if the resolver ever sends this write to the activation
        # ledger instead of the legacy surface, fail here with a clear reason
        # rather than at the on-disk assertion below.
        assert prepared.target == charter_yaml, (
            f"expected the legacy-surface write target {charter_yaml}, got {prepared.target}"
        )
        apply_yaml_write(prepared)

        document = dict(load_charter_yaml(charter_yaml))
        assert document[key] == ["some-id"], "the writer must put the key on disk"
        charter = CharterYaml.model_validate(document)
        assert getattr(charter, key) == ["some-id"]


# ---------------------------------------------------------------------------
# #6855 -- the deny side: a ``deactivated_<kind>`` key is NOT charter.yaml content
# ---------------------------------------------------------------------------

#: One deny-list key, named literally on purpose: the derived-vocabulary pin lives in
#: ``tests/charter/test_activation_vocabulary_setequal.py`` (WP02). Here the point is
#: the MESSAGE a caller sees for a concrete legacy document.
_DENY_KEY = "deactivated_tactics"

#: The activation ledger the refusal must name (the key's only legal home).
_LEDGER_PATH = ".kittify/charter/activation.yaml"


def _sound_mapping() -> dict[str, Any]:
    """``_SOUND_CHARTER_YAML`` as a mapping: everything the model requires, no activation key."""
    return {
        "schema_version": "2.0.0",
        "governance": {},
        "directives": {"directives": []},
        "catalog": {
            "mission": "software-dev",
            "template_set": "software-dev-default",
            "languages": [],
            "references": [],
        },
        "metadata": {"generated_at": "2026-01-01T00:00:00Z", "bundle_schema_version": 2},
    }


class TestDenyKeysAreNotCharterYamlContent:
    """#6855: the deny side is activation-ledger content, refused by design.

    ADR 2026-10-19-1 Decision 1 (C-003) says ``deactivated_*`` keys never appear on
    ``charter.yaml`` or ``config.yaml``; doctor reports a hand-written one as the
    ``LEGACY_DENY_KEY`` error and the ledger migration refuses it. The model therefore
    keeps refusing the document -- and now says which contract it is enforcing instead
    of the bare pydantic ``extra_forbidden`` message.
    """

    def test_deny_key_is_refused_with_the_ledger_contract(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            CharterYaml.model_validate({**_sound_mapping(), _DENY_KEY: ["x"]})

        message = str(excinfo.value)
        # Two stable facts, not the full prose (the wording may be refined later).
        assert _LEDGER_PATH in message, "the refusal must name the activation ledger, the key's only legal home"
        assert "never applied" in message, "the refusal must say the deny key was never applied where it sits"

    def test_same_document_without_the_deny_key_validates(self) -> None:
        """Positive control: the refusal above is the deny key's doing, not the fixture's."""
        charter = CharterYaml.model_validate(_sound_mapping())

        assert charter.activated_tactics is None
        dumped = charter.model_dump(mode="json")
        assert not any(name.startswith("deactivated_") for name in dumped), "no deny key may be declared, or it would be emitted into every charter"

    def test_an_empty_deny_list_is_refused_too(self) -> None:
        """Absent, ``[]`` and a non-empty list are all "not a charter.yaml shape"."""
        with pytest.raises(ValidationError):
            CharterYaml.model_validate({**_sound_mapping(), "deactivated_directives": []})

    def test_deny_key_is_not_a_declared_field(self) -> None:
        assert "deactivated_directives" not in CharterYaml.model_fields
