"""Patch-lookup guard for the reconciliation family (WP04 / FR-020 / C-005).

After a name moves out of ``specify_cli.consolidation.reconciliation`` into a
split module, a patch on the facade replaces only the facade's binding while
the moved code looks the name up in its new module — the patch intercepts
nothing and the test goes vacuously green. This guard makes that a failure:

1. ``test_patched_reconciliation_names_are_looked_up`` — every
   ``reconciliation*`` patch target in the corpus lands in a module that itself
   looks the name up, and no *other* reconciliation module also looks it up
   (a single-module patch on a name two modules look up narrows what the patch
   intercepted before the split — orchestrator decision 2026-11-08, issue 8).
2. ``test_stale_patch_fails_the_guard`` / ``test_narrowed_patch_fails_the_guard``
   — controls proving the guard fails on a stale and on a narrowed patch.
3. ``test_facade_forward_reference_counts_as_a_facade_lookup`` and
   ``test_forward_reference_precedence_and_alias`` — the forward-reference
   rules: a lookup in module M of a name M binds only through a function-local
   ``from specify_cli.consolidation.reconciliation import <name>`` (the Phase 3
   TEMPORARY FORWARD REFERENCE convention) reads the facade's attribute at call
   time, so it counts as a lookup in the facade, not in M.
4. The family-helper tests exercise ``tests/consolidation/reconciliation_family.py``
   (every binding module, consumer bindings, unbound-name refusal).

Scope: patches made through ``setattr_reconciliation_family`` /
``patch_reconciliation_family`` are not string or module-object patches and are
not scanned — they patch every binding module by construction. A direct string
patch on ``specify_cli.consolidation.phase_claim.<name>`` (WP02 T007 step 4) is
outside the guard's scope; the by-name consumers are covered by the helper.
"""

from __future__ import annotations

import ast
import re
import types
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest
from specify_cli.consolidation import phase_claim, phase_gate, forecast, reconciliation
from tests.consolidation import reconciliation_family
from tests.consolidation.reconciliation_family import patch_callee_name, setattr_reconciliation_family

pytestmark = pytest.mark.fast

repo_root = Path(__file__).resolve().parents[2]

_FAMILY_PREFIX = "specify_cli.consolidation.reconciliation"
_FAMILY_TARGET_RE = re.compile(r"^specify_cli\.consolidation\.(reconciliation[a-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)$")
_PATCH_CALLEES = ("setattr", "patch", "patch.object")

_UNLOOKED_UP_TEMPLATE = (
    "{test_path}:{line}: patches {module}.{name}, but {module} never looks {name} up; "
    "patch it where it is looked up (see tests/consolidation/reconciliation_family.py)"
)
_NARROWED_TEMPLATE = (
    "{test_path}:{line}: patches {module}.{name}, but {name} is also looked up in {others}; "
    "patch every binding module with setattr_reconciliation_family "
    "(see tests/consolidation/reconciliation_family.py)"
)


@dataclass(frozen=True)
class _PatchTarget:
    line: int
    module: str
    name: str


def _is_family_module(dotted: str) -> bool:
    return dotted.startswith(_FAMILY_PREFIX)


def _reconciliation_aliases(tree: ast.AST) -> dict[str, str]:
    """Local names bound to a reconciliation-family module, at any scope."""
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "specify_cli.consolidation":
            for alias in node.names:
                if alias.name == "reconciliation" or alias.name.startswith("reconciliation_"):
                    aliases[alias.asname or alias.name] = f"specify_cli.consolidation.{alias.name}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(_FAMILY_PREFIX):
                    aliases[alias.asname or alias.name] = alias.name
    return aliases


def _module_string_constants(tree: ast.Module) -> dict[str, str]:
    """Module-level ``NAME = "<string>"`` constants (f-string bases)."""
    consts: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        value = node.value
        if isinstance(target, ast.Name) and isinstance(value, ast.Constant) and isinstance(value.value, str):
            consts[target.id] = value.value
    return consts


