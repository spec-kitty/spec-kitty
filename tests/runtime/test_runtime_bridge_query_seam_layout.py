"""Module-layout contract for the runtime_bridge split (#2560).

Mission ``runtime-bridge-query-seam-01M490EQ`` moved code out of
``runtime_bridge.py`` into four new seams:

* ``runtime_bridge_decision_mapping`` -- the lower module the advance path,
  the engine adapter and the read path use to turn a runtime ``NextDecision``
  into a CLI ``Decision``;
* ``runtime_bridge_decision_log`` -- the coordination-aware decision-log
  wrapper used by the advance path and the answer path;
* ``runtime_bridge_query`` -- query mode and answer mode;
* ``runtime_bridge_guards`` -- the guard facts io reads and the WP-advance
  guard composition reads (``_resolve_runtime_feature_dir`` went to
  ``runtime_bridge_identity``).

The canonical no-forwarder gate (``tests/runtime/test_bridge_no_compat_delegates.py``)
owns the moved-name table (``REMOVED``), "the bridge neither defines, exposes
nor reads back a moved name" and the re-export identity. This file pins the
rest of ``contracts/module-layout.md`` over the same table:

* every moved name is *defined* in its owning seam, not merely re-imported
  there;
* the bridge's ``__all__`` is unchanged;
* the import direction: no ``runtime_bridge_*`` module imports the bridge at
  all, the lower seams import nothing above them, and the leaf seams
  (identity, cores, retrospective) import no ``runtime_bridge_*`` sibling. The scan walks
  function-local imports too, so a deferred back-edge such as the engine's
  former ``from runtime.next import runtime_bridge as _rb`` is caught. A
  planted forbidden import is reported (self-mutation test).

Known scanner limits, none of which these modules use:
``importlib.import_module(...)``, ``import runtime.next`` followed by
attribute access, and definitions nested in a top-level ``if``/``try`` block.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
from types import GenericAlias, ModuleType

import pytest

from tests.runtime.test_bridge_no_compat_delegates import REMOVED

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_NEXT_DIR = Path(__file__).resolve().parents[2] / "src" / "runtime" / "next"
_PKG = "runtime.next"
_BRIDGE = "runtime_bridge"
_QUERY = "runtime_bridge_query"
_MAPPING = "runtime_bridge_decision_mapping"
_DECISION_LOG = "runtime_bridge_decision_log"
_GUARDS = "runtime_bridge_guards"
_ENGINE = "runtime_bridge_engine"
_COMPOSITION = "runtime_bridge_composition"
_IO = "runtime_bridge_io"
_IDENTITY = "runtime_bridge_identity"
_CORES = "runtime_bridge_cores"
_RETROSPECTIVE = "runtime_bridge_retrospective"

#: The names #2560 moved, by owning module (from the canonical ``REMOVED`` table).
_OWNED: dict[str, tuple[str, ...]] = {
    _MAPPING: REMOVED["decision_mapping"],
    _DECISION_LOG: REMOVED["decision_log"],
    _QUERY: REMOVED["query"],
    _GUARDS: REMOVED["guards"],
    _IDENTITY: ("_resolve_runtime_feature_dir",),
}

_BRIDGE_ALL = {
    "DecisionGitLogUnavailable",
    "MissionNotFoundError",
    "QueryModeValidationError",
    "answer_decision_via_runtime",
    "build_operational_context_for_claim",
    "decide_next_via_runtime",
    "get_or_start_run",
    "query_current_state",
}

#: Module -> sibling modules it must never import, on top of the bridge itself,
#: which no ``runtime_bridge_*`` module may import (contracts §4).
_FORBIDDEN_IMPORTS: dict[str, frozenset[str]] = {
    _MAPPING: frozenset({_QUERY, _ENGINE, _DECISION_LOG, _COMPOSITION, _GUARDS, _IO}),
    _DECISION_LOG: frozenset({_QUERY, _MAPPING, _ENGINE, _GUARDS}),
    _GUARDS: frozenset({_IO, _COMPOSITION, _ENGINE, _QUERY, _DECISION_LOG}),
    _ENGINE: frozenset({_QUERY}),
    _IO: frozenset({_DECISION_LOG, _QUERY}),
}

#: Every seam module that exists on disk (the bridge-import ban covers all of them).
_SEAMS = sorted(path.stem for path in _NEXT_DIR.glob("runtime_bridge_*.py"))

#: Leaf seams (the seam map in ``runtime_bridge.py`` calls identity a "leaf" and
#: cores "pure leaves"; retrospective is one too): they import no
#: ``runtime_bridge_*`` sibling at all, at any depth.
_LEAF_SEAMS = frozenset({_IDENTITY, _CORES, _RETROSPECTIVE})


def _module(name: str) -> ModuleType:
    return importlib.import_module(f"{_PKG}.{name}")


def _top_level_defined_names(path: Path) -> set[str]:
    """Names bound by a top-level ``def``/``class``/assignment in *path*."""
    names: set[str] = set()
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def imported_siblings(source: str) -> set[str]:
    """Every ``runtime.next.<sibling>`` module *source* imports, at any depth.

    Covers ``import runtime.next.x``, ``from runtime.next import x [as y]``,
    ``from runtime.next.x import y`` and the relative forms, including imports
    nested inside functions (deferred back-edges).
    """
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(f"{_PKG}."):
                    found.add(alias.name.split(".")[2])
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level == 1 and not module:
                found.update(alias.name for alias in node.names)
            elif node.level == 1:
                found.add(module.split(".")[0])
            elif module == _PKG:
                found.update(alias.name for alias in node.names)
            elif module.startswith(f"{_PKG}."):
                found.add(module.split(".")[2])
    return found


def forbidden_import_violations(module: str, source: str) -> list[str]:
    forbidden = _FORBIDDEN_IMPORTS.get(module, frozenset()) | {_BRIDGE}
    if module in _LEAF_SEAMS:
        forbidden |= set(_SEAMS)
    return sorted(imported_siblings(source) & forbidden)


# ---------------------------------------------------------------------------
# §1 Ownership
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("owner", "name"), [(owner, name) for owner, names in _OWNED.items() for name in names])
def test_moved_name_is_defined_by_its_owner(owner: str, name: str) -> None:
    assert name in _top_level_defined_names(_NEXT_DIR / f"{owner}.py"), f"{name} must be defined in {owner}.py"
    value = getattr(_module(owner), name)
    if callable(value) and not isinstance(value, GenericAlias):
        assert value.__module__ == f"{_PKG}.{owner}", f"{name} is defined in {value.__module__}, expected {owner}"


def test_bridge_all_is_unchanged() -> None:
    assert set(_module(_BRIDGE).__all__) == _BRIDGE_ALL


# ---------------------------------------------------------------------------
# §4 Import direction
# ---------------------------------------------------------------------------


def test_seam_scan_is_non_vacuous() -> None:
    """Floor: the bridge-import scan covers every seam, old and new."""
    assert {_MAPPING, _DECISION_LOG, _QUERY, _GUARDS, _ENGINE, _IO, _IDENTITY, _COMPOSITION} <= set(_SEAMS)


def test_bridge_seam_map_names_every_seam() -> None:
    """A seam added under ``runtime_bridge_*.py`` must be listed in the bridge's seam-map comment."""
    source = (_NEXT_DIR / f"{_BRIDGE}.py").read_text(encoding="utf-8")
    comments = "\n".join(line for line in source.splitlines() if line.startswith("#"))
    assert [seam for seam in _SEAMS if seam not in comments] == []


