"""Static-import analysis powering the two coverage-honesty guards (FR-001/FR-002).

This is the shared, import-based (no test execution) engine behind
``tests/architectural/test_foreign_coverage_guard.py`` and
``tests/architectural/test_src_reachability_guard.py``. It is built on the
canonical ``specify_cli.ast_analysis.imports`` primitives (the same
``module_of_import_from`` resolver the dead-symbol/dead-module gates use) with a
full :func:`ast.walk`, so deferred / function-level imports count as coverage.

Design posture (mission ci-coverage-honesty, research D1/D3/D9, ledger F17):
**GREEN-AT-BASELINE, not red-first.** The guards record honest current debt in
``.github/ci-foreign-coverage-baseline.json`` and fail only on a *regression*
(a new dark package/root). The one hard, non-baselined check is the
truly-dark floor: a src package imported by NO test anywhere is a real honesty
violation and fails immediately.

Vocabulary:

* **in-matrix test dir** — a directory a ``modules[]`` registry row runs per PR
  (its explicit ``test_dirs`` else ``tests/{module}``, NEVER the phantom
  ``_canonical_test_mirror``).
* **dark root** — a row's own declared src package that no test in the row's
  resolved dirs imports.
* **in-matrix-dark package** — a src package imported by some test *somewhere*
  but by no in-matrix test (reachable only out-of-matrix / nightly).
* **truly-dark package** — a src package imported by NO test anywhere.

Performance (NFR-002): every ``*.py`` file is parsed at most once (memoized by
resolved path); the whole-corpus scan is well under the 5 s budget.
"""

from __future__ import annotations

import ast
import functools
import json
from pathlib import Path
from typing import Any

import yaml

from specify_cli.ast_analysis.imports import module_of_import_from

# ---------------------------------------------------------------------------
# Repo geography
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
TESTS_ROOT = REPO_ROOT / "tests"
DEFAULT_REGISTRY_PATH = REPO_ROOT / ".github" / "ci-module-registry.yml"
DEFAULT_BASELINE_PATH = REPO_ROOT / ".github" / "ci-foreign-coverage-baseline.json"

# The 6 wheel roots (pyproject ``[tool.hatch.build.targets.wheel].packages``);
# every importable src package is enumerated by walking under these.
WHEEL_ROOTS: tuple[str, ...] = (
    "kernel",
    "glossary",
    "mission_runtime",
    "runtime",
    "specify_cli",
    "charter",
)

# Rows exempt from the own-root ratio + dark-root gate: the self-declared
# AGGREGATE / TEST-INVENTORY rows (research D2) whose registry comments state
# they own no single src mirror. ``ci`` is exempt structurally (its roots are
# non-src, so it has no own src package prefix) and is listed here too for
# explicitness.
RATIO_EXEMPT_MODULES: frozenset[str] = frozenset({"execution_context", "core_misc", "unit", "specify_cli_runtime", "ci"})

# ---------------------------------------------------------------------------
# AST import extraction (full walk — deferred imports count)
# ---------------------------------------------------------------------------


def _containing_pkg(py_file: Path) -> str:
    """Dotted package of a file's parent, relative to the repo root.

    Used only to resolve *relative* imports; test files import src packages
    absolutely, so this never mislabels a src package as covered.
    """
    try:
        rel = py_file.resolve().relative_to(REPO_ROOT)
    except ValueError:
        return ""
    return ".".join(rel.parent.parts)


@functools.cache
def imported_modules(py_file: Path) -> frozenset[str]:
    """Every absolute dotted module name a file imports (full :func:`ast.walk`).

    Both ``import a.b`` and ``from a.b import c`` forms are captured, including
    imports nested inside functions/methods (deferred imports), so a
    function-level ``import specify_cli.live_work.bindings`` counts. For a
    ``from a.b import c`` node, both ``a.b`` and ``a.b.c`` are recorded so a
    ``from pkg import submodule`` reaches ``pkg.submodule``.
    """
    text = py_file.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(py_file))
    containing = _containing_pkg(py_file)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = module_of_import_from(node, containing)
            if not module:
                continue
            names.add(module)
            for alias in node.names:
                if alias.name != "*":
                    names.add(f"{module}.{alias.name}")
    return frozenset(names)


def imports_under_package(py_file: Path, pkg_prefix: str) -> bool:
    """Whether *py_file* imports *pkg_prefix* itself or anything beneath it."""
    dotted = f"{pkg_prefix}."
    return any(name == pkg_prefix or name.startswith(dotted) for name in imported_modules(py_file))


