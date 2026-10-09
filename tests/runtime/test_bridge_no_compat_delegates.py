"""Acceptance gate: ``runtime_bridge`` carries no compat delegates (#2561, #2560).

#2561 retired 36 "thin compat delegate" names from
``src/runtime/next/runtime_bridge.py``; #2560 then moved the decision mapping,
the decision-log wrapper, the query/answer read path, the guard facts and
``_resolve_runtime_feature_dir`` out of the bridge into their own seams. Each
name is owned by exactly one seam module; the bridge neither defines it nor
does any seam read it back off the bridge. A few public names stay on the
bridge as plain re-exports bound by ``from runtime.next.runtime_bridge_<seam>
import ...`` (the very same objects): ``get_or_start_run`` and
``build_operational_context_for_claim`` (io), ``query_current_state``,
``answer_decision_via_runtime``, ``QueryModeValidationError`` and
``MissionNotFoundError`` (query) and ``DecisionGitLogUnavailable``
(decision_log).

Every check is static (``ast``) except Check C (identity) and Check D (a
runtime ``hasattr`` that sees every binding form an AST walk of top-level
statements can miss). The checks run per seam; this is a permanent guard, so a
failing row names the seam (and name) that regressed.

Non-vacuity (charter SO#5): the scanners are pure functions over source text
and the self-mutation tests below feed them synthetic offenders.
"""

from __future__ import annotations

import ast
import importlib
from collections.abc import Callable, Iterator
from functools import lru_cache
from pathlib import Path
from types import GenericAlias, ModuleType

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SRC = Path(__file__).resolve().parents[2] / "src"
_NEXT = _SRC / "runtime" / "next"
_BRIDGE_PATH = _NEXT / "runtime_bridge.py"
_BRIDGE_MODULE = "runtime.next.runtime_bridge"
_IO_MODULE = "runtime.next.runtime_bridge_io"
#: Public re-export -> the seam that owns it (the bridge binds it with a plain
#: ``from runtime.next.runtime_bridge_<seam> import <name>``).
_KEPT_RE_EXPORT_OWNERS: dict[str, str] = {
    "get_or_start_run": "io",
    "build_operational_context_for_claim": "io",
    "query_current_state": "query",
    "answer_decision_via_runtime": "query",
    "QueryModeValidationError": "query",
    "MissionNotFoundError": "query",
    "DecisionGitLogUnavailable": "decision_log",
}
_KEPT_RE_EXPORTS = tuple(_KEPT_RE_EXPORT_OWNERS)

