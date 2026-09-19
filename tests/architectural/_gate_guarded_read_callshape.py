"""AST support for the FR-011 CLI error-surface-seam construction gate
(mission ``cli-error-surface-seam-01M2WJD2``, #4746/#2899, WP08/T028).

This module deliberately owns no tests (mirrors ``_gate_read_callshape.py``'s
convention) — the production-corpus assertions live in
``test_cli_error_surface_seam.py``.

Detects raw file-read / decode calls (``open``, ``Path.read_text``,
``Path.read_bytes``, ``json.load``/``json.loads``, ``yaml.safe_load``, a
local ``ruamel.yaml.YAML()`` instance's ``.load(...)``, ``tomllib.load``/
``tomllib.loads``) that are **not** reachable through
``kernel.guarded_read.read_guarded`` — i.e. not the ``parse`` argument of a
``read_guarded(...)`` call in the same module, and not a function called
(by bare name, or one hop through a lambda) from within that argument.

``contracts/guarded-read-primitive.md`` documents the sanctioned shape: a
caller passes its decoder (``json.loads``, ``yaml.safe_load``, a small
wrapper function, or a ``lambda content: helper(content, ...)``) as
``read_guarded``'s second positional argument (or its ``parse=`` keyword);
``read_guarded`` itself performs the actual file I/O and applies that
decoder to the content it read. A raw read/decode call reachable through
that argument is therefore *covered* — it never touches the filesystem on
its own, only the content ``read_guarded`` already fetched safely.

Scope of the invariant (deliberately bounded — read as "read/decode CALL
shapes are closed," not "all malformed-input errors are closed"):

- **Enumerated call shapes only.** The walker matches ``module.attr`` decode
  calls (``json.loads``, ``yaml.safe_load``, ``tomllib.load``) and the
  ``open``/``read_text``/``read_bytes`` reads above. It does NOT recognise
  ``from json import loads`` (bare-name after a from-import), aliased imports
  (``import json as j``), or ``Path.open().read()``. None of the in-scope
  modules use those shapes today, so the gate is not evaded now — but a future
  from-import edit would slip past silently. If you add such a shape, extend
  the detect sets below rather than relying on the current spelling.
- **XML is out of the detect set.** ``review/baseline.py::_parse_junit_xml``
  reads junit output with ``xml.etree.ElementTree.parse`` — the walker cannot
  see ``ET.parse`` (not in the decode set), so a malformed junit XML surfaces
  as a raw ``ET.ParseError``, not a ``GuardedReadError``. This is a known,
  low-reachability residual (junit is machine-generated local test output),
  named here for parity with the ``pydantic.ValidationError`` carve-out the
  production gate documents, and tracked as a follow-up in PR #4774.
"""

from __future__ import annotations

import ast

_RAW_READ_BUILTIN_NAMES: frozenset[str] = frozenset({"open"})
_RAW_READ_PATH_ATTRS: frozenset[str] = frozenset({"read_text", "read_bytes"})
_DECODE_MODULE_ATTRS: dict[str, frozenset[str]] = {
    "json": frozenset({"load", "loads"}),
    "yaml": frozenset({"safe_load", "load"}),
    "tomllib": frozenset({"load", "loads"}),
}
_READ_GUARDED_NAME = "read_guarded"
_YAML_CTOR_NAME = "YAML"


def _call_func_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _call_receiver_name(call: ast.Call) -> str | None:
    """Return the left-hand receiver name of an attribute call (``json`` for
    ``json.loads(...)``), or ``None`` for a bare-name call or a receiver
    that is itself an expression (not a simple ``Name``)."""
    if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name):
        return call.func.value.id
    return None