@pytest.mark.parametrize("module", _SEAMS)
def test_no_forbidden_sibling_import(module: str) -> None:
    source = (_NEXT_DIR / f"{module}.py").read_text(encoding="utf-8")
    assert forbidden_import_violations(module, source) == []


@pytest.mark.parametrize(
    ("module", "owner"),
    [(_ENGINE, _MAPPING), (_IO, _GUARDS), (_IO, _IDENTITY), (_COMPOSITION, _GUARDS)],
)
def test_former_back_edge_imports_the_owning_seam(module: str, owner: str) -> None:
    """Each seam that used to read a name off the bridge imports its owner instead."""
    source = (_NEXT_DIR / f"{module}.py").read_text(encoding="utf-8")
    assert owner in imported_siblings(source)


@pytest.mark.parametrize(
    "planted",
    [
        "from runtime.next import runtime_bridge as _rb\n",
        "def f():\n    from runtime.next import runtime_bridge as _rb\n",
        "import runtime.next.runtime_bridge\n",
        "from runtime.next.runtime_bridge import query_current_state\n",
        "from . import runtime_bridge\n",
        "from .runtime_bridge import query_current_state\n",
    ],
)
def test_planted_back_edge_is_reported(planted: str) -> None:
    """Self-mutation: each import shape of the bridge is caught on its own.

    The planted snippet is scanned alone (a neutral source), so the row cannot
    pass on the strength of an import already present in a real module.
    """
    assert forbidden_import_violations(_ENGINE, planted) == [_BRIDGE]


@pytest.mark.parametrize(
    ("module", "planted", "expected"),
    [
        (_GUARDS, "from runtime.next import runtime_bridge_io as _io\n", [_IO]),
        (_IDENTITY, "def f():\n    from runtime.next import runtime_bridge_cores\n", [_CORES]),
    ],
)
def test_planted_upward_import_is_reported(module: str, planted: str, expected: list[str]) -> None:
    """Self-mutation: a lower seam, or a leaf seam, importing a sibling above it is caught."""
    assert forbidden_import_violations(module, planted) == expected


def test_neutral_source_reports_nothing() -> None:
    """Positive control for the battery above: the scanner is not trigger-happy."""
    assert forbidden_import_violations(_ENGINE, "from runtime.next import runtime_bridge_io\nimport os\n") == []
