"""Always-on gate: pack-skill fixtures never put activation keys in ``extra=``.

``tests/charter/skill_pack_support.write_config`` seeds activation into the
activation ledger (``.kittify/charter/activation.yaml``) through ``ledger=``,
and raises when its ``extra=`` config text carries an activation key (#6595).
That check runs only when the calling test runs, and most callers live in
``tests/specify_cli/``, whose trees are out of the per-PR matrix. A caller
added on a pre-guard base (#6474's projection test) therefore merged green and
first went red in the nightly (#6563).

This gate reads every reference to ``write_config`` statically, so the same
shape fails in the per-PR architectural battery. A reference it cannot read
also fails, because an unread caller would make the gate vacuous: an
``extra=`` that is not a string literal or a module-level string constant
(one bound once, by a plain assignment, and never inside a function), a
``**`` or ``*`` unpack, a reference that is not called directly (an alias of
the function or of the helper module, ``functools.partial``) and a star
import of the helper. Calls inside ``with pytest.raises(ValueError)`` are
the helper's own refusal tests and are skipped.
"""

from __future__ import annotations

import ast
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

from charter.activation.activation_ledger import LEDGER_KEYS

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_TESTS_ROOT = Path(__file__).resolve().parents[1]
_HELPER_MODULE = "skill_pack_support"
_HELPER_FUNCTION = "write_config"

# Concrete floor: callers on main when this gate landed (2026-10-25) number 37.
# A scan that finds fewer than this has stopped reading them.
_MIN_CALLS = 30


@dataclass(frozen=True)
class _Call:
    location: str
    extra: str | None  # None when the reference passes no readable ``extra=``
    resolved: bool


@dataclass
class _HelperNames:
    modules: set[str]  # names bound to the helper module (``import ... as support``)
    functions: set[str]  # names bound to ``write_config`` itself
    star_import_line: int | None = None


def _helper_names(tree: ast.Module) -> _HelperNames:
    names = _HelperNames(set(), set())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            source = node.module or ""
            for alias in node.names:
                if alias.name == _HELPER_MODULE:
                    names.modules.add(alias.asname or alias.name)
                elif source.endswith(_HELPER_MODULE) and alias.name == _HELPER_FUNCTION:
                    names.functions.add(alias.asname or alias.name)
                elif source.endswith(_HELPER_MODULE) and alias.name == "*":
                    names.star_import_line = node.lineno
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.endswith(f".{_HELPER_MODULE}") and alias.asname:
                    names.modules.add(alias.asname)
    return names


def _is_module_ref(node: ast.expr, modules: set[str]) -> bool:
    """``support`` (an import alias) or a dotted ``tests.charter.skill_pack_support``."""
    if isinstance(node, ast.Name):
        return node.id in modules
    return isinstance(node, ast.Attribute) and node.attr == _HELPER_MODULE


def _is_helper_ref(node: ast.AST, names: _HelperNames) -> bool:
    if isinstance(node, ast.Attribute):
        return node.attr == _HELPER_FUNCTION and _is_module_ref(node.value, names.modules)
    return isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in names.functions


def _function_local_names(tree: ast.Module) -> set[str]:
    """Names bound anywhere inside a function: assignments and parameters."""
    local: set[str] = set()
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        params = func.args
        local.update(arg.arg for arg in [*params.posonlyargs, *params.args, *params.kwonlyargs])
        local.update(arg.arg for arg in (params.vararg, params.kwarg) if arg is not None)
        local.update(node.id for node in ast.walk(func) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store))
    return local


