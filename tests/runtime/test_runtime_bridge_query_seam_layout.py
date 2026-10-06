"""Module-layout contract for the runtime_bridge query/answer split (#2560).

Mission ``runtime-bridge-query-seam-01M490EQ`` moved the read path and the
decision mapping it shares with the advance path out of ``runtime_bridge.py``:

* ``runtime_bridge_decision_mapping`` -- the lower module both paths (and the
  engine adapter) use to turn a runtime ``NextDecision`` into a CLI
  ``Decision``;
* ``runtime_bridge_decision_log`` -- the coordination-aware decision-log
  wrapper used by the advance path and the answer path;
* ``runtime_bridge_query`` -- query mode and answer mode.

This file pins the contract in ``contracts/module-layout.md``: who owns each
moved name, that the public names on the bridge are the very same objects
(no forwarding delegate), and the import direction (no module below the
bridge imports it back; the mapping module imports nothing above it). The
import check walks function-local imports too, so a deferred back-edge such
as the engine's former ``from runtime.next import runtime_bridge as _rb`` is
caught. A planted forbidden import is reported (self-mutation test).

Contract §5's "ruff F401 clean on runtime_bridge.py" has no row here: the
repository's ruff gate (CI and ``ruff check``) enforces it. Known scanner
limits, none of which these modules use: ``importlib.import_module(...)``,
``import runtime.next`` followed by attribute access, and definitions nested
in a top-level ``if``/``try`` block.

``_EXTRACTED`` records which owner module the mission has extracted so far.
Every row that depends on a not-yet-extracted owner is a strict xfail: it
documents the red state and fails the run if it starts passing before its
owner is flipped. Each extraction WP flips one key.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
from types import GenericAlias, ModuleType

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_NEXT_DIR = Path(__file__).resolve().parents[2] / "src" / "runtime" / "next"
_PKG = "runtime.next"
_BRIDGE = "runtime_bridge"
_QUERY = "runtime_bridge_query"
_MAPPING = "runtime_bridge_decision_mapping"
_DECISION_LOG = "runtime_bridge_decision_log"
_ENGINE = "runtime_bridge_engine"
_COMPOSITION = "runtime_bridge_composition"

#: Owner module -> extracted yet? Flipped by the WP that creates the module.
_EXTRACTED: dict[str, bool] = {
    _MAPPING: True,
    _DECISION_LOG: True,
    _QUERY: False,
}

#: Owner module -> names it must define (contracts/module-layout.md §1).
_OWNED: dict[str, tuple[str, ...]] = {
    _QUERY: (
        "query_current_state",
        "answer_decision_via_runtime",
        "QueryModeValidationError",
        "MissionNotFoundError",
        "_is_read_path_error",
        "_READ_PATH_ERROR_CODES",
        "_build_finalized_override_query_decision",
        "_build_initial_query_decision",
        "_build_decision_required_query",
        "_build_runtime_query_decision",
        "_query_resolve_mission_context",
        "_query_read_runtime_plan",
        "_query_dispatch_decision",
    ),
    _MAPPING: (
        "_prompt_exists",
        "_materialize_decision",
        "TASKS_GLOB",
        "_WP_ITERATION_STEPS",
        "_is_wp_iteration_step",
        "_has_claimable_planned_wp",
        "_finalized_task_board_override_step",
        "_reduced_wp_lane",
        "_count_wp_endings",
        "_MERGED_MISSION_DONE_REASON",
        "_merged_mission_short_circuit",
        "_WpIterationResolution",
        "_WpBoardAction",
        "_WP_BOARD_DECLINE",
        "_inspect_board_recovery_command",
        "_wp_blocked_action",
        "_wp_task_surface_error",
        "_wp_dispatch_action",
        "_resolve_wp_board_implement_action",
        "_resolve_wp_board_review_action",
        "_resolve_wp_board_action",
        "_wp_iteration_action_and_state",
        "_build_wp_iteration_decision",
        "_build_decision_required_prompt_file",
        "_map_wp_step_decision",
        "_map_non_wp_step_decision",
        "_map_runtime_decision",
    ),
    _DECISION_LOG: (
        "DecisionGitLogUnavailable",
        "_mission_routes_through_coordination",
        "_is_owned_coordination_unavailable",
        "_wrap_with_decision_git_log",
    ),
}

#: Public names the bridge keeps as plain re-exports (contracts §2).
_REEXPORTS: dict[str, str] = {
    "query_current_state": _QUERY,
    "answer_decision_via_runtime": _QUERY,
    "QueryModeValidationError": _QUERY,
    "MissionNotFoundError": _QUERY,
    "DecisionGitLogUnavailable": _DECISION_LOG,
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

#: Module -> sibling modules it must never import (contracts §4).
_FORBIDDEN_IMPORTS: dict[str, frozenset[str]] = {
    _MAPPING: frozenset({_BRIDGE, _QUERY, _ENGINE, _DECISION_LOG, _COMPOSITION}),
    _DECISION_LOG: frozenset({_BRIDGE, _QUERY, _MAPPING, _ENGINE}),
    _QUERY: frozenset({_BRIDGE}),
    _ENGINE: frozenset({_BRIDGE, _QUERY}),
}


def _pending(*owners: str) -> list[pytest.MarkDecorator]:
    """Strict-xfail mark while any of *owners* is not extracted yet."""
    waiting = [owner for owner in owners if not _EXTRACTED.get(owner, True)]
    if not waiting:
        return []
    return [pytest.mark.xfail(strict=True, reason=f"{', '.join(waiting)} not extracted yet (#2560)")]


def _row(*values: object, owners: tuple[str, ...]) -> object:
    return pytest.param(*values, marks=_pending(*owners))


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
    return sorted(imported_siblings(source) & _FORBIDDEN_IMPORTS[module])


# ---------------------------------------------------------------------------
# §1 Ownership
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("owner", "name"), [_row(owner, name, owners=(owner,)) for owner, names in _OWNED.items() for name in names])
def test_moved_name_is_defined_by_its_owner(owner: str, name: str) -> None:
    assert name in _top_level_defined_names(_NEXT_DIR / f"{owner}.py"), f"{name} must be defined in {owner}.py"
    value = getattr(_module(owner), name)
    if callable(value) and not isinstance(value, GenericAlias):
        assert value.__module__ == f"{_PKG}.{owner}", f"{name} is defined in {value.__module__}, expected {owner}"


@pytest.mark.parametrize("owner", [_row(owner, owners=(owner,)) for owner in _OWNED])
def test_bridge_defines_none_of_the_moved_names(owner: str) -> None:
    """§3: no delegate, self-alias or second definition is left in the bridge."""
    bridge_defs = _top_level_defined_names(_NEXT_DIR / f"{_BRIDGE}.py")
    assert sorted(bridge_defs & set(_OWNED[owner])) == []


@pytest.mark.parametrize("owner", [_row(owner, owners=(owner,)) for owner in _OWNED])
def test_bridge_keeps_no_attribute_for_private_moved_names(owner: str) -> None:
    """§5: a stale ``runtime_bridge.<moved private name>`` patch raises AttributeError."""
    bridge = _module(_BRIDGE)
    leaked = sorted(name for name in _OWNED[owner] if name not in _REEXPORTS and hasattr(bridge, name))
    assert leaked == []


# ---------------------------------------------------------------------------
# §2 Re-export identity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "owner"), [_row(name, owner, owners=(owner,)) for name, owner in sorted(_REEXPORTS.items())])
def test_public_name_is_the_owner_object(name: str, owner: str) -> None:
    assert getattr(_module(_BRIDGE), name) is getattr(_module(owner), name)


def test_bridge_all_is_unchanged() -> None:
    assert set(_module(_BRIDGE).__all__) == _BRIDGE_ALL


# ---------------------------------------------------------------------------
# §4 Import direction
# ---------------------------------------------------------------------------


#: A module that does not exist yet cannot import anything; its row waits for it.
_IMPORT_ROW_OWNERS: dict[str, tuple[str, ...]] = {
    _MAPPING: (_MAPPING,),
    _DECISION_LOG: (_DECISION_LOG,),
    _QUERY: (_QUERY,),
    _ENGINE: (_MAPPING,),  # the engine's bridge back-edge goes away with the mapping module
}


@pytest.mark.parametrize("module", [_row(module, owners=_IMPORT_ROW_OWNERS[module]) for module in sorted(_FORBIDDEN_IMPORTS)])
def test_no_forbidden_sibling_import(module: str) -> None:
    source = (_NEXT_DIR / f"{module}.py").read_text(encoding="utf-8")
    assert forbidden_import_violations(module, source) == []


@pytest.mark.parametrize("_unused", [_row(None, owners=(_MAPPING,))])
def test_engine_calls_mapping_directly(_unused: None) -> None:
    """The engine adapter's former ``_rb`` back-edge now targets the mapping module."""
    source = (_NEXT_DIR / f"{_ENGINE}.py").read_text(encoding="utf-8")
    assert _MAPPING in imported_siblings(source)


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
    pass on the strength of a bridge import already present in the engine.
    """
    assert forbidden_import_violations(_ENGINE, planted) == [_BRIDGE]


def test_neutral_source_reports_nothing() -> None:
    """Positive control for the battery above: the scanner is not trigger-happy."""
    assert forbidden_import_violations(_ENGINE, "from runtime.next import runtime_bridge_io\nimport os\n") == []