def _fstring_target(node: ast.JoinedStr, consts: Mapping[str, str]) -> tuple[str, str] | None:
    """``(module, name)`` from a two-part f-string ``f"{BASE}.<name>"`` on a family constant."""
    if len(node.values) != 2:
        return None
    first, second = node.values
    if not (isinstance(first, ast.FormattedValue) and isinstance(first.value, ast.Name)):
        return None
    if not (isinstance(second, ast.Constant) and isinstance(second.value, str)):
        return None
    suffix = second.value
    if not (suffix.startswith(".") and suffix[1:].isidentifier()):
        return None
    base = consts.get(first.value.id)
    if base is None or not _is_family_module(base):
        return None
    return base, suffix[1:]


def _target_from_call(node: ast.Call, aliases: Mapping[str, str], consts: Mapping[str, str]) -> _PatchTarget | None:
    """The reconciliation-family patch target of one call, if it is one."""
    callee = patch_callee_name(node.func)
    if callee not in _PATCH_CALLEES or not node.args:
        return None
    first = node.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        match = _FAMILY_TARGET_RE.match(first.value)
        if match:
            return _PatchTarget(node.lineno, f"specify_cli.consolidation.{match.group(1)}", match.group(2))
        return None
    if isinstance(first, ast.JoinedStr):
        target = _fstring_target(first, consts)
        return _PatchTarget(node.lineno, target[0], target[1]) if target else None
    if isinstance(first, ast.Name) and first.id in aliases and len(node.args) > 1:
        second = node.args[1]
        if isinstance(second, ast.Constant) and isinstance(second.value, str):
            return _PatchTarget(node.lineno, aliases[first.id], second.value)
    return None


def _patch_targets(source: str) -> list[_PatchTarget]:
    """Every reconciliation-family patch target in one test source."""
    tree = ast.parse(source)
    aliases = _reconciliation_aliases(tree)
    consts = _module_string_constants(tree)
    targets: list[_PatchTarget] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            target = _target_from_call(node, aliases, consts)
            if target:
                targets.append(target)
    return targets


def _parent_map(tree: ast.Module) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    return parents


def _function_chain(node: ast.AST, parents: Mapping[ast.AST, ast.AST]) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """The function definitions enclosing *node*, innermost first."""
    chain: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    current: ast.AST | None = node
    while current is not None:
        parent = parents.get(current)
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            chain.append(parent)
        current = parent
    return chain


def _is_attribute_root(node: ast.Name, parents: Mapping[ast.AST, ast.AST]) -> bool:
    parent = parents.get(node)
    return isinstance(parent, ast.Attribute) and parent.value is node


def _module_level_bindings(tree: ast.Module) -> set[str]:
    """Names bound at module level: defs, classes, assignments and imports in ``tree.body``."""
    bound: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    bound.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            bound.add(node.target.id)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                bound.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                bound.add(alias.asname or alias.name)
    return bound


def _own_nodes(func: ast.FunctionDef | ast.AsyncFunctionDef) -> Iterator[ast.AST]:
    """Nodes inside *func*, excluding nested function bodies (their imports are their own)."""
    stack = list(ast.iter_child_nodes(func))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        yield node
        stack.extend(ast.iter_child_nodes(node))


def _function_scoped_imports(tree: ast.Module) -> dict[int, dict[str, tuple[str, str]]]:
    """``id(func)`` -> local name -> (source module, original name) for imports in that function's own body."""
    imports: dict[int, dict[str, tuple[str, str]]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        own: dict[str, tuple[str, str]] = {}
        for inner in _own_nodes(node):
            if not (isinstance(inner, ast.ImportFrom) and inner.module):
                continue
            for alias in inner.names:
                own[alias.asname or alias.name] = (inner.module, alias.name)
        imports[id(node)] = own
    return imports


def _resolve_load(
    node: ast.Name,
    module_name: str,
    bindings: set[str],
    func_imports: Mapping[int, Mapping[str, tuple[str, str]]],
    parents: Mapping[ast.AST, ast.AST],
) -> tuple[str, str]:
    """Resolve one counted load to ``(dotted module, looked-up name)``.

    Precedence (T022): a module-level binding in M wins over a function-local
    import; a function-local alias resolves to the imported name; a
    function-local import from a reconciliation module counts as a lookup in
    that source module; any other function-local import is ignored and the
    name counts as a lookup in M.
    """
    if node.id in bindings:
        return module_name, node.id
    for func in _function_chain(node, parents):
        imported = func_imports.get(id(func), {}).get(node.id)
        if imported is None:
            continue
        source, original = imported
        if _is_family_module(source):
            return source, original
        return module_name, node.id
    return module_name, node.id


def _module_reads(module_name: str, tree: ast.Module) -> set[tuple[str, str]]:
    """``(module, name)`` pairs this module looks up: loads inside function or method
    bodies, plus attribute chains rooted at the name outside them. Module-level
    ``__all__`` entries and pure re-export import statements bind, they never load."""
    parents = _parent_map(tree)
    bindings = _module_level_bindings(tree)
    func_imports = _function_scoped_imports(tree)
    reads: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)):
            continue
        if not _function_chain(node, parents) and not _is_attribute_root(node, parents):
            continue
        reads.add(_resolve_load(node, module_name, bindings, func_imports, parents))
    return reads


