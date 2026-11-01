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
import copy
import dataclasses
import enum
import functools
import inspect
import sys
from pathlib import Path
from unittest.mock import patch

import pydantic
import pytest
import yaml

from specify_cli.ast_analysis.imports import extract_static_all
from tests.architectural.test_doctrine_census import (
    DISPOSITION,
    TICKETED_BASELINE,
    reached_offering_paths,
)

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


# ---------------------------------------------------------------------------
# Frozen census (#6285) — the one committed list the surface is pinned to
#
# ``charter_offering_public_surface.yaml`` is the frozen public contract (#6285,
# P1 of epic #6099). Per exported symbol it records: the module
# ``charter.offering.api`` imports it from, its disposition, the charter facades
# that front it, its runtime contract kind, today's hand-written type, and the
# ADR-0004 generated-DTO direction with today's types marked transitional.
#
# Each check is a pure ``(census) -> list[str]`` predicate so the
# planted-mutation self-test exercises the SAME predicate the real check runs
# (architectural-gate non-vacuity).
# ---------------------------------------------------------------------------

_CENSUS_PATH = Path(__file__).with_name("charter_offering_public_surface.yaml")

#: The facade import source the census routes symbols through by identity.
_FACADE_SOURCE = "charter.offering.api"

#: Dispositions that sanction a reached-but-not-public path (no public-contract
#: delta): a facade fronts it, the dead-symbol ratchet owns it, construction
#: routes it through the service, or it is package metadata.
_SANCTIONED_NON_PUBLIC = frozenset({"FACADE-ONLY", "TICKETED-BASELINE", "CONSTRUCTION-ROUTED", "INTERNAL-METADATA"})


