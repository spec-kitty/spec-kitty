"""Gate: no raw ``activated_<plural>`` membership checks outside the activation seam (WP05, FR-006, M2).

The effective set of a kind is its allow state **minus the effective deny**
(ADR ``2026-10-19-1`` Decision 2). A reader that tests ``ctx.activated_<plural>
is None`` (or ``x in ctx.activated_<plural>``, or reads the field through
``getattr`` with an ``activated_*`` name) decides membership from the allow
list alone, so a deactivated id under an absent ("all") allow list leaks back.
Readers go through :class:`~charter.activation.pack_context.PackContext`'s
accessors (``allow_for``, ``denied_for``, ``admits``, ``effective_ids``)
instead.

Patterns flagged, over every module under ``src/``:

* ``<x>.activated_<plural> is None`` / ``is not None`` (either side), and a
  name bound from such an attribute compared the same way;
* ``... in <x>.activated_<plural>`` / ``not in`` (and a name bound from one);
* a truthiness fallback ``<x>.activated_<plural> or <default>``;
* ``getattr(<x>, <name>)`` where ``<name>`` is an ``activated_<plural>`` string,
  an f-string starting with ``activated_``, an ``allow_key(...)`` call, or a
  name derived from one (module constant, loop target, local assignment, or a
  parameter some call in the module passes such a value);
* ``getattr(<ctx>, <dynamic>)`` on a ``PackContext``-typed receiver (an
  annotated parameter / local, or ``PackContext.from_config(...)``).

The plural set derives from :class:`ArtifactKind` (C-004). Only
``pack_context.py`` and ``activation_ledger.py`` may hold these patterns.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

from charter.offering.artifact_kinds import ArtifactKind
from tests.architectural._ast_scan import parse_source, read_source

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"

#: The ``activated_<plural>`` field names of every charter-activatable kind.
ACTIVATED_FIELDS: frozenset[str] = frozenset(f"activated_{kind.plural}" for kind in ArtifactKind if kind.activatable)

#: The seam: the only modules allowed to read allow-list membership raw.
PERMITTED: frozenset[str] = frozenset(
    {
        "src/charter/activation/pack_context.py",
        "src/charter/activation/activation_ledger.py",
    }
)

#: Temporary entries outside the seam (WP06 drained the last specify_cli readers; must stay empty).
TEMPORARY: dict[str, str] = {}

_PACK_CONTEXT_NAMES = frozenset({"PackContext", "_PackContext"})
_PREFILTER_TOKENS = ("activated_", "allow_key", "PackContext")


@dataclass(frozen=True)
class Hit:
    path: str
    line: int
    pattern: str


# --------------------------------------------------------------------------- #
# Taint helpers
# --------------------------------------------------------------------------- #


def _is_activated_literal(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value in ACTIVATED_FIELDS
    if isinstance(node, ast.JoinedStr) and node.values:
        head = node.values[0]
        return isinstance(head, ast.Constant) and isinstance(head.value, str) and head.value.startswith("activated_")
    if isinstance(node, ast.Call):
        func = node.func
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
        return name == "allow_key"
    return False


def _value_nodes(node: ast.AST) -> list[ast.AST]:
    """The sub-nodes that can flow into a value: comparisons (booleans) and comprehension filters are skipped."""
    out: list[ast.AST] = []
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, ast.Compare):
            continue
        out.append(current)
        if isinstance(current, ast.comprehension):
            stack.extend((current.target, current.iter))
            continue
        stack.extend(ast.iter_child_nodes(current))
    return out


def _contains_taint(node: ast.AST, tainted: set[str]) -> bool:
    for sub in _value_nodes(node):
        if _is_activated_literal(sub):
            return True
        if isinstance(sub, ast.Name) and sub.id in tainted:
            return True
    return False


def _is_activated_attribute(node: ast.AST) -> bool:
    return isinstance(node, ast.Attribute) and node.attr in ACTIVATED_FIELDS


def _target_names(target: ast.AST) -> list[str]:
    return [sub.id for sub in ast.walk(target) if isinstance(sub, ast.Name)]


def _bindings(scope: ast.AST) -> list[tuple[list[str], ast.AST]]:
    """``(target names, value)`` for every assignment / loop / comprehension binding in *scope*."""
    out: list[tuple[list[str], ast.AST]] = []
    for node in ast.walk(scope):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                out.append((_target_names(target), node.value))
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and node.value is not None:
            out.append((_target_names(node.target), node.value))
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            out.append((_target_names(node.target), node.iter))
    return out


def _fixpoint(bindings: list[tuple[list[str], ast.AST]], seed: set[str]) -> set[str]:
    tainted = set(seed)
    changed = True
    while changed:
        changed = False
        for names, value in bindings:
            if _contains_taint(value, tainted) and not set(names) <= tainted:
                tainted.update(names)
                changed = True
    return tainted


def _call_name(call: ast.Call) -> str:
    func = call.func
    return func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""


def _tainted_params(tree: ast.Module, tainted_module: set[str]) -> dict[str, set[str]]:
    """Per function name, the parameters some call in the module passes an ``activated_*`` value."""
    params: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names = [arg.arg for arg in (*node.args.posonlyargs, *node.args.args)]
            params[node.name] = names[1:] if names[:1] in (["self"], ["cls"]) else names
    out: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _call_name(node) not in params:
            continue
        names = params[_call_name(node)]
        for index, arg in enumerate(node.args):
            if index < len(names) and _contains_taint(arg, tainted_module):
                out.setdefault(_call_name(node), set()).add(names[index])
        for keyword in node.keywords:
            if keyword.arg is not None and _contains_taint(keyword.value, tainted_module):
                out.setdefault(_call_name(node), set()).add(keyword.arg)
    return out


def _annotation_is_pack_context(annotation: ast.AST | None) -> bool:
    if annotation is None:
        return False
    for sub in ast.walk(annotation):
        if isinstance(sub, ast.Name) and sub.id in _PACK_CONTEXT_NAMES:
            return True
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str) and "PackContext" in sub.value:
            return True
    return False


def _is_pack_context_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name):
        return func.id in _PACK_CONTEXT_NAMES
    return isinstance(func, ast.Attribute) and func.attr == "from_config" and isinstance(func.value, ast.Name) and func.value.id in _PACK_CONTEXT_NAMES


def _pack_context_names(function: ast.AST) -> set[str]:
    names: set[str] = set()
    if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
        args = function.args
        for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs):
            if _annotation_is_pack_context(arg.annotation):
                names.add(arg.arg)
    for node in ast.walk(function):
        if isinstance(node, ast.AnnAssign) and _annotation_is_pack_context(node.annotation):
            names.update(_target_names(node.target))
        elif isinstance(node, ast.Assign) and _is_pack_context_call(node.value):
            for target in node.targets:
                names.update(_target_names(target))
    return names


# --------------------------------------------------------------------------- #
# Scanner
# --------------------------------------------------------------------------- #


def _attribute_bound_names(scope: ast.AST) -> set[str]:
    return {name for names, value in _bindings(scope) if _is_activated_attribute(value) for name in names}


def _is_raw_operand(side: ast.AST, attr_names: set[str]) -> bool:
    return _is_activated_attribute(side) or (isinstance(side, ast.Name) and side.id in attr_names)


def _compare_hits(node: ast.Compare, attr_names: set[str]) -> list[str]:
    def raw(side: ast.AST) -> bool:
        return _is_raw_operand(side, attr_names)

    operands = [node.left, *node.comparators]
    hits: list[str] = []
    for index, op in enumerate(node.ops):
        lhs, rhs = operands[index], operands[index + 1]
        if isinstance(op, (ast.Is, ast.IsNot)) and (raw(lhs) or raw(rhs)):
            hits.append("is None")
        elif isinstance(op, (ast.In, ast.NotIn)) and raw(rhs):
            hits.append("in")
    return hits


def _getattr_hit(node: ast.Call, tainted: set[str], ctx_names: set[str]) -> str | None:
    if not (isinstance(node.func, ast.Name) and node.func.id == "getattr" and len(node.args) >= 2):
        return None
    receiver, name = node.args[0], node.args[1]
    if _is_activated_literal(name) or (isinstance(name, ast.Name) and name.id in tainted):
        return "getattr activated_*"
    dynamic = not (isinstance(name, ast.Constant) and isinstance(name.value, str))
    typed = _is_pack_context_call(receiver) or (isinstance(receiver, ast.Name) and receiver.id in ctx_names)
    return "getattr PackContext" if dynamic and typed else None


def _scope_hits(scope: ast.AST, seed: set[str], ctx_names: set[str]) -> list[tuple[int, str]]:
    tainted = _fixpoint(_bindings(scope), seed)
    attr_names = _attribute_bound_names(scope)
    found: list[tuple[int, str]] = []
    for node in ast.walk(scope):
        if isinstance(node, ast.Compare):
            found.extend((node.lineno, pattern) for pattern in _compare_hits(node, attr_names))
        elif isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or) and _is_raw_operand(node.values[0], attr_names):
            found.append((node.lineno, "or fallback"))
        elif isinstance(node, ast.Call):
            pattern = _getattr_hit(node, tainted, ctx_names)
            if pattern is not None:
                found.append((node.lineno, pattern))
    return found


def scan_source(source: str, display: str) -> list[Hit]:
    """Every raw ``activated_<plural>`` membership pattern in *source*.

    A module naming none of ``activated_``, ``allow_key`` or ``PackContext``
    cannot hold a pattern (each needs one of them), so it is parsed but not walked.
    """
    tree = parse_source(source, display=display)
    if not any(token in source for token in _PREFILTER_TOKENS):
        return []
    module_level = [stmt for stmt in tree.body if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    module_tainted = _fixpoint([binding for stmt in module_level for binding in _bindings(stmt)], set())
    params = _tainted_params(tree, module_tainted)
    found: set[tuple[int, str]] = set()
    for stmt in module_level:
        found.update(_scope_hits(stmt, module_tainted, set()))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            seed = module_tainted | params.get(node.name, set())
            found.update(_scope_hits(node, seed, _pack_context_names(node)))
    return [Hit(display, line, pattern) for line, pattern in sorted(found)]


def _scan_tree(root: Path) -> list[Hit]:
    hits: list[Hit] = []
    for path in sorted(root.rglob("*.py")):
        display = path.relative_to(_REPO_ROOT).as_posix()
        hits.extend(scan_source(read_source(path, display=display), display))
    return hits


# --------------------------------------------------------------------------- #
# The gate
# --------------------------------------------------------------------------- #


def test_plural_set_derives_from_the_artifact_kind_authority() -> None:
    assert {"activated_directives", "activated_skills", "activated_mission_step_contracts"} <= ACTIVATED_FIELDS
    assert len(ACTIVATED_FIELDS) == sum(1 for kind in ArtifactKind if kind.activatable)
    assert "activated_kinds" not in ACTIVATED_FIELDS  # not an artifact kind: no deny list
    assert "activated_mission_types" not in ACTIVATED_FIELDS


def test_no_raw_activation_membership_outside_the_seam() -> None:
    hits = _scan_tree(_SRC)
    outside = sorted({hit.path for hit in hits if hit.path not in PERMITTED})
    detail = "\n".join(f"  {hit.path}:{hit.line} ({hit.pattern})" for hit in hits if hit.path not in PERMITTED and hit.path not in TEMPORARY)
    assert outside == sorted(TEMPORARY), (
        "Raw activated_<plural> membership outside the activation seam; use PackContext.allow_for / denied_for / admits / effective_ids:\n" + detail
    )


def test_the_temporary_allowlist_is_drained() -> None:
    """WP06 moved every specify_cli reader onto the accessors; the allowlist must not grow back."""
    assert TEMPORARY == {}


def test_the_seam_itself_is_scanned() -> None:
    """Concrete floor on real code: the seam's own accessors hold the pattern, so the scanner reaches them."""
    hits = _scan_tree(_SRC / "charter" / "activation")
    assert any(hit.path == "src/charter/activation/pack_context.py" for hit in hits)


