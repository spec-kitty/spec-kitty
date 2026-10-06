"""Acceptance gate: ``runtime_bridge`` carries no compat delegates (#2561).

The mission retires 36 "thin compat delegate" names from
``src/runtime/next/runtime_bridge.py``. Each name is owned by exactly one seam
module (``data-model.md``); after the mission the bridge neither defines it
nor does any seam read it back off the bridge. Two names, ``get_or_start_run``
and ``build_operational_context_for_claim``, stay on the bridge as public
re-exports bound by ``from runtime.next.runtime_bridge_io import ...`` (the
very same objects).

Every check is static (``ast``) except Check C (identity) and Check D (a
runtime ``hasattr`` that sees every binding form an AST walk of top-level
statements can miss). The checks run per seam so each migrating work package
flips exactly its own rows from ``xfail(strict=True)`` to passing: remove the
seam from ``_PENDING_SEAMS`` in the same diff that migrates it.

Non-vacuity (charter SO#5): the scanners are pure functions over source text
and the self-mutation tests below feed them synthetic offenders.
"""

from __future__ import annotations

import ast
import importlib
from collections.abc import Callable, Iterator
from functools import lru_cache
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SRC = Path(__file__).resolve().parents[2] / "src"
_NEXT = _SRC / "runtime" / "next"
_BRIDGE_PATH = _NEXT / "runtime_bridge.py"
_BRIDGE_MODULE = "runtime.next.runtime_bridge"
_IO_MODULE = "runtime.next.runtime_bridge_io"
_KEPT_RE_EXPORTS = ("get_or_start_run", "build_operational_context_for_claim")

