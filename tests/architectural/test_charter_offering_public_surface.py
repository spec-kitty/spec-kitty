"""Doctrine public-surface gates (mission doctrine-public-api-surface, WP02).

This module enforces the ``doctrine/api.py`` public surface introduced by WP02
(FR-001, FR-007, FR-008, NFR-004). Three concerns:

* **Positive (FR-001):** every name in ``charter.offering.api.__all__`` is importable and
  non-None — the wheel would export a real, resolvable contract.
* **Disposition coupling (FR-001/FR-002):** every api symbol originates from a
  doctrine module-path tagged ``PUBLIC`` in the authoritative WP01 census
  manifest (``test_doctrine_census.DISPOSITION``). A ``FACADE-ONLY`` or
  ``TICKETED-BASELINE`` symbol must never leak into the wheel surface.
* **Negative (FR-007 / contract C6):** the WP01-sanctioned *no-public-door* set —
  the ``TICKETED-BASELINE`` doctrine paths, which have no clean charter door and
  are handled by the dead-symbol ratchet allowlist, not a facade — appears in
  neither ``charter.offering.api.__all__`` nor any ``charter.*`` facade ``__all__``.
  Facade modules are discovered **dynamically** (glob ``src/charter/*.py``) so the
  guard stays valid as WP03 adds ``charter.missions`` / ``charter.model_routing`` /
  ``charter.assets`` — a hard-coded facade list would run before WP03 and go stale.

The live-caller assertion (T007) is authored **tolerant** here: the charter
facades that re-export PUBLIC symbols *from ``charter.offering.api``* land in WP03, which
is not yet merged, so ``charter.offering.api`` has no facade importer today. See
``test_every_public_symbol_is_routed_through_a_facade`` for the tolerant form and
the strict post-WP03 shape it documents.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from specify_cli.ast_analysis.imports import extract_static_all
from tests.architectural.test_doctrine_census import DISPOSITION, TICKETED_BASELINE

pytestmark = [pytest.mark.architectural]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_ROOT = _REPO_ROOT / "src"
_CHARTER_GLOB = "charter/*.py"
_OFFERING_API = _SRC_ROOT / "charter" / "offering" / "api.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_api_module() -> object:
    """Import ``charter.offering.api`` (the surface under test)."""
    import charter.offering.api as api  # noqa: PLC0415 — imported at call time, not module import

    return api


def _api_import_origins() -> dict[str, str]:
    """Map each re-exported name in ``doctrine/api.py`` to its origin module.

    Parsed statically from the ``from charter.offering.… import …`` statements so the
    disposition-coupling gate checks the DECLARED origin, not a runtime alias.
    """
    tree = ast.parse(_OFFERING_API.read_text(encoding="utf-8"), filename=str(_OFFERING_API))
    origins: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            for alias in node.names:
                origins[alias.asname or alias.name] = node.module
    return origins


def _disposition_for_origin(origin_module: str) -> str | None:
    """Return the WP01 disposition for a doctrine origin module (longest-prefix).

    ``DISPOSITION`` keys the model-routing cluster at the package level
    (``charter.offering.model_task_routing``) while ``doctrine/api.py`` imports from the
    ``.evaluator`` / ``.loader`` submodules, so an exact match is insufficient —
    resolve by the longest key that the origin equals or is nested under.
    """
    best: str | None = None
    for key in DISPOSITION:
        matches = origin_module == key or origin_module.startswith(key + ".")
        if matches and (best is None or len(key) > len(best)):
            best = key
    return DISPOSITION[best] if best is not None else None


def _charter_facade_files() -> list[Path]:
    """Every ``src/charter/*.py`` facade module (discovered dynamically)."""
    return sorted(_SRC_ROOT.glob(_CHARTER_GLOB))


def _facade_all_names() -> set[str]:
    """Union of every ``charter.*`` module's static ``__all__`` (dynamic glob)."""
    names: set[str] = set()
    for path in _charter_facade_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        names.update(extract_static_all(tree))
    return names


def _module_public_defs(module_path: str) -> set[str]:
    """Module-scope public ``def``/``class`` names for a doctrine module path.

    ``charter.offering.drg.override_policy`` -> ``src/charter/offering/drg/override_policy.py``.
    Only ``FunctionDef`` / ``AsyncFunctionDef`` / ``ClassDef`` at module scope
    whose name does not start with ``_`` are returned (the callable/type surface
    that a leak would expose).
    """
    rel = Path(*module_path.split(".")).with_suffix(".py")
    file_path = _SRC_ROOT / rel
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    out: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not node.name.startswith("_"):
            out.add(node.name)
    return out


def _no_door_symbols() -> set[str]:
    """The WP01 ``TICKETED-BASELINE`` (no-public-door) symbol set."""
    symbols: set[str] = set()
    for module_path in TICKETED_BASELINE:
        symbols.update(_module_public_defs(module_path))
    return symbols


def _api_symbols_reexported_by_facades() -> set[str]:
    """Names any ``charter.*`` facade re-exports via ``from charter.offering.api import …``.

    Empty until WP03 wires the facades onto ``charter.offering.api`` — see the tolerant
    live-caller test below.
    """
    reexported: set[str] = set()
    for path in _charter_facade_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "charter.offering.api":
                reexported.update(alias.asname or alias.name for alias in node.names)
    return reexported


# ---------------------------------------------------------------------------
# Positive — FR-001
# ---------------------------------------------------------------------------


def test_public_surface_symbols_importable_and_non_none() -> None:
    """FR-001: every ``charter.offering.api.__all__`` name resolves to a non-None object."""
    api = _load_api_module()
    exported = list(getattr(api, "__all__", []))
    assert exported, "charter.offering.api.__all__ is empty — the public surface must enumerate PUBLIC symbols."
    missing = [name for name in exported if not hasattr(api, name)]
    assert not missing, f"charter.offering.api.__all__ names not importable from the module: {missing}"
    none_valued = [name for name in exported if getattr(api, name) is None]
    assert not none_valued, f"charter.offering.api.__all__ names resolve to None: {none_valued}"


def test_public_surface_all_is_sorted_and_unique() -> None:
    """The curated surface stays a sorted, duplicate-free manifest (reviewable diffs)."""
    api = _load_api_module()
    exported = list(getattr(api, "__all__", []))
    assert exported == sorted(exported), "charter.offering.api.__all__ must be sorted."
    assert len(exported) == len(set(exported)), "charter.offering.api.__all__ has duplicates."


# ---------------------------------------------------------------------------
# Disposition coupling — FR-001 / FR-002
# ---------------------------------------------------------------------------


def test_every_public_symbol_originates_from_a_public_disposition() -> None:
    """Every api symbol comes from a doctrine path tagged PUBLIC in WP01's census.

    Guards against a ``FACADE-ONLY`` / ``TICKETED-BASELINE`` / construction-routed
    symbol silently entering the wheel surface: the wheel exports only PUBLIC.
    """
    api = _load_api_module()
    origins = _api_import_origins()
    offenders: list[str] = []
    for name in getattr(api, "__all__", []):
        origin = origins.get(name)
        disposition = _disposition_for_origin(origin) if origin else None
        if disposition != "PUBLIC":
            offenders.append(f"{name} (origin={origin!r}, disposition={disposition!r})")
    assert not offenders, (
        "charter.offering.api.__all__ contains symbols whose origin is not PUBLIC in the "
        "WP01 census DISPOSITION — only PUBLIC-tagged paths belong on the wheel "
        "surface:\n  - " + "\n  - ".join(sorted(offenders))
    )


# ---------------------------------------------------------------------------
# Negative — FR-007 / contract C6
# ---------------------------------------------------------------------------


def test_charter_facades_are_discovered_dynamically() -> None:
    """Guard against a false-green negative test: the glob must find real facades.

    If ``src/charter/*.py`` ever globbed empty (a refactor moved the package),
    the negative assertions below would vacuously pass — this makes that loud.
    """
    facades = _charter_facade_files()
    assert facades, "No src/charter/*.py facade modules discovered — negative guard would be vacuous."
    assert _facade_all_names(), "No charter facade declares __all__ — negative guard would be vacuous."


def test_no_door_symbols_absent_from_public_surface_and_facades() -> None:
    """FR-007 / C6: WP01 no-door (TICKETED-BASELINE) symbols reach no public door.

    These doctrine-management internals (``charter.offering.drg.override_policy``,
    ``charter.offering.drg.migration.hand_authored_overlay``) have no clean charter door —
    WP01 handles them via the dead-symbol ratchet allowlist. They must appear in
    neither ``charter.offering.api.__all__`` nor any dynamically-discovered ``charter.*``
    facade ``__all__``.
    """
    assert TICKETED_BASELINE, "WP01 TICKETED_BASELINE is empty — the negative guard has no anchor."
    no_door = _no_door_symbols()
    assert no_door, "Resolved no-door symbol set is empty — check TICKETED_BASELINE path resolution."

    api = _load_api_module()
    api_all = set(getattr(api, "__all__", []))
    facade_all = _facade_all_names()

    in_api = sorted(no_door & api_all)
    in_facades = sorted(no_door & facade_all)
    assert not in_api, f"No-door doctrine symbols leaked into charter.offering.api.__all__: {in_api}"
    assert not in_facades, f"No-door doctrine symbols leaked into a charter facade __all__: {in_facades}"


# ---------------------------------------------------------------------------
# Live-caller (T007) — authored TOLERANT until WP03 lands the facades
# ---------------------------------------------------------------------------


def test_every_public_symbol_is_routed_through_a_facade() -> None:
    """T007 live-caller assertion — STRICT (post-WP03).

    The manifest's whole point is that PUBLIC symbols are fronted by charter
    facades that re-export them *from ``charter.offering.api``* (so ``charter.offering.api`` gets a
    live in-repo caller, not just object identity via the origin submodule). WP03
    (mission ``doctrine-public-api-surface-01KZPDSR``) built those facades:
    ``charter.drg`` re-exports ``ArtifactKind``, ``charter.assets`` the five asset
    symbols, and ``charter.model_routing`` the four routing symbols — every one
    ``from charter.offering.api import …``.

    Two invariants, both enforced now that WP03 has landed:

    * **Consistency:** every symbol a facade re-exports from ``charter.offering.api``
      names a real member of ``charter.offering.api.__all__`` — a typo or a dropped
      surface entry fails here immediately.
    * **Coverage (strict):** every symbol in ``charter.offering.api.__all__`` is
      re-exported from ``charter.offering.api`` by at least one charter facade, i.e.
      ``set(api.__all__) - _api_symbols_reexported_by_facades() == set()``. The
      tolerant pre-WP03 ``pytest.skip`` and the ``_SYMBOL_ALLOWLIST`` bridge
      (#3179) are both retired.
    """
    api = _load_api_module()
    api_all = set(getattr(api, "__all__", []))
    facade_reexports = _api_symbols_reexported_by_facades()

    unknown = sorted(facade_reexports - api_all)
    assert not unknown, f"A charter facade re-exports names from charter.offering.api that are absent from charter.offering.api.__all__ (surface drift): {unknown}"

    coverage_gap = sorted(api_all - facade_reexports)
    assert not coverage_gap, (
        "Every charter.offering.api PUBLIC symbol must be re-exported from charter.offering.api by "
        "at least one charter facade (so charter.offering.api has a live in-repo caller). "
        f"Symbols with no facade caller: {coverage_gap}"
    )
