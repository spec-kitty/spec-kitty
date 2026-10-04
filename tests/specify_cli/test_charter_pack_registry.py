"""Guard tests for ``specify_cli.charter_pack_registry`` (#3064 follow-up).

``PER_KIND_ACTIVATION_KEYS`` used to be a hand-written eight-key tuple that
could silently drift from ``charter.activation.pack_manager.YAML_KEY_MAP`` (the
canonical charter-kind -> ``config.yaml``-key table) if a new charter kind
was ever added. It is now derived from ``YAML_KEY_MAP.values()`` with
``mission_type_activations`` (the documented ``mission-type`` outlier) and
``activated_glossary_packs`` (deliberately not declared by either built-in
pack — see the module docstring) excluded.

These tests pin:

1. The derivation stays byte-identical to ``YAML_KEY_MAP`` minus the two
   documented exclusions, so a tenth charter kind added later is picked up
   automatically instead of drifting silently.
2. ``activated_glossary_packs`` is never in the derived set (glossary
   three-state absence stays owned by the later normalize-absence
   migration).
3. Every ``BUILTIN_PACKS`` name resolves to an existing shipped file via
   ``resolve_builtin_pack_path`` (the fail-closed ``.exists()`` guard).
"""

from __future__ import annotations

import pytest

from charter.activation.pack_manager import YAML_KEY_MAP
from specify_cli.charter_pack_registry import (
    ACTIVATION_KEYS,
    BUILTIN_PACKS,
    PER_KIND_ACTIVATION_KEYS,
    UnknownPackError,
    resolve_builtin_pack_path,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_per_kind_activation_keys_matches_yaml_key_map_minus_glossary() -> None:
    """Derivation is pinned: YAML_KEY_MAP values minus the mission-type outlier
    and the deliberately-excluded glossary key."""
    assert set(PER_KIND_ACTIVATION_KEYS) == set(YAML_KEY_MAP.values()) - {
        "mission_type_activations",
        "activated_glossary_packs",
        "activated_skills",
    }


def test_per_kind_activation_keys_excludes_skills() -> None:
    """Skill activation is opt-in: an absent key means org-required only, so no
    built-in pack may carry the key (it would flip default-in-force)."""
    assert "activated_skills" not in PER_KIND_ACTIVATION_KEYS


def test_per_kind_activation_keys_excludes_glossary() -> None:
    """Glossary-pack activation is never a per-kind pack key (three-state
    absence is owned by the 3.2.x normalize-absence migration)."""
    assert "activated_glossary_packs" not in PER_KIND_ACTIVATION_KEYS


def test_per_kind_activation_keys_excludes_mission_type() -> None:
    """``mission_type_activations`` is the documented outlier, already listed
    separately in ACTIVATION_KEYS."""
    assert "mission_type_activations" not in PER_KIND_ACTIVATION_KEYS


def test_per_kind_activation_keys_is_unchanged_eight_key_set() -> None:
    """Today's derived result must be byte-identical to the previous
    hand-written eight-key tuple (behaviour-preserving refactor)."""
    assert set(PER_KIND_ACTIVATION_KEYS) == {
        "activated_directives",
        "activated_tactics",
        "activated_styleguides",
        "activated_toolguides",
        "activated_paradigms",
        "activated_procedures",
        "activated_agent_profiles",
        "activated_mission_step_contracts",
    }


def test_activation_keys_still_includes_mission_type_and_kinds() -> None:
    assert "mission_type_activations" in ACTIVATION_KEYS
    assert "activated_kinds" in ACTIVATION_KEYS


@pytest.mark.parametrize("name", sorted(BUILTIN_PACKS))
def test_every_builtin_pack_resolves_to_an_existing_file(name: str) -> None:
    resolved = resolve_builtin_pack_path(name)
    assert resolved.is_file(), f"BUILTIN_PACKS['{name}'] resolved to a missing file: {resolved}"


def test_resolve_builtin_pack_path_fails_closed_on_unknown_name() -> None:
    with pytest.raises(UnknownPackError):
        resolve_builtin_pack_path("no-such-pack")


def test_resolve_builtin_pack_path_fails_closed_on_missing_shipped_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A registered pack name whose shipped file is absent must raise, not
    silently return a nonexistent path."""
    import specify_cli.charter_pack_registry as registry

    monkeypatch.setitem(registry.BUILTIN_PACKS, "phantom", "A pack with no shipped file.")
    with pytest.raises(FileNotFoundError):
        registry.resolve_builtin_pack_path("phantom")
