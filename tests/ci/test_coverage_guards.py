"""Unit tests for ``scripts/ci/coverage_guard_lib.py`` (WP01 T006, FR-001/FR-002).

Exercise the shared coverage-honesty analysis engine directly: the shrink-only
baseline logic (grow → fail, shrink → pass, equal → pass) for ALL THREE baselines
(dark-root, truly-dark, in-matrix-dark — all keyed on the same
``grown_beyond_baseline`` primitive), the own-root ratio ratchet, a
deferred/function-level import, the module-tests.yml resolver precedence,
subpackage enumeration (excludes data-only dirs, includes loose modules), the
data-package predicate, and ratio computation.

The module is loaded by file path (``scripts/ci`` is not an importable package —
mirrors ``tests/ci/test_sonar_project_version.py``).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LIB_PATH = _REPO_ROOT / "scripts" / "ci" / "coverage_guard_lib.py"


def _load_lib() -> ModuleType:
    spec = importlib.util.spec_from_file_location("coverage_guard_lib", _LIB_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot build an import spec for {_LIB_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def lib() -> ModuleType:
    return _load_lib()


# ---------------------------------------------------------------------------
# shrink-only baseline logic — the single primitive behind all three baselines
# (dark-root, truly-dark, in-matrix-dark)
# ---------------------------------------------------------------------------


def test_grown_beyond_baseline_grow_fails(lib: ModuleType) -> None:
    """A NEW member absent from the baseline is reported (growth → guard fails)."""
    baseline = ["a", "b"]
    current = ["a", "b", "c"]
    assert lib.grown_beyond_baseline(current, baseline) == ["c"]


def test_grown_beyond_baseline_shrink_passes(lib: ModuleType) -> None:
    """A set that shrank has no growth → empty (guard passes)."""
    assert lib.grown_beyond_baseline(["a"], ["a", "b"]) == []


def test_grown_beyond_baseline_equal_passes(lib: ModuleType) -> None:
    """An unchanged set has no growth → empty (guard passes at baseline)."""
    assert lib.grown_beyond_baseline(["a", "b"], ["b", "a"]) == []


@pytest.mark.parametrize(
    "baseline_key",
    ["dark_roots", "truly_dark_packages", "in_matrix_dark_packages"],
)
def test_all_three_committed_baselines_pass_at_current(lib: ModuleType, baseline_key: str) -> None:
    """Green-at-baseline: each committed set has NOT grown vs. today's measurement.

    Proves the seeded sidecar makes each of the three shrink-only baselines pass
    against the live computation (not a synthetic list) — the whole point of WP01.
    """
    baseline = lib.load_baseline()
    truly_dark, in_matrix_dark = lib.reachability_partition()
    current = {
        "dark_roots": lib.dark_roots(),
        "truly_dark_packages": truly_dark,
        "in_matrix_dark_packages": in_matrix_dark,
    }[baseline_key]
    assert lib.grown_beyond_baseline(current, baseline[baseline_key]) == []


def test_synthetic_new_dark_member_would_fail(lib: ModuleType) -> None:
    """A synthetic package added on top of a committed baseline is flagged.

    Guards against the ratchet passing vacuously: injecting a fabricated new
    member into the *current* set (over the real baseline) must be reported.
    """
    baseline = lib.load_baseline()
    poisoned = [*baseline["truly_dark_packages"], "specify_cli.__fake_dark_pkg__"]
    assert lib.grown_beyond_baseline(poisoned, baseline["truly_dark_packages"]) == ["specify_cli.__fake_dark_pkg__"]


# ---------------------------------------------------------------------------
# own-root ratio ratchet
# ---------------------------------------------------------------------------


def test_ratio_regressions_flags_a_drop(lib: ModuleType) -> None:
    current = {"merge": 0.5}
    baseline = {"merge": 0.7}
    regressions = lib.ratio_regressions(current, baseline)
    assert len(regressions) == 1 and "merge" in regressions[0]


def test_ratio_regressions_allows_equal_and_improvement(lib: ModuleType) -> None:
    baseline = {"merge": 0.7, "cli": 0.5}
    current = {"merge": 0.7, "cli": 0.9}  # equal + improved
    assert lib.ratio_regressions(current, baseline) == []


def test_ratio_regressions_flags_a_vanished_row(lib: ModuleType) -> None:
    assert lib.ratio_regressions({}, {"merge": 0.7}) == ["merge: row vanished from the registry"]


def test_current_own_root_ratios_excludes_exempt_rows(lib: ModuleType) -> None:
    ratios = lib.current_own_root_ratios()
    assert ratios  # non-empty
    assert not (set(ratios) & lib.RATIO_EXEMPT_MODULES)


# ---------------------------------------------------------------------------
# imports_under_package — full ast.walk catches deferred / function-level imports
# ---------------------------------------------------------------------------


def test_imports_under_package_top_level(lib: ModuleType, tmp_path: Path) -> None:
    src = tmp_path / "test_top.py"
    src.write_text("from specify_cli.merge import executor\n", encoding="utf-8")
    assert lib.imports_under_package(src, "specify_cli.merge") is True
    assert lib.imports_under_package(src, "specify_cli.status") is False


def test_imports_under_package_deferred_function_level(lib: ModuleType, tmp_path: Path) -> None:
    """A function-level (deferred) import still counts — the full ast.walk sees it."""
    src = tmp_path / "test_deferred.py"
    src.write_text(
        "def probe():\n    import specify_cli.live_work.bindings  # deferred\n    return specify_cli.live_work.bindings\n",
        encoding="utf-8",
    )
    assert lib.imports_under_package(src, "specify_cli.live_work") is True


def test_imports_under_package_parent_does_not_fabricate_child(lib: ModuleType, tmp_path: Path) -> None:
    """Importing a parent package never fabricates coverage of a child package."""
    src = tmp_path / "test_parent.py"
    src.write_text("import specify_cli\n", encoding="utf-8")
    assert lib.imports_under_package(src, "specify_cli") is True
    assert lib.imports_under_package(src, "specify_cli.merge") is False


# ---------------------------------------------------------------------------
# resolver precedence (module-tests.yml, never _canonical_test_mirror)
# ---------------------------------------------------------------------------


def test_resolve_test_dirs_prefers_explicit(lib: ModuleType) -> None:
    row = {"module": "merge", "test_dirs": ["tests/merge", "tests/terminus"]}
    resolved = [str(p) for p in lib.resolve_test_dirs(row)]
    assert resolved == [str(lib.REPO_ROOT / "tests/merge"), str(lib.REPO_ROOT / "tests/terminus")]


def test_resolve_test_dirs_defaults_to_tests_module(lib: ModuleType) -> None:
    row = {"module": "agent"}  # no explicit test_dirs
    resolved = [str(p) for p in lib.resolve_test_dirs(row)]
    assert resolved == [str(lib.TESTS_ROOT / "agent")]  # tests/agent, NOT tests/agent_utils


# ---------------------------------------------------------------------------
# enumeration + data-package exclusion
# ---------------------------------------------------------------------------


def test_enumerate_includes_real_and_loose_modules(lib: ModuleType) -> None:
    packages = set(lib.enumerate_src_packages())
    assert "specify_cli.merge" in packages  # real subpackage
    assert "specify_cli.mission" in packages  # loose top-level *.py module
    assert "kernel" in packages


def test_enumerate_excludes_data_only_packages(lib: ModuleType) -> None:
    packages = set(lib.enumerate_src_packages())
    for data_pkg in (
        "charter.activation.corpus",
        "charter.activation.packs",
        "specify_cli.skills.data",
    ):
        assert data_pkg not in packages
    assert "specify_cli.schemas" not in packages  # no __init__.py → not enumerated


def test_is_data_only_package(lib: ModuleType) -> None:
    # ships only *.yaml / *.json + __init__.py → data-only
    assert lib.is_data_only_package("charter.activation.corpus") is True
    assert lib.is_data_only_package("specify_cli.skills.data") is True
    # a real code package is NOT data-only
    assert lib.is_data_only_package("specify_cli.merge") is False
    # a non-existent dotted path is not a package
    assert lib.is_data_only_package("specify_cli.__does_not_exist__") is False


# ---------------------------------------------------------------------------
# own_root_ratio + root->pkg mapping
# ---------------------------------------------------------------------------


def test_own_root_ratio_is_a_fraction(lib: ModuleType) -> None:
    row = next(r for r in lib.registry_rows() if r["module"] == "merge")
    ratio = lib.own_root_ratio(row)
    assert 0.0 <= ratio <= 1.0


def test_root_glob_to_pkg_maps_and_skips_non_src(lib: ModuleType) -> None:
    assert lib.root_glob_to_pkg("src/specify_cli/merge/**") == "specify_cli.merge"
    assert lib.root_glob_to_pkg("src/specify_cli/mission.py") == "specify_cli.mission"
    assert lib.root_glob_to_pkg("scripts/ci/**") is None  # non-src, recorded exemption
    assert lib.root_glob_to_pkg(".github/workflows/**") is None
