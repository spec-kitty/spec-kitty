"""Architectural gate: no committed provenance leaks an absolute built-in-pack path.

Locks in T011-T015 of mission ``operator-config-ergonomics-01M04YK8`` WP03
(contracts/provenance-and-channel.md C-PRV-5): the two committed provenance
carriers -- ``.kittify/charter/charter.yaml``'s ``catalog.references`` and
``.kittify/agent_profiles_manifest.json``'s entries -- must never store an
operator-/platform-specific absolute filesystem path for a built-in-pack
source. Empirically real before this WP: this very repository's committed
``charter.yaml`` carried a Linux path and its ``agent_profiles_manifest.json``
carried a macOS Homebrew wheel path (both healed by
``m_3_2_7_heal_provenance_paths``).

**Scan is PATTERN-based, not resolver-based.** ``charter.offering.provenance.
is_built_in_pack_path`` classifies against THIS process's OWN resolved
built-in pack root (``kernel.paths.get_built_in_pack_root()``) -- which,
inside a Spec Kitty lane worktree, differs from the path baked into a
committed file that originated from a sibling checkout (e.g. the primary
repository root). A resolver-based scan would silently pass over exactly
that drift. This gate instead matches the built-in-pack SHAPE textually
(``.../packs/built-in/...``, derived from the one owned kernel constant,
:data:`~kernel.paths.BUILT_IN_PACK_SIBLING_PATTERN` -- never hand-typed) on
any absolute ``source_path``, independent of which checkout is running the
test.

Issue #5253 extends the original C-PRV-6 scope to the built-in template-set
reference emitted by ``charter.activation.compiler._template_reference``.
The manifest's ``output_path`` remains excluded because it is a distinct,
repo-relative-only carrier; only manifest ``source_path`` is scanned.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

pytestmark = [pytest.mark.architectural]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CHARTER_YAML_PATH = _REPO_ROOT / ".kittify" / "charter" / "charter.yaml"
_MANIFEST_PATH = _REPO_ROOT / ".kittify" / "agent_profiles_manifest.json"


def _built_in_marker() -> str:
    """Return the ``packs/built-in/`` textual marker, derived from the owned kernel constant."""
    from kernel.paths import BUILT_IN_PACK_SIBLING_PATTERN

    return f"{BUILT_IN_PACK_SIBLING_PATTERN.as_posix()}/"


def _is_absolute_built_in_shape(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    if not Path(value).is_absolute():
        return False
    return _built_in_marker() in value.replace("\\", "/")


def _catalog_violations() -> list[str]:
    if not _CHARTER_YAML_PATH.exists():
        return []
    document = YAML(typ="safe").load(_CHARTER_YAML_PATH.read_text(encoding="utf-8")) or {}
    catalog = document.get("catalog") if isinstance(document, dict) else None
    references = catalog.get("references") if isinstance(catalog, dict) else None
    if not isinstance(references, list):
        return []

    violations: list[str] = []
    for ref in references:
        if not isinstance(ref, dict):
            continue
        source_path = ref.get("source_path")
        if _is_absolute_built_in_shape(source_path):
            violations.append(f"charter.yaml catalog[{ref.get('id', '?')}].source_path={source_path!r}")
    return violations


def _manifest_violations() -> list[str]:
    if not _MANIFEST_PATH.exists():
        return []
    raw: dict[str, Any] = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    entries = raw.get("entries")
    if not isinstance(entries, list):
        return []

    violations: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        source_path = entry.get("source_path")
        if _is_absolute_built_in_shape(source_path):
            urn = entry.get("profile_urn", "?")
            tool = entry.get("tool_key", "?")
            violations.append(f"agent_profiles_manifest.json[{urn}/{tool}].source_path={source_path!r}")
    return violations


def test_charter_yaml_and_manifest_exist_and_are_scanned() -> None:
    """Non-vacuity: the two carriers this gate scans are real, committed files."""
    assert _CHARTER_YAML_PATH.is_file(), f"expected {_CHARTER_YAML_PATH} to exist"
    assert _MANIFEST_PATH.is_file(), f"expected {_MANIFEST_PATH} to exist"


def test_no_absolute_built_in_pack_path_in_charter_yaml_catalog() -> None:
    violations = _catalog_violations()
    assert violations == [], (
        "charter.yaml catalog references leak an absolute built-in-pack "
        "source_path (C-PRV-5). Run `spec-kitty migrate` to apply "
        "m_3_2_7_heal_provenance_paths.\nViolations:\n" + "\n".join(f"  {v}" for v in violations)
    )


def test_no_absolute_built_in_pack_path_in_agent_profiles_manifest() -> None:
    violations = _manifest_violations()
    assert violations == [], (
        "agent_profiles_manifest.json entries leak an absolute built-in-pack "
        "source_path (C-PRV-5). Run `spec-kitty migrate` to apply "
        "m_3_2_7_heal_provenance_paths.\nViolations:\n" + "\n".join(f"  {v}" for v in violations)
    )


def test_template_set_reference_is_emitted_as_portable_token() -> None:
    """Issue #5253 extends the provenance normalizer to built-in template sets."""
    document = YAML(typ="safe").load(_CHARTER_YAML_PATH.read_text(encoding="utf-8")) or {}
    references = document["catalog"]["references"]
    template_refs = [r for r in references if isinstance(r, dict) and r.get("kind") == "template_set"]

    assert template_refs, "expected at least one template_set reference in charter.yaml (test non-vacuity)"
    assert template_refs[0].get("source_path") == ("${SPEC_KITTY_PACKS_ROOT}/built-in/missions/software-dev/mission.yaml")