def _covered_prefixes(files: list[Path]) -> frozenset[str]:
    """All dotted prefixes of every module the given files import.

    A package ``P`` is *reachable* by these files iff ``P`` is in this set:
    importing ``a.b.c`` covers ``a``, ``a.b`` and ``a.b.c`` (a parent package
    is reached by importing any of its descendants), but importing a parent
    never fabricates coverage of a child package.
    """
    covered: set[str] = set()
    for file in files:
        for name in imported_modules(file):
            parts = name.split(".")
            for index in range(1, len(parts) + 1):
                covered.add(".".join(parts[:index]))
    return frozenset(covered)


# ---------------------------------------------------------------------------
# Registry access + test-dir resolution
# ---------------------------------------------------------------------------


@functools.cache
def load_registry(path: Path | None = None) -> dict[str, Any]:
    """Parse ``.github/ci-module-registry.yml`` (PyYAML)."""
    registry_path = path or DEFAULT_REGISTRY_PATH
    return dict(yaml.safe_load(registry_path.read_text(encoding="utf-8")))


def registry_rows(path: Path | None = None) -> list[dict[str, Any]]:
    """The ``modules[]`` rows — the single data source for the per-PR matrix."""
    return [dict(row) for row in load_registry(path)["modules"]]


def resolve_test_dirs(row: dict[str, Any]) -> list[Path]:
    """A row's test directories with **module-tests.yml precedence**.

    Explicit ``test_dirs`` when the row declares them, else the ``tests/{module}``
    default. Never ``_canonical_test_mirror`` (the phantom ``tests/agent_utils``
    the authority bug produced — research D8/FR-003).
    """
    explicit = row.get("test_dirs")
    if isinstance(explicit, list) and explicit:
        return [REPO_ROOT / str(test_dir) for test_dir in explicit]
    return [TESTS_ROOT / str(row["module"])]


def in_matrix_test_dirs(path: Path | None = None) -> list[Path]:
    """Union of every ``modules[]`` row's resolved test dirs (per-PR matrix)."""
    seen: dict[Path, None] = {}
    for row in registry_rows(path):
        for test_dir in resolve_test_dirs(row):
            seen.setdefault(test_dir, None)
    return list(seen)


# ---------------------------------------------------------------------------
# src-package enumeration
# ---------------------------------------------------------------------------


def _dir_to_dotted(directory: Path) -> str:
    return ".".join(directory.relative_to(SRC_ROOT).parts)


def is_data_only_package(pkg_prefix: str) -> bool:
    """Whether *pkg_prefix* is a data-shipping package with no testable module.

    True iff the package directory's subtree contains at least one non-Python
    *data* file (``.yaml`` / ``.json`` / a template / …) and **no** ``.py`` file
    other than ``__init__.py`` (the F18 data-package exclusion). Such a package
    is not import-testable, so the reachability guard excludes it: e.g.
    ``charter.activation.corpus`` / ``charter.activation.packs`` (only
    ``*.yaml``), ``specify_cli.skills.data`` (only ``*.json``),
    ``specify_cli.dashboard.templates`` (only rendered templates).

    A *content-free* package (only ``__init__.py``, no data files) is **not**
    data-only — it stays enumerated as honest dark debt (nothing was silently
    hidden). ``schemas`` has no ``__init__.py`` and is already excluded from
    enumeration by construction, so it never reaches this predicate.
    """
    directory = SRC_ROOT / Path(*pkg_prefix.split("."))
    if not directory.is_dir():
        return False
    has_py = False
    has_data = False
    for entry in directory.rglob("*"):
        if "__pycache__" in entry.parts or not entry.is_file():
            continue
        if entry.suffix == ".py":
            if entry.name != "__init__.py":
                has_py = True
        else:
            has_data = True
    return has_data and not has_py


def enumerate_src_packages() -> list[str]:
    """Every importable src package under the 6 wheel roots.

    A package is any ``__init__.py``-bearing directory (walked recursively) plus
    every loose top-level ``*.py`` module directly under a wheel root. Two kinds
    of directory are excluded:

    * **no ``__init__.py``** (e.g. ``specify_cli/schemas``) — not a package, so
      not import-testable; excluded by construction (the walk keys on
      ``__init__.py``).
    * **data-only packages** (:func:`is_data_only_package`) — an
      ``__init__.py``-bearing directory that ships only data files (``*.yaml`` /
      ``*.json`` / templates) with no ``.py`` module to import; excluded per the
      F18 refinement so they never pollute the truly-dark / in-matrix-dark sets.
    """
    packages: set[str] = set()
    for root in WHEEL_ROOTS:
        root_dir = SRC_ROOT / root
        if not root_dir.is_dir():
            continue
        for init_file in root_dir.rglob("__init__.py"):
            if "__pycache__" in init_file.parts:
                continue
            dotted = _dir_to_dotted(init_file.parent)
            if is_data_only_package(dotted):
                continue
            packages.add(dotted)
        for module_file in root_dir.glob("*.py"):
            if module_file.name == "__init__.py":
                continue
            packages.add(_dir_to_dotted(module_file.with_suffix("")))
    return sorted(packages)


