"""Patch-site liveness gate for every ``tasks_*`` seam and the ``tasks`` bridge.

Originated as the move-task gate (#5629 FR-008, SC-004); broadened by #5684 to
every ``src/specify_cli/cli/commands/agent/tasks_*.py`` module plus the
``tasks`` namespace module. The module set is derived from the filesystem.

A ``patch``/``monkeypatch`` that targets a name in one of these modules only
intercepts anything if the call is dispatched through that module's globals.
After a verbatim move, a patch left on the old home module silently stops
intercepting: the test stays green while exercising the real function.

Seam-module rule: a name is live for ``tasks_*`` module M when it is imported at call time
(``from <pkg>.M import name`` inside a function, anywhere under ``src/``) or
when M's source reads the module-level name as a plain ``Name`` load (a call,
a ``<name>.attr`` read, or a bare value read such as ``KITTY_SPECS_DIR``) outside the
name's own ``def`` (recursion does not count), the read is not shadowed by a
parameter or local of an enclosing function, and the name is not bound solely by a function-local
``ImportFrom``. ``ImportFrom`` re-export lines never count. Names reached via
the ``_tasks.<name>`` bridge are intercepted by patching ``tasks``, so they are
NOT live for the seam modules.

``tasks`` rule: a name is live for ``tasks`` when (a) ``tasks.py`` itself calls
it as a bare ``Name`` (same rule as above), or (b) any ``tasks_*`` module
reaches it as ``<alias>.<name>`` where ``<alias>`` is bound by
``from specify_cli.cli.commands.agent import tasks as <alias>`` (attribute
access on the lazily imported module, whether called directly or first bound to
a local such as ``routed = _tasks.commit_for_mission``), or (c) a
``getattr(<alias>, "<prefix>" + ... + "<suffix>")`` read matches its prefix and
suffix (the KITTY_SPECS_DIR-named alias).

Liveness is per ``(module, name)``, not per call site: a name that is live somewhere
in the module passes for every patch of it. That is a necessary condition for an
intercept, not a sufficient one. A target the scanner cannot resolve to ``(module, name)``
is counted (``UNRESOLVABLE_BASELINE``), never dropped. A path that goes deeper than the
module (``<module>.console.print``) patches a shared object and is out of scope by design
(so a patch through a module alias kept on the old home is not checked).

Families (#5635 FR-010): the same scan also covers the **implement family**, every
``src/specify_cli/cli/commands/implement*.py`` whose stem is ``implement`` or starts with
``implement_`` (derived by glob, so siblings later work packages add join automatically).
Its liveness is the seam-module rule above **plus the attribute rule**: a name ``n`` is live
for family module M when any module under ``src/`` reads ``<alias>.n`` (or the dotted chain
``specify_cli.cli.commands.M.n``), where ``<alias>`` is bound to M by
``import specify_cli.cli.commands.M as <alias>``, ``from specify_cli.cli.commands import M [as <alias>]``
or a lazy in-function form of either (relative imports resolve against the importing file).
That is what makes the call style ``implement_claim.fn(...)`` count as live. The implement
family has no ``tasks``-style bridge and its unresolvable baseline is zero.
"""

from __future__ import annotations

import ast
import dataclasses
import functools
import importlib
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO = Path(__file__).resolve().parents[5]
_SRC_ROOT = _REPO / "src"


@dataclass(frozen=True)
class Family:
    """One scanned module family: where it lives, how its modules are found, how liveness is read."""

    name: str
    pkg: str  # dotted package that holds the family modules
    modules: tuple[str, ...]  # short module names, derived from the filesystem
    test_prefilter: re.Pattern[str]  # a test file is scanned only when its text matches
    module_hint: re.Pattern[str]  # a patch target text that mentions a family module
    src_hint: str  # a src file is read for call-time imports only when it contains this text
    bridge: str | None  # the ``tasks``-style namespace module, if the family has one
    attribute_rule: bool  # ``<alias>.<name>`` reads from any src module make a name live

    @property
    def src_dir(self) -> Path:
        return _SRC_ROOT.joinpath(*self.pkg.split("."))


_TASKS_PKG = "specify_cli.cli.commands.agent"
_TASKS_DIR = _SRC_ROOT.joinpath(*_TASKS_PKG.split("."))
#: Seam modules (``tasks_*.py``) derived from the package directory.
_SEAMS = tuple(sorted(p.stem for p in _TASKS_DIR.glob("tasks_*.py")))
_BRIDGE = "tasks"
TASKS = Family(
    name="tasks",
    pkg=_TASKS_PKG,
    modules=(*_SEAMS, _BRIDGE),
    test_prefilter=re.compile(r"commands\.agent"),
    module_hint=re.compile(r"agent\.tasks|\.tasks\.|tasks_[a-z_]+"),
    src_hint=f"{_TASKS_PKG}.tasks",
    bridge=_BRIDGE,
    attribute_rule=False,
)

_COMMANDS_PKG = "specify_cli.cli.commands"
_COMMANDS_DIR = _SRC_ROOT.joinpath(*_COMMANDS_PKG.split("."))
#: ``implement`` plus every ``implement_*`` sibling, by glob: later work packages join by existing.
_IMPLEMENT_MODULES = tuple(sorted(p.stem for p in _COMMANDS_DIR.glob("implement*.py") if p.stem == "implement" or p.stem.startswith("implement_")))
IMPLEMENT = Family(
    name="implement",
    pkg=_COMMANDS_PKG,
    modules=_IMPLEMENT_MODULES,
    # ``from specify_cli.cli.commands import implement_x`` (also the parenthesised form) never contains
    # ``commands.implement``, so the pre-filter has to admit the ``commands import`` spelling too.
    test_prefilter=re.compile(r"commands\.implement|cli\.commands\s+import"),
    module_hint=re.compile(r"commands\.implement"),
    src_hint=f"{_COMMANDS_PKG}.implement",
    bridge=None,
    attribute_rule=True,
)
FAMILIES = (TASKS, IMPLEMENT)

_PKG = TASKS.pkg
_SRC_DIR = TASKS.src_dir
_MODULES = TASKS.modules


def seam_modules() -> dict[str, ModuleType]:
    """Every ``tasks_*.py`` seam module on disk, imported, keyed by short name.

    The one discovery shared by this gate, ``test_tasks_compat_surface`` and
    ``test_tasks_move_task_seams``: a new seam module joins all three by existing.
    """
    return {name: importlib.import_module(f"{_PKG}.{name}") for name in _SEAMS}


_TESTS_DIR = _REPO / "tests"

#: Recorded baseline of patch targets this scan could not resolve statically.
#: A new unresolvable target must be resolved or consciously raise this number.
UNRESOLVABLE_BASELINE = 1

