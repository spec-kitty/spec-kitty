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
"""

from __future__ import annotations

import ast
import functools
import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_PKG = "specify_cli.cli.commands.agent"
_REPO = Path(__file__).resolve().parents[5]
_SRC_DIR = _REPO / "src" / "specify_cli" / "cli" / "commands" / "agent"
_BRIDGE = "tasks"
#: Seam modules (``tasks_*.py``) derived from the package directory.
_SEAMS = tuple(sorted(p.stem for p in _SRC_DIR.glob("tasks_*.py")))
_MODULES = (*_SEAMS, _BRIDGE)
_MODULE_HINT = re.compile(r"agent\.tasks|\.tasks\.|tasks_[a-z_]+")
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
def _module_tree(module: str) -> ast.Module:
    return ast.parse((_SRC_DIR / f"{module}.py").read_text(encoding="utf-8"))


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


def _lazy_imports_from_modules(tree: ast.Module) -> dict[str, set[str]]:
    """``{module: names}`` pulled by a function-local ``from <pkg>.<module> import name``.

    A call-time import re-reads the attribute from the (patched) module, so the
    patch intercepts it no matter which package module performs the import.
    """
    found: dict[str, set[str]] = {}

    def visit(node: ast.AST, in_func: bool) -> None:
        if in_func and isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(f"{_PKG}."):
            module = node.module[len(_PKG) + 1 :]
            if module in _MODULES:
                found.setdefault(module, set()).update(a.name for a in node.names)
        inner = in_func or isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        for child in ast.iter_child_nodes(node):
            visit(child, inner)

    visit(tree, False)
    return found


@functools.cache
def _lazy_import_live_names() -> dict[str, set[str]]:
    """Call-time imports of any ``tasks``/``tasks_*`` name anywhere under ``src/``."""
    live: dict[str, set[str]] = {m: set() for m in _MODULES}
    for path in sorted((_REPO / "src").rglob("*.py")):
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if f"{_PKG}.tasks" not in source:
            continue
        for module, names in _lazy_imports_from_modules(ast.parse(source)).items():
            live[module] |= names
    return live


@functools.cache
def _live_names_by_module() -> dict[str, set[str]]:
    live = {m: _live_names(_module_tree(m)) for m in _MODULES}
    for seam in _SEAMS:
        live[_BRIDGE] |= _bridged_names(_module_tree(seam))
    for module, names in _lazy_import_live_names().items():
        live[module] |= names
    return live


def _module_of_dotted(dotted: str) -> tuple[str, str] | None:
    """Split ``<pkg>.<module>.<name>`` into ``(module, name)`` if in scope."""
    prefix = f"{_PKG}."
    if not dotted.startswith(prefix):
        return None
    rest = dotted[len(prefix) :].split(".")
    if len(rest) == 2 and rest[0] in _MODULES:
        return rest[0], rest[1]
    return None


class _Scanner:
    """Collect in-scope patch targets from one test source."""

    def __init__(self, source: str, rel: str) -> None:
        self.rel = rel
        self.tree = ast.parse(source)
        self.hits: list[Hit] = []
        self.unresolvable: list[tuple[str, int]] = []
        self.aliases: dict[str, str] = {}
        self.consts: dict[str, str] = {}
        self._collect_bindings()

    def _collect_bindings(self) -> None:
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ImportFrom) and node.module == _PKG:
                for a in node.names:
                    if a.name in _MODULES:
                        self.aliases[a.asname or a.name] = a.name
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if a.asname and a.name.startswith(f"{_PKG}.") and a.name.rsplit(".", 1)[1] in _MODULES:
                        self.aliases[a.asname] = a.name.rsplit(".", 1)[1]
            elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        self.consts[t.id] = node.value.value

    def _string(self, node: ast.expr) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            return self.consts.get(node.id)
        if isinstance(node, ast.JoinedStr):
            parts: list[str] = []
            for v in node.values:
                piece = self._string(v.value) if isinstance(v, ast.FormattedValue) else self._string(v)
                if piece is None:
                    return None
                parts.append(piece)
            return "".join(parts)
        return None

    def _fragments_mention_module(self, node: ast.expr) -> bool:
        return any(isinstance(n, ast.Constant) and isinstance(n.value, str) and _MODULE_HINT.search(n.value) for n in ast.walk(node))

    @staticmethod
    def _is_patch_call(call: ast.Call) -> str | None:
        """Classify a call by its trailing attribute chain.

        Covers ``patch``, ``mock.patch``, ``unittest.mock.patch``,
        ``mocker.patch`` (string form), the matching ``.object`` forms and
        ``monkeypatch.setattr``.
        """

        def is_patch(n: ast.expr) -> bool:
            return (isinstance(n, ast.Name) and n.id == "patch") or (isinstance(n, ast.Attribute) and n.attr == "patch")

        f = call.func
        if is_patch(f):
            return "string"
        if isinstance(f, ast.Attribute):
            if f.attr == "object" and is_patch(f.value):
                return "object"
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
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                kind = self._is_patch_call(node)
                if kind is not None:
                    self._handle(node, kind)

    def _handle(self, call: ast.Call, kind: str) -> None:
        target = self._arg(call, 0, "target")
        if target is None:
            return
        if isinstance(target, ast.Name) and target.id in self.aliases:
            module = self.aliases[target.id]
            attr_node = self._arg(call, 1, "attribute", "name")
            name = self._string(attr_node) if attr_node is not None else None
            if name is None:
                self.unresolvable.append((self.rel, call.lineno))
            else:
                self.hits.append((self.rel, call.lineno, module, name))
            return
        if kind in ("string", "setattr"):
            dotted = self._string(target)
            if dotted is None:
                if self._fragments_mention_module(target):
                    self.unresolvable.append((self.rel, call.lineno))
                return
            resolved = _module_of_dotted(dotted)
            if resolved is not None:
                self.hits.append((self.rel, call.lineno, *resolved))


def _scan_source(source: str, rel: str) -> tuple[list[Hit], list[tuple[str, int]]]:
    scanner = _Scanner(source, rel)
    scanner.scan()
    return scanner.hits, scanner.unresolvable


def _dead_hits(hits: list[Hit], live: dict[str, set[str]]) -> list[Hit]:
    return [h for h in hits if h[3] not in live[h[2]] and not _is_dynamically_bridged(h[2], h[3]) and (h[0], h[2], h[3]) not in ALLOWLIST]


def _scan_tests() -> tuple[list[Hit], list[tuple[str, int]]]:
    hits: list[Hit] = []
    unresolvable: list[tuple[str, int]] = []
    for path in sorted(_TESTS_DIR.rglob("*.py")):
        if path == Path(__file__).resolve():
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "commands.agent" not in source:
            continue
        h, u = _scan_source(source, str(path.relative_to(_REPO)))
        hits += h
        unresolvable += u
    return hits, unresolvable


def test_every_tasks_patch_target_is_live() -> None:
    hits, unresolvable = _scan_tests()
    live = _live_names_by_module()
    assert hits, "scan found no tasks patch targets at all; the scanner is broken"
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
        "from unittest.mock import patch\n"
        f'_M = "{_PKG}.tasks_move_task_gates"\n'
        f'a = patch("{_PKG}.tasks_move_task_hops._x")\n'
        'b = patch(f"{_M}._y")\n'
        'c = patch(f"{unknown}.tasks_move_task._z")\n'
    )
    hits, unresolvable = _scan_source(source, "synthetic.py")
    assert [(h[2], h[3]) for h in hits] == [("tasks_move_task_hops", "_x"), ("tasks_move_task_gates", "_y")]
    assert len(unresolvable) == 1


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


def _never_called_name(module: str) -> str:
    """A name ``module`` defines at module level but never calls (else a sentinel)."""
    defined = {n.name for n in _module_tree(module).body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    dead = sorted(defined - _live_names_by_module()[module])
    return dead[0] if dead else "_never_called_sentinel_zz"


def test_module_set_is_derived_from_the_package() -> None:
    assert _BRIDGE in _MODULES
    assert {"tasks_move_task", "tasks_move_task_executor", "tasks_shared", "tasks_finalize"} <= set(_SEAMS)
    assert all(m == _BRIDGE or m.startswith("tasks_") for m in _MODULES)


@pytest.mark.parametrize("module", _SEAMS)
def test_negative_control_uncalled_name_is_dead_for_every_seam(module: str) -> None:
    """A patch on a name the seam defines but never calls must be reported dead."""
    name = _never_called_name(module)
    source = f"from unittest.mock import patch\nfrom {_PKG} import {module}\ndef test_x():\n    with patch.object({module}, {name!r}):\n        pass\n"
    hits, unresolvable = _scan_source(source, "synthetic.py")
    assert hits == [("synthetic.py", 4, module, name)]
    assert not unresolvable
    assert _dead_hits(hits, _live_names_by_module()) == hits


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