def _target_messages(
    test_path: Path,
    target: _PatchTarget,
    reads: set[tuple[str, str]],
    lookers: Mapping[str, set[str]],
    patched: Mapping[str, set[str]],
) -> list[str]:
    """The stale-patch and narrowed-patch messages for one target; they fire independently."""
    messages: list[str] = []
    if (target.module, target.name) not in reads:
        messages.append(_UNLOOKED_UP_TEMPLATE.format(test_path=test_path, line=target.line, module=target.module, name=target.name))
    others = lookers.get(target.name, set()) - patched.get(target.name, set())
    if others:
        messages.append(
            _NARROWED_TEMPLATE.format(
                test_path=test_path,
                line=target.line,
                module=target.module,
                name=target.name,
                others=", ".join(sorted(others)),
            )
        )
    return messages


def unlooked_up_patches(test_sources: Mapping[Path, str], module_sources: Mapping[str, str]) -> list[str]:
    """One message per stale or narrowed reconciliation-family patch target.

    ``module_sources`` maps a dotted reconciliation-family module name to its
    source text; ``test_sources`` maps a test file path to its source text. A
    patch target is any string, f-string or module-object patch of
    ``specify_cli.consolidation.reconciliation*.<name>`` in a test source. The
    messages name the test path and line, the patched module and name, and the
    remedy (``tests/consolidation/reconciliation_family.py``).
    """
    reads: set[tuple[str, str]] = set()
    for module_name, source in module_sources.items():
        reads |= _module_reads(module_name, ast.parse(source))
    lookers: dict[str, set[str]] = {}
    for module_name, name in reads:
        lookers.setdefault(name, set()).add(module_name)
    messages: list[str] = []
    for test_path, source in test_sources.items():
        targets = _patch_targets(source)
        patched: dict[str, set[str]] = {}
        for target in targets:
            patched.setdefault(target.name, set()).add(target.module)
        for target in targets:
            messages.extend(_target_messages(test_path, target, reads, lookers, patched))
    return messages


@pytest.mark.non_sandbox
def test_patched_reconciliation_names_are_looked_up() -> None:
    module_sources: dict[str, str] = {}
    consolidation = repo_root / "src" / "specify_cli" / "consolidation"
    for path in sorted(consolidation.glob("reconciliation*.py")):
        module_sources[f"specify_cli.consolidation.{path.stem}"] = path.read_text(encoding="utf-8")
    test_sources: dict[Path, str] = {}
    for path in sorted((repo_root / "tests").rglob("*.py")):
        if "__pycache__" not in path.parts:
            test_sources[path] = path.read_text(encoding="utf-8")
    messages = unlooked_up_patches(test_sources, module_sources)
    assert not messages, "\n".join(messages)


