"""The ``code_producing`` capability on a resolved charter-offering mission type (#6327 / #6328).

Covers the capability contract the review-readiness pre-flight consumes:

* built-in defaults (``software-dev`` true; ``research`` / ``documentation`` / ``plan`` false);
* a charter-pack / org / project type may declare its own value;
* an undeclared custom type is conservatively ``false``;
* the neutral (typeless) bundle answers ``false`` and never raises;
* resolution failures fall back to the built-in default instead of raising;
* the facet is resolved lazily and memoised, so the ``action_sequence`` hot path
  pays nothing for it.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from charter.activation.api import code_producing_for as api_code_producing_for
from charter.activation.mission_type_profiles import (
    BUILTIN_CODE_PRODUCING,
    BUILTIN_REQUIRES_SUBSTANTIVE_SPEC,
    _neutral_context,
    code_producing_for,
    resolve_mission_type_context,
)
from charter.offering.missions.capabilities import BUILTIN_TYPE_CAPABILITIES
from charter.offering.missions.models import MissionType

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


def _write_config(repo_root: Path, activations: list[str]) -> None:
    """Activate *activations* for *repo_root* (the ``#6315`` capability fixture)."""
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    lines = "\n".join(f"  - {mt}" for mt in activations)
    (kittify / "config.yaml").write_text(f"mission_type_activations:\n{lines}\n", encoding="utf-8")


@dataclass(frozen=True)
class _StubPack:
    pack_roots: tuple[Path, ...]
    repo_root: Path


# ---------------------------------------------------------------------------
# FR-002: built-in defaults
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mission_type", "expected"),
    [
        ("software-dev", True),
        ("research", False),
        ("documentation", False),
        ("plan", False),
    ],
)
def test_builtin_code_producing_defaults(tmp_path: Path, mission_type: str, expected: bool) -> None:
    """FR-002: the four built-in families resolve their documented capability."""
    _write_config(tmp_path, [mission_type])
    bundle = resolve_mission_type_context(tmp_path, mission_type=mission_type)
    assert bundle.code_producing is expected
    assert code_producing_for(tmp_path, mission_type) is expected


def test_builtin_map_is_the_single_owning_list() -> None:
    """NFR-004: one capability table, four built-in keys, boolean values only."""
    assert dict(BUILTIN_CODE_PRODUCING) == {
        "software-dev": True,
        "research": False,
        "documentation": False,
        "plan": False,
    }
    assert all(isinstance(value, bool) for value in BUILTIN_CODE_PRODUCING.values())
    # The activation-side map is derived from the offering-layer table, not a
    # second enumeration: the two cannot drift.
    assert dict(BUILTIN_CODE_PRODUCING) == {mission_type: capabilities["code_producing"] for mission_type, capabilities in BUILTIN_TYPE_CAPABILITIES.items()}
    assert dict(BUILTIN_REQUIRES_SUBSTANTIVE_SPEC) == {
        mission_type: capabilities["requires_substantive_spec"] for mission_type, capabilities in BUILTIN_TYPE_CAPABILITIES.items()
    }


# ---------------------------------------------------------------------------
# FR-001 / FR-003: the DTO field and declared-value precedence
# ---------------------------------------------------------------------------


def test_mission_type_declares_the_field_tri_state() -> None:
    """FR-001: the authored descriptor carries a tri-state ``code_producing``.

    ``MissionType`` is ``extra="forbid"``, so the field existing on the model is
    what lets a YAML descriptor set it at all.
    """
    assert "code_producing" in MissionType.model_fields
    undeclared = MissionType(schema_version=1, id="qa", display_name="Qa")
    assert undeclared.code_producing is None
    assert MissionType(schema_version=1, id="qa", display_name="Qa", code_producing=True).code_producing is True
    assert MissionType(schema_version=1, id="qa", display_name="Qa", code_producing=False).code_producing is False


def _resolve_org_layer_type(
    tmp_path: Path,
    *,
    mission_type: str,
    mission_type_yaml: str,
) -> tuple[Any, bool]:
    """Resolve *mission_type* declared in a throwaway org-layer pack.

    Mirrors the fixture shape used by
    ``tests/charter/test_resolved_mission_type_context.py``
    (``TestCapabilityFacets.test_custom_type_capabilities``): a real org pack on
    disk, with only the two project-config seams patched, so the layered roster
    read is real rather than stubbed.
    """
    from charter.offering.missions.mission_type_repository import resolve_layered_mission_types

    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    org = tmp_path / "org"
    (org / "mission_types").mkdir(parents=True, exist_ok=True)
    (org / "mission_types" / f"{mission_type}.yaml").write_text(mission_type_yaml, encoding="utf-8")
    (org / "missions" / mission_type).mkdir(parents=True, exist_ok=True)
    steps = "".join(f"  - id: {step}\n    title: {step}\n" for step in ("specify", "implement", "review"))
    (org / "missions" / mission_type / "mission-runtime.yaml").write_text(
        f"mission:\n  key: {mission_type}\nsteps:\n{steps}",
        encoding="utf-8",
    )
    ctx = _StubPack(pack_roots=(Path("/nonexistent-builtin-pack"), org), repo_root=org / "repo")

    resolve_layered_mission_types.cache_clear()
    try:
        with (
            patch(
                "charter.activation.mission_type_profiles.existing_mission_types",
                return_value=[mission_type],
            ),
            patch(
                "charter.activation.pack_context.PackContext.from_config",
                return_value=ctx,
            ),
        ):
            bundle = resolve_mission_type_context(repo, mission_type=mission_type)
            # The public accessor re-resolves, so it must run inside the same
            # patched pack context to exercise the declared value.
            return bundle, code_producing_for(repo, mission_type)
    finally:
        resolve_layered_mission_types.cache_clear()


