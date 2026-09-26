"""Foreign-coverage honesty guard (FR-001) — GREEN-AT-BASELINE, shrink-only.

For every registry ``modules[]`` row whose ``roots`` resolve to importable src
packages, this guard enforces two shrink-only ratchets against the committed
MEASURED baseline in ``.github/ci-foreign-coverage-baseline.json``:

* **Dark-root baseline** — a row's own declared src root that no test in its
  resolved test dirs imports is "dark". The set may not GROW beyond the recorded
  baseline (today: ``next::specify_cli.runtime``). A new dark root fails; the
  recorded ones are honest debt, not a hard fail.
* **Own-root ratio ratchet** — a row's fraction of resolved test files importing
  an own root package may not DROP more than 8.5% (relative) below its recorded
  baseline; the floor is ``baseline * (1 - 0.085)``. The slack absorbs a fix
  whose new own-root code is exercised by the real-CLI foreign suites
  (``tests/terminus/``, ``tests/lanes/``) per ADR 2026-07-17-1; a genuine
  regression (own-root test files removed) drops the ratio far past it and still
  fails. Improving ratchets the baseline up (WP02).

Recorded exemptions (never gated): non-src-root rows (``ci``) and the
self-declared aggregate / inventory rows (``execution_context``, ``core_misc``,
``unit``, ``specify_cli_runtime``).

The guard PASSES at baseline by construction. The synthetic grow-fails /
shrink-passes proofs live in ``tests/ci/test_coverage_guards.py``. Import-based,
no test execution — well under the NFR-002 5 s budget.
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
def baseline(lib: ModuleType) -> dict[str, Any]:
    return cast("dict[str, Any]", lib.load_baseline())


def test_no_new_dark_root(lib: ModuleType, baseline: dict[str, Any]) -> None:
    """Shrink-only: no own root goes dark beyond the committed baseline."""
    grown = lib.grown_beyond_baseline(lib.dark_roots(), baseline["dark_roots"])
    assert not grown, (
        "new dark root(s) — a row's own src package that no test in its resolved "
        f"dirs imports: {grown}. Add a test importing it, or fold it into the "
        "committed baseline only if it is genuinely honest debt."
    )


def test_own_root_ratios_have_not_regressed(lib: ModuleType, baseline: dict[str, Any]) -> None:
    """Shrink-only ratchet: no row's own-root import ratio drops >8.5% below baseline."""
    regressions = lib.ratio_regressions(lib.current_own_root_ratios(), baseline["own_root_ratios"])
    assert not regressions, "own-root coverage ratio regressed below baseline:\n" + "\n".join(regressions)


def test_baseline_is_not_vacuous(lib: ModuleType, baseline: dict[str, Any]) -> None:
    """The baseline records real debt: the known dark root and every gated row.

    Guards against a truncated / emptied sidecar silently passing both ratchets.
    """
    assert "next::specify_cli.runtime" in baseline["dark_roots"]
    assert baseline["own_root_ratios"], "own_root_ratios baseline is empty"
    # Every gated row in the baseline is a real registry row, and none of the
    # recorded exemptions leaked into the gated ratio set.
    registry_modules = {str(row["module"]) for row in lib.registry_rows()}
    for module in baseline["own_root_ratios"]:
        assert module in registry_modules, f"baseline row {module!r} is not in the registry"
        assert module not in lib.RATIO_EXEMPT_MODULES, f"exempt row {module!r} must not be gated by the ratio ratchet"


def test_exempt_rows_are_never_dark_gated(lib: ModuleType) -> None:
    """Recorded exemptions (non-src ``ci`` + aggregate rows) never appear dark."""
    dark_modules = {entry.split("::", 1)[0] for entry in lib.dark_roots()}
    assert not (dark_modules & lib.RATIO_EXEMPT_MODULES), "an exempt aggregate/non-src row was reported dark — the exemption regressed"
