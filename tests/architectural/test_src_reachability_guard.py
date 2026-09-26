"""Src-reachability honesty guard (FR-002) — two shrink-only baselines.

Enumerates every importable src package under the 6 wheel roots (fs-walk of
``__init__.py`` subpackages + loose top-level modules, data-only packages
excluded per F18) and partitions them against the committed MEASURED baseline in
``.github/ci-foreign-coverage-baseline.json``:

* **Truly-dark baseline (shrink-only, hard-fail on GROWTH)** — a package imported
  by NO test anywhere (in-matrix ∪ out-of-matrix ∪ nightly). The strongest
  honesty ratchet: no new untested-anywhere code may land. Seeded at the measured
  set (20 today: the raw pre-exclusion figure was 23, less the 3 named data
  packages). A hard zero-floor is unsatisfiable — static import analysis cannot
  see subprocess/CLI-tested modules (``specify_cli.__main__``, ``encoding``) — so
  the shrink-only baseline is the honest floor.
* **In-matrix-dark baseline (shrink-only)** — a package reachable by some
  out-of-matrix / nightly test but by no per-PR (in-matrix) test. Seeded at the
  measured set (27 today). Fails only on growth; WP02 remediation shrinks it.

The guard PASSES at baseline by construction. Synthetic grow-fail / shrink-pass
proofs live in ``tests/ci/test_coverage_guards.py``. Import-based, no test
execution; the whole-corpus parse is memoized once (NFR-002 5 s budget).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LIB_PATH = _REPO_ROOT / "scripts" / "ci" / "coverage_guard_lib.py"


def _load_lib() -> ModuleType:
    """Load ``scripts/ci/coverage_guard_lib.py`` by path (``scripts/ci`` is not
    an importable package — same pattern as ``test_sonar_project_version.py``)."""
    spec = importlib.util.spec_from_file_location("coverage_guard_lib", _LIB_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot build an import spec for {_LIB_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def lib() -> ModuleType:
    return _load_lib()


@pytest.fixture(scope="module")
def partition(lib: ModuleType) -> tuple[list[str], list[str]]:
    """(truly_dark, in_matrix_dark) computed once — the heavy whole-corpus scan."""
    return cast("tuple[list[str], list[str]]", lib.reachability_partition())


@pytest.fixture(scope="module")
def baseline(lib: ModuleType) -> dict[str, Any]:
    return cast("dict[str, Any]", lib.load_baseline())


def test_no_new_truly_dark_package(lib: ModuleType, partition: tuple[list[str], list[str]], baseline: dict[str, Any]) -> None:
    """Hard honesty ratchet: no NEW package tested nowhere may appear."""
    truly_dark, _ = partition
    grown = lib.grown_beyond_baseline(truly_dark, baseline["truly_dark_packages"])
    assert not grown, (
        "new truly-dark package(s) — imported by NO test anywhere (in-matrix, "
        f"out-of-matrix, or nightly): {grown}. Add a test that imports it (or "
        "delete the dead code); it may NOT be masked by the baseline."
    )


def test_no_new_in_matrix_dark_package(lib: ModuleType, partition: tuple[list[str], list[str]], baseline: dict[str, Any]) -> None:
    """Shrink-only: no NEW package becomes reachable only out-of-matrix/nightly."""
    _, in_matrix_dark = partition
    grown = lib.grown_beyond_baseline(in_matrix_dark, baseline["in_matrix_dark_packages"])
    assert not grown, (
        f"new in-matrix-dark package(s) — reachable only out-of-matrix / nightly, by no per-PR test: {grown}. Enroll its tests in a per-PR module row."
    )


def test_data_only_packages_are_excluded(lib: ModuleType) -> None:
    """F18: data-shipping packages (no testable module) are not enumerated."""
    packages = set(lib.enumerate_src_packages())
    for data_pkg in (
        "charter.activation.corpus",
        "charter.activation.packs",
        "specify_cli.skills.data",
    ):
        assert lib.is_data_only_package(data_pkg), f"{data_pkg} should be classified data-only (ships only data files)"
        assert data_pkg not in packages, f"{data_pkg} leaked into the enumeration"
    # ``schemas`` has no __init__.py and is excluded by construction.
    assert "specify_cli.schemas" not in packages


def test_enumeration_includes_real_packages_and_loose_modules(lib: ModuleType) -> None:
    """Enumeration is non-vacuous: real packages AND loose top-level modules."""
    packages = set(lib.enumerate_src_packages())
    assert "specify_cli.merge" in packages  # a real subpackage
    assert "specify_cli.mission" in packages  # a loose top-level *.py module
    assert len(packages) > 200, "enumeration collapsed — too few packages found"


def test_baselines_are_not_vacuous(baseline: dict[str, Any]) -> None:
    """A truncated / emptied baseline must not silently pass the growth ratchets."""
    assert baseline["truly_dark_packages"], "truly_dark baseline is empty"
    assert baseline["in_matrix_dark_packages"], "in_matrix_dark baseline is empty"
    # The subprocess/CLI-tested modules the honesty note names stay recorded.
    assert "specify_cli.__main__" in baseline["truly_dark_packages"]
