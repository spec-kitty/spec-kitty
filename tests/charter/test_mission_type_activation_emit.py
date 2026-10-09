"""ATDD for charter generation emitting ``mission_type_activations``.

WP04 (charter-activation-authority) made the provisioned charter the SOLE
mission-type activation authority. Construction returns an EMPTY activation
set on an absent ``mission_type_activations`` key (no all-four backfill); the
fail-closed fires at the mission-CREATE boundary. But the charter *generation*
path never emitted that key, so a pointer-based charter (``config.yaml``
``charter:`` pointer -> ``charter.yaml``) that predates the provisioning
feature offered NO mission types (mission-create on it fails closed).

These tests pin ``charter.activation.compiler.provision_mission_type_activations`` — the
non-crashing, additive provisioning primitive that emits the built-in mission
type set into the activation authority (the pointer-resolved ``charter.yaml``
for a migrated project, or ``config.yaml`` for a legacy one), mirroring
``src/charter/activation/packs/default.yaml``'s authored ``mission_type_activations`` list.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.activation.compiler import provision_mission_type_activations
from charter.activation.default_pack import load_default_mission_type_activations
from charter.activation.pack_context import PackContext


pytestmark = [pytest.mark.fast]


_POINTER_CONFIG = """\
vcs:
  type: git
charter: .kittify/charter/charter.yaml
"""

# A migrated charter.yaml that predates the WP04 provisioning key: it carries
# per-kind activation but NO ``mission_type_activations`` (the exact broken
# shape of the dogfood checkout before regeneration).
_CHARTER_YAML_WITHOUT_KEY = """\
schema_version: "2.0.0"
governance:
  testing: {}
directives: []
catalog: {}
activated_kinds:
  - directives
activated_directives:
  - 001-architectural-integrity-standard
metadata:
  bundle_schema_version: 2
"""


def _write_pointer_project(tmp_path: Path, charter_body: str) -> Path:
    kittify = tmp_path / ".kittify"
    charter_dir = kittify / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(_POINTER_CONFIG, encoding="utf-8")
    (charter_dir / "charter.yaml").write_text(charter_body, encoding="utf-8")
    return charter_dir / "charter.yaml"


def _load(path: Path) -> dict:
    return YAML(typ="safe").load(path.read_text(encoding="utf-8"))


def _builtin_mission_types() -> list[str]:
    return load_default_mission_type_activations()


def test_provision_emits_builtin_set_into_pointer_charter(tmp_path: Path) -> None:
    """A pointer charter that lacks the key gains the default.yaml built-in set."""
    charter_path = _write_pointer_project(tmp_path, _CHARTER_YAML_WITHOUT_KEY)

    written = provision_mission_type_activations(tmp_path)

    assert written is True
    doc = _load(charter_path)
    assert doc["mission_type_activations"] == _builtin_mission_types()
    # The built-in set is exactly the four shipped mission types.
    assert doc["mission_type_activations"] == [
        "software-dev",
        "documentation",
        "research",
        "plan",
    ]


def test_provisioned_charter_is_readable_by_pack_context(tmp_path: Path) -> None:
    """After provisioning, ``PackContext.from_config`` no longer fail-closes."""
    _write_pointer_project(tmp_path, _CHARTER_YAML_WITHOUT_KEY)

    provision_mission_type_activations(tmp_path)

    ctx = PackContext.from_config(tmp_path)
    assert ctx.activated_mission_types == frozenset(_builtin_mission_types())


def test_provision_is_additive_noop_when_present(tmp_path: Path) -> None:
    """An already-provisioned (even custom) key is never overwritten."""
    body = _CHARTER_YAML_WITHOUT_KEY + "mission_type_activations:\n  - research\n"
    charter_path = _write_pointer_project(tmp_path, body)

    written = provision_mission_type_activations(tmp_path)

    assert written is False
    assert _load(charter_path)["mission_type_activations"] == ["research"]


def test_provision_respects_explicit_empty_optout(tmp_path: Path) -> None:
    """An explicit ``mission_type_activations: []`` opt-out is preserved."""
    body = _CHARTER_YAML_WITHOUT_KEY + "mission_type_activations: []\n"
    charter_path = _write_pointer_project(tmp_path, body)

    written = provision_mission_type_activations(tmp_path)

    assert written is False
    assert _load(charter_path)["mission_type_activations"] == []


def test_provision_writes_config_for_legacy_project(tmp_path: Path) -> None:
    """No ``charter:`` pointer -> the authority is ``config.yaml`` itself."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True)
    (kittify / "config.yaml").write_text("vcs:\n  type: git\n", encoding="utf-8")

    written = provision_mission_type_activations(tmp_path)

    assert written is True
    doc = _load(kittify / "config.yaml")
    assert doc["mission_type_activations"] == _builtin_mission_types()