REMOVED: dict[str, tuple[str, ...]] = {
    "identity": (
        "_primary_runtime_feature_dir",
        "_resolve_coordination_branch",
        "_resolve_mission_ulid",
        "_resolve_runtime_feature_dir",  # #2560
    ),
    "cores": (
        "_parse_wp_sections_from_tasks_md",
        "_parse_requirement_refs_from_tasks_md",
        "SPEC_ARTIFACT",  # #2560: the guards seam reads them from here
        "TASKS_ARTIFACT",
    ),
    "engine": ("_advance_run_state_after_composition",),
    "retrospective": (
        "_rich_hic_prompt",
        "_resolve_mission_id_for_terminus",
        "_build_retrospective_facilitator_callback",
        "_resolve_retrospective_policy_for_runtime",
        "_run_retrospective_learning_capture",
        "_classify_exc",
        "_remediation_hint",
        "_classify_and_emit_failure",
    ),
    "composition": (
        "_normalize_action_for_composition",
        "_should_dispatch_via_composition",
        "_resolve_step_agent_profile",
        "_resolve_runtime_contract_for_step",
        "_count_source_documented_events",
        "_publication_approved",
        "_check_composed_action_guard",
        "_dispatch_via_composition",
    ),
    "io": (
        "_load_feature_runs",
        "_mission_key_for_run_ref",
        "_build_run_ref",
        "_build_discovery_context",
        "_resolve_runtime_template_in_root",
        "_runtime_template_key",
        "_existing_run_ref",
        "_start_ephemeral_query_run",
        "get_or_start_run",
        "_resolve_run_dir_for_mission",
        "_resolve_tech_stack_for_profile",
        "build_operational_context_for_claim",
        "_build_operational_context_for_decision",
    ),
    # #2560: the shared decision mapping (advance path, engine adapter, read path).
    "decision_mapping": (
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
    # #2560: the coordination-aware decision-log wrapper.
    "decision_log": (
        "DecisionGitLogUnavailable",
        "_mission_routes_through_coordination",
        "_is_owned_coordination_unavailable",
        "_wrap_with_decision_git_log",
    ),
    # #2560: the query/answer read path.
    "query": (
        "_READ_PATH_ERROR_CODES",
        "_is_read_path_error",
        "QueryModeValidationError",
        "MissionNotFoundError",
        "_build_finalized_override_query_decision",
        "_build_initial_query_decision",
        "_build_decision_required_query",
        "_build_runtime_query_decision",
        "query_current_state",
        "_query_resolve_mission_context",
        "_query_read_runtime_plan",
        "_query_dispatch_decision",
        "answer_decision_via_runtime",
    ),
    # #2560: the guard facts io reads and the WP-advance guard composition reads.
    "guards": (
        "_should_advance_wp_step",
        "_wp_blocks_step",
        "_occurrence_gate_failures",
        "_log_requirement_extraction_warnings",
        "_log_requirement_extraction_warnings_safely",
        "_load_wps_manifest_findings",
        "_check_requirement_mapping_ready",
        "_check_bare_prose_requirements_ready",
        "_has_raw_dependencies_field",
    ),
}
_SEAMS = tuple(REMOVED)
#: 36 names retired by #2561 plus 56 moved by #2560 (decision_mapping 27,
#: decision_log 4, query 13, guards 9, identity 1, and the two artifact file
#: names, which cores owns once and guards reads from it), less
#: ``_BufferingRuntimeEmitter``, which is a live seam-owned class on
#: ``runtime_bridge_retrospective`` (the decision-log emitter replay, ADR
#: 2026-09-06-2 (c)) rather than a retired bridge name, so it is not a row here.
_EXPECTED_TOTAL = 91

# Floor and uniqueness: a shrinking or duplicated table must not make the gate vacuous.
_ALL_REMOVED = [_n for _names_ in REMOVED.values() for _n in _names_]
assert len(_ALL_REMOVED) == len(set(_ALL_REMOVED)) >= _EXPECTED_TOTAL, "REMOVED table shrank below the floor or repeats a name"

#: Owner-side name where it differs from the bridge-side name.
_OWNER_NAME = {
    "_load_feature_runs": "load_feature_runs",
    "_advance_run_state_after_composition": "advance_run_state_after_composition",
}

_LEGACY_PHRASE = "Thin compat delegate"


def _names(seam: str, *, with_re_exports: bool = True) -> tuple[str, ...]:
    names = REMOVED[seam]
    if with_re_exports:
        return names
    return tuple(n for n in names if n not in _KEPT_RE_EXPORTS)


def _rows(seams: tuple[str, ...] = _SEAMS) -> list[object]:
    return [pytest.param(seam, id=seam) for seam in seams]


# ---------------------------------------------------------------------------
# Scanners (pure functions over source text)
# ---------------------------------------------------------------------------


def _is_bridge_from(node: ast.ImportFrom) -> bool:
    if node.level == 0:
        return node.module == _BRIDGE_MODULE
    return node.module == "runtime_bridge"


def _binds_package_member(node: ast.ImportFrom) -> bool:
    """``from runtime.next import X`` / ``from . import X``."""
    return (node.level == 0 and node.module == "runtime.next") or (node.level > 0 and node.module is None)


def bridge_aliases(tree: ast.AST) -> set[str]:
    """Names bound to the bridge module at any scope."""
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and _binds_package_member(node):
            aliases.update(a.asname or a.name for a in node.names if a.name == "runtime_bridge")
        elif isinstance(node, ast.Import):
            aliases.update(a.asname for a in node.names if a.name == _BRIDGE_MODULE and a.asname)
    return aliases


def _dotted(node: ast.expr) -> str | None:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


def _target_names(target: ast.expr) -> Iterator[str]:
    if isinstance(target, ast.Name):
        yield target.id
    elif isinstance(target, ast.Tuple | ast.List):
        for element in target.elts:
            yield from _target_names(element)


def _bound_names(node: ast.stmt) -> list[str]:
    """Names a top-level statement binds, excluding imports."""
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
        return [node.name]
    if isinstance(node, ast.Assign):
        return [n for target in node.targets for n in _target_names(target)]
    if isinstance(node, ast.AnnAssign):
        return list(_target_names(node.target))
    return []


def _import_bindings(node: ast.stmt, names: frozenset[str]) -> list[str]:
    """Removed names an import binds, other than the kept public re-exports."""
    if not isinstance(node, ast.ImportFrom):
        return []
    hits: list[str] = []
    for alias in node.names:
        bound = alias.asname or alias.name
        if bound not in names:
            continue
        owner = _KEPT_RE_EXPORT_OWNERS.get(bound)
        legitimate = owner is not None and node.module == f"runtime.next.runtime_bridge_{owner}" and node.level == 0 and alias.asname is None
        if not legitimate:
            hits.append(f"line {node.lineno}: imports {bound} from {node.module}")
    return hits


def scan_definitions(source: str, names: tuple[str, ...]) -> list[str]:
    """Check A: top-level definitions, assignments and foreign imports of ``names``."""
    wanted = frozenset(names)
    findings: list[str] = []
    for node in ast.parse(source).body:
        findings += [f"line {node.lineno}: defines {n}" for n in _bound_names(node) if n in wanted]
        findings += _import_bindings(node, wanted)
    return findings


def scan_name_loads(source: str, names: tuple[str, ...]) -> list[str]:
    """Check A': any ``ast.Name`` load of a removed name (annotations included)."""
    wanted = frozenset(names)
    return [f"line {n.lineno}: loads {n.id}" for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id in wanted]


def scan_back_edges(source: str, names: tuple[str, ...]) -> list[str]:
    """Check B: ``<bridge alias>.<removed name>`` anywhere in ``source``."""
    tree = ast.parse(source)
    aliases = bridge_aliases(tree)
    wanted = frozenset(names)
    return [
        f"line {n.lineno}: {n.value.id}.{n.attr}"
        for n in ast.walk(tree)
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id in aliases and n.attr in wanted
    ]


def _indirect_from_imports(tree: ast.AST, wanted: frozenset[str]) -> list[str]:
    return [
        f"line {n.lineno}: from runtime_bridge import {a.name}"
        for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom) and _is_bridge_from(n)
        for a in n.names
        if a.name in wanted
    ]