def test_stale_patch_fails_the_guard() -> None:
    module_sources = {"specify_cli.consolidation.reconciliation": "Y = 2\n\ndef f():\n    return 1\n"}
    cases = {
        "plain string": 'def test(monkeypatch):\n    monkeypatch.setattr("specify_cli.consolidation.reconciliation.Y", 3)\n',
        "f-string constant": 'BASE = "specify_cli.consolidation.reconciliation"\n\ndef test(monkeypatch):\n    monkeypatch.setattr(f"{BASE}.Y", 3)\n',
        "module object": 'from specify_cli.consolidation import reconciliation as rec\n\ndef test(monkeypatch):\n    monkeypatch.setattr(rec, "Y", 3)\n',
        "mock.patch string": ('from unittest import mock\n\ndef test():\n    with mock.patch("specify_cli.consolidation.reconciliation.Y"):\n        pass\n'),
        "mock.patch.object": (
            "from specify_cli.consolidation import reconciliation as rec\n"
            "from unittest import mock\n\n"
            "def test():\n"
            '    with mock.patch.object(rec, "Y"):\n'
            "        pass\n"
        ),
        "bare patch string": ('from unittest.mock import patch\n\ndef test():\n    with patch("specify_cli.consolidation.reconciliation.Y"):\n        pass\n'),
        "bare patch.object": (
            "from specify_cli.consolidation import reconciliation as rec\n"
            "from unittest.mock import patch\n\n"
            "def test():\n"
            '    with patch.object(rec, "Y"):\n'
            "        pass\n"
        ),
    }
    for form, source in cases.items():
        messages = unlooked_up_patches({Path("t.py"): source}, module_sources)
        assert len(messages) == 1, (form, messages)
        assert "Y" in messages[0], (form, messages[0])


def test_narrowed_patch_fails_the_guard() -> None:
    module_sources = {
        "specify_cli.consolidation.reconciliation": "def f():\n    return Y\n",
        "specify_cli.consolidation.reconciliation_kernel": "def g():\n    return Y\n",
    }
    narrowed = 'def test(monkeypatch):\n    monkeypatch.setattr("specify_cli.consolidation.reconciliation.Y", 3)\n'
    messages = unlooked_up_patches({Path("t.py"): narrowed}, module_sources)
    assert len(messages) == 1, messages
    assert "reconciliation_kernel" in messages[0], messages[0]

    both = (
        "def test(monkeypatch):\n"
        '    monkeypatch.setattr("specify_cli.consolidation.reconciliation.Y", 3)\n'
        '    monkeypatch.setattr("specify_cli.consolidation.reconciliation_kernel.Y", 3)\n'
    )
    assert unlooked_up_patches({Path("t.py"): both}, module_sources) == []


def test_facade_forward_reference_counts_as_a_facade_lookup() -> None:
    facade = "def h():\n    return Y\n"
    facade_patch = 'def test(monkeypatch):\n    monkeypatch.setattr("specify_cli.consolidation.reconciliation.Y", 3)\n'
    kernel_function_local = "def g():\n    from specify_cli.consolidation.reconciliation import Y\n    return Y\n"
    modules = {
        "specify_cli.consolidation.reconciliation": facade,
        "specify_cli.consolidation.reconciliation_kernel": kernel_function_local,
    }
    assert unlooked_up_patches({Path("t.py"): facade_patch}, modules) == []

    kernel_module_level = "from specify_cli.consolidation.reconciliation import Y\n\ndef g():\n    return Y\n"
    control_modules = {
        "specify_cli.consolidation.reconciliation": facade,
        "specify_cli.consolidation.reconciliation_kernel": kernel_module_level,
    }
    messages = unlooked_up_patches({Path("t.py"): facade_patch}, control_modules)
    assert len(messages) == 1, messages
    assert "reconciliation_kernel" in messages[0], messages[0]