def _module_scope_bindings(node: ast.AST) -> Iterator[str]:
    """Every name bound at module scope, once per binding, function and class bodies excluded."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
            yield child.id
        elif isinstance(child, ast.alias):
            yield (child.asname or child.name).split(".")[0]
        yield from _module_scope_bindings(child)


def _module_strings(tree: ast.Module) -> dict[str, str]:
    """Module-level string constants bound exactly once, by a simple assignment, and never in a function."""
    strings: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target: ast.expr = node.targets[0]
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            target = node.target
        else:
            continue
        text = _literal_string(node.value, {}) if node.value is not None else None
        if isinstance(target, ast.Name) and text is not None:
            strings[target.id] = text
    rebound = [name for name, count in Counter(_module_scope_bindings(tree)).items() if count > 1]
    for name in {*rebound, *_function_local_names(tree)}:
        strings.pop(name, None)
    return strings


def _literal_string(node: ast.expr, constants: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _literal_string(node.left, constants)
        right = _literal_string(node.right, constants)
        return None if left is None or right is None else left + right
    return None


def _is_refusal_block(item: ast.withitem) -> bool:
    """``pytest.raises(ValueError, ...)``: the helper's own refusal of an activation key."""
    call = item.context_expr
    return (
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "raises"
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "pytest"
        and bool(call.args)
        and isinstance(call.args[0], ast.Name)
        and call.args[0].id == "ValueError"
    )


def _nodes_outside_refusals(node: ast.AST, inside: bool = False) -> Iterator[tuple[ast.AST, bool]]:
    if isinstance(node, ast.With):
        inside = inside or any(_is_refusal_block(item) for item in node.items)
    yield node, inside
    for child in ast.iter_child_nodes(node):
        yield from _nodes_outside_refusals(child, inside)


def _read_call(call: ast.Call, location: str, constants: dict[str, str]) -> _Call:
    if any(kw.arg is None for kw in call.keywords) or any(isinstance(arg, ast.Starred) for arg in call.args):
        return _Call(location, None, resolved=False)
    extra = next((kw.value for kw in call.keywords if kw.arg == "extra"), None)
    if extra is None:
        return _Call(location, None, resolved=True)
    text = _literal_string(extra, constants)
    return _Call(location, text, resolved=text is not None)


def scan_source(source: str, filename: str) -> list[_Call]:
    """Every reference to ``write_config`` in *source*, with its resolved ``extra=`` text."""
    tree = ast.parse(source, filename=filename)
    names = _helper_names(tree)
    found: list[_Call] = []
    if names.star_import_line is not None:
        found.append(_Call(f"{filename}:{names.star_import_line}", None, resolved=False))
    constants = _module_strings(tree)
    called: dict[int, ast.Call] = {}
    attribute_bases: set[int] = set()
    references: list[tuple[ast.AST, bool]] = []
    module_names: list[ast.Name] = []
    for node, inside in _nodes_outside_refusals(tree):
        if isinstance(node, ast.Call):
            called[id(node.func)] = node
        if isinstance(node, ast.Attribute):
            attribute_bases.add(id(node.value))
        if _is_helper_ref(node, names):
            references.append((node, inside))
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in names.modules:
            module_names.append(node)
    # The helper module used other than as ``support.<attr>`` (``alias = support``) hides its calls.
    found.extend(_Call(f"{filename}:{name.lineno}", None, resolved=False) for name in module_names if id(name) not in attribute_bases)
    for ref, inside in references:
        call = called.get(id(ref))
        if inside and call is not None:
            continue
        location = f"{filename}:{getattr(ref, 'lineno', 0)}"
        found.append(_Call(location, None, resolved=False) if call is None else _read_call(call, location, constants))
    return found


def activation_keys_in(extra: str) -> list[str]:
    """The activation keys in *extra*, read the way ``write_config`` reads them."""
    loaded = yaml.safe_load(extra) or {}
    keys = set(loaded) if isinstance(loaded, (dict, list)) else set()
    return sorted(keys & set(LEDGER_KEYS))