def _is_alias_getattr(call: ast.Call, aliases: set[str]) -> str | None:
    """The attribute name of ``getattr(<bridge alias>, "<name>")``, else ``None``."""
    func = call.func
    if not (isinstance(func, ast.Name) and func.id == "getattr" and len(call.args) >= 2):
        return None
    holder, attr = call.args[0], call.args[1]
    if isinstance(holder, ast.Name) and holder.id in aliases and isinstance(attr, ast.Constant) and isinstance(attr.value, str):
        return attr.value
    return None


def scan_indirect_bridge_reads(source: str, names: tuple[str, ...]) -> list[str]:
    """Check B': deferred imports, ``getattr(alias, "x")`` and fully dotted reads."""
    tree = ast.parse(source)
    wanted = frozenset(names)
    aliases = bridge_aliases(tree)
    findings = _indirect_from_imports(tree, wanted)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            attr = _is_alias_getattr(node, aliases)
            if attr in wanted:
                findings.append(f"line {node.lineno}: getattr(bridge, {attr!r})")
        elif isinstance(node, ast.Attribute) and node.attr in wanted and _dotted(node.value) == _BRIDGE_MODULE:
            findings.append(f"line {node.lineno}: {_BRIDGE_MODULE}.{node.attr}")
    return findings


def scan_bare_calls(source: str, names: tuple[str, ...]) -> list[str]:
    """Call-style rule: ``name(...)`` as a bare call instead of ``_io_seam.name(...)``."""
    wanted = frozenset(names)
    return [
        f"line {n.lineno}: bare call {n.func.id}(...)"
        for n in ast.walk(ast.parse(source))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in wanted
    ]


# ---------------------------------------------------------------------------
# Source access
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _bridge_source() -> str:
    return _BRIDGE_PATH.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _seam_sources() -> dict[Path, str]:
    return {p: p.read_text(encoding="utf-8") for p in sorted(_NEXT.glob("runtime_bridge_*.py"))}


