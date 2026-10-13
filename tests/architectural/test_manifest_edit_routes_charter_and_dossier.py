"""Router-parity gate (issue #6125): a mission-manifest edit selects charter + dossier.

A change to a mission's ``packs/built-in/missions/<type>/expected-artifacts.yaml`` is
owned by ``charter.offering.missions`` and consumed by ``charter.activation`` and
``dossier.ManifestRegistry`` (``src/specify_cli/dossier/manifest.py``). Per the charter
blast-radius rule such an edit must run ``tests/charter`` (+``tests/charter_offering``)
**and** ``tests/dossier`` green before merge. Before this gate, the per-PR path router
(``scripts/ci/gate_selection.py``) selected ZERO modules for such an edit — only the
non-module ``corpus`` group matched and ``unmatched_src`` was ``False``, so neither the
``charter`` module nor anything covering ``tests/dossier`` ran per-PR. A broken
charter/dossier manifest assertion could therefore ship green to red ``main``.

This is the non-vacuous pin the issue asks for: it asserts the real routing authority
``select_modules`` selects the ``charter`` AND ``dossier`` modules for a representative
manifest diff (all four manifests), proves the gate flips red when the routing glob is
removed (self-break), and proves the fix stays file-specific — a non-manifest corpus file
(``packs/built-in/missions/foo.md``) must still select zero code shards, so the fix cannot
be a broad ``packs/**`` over-match.
"""

from __future__ import annotations

import dataclasses

import pytest

from scripts.ci.gate_selection import Router, load_router, select_gates, select_modules

pytestmark = pytest.mark.architectural

#: The mission manifests on ``main``. Each is owned by ``charter.offering.missions`` and
#: consumed by the ``charter`` and ``dossier`` modules.
MANIFEST_PATHS = (
    "packs/built-in/missions/software-dev/expected-artifacts.yaml",
    "packs/built-in/missions/research/expected-artifacts.yaml",
    "packs/built-in/missions/plan/expected-artifacts.yaml",
    "packs/built-in/missions/documentation/expected-artifacts.yaml",
)

#: The modules a mission-manifest edit must select per-PR (issue #6125).
REQUIRED_MODULES = frozenset({"charter", "dossier"})

#: The glob that routes a manifest edit to the charter/dossier groups. File-specific on
#: purpose: a broad ``packs/built-in/missions/**`` would over-match corpus files and
#: pollute the canonical test mirror (``tests/missions``).
MANIFEST_GLOB = "packs/built-in/missions/**/expected-artifacts.yaml"


@pytest.mark.parametrize("manifest", MANIFEST_PATHS)
def test_manifest_edit_selects_charter_and_dossier(manifest: str) -> None:
    """FR-001 / SC-001: each mission-manifest diff selects the charter AND dossier modules."""
    selected = select_modules([manifest])
    missing = REQUIRED_MODULES - selected
    assert not missing, f"manifest {manifest!r} did not select {sorted(missing)} (selected {sorted(selected)})"


def _router_without_manifest_glob() -> Router:
    """The live router with the manifest glob stripped from every routing group."""
    router = load_router()
    stripped = {group: tuple(g for g in globs if g != MANIFEST_GLOB) for group, globs in router.filters.items()}
    return dataclasses.replace(router, filters=stripped)


def test_gate_is_non_vacuous_self_break() -> None:
    """Removing the manifest glob from the router flips the selection red.

    Proves the gate is a real bound, not a tautology: with the glob present the manifest
    selects charter+dossier; with it removed, it does not.
    """
    manifest = MANIFEST_PATHS[0]
    assert select_modules([manifest]) >= REQUIRED_MODULES, "precondition: live router must route the manifest"

    without = _router_without_manifest_glob()
    selected = select_modules([manifest], router=without)
    assert not (selected >= REQUIRED_MODULES), (
        "self-break failed: the manifest still selected charter+dossier with the glob removed — "
        f"selected {sorted(selected)} (the gate would pass against a router that does not route the manifest)"
    )


def test_non_manifest_corpus_file_still_selects_zero_code_shards() -> None:
    """C-002: the fix is file-specific — a non-manifest corpus file routes to no code shard.

    Mirrors ``test_gate_selection_authority.py::test_corpus_only_diff_selects_zero_code_shards``;
    guards against the fix broadening to the whole ``packs/built-in/missions/**`` tree.
    """
    selection = select_gates(["packs/built-in/missions/foo.md"])
    assert selection.selected_code_shards == frozenset()
    assert not selection.unmatched_src
    assert select_modules(["packs/built-in/missions/foo.md"]) == frozenset()