#: ``(repo-relative test path, module, name)`` -> reason. Legitimately
#: non-intercepting patches only (e.g. identity assertion on a re-export).
#: Each entry needs a TODO pointing at #2561.
_REVIEW_PTR = "tests/agent/test_review_feedback_pointer_2x_unit.py"
_REVIEW_PTR_REASON = (
    "TODO(#2561): the whole file is skipped (IS_2X_BRANCH is false), so the dead patch cannot be "
    "re-pointed and verified; re-point or delete when the 2.x review-pointer contract is revived"
)
ALLOWLIST: dict[tuple[str, str, str], str] = {
    (_REVIEW_PTR, "tasks", "read_events"): _REVIEW_PTR_REASON,
    (_REVIEW_PTR, "tasks", "safe_commit"): _REVIEW_PTR_REASON,
}

Hit = tuple[str, int, str, str]  # (file, line, module, name)


def _function_locals(func: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda) -> set[str]:
    """Names a function binds locally (parameters, stores, nested defs).

    Function-local imports are deliberately not shadows here: ``_bound_names``
    handles them (``lazy_import_only``) so a name that is also imported at
    module level stays live.

    A ``global`` declaration un-shadows the name. Nested functions are not
    descended into for their own stores, but their ``def`` name is a local here.
    """
    args = func.args
    local = {a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)}
    local.update(a.arg for a in (args.vararg, args.kwarg) if a is not None)
    declared_global: set[str] = set()

    def walk(node: ast.AST) -> None:
        if isinstance(node, ast.Global):
            declared_global.update(node.names)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            local.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            local.add(node.name)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            local.add(node.name)
            return
        for child in ast.iter_child_nodes(node):
            walk(child)

    body = [func.body] if isinstance(func, ast.Lambda) else func.body
    for stmt in body:
        walk(stmt)
    return local - declared_global


def _name_loads_outside_own_def(tree: ast.AST) -> set[str]:
    """Names read as a global (any ``Name`` load: call, ``Name.attr`` or plain value).

    Excludes reads inside the name's own ``def``/class (recursion) and reads of
    a name that an enclosing function binds locally (a parameter or local
    variable shadowing a module global does not exercise the global).
    """
    live: set[str] = set()

    def visit(node: ast.AST, enclosing: tuple[str, ...], shadowed: frozenset[str]) -> None:
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id not in enclosing and node.id not in shadowed:
            live.add(node.id)
        inner = enclosing + (node.name,) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else enclosing
        inner_shadow = shadowed | _function_locals(node) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) else shadowed
        for child in ast.iter_child_nodes(node):
            visit(child, inner, inner_shadow)

    visit(tree, (), frozenset())
    return live


def _bound_names(tree: ast.Module) -> tuple[set[str], set[str]]:
    """Return ``(module_level, lazy_import_only)`` bound-name sets.

    ``module_level`` holds names bound outside any function body (def, class,
    import, assignment). ``lazy_import_only`` holds names bound solely by an
    ``ImportFrom`` inside a function body: patching the module attribute does
    not intercept such a call, because the function re-binds a local each time.
    """
    module_level: set[str] = set()
    local_imports: set[str] = set()

    def visit(node: ast.AST, in_func: bool) -> None:
        if isinstance(node, ast.ImportFrom):
            names = {a.asname or a.name for a in node.names}
            (local_imports if in_func else module_level).update(names)
        elif not in_func:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                module_level.add(node.name)
            elif isinstance(node, ast.Import):
                module_level.update((a.asname or a.name).split(".")[0] for a in node.names)
            elif isinstance(node, ast.Assign):
                module_level.update(n.id for t in node.targets for n in ast.walk(t) if isinstance(n, ast.Name))
            elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and isinstance(node.target, ast.Name):
                module_level.add(node.target.id)
        inner = in_func or isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        for child in ast.iter_child_nodes(node):
            visit(child, inner)

    visit(tree, False)
    return module_level, local_imports - module_level


def _live_names(tree: ast.Module) -> set[str]:
    module_level, lazy_only = _bound_names(tree)
    # Intersect with module-level bindings: a read that resolves to a builtin or
    # an unbound name is not a module-global intercept point.
    return (_name_loads_outside_own_def(tree) & module_level) - lazy_only


@functools.cache
def _module_tree(module: str, family: Family = TASKS) -> ast.Module:
    return ast.parse((family.src_dir / f"{module}.py").read_text(encoding="utf-8"))


def _bridge_aliases(tree: ast.Module) -> set[str]:
    """Local names bound to the ``tasks`` module by ``from <pkg> import tasks``."""
    return {(a.asname or a.name) for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module == _PKG for a in n.names if a.name == _BRIDGE}


def _bridged_names(tree: ast.Module) -> set[str]:
    """Attributes read off a ``tasks`` bridge alias (``_tasks.<name>``)."""
    aliases = _bridge_aliases(tree)
    return {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id in aliases}


def _concat_operands(node: ast.expr) -> list[ast.expr]:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _concat_operands(node.left) + _concat_operands(node.right)
    return [node]


def _bridge_getattr_patterns(tree: ast.Module) -> list[tuple[str, str]]:
    """``(prefix, suffix)`` of ``getattr(<alias>, "pre" + ... + "suf")`` reads.

    A dynamically named attribute read off the bridge (the KITTY_SPECS_DIR
    alias) is live for every ``tasks`` name that starts with the leading and
    ends with the trailing string constant of the concatenation.
    """
    aliases = _bridge_aliases(tree)
    patterns: list[tuple[str, str]] = []
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "getattr" and len(n.args) >= 2):
            continue
        if not (isinstance(n.args[0], ast.Name) and n.args[0].id in aliases):
            continue
        parts = _concat_operands(n.args[1])
        first, last = parts[0], parts[-1]
        prefix = first.value if isinstance(first, ast.Constant) and isinstance(first.value, str) else ""
        suffix = last.value if isinstance(last, ast.Constant) and isinstance(last.value, str) else ""
        patterns.append((prefix, suffix))
    return patterns


@functools.cache
def _dynamic_bridge_patterns() -> tuple[tuple[str, str], ...]:
    return tuple(p for seam in _SEAMS for p in _bridge_getattr_patterns(_module_tree(seam)))


def _is_dynamically_bridged(module: str, name: str) -> bool:
    return module == _BRIDGE and any(len(pre) + len(suf) > 0 and name.startswith(pre) and name.endswith(suf) for pre, suf in _dynamic_bridge_patterns())


def _lazy_imports_from_modules(tree: ast.Module, family: Family = TASKS) -> dict[str, set[str]]:
    """``{module: names}`` pulled by a function-local ``from <pkg>.<module> import name``.

    A call-time import re-reads the attribute from the (patched) module, so the
    patch intercepts it no matter which package module performs the import.
    """
    found: dict[str, set[str]] = {}
    prefix = f"{family.pkg}."

    def visit(node: ast.AST, in_func: bool) -> None:
        if in_func and isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(prefix):
            module = node.module[len(prefix) :]
            if module in family.modules:
                found.setdefault(module, set()).update(a.name for a in node.names)
        inner = in_func or isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        for child in ast.iter_child_nodes(node):
            visit(child, inner)

    visit(tree, False)
    return found


