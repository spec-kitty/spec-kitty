"""Provenance-completeness gate for the committed shard timings (FR-015, FR-016).

``.github/ci-shard-timings.json`` carries one ``module_capture_provenance`` record per
module. A module whose record is missing, or whose capture did not actually run the
suite, has timings nobody can trust: the shard balancing then rests on numbers of
unknown origin. This gate requires every ``.github/ci-module-registry.yml`` module to
carry a record that passes :func:`scripts.ci.recapture_shard_timings.is_valid_capture`
(imported, never restated: one authority for "trustworthy capture", research D-11).

Shard counts are covered by the existing skew check in
``test_module_shard_registry.py``; this mission adds no second check. The paired
control at the bottom proves that check *fires*: a deliberately skewed duration set
fed to the very helpers it uses is rejected (FR-016).

Both data files are read lazily inside tests, never at import time.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

import pytest

from scripts.ci.capture_shard_timings import MODULE_NODE_DURATIONS_KEY, validate_module_tables
from scripts.ci.recapture_shard_timings import is_valid_capture
from tests.architectural.test_module_shard_registry import (
    _MAX_SKEW,
    _load_registry,
    _load_timings,
    _lpt_bin_pack,
    _modules,
    _skew_of,
)

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_PROVENANCE_KEY = "module_capture_provenance"

# Literal floor on the registry size, so an empty or truncated registry load cannot
# pass the completeness check vacuously. Read from `.github/ci-module-registry.yml`
# on 2026-10-04: 20 module rows. Raise it when a module is added; lowering it needs a
# reason (a module was removed from the registry).
_REGISTRY_MODULE_FLOOR = 20


def _provenance_records(timings: Mapping[str, Any]) -> Mapping[str, Any]:
    records = timings.get(_PROVENANCE_KEY)
    return records if isinstance(records, Mapping) else {}


def modules_without_valid_provenance(modules: list[str], timings: Mapping[str, Any]) -> list[str]:
    """The modules (in registry order) whose provenance record is missing or not a valid capture.

    The ONE checking helper: the real-data test and every mutation test call it, so a
    mutation proves the same code path the real gate runs.
    """
    records = _provenance_records(timings)
    return [module for module in modules if not is_valid_capture(records.get(module))]


def _registry_module_names() -> list[str]:
    return [str(row["module"]) for row in _modules(_load_registry())]


# ---------------------------------------------------------------------------
# The real gate (red until the measured capture lands every module's record)
# ---------------------------------------------------------------------------
def test_every_registry_module_has_valid_capture_provenance() -> None:
    """FR-015: no registry module may carry timings of unknown or invalid origin."""
    modules = _registry_module_names()
    timings = _load_timings()

    bad = modules_without_valid_provenance(modules, timings)

    assert not bad, (
        f"{len(bad)} of {len(modules)} registry module(s) lack a valid capture provenance record "
        f"(exit_code 0 or 1 and unique_tests_measured > 0): {bad}. Capture each with "
        "`python -m scripts.ci.capture_shard_timings --module <name> --write` "
        "(or `python -m scripts.ci.recapture_shard_timings capture --write`)."
    )


def test_registry_module_count_meets_the_literal_floor() -> None:
    """A registry that loads empty (or loses rows) must not let the check above pass vacuously."""
    modules = _registry_module_names()
    assert len(modules) >= _REGISTRY_MODULE_FLOOR, (
        f"registry yields {len(modules)} module(s), below the pinned floor of {_REGISTRY_MODULE_FLOOR}; "
        "an empty or truncated load would make the provenance check vacuous."
    )


# ---------------------------------------------------------------------------
# Self-mutation (Standing Order #5): same data, same helper, deliberately broken.
# ---------------------------------------------------------------------------
def _fully_valid_timings(modules: list[str]) -> dict[str, Any]:
    """A synthetic timings payload in which every module has a valid record."""
    return {_PROVENANCE_KEY: {module: {"exit_code": 0, "unique_tests_measured": 10, "producer": "scripts/ci/capture_shard_timings.py"} for module in modules}}


def test_checker_accepts_a_fully_valid_synthetic_payload() -> None:
    """Symmetry: the helper reports nothing when every record is valid (no false positives)."""
    modules = ["alpha", "bravo", "charlie"]
    assert modules_without_valid_provenance(modules, _fully_valid_timings(modules)) == []


def test_checker_returns_the_module_whose_record_is_deleted() -> None:
    modules = ["alpha", "bravo", "charlie"]
    timings = copy.deepcopy(_fully_valid_timings(modules))
    del timings[_PROVENANCE_KEY]["bravo"]

    assert modules_without_valid_provenance(modules, timings) == ["bravo"]


def test_checker_returns_the_module_with_a_failed_capture_exit_status() -> None:
    modules = ["alpha", "bravo", "charlie"]
    timings = copy.deepcopy(_fully_valid_timings(modules))
    timings[_PROVENANCE_KEY]["charlie"]["exit_code"] = 2  # interrupted / collection error

    assert modules_without_valid_provenance(modules, timings) == ["charlie"]


def test_checker_returns_the_module_that_measured_zero_tests() -> None:
    modules = ["alpha", "bravo", "charlie"]
    timings = copy.deepcopy(_fully_valid_timings(modules))
    timings[_PROVENANCE_KEY]["alpha"]["unique_tests_measured"] = 0

    assert modules_without_valid_provenance(modules, timings) == ["alpha"]


def test_checker_tolerates_a_payload_with_no_provenance_section() -> None:
    """A timings file with no provenance key at all fails every module, never raises."""
    assert modules_without_valid_provenance(["alpha", "bravo"], {}) == ["alpha", "bravo"]


# ---------------------------------------------------------------------------
# FR-016 paired control: the skew check that governs `shard_count` must fire.
# ---------------------------------------------------------------------------


def _skew_exceeds_ceiling(durations: list[float], shard_count: int) -> bool:
    """`test_module_shard_registry.test_inter_shard_skew_within_twenty_percent`'s verdict for one module.

    Composed from the helpers and ceiling that test imports and uses (`_lpt_bin_pack`,
    `_skew_of`, `_MAX_SKEW`); that test inlines the comparison, so this is the same
    expression, not a second skew rule.
    """
    return _skew_of(_lpt_bin_pack(durations, shard_count)) > _MAX_SKEW


def test_skew_check_rejects_a_deliberately_skewed_two_shard_module() -> None:
    """One 100 s test beside nine 1 s tests cannot balance across two shards (skew 91%)."""
    skewed = [100.0] + [1.0] * 9

    assert _skew_exceeds_ceiling(skewed, 2)


def test_skew_check_accepts_a_balanced_two_shard_module() -> None:
    """Symmetry: ten equal tests split evenly across two shards, so the control is not trivially red."""
    assert not _skew_exceeds_ceiling([1.0] * 10, 2)


# ---------------------------------------------------------------------------
# Identity-keyed table: the selector trusts it, so it must be self-consistent.
# The positional `module_test_durations` list is a DERIVED projection of it; a
# module whose two disagree would hand the selector one set of weights and the
# skew gate another. Only modules that carry identities are checked, so this
# gate is green while the legacy arrays are still being recaptured.
# ---------------------------------------------------------------------------


def _identity_keyed_modules(timings: Mapping[str, Any]) -> list[str]:
    table = timings.get(MODULE_NODE_DURATIONS_KEY)
    return list(table) if isinstance(table, Mapping) else []


def _inconsistent_identity_modules(modules: list[str], timings: Mapping[str, Any]) -> dict[str, str]:
    """``{module: why}`` for every identity-keyed module whose tables disagree with each other."""
    return {module: problem for module in modules if (problem := validate_module_tables(timings, module)) is not None}


def _half_migrated_modules(modules: list[str], timings: Mapping[str, Any]) -> list[str]:
    """Modules whose provenance claims node ids the table does not carry (or vice versa)."""
    records = _provenance_records(timings)
    keyed = set(_identity_keyed_modules(timings))
    half: list[str] = []
    for module in modules:
        record = records.get(module)
        claims = isinstance(record, Mapping) and isinstance(record.get("node_ids_measured"), int) and record.get("node_ids_measured") > 0
        if claims != (module in keyed):
            half.append(module)
    return half


def test_identity_keyed_modules_are_internally_consistent() -> None:
    """Wherever a module carries node ids, every derived table must agree with them."""
    timings = _load_timings()

    problems = _inconsistent_identity_modules(_identity_keyed_modules(timings), timings)

    assert not problems, "identity-keyed timings disagree with their derived projections: " + repr(problems)


def test_no_registry_module_carries_half_migrated_identity_data() -> None:
    """A capture that recorded node ids must keep them; a legacy capture must not claim them."""
    half = _half_migrated_modules(_registry_module_names(), _load_timings())
    assert not half, (
        f"half-migrated identity data for {half}: provenance claims node ids the {MODULE_NODE_DURATIONS_KEY} table does not carry "
        "(or the reverse). Recapture the module rather than deleting one side."
    )


def _keyed_payload() -> dict[str, Any]:
    """A synthetic, fully consistent identity-keyed module slice (the shape a capture writes)."""
    node_ids = ["tests/x/test_a.py::test_one", "tests/x/test_a.py::test_two"]
    return {
        MODULE_NODE_DURATIONS_KEY: {"alpha": dict.fromkeys(node_ids, 1.5)},
        "module_test_durations": {"alpha": [1.5, 1.5]},
        "module_test_count": {"alpha": 2},
        "module_duration_seconds": {"alpha": 3.0},
        "module_capture_provenance": {"alpha": {"exit_code": 0, "unique_tests_measured": 2, "node_ids_measured": 2}},
    }


def test_the_identity_consistency_gate_accepts_a_consistent_synthetic_payload() -> None:
    """Symmetry: the checker is not trivially red."""
    assert _inconsistent_identity_modules(["alpha"], _keyed_payload()) == {}
    assert _half_migrated_modules(["alpha"], _keyed_payload()) == []


@pytest.mark.parametrize(
    ("mutate", "needle"),
    [
        (lambda p: p["module_test_durations"].update({"alpha": [9.0, 1.5]}), "projection"),
        (lambda p: p["module_test_count"].update({"alpha": 3}), "module_test_count"),
        (lambda p: p["module_duration_seconds"].update({"alpha": 99.0}), "module_duration_seconds"),
        (lambda p: p["module_capture_provenance"].update({"alpha": {"exit_code": 0, "unique_tests_measured": 9}}), "unique_tests_measured"),
    ],
)
def test_the_identity_consistency_gate_fires_on_a_divergent_slice(mutate: Any, needle: str) -> None:
    payload = copy.deepcopy(_keyed_payload())
    mutate(payload)

    problems = _inconsistent_identity_modules(["alpha"], payload)
    assert "alpha" in problems
    assert needle in problems["alpha"]


def test_the_identity_consistency_gate_fires_on_a_negative_duration() -> None:
    payload = copy.deepcopy(_keyed_payload())
    payload[MODULE_NODE_DURATIONS_KEY]["alpha"]["tests/x/test_a.py::test_one"] = -1.0

    problems = _inconsistent_identity_modules(["alpha"], payload)
    assert "non-finite/negative" in problems["alpha"]


def test_the_half_migration_gate_fires_when_the_table_is_dropped() -> None:
    payload = copy.deepcopy(_keyed_payload())
    payload.pop(MODULE_NODE_DURATIONS_KEY)
    assert _half_migrated_modules(["alpha"], payload) == ["alpha"]


def test_the_half_migration_gate_fires_when_the_provenance_claim_is_dropped() -> None:
    payload = copy.deepcopy(_keyed_payload())
    payload["module_capture_provenance"]["alpha"] = {"exit_code": 0, "unique_tests_measured": 2}
    assert _half_migrated_modules(["alpha"], payload) == ["alpha"]