def _yaml_instance_names(tree: ast.AST) -> frozenset[str]:
    """Local variable names bound to a ``ruamel.yaml.YAML(...)`` instance —
    ``yaml = YAML()`` / ``yaml = YAML(typ="safe")`` — so ``yaml.load(...)``
    is recognised as a decode call alongside the module-level ``yaml``
    import's ``safe_load``."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        value = node.value
        if not (isinstance(value, ast.Call) and _call_func_name(value) == _YAML_CTOR_NAME):
            continue
        names.update(target.id for target in node.targets if isinstance(target, ast.Name))
    return frozenset(names)


def _open_call_is_write_mode(call: ast.Call) -> bool:
    """True when a bare ``open(...)`` call's mode argument is write/append/
    exclusive-create (``w``/``a``/``x``, with or without ``+``/``b``) —
    out of this READ-only gate's scope. Absent mode, or any ``r`` mode,
    counts as a read."""
    mode_expr = call.args[1] if len(call.args) >= 2 else next((kw.value for kw in call.keywords if kw.arg == "mode"), None)
    if not isinstance(mode_expr, ast.Constant) or not isinstance(mode_expr.value, str):
        return False
    return any(flag in mode_expr.value for flag in ("w", "a", "x"))


def _is_raw_read_call(call: ast.Call, *, yaml_instance_names: frozenset[str]) -> bool:
    """Return True when *call* is one of the named raw read/decode shapes."""
    name = _call_func_name(call)
    if name is None:
        return False
    if isinstance(call.func, ast.Name):
        return name in _RAW_READ_BUILTIN_NAMES and not _open_call_is_write_mode(call)
    if name in _RAW_READ_PATH_ATTRS:
        return True
    receiver = _call_receiver_name(call)
    if receiver is None:
        return False
    if receiver in _DECODE_MODULE_ATTRS and name in _DECODE_MODULE_ATTRS[receiver]:
        return True
    return receiver in yaml_instance_names and name == "load"


def _find_calls_named(tree: ast.AST, name: str) -> list[ast.Call]:
    return [node for node in ast.walk(tree) if isinstance(node, ast.Call) and _call_func_name(node) == name]


def _parse_argument(call: ast.Call) -> ast.expr | None:
    """Return ``read_guarded``'s decoder argument: the 2nd positional arg,
    or the ``parse=`` keyword."""
    if len(call.args) >= 2:
        return call.args[1]
    return next((kw.value for kw in call.keywords if kw.arg == "parse"), None)


def _names_referenced_by(expr: ast.expr | None) -> set[str]:
    """Names this decoder argument would call if invoked: itself (a bare
    function reference) or, one hop through a lambda, whatever it calls."""
    if isinstance(expr, ast.Name):
        return {expr.id}
    if isinstance(expr, ast.Lambda):
        return {node.func.id for node in ast.walk(expr.body) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    return set()


def _covered_function_names(tree: ast.AST) -> frozenset[str]:
    """Functions reachable as some ``read_guarded(...)`` call's decoder —
    their raw read/decode calls execute on already-guarded content, never
    touching the filesystem on their own."""
    covered: set[str] = set()
    for call in _find_calls_named(tree, _READ_GUARDED_NAME):
        covered |= _names_referenced_by(_parse_argument(call))
    return frozenset(covered)


def _iter_functions(tree: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)]


def _direct_calls(node: ast.AST) -> list[ast.Call]:
    """Calls in *node*'s own scope — recurses into lambdas and control flow,
    but stops at a nested named function/method (scanned separately as its
    own entry by :func:`_iter_functions`)."""
    calls: list[ast.Call] = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if isinstance(child, ast.Call):
            calls.append(child)
        calls.extend(_direct_calls(child))
    return calls


def find_unguarded_raw_reads(source: str) -> list[str]:
    """Return the sorted, deduplicated names of functions in *source* whose
    own scope contains a raw read/decode call not covered by
    ``read_guarded`` (directly, or one hop through its decoder argument).
    """
    tree = ast.parse(source)
    yaml_instances = _yaml_instance_names(tree)
    covered = _covered_function_names(tree)
    violating: set[str] = set()
    for func in _iter_functions(tree):
        if func.name in covered:
            continue
        if any(_is_raw_read_call(call, yaml_instance_names=yaml_instances) for call in _direct_calls(func)):
            violating.add(func.name)
    return sorted(violating)