def test_forward_reference_precedence_and_alias() -> None:
    facade = "def h():\n    return Y\n"
    facade_patch = 'def test(monkeypatch):\n    monkeypatch.setattr("specify_cli.consolidation.reconciliation.Y", 3)\n'
    alias_patch = 'def test(monkeypatch):\n    monkeypatch.setattr("specify_cli.consolidation.reconciliation.Z", 3)\n'

    # Rule 1: a module-level binding in the kernel wins over its function-local import.
    rule1_modules = {
        "specify_cli.consolidation.reconciliation": facade,
        "specify_cli.consolidation.reconciliation_kernel": "Y = 1\n\ndef g():\n    from specify_cli.consolidation.reconciliation import Y\n    return Y\n",
    }
    messages = unlooked_up_patches({Path("t.py"): facade_patch}, rule1_modules)
    assert len(messages) == 1, messages
    assert "reconciliation_kernel" in messages[0], messages[0]

    # Rule 2: a function-local alias resolves to the imported name.
    rule2_modules = {
        "specify_cli.consolidation.reconciliation": facade,
        "specify_cli.consolidation.reconciliation_kernel": "def g():\n    from specify_cli.consolidation.reconciliation import Y as Z\n    return Z\n",
    }
    assert unlooked_up_patches({Path("t.py"): facade_patch}, rule2_modules) == []
    messages = unlooked_up_patches({Path("t.py"): alias_patch}, rule2_modules)
    assert len(messages) == 1, messages
    assert "Z" in messages[0], messages[0]

    # Rule 3: the source module of the function-local import owns the lookup.
    rule3_modules = {
        "specify_cli.consolidation.reconciliation": "X = 0\n",
        "specify_cli.consolidation.reconciliation_kernel": "def g():\n    from specify_cli.consolidation.reconciliation_bound import Y\n    return Y\n",
        "specify_cli.consolidation.reconciliation_bound": "def b():\n    return Y\n",
    }
    bound_patch = 'def test(monkeypatch):\n    monkeypatch.setattr("specify_cli.consolidation.reconciliation_bound.Y", 3)\n'
    assert unlooked_up_patches({Path("t.py"): bound_patch}, rule3_modules) == []

    # Rule 4: a function-local import from any other module is ignored — the
    # name counts as a lookup in M itself.
    rule4_modules = {
        "specify_cli.consolidation.reconciliation": "X = 0\n",
        "specify_cli.consolidation.reconciliation_kernel": "def g():\n    from os import Y\n    return Y\n",
    }
    kernel_patch = 'def test(monkeypatch):\n    monkeypatch.setattr("specify_cli.consolidation.reconciliation_kernel.Y", 3)\n'
    assert unlooked_up_patches({Path("t.py"): kernel_patch}, rule4_modules) == []


def test_family_helper_patches_every_binding_module(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = types.ModuleType("fake")
    vars(fake)["TERMINUS_ENTRY_POINTS"] = object()
    monkeypatch.setattr(reconciliation_family, "RECONCILIATION_FAMILY", (reconciliation, fake))
    sentinel = object()
    setattr_reconciliation_family(monkeypatch, "TERMINUS_ENTRY_POINTS", sentinel)
    assert reconciliation.TERMINUS_ENTRY_POINTS is sentinel
    assert vars(fake)["TERMINUS_ENTRY_POINTS"] is sentinel


def test_family_helper_patches_consumer_bindings(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel = object()
    setattr_reconciliation_family(monkeypatch, "build_approved_wp_set", sentinel)
    assert reconciliation.build_approved_wp_set is sentinel
    assert phase_claim.build_approved_wp_set is sentinel
    assert phase_gate.build_approved_wp_set is sentinel
    assert forecast.build_approved_wp_set is sentinel

    fake_consumer = types.ModuleType("fake_consumer")
    vars(fake_consumer)["build_approved_wp_set"] = object()
    monkeypatch.setattr(
        reconciliation_family,
        "RECONCILIATION_CONSUMERS",
        (*reconciliation_family.RECONCILIATION_CONSUMERS, fake_consumer),
    )
    second = object()
    setattr_reconciliation_family(monkeypatch, "build_approved_wp_set", second)
    assert vars(fake_consumer)["build_approved_wp_set"] is not second


def test_family_helper_refuses_unbound_name() -> None:
    with pytest.raises(AttributeError, match="no consolidation reconciliation-family module binds"):
        reconciliation_family.family_modules_binding("definitely_not_bound")


def test_patch_reconciliation_family_patches_and_restores(monkeypatch: pytest.MonkeyPatch) -> None:
    """``patch_reconciliation_family`` patches every binding module and restores them all."""
    fake = types.ModuleType("fake")
    original = reconciliation.TERMINUS_ENTRY_POINTS
    vars(fake)["TERMINUS_ENTRY_POINTS"] = original
    monkeypatch.setattr(reconciliation_family, "RECONCILIATION_FAMILY", (reconciliation, fake))
    sentinel = object()
    with reconciliation_family.patch_reconciliation_family("TERMINUS_ENTRY_POINTS", sentinel) as patched:
        assert patched is sentinel
        assert reconciliation.TERMINUS_ENTRY_POINTS is sentinel
        assert vars(fake)["TERMINUS_ENTRY_POINTS"] is sentinel
    assert reconciliation.TERMINUS_ENTRY_POINTS is original
    assert vars(fake)["TERMINUS_ENTRY_POINTS"] is original