# ---------------------------------------------------------------------------
# roots -> src package prefix
# ---------------------------------------------------------------------------


def root_glob_to_pkg(root: str) -> str | None:
    """Convert a registry ``roots`` glob to its src package prefix, or ``None``.

    ``src/specify_cli/merge/**`` -> ``specify_cli.merge``;
    ``src/specify_cli/mission.py`` -> ``specify_cli.mission``. A non-``src/``
    root (``scripts/ci/**``, ``.github/workflows/**``) has no importable prefix
    and returns ``None`` (recorded exemption, research D1).
    """
    text = root.strip()
    if not text.startswith("src/"):
        return None
    rel = text[len("src/") :].rstrip("/")
    if rel.endswith("/**"):
        rel = rel[:-3]
    elif rel.endswith("**"):
        rel = rel[:-2]
    rel = rel.rstrip("/")
    if rel.endswith(".py"):
        rel = rel[:-3]
    return rel.replace("/", ".") if rel else None


def own_pkg_prefixes(row: dict[str, Any]) -> list[str]:
    """A row's own declared src package prefixes, derived from its ``roots``."""
    prefixes: dict[str, None] = {}
    for root in row.get("roots") or ():
        prefix = root_glob_to_pkg(str(root))
        if prefix is not None:
            prefixes.setdefault(prefix, None)
    return list(prefixes)


# ---------------------------------------------------------------------------
# test-file collection + ratio
# ---------------------------------------------------------------------------


def test_files_in(dirs: list[Path]) -> list[Path]:
    """All ``test_*.py`` files under the given directories (recursive, deduped)."""
    seen: dict[Path, None] = {}
    for directory in dirs:
        if not directory.is_dir():
            continue
        for test_file in directory.rglob("test_*.py"):
            if "__pycache__" in test_file.parts:
                continue
            seen.setdefault(test_file.resolve(), None)
    return list(seen)


def own_root_ratio(row: dict[str, Any]) -> float:
    """Fraction of the row's resolved test files importing an own root package.

    Returns ``0.0`` when the row has no own src prefixes or no resolved test
    files (both are recorded as-is in the baseline; the shrink-only ratchet then
    only ever requires the ratio not to *drop*).
    """
    prefixes = own_pkg_prefixes(row)
    if not prefixes:
        return 0.0
    files = test_files_in(resolve_test_dirs(row))
    if not files:
        return 0.0
    hits = sum(1 for file in files if any(imports_under_package(file, prefix) for prefix in prefixes))
    return hits / len(files)


# ---------------------------------------------------------------------------
# dark-root / reachability computations
# ---------------------------------------------------------------------------


def dark_roots(path: Path | None = None) -> list[str]:
    """``module::pkg`` for each own root no test in the row's resolved dirs imports.

    Exempt rows (:data:`RATIO_EXEMPT_MODULES`) and non-src rows are skipped.
    """
    dark: list[str] = []
    for row in registry_rows(path):
        module = str(row["module"])
        if module in RATIO_EXEMPT_MODULES:
            continue
        prefixes = own_pkg_prefixes(row)
        if not prefixes:
            continue
        files = test_files_in(resolve_test_dirs(row))
        for prefix in prefixes:
            if not any(imports_under_package(file, prefix) for file in files):
                dark.append(f"{module}::{prefix}")
    return sorted(dark)


def _all_test_files() -> list[Path]:
    """Every ``test_*.py`` file anywhere under ``tests/`` (the honesty universe)."""
    return test_files_in([TESTS_ROOT])