REMOVED: dict[str, tuple[str, ...]] = {
    "identity": (
        "_primary_runtime_feature_dir",
        "_resolve_coordination_branch",
        "_resolve_mission_ulid",
    ),
    "cores": (
        "_parse_wp_sections_from_tasks_md",
        "_parse_requirement_refs_from_tasks_md",
    ),
    "engine": ("_advance_run_state_after_composition",),
    "retrospective": (
        "_BufferingRuntimeEmitter",
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
}
_SEAMS = tuple(REMOVED)
_EXPECTED_TOTAL = 36

#: Owner-side name where it differs from the bridge-side name.
_OWNER_NAME = {
    "_load_feature_runs": "load_feature_runs",
    "_advance_run_state_after_composition": "advance_run_state_after_composition",
}

#: The work package that migrates each seam (xfail reason).
_MIGRATING_WP = {
    "identity": "WP02",
    "cores": "WP02",
    "engine": "WP02",
    "retrospective": "WP03",
    "composition": "WP04",
    "io": "WP05",
}

#: Seams not yet migrated. Each migrating WP removes its seam in its own diff.
_PENDING_SEAMS = {"io"}

#: Rows whose check already holds on the pre-mission tree. They are a plain
#: regression guard from day one (a strict xfail would XPASS and go red).
_GREEN_TODAY: frozenset[tuple[str, str]] = frozenset({("B", "cores"), ("B", "engine")} | {("B'", seam) for seam in _SEAMS})

_LEGACY_PHRASE = "Thin compat delegate"


def _names(seam: str, *, with_re_exports: bool = True) -> tuple[str, ...]:
    names = REMOVED[seam]
    if with_re_exports:
        return names
    return tuple(n for n in names if n not in _KEPT_RE_EXPORTS)


def _row(check: str, seam: str) -> object:
    """A parametrize entry for ``seam``; strict-xfail while the seam is pending."""
    if seam in _PENDING_SEAMS and (check, seam) not in _GREEN_TODAY:
        mark = pytest.mark.xfail(strict=True, reason=f"migrated in {_MIGRATING_WP[seam]}")
        return pytest.param(seam, marks=mark, id=seam)
    return pytest.param(seam, id=seam)


def _rows(check: str, seams: tuple[str, ...] = _SEAMS) -> list[object]:
    return [_row(check, seam) for seam in seams]


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
        legitimate = node.module == _IO_MODULE and node.level == 0 and bound in _KEPT_RE_EXPORTS and alias.asname is None
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


def test_removed_table_pins_36_names() -> None:
    """Concrete floor so a shrinking table cannot make the gate vacuous."""
    counts = {seam: len(names) for seam, names in REMOVED.items()}
    assert counts == {"identity": 3, "cores": 2, "engine": 1, "retrospective": 9, "composition": 8, "io": 13}
    flat = [n for names in REMOVED.values() for n in names]
    assert len(flat) == len(set(flat)) == _EXPECTED_TOTAL


@pytest.mark.parametrize("seam", _rows("A"))
def test_check_a_bridge_defines_none_of_the_names(seam: str) -> None:
    assert scan_definitions(_bridge_source(), _names(seam)) == []


@pytest.mark.parametrize("seam", _rows("A'"))
def test_check_a_prime_bridge_loads_none_of_the_names(seam: str) -> None:
    assert scan_name_loads(_bridge_source(), _names(seam)) == []


@pytest.mark.parametrize("seam", _rows("B"))
def test_check_b_no_seam_reads_a_name_off_the_bridge(seam: str) -> None:
    assert _scan_files(_seam_sources(), scan_back_edges, _names(seam)) == []


@pytest.mark.parametrize("seam", _rows("B'"))
def test_check_b_prime_no_indirect_bridge_read_anywhere_in_src(seam: str) -> None:
    names = _names(seam, with_re_exports=False)  # CLI callers legitimately use the re-exports
    assert _scan_files(_src_sources(), scan_indirect_bridge_reads, names) == []


@pytest.mark.parametrize("seam", _rows("D"))
def test_check_d_bridge_has_no_attribute_for_any_name(seam: str) -> None:
    present = [n for n in _names(seam, with_re_exports=False) if hasattr(_bridge(), n)]
    assert present == []


def _named_row(check: str, name: str) -> object:
    """Like :func:`_row` but keyed on a re-exported name of the ``io`` seam."""
    if "io" in _PENDING_SEAMS and (check, "io") not in _GREEN_TODAY:
        return pytest.param(name, marks=pytest.mark.xfail(strict=True, reason=f"migrated in {_MIGRATING_WP['io']}"), id=name)
    return pytest.param(name, id=name)


@pytest.mark.parametrize("name", [_named_row("C", n) for n in _KEPT_RE_EXPORTS])
def test_check_c_re_export_is_the_owning_seam_object(name: str) -> None:
    assert getattr(_bridge(), name) is getattr(_owner_module("io"), name)
    assert name in _bridge().__all__


@pytest.mark.parametrize("seam", _rows("call-style", ("io",)))
def test_call_style_bridge_calls_io_functions_on_the_seam(seam: str) -> None:
    assert scan_bare_calls(_bridge_source(), _names(seam)) == []


@pytest.mark.xfail(strict=True, reason="WP06")
def test_no_thin_compat_delegate_docstring_left_on_the_bridge() -> None:
    assert _bridge_source().count(_LEGACY_PHRASE) == 0


@pytest.mark.parametrize("seam", [pytest.param(s, id=s) for s in _SEAMS])
def test_floor_every_removed_name_exists_on_its_owning_seam(seam: str) -> None:
    owner = _owner_module(seam)
    missing = [n for n in REMOVED[seam] if not hasattr(owner, _OWNER_NAME.get(n, n))]
    assert missing == []


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


def test_scan_definitions_allows_only_the_kept_re_exports_from_io() -> None:
    kept = "from runtime.next.runtime_bridge_io import get_or_start_run\n"
    assert scan_definitions(kept, _KEPT_RE_EXPORTS) == []
    assert scan_definitions("from runtime.next.runtime_bridge_io import _build_run_ref\n", _BUILD) != []
    assert scan_definitions("from elsewhere import get_or_start_run\n", _KEPT_RE_EXPORTS) != []


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
    owned = "def f():\n    from runtime.next import runtime_bridge as _rb\n    return _rb._should_advance_wp_step()\n"
    assert scan_back_edges(owned, _BUILD) == []
    assert scan_back_edges(owned, ("_should_advance_wp_step",)) != []


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
    source = "def f():\n    from runtime.next.runtime_bridge import _should_advance_wp_step\n"
    assert scan_indirect_bridge_reads(source, _BUILD) == []


def test_scan_name_loads_flags_a_stale_annotation() -> None:
    source = "from __future__ import annotations\n\ndef f(buffer: _BufferingRuntimeEmitter) -> None: ...\n"
    assert scan_name_loads(source, ("_BufferingRuntimeEmitter",)) != []
    assert scan_name_loads("_BufferingRuntimeEmitter = 1\n", ("_BufferingRuntimeEmitter",)) == []


def test_scan_bare_calls_flags_a_bare_io_call_only() -> None:
    assert scan_bare_calls("run_ref = get_or_start_run(slug, root, kind)\n", _KEPT_RE_EXPORTS) != []
    assert scan_bare_calls("run_ref = _io_seam.get_or_start_run(slug, root, kind)\n", _KEPT_RE_EXPORTS) == []