@functools.cache
def _lazy_import_live_names(family: Family = TASKS) -> dict[str, set[str]]:
    """Call-time imports of any family module's name anywhere under ``src/``."""
    live: dict[str, set[str]] = {m: set() for m in family.modules}
    for _path, source in _src_sources(family.src_hint):
        for module, names in _lazy_imports_from_modules(ast.parse(source), family).items():
            live[module] |= names
    return live


@functools.cache
def _src_sources(hint: str) -> tuple[tuple[Path, str], ...]:
    """Every ``src/**/*.py`` whose text contains ``hint`` (the cheap pre-filter), read once."""
    found: list[tuple[Path, str]] = []
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if hint in source:
            found.append((path, source))
    return tuple(found)


def _importer_package(path: Path) -> str:
    """Dotted package a ``src`` file lives in (for resolving its relative imports)."""
    parts = path.relative_to(_SRC_ROOT).with_suffix("").parts
    return ".".join(parts[:-1])


def _resolve_import_from(node: ast.ImportFrom, importer_pkg: str) -> str | None:
    """Absolute dotted module of an ``ImportFrom`` (relative levels resolved), or ``None``."""
    if node.level == 0:
        return node.module
    base = importer_pkg.split(".")
    if node.level - 1 > len(base):
        return None
    base = base[: len(base) - (node.level - 1)]
    return ".".join([*base, *([node.module] if node.module else [])])


def _family_aliases(tree: ast.Module, family: Family, importer_pkg: str) -> dict[str, str]:
    """``{local alias: family module}`` bound anywhere in a file (module level or lazy in-function).

    ``import <pkg>.M as a``, ``from <pkg> import M [as a]`` and their relative spellings.
    Aliases are file-wide on purpose: a lazy in-function alias counts, and a clash only ever
    widens liveness for a name that is genuinely read off a family module.
    """
    aliases: dict[str, str] = {}
    prefix = f"{family.pkg}."
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.asname and a.name.startswith(prefix) and a.name[len(prefix) :] in family.modules:
                    aliases[a.asname] = a.name[len(prefix) :]
        elif isinstance(node, ast.ImportFrom) and _resolve_import_from(node, importer_pkg) == family.pkg:
            aliases.update({a.asname or a.name: a.name for a in node.names if a.name in family.modules})
    return aliases


def _attribute_reads(tree: ast.Module, family: Family, importer_pkg: str) -> dict[str, set[str]]:
    """``{module: names}`` read as ``<alias>.<name>`` (or ``<pkg>.<module>.<name>``) in one file."""
    aliases = _family_aliases(tree, family, importer_pkg)
    found: dict[str, set[str]] = {}
    prefix = f"{family.pkg}."
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load)):
            continue
        base = _attr_chain(node.value)
        if base is None:
            continue
        module = aliases.get(base) if "." not in base else None
        if module is None and base.startswith(prefix) and base[len(prefix) :] in family.modules:
            module = base[len(prefix) :]
        if module is not None:
            found.setdefault(module, set()).add(node.attr)
    return found


@functools.cache
def _attribute_live_names(family: Family = IMPLEMENT) -> dict[str, set[str]]:
    """The attribute rule over every ``src`` file: names read off a family module by any importer."""
    live: dict[str, set[str]] = {m: set() for m in family.modules}
    for path, source in _src_sources("implement"):
        for module, names in _attribute_reads(ast.parse(source), family, _importer_package(path)).items():
            live[module] |= names
    return live


@functools.cache
def _live_names_by_module(family: Family = TASKS) -> dict[str, set[str]]:
    live = {m: _live_names(_module_tree(m, family)) for m in family.modules}
    if family.bridge is not None:
        for seam in family.modules:
            if seam != family.bridge:
                live[family.bridge] |= _bridged_names(_module_tree(seam, family))
    for module, names in _lazy_import_live_names(family).items():
        live[module] |= names
    if family.attribute_rule:
        for module, names in _attribute_live_names(family).items():
            live[module] |= names
    return live


def _module_of_dotted(dotted: str, family: Family = TASKS) -> tuple[str, str] | None:
    """Split ``<pkg>.<module>.<name>`` into ``(module, name)`` if in scope."""
    prefix = f"{family.pkg}."
    if not dotted.startswith(prefix):
        return None
    rest = dotted[len(prefix) :].split(".")
    if len(rest) == 2 and rest[0] in family.modules:
        return rest[0], rest[1]
    return None


_FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)
#: ``patch.multiple`` keywords that configure the patch rather than name an attribute.
_PATCH_OPTIONS = frozenset({"spec", "create", "spec_set", "autospec", "new_callable"})


def _nodes_in_scope(node: ast.AST) -> Iterator[ast.AST]:
    """Pre-order descendants of ``node`` that belong to its own scope (not nested functions)."""
    for child in ast.iter_child_nodes(node):
        yield child
        if not isinstance(child, (*_FUNCTIONS, ast.Lambda)):
            yield from _nodes_in_scope(child)