# --------------------------------------------------------------------------- #
# Concrete floor and self-mutation
# --------------------------------------------------------------------------- #

#: The pre-WP05 ``resolver.py:247`` shape: a ``PackContext`` field read by name.
_PRE_CHANGE_RESOLVER = """
class ActiveCharterService:
    def _activation_for(self, field_name: str) -> frozenset[str] | None:
        pack_ctx: PackContext | None = object.__getattribute__(self, "_pack_context")
        if pack_ctx is None:
            return None
        value: frozenset[str] | None = getattr(pack_ctx, field_name)
        return value

    def paradigms(self):
        return self._gated(ArtifactKind.PARADIGM, {}, self._activation_for("activated_paradigms"))
"""


def test_scanner_flags_the_pre_change_resolver_pattern() -> None:
    hits = scan_source(_PRE_CHANGE_RESOLVER, "snippet.py")
    assert len(hits) >= 1
    assert any(hit.pattern.startswith("getattr") for hit in hits)


@pytest.mark.parametrize(
    ("snippet", "pattern"),
    [
        ("def f(ctx):\n    return ctx.activated_directives is None\n", "is None"),
        ("def f(ctx):\n    return ctx.activated_tactics is not None\n", "is None"),
        ("def f(ctx):\n    value = ctx.activated_tactics\n    return value is None\n", "is None"),
        ("def f(ctx, x):\n    return x in ctx.activated_skills\n", "in"),
        ("def f(ctx, x):\n    return x not in ctx.activated_agent_profiles\n", "in"),
        ("def f(ctx):\n    return getattr(ctx, 'activated_paradigms')\n", "getattr activated_*"),
        ("def f(ctx, kind):\n    return getattr(ctx, f'activated_{kind.plural}', None)\n", "getattr activated_*"),
        ("def f(ctx, kind):\n    return getattr(ctx, allow_key(kind))\n", "getattr activated_*"),
        ("FIELDS = ('activated_directives',)\ndef f(ctx):\n    return [getattr(ctx, name) for name in FIELDS]\n", "getattr activated_*"),
        ("def g(ctx, key):\n    return getattr(ctx, key)\ndef f(ctx):\n    return g(ctx, 'activated_styleguides')\n", "getattr activated_*"),
        ("def f(repo, key):\n    return getattr(PackContext.from_config(repo), key, None)\n", "getattr PackContext"),
        ("def f(context: PackContext, key):\n    return getattr(context, key)\n", "getattr PackContext"),
        ("def f(ctx, every):\n    return ctx.activated_tactics or every\n", "or fallback"),
    ],
)
def test_scanner_flags_each_pattern(tmp_path: Path, snippet: str, pattern: str) -> None:
    """Self-mutation: a temp module carrying the pattern is flagged."""
    module = tmp_path / "mutant.py"
    module.write_text(snippet, encoding="utf-8")
    hits = scan_source(read_source(module, display="mutant.py"), "mutant.py")
    assert [hit.pattern for hit in hits] == [pattern]


@pytest.mark.parametrize(
    "snippet",
    [
        "def f(ctx):\n    return ctx.activated_kinds is None\n",
        "def f(ctx, x):\n    return x in ctx.activated_mission_types\n",
        "def f(ctx, kind):\n    return ctx.allow_for(kind) is None\n",
        "def f(service, slot):\n    return getattr(service, slot, None)\n",
        "def f(context: PackContext):\n    return getattr(context, 'repo_root')\n",
    ],
)
def test_scanner_ignores_accessors_and_non_kind_fields(snippet: str) -> None:
    assert scan_source(snippet, "clean.py") == []