def reachability_partition(
    path: Path | None = None,
) -> tuple[list[str], list[str]]:
    """Partition enumerated src packages into (truly_dark, in_matrix_dark).

    * ``truly_dark`` — imported by NO test anywhere under ``tests/``.
    * ``in_matrix_dark`` — imported by some test somewhere but by no in-matrix
      test (reachable only out-of-matrix / nightly).
    """
    packages = enumerate_src_packages()
    covered_anywhere = _covered_prefixes(_all_test_files())
    covered_in_matrix = _covered_prefixes(test_files_in(in_matrix_test_dirs(path)))
    truly_dark = [pkg for pkg in packages if pkg not in covered_anywhere]
    in_matrix_dark = [pkg for pkg in packages if pkg in covered_anywhere and pkg not in covered_in_matrix]
    return sorted(truly_dark), sorted(in_matrix_dark)


def truly_dark_packages(path: Path | None = None) -> list[str]:
    return reachability_partition(path)[0]


def in_matrix_dark_packages(path: Path | None = None) -> list[str]:
    return reachability_partition(path)[1]


# ---------------------------------------------------------------------------
# baseline shrink-only comparison
# ---------------------------------------------------------------------------


def grown_beyond_baseline(current: list[str], baseline: list[str]) -> list[str]:
    """Members of *current* absent from *baseline* — a regression (growth).

    Shrink-only semantics: a set that shrank (or held equal) passes; only NEW
    members are violations. Returned sorted.
    """
    return sorted(set(current) - set(baseline))


# A row's own-root ratio may drop by up to this *relative* fraction of its
# committed baseline before the ratchet fires (i.e. the floor is
# ``baseline * (1 - RELATIVE_DROP_TOLERANCE)``). Real-CLI merge/terminus
# integrity tests legitimately live in FOREIGN roots (``tests/terminus/``,
# ``tests/lanes/``) per the ATDD/real-CLI discipline (ADR 2026-07-17-1), so a
# fix that lands new ``src/specify_cli/merge`` code covered by those foreign
# suites dilutes the own-root ratio slightly without being dishonest debt. This
# slack absorbs that; a genuine regression (whole own-root test files removed)
# still drops the ratio far past 8.5% and fails. Improvements continue to
# ratchet the committed baseline UP, so the slack never compounds across PRs.
_OWN_ROOT_RATIO_RELATIVE_DROP_TOLERANCE: float = 0.085


def ratio_regressions(
    current: dict[str, float],
    baseline: dict[str, float],
    *,
    tolerance: float = 1e-6,
    relative_drop_tolerance: float = _OWN_ROOT_RATIO_RELATIVE_DROP_TOLERANCE,
) -> list[str]:
    """Rows whose current own-root ratio dropped more than the allowed slack below baseline.

    Shrink-only ratchet in the improving direction: a ratio that held or *rose*
    passes; a violation is a drop below the floor ``baseline * (1 -
    relative_drop_tolerance) - tolerance``. ``relative_drop_tolerance`` (default
    ``0.085``) permits an 8.5% relative dip so a merge fix whose new code is
    exercised by the real-CLI foreign suites is not falsely failed; see
    :data:`_OWN_ROOT_RATIO_RELATIVE_DROP_TOLERANCE`. The ``1e-6`` ``tolerance``
    additionally absorbs the 6-decimal rounding of the committed baseline (whose
    stored value can round *up* past the full-precision live ratio) so an
    unchanged ratio never false-fails; a real regression removes whole test files
    and drops the ratio by far more than the slack. Returned as sorted
    human-readable strings.
    """
    regressions: list[str] = []
    for module, base_ratio in baseline.items():
        cur = current.get(module)
        if cur is None:
            regressions.append(f"{module}: row vanished from the registry")
            continue
        floor = base_ratio * (1.0 - relative_drop_tolerance)
        if cur + tolerance < floor:
            regressions.append(f"{module}: {cur:.6f} < floor {floor:.6f} (baseline {base_ratio:.6f} − {relative_drop_tolerance:.1%})")
    return sorted(regressions)


# ---------------------------------------------------------------------------
# committed baseline sidecar
# ---------------------------------------------------------------------------


@functools.cache
def load_baseline(path: Path | None = None) -> dict[str, Any]:
    """Parse the committed MEASURED baseline sidecar (all fields shrink-only)."""
    baseline_path = path or DEFAULT_BASELINE_PATH
    return dict(json.loads(baseline_path.read_text(encoding="utf-8")))


def current_own_root_ratios(path: Path | None = None) -> dict[str, float]:
    """Measured own-root ratio for every non-exempt, src-backed registry row."""
    ratios: dict[str, float] = {}
    for row in registry_rows(path):
        module = str(row["module"])
        if module in RATIO_EXEMPT_MODULES:
            continue
        if not own_pkg_prefixes(row):
            continue
        ratios[module] = own_root_ratio(row)
    return ratios