def _attr_chain(node: ast.expr) -> str | None:
    """``a.b.c`` for a pure ``Name``/``Attribute`` chain, else ``None``."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        head = _attr_chain(node.value)
        return None if head is None else f"{head}.{node.attr}"
    return None


class _Scope:
    """String constants and tasks-module aliases bound directly in one function (or the module).

    Lookups fall back to the enclosing scope, so two functions that bind the same local
    name to different modules each resolve their own.
    """

    def __init__(self, parent: _Scope | None) -> None:
        self.parent = parent
        self.consts: dict[str, str] = {}
        self.aliases: dict[str, str] = {}

    def const(self, name: str) -> str | None:
        scope: _Scope | None = self
        while scope is not None:
            if name in scope.consts:
                return scope.consts[name]
            scope = scope.parent
        return None

    def alias(self, name: str) -> str | None:
        scope: _Scope | None = self
        while scope is not None:
            if name in scope.aliases:
                return scope.aliases[name]
            scope = scope.parent
        return None

    def alias_names(self) -> set[str]:
        names = set(self.parent.alias_names()) if self.parent else set()
        return names | set(self.aliases)


class _Scanner:
    """Collect in-scope patch targets from one test source.

    A patch call whose target mentions a tasks module but cannot be resolved to
    ``(module, name)`` is recorded as unresolvable, never silently dropped.
    """

    def __init__(self, source: str, rel: str, family: Family = TASKS) -> None:
        self.rel = rel
        self.family = family
        self.tree = ast.parse(source)
        self.hits: list[Hit] = []
        self.unresolvable: list[tuple[str, int]] = []

    def _bind_scope(self, node: ast.AST, scope: _Scope) -> None:
        for child in _nodes_in_scope(node):
            if isinstance(child, ast.ImportFrom) and child.module == self.family.pkg:
                scope.aliases.update({a.asname or a.name: a.name for a in child.names if a.name in self.family.modules})
            elif isinstance(child, ast.Import):
                for a in child.names:
                    if a.asname and a.name.startswith(f"{self.family.pkg}.") and a.name.rsplit(".", 1)[1] in self.family.modules:
                        scope.aliases[a.asname] = a.name.rsplit(".", 1)[1]
            elif isinstance(child, ast.Assign):
                self._bind_assign(child, scope)

    def _bind_assign(self, node: ast.Assign, scope: _Scope) -> None:
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        text = self._string(node.value, scope) if isinstance(node.value, (ast.Constant, ast.JoinedStr, ast.Attribute, ast.BinOp)) else None
        if text is not None:
            scope.consts.update(dict.fromkeys(names, text))
            return
        module = self._imported_module(node.value, scope)
        if module is not None:
            scope.aliases.update(dict.fromkeys(names, module))

    def _imported_module(self, node: ast.expr, scope: _Scope) -> str | None:
        """Module short name for ``importlib.import_module("<pkg>.<module>")`` (or bare ``import_module``)."""
        if not (isinstance(node, ast.Call) and node.args):
            return None
        func = node.func
        if not ((isinstance(func, ast.Name) and func.id == "import_module") or (isinstance(func, ast.Attribute) and func.attr == "import_module")):
            return None
        dotted = self._string(node.args[0], scope)
        resolved = _module_of_dotted(f"{dotted}.x", self.family) if dotted else None
        return resolved[0] if resolved else None

    def _module_ref(self, node: ast.expr, scope: _Scope) -> str | None:
        """The tasks module an expression refers to (alias, dotted attribute chain or ``import_module``)."""
        if isinstance(node, ast.Name):
            return scope.alias(node.id)
        if isinstance(node, ast.Call):
            return self._imported_module(node, scope)
        chain = _attr_chain(node)
        if chain is not None and chain.startswith(f"{self.family.pkg}."):
            tail = chain[len(self.family.pkg) + 1 :]
            return tail if tail in self.family.modules else None
        return None

    def _string(self, node: ast.expr, scope: _Scope) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            return scope.const(node.id)
        if isinstance(node, ast.Attribute) and node.attr == "__name__":
            module = self._module_ref(node.value, scope)
            return None if module is None else f"{self.family.pkg}.{module}"
        if isinstance(node, ast.FormattedValue):
            return self._string(node.value, scope)
        if isinstance(node, ast.JoinedStr):
            return self._join([self._string(v, scope) for v in node.values])
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return self._join([self._string(node.left, scope), self._string(node.right, scope)])
        return None

    @staticmethod
    def _join(pieces: list[str | None]) -> str | None:
        return None if any(p is None for p in pieces) else "".join(p for p in pieces if p is not None)

    def _mentions_module(self, node: ast.expr, scope: _Scope) -> bool:
        """True when ``node`` names a tasks module by alias, string fragment or dotted attribute chain."""
        aliases = scope.alias_names()
        for n in ast.walk(node):
            if isinstance(n, ast.Name) and n.id in aliases:
                return True
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and self.family.module_hint.search(n.value):
                return True
            if isinstance(n, ast.Attribute) and self.family.module_hint.search(_attr_chain(n) or ""):
                return True
        return False

    @staticmethod
    def _is_patch_call(call: ast.Call) -> str | None:
        """Classify a call by its trailing attribute chain.

        Covers ``patch``, ``mock.patch``, ``unittest.mock.patch``,
        ``mocker.patch`` (string form), the matching ``.object`` and ``.multiple``
        forms and ``monkeypatch.setattr``.
        """

        def is_patch(n: ast.expr) -> bool:
            return (isinstance(n, ast.Name) and n.id == "patch") or (isinstance(n, ast.Attribute) and n.attr == "patch")

        f = call.func
        if is_patch(f):
            return "string"
        if isinstance(f, ast.Attribute):
            if f.attr in ("object", "multiple") and is_patch(f.value):
                return f.attr
            if f.attr == "setattr":
                return "setattr"
        return None

    @staticmethod
    def _arg(call: ast.Call, index: int, *keywords: str) -> ast.expr | None:
        """Positional argument ``index`` or the first matching keyword value."""
        if len(call.args) > index:
            return call.args[index]
        for kw in call.keywords:
            if kw.arg in keywords:
                return kw.value
        return None

    def scan(self) -> None:
        self._visit(self.tree, self._new_scope(self.tree, None))

    def _new_scope(self, node: ast.AST, parent: _Scope | None) -> _Scope:
        scope = _Scope(parent)
        self._bind_scope(node, scope)
        return scope

    def _visit(self, node: ast.AST, scope: _Scope) -> None:
        if isinstance(node, ast.Call):
            kind = self._is_patch_call(node)
            if kind is not None:
                self._handle(node, kind, scope)
        if isinstance(node, _FUNCTIONS):
            # Decorators and defaults run in the enclosing scope; only the body sees the locals.
            for outer in (*node.decorator_list, node.args, node.returns):
                if outer is not None:
                    self._visit(outer, scope)
            inner = self._new_scope(node, scope)
            for stmt in node.body:
                self._visit(stmt, inner)
            return
        for child in ast.iter_child_nodes(node):
            self._visit(child, scope)

    def _record(self, call: ast.Call, module: str, name: str | None) -> None:
        if name is None:
            self.unresolvable.append((self.rel, call.lineno))
        else:
            self.hits.append((self.rel, call.lineno, module, name))

    def _handle(self, call: ast.Call, kind: str, scope: _Scope) -> None:
        target = self._arg(call, 0, "target")
        if target is None:
            return
        module = self._module_ref(target, scope)
        if module is None and kind in ("string", "setattr", "multiple"):
            dotted = self._string(target, scope)
            pkg_prefix = f"{self.family.pkg}."
            if dotted is not None and kind == "multiple" and dotted.startswith(pkg_prefix):
                tail = dotted[len(pkg_prefix) :]
                module = tail if tail in self.family.modules else None
            elif dotted is not None:
                self._handle_dotted(call, dotted)
                return
        if module is not None:
            self._handle_module(call, kind, module, scope)
        elif self._is_nested_object(target, scope):
            return  # patches an attribute of an object the module holds, not the module global
        elif self._mentions_module(target, scope):
            self.unresolvable.append((self.rel, call.lineno))

    def _is_nested_object(self, node: ast.expr, scope: _Scope) -> bool:
        """``<module>.<obj>[.<attr>...]`` as an object target (``patch.object(tasks.console, "print")``)."""
        return isinstance(node, ast.Attribute) and (self._module_ref(node.value, scope) is not None or self._is_nested_object(node.value, scope))

    def _handle_dotted(self, call: ast.Call, dotted: str) -> None:
        resolved = _module_of_dotted(dotted, self.family)
        if resolved is not None:
            self.hits.append((self.rel, call.lineno, *resolved))
        # A deeper path (``<module>.console.print``) patches the shared object itself and
        # intercepts every caller regardless of which module reads it: out of scope by design.

    def _handle_module(self, call: ast.Call, kind: str, module: str, scope: _Scope) -> None:
        if kind == "multiple":
            if any(kw.arg is None for kw in call.keywords):
                self.unresolvable.append((self.rel, call.lineno))
            for kw in call.keywords:
                if kw.arg is not None and kw.arg not in _PATCH_OPTIONS:
                    self._record(call, module, kw.arg)
            return
        attr_node = self._arg(call, 1, "attribute", "name")
        self._record(call, module, self._string(attr_node, scope) if attr_node is not None else None)


def _scan_source(source: str, rel: str, family: Family = TASKS) -> tuple[list[Hit], list[tuple[str, int]]]:
    scanner = _Scanner(source, rel, family)
    scanner.scan()
    return scanner.hits, scanner.unresolvable


def _dead_hits(hits: list[Hit], live: dict[str, set[str]]) -> list[Hit]:
    return [h for h in hits if h[3] not in live[h[2]] and not _is_dynamically_bridged(h[2], h[3]) and (h[0], h[2], h[3]) not in ALLOWLIST]


def _scan_tests(family: Family = TASKS) -> tuple[list[Hit], list[tuple[str, int]]]:
    """Patch hits and unresolvable targets of ``family`` across ``tests/``."""
    hits, unresolvable, _scanned = _scan_tests_counting(family)
    return hits, unresolvable


def _scan_tests_counting(family: Family) -> tuple[list[Hit], list[tuple[str, int]], int]:
    hits: list[Hit] = []
    unresolvable: list[tuple[str, int]] = []
    scanned = 0
    for path in sorted(_TESTS_DIR.rglob("*.py")):
        if path == Path(__file__).resolve():
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not family.test_prefilter.search(source):
            continue
        scanned += 1
        h, u = _scan_source(source, str(path.relative_to(_REPO)), family)
        hits += h
        unresolvable += u
    return hits, unresolvable, scanned


def test_every_tasks_patch_target_is_live() -> None:
    hits, unresolvable = _scan_tests()
    live = _live_names_by_module()
    # Positive control: one real f-string site (``f"{_tmt_executor.__name__}.<name>"``) must be found.
    seam_test = "tests/specify_cli/cli/commands/agent/test_tasks_move_task_seam.py"
    assert (seam_test, "tasks_move_task_executor", "_persist_approved_review_cycle") in {(h[0], h[2], h[3]) for h in hits}, (
        "scan lost a known patch site; the scanner is broken"
    )
    dead = _dead_hits(hits, live)
    print(f"tasks patch targets scanned: {len(hits)}; unresolvable: {len(unresolvable)}")
    for file, line in unresolvable:
        print(f"unresolvable patch target: {file}:{line}")
    assert len(unresolvable) <= UNRESOLVABLE_BASELINE, f"unresolvable patch targets {len(unresolvable)} exceed baseline {UNRESOLVABLE_BASELINE}"
    detail = "\n".join(f"  {f}:{ln} patches {m}.{n}" for f, ln, m, n in dead)
    assert not dead, (
        "dead patch intercepts (the module never reads the name as a module global: no call, Name load, "
        f"Name.attr read, _tasks.<name> bridge read or call-time import):\n{detail}"
    )


def test_negative_control_moved_symbol_patch_is_reported_dead() -> None:
    """A patch on a module that no longer calls the patched name (here
    ``_mt_emit_runtime_state`` on ``tasks_move_task``) must be reported dead."""
    source = (
        "from unittest.mock import patch\n"
        "from specify_cli.cli.commands.agent import tasks_move_task\n"
        "def test_x():\n"
        "    with patch.object(tasks_move_task, '_mt_emit_runtime_state'):\n"
        "        pass\n"
    )
    hits, unresolvable = _scan_source(source, "synthetic.py")
    assert hits == [("synthetic.py", 4, "tasks_move_task", "_mt_emit_runtime_state")]
    assert not unresolvable
    assert _dead_hits(hits, _live_names_by_module()) == hits


def test_scanner_resolves_string_and_fstring_targets() -> None:
    source = (
        "import importlib\n"
        "from unittest.mock import patch\n"
        "from specify_cli.cli.commands.agent import tasks_move_task, tasks_move_task_executor as _ex\n"
        f'_M = "{_PKG}.tasks_move_task_gates"\n'
        f'a = patch("{_PKG}.tasks_move_task_hops._x")\n'
        'b = patch(f"{_M}._y")\n'
        'c = patch(f"{unknown}.tasks_move_task._z")\n'
        # ``{<alias>.__name__}`` resolves to the aliased module.
        'd = patch(f"{tasks_move_task.__name__}._n")\n'
        'e = patch(f"{_ex.__name__}._m")\n'
        'f = patch(_ex.__name__ + "._k")\n'
        # A tasks target that cannot be resolved is counted, never dropped.
        'g = patch(f"{dyn()}.tasks_move_task._lost")\n'
        "h = patch.object(pkg.sub.tasks_move_task, name_var)\n"
        "def alias_binding():\n"
        f'    m = importlib.import_module("{_PKG}.tasks_move_task_hops")\n'
        '    patch.object(m, "_im")\n'
        "    patch.multiple(m, _ma=1, _mb=2, create=True)\n"
        "    patch.multiple(m, **opts)\n"
        # Module-level ``patch.object`` on a dotted attribute chain resolves; nested objects are out of scope.
        f'i = patch.object({_PKG}.tasks_move_task_gates, "_chain")\n'
        'j = patch.object(tasks_move_task.console, "print")\n'
        # A local string bound in a function is scoped to it: same name, different module per function.
        "def f1():\n"
        f'    _L = "{_PKG}.tasks_move_task_hops"\n'
        '    patch(f"{_L}._p")\n'
        "def f2():\n"
        f'    _L = "{_PKG}.tasks_move_task_gates"\n'
        '    patch(f"{_L}._q")\n'
        # A module name held in a variable assigned from ``__name__`` is followed too.
        "_N = tasks_move_task.__name__\n"
        'k = patch(f"{_N}._nm")\n'
    )
    hits, unresolvable = _scan_source(source, "synthetic.py")
    assert [(h[2], h[3]) for h in hits] == [
        ("tasks_move_task_hops", "_x"),
        ("tasks_move_task_gates", "_y"),
        ("tasks_move_task", "_n"),
        ("tasks_move_task_executor", "_m"),
        ("tasks_move_task_executor", "_k"),
        ("tasks_move_task_hops", "_im"),
        ("tasks_move_task_hops", "_ma"),
        ("tasks_move_task_hops", "_mb"),
        ("tasks_move_task_gates", "_chain"),
        ("tasks_move_task_hops", "_p"),
        ("tasks_move_task_gates", "_q"),
        ("tasks_move_task", "_nm"),
    ]
    # c, g (dynamic prefix), h (unresolved name on a dotted chain) and ``patch.multiple(**opts)``.
    assert len(unresolvable) == 4


def test_recursion_and_reexport_do_not_make_a_name_live() -> None:
    tree = ast.parse("from m import helper\ndef f():\n    return f()\ndef g():\n    return h()\n")
    assert _name_loads_outside_own_def(tree) == {"h"}


def test_positive_control_module_constant_read_as_a_name_is_live() -> None:
    """Patching a module constant that is only read as a plain Name is a real intercept."""
    tree = ast.parse("import os\nSPECS = 'kitty-specs'\ndef f(root):\n    return root / SPECS / os.sep\n")
    live = _live_names(tree)
    assert {"SPECS", "os"} <= live
    source = (
        "from unittest.mock import patch\n"
        "from specify_cli.cli.commands.agent import tasks_move_task\n"
        "def test_x():\n"
        "    patch.object(tasks_move_task, 'KITTY_SPECS_DIR')\n"
    )
    hits, _ = _scan_source(source, "synthetic.py")
    assert hits == [("synthetic.py", 4, "tasks_move_task", "KITTY_SPECS_DIR")]
    assert _dead_hits(hits, _live_names_by_module()) == []


def test_negative_control_local_variable_shadowing_a_global_does_not_make_it_live() -> None:
    """A function-local (or parameter) with the same name as a never-read module global is not a read of it."""
    tree = ast.parse(
        "GLOBAL_A = 1\nGLOBAL_B = 2\nGLOBAL_C = 3\n"
        "def f(GLOBAL_B):\n    GLOBAL_A = 5\n    return GLOBAL_A + GLOBAL_B\n"
        "def g():\n    global GLOBAL_C\n    return GLOBAL_C\n"
    )
    live = _live_names(tree)
    assert "GLOBAL_A" not in live
    assert "GLOBAL_B" not in live
    assert "GLOBAL_C" in live


def test_name_load_of_unbound_name_is_not_a_module_global() -> None:
    assert "len" not in _live_names(ast.parse("def f(x):\n    return len(x)\n"))


def test_scanner_recognises_mock_patch_variants() -> None:
    source = (
        "import unittest.mock\n"
        "from specify_cli.cli.commands.agent import tasks_move_task as m\n"
        "def test_x(mocker):\n"
        "    mock.patch.object(m, 'a')\n"
        "    mocker.patch.object(m, 'b')\n"
        "    unittest.mock.patch('specify_cli.cli.commands.agent.tasks_move_task.c')\n"
        "    mocker.patch('specify_cli.cli.commands.agent.tasks_move_task.d')\n"
    )
    hits, unresolvable = _scan_source(source, "synthetic.py")
    assert [(h[2], h[3]) for h in hits] == [("tasks_move_task", n) for n in "abcd"]
    assert not unresolvable


def test_scanner_resolves_keyword_only_targets_or_counts_unresolvable() -> None:
    source = (
        "from unittest.mock import patch\n"
        "from specify_cli.cli.commands.agent import tasks_move_task as m\n"
        "def test_x(dyn):\n"
        "    patch.object(target=m, attribute='a')\n"
        "    patch(target='specify_cli.cli.commands.agent.tasks_move_task.b')\n"
        "    patch.object(target=m, attribute=dyn)\n"
    )
    hits, unresolvable = _scan_source(source, "synthetic.py")
    assert [(h[2], h[3]) for h in hits] == [("tasks_move_task", "a"), ("tasks_move_task", "b")]
    assert unresolvable == [("synthetic.py", 6)]


def test_lazy_function_local_import_is_not_live() -> None:
    tree = ast.parse("from pkg import eager\ndef f():\n    from pkg import lazy_only, eager\n    lazy_only()\n    eager()\n    local()\ndef local():\n    pass\n")
    live = _live_names(tree)
    assert "lazy_only" not in live
    assert {"eager", "local"} <= live


def test_module_set_is_derived_from_the_package() -> None:
    assert _BRIDGE in _MODULES
    assert {"tasks_move_task", "tasks_move_task_executor", "tasks_shared", "tasks_finalize"} <= set(_SEAMS)
    assert all(m == _BRIDGE or m.startswith("tasks_") for m in _MODULES)


def _bridge_hit(name: str) -> list[Hit]:
    source = f'from unittest.mock import patch\ndef test_x():\n    patch("{_PKG}.tasks.{name}")\n'
    hits, unresolvable = _scan_source(source, "synthetic.py")
    assert not unresolvable
    return hits


def test_negative_control_tasks_bridge_name_never_bridged_is_dead() -> None:
    name = "_zz_no_bridge_call_exists"
    assert all(name not in _bridged_names(_module_tree(m)) for m in _SEAMS)
    hits = _bridge_hit(name)
    assert hits == [("synthetic.py", 3, "tasks", name)]
    assert _dead_hits(hits, _live_names_by_module()) == hits


def test_positive_control_real_bridged_name_is_live() -> None:
    bridged = sorted(set().union(*(_bridged_names(_module_tree(m)) for m in _SEAMS)))
    assert "locate_project_root" in bridged
    for name in ("locate_project_root", "commit_for_mission"):
        hits = _bridge_hit(name)
        assert hits and _dead_hits(hits, _live_names_by_module()) == []


def test_dynamic_getattr_bridge_and_lazy_import_rules() -> None:
    tree = ast.parse(
        f"def f():\n    from {_PKG} import tasks as _t\n    return getattr(_t, 'pre_' + X + '_suf')\n"
        f"def g():\n    from {_PKG}.tasks_shared import helper\n    helper()\n"
    )
    assert _bridge_getattr_patterns(tree) == [("pre_", "_suf")]
    assert _lazy_imports_from_modules(tree) == {"tasks_shared": {"helper"}}


# --------------------------------------------------------------------------------------
# Implement family (#5635 FR-010): seam-module rule + attribute rule, glob-derived modules.
# --------------------------------------------------------------------------------------

_CMD = "specify_cli.cli.commands"
#: The family as it will look once a sibling ``implement_claim`` exists (synthetic controls only).
_IMPLEMENT_PLUS_CLAIM = dataclasses.replace(IMPLEMENT, modules=(*IMPLEMENT.modules, "implement_claim"))
#: The dispatch map ``_implement_dispatch.py`` (created by the characterization work package) exposes
#: ``DISPATCH``: ``{logical collaborator: "<pkg>.<module>.<name>"}``.
_DISPATCH_MODULE = "tests.specify_cli.cli.commands._implement_dispatch"
_DISPATCH_FILE = _TESTS_DIR / "specify_cli" / "cli" / "commands" / "_implement_dispatch.py"


def _implement_dead_hits(source: str, family: Family, live: dict[str, set[str]]) -> list[Hit]:
    hits, unresolvable = _scan_source(source, "synthetic.py", family)
    assert not unresolvable
    return _dead_hits(hits, live)


def _owner_module_aliases(tree: ast.Module, importer_pkg: str) -> dict[str, str]:
    """``{local alias: dotted module}`` for ``import a.b as c`` and ``from a import b [as c]`` anywhere in a file.

    ``from a import b`` binds ``b`` to ``a.b`` only when ``a.b`` is a module; the caller checks the
    candidate against the dispatch target's owner module, so a plain name binding never matches.
    """
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            aliases.update({a.asname: a.name for a in node.names if a.asname})
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_import_from(node, importer_pkg)
            if base is not None:
                aliases.update({a.asname or a.name: f"{base}.{a.name}" for a in node.names})
    return aliases


@functools.cache
def _owner_attribute_reads(family: Family = IMPLEMENT) -> dict[str, set[str]]:
    """``{owner module: names}`` the family's own modules read as ``<alias>.<name>`` off a module outside the family.

    This is the call style the mission prescribes for moved collaborators (``workspace_context.find_wp_file(...)``):
    a patch on the owner module intercepts it. Only the family's modules count, so a name read by an
    unrelated caller does not make a dispatch target live.
    """
    reads: dict[str, set[str]] = {}
    for module in family.modules:
        tree = _module_tree(module, family)
        aliases = _owner_module_aliases(tree, family.pkg)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load) and isinstance(node.value, ast.Name) and node.value.id in aliases:
                reads.setdefault(aliases[node.value.id], set()).add(node.attr)
    return reads


def _dispatch_problems(
    mapping: Mapping[str, str],
    family: Family,
    live: dict[str, set[str]],
    owner_reads: Mapping[str, set[str]] | None = None,
) -> list[str]:
    """Dispatch-map entries whose target is not live.

    A target is live when it is a module-global name of a family module (one that module looks up),
    or when it names a collaborator that moved to an owner module outside the family and a family
    module calls it as ``<alias-of-owner>.<name>(...)`` (``owner_reads``, the mission's call style).
    """
    owner_reads = _owner_attribute_reads(family) if owner_reads is None else owner_reads
    problems: list[str] = []
    for logical, dotted in sorted(mapping.items()):
        resolved = _module_of_dotted(dotted, family)
        owner, _, name = dotted.rpartition(".")
        if resolved is not None:
            if resolved[1] not in live[resolved[0]]:
                problems.append(f"{logical}: {dotted} is dead (module {resolved[0]} never looks {resolved[1]} up as a module global)")
        elif name not in owner_reads.get(owner, set()):
            problems.append(
                f"{logical}: {dotted} is not <{family.pkg}>.<module>.<name> of a {family.name} module, "
                f"and no {family.name} module reads it as <alias-of-{owner}>.{name}"
            )
    return problems


def test_implement_family_modules_are_derived_by_glob() -> None:
    assert {"implement", "implement_cores"} <= set(IMPLEMENT.modules)
    assert all(m == "implement" or m.startswith("implement_") for m in IMPLEMENT.modules)
    assert all((_COMMANDS_DIR / f"{m}.py").is_file() for m in IMPLEMENT.modules)
    assert IMPLEMENT.bridge is None and IMPLEMENT.attribute_rule


def test_every_implement_patch_target_is_live() -> None:
    hits, unresolvable, scanned = _scan_tests_counting(IMPLEMENT)
    live = _live_names_by_module(IMPLEMENT)
    print(f"implement patch targets scanned: {len(hits)} in {scanned} test files; unresolvable: {len(unresolvable)}")
    # Positive controls: the pre-filter selects the implement test files and the scan finds known sites.
    assert scanned > 0 and hits, "implement scan covered zero patches; the pre-filter or scanner is broken"
    found = {(h[2], h[3]) for h in hits}
    assert ("implement", "find_repo_root") in found and ("implement", "create_lane_workspace") in found, "scan lost a known implement patch site"
    assert not unresolvable, f"implement patch targets must all resolve statically (no baseline): {unresolvable}"
    assert not [k for k in ALLOWLIST if k[1] in IMPLEMENT.modules], "the implement family takes no allow-list entries"
    dead = _dead_hits(hits, live)
    detail = "\n".join(f"  {f}:{ln} patches {m}.{n}" for f, ln, m, n in dead)
    assert not dead, (
        "dead implement patch intercepts (the module never reads the name as a module global: no Name load, "
        f"call-time import or <alias>.<name> read from another src module):\n{detail}"
    )


def test_negative_control_dead_implement_patch_is_reported() -> None:
    """A patch on a name no family module looks up must be reported dead, in every patch spelling."""
    source = (
        "from unittest.mock import patch\n"
        f"from {_CMD} import implement, implement_cores as ic\n"
        "def test_x(monkeypatch):\n"
        f"    patch('{_CMD}.implement.no_such_name')\n"
        "    patch.object(ic, 'also_no_such_name')\n"
        f"    monkeypatch.setattr('{_CMD}.implement_cores.nor_this', 1)\n"
        "    patch.multiple(implement, nope_a=1, create=True)\n"
    )
    dead = _implement_dead_hits(source, IMPLEMENT, _live_names_by_module(IMPLEMENT))
    assert [(h[2], h[3]) for h in dead] == [
        ("implement", "no_such_name"),
        ("implement_cores", "also_no_such_name"),
        ("implement_cores", "nor_this"),
        ("implement", "nope_a"),
    ]


def test_implement_scanner_resolves_family_targets_and_counts_unresolvable() -> None:
    source = (
        "import importlib\n"
        "from unittest.mock import patch\n"
        f"import {_CMD}.implement_cores as _ic\n"
        f"_M = '{_CMD}.implement'\n"
        f"a = patch('{_CMD}.implement.x')\n"
        "b = patch(f'{_M}.y')\n"
        "c = patch.object(_ic, 'z')\n"
        f"d = patch.object({_CMD}.implement, 'w')\n"
        "def f():\n"
        f"    m = importlib.import_module('{_CMD}.implement_cores')\n"
        "    patch.object(m, 'v')\n"
        # A deeper path patches a shared object: out of scope. Another package's module is out of scope too.
        f"e = patch('{_CMD}.implement.console.print')\n"
        f"g = patch('{_CMD}.agent.tasks.t')\n"
        # A family target that cannot be resolved is counted, never dropped.
        f"h = patch(f'{{dyn()}}.{_CMD}.implement.lost')\n"
    )
    hits, unresolvable = _scan_source(source, "synthetic.py", IMPLEMENT)
    assert [(h[2], h[3]) for h in hits] == [("implement", "x"), ("implement", "y"), ("implement_cores", "z"), ("implement", "w"), ("implement_cores", "v")]
    assert len(unresolvable) == 1


def test_implement_test_prefilter_admits_every_import_spelling() -> None:
    pre = IMPLEMENT.test_prefilter
    assert pre.search(f"from {_CMD} import implement as impl_mod\n")
    assert pre.search(f"from {_CMD} import (\n    implement,\n)\n")
    assert pre.search(f"importlib.import_module('{_CMD}.implement_cores')\n")
    assert pre.search(f"patch('{_CMD}.implement.find_repo_root')\n")
    assert not pre.search("from specify_cli.status import emit\n")


def test_attribute_rule_reads_off_every_alias_spelling() -> None:
    """``<alias>.<name>`` reads count for the module the alias is bound to, however it was bound."""
    tree = ast.parse(
        f"import {_CMD}.implement_claim as a1\n"
        f"from {_CMD} import implement_claim as a2, implement as a3\n"
        f"from {_CMD} import implement_claim\n"
        "from . import implement_claim as a4\n"
        "import specify_cli.other as unrelated\n"
        "def lazy():\n"
        f"    from {_CMD} import implement_claim as a5\n"
        "    return a5.lazy_read\n"
        "def use():\n"
        "    a1.via_import_as()\n"
        "    a2.via_from_alias()\n"
        "    a3.on_implement()\n"
        "    implement_claim.via_plain_from()\n"
        "    a4.via_relative()\n"
        f"    return {_CMD}.implement_claim.via_dotted_chain\n"
        "def not_family():\n"
        "    unrelated.nope()\n"
        "    a1.stored = 1\n"
        "    stranger.nope2()\n"
    )
    found = _attribute_reads(tree, _IMPLEMENT_PLUS_CLAIM, _CMD)
    assert found["implement_claim"] == {"via_import_as", "via_from_alias", "via_plain_from", "via_relative", "via_dotted_chain", "lazy_read"}
    assert found["implement"] == {"on_implement"}
    assert set(found) == {"implement", "implement_claim"}


def test_relative_import_resolution_follows_the_importing_package() -> None:
    def resolve(statement: str, importer_pkg: str) -> str | None:
        node = ast.parse(statement).body[0]
        assert isinstance(node, ast.ImportFrom)
        return _resolve_import_from(node, importer_pkg)

    assert resolve("from . import x", _CMD) == _CMD
    assert resolve("from .. import x", f"{_CMD}.agent") == _CMD
    assert resolve("from .implement import x", _CMD) == f"{_CMD}.implement"
    assert resolve("from ...... import x", "a.b") is None
    assert resolve("from specify_cli import x", _CMD) == "specify_cli"


def test_positive_control_attribute_read_from_another_module_makes_the_owner_patch_live() -> None:
    """The mission's call style (``implement_claim.fn(...)`` from ``implement.py``) is a live intercept point."""
    caller = ast.parse(f"from {_CMD} import implement_claim\ndef implement():\n    implement_claim.commit_wp_claim_status()\n")
    reads = _attribute_reads(caller, _IMPLEMENT_PLUS_CLAIM, _CMD)
    # The owner module itself never reads the name, so the seam rule alone calls it dead...
    live: dict[str, set[str]] = {m: set() for m in _IMPLEMENT_PLUS_CLAIM.modules}
    source = f"from unittest.mock import patch\ndef test_x():\n    patch('{_CMD}.implement_claim.commit_wp_claim_status')\n"
    assert [h[3] for h in _implement_dead_hits(source, _IMPLEMENT_PLUS_CLAIM, live)] == ["commit_wp_claim_status"]
    # ...and the attribute rule makes it live.
    for module, names in reads.items():
        live[module] |= names
    assert _implement_dead_hits(source, _IMPLEMENT_PLUS_CLAIM, live) == []


def test_attribute_rule_is_wired_into_the_implement_live_set_only() -> None:
    """Real-source wiring: attribute reads in ``src/`` reach the implement live set, and the tasks family ignores the rule."""
    assert not TASKS.attribute_rule
    live = _live_names_by_module(IMPLEMENT)
    for module, names in _attribute_live_names(IMPLEMENT).items():
        assert names <= live[module]
    # ``__init__`` registers ``implement_module.implement`` via ``from . import implement as implement_module``.
    assert "implement" in _attribute_live_names(IMPLEMENT)["implement"]


def test_dispatch_map_hook_accepts_an_owner_module_read_by_attribute_and_flags_an_unread_one() -> None:
    live = {"implement": set(), "implement_cores": set()}
    reads = {"specify_cli.workspace.context": {"find_wp_file"}}
    mapping = {"read": "specify_cli.workspace.context.find_wp_file", "unread": "specify_cli.workspace.context.resolve_lane_state_dir"}
    problems = _dispatch_problems(mapping, IMPLEMENT, live, reads)
    assert [p.split(":")[0] for p in problems] == ["unread"]


def test_owner_attribute_reads_see_the_real_call_style() -> None:
    """Real-source wiring: ``implement.py`` calls the moved context reads and the claim gate through their owner modules."""
    reads = _owner_attribute_reads(IMPLEMENT)
    assert {"find_wp_file", "resolve_mission_target_branch", "resolve_lane_state_dir"} <= reads["specify_cli.workspace.context"]
    assert "ensure_wp_claim_preconditions" in reads["specify_cli.core.dependency_graph"]


def test_owner_module_aliases_resolve_every_import_spelling() -> None:
    tree = ast.parse("import specify_cli.core.dependency_graph as dg\nfrom specify_cli.workspace import context as wc\nfrom ...core import errors\n")
    assert _owner_module_aliases(tree, _CMD) == {
        "dg": "specify_cli.core.dependency_graph",
        "wc": "specify_cli.workspace.context",
        "errors": "specify_cli.core.errors",
    }


def test_dispatch_map_hook_flags_dead_and_foreign_entries() -> None:
    live = {"implement": {"find_repo_root"}, "implement_cores": set()}
    good = {"find_repo": f"{_CMD}.implement.find_repo_root"}
    assert _dispatch_problems(good, IMPLEMENT, live, {}) == []
    planted = {**good, "dead": f"{_CMD}.implement.no_such_name", "foreign": f"{_CMD}.agent.tasks.x", "deep": f"{_CMD}.implement.console.print"}
    problems = _dispatch_problems(planted, IMPLEMENT, live, {})
    assert [p.split(":")[0] for p in problems] == ["dead", "deep", "foreign"]
    assert "is dead" in problems[0]


def test_implement_dispatch_map_targets_are_live() -> None:
    assert _DISPATCH_FILE.is_file(), "the characterization suite's dispatch map is missing"
    mapping = importlib.import_module(_DISPATCH_MODULE).DISPATCH
    assert mapping, "an existing dispatch map must not be empty"
    problems = _dispatch_problems(mapping, IMPLEMENT, _live_names_by_module(IMPLEMENT))
    assert not problems, "dead dispatch-map entries:\n" + "\n".join(f"  {p}" for p in problems)