def _load_census() -> dict:
    """Load the frozen census, failing loudly when it is absent or not a mapping."""
    assert _CENSUS_PATH.is_file(), (
        f"The frozen offering public-surface census is missing at {_CENSUS_PATH}. "
        "It is the canonical list `charter.offering.api.__all__` is pinned to (#6285); "
        "an absent census must never make the freeze vacuous."
    )
    data = yaml.safe_load(_CENSUS_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{_CENSUS_PATH.name} must parse to a mapping, got {type(data).__name__}."
    return data


def _surface_rows(census: dict) -> list[dict]:
    """The census ``surface`` rows (one per exported symbol)."""
    rows = census.get("surface")
    assert isinstance(rows, list) and rows, f"{_CENSUS_PATH.name} must carry a non-empty 'surface' list."
    return [row for row in rows if isinstance(row, dict)]


def _facade_reexport_map() -> dict[str, set[str]]:
    """Map each symbol to the ``charter.*`` facades importing it from the api surface.

    Derived from the facade modules' own ``from charter.offering.api import …``
    statements — the actual wiring whose object identity the facade gate proves.
    Copying ``_FACADE_TABLE`` here would be a second source of truth; this is the code.
    """
    mapping: dict[str, set[str]] = {}
    for path in _charter_facade_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == _FACADE_SOURCE:
                for alias in node.names:
                    mapping.setdefault(alias.asname or alias.name, set()).add(f"charter.{path.stem}")
    return mapping


@functools.cache
def _reached_path_consumers() -> dict[str, set[str]]:
    """Map each reached offering path to the repo-relative files that reach it.

    Cached per process: the authoritative census scan walks every module under
    ``src/specify_cli/`` and ``src/runtime/``, and re-running it per assertion would
    make this gate file pay that cost several times over.
    """
    consumers: dict[str, set[str]] = {}
    for source, paths in reached_offering_paths().items():
        for path in paths:
            consumers.setdefault(path, set()).add(str(source))
    return consumers


def _runtime_contract_kind(obj: object) -> str:
    """Classify a public-surface object by its runtime shape."""
    if inspect.isclass(obj):
        if isinstance(obj, enum.EnumMeta):
            return "enum"
        if issubclass(obj, BaseException):
            return "exception"
        if issubclass(obj, pydantic.BaseModel):
            return "model"
        if dataclasses.is_dataclass(obj):
            return "dataclass"
        if inspect.isabstract(obj):
            return "protocol"
        return "class"
    if inspect.isfunction(obj):
        return "function"
    return "constant"


def _name_set_problems(census: dict) -> list[str]:
    """Freeze (FR-002): the census list equals ``api.__all__`` in order, both directions."""
    api = _load_api_module()
    expected = list(getattr(api, "__all__", []))
    actual = [str(row.get("name")) for row in _surface_rows(census)]
    if actual == expected:
        return []
    problems: list[str] = []
    missing = [name for name in expected if name not in actual]
    unexported = [name for name in actual if name not in expected]
    duplicated = sorted({name for name in actual if actual.count(name) > 1})
    if missing:
        problems.append(f"census is missing exported symbols: {missing}")
    if unexported:
        problems.append(f"census lists symbols charter.offering.api does not export: {unexported}")
    if duplicated:
        problems.append(f"census lists symbols more than once: {duplicated}")
    if not problems:
        problems.append(f"census order {actual} does not match api.__all__ order {expected}")
    return problems


def _provenance_problems(census: dict) -> list[str]:
    """Provenance (FR-002/FR-005): origin and disposition agree with the code and the manifest."""
    origins = _api_import_origins()
    problems: list[str] = []
    for row in _surface_rows(census):
        name = str(row.get("name"))
        imported_from = origins.get(name)
        if imported_from is None:
            problems.append(f"{name}: charter.offering.api does not import it, so it has no origin")
            continue
        if row.get("origin") != imported_from:
            problems.append(f"{name}: census origin {row.get('origin')!r} != the imported module {imported_from!r}")
        disposition = _disposition_for_origin(imported_from)
        if row.get("disposition") != "PUBLIC":
            problems.append(f"{name}: census disposition {row.get('disposition')!r} is not PUBLIC")
        if disposition != "PUBLIC":
            problems.append(f"{name}: origin {imported_from!r} is {disposition!r} in the WP01 census, not PUBLIC")
    return problems


def _facade_problems(census: dict) -> list[str]:
    """Facade routing (FR-003): the recorded facades are the ones that actually re-export it."""
    mapping = _facade_reexport_map()
    if not mapping:
        return ["no charter facade re-exports anything from charter.offering.api — the facade comparison would be vacuous, so the census cannot be verified"]
    problems: list[str] = []
    for row in _surface_rows(census):
        name = str(row.get("name"))
        live = sorted(mapping.get(name, set()))
        recorded = sorted(str(facade) for facade in (row.get("facades") or []))
        if not live:
            problems.append(f"{name}: no charter facade re-exports it from {_FACADE_SOURCE}")
        elif recorded != live:
            problems.append(f"{name}: census facades {recorded} != live facades {live}")
    return problems


def _annotation_problems(census: dict) -> list[str]:
    """DTO-forward annotation (FR-004): kind, today's type, signature and the DTO direction."""
    api = _load_api_module()
    problems: list[str] = []
    for row in _surface_rows(census):
        name = str(row.get("name"))
        obj = getattr(api, name, None)
        if obj is None:
            problems.append(f"{name}: not importable from charter.offering.api")
            continue
        runtime_kind = _runtime_contract_kind(obj)
        if row.get("contract_kind") != runtime_kind:
            problems.append(f"{name}: contract_kind {row.get('contract_kind')!r} != runtime kind {runtime_kind!r}")
        for field in ("today_type", "dto_target"):
            if not str(row.get(field) or "").strip():
                problems.append(f"{name}: {field} must be a non-empty description")
        if row.get("dto_status") != "transitional":
            problems.append(
                f"{name}: dto_status {row.get('dto_status')!r} must be 'transitional' — nothing on this surface is "
                "final until the generated-DTO contract work lands (ADR-0004, #6218)"
            )
        expected_signature = str(inspect.signature(obj)) if inspect.isfunction(obj) else None
        if row.get("signature") != expected_signature:
            problems.append(f"{name}: signature {row.get('signature')!r} != live {expected_signature!r}")
    return problems


def _classification_problems(census: dict) -> list[str]:
    """Whole-picture classification (FR-005): reached paths, dispositions and the public delta."""
    consumers = _reached_path_consumers()
    if not consumers:
        return [
            "the live reached-path scan returned nothing — the classification and public-contract-delta "
            "checks would pass vacuously, so the census cannot be verified"
        ]
    rows = {str(row.get("path")): row for row in (census.get("reached_classification") or []) if isinstance(row, dict)}
    surface_origins = {str(row.get("origin")) for row in _surface_rows(census)}
    problems: list[str] = []
    for path in sorted(consumers):
        row = rows.get(path)
        if row is None:
            problems.append(f"{path}: reached from {sorted(consumers[path])} but absent from reached_classification")
            continue
        manifest_disposition = _disposition_for_origin(path)
        if row.get("disposition") != manifest_disposition:
            problems.append(f"{path}: disposition {row.get('disposition')!r} != the WP01 census {manifest_disposition!r}")
        on_surface = path in surface_origins
        if bool(row.get("on_surface")) != on_surface:
            problems.append(f"{path}: on_surface {row.get('on_surface')!r} != {on_surface!r} for the frozen surface")
        recorded_consumers = sorted(str(source) for source in (row.get("consumers") or []))
        if recorded_consumers != sorted(consumers[path]):
            problems.append(f"{path}: recorded consumers != live consumers {sorted(consumers[path])}")
        if not on_surface and not str(row.get("route") or "").strip():
            problems.append(f"{path}: a non-surface reached path must name its sanctioned route")
    unreached = sorted(set(rows) - set(consumers))
    if unreached:
        problems.append(f"reached_classification lists paths nothing reaches: {unreached}")

    computed_delta = sorted(path for path in consumers if path not in surface_origins and _disposition_for_origin(path) not in _SANCTIONED_NON_PUBLIC)
    declared_delta = sorted(str(path) for path in (census.get("public_contract_delta") or []))
    if computed_delta != declared_delta:
        problems.append(
            f"public_contract_delta {declared_delta} != the delta recomputed from the live tree {computed_delta} "
            "(a reached PUBLIC path absent from the frozen surface is a delta for operator approval, never a "
            "silent widening)"
        )
    return problems


def _census_problems(census: dict) -> list[str]:
    """Every freeze violation, from every predicate (the mutation test's single entry point)."""
    return _name_set_problems(census) + _provenance_problems(census) + _facade_problems(census) + _annotation_problems(census) + _classification_problems(census)


def test_census_enumerates_exactly_the_live_surface() -> None:
    """FR-002: ``api.__all__`` and the census name list are equal in both directions and in order."""
    problems = _name_set_problems(_load_census())
    assert not problems, "The frozen census and the live public surface have drifted:\n  - " + "\n  - ".join(problems)


def test_census_origin_and_disposition_match_the_module() -> None:
    """FR-002/FR-005: each row's origin is the module the api imports it from, and it is PUBLIC."""
    problems = _provenance_problems(_load_census())
    assert not problems, "Census provenance disagrees with the module or the disposition manifest:\n  - " + "\n  - ".join(problems)


def test_census_facades_match_the_identity_table() -> None:
    """FR-003: the recorded facades are exactly the ones importing the symbol from the surface."""
    problems = _facade_problems(_load_census())
    assert not problems, "Census facade routing disagrees with the facade wiring:\n  - " + "\n  - ".join(problems)


def test_every_surface_row_is_dto_forward_annotated() -> None:
    """FR-004: every row states its kind, today's type, signature and the generated-DTO direction."""
    problems = _annotation_problems(_load_census())
    assert not problems, "Census rows are not fully DTO-forward annotated:\n  - " + "\n  - ".join(problems)


def test_reached_paths_are_classified_and_delta_is_empty() -> None:
    """FR-005: every reached offering path is classified and the public-contract delta is empty."""
    problems = _classification_problems(_load_census())
    assert not problems, "Reached-path classification or the public-contract delta has drifted:\n  - " + "\n  - ".join(problems)


def test_census_checks_reject_planted_mutations() -> None:
    """Non-vacuity: each freeze predicate fails on a planted mutation of the committed census."""
    census = _load_census()
    baseline = _census_problems(census)
    assert not baseline, "Positive control failed: the committed census must be clean before mutations are planted:\n  - " + "\n  - ".join(baseline)

    dropped = copy.deepcopy(census)
    dropped["surface"] = dropped["surface"][:-1]
    assert _name_set_problems(dropped), "A dropped surface row must fail the name-set freeze."

    added = copy.deepcopy(census)
    added["surface"] = [*added["surface"], {**copy.deepcopy(census["surface"][-1]), "name": "NotExported"}]
    assert _name_set_problems(added), "A census row for an unexported name must fail the name-set freeze."

    wrong_origin = copy.deepcopy(census)
    wrong_origin["surface"][0]["origin"] = "charter.offering.nope"
    assert _provenance_problems(wrong_origin), "A wrong origin must fail the provenance check."

    wrong_facade = copy.deepcopy(census)
    wrong_facade["surface"][0]["facades"] = []
    assert _facade_problems(wrong_facade), "A dropped facade must fail the facade-routing check."

    final_type = copy.deepcopy(census)
    final_type["surface"][0]["dto_status"] = "final"
    assert _annotation_problems(final_type), "A row claiming a final hand-written type must fail the annotation check."

    wrong_signature = copy.deepcopy(census)
    wrong_signature["surface"][-1]["signature"] = "() -> 'int'"
    assert _annotation_problems(wrong_signature), "A changed callable signature must fail the annotation check."

    vanished_surface = copy.deepcopy(census)
    for row in vanished_surface["reached_classification"]:
        if row.get("on_surface"):
            row["on_surface"] = False
            break
    assert _classification_problems(vanished_surface), "A PUBLIC reached path hidden off the surface must fail the delta check."

    with patch.object(sys.modules[__name__], "_reached_path_consumers", return_value={}):
        assert _classification_problems(census), "An empty reached-path scan must fail, not pass the classification and delta checks vacuously."
