"""The mission-type capability contract is on the offering seam (#6331, FR-001..FR-008).

Before this mission a consumer that may only import from ``charter.offering.api`` could not
read a mission type's ``wp_driven`` / ``requires_substantive_spec`` capabilities without
importing ``charter.activation.mission_type_profiles``. The seam now carries the *contract* —
a frozen value object, a runtime-checkable protocol and one read function — while the
activation resolver stays in ``charter.activation`` (ADR 2026-10-16-1, Amendment 2026-10-19:
``charter.offering`` has no code dependency on ``charter.activation``).

This module is the binding gate for the new census ``PUBLIC`` row: the capability names are
imported from ``charter.offering.api`` only, and the resolved bundles come from the
activation tier the consumer already owns.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from charter.offering.api import (
    MissionTypeCapabilities,
    MissionTypeCapabilitySource,
    capabilities_of,
)

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_config(repo_root: Path, activations: list[str]) -> None:
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    lines = "\n".join(f"  - {mt}" for mt in activations)
    (kittify / "config.yaml").write_text(f"mission_type_activations:\n{lines}\n", encoding="utf-8")


def _resolve(repo_root: Path, mission_type: str):
    from charter.activation.mission_type_profiles import resolve_mission_type_context

    return resolve_mission_type_context(repo_root, mission_type=mission_type)


# ---------------------------------------------------------------------------
# FR-001 / FR-004 — the seam carries the contract and the built-ins read through it
# ---------------------------------------------------------------------------


def test_capability_symbols_are_on_the_seam_manifest() -> None:
    """Every capability symbol is listed on ``charter.offering.api.__all__`` (FR-001)."""
    import charter.offering.api as api

    for name in ("MissionTypeCapabilities", "MissionTypeCapabilitySource", "capabilities_of"):
        assert name in api.__all__, f"{name} is missing from charter.offering.api.__all__"
        assert getattr(api, name) is not None


@pytest.mark.parametrize(
    ("mission_type", "expected"),
    [
        ("software-dev", (True, True)),
        ("research", (False, True)),
        ("documentation", (False, False)),
        ("plan", (False, False)),
    ],
)
def test_builtin_capabilities_read_through_the_seam(tmp_path: Path, mission_type: str, expected: tuple[bool, bool]) -> None:
    """A seam-only consumer reads both capabilities for every built-in family (US-1, SC-001)."""
    _write_config(tmp_path, [mission_type])
    bundle = _resolve(tmp_path, mission_type)

    snapshot = capabilities_of(bundle)
    assert (snapshot.wp_driven, snapshot.requires_substantive_spec) == expected
    # The DTO hands back the seam's value object, and both roads agree: the seam is a second
    # door, never a second source of truth.
    assert isinstance(bundle.capabilities, MissionTypeCapabilities)
    assert bundle.capabilities == snapshot
    assert (bundle.wp_driven, bundle.requires_substantive_spec) == expected


def test_resolved_bundle_satisfies_the_protocol(tmp_path: Path) -> None:
    """A resolved mission type *is* a capability source structurally (FR-002 / FR-004)."""
    _write_config(tmp_path, ["software-dev"])
    bundle = _resolve(tmp_path, "software-dev")

    assert isinstance(bundle, MissionTypeCapabilitySource)
    assert isinstance(capabilities_of(bundle), MissionTypeCapabilities)


# ---------------------------------------------------------------------------
# FR-002 / FR-003 — the protocol check and the read are not vacuous
# ---------------------------------------------------------------------------


class _OnlyWpDriven:
    """A source that answers one capability only — the negative control."""

    __slots__ = ()

    @property
    def wp_driven(self) -> bool:
        return True


def test_protocol_rejects_a_source_missing_a_capability() -> None:
    """The runtime-checkable protocol is not satisfied by a partial source (FR-002)."""
    assert isinstance(_OnlyWpDriven(), MissionTypeCapabilitySource) is False


def test_capabilities_of_fails_loud_on_a_non_conforming_source() -> None:
    """A partial source raises instead of silently defaulting a capability to False (FR-003)."""
    with pytest.raises(AttributeError):
        capabilities_of(_OnlyWpDriven())  # type: ignore[arg-type]


def test_value_object_is_frozen_and_compares_by_value() -> None:
    """The snapshot is an immutable value, not a mutable carrier (FR-001)."""
    default = MissionTypeCapabilities()
    assert (default.wp_driven, default.requires_substantive_spec) == (False, False)

    left = MissionTypeCapabilities(wp_driven=True, requires_substantive_spec=False)
    right = MissionTypeCapabilities(wp_driven=True, requires_substantive_spec=False)
    assert left == right
    assert hash(left) == hash(right)

    with pytest.raises(dataclasses.FrozenInstanceError):
        left.wp_driven = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# FR-008 — the edge cases the contract pins
# ---------------------------------------------------------------------------


def test_typeless_mission_reads_both_capabilities_false(tmp_path: Path) -> None:
    """A typeless mission yields the conservative answer and never raises (FR-008)."""
    from charter.activation.mission_type_profiles import resolve_mission_type_context

    bundle = resolve_mission_type_context(tmp_path)
    assert bundle.mission_type is None
    snapshot = capabilities_of(bundle)
    assert (snapshot.wp_driven, snapshot.requires_substantive_spec) == (False, False)


@dataclasses.dataclass(frozen=True)
class _StubPack:
    pack_roots: tuple[Path, ...]
    repo_root: Path


def test_custom_type_declaring_substantive_spec_reads_true(tmp_path: Path) -> None:
    """An authored ``requires_substantive_spec: true`` wins over the conservative default (FR-008)."""
    from charter.offering.missions.mission_type_repository import resolve_layered_mission_types

    org = tmp_path / "org"
    (org / "mission_types").mkdir(parents=True)
    (org / "mission_types" / "qa.yaml").write_text(
        "schema_version: 1\nid: qa\ndisplay_name: Qa\nrequires_substantive_spec: true\n",
        encoding="utf-8",
    )
    (org / "missions" / "qa").mkdir(parents=True)
    (org / "missions" / "qa" / "mission-runtime.yaml").write_text(
        "mission:\n  key: qa\nsteps:\n" + "".join(f"  - id: {s}\n    title: {s}\n" for s in ("specify", "implement", "review")),
        encoding="utf-8",
    )
    ctx = _StubPack(pack_roots=(Path("/nonexistent-builtin-pack"), org), repo_root=org / "repo")
    resolve_layered_mission_types.cache_clear()
    try:
        with (
            patch(
                "charter.activation.mission_type_profiles.existing_mission_types",
                return_value=["qa"],
            ),
            patch("charter.activation.pack_context.PackContext.from_config", return_value=ctx),
        ):
            bundle = _resolve(tmp_path / "repo", "qa")
    finally:
        resolve_layered_mission_types.cache_clear()

    snapshot = capabilities_of(bundle)
    assert snapshot.wp_driven is True  # the action sequence declares ``implement``
    assert snapshot.requires_substantive_spec is True


# ---------------------------------------------------------------------------
# FR-007 / NFR-002 / C-001 — the offering tier does not reach into activation
# ---------------------------------------------------------------------------

_PROBE = """
import sys
import {module}
print(",".join(sorted(m for m in sys.modules if m == "charter.activation" or m.startswith("charter.activation."))))
"""


def _activation_modules_after_importing(module: str) -> list[str]:
    """Import ``module`` in a fresh interpreter and report the activation modules it pulled in."""
    completed = subprocess.run(
        [sys.executable, "-c", _PROBE.format(module=module)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [name for name in completed.stdout.strip().split(",") if name]


def test_importing_the_contract_pulls_in_no_activation_module() -> None:
    """The contract module is offering-tier: importing it registers no activation module (FR-007)."""
    assert _activation_modules_after_importing("charter.offering.missions.capabilities") == []


def test_the_activation_probe_sees_activation_when_it_is_there() -> None:
    """Positive control: the same probe reports activation for a module that does import it."""
    assert _activation_modules_after_importing("charter.activation.mission_type_profiles")


def test_the_contract_module_imports_nothing_from_activation() -> None:
    """Static half of the boundary proof: no ``charter.activation`` import in the module (C-001)."""
    from charter.offering.missions import capabilities

    tree = ast.parse(inspect.getsource(capabilities))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    offenders = sorted(name for name in imported if name == "charter.activation" or name.startswith("charter.activation."))
    assert offenders == []