def _all_calls() -> list[_Call]:
    calls: list[_Call] = []
    for path in sorted(_TESTS_ROOT.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        if _HELPER_MODULE in source and path.name != f"{_HELPER_MODULE}.py":
            calls.extend(scan_source(source, path.relative_to(_TESTS_ROOT.parent).as_posix()))
    return calls


def test_scan_reads_the_callers() -> None:
    calls = _all_calls()
    assert len(calls) >= _MIN_CALLS, f"found only {len(calls)} write_config calls; the scan stopped reading callers"


def test_every_reference_is_readable() -> None:
    unread = [call.location for call in _all_calls() if not call.resolved]
    assert not unread, f"call write_config directly, with extra= as a string literal or a module-level string constant, so this gate can read it: {unread}"


def test_no_caller_seeds_activation_through_extra() -> None:
    offenders = {call.location: keys for call in _all_calls() if call.extra and (keys := activation_keys_in(call.extra))}
    assert not offenders, f"pass these activation keys through ledger=, not extra=: {offenders}"


_MUTANT = """
import functools
import tests.charter.skill_pack_support
from tests.charter import skill_pack_support as support
from tests.charter.skill_pack_support import write_config as wc

AGENTS = "agents:\\n  available:\\n    - claude\\n"
SHADOWED = "agents: {}\\n"

def test_a(tmp_path):
    support.write_config(tmp_path, None, extra=AGENTS + "activated_skills: []\\n")

def test_b(tmp_path):
    wc(tmp_path, None, extra="deactivated_skills: [x]\\n")

def test_c(tmp_path, dynamic):
    support.write_config(tmp_path, None, extra=dynamic)

def test_d(tmp_path):
    with pytest.raises(ValueError):
        support.write_config(tmp_path, None, extra="activated_skills: []\\n")

def test_e(tmp_path):
    SHADOWED = "activated_skills: []\\n"
    support.write_config(tmp_path, None, extra=SHADOWED)

def test_f(tmp_path):
    support.write_config(tmp_path, None, **{"extra": "activated_skills: []\\n"})

def test_g(tmp_path):
    write = support.write_config
    functools.partial(wc, extra="activated_skills: []\\n")(tmp_path, None)

def test_h(tmp_path):
    tests.charter.skill_pack_support.write_config(tmp_path, None, extra="activated_skills: []\\n")

def test_i(tmp_path):
    with pytest.raises(KeyError):
        support.write_config(tmp_path, None, extra="activated_skills: []\\n")

ALIAS = support
GROWN = "agents: {}\\n"
GROWN += "activated_skills: []\\n"
PAIR = "agents: {}\\n"
PAIR, OTHER = "activated_skills: []\\n", 1
if True:
    NESTED = "activated_skills: []\\n"
NESTED = "agents: {}\\n"

def test_j(tmp_path):
    support.write_config(tmp_path, None, extra=GROWN)
    support.write_config(tmp_path, None, extra=PAIR)
    support.write_config(tmp_path, None, extra=NESTED)
"""


def test_gate_flags_the_legacy_shape() -> None:
    """Self-mutation: every shape the gate must flag, and the one refusal block it must skip."""
    calls = {call.location.removeprefix("mutant.py:"): call for call in scan_source(_MUTANT, "mutant.py")}

    flagged = {line: activation_keys_in(call.extra or "") for line, call in calls.items() if call.resolved}
    unread = sorted(line for line, call in calls.items() if not call.resolved)
    assert flagged == {"11": ["activated_skills"], "14": ["deactivated_skills"], "35": ["activated_skills"], "39": ["activated_skills"]}
    assert unread == ["17", "25", "28", "31", "32", "41", "51", "52", "53"]
    assert "21" not in calls  # the helper's own refusal test


def test_gate_flags_a_star_import() -> None:
    calls = scan_source("from tests.charter.skill_pack_support import *\n", "mutant.py")

    assert [(call.location, call.resolved) for call in calls] == [("mutant.py:1", False)]


def test_keys_are_read_like_the_helper_reads_them() -> None:
    assert activation_keys_in("[activated_skills]\n") == ["activated_skills"]
    assert activation_keys_in("agents:\n  available: [claude]\n") == []
    assert activation_keys_in("just text\n") == []