@lru_cache(maxsize=1)
def _src_sources() -> dict[Path, str]:
    """Every ``src/`` module that mentions the bridge at all (cheap pre-filter)."""
    found: dict[Path, str] = {}
    for path in sorted(_SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "runtime_bridge" in text:
            found[path] = text
    return found


def _scan_files(sources: dict[Path, str], scanner: Callable[[str, tuple[str, ...]], list[str]], names: tuple[str, ...]) -> list[str]:
    return [f"{path.relative_to(_SRC.parent)}: {hit}" for path, text in sources.items() for hit in scanner(text, names)]


def _bridge() -> ModuleType:
    return importlib.import_module(_BRIDGE_MODULE)


def _owner_module(seam: str) -> ModuleType:
    return importlib.import_module(f"runtime.next.runtime_bridge_{seam}")


# ---------------------------------------------------------------------------
# The gate, per seam
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seam", _rows())
def test_check_a_prime_bridge_loads_none_of_the_names(seam: str) -> None:
    assert scan_name_loads(_bridge_source(), _names(seam)) == []


@pytest.mark.parametrize("seam", _rows())
def test_check_b_no_seam_reads_a_name_off_the_bridge(seam: str) -> None:
    assert _scan_files(_seam_sources(), scan_back_edges, _names(seam)) == []


@pytest.mark.parametrize("seam", _rows())
def test_check_b_prime_no_indirect_bridge_read_anywhere_in_src(seam: str) -> None:
    names = _names(seam, with_re_exports=False)  # CLI callers legitimately use the re-exports
    assert _scan_files(_src_sources(), scan_indirect_bridge_reads, names) == []


@pytest.mark.parametrize("seam", _rows())
def test_check_d_bridge_has_no_attribute_for_any_name(seam: str) -> None:
    """The bridge exposes no removed name (the kept re-exports are check C's).

    Subsumes the former source-level definition scan: a top-level def, assignment
    or foreign import of a removed name is an attribute at runtime. The scanner
    stays in the failure message to report the offending line numbers.
    """
    names = _names(seam, with_re_exports=False)
    present = [n for n in names if hasattr(_bridge(), n)]
    assert present == [], f"{present}; source hits: {scan_definitions(_bridge_source(), names)}"


@pytest.mark.parametrize("name", list(_KEPT_RE_EXPORTS))
def test_check_c_re_export_is_the_owning_seam_object(name: str) -> None:
    assert getattr(_bridge(), name) is getattr(_owner_module(_KEPT_RE_EXPORT_OWNERS[name]), name)
    assert name in _bridge().__all__


@pytest.mark.parametrize("seam", _rows(("io",)))
def test_call_style_bridge_calls_io_functions_on_the_seam(seam: str) -> None:
    """No bare ``get_or_start_run(...)`` in the bridge: calls go through ``_io_seam.<name>``.

    That keeps the ``runtime_bridge_io.get_or_start_run`` patches in the tests
    effective; a bare call would bind the function at import and bypass them.
    """
    assert scan_bare_calls(_bridge_source(), _names(seam)) == []


def test_no_thin_compat_delegate_docstring_left_on_the_bridge() -> None:
    assert _bridge_source().count(_LEGACY_PHRASE) == 0


def _top_level_defined_names(path: Path) -> set[str]:
    """Names bound by a top-level ``def``/``class``/assignment in *path*.

    A definition nested inside a top-level ``if``/``try`` block is not seen, so such a
    name is reported as missing: the scan fails closed rather than passing it.
    """
    names: set[str] = set()
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


@pytest.mark.parametrize("seam", [pytest.param(s, id=s) for s in _SEAMS])
def test_every_removed_name_is_defined_by_its_owning_seam(seam: str) -> None:
    """The single ownership floor: each moved name is *defined* in its owner.

    A name merely re-imported into the owner (so ``hasattr`` still holds) does
    not count: the name must be bound by a top-level definition in the owner's
    source, and a callable it binds must report the owner as its ``__module__``.
    """
    owner = _owner_module(seam)
    defined = _top_level_defined_names(_NEXT / f"runtime_bridge_{seam}.py")
    not_defined = []
    wrong_module = []
    for name in REMOVED[seam]:
        owner_name = _OWNER_NAME.get(name, name)
        if owner_name not in defined:
            not_defined.append(owner_name)
            continue
        value = getattr(owner, owner_name)
        if callable(value) and not isinstance(value, GenericAlias) and getattr(value, "__module__", owner.__name__) != owner.__name__:
            wrong_module.append(owner_name)
    assert (not_defined, wrong_module) == ([], [])


# ---------------------------------------------------------------------------
# Self-mutation: the scanners can fail (charter SO#5)
# ---------------------------------------------------------------------------

_FORWARDING_MODULE = "def _build_run_ref(*, run_id):\n    return _io._build_run_ref(run_id=run_id)\n"
_BACK_EDGE_MODULE = "def f():\n    from runtime.next import runtime_bridge as _rb\n    return _rb._build_run_ref()\n"
_BUILD = ("_build_run_ref",)


def test_scan_definitions_flags_a_forwarding_module() -> None:
    assert scan_definitions(_FORWARDING_MODULE, _BUILD) != []


@pytest.mark.parametrize(
    "source",
    [
        "_build_run_ref = _io._build_run_ref\n",
        "from somewhere import _build_run_ref\n",
        "if True:\n    pass\nclass _build_run_ref: ...\n",
        "_a, _build_run_ref = 1, 2\n",
    ],
)
def test_scan_definitions_flags_every_top_level_binding_form(source: str) -> None:
    assert scan_definitions(source, _BUILD) != []


def test_scan_definitions_allows_only_the_kept_re_exports_from_their_owner() -> None:
    kept = "from runtime.next.runtime_bridge_io import get_or_start_run\nfrom runtime.next.runtime_bridge_query import query_current_state\n"
    assert scan_definitions(kept, _KEPT_RE_EXPORTS) == []
    assert scan_definitions("from runtime.next.runtime_bridge_io import _build_run_ref\n", _BUILD) != []
    assert scan_definitions("from elsewhere import get_or_start_run\n", _KEPT_RE_EXPORTS) != []
    # A public re-export bound from the wrong seam is not legitimate (#2560).
    assert scan_definitions("from runtime.next.runtime_bridge_io import query_current_state\n", _KEPT_RE_EXPORTS) != []


def test_scan_back_edges_flags_a_deferred_bridge_attribute_lookup() -> None:
    assert scan_back_edges(_BACK_EDGE_MODULE, _BUILD) != []


@pytest.mark.parametrize(
    "header",
    ["import runtime.next.runtime_bridge as _rb", "from runtime.next import runtime_bridge as _rb", "from . import runtime_bridge as _rb"],
)
def test_scan_back_edges_recognises_every_alias_form(header: str) -> None:
    assert scan_back_edges(f"{header}\n_rb._build_run_ref()\n", _BUILD) != []


def test_scan_back_edges_ignores_names_the_bridge_still_owns() -> None:
    """FR-004 positive control: bridge-owned back-edge targets are not flagged."""
    owned = "def f():\n    from runtime.next import runtime_bridge as _rb\n    return _rb._check_cli_guards()\n"
    assert scan_back_edges(owned, _BUILD) == []
    assert scan_back_edges(owned, ("_check_cli_guards",)) != []


def test_scan_back_edges_ignores_an_unrelated_alias() -> None:
    assert scan_back_edges("import os as _rb\n_rb._build_run_ref()\n", _BUILD) == []


def test_scan_indirect_flags_a_deferred_from_import() -> None:
    source = "def f():\n    from runtime.next.runtime_bridge import _classify_exc\n    return _classify_exc\n"
    assert scan_indirect_bridge_reads(source, ("_classify_exc",)) != []


def test_scan_indirect_flags_getattr_and_dotted_reads() -> None:
    getattr_src = "from runtime.next import runtime_bridge as _rb\nx = getattr(_rb, '_build_run_ref')\n"
    dotted_src = "import runtime.next.runtime_bridge\nruntime.next.runtime_bridge._build_run_ref()\n"
    assert scan_indirect_bridge_reads(getattr_src, _BUILD) != []
    assert scan_indirect_bridge_reads(dotted_src, _BUILD) != []


def test_scan_indirect_ignores_names_the_bridge_still_owns() -> None:
    source = "def f():\n    from runtime.next.runtime_bridge import _check_cli_guards\n"
    assert scan_indirect_bridge_reads(source, _BUILD) == []


def test_scan_name_loads_flags_a_stale_annotation() -> None:
    source = "from __future__ import annotations\n\ndef f(rich: _rich_hic_prompt) -> None: ...\n"
    assert scan_name_loads(source, ("_rich_hic_prompt",)) != []
    assert scan_name_loads("_rich_hic_prompt = 1\n", ("_rich_hic_prompt",)) == []


def test_scan_bare_calls_flags_a_bare_io_call_only() -> None:
    assert scan_bare_calls("run_ref = get_or_start_run(slug, root, kind)\n", _KEPT_RE_EXPORTS) != []
    assert scan_bare_calls("run_ref = _io_seam.get_or_start_run(slug, root, kind)\n", _KEPT_RE_EXPORTS) == []
