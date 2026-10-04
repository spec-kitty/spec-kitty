"""Patch-site liveness gate for the move-task modules (#5629 FR-008, SC-004).

A ``patch``/``monkeypatch`` that targets a name in one of the four move-task
modules only intercepts anything if that module itself calls the name through
its own module globals, i.e. an ``ast.Call`` whose ``func`` is a bare
``Name``. After a verbatim move, a patch left on the old home module silently
stops intercepting: the test stays green while exercising the real function.

Liveness rule: a name is live for module M only when M's source holds a
``Call(func=Name(id=<name>))`` outside the name's own ``def`` (recursion does
not count). ``ImportFrom`` re-export lines never count. Names reached through
the ``_tasks.<name>(...)`` bridge are intercepted by patching module ``tasks``,
not ``tasks_move_task``, so they are NOT live for the move-task modules.

Scope: only the four move-task modules. Patches on ``tasks`` are out of scope.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_PKG = "specify_cli.cli.commands.agent"
_MODULES = (
    "tasks_move_task",
    "tasks_move_task_gates",
    "tasks_move_task_hops",
    "tasks_move_task_executor",
)
_REPO = Path(__file__).resolve().parents[5]
_SRC_DIR = _REPO / "src" / "specify_cli" / "cli" / "commands" / "agent"
_TESTS_DIR = _REPO / "tests"

#: Recorded baseline of patch targets this scan could not resolve statically.
#: A new unresolvable target must be resolved or consciously raise this number.
UNRESOLVABLE_BASELINE = 0

#: ``(repo-relative test path, module, name)`` -> reason. Legitimately
#: non-intercepting patches only (e.g. identity assertion on a re-export).
#: Each entry needs a TODO pointing at #2561.
ALLOWLIST: dict[tuple[str, str, str], str] = {}

Hit = tuple[str, int, str, str]  # (file, line, module, name)


def _calls_outside_own_def(tree: ast.AST) -> set[str]:
    """Names invoked as ``Name(...)`` outside their own ``def`` body."""
    live: set[str] = set()

    def visit(node: ast.AST, enclosing: tuple[str, ...]) -> None:
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id not in enclosing:
            live.add(node.func.id)
        inner = enclosing + (node.name,) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else enclosing
        for child in ast.iter_child_nodes(node):
            visit(child, inner)

    visit(tree, ())
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
            elif isinstance(node, ast.Assign):
                module_level.update(t.id for t in node.targets if isinstance(t, ast.Name))
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                module_level.add(node.target.id)
        inner = in_func or isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        for child in ast.iter_child_nodes(node):
            visit(child, inner)

    visit(tree, False)
    return module_level, local_imports - module_level


def _live_names(tree: ast.Module) -> set[str]:
    _, lazy_only = _bound_names(tree)
    return _calls_outside_own_def(tree) - lazy_only


def _live_names_by_module() -> dict[str, set[str]]:
    return {m: _live_names(ast.parse((_SRC_DIR / f"{m}.py").read_text(encoding="utf-8"))) for m in _MODULES}


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
        return any(isinstance(n, ast.Constant) and isinstance(n.value, str) and any(m in n.value for m in _MODULES) for n in ast.walk(node))

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
    return [h for h in hits if h[3] not in live[h[2]] and (h[0], h[2], h[3]) not in ALLOWLIST]


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
        if not any(m in source for m in _MODULES):
            continue
        h, u = _scan_source(source, str(path.relative_to(_REPO)))
        hits += h
        unresolvable += u
    return hits, unresolvable


def test_every_move_task_patch_target_is_live() -> None:
    hits, unresolvable = _scan_tests()
    live = _live_names_by_module()
    assert hits, "scan found no move-task patch targets at all; the scanner is broken"
    dead = _dead_hits(hits, live)
    print(f"move-task patch targets scanned: {len(hits)}; unresolvable: {len(unresolvable)}")
    for file, line in unresolvable:
        print(f"unresolvable patch target: {file}:{line}")
    assert len(unresolvable) <= UNRESOLVABLE_BASELINE, f"unresolvable patch targets {len(unresolvable)} exceed baseline {UNRESOLVABLE_BASELINE}"
    assert not dead, "dead patch intercepts (module never calls the name as a bare Name):\n" + "\n".join(f"  {f}:{ln} patches {m}.{n}" for f, ln, m, n in dead)


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
    assert _calls_outside_own_def(tree) == {"h"}


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