def test_custom_type_declaring_code_producing_true(tmp_path: Path) -> None:
    """FR-001: a custom type can declare ``code_producing: true``."""
    bundle, via_accessor = _resolve_org_layer_type(
        tmp_path,
        mission_type="qa",
        mission_type_yaml="schema_version: 1\nid: qa\ndisplay_name: Qa\ncode_producing: true\n",
    )
    assert bundle.code_producing is True
    assert via_accessor is True


def test_custom_type_declaring_code_producing_false(tmp_path: Path) -> None:
    """FR-001: a custom type can declare ``code_producing: false``."""
    bundle, via_accessor = _resolve_org_layer_type(
        tmp_path,
        mission_type="qa",
        mission_type_yaml="schema_version: 1\nid: qa\ndisplay_name: Qa\ncode_producing: false\n",
    )
    assert bundle.code_producing is False
    assert via_accessor is False


def test_custom_type_declaring_nothing_is_conservatively_false(tmp_path: Path) -> None:
    """FR-003: an undeclared custom type does not silently gain code rigour."""
    bundle, via_accessor = _resolve_org_layer_type(
        tmp_path,
        mission_type="qa",
        mission_type_yaml="schema_version: 1\nid: qa\ndisplay_name: Qa\n",
    )
    assert bundle.code_producing is False
    assert via_accessor is False


# ---------------------------------------------------------------------------
# FR-004 / FR-005: public surface, neutral bundle
# ---------------------------------------------------------------------------


def test_accessor_is_public_through_the_activation_api_seam() -> None:
    """FR-005: the consumer reaches the capability via ``charter.activation.api``."""
    assert api_code_producing_for is code_producing_for


def test_neutral_bundle_answers_false_without_raising() -> None:
    """FR-004: the typeless bundle produces no code."""
    assert _neutral_context().code_producing is False


def test_unknown_mission_type_is_false(tmp_path: Path) -> None:
    """FR-003: an unknown type never gains code rigour through the fallback."""
    assert code_producing_for(tmp_path, "no-such-mission-type") is False


# ---------------------------------------------------------------------------
# NFR-001: resolution failure falls back to the built-in default
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("mission_type", "expected"), [("software-dev", True), ("qa", False)])
def test_resolution_failure_falls_back_to_builtin_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mission_type: str, expected: bool) -> None:
    """NFR-001: a raising resolver must not crash the consumer (which is a gate)."""

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("charter config is unreadable")

    monkeypatch.setattr("charter.activation.mission_type_profiles.resolve_mission_type_context", _boom)
    assert code_producing_for(tmp_path, mission_type) is expected


# ---------------------------------------------------------------------------
# NFR-002: lazy + memoised
# ---------------------------------------------------------------------------


def test_facet_is_thunk_backed_and_memoised() -> None:
    """NFR-002: the capability is deferred and memoised, not computed eagerly.

    A call-counted thunk stands in for the roster read: the bundle must be
    constructible without firing it (the ``action_sequence`` hot path), fire it
    exactly once on first read, and not again afterwards.
    """
    calls: list[int] = []

    def _thunk() -> bool:
        calls.append(1)
        return True

    bundle = dataclasses.replace(
        _neutral_context(),
        mission_type="qa",
        _code_producing_thunk=_thunk,
    )
    assert calls == [], "constructing the bundle must not read the roster"
    assert bundle.code_producing is True
    assert len(calls) == 1
    assert bundle.code_producing is True
    assert len(calls) == 1, "the facet must be memoised"


def test_action_sequence_hot_path_does_not_fire_the_capability(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-002: reading only ``action_sequence`` performs no capability read."""
    fired: list[str] = []

    def _spy(*_args: object, **_kwargs: object) -> bool:
        fired.append("resolved")
        return True

    monkeypatch.setattr(
        "charter.activation.mission_type_profiles._resolve_code_producing",
        _spy,
    )
    _write_config(tmp_path, ["software-dev"])
    bundle = resolve_mission_type_context(tmp_path, mission_type="software-dev")
    _ = bundle.action_sequence
    assert fired == [], "the action_sequence hot path must not resolve the capability"
    assert bundle.code_producing is True
    assert fired == ["resolved"]
