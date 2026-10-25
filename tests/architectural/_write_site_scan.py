"""Static write-site scanner shared by the event-log writes gates.

Extracted from ``test_status_events_writes_gate.py`` (#6603) so the
multi-log gate (``test_event_log_writes_gate.py``) reuses the same,
non-vacuity-tested scanner instead of a second copy. The behaviour is
unchanged; see the status gate's docstring for the resolution rules.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"

EVENTS_LOG = "status.events.jsonl"
STORE_MODULE = "specify_cli.status.store"
_EVENTS_CONST_HOMES = frozenset({"specify_cli.status", "specify_cli.status.store", "specify_cli.status._unsafe"})
_EVENTS_CONST_NAME = "EVENTS_FILENAME"
_WRITE_FLAG_TOKENS = ("O_WRONLY", "O_RDWR", "O_APPEND", "O_TRUNC", "O_CREAT")
_RENAME_KINDS = frozenset({"os.replace", "os.rename", "shutil.move"})
_PATH_WRAPPERS = frozenset({"Path", "PurePath", "PurePosixPath", "PureWindowsPath", "str"})
_PATH_PASSTHROUGH_METHODS = frozenset({"resolve", "absolute", "expanduser"})
_SELF_NAMES = frozenset({"self", "cls"})
_MAX_DEPTH = 16


@dataclass(frozen=True)
class WriteSite:
    """One write-mode file operation found by the scanner."""

    module: str
    lineno: int
    kind: str
    mode: str
    path_expr: str
    path_text: str | None

    @property
    def targets_events_log(self) -> bool:
        return self.path_text is not None and self.path_text.endswith(EVENTS_LOG)

    @property
    def is_event_named(self) -> bool:
        return "event" in self.path_expr.lower()

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.module, self.kind, self.path_expr)


# ---------------------------------------------------------------------------
# Module context: what the resolver may consult besides the expression itself
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _ModuleContext:
    functions: Mapping[str, ast.FunctionDef]
    module_assignments: Mapping[str, ast.expr]
    self_attributes: Mapping[str, tuple[ast.expr, ast.FunctionDef | None]]
    events_aliases: frozenset[str]
    parents: Mapping[ast.AST, ast.AST]
    calls: tuple[ast.Call, ...]


def _assignment_targets(node: ast.AST) -> Iterable[tuple[ast.expr, ast.expr]]:
    if isinstance(node, ast.Assign):
        return ((target, node.value) for target in node.targets)
    if isinstance(node, ast.AnnAssign) and node.value is not None:
        return ((node.target, node.value),)
    return ()


def _events_aliases(tree: ast.Module) -> frozenset[str]:
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module in _EVENTS_CONST_HOMES or (node.level and node.module in {"store", None})):
            aliases.update(alias.asname or alias.name for alias in node.names if alias.name == _EVENTS_CONST_NAME)
    return frozenset(aliases)


def _enclosing(parents: Mapping[ast.AST, ast.AST], node: ast.AST, kind: type) -> ast.AST | None:
    current = parents.get(node)
    while current is not None and not isinstance(current, kind):
        current = parents.get(current)
    return current


def _enclosing_function(parents: Mapping[ast.AST, ast.AST], node: ast.AST) -> ast.FunctionDef | None:
    found = _enclosing(parents, node, ast.FunctionDef)
    return found if isinstance(found, ast.FunctionDef) else None


def _build_context(tree: ast.Module) -> _ModuleContext:
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    module_assignments: dict[str, ast.expr] = {}
    for node in tree.body:
        for target, value in _assignment_targets(node):
            if isinstance(target, ast.Name):
                module_assignments[target.id] = value
    self_attributes: dict[str, tuple[ast.expr, ast.FunctionDef | None]] = {}
    for node in ast.walk(tree):
        for target, value in _assignment_targets(node):
            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id in _SELF_NAMES:
                self_attributes[target.attr] = (value, _enclosing_function(parents, node))
    calls = tuple(node for node in ast.walk(tree) if isinstance(node, ast.Call))
    return _ModuleContext(functions, module_assignments, self_attributes, _events_aliases(tree), parents, calls)


# ---------------------------------------------------------------------------
# Static path resolution
# ---------------------------------------------------------------------------


class _Resolver:
    """Best-effort static text of a path expression (only its tail matters)."""

    def __init__(self, ctx: _ModuleContext) -> None:
        self._ctx = ctx

    def resolve(self, expr: ast.expr, fn: ast.FunctionDef | None, depth: int = 0) -> str | None:
        if depth > _MAX_DEPTH:
            return None
        handler = self._handlers.get(type(expr))
        return handler(self, expr, fn, depth + 1) if handler else None

    def _constant(self, expr: ast.Constant, _fn: ast.FunctionDef | None, _depth: int) -> str | None:
        return expr.value if isinstance(expr.value, str) else None

    def _joined(self, expr: ast.JoinedStr, fn: ast.FunctionDef | None, depth: int) -> str | None:
        parts: list[str] = []
        for value in expr.values:
            if isinstance(value, ast.Constant):
                parts.append(str(value.value))
            elif isinstance(value, ast.FormattedValue):
                parts.append(self.resolve(value.value, fn, depth) or "{}")
        return "".join(parts)

    def _binop(self, expr: ast.BinOp, fn: ast.FunctionDef | None, depth: int) -> str | None:
        if isinstance(expr.op, ast.Div):
            return self.resolve(expr.right, fn, depth)
        if isinstance(expr.op, ast.Add):
            right = self.resolve(expr.right, fn, depth)
            return None if right is None else (self.resolve(expr.left, fn, depth) or "{}") + right
        if isinstance(expr.op, ast.Mod):
            return self.resolve(expr.left, fn, depth)
        return None

    def _call(self, expr: ast.Call, fn: ast.FunctionDef | None, depth: int) -> str | None:
        func = expr.func
        if isinstance(func, ast.Name):
            return self._call_by_name(func.id, expr, fn, depth)
        if isinstance(func, ast.Attribute):
            return self._call_by_method(func, expr, fn, depth)
        return None

    def _call_by_name(self, name: str, expr: ast.Call, fn: ast.FunctionDef | None, depth: int) -> str | None:
        if name in _PATH_WRAPPERS and expr.args:
            return self.resolve(expr.args[0], fn, depth)
        target = self._ctx.functions.get(name)
        return self._function_return(target, depth) if target is not None else None

    def _call_by_method(self, func: ast.Attribute, expr: ast.Call, fn: ast.FunctionDef | None, depth: int) -> str | None:
        if isinstance(func.value, ast.Name) and func.value.id == "pathlib" and func.attr in _PATH_WRAPPERS and expr.args:
            return self.resolve(expr.args[0], fn, depth)
        if func.attr in _PATH_PASSTHROUGH_METHODS:
            return self.resolve(func.value, fn, depth)
        if func.attr in {"joinpath", "with_name"} and expr.args:
            return self.resolve(expr.args[-1], fn, depth)
        return None

    def _function_return(self, target: ast.FunctionDef, depth: int) -> str | None:
        returns = [node for node in ast.walk(target) if isinstance(node, ast.Return) and node.value is not None]
        return self._agree(self.resolve(node.value, target, depth) for node in returns)

    def _attribute(self, expr: ast.Attribute, _fn: ast.FunctionDef | None, depth: int) -> str | None:
        if isinstance(expr.value, ast.Name) and expr.value.id in _SELF_NAMES and expr.attr in self._ctx.self_attributes:
            value, owner = self._ctx.self_attributes[expr.attr]
            return self.resolve(value, owner, depth)
        return None

    def _name(self, expr: ast.Name, fn: ast.FunctionDef | None, depth: int) -> str | None:
        if expr.id in self._ctx.events_aliases:
            return EVENTS_LOG
        local = _last_local_assignment(fn, expr.id) if fn is not None else None
        if local is not None:
            return self.resolve(local, fn, depth)
        module_value = self._ctx.module_assignments.get(expr.id)
        if module_value is not None:
            return self.resolve(module_value, None, depth)
        return self._parameter(fn, expr.id, depth) if fn is not None else None

    def _parameter(self, fn: ast.FunctionDef, name: str, depth: int) -> str | None:
        """A parameter resolves when every same-module call site passes the same static tail."""
        position = _parameter_position(fn, name)
        if position is None:
            return None
        arguments = [_argument_for(call, name, position) for call in _call_sites_of(self._ctx, fn)]
        if not arguments or any(argument is None for argument in arguments):
            return None
        return self._agree(self.resolve(argument, _enclosing_function(self._ctx.parents, argument), depth) for argument in arguments if argument is not None)

    @staticmethod
    def _agree(values: Iterable[str | None]) -> str | None:
        distinct = set(values)
        return distinct.pop() if len(distinct) == 1 else None

    _handlers = {
        ast.Constant: _constant,
        ast.JoinedStr: _joined,
        ast.BinOp: _binop,
        ast.Call: _call,
        ast.Attribute: _attribute,
        ast.Name: _name,
    }


def _last_local_assignment(fn: ast.FunctionDef, name: str) -> ast.expr | None:
    found: ast.expr | None = None
    for node in ast.walk(fn):
        for target, value in _assignment_targets(node):
            if isinstance(target, ast.Name) and target.id == name and not (isinstance(value, ast.Name) and value.id == name):
                found = value
    return found


def _parameter_position(fn: ast.FunctionDef, name: str) -> int | None:
    """Positional index of ``name`` among the caller-visible arguments (``-1`` = keyword-only)."""
    positional = [arg.arg for arg in fn.args.posonlyargs + fn.args.args]
    if positional and positional[0] in _SELF_NAMES:
        positional = positional[1:]
    if name in positional:
        return positional.index(name)
    return -1 if name in {arg.arg for arg in fn.args.kwonlyargs} else None


def _argument_for(call: ast.Call, name: str, position: int) -> ast.expr | None:
    keyword = next((kw.value for kw in call.keywords if kw.arg == name), None)
    if keyword is not None:
        return keyword
    if 0 <= position < len(call.args) and not isinstance(call.args[position], ast.Starred):
        return call.args[position]
    return None


def _call_sites_of(ctx: _ModuleContext, fn: ast.FunctionDef) -> list[ast.Call]:
    """Same-module calls of ``fn``: ``name(...)``, ``self.name(...)``, ``Class(...)`` for ``__init__``."""
    owner = _enclosing(ctx.parents, fn, ast.ClassDef)
    names = {fn.name} if fn.name != "__init__" or not isinstance(owner, ast.ClassDef) else {owner.name, *_SELF_NAMES}
    return [call for call in ctx.calls if _is_call_of(call.func, names)]


def _is_call_of(func: ast.expr, names: set[str]) -> bool:
    if isinstance(func, ast.Name):
        return func.id in names
    return isinstance(func, ast.Attribute) and func.attr in names and isinstance(func.value, ast.Name) and func.value.id in _SELF_NAMES


# ---------------------------------------------------------------------------
# Write-site detection
# ---------------------------------------------------------------------------


def _keyword(call: ast.Call, name: str) -> ast.expr | None:
    return next((kw.value for kw in call.keywords if kw.arg == name), None)


def _positional_or_keyword(call: ast.Call, index: int, name: str) -> ast.expr | None:
    if len(call.args) > index:
        return call.args[index]
    return _keyword(call, name)


def _mode_text(expr: ast.expr | None, default: str) -> str:
    if expr is None:
        return default
    return expr.value if isinstance(expr, ast.Constant) and isinstance(expr.value, str) else "?"


def _is_write_mode(mode: str) -> bool:
    return mode == "?" or any(flag in mode for flag in "wax+")


def _dotted(func: ast.expr) -> str | None:
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return f"{func.value.id}.{func.attr}"
    return None


def classify_call(call: ast.Call) -> tuple[str, str, ast.expr] | None:
    """(kind, mode, path expression) when ``call`` is a write-mode file operation."""
    func = call.func
    dotted = _dotted(func)
    if (isinstance(func, ast.Name) and func.id == "open") or dotted == "io.open":
        path = _positional_or_keyword(call, 0, "file")
        mode = _mode_text(_positional_or_keyword(call, 1, "mode"), "r")
        return ("open", mode, path) if path is not None and _is_write_mode(mode) else None
    if dotted == "os.open":
        flags = _positional_or_keyword(call, 1, "flags")
        flag_text = ast.unparse(flags) if flags is not None else "?"
        writes = flag_text == "?" or any(token in flag_text for token in _WRITE_FLAG_TOKENS)
        return ("os.open", flag_text, call.args[0]) if writes and call.args else None
    if dotted in _RENAME_KINDS:
        destination = _positional_or_keyword(call, 1, "dst")
        return (dotted, "replace", destination) if destination is not None else None
    return _classify_method_call(func, call)


def _classify_method_call(func: ast.expr, call: ast.Call) -> tuple[str, str, ast.expr] | None:
    if not isinstance(func, ast.Attribute):
        return None
    if func.attr in {"write_text", "write_bytes"}:
        return (func.attr, "w", func.value)
    if func.attr == "open":
        mode = _mode_text(_positional_or_keyword(call, 0, "mode"), "r")
        return ("Path.open", mode, func.value) if _is_write_mode(mode) else None
    return None


def scan_write_sites(module: str, tree: ast.Module) -> list[WriteSite]:
    """Every write-mode file operation in ``tree`` with its resolved path text."""
    ctx = _build_context(tree)
    resolver = _Resolver(ctx)
    sites: list[WriteSite] = []
    for node in ctx.calls:
        classified = classify_call(node)
        if classified is None:
            continue
        kind, mode, path = classified
        text = resolver.resolve(path, _enclosing_function(ctx.parents, node))
        sites.append(WriteSite(module, node.lineno, kind, mode, ast.unparse(path), text))
    return sites


def scan_write_sites_from_source(module: str, source: str) -> list[WriteSite]:
    return scan_write_sites(module, ast.parse(source))


def module_name_for(path: Path, src_root: Path = _SRC) -> str:
    parts = list(path.relative_to(src_root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)
