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
