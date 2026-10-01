"""Symbol-level dead-code gate (Slice F WP02 / FR-120).

Where ``test_no_dead_modules`` ensures every module has at least one
non-test caller, this gate ensures every public module-level NAME has
at least one non-test caller too. A public class declared in
``__all__`` with zero callers -- the failure mode that bit Mission B
WP08 cycle 1 -- fails here.

ATDD anchor: AC-8 (covers: FR-120, FR-122).

Scope (#470): widened beyond ``__all__``
-----------------------------------------

The gate originally scanned ONLY names listed in a module's ``__all__``
literal. That left every public (non-underscore) module-level name NOT
in ``__all__`` invisible to the gate -- exactly the blind spot that let
``audit_invocation_disagreement`` sit dead (imported only by its own
unit test, never wired to any ``src/`` caller) while nothing red-ed.
``decls`` (below) is now the UNION of a module's ``__all__`` members and
every public (non-underscore) module-level ``def``/``class``/assignment
target. Two consequences of widening past ``__all__``'s explicit
"exported for other modules" declaration:

* A non-``__all__`` name that is merely referenced somewhere else in its
  OWN defining module (a ``logger = logging.getLogger(__name__)``-style
  module-private helper that never intended cross-module use) is not
  dead -- see ``_used_within_own_module``. This intra-module signal is
  deliberately NOT extended to ``__all__`` members: being in ``__all__``
  is itself a claim of cross-module export, so an ``__all__`` member
  used only within its own module stays caught, unchanged from the
  original gate.
* A Typer ``@app.command(...)``/``@app.callback(...)``-decorated
  function is dispatched only through the CLI framework, never via a
  direct ``from module import name`` -- see
  ``_is_typer_command_definition`` (T013 structural auto-exempt,
  alongside the pre-existing migration-class / Typer-sub-app / re-export
  checks).

The initial widening pass's residual offenders (real functions/classes/
constants with zero callers under either signal above, once the two
structural rescues above are applied) are far too many to hand-triage in
one PR -- exactly the "unpredictable blast radius...expect a batch of
small follow-up fixes" the issue anticipated. They are grandfathered in
the ``widened_grandfathered_470`` section of the allowlist file (see
"Allowlist" below; exposed here as ``_WIDENED_SCOPE_GRANDFATHERED_470``)
pending follow-up triage in #633.

Mechanics
---------

* Walk every ``*.py`` file under ``src/`` and collect, per module, the
  UNION of its ``__all__`` literal (``ast.Assign`` whose target is
  ``Name(id="__all__")`` with a list / tuple of string literals as
  value) and its public module-level ``def``/``class``/assignment names.
* Walk every ``*.py`` file under ``src/`` again and collect every
  ``from <module> import <name>`` site, resolving relative imports
  against the importer's containing package (same logic as
  ``test_no_dead_modules``).
* For each ``(module, name)`` in ``decls``, fail if no caller in
  ``src/`` (other than the declaring module itself) imports that name
  from that module OR re-exports it from its parent package -- UNLESS
  *name* is not an ``__all__`` member and is used within its own
  defining module (see above).

The real-tree walk runs once per file (:func:`_real_tree_inputs`, read-only
views), however many tests in this file consume it, and is released at file
end by the module-scoped ``_clear_real_tree_inputs`` fixture (FR-006): the
cached inputs hold every ``src/`` syntax tree and its source, the one reasoned
exception to "caches hold findings, not trees", bounded to this file.

Tests under ``tests/`` are deliberately NOT counted as callers -- a
symbol exercised only by its own unit tests is functionally dead in the
runtime sense this gate cares about (the WP08 cycle-1 case study).

Allowlist
---------

The documented exceptions live in ``tests/architectural/dead_symbol_allowlist.yaml``,
read by exactly one loader, ``tests/architectural/_dead_symbol_allowlist.py``,
which enforces the schema (a category with a rationale on every entry, an
issue where the category requires one, whole-file ``(module, name)``
uniqueness, no tombstone categories). The file has two sections, and the gate
evaluates both from the SAME parsed ``DeadSymbolAllowlist`` instance:

* ``entries`` -- the ``__all__``-scope exemptions. Identity is
  ``(module, name)``: ``module`` is the dotted module whose ``__all__``
  declares the name, ``name`` the bare module-level name. An entry exempts
  its symbol only while the name is also *keyable* (it binds a real
  definition, import alias or facade entry -- fail-closed, so
  ``__all__ = ['Ghost']`` stays an offender). A body edit to an exempted
  symbol costs no allowlist edit. Each entry that no longer earns its place
  gets exactly one stale verdict, first match wins: INVALID (declared but
  un-keyable), GONE (no longer declared in that module's ``__all__`` --
  deleted, renamed, moved or dropped; a move gets a "probably moved to"
  hint), REVIVED (it has a caller again), SUPERSEDED (a T013 structural
  auto-exemption now covers it) or MOOT (the module is star-imported, so the
  entry exempts nothing).
* ``widened_grandfathered_470`` -- the #470 widened-scope debt, as
  ``module::name`` strings, with its own per-entry stale ratchet
  (:func:`_compute_widened_stale`).

Content hashes are never persisted. :func:`_resolve_final_key` still
computes one at runtime, for two jobs only: the keyability precondition
above, and condition (1) of the re-export auto-exempt (a live same-name
collision is never auto-exempt). The decision record is the dead-symbol
allowlist identity ADR under ``docs/adr/4.x/``.

To add an entry, first try to wire the symbol, drop it from ``__all__`` or
delete it. If an exception is genuinely warranted, add a ``(module, name)``
entry to the YAML file under the right category, with a rationale and, where
the category requires one, a follow-up issue (FR-303). The file's size is
capped by the shrink-only ratchet in ``_baselines.yaml``.
"""

from __future__ import annotations

import ast
import copy
import functools
import inspect
import sys
from collections.abc import Iterator, Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest
import yaml

from specify_cli.ast_analysis.imports import (
    extract_static_all as _extract_all_literal,
)
from specify_cli.ast_analysis.imports import (
    module_of_import_from as _resolve_import_from,
)
from tests.architectural._ast_scan import read_and_parse
from tests.architectural._dead_symbol_allowlist import (
    ALLOWLIST,
    ALLOWLIST_PATH,
    SYMBOL_ALLOWLIST,
    WIDENED_SCOPE_GRANDFATHERED_470,
    AllowlistCategory,
    AllowlistEntry,
    DeadSymbolAllowlist,
    DeadSymbolKey,
    StaleVerdict,
    load_allowlist,
)
from tests.architectural._symbol_key import (
    CorpusModule,
    Location,
    SymbolKey,
    bind_call_accessor_aliases,
    classify_collisions,
    definition_span,
    find_module_factory_functions,
    key_tier,
    record_call_chain_attr_edges,
    resolve_symbol_key,
)

pytestmark = [pytest.mark.architectural]


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_ROOT = _REPO_ROOT / "src"


# Compatibility aliases (G8). The data lives in ``dead_symbol_allowlist.yaml``;
# both names are views of the loader's single parse (``ALLOWLIST``), never a
# second read. ``test_p1_planted_regression.py`` and ``len()`` consumers read them.
_SYMBOL_ALLOWLIST: frozenset[DeadSymbolKey] = SYMBOL_ALLOWLIST
_WIDENED_SCOPE_GRANDFATHERED_470: frozenset[str] = WIDENED_SCOPE_GRANDFATHERED_470

# Non-vacuity floor on the scanned corpus, not a pin (contract §2.1). A walker
# that silently returned a fraction of ``src/`` would otherwise pass vacuously.
# Live on the #5346 base: 3,922 ``__all__`` names across 656 modules.
_CORPUS_FLOOR_NAMES = 3500
_CORPUS_FLOOR_MODULES = 600


def _is_asset_blob(path: Path) -> bool:
    """True if *path* is a shipped doctrine ``asset`` blob, not a module.

    An ``ArtifactKind.ASSET`` blob is packaged data/logic shipped with a
    doctrine pack and loaded by file path (never imported), identified by a
    sibling ``<name>.asset.yaml`` sidecar manifest. Its public ``__all__``
    symbols are consumed by the shipped script itself, not by ``src/`` callers,
    so the dead-symbol gate must not treat them as unimported.
    """
    return (path.parent / f"{path.name}.asset.yaml").is_file()


def _iter_src_python_files() -> list[Path]:
    """Yield every importable ``*.py`` under ``src/`` (sorted, deterministic).

    Excludes doctrine ``asset`` blobs (shipped, loaded by path — see
    :func:`_is_asset_blob`).
    """
    return sorted(p for p in _SRC_ROOT.rglob("*.py") if "__pycache__" not in p.parts and not _is_asset_blob(p))


def _module_dotted(path: Path) -> str:
    """Return the dotted module name for *path* relative to ``src/``.

    ``src/charter/activation/mission_type_profiles.py`` -> ``charter.activation.mission_type_profiles``.
    For ``__init__.py`` the package itself is returned (``charter``).
    """
    rel = path.relative_to(_SRC_ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _package_of(path: Path) -> str:
    """Return the dotted package containing *path* (for relative imports).

    Mirrors the helper in ``test_no_dead_modules`` so resolution is
    identical.
    """
    rel = path.relative_to(_SRC_ROOT).with_suffix("")
    parts = list(rel.parts)
    return ".".join(parts[:-1])


def _extract_str_consts_from_body(tree: ast.Module) -> dict[str, str]:
    """Extract top-level ``NAME = "string"`` constants from a module body.

    Only top-level body nodes are inspected (not nested scopes) to avoid
    false matches from deeply nested string literals.

    Used by ``_build_alias_map_and_consts`` as a separate helper to keep
    ``_build_alias_map_and_consts`` within the McCabe complexity ceiling.
    """
    str_consts: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name):
                        str_consts[tgt.id] = node.value.value
        elif (
            isinstance(node, ast.AnnAssign)
            and node.value is not None
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
            and isinstance(node.target, ast.Name)
        ):
            str_consts[node.target.id] = node.value.value
    return str_consts


def _build_alias_map_and_consts(
    tree: ast.Module,
    containing_pkg: str,
) -> tuple[dict[str, str], dict[str, str]]:
    """Build per-file import alias map and top-level string constants.

    Returns ``(alias_map, str_consts)`` where:

    * ``alias_map`` maps a local Python name to the dotted module it
      resolves to.  Explicit and unaliased ``ImportFrom`` bindings are
      captured:

      - ``import a.b.c as x``  →  ``{"x": "a.b.c"}``
      - ``from X import Y`` / ``from X import Y as Z``  →
        ``{"Y"/"Z": "X.Y"}`` (absolute X)

      Plain ``import a.b.c`` (no alias) is skipped: the gate only needs
      to trace ``x.attr``-style attribute accesses where the module is
      bound to a single local name.

    * ``str_consts`` maps top-level ``NAME = "string"`` (or ``AnnAssign``)
      to the string value.  Used by ``_record_facade_edges`` to resolve
      symbolic module-path variables like ``_EVENTS_MODULE = ".events"``.
    """
    alias_map: dict[str, str] = {}
    # Walk ALL nodes for import aliases: late/local imports (inside functions
    # or try-blocks) are common in spec-kitty for cycle-safety, and the
    # module-attr detector must see them.  String-constant resolution is
    # limited to top-level body (see ``_extract_str_consts_from_body``).
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    alias_map[alias.asname] = alias.name
                elif "." not in alias.name:
                    # ``import flat_module`` — local name IS the module name.
                    # Dotted imports (``import a.b.c``) are skipped: the local
                    # binding is just ``a``, which would mismatch the full path.
                    alias_map[alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom):
            target = _resolve_import_from(node, containing_pkg)
            for alias in node.names:
                if alias.name != "*":
                    alias_map[alias.asname or alias.name] = f"{target}.{alias.name}"
    return alias_map, _extract_str_consts_from_body(tree)


def _record_module_attr_edges(
    tree: ast.Module,
    alias_map: dict[str, str],
    per_symbol: dict[str, set[str]],
    known_modules: frozenset[str],
) -> None:
    """Record caller-edges from ``alias.attr`` attribute patterns (detector a).

    For every ``<alias>.<name>`` node where ``<alias>`` resolves to a
    *real module* (a key in ``known_modules``) via ``alias_map``, records
    ``per_symbol[resolved_module].add(name)``.

    This subsumes the previously-missing Typer ``app.command()`` and
    lifecycle-module attribute patterns (detector c in the research).

    The ``known_modules`` guard is load-bearing (T004 / no-false-negative):
    ``from M import SomeClass as C`` binds ``C`` to the *synthetic* path
    ``M.SomeClass`` (a symbol, not a module). A class-attribute access
    ``C.NAME`` must NOT record a module-edge on ``M`` — otherwise
    ``_submodule_index`` would index ``M.SomeClass`` under prefix ``M`` and
    rule 3 of ``_symbol_has_caller`` would falsely rescue a genuinely-dead
    ``M::NAME``, silently re-blinding the very gate this mission hardens.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in alias_map:
            resolved = alias_map[node.value.id]
            if resolved in known_modules:
                per_symbol.setdefault(resolved, set()).add(node.attr)


def _record_getattr_str_edges(
    tree: ast.Module,
    alias_map: dict[str, str],
    per_symbol: dict[str, set[str]],
    known_modules: frozenset[str],
) -> None:
    """Record caller-edges from ``getattr(alias, 'name')`` patterns (detector d).

    For every ``getattr(<alias>, <str_literal>)`` call where ``<alias>``
    resolves to a *real module* (in ``known_modules``) via ``alias_map``,
    records ``per_symbol[resolved_module].add(str_literal)``. See
    ``_record_module_attr_edges`` for why the ``known_modules`` guard is
    required to avoid re-blinding the gate via a symbol-path collision.
    """
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getattr" and len(node.args) >= 2):
            continue
        obj, attr_arg = node.args[0], node.args[1]
        if not (isinstance(obj, ast.Name) and obj.id in alias_map):
            continue
        if not (isinstance(attr_arg, ast.Constant) and isinstance(attr_arg.value, str)):
            continue
        resolved = alias_map[obj.id]
        if resolved in known_modules:
            per_symbol.setdefault(resolved, set()).add(attr_arg.value)


def _find_facade_lazy_dict_name(tree: ast.Module) -> str | None:
    """Return the lazy-imports dict variable referenced in a ``__getattr__`` facade.

    Searches for ``def __getattr__(name): ... DICT[name] ...`` at module
    scope.  Returns the dict variable name, or ``None`` if not a facade.
    """
    for node in tree.body:
        if not (isinstance(node, ast.FunctionDef) and node.name == "__getattr__"):
            continue
        if not node.args.args:
            continue
        arg_id = node.args.args[0].arg
        for child in ast.walk(node):
            if isinstance(child, ast.Subscript) and isinstance(child.value, ast.Name) and isinstance(child.slice, ast.Name) and child.slice.id == arg_id:
                return child.value.id
    return None


def _resolve_relative_module(mod_path: str, containing_pkg: str) -> str:
    """Resolve a relative-or-absolute dotted module path to its absolute form.

    ``".clock"`` resolved from ``"specify_cli.sync"`` →
    ``"specify_cli.sync.clock"``.  Absolute paths are returned unchanged.
    """
    if not mod_path.startswith("."):
        return mod_path
    level = len(mod_path) - len(mod_path.lstrip("."))
    rel = mod_path.lstrip(".")
    pkg_parts = containing_pkg.split(".") if containing_pkg else []
    base_parts = pkg_parts[: len(pkg_parts) - (level - 1)] if level > 1 else list(pkg_parts)
    if rel:
        base_parts = base_parts + rel.split(".")
    return ".".join(base_parts)


def _record_facade_edges(
    tree: ast.Module,
    containing_pkg: str,
    str_consts: dict[str, str],
    per_symbol: dict[str, set[str]],
    known_modules: frozenset[str],
) -> None:
    """Record caller-edges from a ``__getattr__``-style lazy-import facade (detector b).

    Detects the pattern::

        _LAZY_IMPORTS = {
            "Foo": (".bar", "Foo"),           # literal relative module
            "Baz": (_EVENTS_MODULE, "Baz"),   # name resolved via str_consts
        }
        def __getattr__(name):
            module_path, attr = _LAZY_IMPORTS[name]
            ...

    For each resolvable dict entry, records
    ``per_symbol[resolved_submodule].add(attr_name)``.  The ``_LAZY_IMPORTS``
    dict may be typed (``ast.AnnAssign``) or untyped (``ast.Assign``).
    """
    dict_name = _find_facade_lazy_dict_name(tree)
    if dict_name is None:
        return
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets: list[ast.expr] = list(node.targets)
            value_node: ast.expr | None = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value_node = node.value
        else:
            continue
        if not any(isinstance(t, ast.Name) and t.id == dict_name for t in targets):
            continue
        if not isinstance(value_node, ast.Dict):
            continue
        for val in value_node.values:
            if not isinstance(val, (ast.Tuple, ast.List)) or len(val.elts) != 2:
                continue
            mod_expr, attr_expr = val.elts
            if not (isinstance(attr_expr, ast.Constant) and isinstance(attr_expr.value, str)):
                continue
            attr_name: str = attr_expr.value
            mod_path: str | None = None
            if isinstance(mod_expr, ast.Constant) and isinstance(mod_expr.value, str):
                mod_path = mod_expr.value
            elif isinstance(mod_expr, ast.Name) and mod_expr.id in str_consts:
                mod_path = str_consts[mod_expr.id]
            if mod_path is None:
                continue
            resolved = _resolve_relative_module(mod_path, containing_pkg)
            if resolved in known_modules:
                per_symbol.setdefault(resolved, set()).add(attr_name)


def _extract_public_module_level_names(tree: ast.Module) -> frozenset[str]:
    """Every public (non-underscore) module-level ``def``/``class``/assignment name (#470).

    Scoped to module-scope statements only (``tree.body``, never nested
    scopes) -- a public-looking name inside a function/class body is not a
    module-level declaration. An ``ast.Assign``/``ast.AnnAssign`` contributes
    only ``ast.Name`` targets (a tuple/attribute/subscript target is not a
    simple module-level symbol binding).
    """
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                names.add(node.name)
            continue
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and not target.id.startswith("_"):
                    names.add(target.id)
    return frozenset(names)


def _argument_nodes(args: ast.arguments) -> tuple[ast.arg, ...]:
    return (
        *args.posonlyargs,
        *args.args,
        *args.kwonlyargs,
        *(() if args.vararg is None else (args.vararg,)),
        *(() if args.kwarg is None else (args.kwarg,)),
    )


def _visit_function_outer_expressions(visitor: ast.NodeVisitor, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
    for decorator in node.decorator_list:
        visitor.visit(decorator)
    for default in (*node.args.defaults, *(value for value in node.args.kw_defaults if value is not None)):
        visitor.visit(default)
    for argument in _argument_nodes(node.args):
        if argument.annotation is not None:
            visitor.visit(argument.annotation)
    if node.returns is not None:
        visitor.visit(node.returns)


class _FunctionScopeVisitor(ast.NodeVisitor):
    def __init__(self, name: str) -> None:
        self.name = name
        self.binds_name = False
        self.global_declared = False
        self.nonlocal_declared = False

    def visit_Name(self, node: ast.Name) -> None:
        if node.id == self.name and not isinstance(node.ctx, ast.Load):
            self.binds_name = True

    def visit_alias(self, node: ast.alias) -> None:
        bound_name = node.asname or node.name.rpartition(".")[2]
        if bound_name == self.name:
            self.binds_name = True

    def visit_Global(self, node: ast.Global) -> None:
        if self.name in node.names:
            self.global_declared = True

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        if self.name in node.names:
            self.nonlocal_declared = True

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name == self.name:
            self.binds_name = True
        self.generic_visit(node)

    def visit_MatchAs(self, node: ast.MatchAs) -> None:
        if node.name == self.name:
            self.binds_name = True
        self.generic_visit(node)

    def visit_MatchStar(self, node: ast.MatchStar) -> None:
        if node.name == self.name:
            self.binds_name = True
        self.generic_visit(node)

    def visit_MatchMapping(self, node: ast.MatchMapping) -> None:
        if node.rest == self.name:
            self.binds_name = True
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.name == self.name:
            self.binds_name = True
        _visit_function_outer_expressions(self, node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if node.name == self.name:
            self.binds_name = True
        _visit_function_outer_expressions(self, node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for default in node.args.defaults:
            self.visit(default)
        for default in (value for value in node.args.kw_defaults if value is not None):
            self.visit(default)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if node.name == self.name:
            self.binds_name = True
        for decorator in node.decorator_list:
            self.visit(decorator)
        for base in node.bases:
            self.visit(base)
        for keyword in node.keywords:
            self.visit(keyword.value)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self.visit(node.iter)
        for condition in node.ifs:
            self.visit(condition)


def _classify_function_scope(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda, name: str) -> tuple[bool, bool, bool]:
    visitor = _FunctionScopeVisitor(name)
    for argument in _argument_nodes(node.args):
        if argument.arg == name:
            visitor.binds_name = True
    if isinstance(node, ast.Lambda):
        visitor.visit(node.body)
    else:
        for statement in node.body:
            visitor.visit(statement)
    return visitor.binds_name, visitor.global_declared, visitor.nonlocal_declared


def _target_binds_name(target: ast.expr, name: str) -> bool:
    return any(isinstance(node, ast.Name) and node.id == name for node in ast.walk(target))


class _ModuleLevelNameUseVisitor(ast.NodeVisitor):
    def __init__(self, name: str) -> None:
        self.name = name
        self.found = False
        self.scopes: list[tuple[str, bool, bool]] = []

    def _name_is_shadowed(self, *, skip_class_scopes: bool = False) -> bool:
        crossed_scope_boundary = skip_class_scopes
        for kind, is_shadowed, global_declared in reversed(self.scopes):
            if kind == "class" and crossed_scope_boundary:
                continue
            if global_declared:
                return False
            if is_shadowed:
                return True
            crossed_scope_boundary = True
        return False

    def _mark_current_scope_shadowed(self) -> None:
        if not self.scopes:
            return
        kind, _, global_declared = self.scopes[-1]
        if not global_declared:
            self.scopes[-1] = (kind, True, global_declared)

    def _mark_current_scope_global(self) -> None:
        if not self.scopes:
            return
        kind, is_shadowed, _ = self.scopes[-1]
        self.scopes[-1] = (kind, is_shadowed, True)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id != self.name:
            return
        if not isinstance(node.ctx, ast.Load):
            if self.scopes and self.scopes[-1][0] == "class":
                self._mark_current_scope_shadowed()
            return
        if not self._name_is_shadowed():
            self.found = True

    def visit_alias(self, node: ast.alias) -> None:
        bound_name = node.asname or node.name.rpartition(".")[2]
        if bound_name == self.name and self.scopes and self.scopes[-1][0] == "class":
            self._mark_current_scope_shadowed()

    def visit_Global(self, node: ast.Global) -> None:
        if self.name in node.names and self.scopes and self.scopes[-1][0] == "class":
            self._mark_current_scope_global()

    def _visit_function_body(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda) -> None:
        binds_name, global_declared, nonlocal_declared = _classify_function_scope(node, self.name)
        if global_declared:
            is_shadowed = False
        elif nonlocal_declared:
            is_shadowed = self._name_is_shadowed(skip_class_scopes=True)
        else:
            is_shadowed = self._name_is_shadowed(skip_class_scopes=True) or binds_name
        self.scopes.append(("function", is_shadowed, global_declared))
        if isinstance(node, ast.Lambda):
            self.visit(node.body)
        else:
            for statement in node.body:
                self.visit(statement)
        self.scopes.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        _visit_function_outer_expressions(self, node)
        self._visit_function_body(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        _visit_function_outer_expressions(self, node)
        self._visit_function_body(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for default in node.args.defaults:
            self.visit(default)
        for default in (value for value in node.args.kw_defaults if value is not None):
            self.visit(default)
        self._visit_function_body(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for decorator in node.decorator_list:
            self.visit(decorator)
        for base in node.bases:
            self.visit(base)
        for keyword in node.keywords:
            self.visit(keyword.value)
        if node.name == self.name and self.scopes and self.scopes[-1][0] == "class":
            self._mark_current_scope_shadowed()
        self.scopes.append(("class", False, False))
        for statement in node.body:
            self.visit(statement)
        self.scopes.pop()

    def _visit_comprehension(self, node: ast.ListComp | ast.SetComp | ast.GeneratorExp | ast.DictComp) -> None:
        if node.generators:
            self.visit(node.generators[0].iter)
        self.scopes.append(("comprehension", False, False))
        for index, generator in enumerate(node.generators):
            if index > 0:
                self.visit(generator.iter)
            if _target_binds_name(generator.target, self.name):
                self._mark_current_scope_shadowed()
            for condition in generator.ifs:
                self.visit(condition)
        if isinstance(node, ast.DictComp):
            self.visit(node.key)
            self.visit(node.value)
        else:
            self.visit(node.elt)
        self.scopes.pop()

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_comprehension(node)

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._visit_comprehension(node)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._visit_comprehension(node)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._visit_comprehension(node)


def _used_within_own_module(tree: ast.Module, name: str) -> bool:
    """True if *name* has a Load that can resolve to the module binding (#470).

    Used ONLY to rescue a widened (non-``__all__``) symbol: intra-module use
    is real evidence a module-private-by-convention name is not dead, but is
    deliberately never consulted for an ``__all__`` member -- ``__all__``
    membership is itself a claim of cross-module export, so a same-module-only
    ``__all__`` symbol must stay caught (unchanged from the original gate).
    """
    visitor = _ModuleLevelNameUseVisitor(name)
    visitor.visit(tree)
    return visitor.found


def _walk_modules() -> tuple[
    dict[str, frozenset[str]],
    dict[str, frozenset[str]],
    dict[Path, str],
    dict[Path, ast.Module],
    dict[str, CorpusModule],
]:
    """Walk src/, return (decls, all_literal_decls, path_to_dotted, path_to_tree, corpus).

    * ``decls`` maps module dotted name to the UNION of its static
      ``__all__`` set and its public module-level names (#470 -- widened
      past ``__all__``, see the module docstring).
    * ``all_literal_decls`` maps module dotted name to ONLY its static
      ``__all__`` set (the pre-#470 scope) -- callers use this to tell an
      original ``__all__`` member from a widened-in name, since the two are
      rescued by different caller-detection rules.
    * ``path_to_dotted`` maps each ``*.py`` path to its dotted name.
    * ``path_to_tree`` caches parsed ASTs so the import walk does not
      re-read every file.
    * ``corpus`` maps dotted module name -> :class:`CorpusModule`
      (tree, source, containing_pkg) -- the source-bearing inversion T008
      (relocation-hardened-dead-code-scanners-01KX958P WP02) requires so
      :func:`tests.architectural._symbol_key.resolve_symbol_key` can hash a
      symbol's definition span: ``code_tokens_by_line`` needs the source
      STRING, not just the parsed tree. Not in the C-005 byte-frozen set --
      safe to extend.
    """
    decls: dict[str, frozenset[str]] = {}
    all_literal_decls: dict[str, frozenset[str]] = {}
    path_to_dotted: dict[Path, str] = {}
    path_to_tree: dict[Path, ast.Module] = {}
    corpus: dict[str, CorpusModule] = {}
    for path in _iter_src_python_files():
        source, tree = read_and_parse(path)
        dotted = _module_dotted(path)
        path_to_dotted[path] = dotted
        path_to_tree[path] = tree
        corpus[dotted] = CorpusModule(tree=tree, source=source, containing_pkg=_package_of(path))
        all_literal = _extract_all_literal(tree) or frozenset()
        if all_literal:
            all_literal_decls[dotted] = all_literal
        widened = all_literal | _extract_public_module_level_names(tree)
        if widened:
            decls[dotted] = widened
    return decls, all_literal_decls, path_to_dotted, path_to_tree, corpus


def _imports_by_target(
    path_to_dotted: dict[Path, str],
    path_to_tree: dict[Path, ast.Module],
) -> tuple[dict[str, set[str]], set[str]]:
    """Return (per-symbol imports, star-import targets).

    * ``per_symbol_imports`` maps target dotted module -> set of names
      that *some* ``src/`` file imports via ``from <target> import <name>``.
      Plain ``import X`` is intentionally NOT counted: it pins the
      module name itself, not any specific public name from ``__all__``
      (the module-level gate already covers module-level use).
    * ``star_targets`` is the set of modules wildcard-imported via
      ``from X import *`` somewhere in ``src/``. A wildcard import
      satisfies every name in the target's ``__all__``.

    Detector (e) -- first-party dynamic (call-bound) module access
    (:func:`_record_dynamic_call_accessor_edges`, IC-01 / FR-001 / FR-002 /
    #2559) is folded in here (WP05 / FR-002): the production
    offender/stale ratchet now sees ``factory().attr`` /
    ``bound = factory(); bound.attr`` dynamic-access edges, which is what
    lets the 4 ``runtime.next.runtime_bridge`` façade rows of the former
    runtime-bridge compat-surface allowlist category be recognised live
    WITHOUT a permanent allowlist entry (see the WP05 row removal + this
    wiring landing in the same commit, NFR-001 safety ordering).
    """
    per_symbol: dict[str, set[str]] = {}
    star_targets: set[str] = set()
    # The set of REAL src modules. Attribute/getattr/facade detectors only
    # record an edge when the alias resolves to a member of this set, so a
    # symbol-path collision (``from M import Cls as C; C.NAME``) cannot
    # re-blind the gate (T004 / no-false-negative). See
    # ``_record_module_attr_edges``.
    known_modules = frozenset(path_to_dotted.values())
    for path, tree in path_to_tree.items():
        containing = _package_of(path)
        alias_map, str_consts = _build_alias_map_and_consts(tree, containing)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                target = _resolve_import_from(node, containing)
                for alias in node.names:
                    if alias.name == "*":
                        star_targets.add(target)
                    else:
                        per_symbol.setdefault(target, set()).add(alias.name)
        _record_module_attr_edges(tree, alias_map, per_symbol, known_modules)
        _record_getattr_str_edges(tree, alias_map, per_symbol, known_modules)
        _record_facade_edges(tree, containing, str_consts, per_symbol, known_modules)
    _record_dynamic_call_accessor_edges(path_to_dotted, path_to_tree, per_symbol)
    return per_symbol, star_targets


def _record_dynamic_call_accessor_edges(
    path_to_dotted: dict[Path, str],
    path_to_tree: dict[Path, ast.Module],
    per_symbol: dict[str, set[str]],
) -> None:
    """Overlay detector (e) -- first-party dynamic (call-bound) module access
    (IC-01 / FR-001 / FR-002 / #2559) -- on top of an existing ``per_symbol``
    map.

    Folded into :func:`_imports_by_target` proper as of WP05 (FR-002): the
    4 ``runtime.next.runtime_bridge`` façade rows previously hand-carried in
    the runtime-bridge compat-surface allowlist category are removed in the
    same commit that wires this call in, so the production
    offender/stale ratchet and the allowlist-row removal land
    atomically (NFR-001 safety ordering -- removing the rows without this
    wiring would red the offenders check; wiring this in without removing
    the rows would red the stale-allowlist check). Kept as a separate
    function (rather than inlined) because it is independently exercised by
    ``test_wp01_runtime_bridge_facade_symbols_recognised_live_without_allowlist``
    against the real live corpus.
    """
    known_modules = frozenset(path_to_dotted.values())
    for path, tree in path_to_tree.items():
        containing = _package_of(path)
        alias_map, str_consts = _build_alias_map_and_consts(tree, containing)
        factories = find_module_factory_functions(tree, alias_map, str_consts, containing, known_modules, _resolve_relative_module)
        if not factories:
            continue
        merged_alias_map = {**alias_map, **bind_call_accessor_aliases(tree, factories)}
        _record_module_attr_edges(tree, merged_alias_map, per_symbol, known_modules)
        record_call_chain_attr_edges(tree, factories, per_symbol)


def _symbol_has_caller(
    name: str,
    mod_dotted: str,
    per_symbol: Mapping[str, AbstractSet[str]],
    submodule_prefixes: Mapping[str, list[str]],
) -> bool:
    """Return True iff *name* (declared in ``mod_dotted.__all__``) has a caller.

    A symbol is "called" if any ``from <X> import <name>`` site in ``src/``
    targets:

    * the declaring module itself (``X == mod_dotted``);
    * the declaring module's parent package (``X == parent(mod_dotted)``)
      -- the parent re-exports the name via its own ``__all__``;
    * any submodule of ``mod_dotted`` (``X.startswith(mod_dotted + ".")``)
      -- this covers package ``__init__.py`` re-exports: a name listed
      in ``charter.__all__`` and imported via ``charter.activation.compiler``
      proves the symbol is live runtime code.

    The third rule is necessary because the WP08 anti-pattern we gate
    against is *symbol with zero callers anywhere*, not *symbol unused
    via this exact import path*. Re-export contracts are honoured by
    proof-of-life from any importer of the canonical implementation.
    """
    # Direct: from mod_dotted import name
    if name in per_symbol.get(mod_dotted, set()):
        return True
    # Re-export via parent package
    if "." in mod_dotted:
        parent = mod_dotted.rsplit(".", 1)[0]
        if name in per_symbol.get(parent, set()):
            return True
    # Re-export via any submodule (covers package __init__ re-exports
    # where the canonical home is a submodule that callers import from
    # directly).
    return any(name in per_symbol.get(sub, set()) for sub in submodule_prefixes.get(mod_dotted, ()))


def _submodule_index(per_symbol: Mapping[str, AbstractSet[str]]) -> dict[str, list[str]]:
    """Build ``{prefix: [submodule, ...]}`` for fast submodule lookups.

    Used by ``_symbol_has_caller`` to honour re-export proof-of-life.
    """
    out: dict[str, list[str]] = {}
    for target in per_symbol:
        if "." not in target:
            continue
        parts = target.split(".")
        for i in range(1, len(parts)):
            prefix = ".".join(parts[:i])
            out.setdefault(prefix, []).append(target)
    return out


def _resolve_final_key(
    name: str,
    mod_dotted: str,
    module: CorpusModule | None,
    corpus: Mapping[str, CorpusModule],
    collision_index: Mapping[str, list[Location]],
) -> SymbolKey | None:
    """Resolve *name* (declared in ``mod_dotted``'s ``__all__``) to its FINAL
    (tier-assigned) :class:`SymbolKey` against the live corpus + collision
    index (relocation-hardened-dead-code-scanners-01KX958P WP02 T009/T012 --
    FR-005/FR-009).

    Returns ``None`` -- fail-closed (T006/FR-009) -- whenever the symbol is
    un-keyable OR its content key resolves to a live collision that
    ``module_path`` cannot disambiguate. A ``None`` result is NEVER treated
    as a silent exemption by callers; it always falls through to the
    caller-detection / offender path ([[no_legacy_resolver_paths]]).
    """
    if module is None:
        return None
    key = resolve_symbol_key(name, mod_dotted, module, corpus=corpus)
    return key_tier(key, mod_dotted, collision_index)


def _is_registered_migration_class(mod_dotted: str, name: str, tree: ast.Module) -> bool:
    """T013 auto-exempt: a class decorated with ``@MigrationRegistry.register``.

    Migration classes are loaded via runtime discovery (``MigrationRegistry``
    auto-discovery over ``upgrade/migrations/m_*.py``), never via a direct
    ``from module import Name`` -- a genuinely-wired migration class has zero
    direct-import callers BY DESIGN, not because it is dead. Scoped to the
    CLASS only (FR-010 / DoD e): a dead helper or constant elsewhere in the
    same ``m_*.py`` file is NOT covered by this check and stays caught.
    """
    if not mod_dotted.startswith("specify_cli.upgrade.migrations."):
        return False
    for node in tree.body:
        if not (isinstance(node, ast.ClassDef) and node.name == name):
            continue
        for dec in node.decorator_list:
            if isinstance(dec, ast.Attribute) and dec.attr == "register" and isinstance(dec.value, ast.Name) and dec.value.id == "MigrationRegistry":
                return True
    return False


def _is_typer_subapp_definition(name: str, tree: ast.Module) -> bool:
    """T013 auto-exempt: a module-level ``NAME = typer.Typer(...)`` definition.

    A Typer sub-app is normally consumed by its parent via
    ``parent_app.add_typer(mod.NAME)`` -- a module-attribute CALL pattern
    already rescued by detector (a) wherever a caller is present. This
    structural, definition-shape check covers the residual case where no
    detector (a) caller has (yet) been recorded.
    """
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            continue
        value = node.value
        return (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Attribute)
            and value.func.attr == "Typer"
            and isinstance(value.func.value, ast.Name)
            and value.func.value.id == "typer"
        )
    return False


def _is_typer_command_definition(name: str, tree: ast.Module) -> bool:
    """T013 auto-exempt (#470): a function decorated with ``@X.command(...)``
    or ``@X.callback(...)``.

    A Typer command/callback function is dispatched only through the Typer
    CLI framework's decorator-driven registration, never via a direct
    ``from module import Name`` -- the same reasoning as
    :func:`_is_typer_subapp_definition`, extended to the command function
    itself. Introduced because the #470 widened walk now includes every
    public module-level ``def``, not only ``__all__`` members, and CLI
    command functions are overwhelmingly public-but-`__all__`-absent.
    """
    for node in tree.body:
        if not (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name):
            continue
        for dec in node.decorator_list:
            target = dec.func if isinstance(dec, ast.Call) else dec
            if isinstance(target, ast.Attribute) and target.attr in ("command", "callback"):
                return True
    return False


def _reexport_origin(tree: ast.Module, containing_pkg: str, name: str) -> tuple[str, str] | None:
    """Return ``(origin_module, origin_name)`` for a single-alias ``ImportFrom``
    binding *name*, or ``None`` if *name* is not a simple re-export.

    Used only by :func:`_is_reexport_shim_symbol` (T013) to trace a re-export
    to its origin so the origin's OWN caller graph can be consulted.
    """
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        target = _resolve_import_from(node, containing_pkg)
        for alias in node.names:
            if alias.name == "*":
                continue
            bound = alias.asname or alias.name
            if bound == name:
                return target, alias.name
    return None


def _is_reexport_shim_symbol(
    mod_dotted: str,
    name: str,
    module: CorpusModule,
    final_key: SymbolKey | None,
    per_symbol: Mapping[str, AbstractSet[str]],
    submodule_index: Mapping[str, list[str]],
) -> bool:
    """T013 auto-exempt: a pure re-export whose UNDERLYING definition has a
    live caller elsewhere (just not via THIS shim's own import path).

    Requires ALL of:

    1. ``final_key`` is a plain CONTENT-tier key (``module_path is None``).
       A collision bare_name (escalated tier, or fail-closed ``None``) is
       NEVER auto-exempt -- it MUST be hand-curated so the FR-005 live
       classifier's escalate-or-fail-close path (T012) stays the only route
       to exempting a same-name collision. This is load-bearing: without
       it, a future GateDecision-collapse-style rogue same-name sibling
       could be silently swallowed by this structural check instead of
       being caught by the escalation logic (DoD i).
    2. ``name`` has no local definition in this module (it is imported, not
       defined -- ``definition_span`` returns ``None``).
    3. The single-alias ``ImportFrom`` resolves to an ORIGIN module/name
       that has a REAL caller elsewhere in the corpus (``_symbol_has_caller``
       on the origin, not this shim). This is what distinguishes "compat
       shim re-exporting something already proven live" from "genuinely
       dead symbol that also happens to be re-exported nowhere else" --
       the latter must stay caught (FR-013 (c)/(e)).
    """
    if final_key is None or final_key.module_path is not None:
        return False
    if definition_span(module.tree, name) is not None:
        return False
    origin = _reexport_origin(module.tree, module.containing_pkg, name)
    if origin is None:
        return False
    origin_module, origin_name = origin
    if origin_module == mod_dotted:
        return False
    return _symbol_has_caller(origin_name, origin_module, per_symbol, submodule_index)


def _is_auto_exempt(
    mod_dotted: str,
    name: str,
    module: CorpusModule | None,
    final_key: SymbolKey | None,
    per_symbol: Mapping[str, AbstractSet[str]],
    submodule_index: Mapping[str, list[str]],
) -> bool:
    """T013 -- symbol-granular auto-derived exemptions (never per-module).

    Four structural categories (FR-010; the fourth added by #470), checked
    in order: a registered ``@MigrationRegistry.register`` class, a Typer
    sub-app definition, a Typer ``@X.command``/``@X.callback`` function, or
    a re-export shim whose underlying symbol is proven live elsewhere. See
    ``test_auto_exempt_disjoint_from_hand_allowlist`` for the disjointness
    proof against the allowlist's ``entries`` (auto_exempt ∩ hand_allowlist
    = ∅); an overlapping entry is also reported stale SUPERSEDED.
    """
    if module is None:
        return False
    tree = module.tree
    if _is_registered_migration_class(mod_dotted, name, tree):
        return True
    if _is_typer_subapp_definition(name, tree):
        return True
    if _is_typer_command_definition(name, tree):
        return True
    return _is_reexport_shim_symbol(mod_dotted, name, module, final_key, per_symbol, submodule_index)


def _compute_offenders(
    decls: Mapping[str, frozenset[str]],
    per_symbol: Mapping[str, AbstractSet[str]],
    star_targets: AbstractSet[str],
    allowlist: AbstractSet[DeadSymbolKey],
    corpus: Mapping[str, CorpusModule],
    collision_index: Mapping[str, list[Location]],
) -> list[str]:
    """Return ``module::Name`` offenders for the symbol-level gate, ordered by module, then name.

    Extracted so the end-to-end "teeth" self-test
    (``test_gate_still_flags_a_truly_dead_symbol``) drives a constructed
    dead-symbol fixture through the *exact* aggregate path the real gate
    uses — proving the four additive caller-detectors did not turn the gate
    into a silent no-op (NFR-001 / gate-can't-self-validate).

    A declared name is exempt, in this order: (1) its ``(module, name)`` key
    is in ``allowlist`` AND the name is keyable -- :func:`_resolve_final_key`
    is not ``None`` (G1: an un-keyable name such as ``__all__ = ['Ghost']``
    is never exempted, fail-closed); else (2) it matches a T013 structural
    auto-exempt category (:func:`_is_auto_exempt`); else (3) it has a caller
    (the existing caller-detection path, unchanged). Otherwise it is an
    offender.
    """
    submodule_index = _submodule_index(per_symbol)
    offenders: list[str] = []
    for mod_dotted, names in sorted(decls.items()):
        if mod_dotted in star_targets:
            # Star-imported elsewhere; ``__all__`` is consumed wholesale.
            continue
        module = corpus.get(mod_dotted)
        for name in sorted(names):
            qualified = f"{mod_dotted}::{name}"
            final_key = _resolve_final_key(name, mod_dotted, module, corpus, collision_index)
            if final_key is not None and DeadSymbolKey(mod_dotted, name) in allowlist:
                continue
            if _is_auto_exempt(mod_dotted, name, module, final_key, per_symbol, submodule_index):
                continue
            if _symbol_has_caller(name, mod_dotted, per_symbol, submodule_index):
                continue
            offenders.append(qualified)
    return offenders


# ---------------------------------------------------------------------------
# The evaluation seam (FR-009): one real-tree walk, one allowlist evaluation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RealTreeInputs:
    """Everything the gate derives from one walk of ``src/``, as read-only views.

    Built once per file by :func:`_real_tree_inputs` (cleared at file end by
    ``_clear_real_tree_inputs``) and shared by every real-tree test in this file. The mappings are ``MappingProxyType`` views
    and the caller sets are frozensets, so no test can mutate the cached walk
    (adding a caller to ``per_symbol`` would silently rescue dead symbols for
    every later real-tree test on the same worker). The collision-index
    values stay lists because ``key_tier`` is typed on lists; nothing here
    writes to them.
    """

    decls: Mapping[str, frozenset[str]]
    all_literal_decls: Mapping[str, frozenset[str]]
    corpus: Mapping[str, CorpusModule]
    per_symbol: Mapping[str, frozenset[str]]
    star_targets: frozenset[str]
    collision_index: Mapping[str, list[Location]]


@functools.lru_cache(maxsize=1)
def _real_tree_inputs() -> RealTreeInputs:
    """Walk ``src/`` once per file and return the read-only :class:`RealTreeInputs`.

    The result keeps every ``src/`` syntax tree and its source resident -- the
    one reasoned exception to "caches hold findings, not trees" (FR-006). It is
    bounded to this file: ``_clear_real_tree_inputs`` clears it at module teardown.

    Never monkeypatch the walker and then call this: the cache would either
    serve the full tree (a false green) or keep the partial tree for the real
    gate. Drive synthetic inputs through the pure helpers instead.
    """
    decls, all_literal_decls, path_to_dotted, path_to_tree, corpus = _walk_modules()
    per_symbol, star_targets = _imports_by_target(path_to_dotted, path_to_tree)
    return RealTreeInputs(
        decls=MappingProxyType(decls),
        all_literal_decls=MappingProxyType(all_literal_decls),
        corpus=MappingProxyType(corpus),
        per_symbol=MappingProxyType({target: frozenset(names) for target, names in per_symbol.items()}),
        star_targets=frozenset(star_targets),
        collision_index=MappingProxyType(classify_collisions(corpus)),
    )


def _release_real_tree_inputs() -> None:
    """Drop the real-tree inputs (trees + source of all of ``src/``) when this file finishes (FR-006)."""
    _real_tree_inputs.cache_clear()  # module global, resolved at CALL time


@pytest.fixture(autouse=True, scope="module")
def _clear_real_tree_inputs() -> Iterator[None]:
    """Release the cached ``src/`` walk at file end so no syntax tree outlives its file."""
    yield
    _release_real_tree_inputs()


@dataclass(frozen=True)
class StaleFinding:
    """One allowlist entry that no longer earns its place, with its single verdict."""

    key: DeadSymbolKey
    verdict: StaleVerdict
    hint: str

    def render(self) -> str:
        """``module::name [VERDICT] hint``, the form the gate prints."""
        return f"{self.key} [{self.verdict}] {self.hint}".rstrip()


@dataclass(frozen=True)
class AllowlistEvaluation:
    """The ``__all__``-scope result of evaluating one allowlist against one corpus.

    ``offenders`` is sorted and covers the ``__all__`` scope only (the #470
    widened scope is :func:`_evaluate_widened`'s). ``stale`` is ordered by
    ``(module, name)``.
    """

    offenders: list[str]
    stale: list[StaleFinding]


_HINT_INVALID = "binds nothing keyable, so the entry cannot exempt it; fix the declaration or delete the entry"
_HINT_GONE = "deleted, renamed, or dropped from `__all__`; delete the entry or update it"
_HINT_REVIVED = "the symbol has a caller again; delete the entry"
_HINT_SUPERSEDED = "a T013 structural auto-exemption now covers it; delete the entry"
_HINT_MOOT = "the module is star-imported, so the entry exempts nothing; delete the entry"

_VERDICT_HINTS: Mapping[StaleVerdict, str] = MappingProxyType(
    {
        StaleVerdict.INVALID: _HINT_INVALID,
        StaleVerdict.REVIVED: _HINT_REVIVED,
        StaleVerdict.SUPERSEDED: _HINT_SUPERSEDED,
        StaleVerdict.MOOT: _HINT_MOOT,
    }
)


@dataclass(frozen=True)
class _StaleContext:
    """The corpus-side inputs of the stale classifier, bundled once per evaluation."""

    all_literal_decls: Mapping[str, frozenset[str]]
    corpus: Mapping[str, CorpusModule]
    collision_index: Mapping[str, list[Location]]
    per_symbol: Mapping[str, AbstractSet[str]]
    submodule_index: Mapping[str, list[str]]
    star_targets: AbstractSet[str]


def _classify_entry(key: DeadSymbolKey, ctx: _StaleContext) -> StaleVerdict | None:
    """The one stale verdict for *key*, or ``None`` when the entry is live (data-model §1.5).

    The first matching rule wins: INVALID, GONE, REVIVED, SUPERSEDED, MOOT.
    """
    module = ctx.corpus.get(key.module)
    if key.name in ctx.all_literal_decls.get(key.module, frozenset()):
        final_key = _resolve_final_key(key.name, key.module, module, ctx.corpus, ctx.collision_index)
        if final_key is None:
            return StaleVerdict.INVALID
    else:
        return StaleVerdict.GONE
    if _symbol_has_caller(key.name, key.module, ctx.per_symbol, ctx.submodule_index):
        return StaleVerdict.REVIVED
    if _is_auto_exempt(key.module, key.name, module, final_key, ctx.per_symbol, ctx.submodule_index):
        return StaleVerdict.SUPERSEDED
    if key.module in ctx.star_targets:
        return StaleVerdict.MOOT
    return None


def _gone_hint(key: DeadSymbolKey, offenders: list[str]) -> str:
    """The GONE hint: name the module(s) where an offender of the same name now lives."""
    new_homes = sorted({module for module, _, name in (o.partition("::") for o in offenders) if name == key.name and module != key.module})
    if not new_homes:
        return _HINT_GONE
    candidates = " or ".join(f"`{module}`" for module in new_homes)
    return f"probably moved to {candidates}; update `module:`"


def _classify_allowlist(keys: AbstractSet[DeadSymbolKey], ctx: _StaleContext, offenders: list[str]) -> list[StaleFinding]:
    """Classify every entry; return the stale ones, ordered by ``(module, name)``."""
    findings: list[StaleFinding] = []
    for key in sorted(keys):
        verdict = _classify_entry(key, ctx)
        if verdict is None:
            continue
        hint = _gone_hint(key, offenders) if verdict is StaleVerdict.GONE else _VERDICT_HINTS[verdict]
        findings.append(StaleFinding(key=key, verdict=verdict, hint=hint))
    return findings


def _evaluate_allowlist(
    all_literal_decls: Mapping[str, frozenset[str]],
    per_symbol: Mapping[str, AbstractSet[str]],
    star_targets: AbstractSet[str],
    corpus: Mapping[str, CorpusModule],
    allowlist: DeadSymbolAllowlist,
    collision_index: Mapping[str, list[Location]] | None = None,
) -> AllowlistEvaluation:
    """Evaluate the ``__all__``-scope section of *allowlist* against one corpus.

    Runs the production :func:`_compute_offenders` over ``all_literal_decls``
    with ``allowlist.keys``, then gives every entry its stale verdict. The
    collision index is built from *corpus* when not supplied.
    """
    index = classify_collisions(corpus) if collision_index is None else collision_index
    offenders = sorted(_compute_offenders(all_literal_decls, per_symbol, star_targets, allowlist.keys, corpus, index))
    ctx = _StaleContext(
        all_literal_decls=all_literal_decls,
        corpus=corpus,
        collision_index=index,
        per_symbol=per_symbol,
        submodule_index=_submodule_index(per_symbol),
        star_targets=star_targets,
    )
    return AllowlistEvaluation(offenders=offenders, stale=_classify_allowlist(allowlist.keys, ctx, offenders))


def _corpus_floor_shortfall(all_literal_decls: Mapping[str, frozenset[str]]) -> list[str]:
    """Every §2.1 non-vacuity floor the scanned corpus misses (empty when both hold)."""
    names = sum(len(declared) for declared in all_literal_decls.values())
    modules = len(all_literal_decls)
    shortfall: list[str] = []
    if names < _CORPUS_FLOOR_NAMES:
        shortfall.append(f"only {names} `__all__` names scanned (floor {_CORPUS_FLOOR_NAMES})")
    if modules < _CORPUS_FLOOR_MODULES:
        shortfall.append(f"only {modules} `__all__`-declaring modules scanned (floor {_CORPUS_FLOOR_MODULES})")
    return shortfall


# The #470 widened-scope grandfather list is the ``widened_grandfathered_470``
# section of ``dead_symbol_allowlist.yaml``: pre-existing debt the widened walk
# surfaced, one ``module::Name`` per entry, each to be wired into ``__all__``
# plus a real caller, or deleted, in follow-up triage issue #633. It is
# evaluated separately from the ``__all__``-scope ``entries`` (see
# :func:`_evaluate_widened`): a widened name is only ever rescued by a T013
# auto-exemption, a real caller, an intra-module reference or this list, never
# by an ``entries`` key. Each entry must still earn its place:
# :func:`_compute_widened_stale` (dead-code review 2026-09-30) fails the gate
# when an entry gains a caller, moves into ``__all__``, stops being declared,
# or is already rescued by an intra-module reference.


def _apply_widened_scope_exemptions(
    offenders: list[str],
    all_literal_decls: Mapping[str, frozenset[str]],
    corpus: Mapping[str, CorpusModule],
    grandfathered: AbstractSet[str],
) -> list[str]:
    """Drop rescued widened-in (non-``__all__``) offenders (#470).

    An ``__all__`` member is passed through unchanged -- membership in
    ``__all__`` is itself a claim of a cross-module export contract, so the
    original strict caller-only semantics stay exactly as they were before
    #470. A non-``__all__`` offender (only reachable here because the walk
    now covers every public module-level name) is dropped iff it is either
    (a) referenced anywhere within its own module (:func:`_used_within_own_module`
    -- module-private-by-convention names, e.g. a module ``logger``, are not
    "dead", just never exported), or (b) listed in *grandfathered*, the
    pre-existing debt this widening surfaced pending individual follow-up
    triage (the gate passes the widened section of the allowlist it evaluates).
    """
    kept: list[str] = []
    for qualified in offenders:
        mod_dotted, _, name = qualified.partition("::")
        if name in all_literal_decls.get(mod_dotted, frozenset()):
            kept.append(qualified)
            continue
        module = corpus.get(mod_dotted)
        if module is not None and _used_within_own_module(module.tree, name):
            continue
        if qualified in grandfathered:
            continue
        kept.append(qualified)
    return kept


def _compute_widened_stale(
    grandfathered: AbstractSet[str],
    pre_rescue_widened_offenders: list[str],
    corpus: Mapping[str, CorpusModule],
) -> list[str]:
    """Return every widened grandfather entry that no longer earns its place.

    An entry is stale when the widened-only offender pass no longer reports it
    (it gained a caller, moved into ``__all__``, or is no longer declared), or
    when the intra-module rescue already exempts it. Either way the grandfather
    entry rescues nothing, and leaving it in place would silently re-admit the
    name if it went dead again.
    """
    reported = set(pre_rescue_widened_offenders)
    stale: list[str] = []
    for qualified in sorted(grandfathered):
        if qualified not in reported:
            stale.append(f"{qualified} (no longer a widened offender)")
            continue
        mod_dotted, _, name = qualified.partition("::")
        module = corpus.get(mod_dotted)
        if module is not None and _used_within_own_module(module.tree, name):
            stale.append(f"{qualified} (already rescued: used within its own module)")
    return stale


def _evaluate_widened(
    decls: Mapping[str, frozenset[str]],
    all_literal_decls: Mapping[str, frozenset[str]],
    per_symbol: Mapping[str, AbstractSet[str]],
    star_targets: AbstractSet[str],
    corpus: Mapping[str, CorpusModule],
    collision_index: Mapping[str, list[Location]],
    grandfathered: AbstractSet[str],
) -> tuple[list[str], list[str]]:
    """The #470 widened-only pass: ``(post-rescue widened offenders, widened stale)``.

    The widened (non-``__all__``) names are run through the production
    :func:`_compute_offenders` against an EMPTY allowlist, so they can only
    be rescued by a T013 auto-exemption or a real caller -- never by an
    ``entries`` key -- and then through the #470 rescue with *grandfathered*,
    the widened section of the allowlist being evaluated.
    """
    widened_only_decls = {mod: leftover for mod, names in decls.items() if (leftover := names - all_literal_decls.get(mod, frozenset()))}
    pre_rescue_widened_offenders = _compute_offenders(widened_only_decls, per_symbol, star_targets, frozenset(), corpus, collision_index)
    # #470 mutation-proofing (squad pass 2, sk-squad-spec-kitty-638): this is
    # the LIVE widened-only offender pass, not a hand-built copy of it -- the
    # assertion below proves this exact call is load-bearing. Replacing the
    # `pre_rescue_widened_offenders` call above with a no-op leaves every
    # other test in this file passing, because the live tree happens to have
    # no *new* offenders either way. A known grandfathered entry is
    # dead-with-no-caller by construction (that's why it needed
    # grandfathering), so it must show up here, pre-rescue -- if it stops
    # showing up, either this pass was unwired or the entry gained a real
    # caller and should be pruned (#633 triage).
    assert any(o in grandfathered for o in pre_rescue_widened_offenders), (
        "the widened-only _compute_offenders pass found none of the known "
        "widened_grandfathered_470 entries as pre-rescue offenders -- "
        "either that pass has been unwired from the live gate, or every "
        "grandfathered entry has since gained a real caller and should be "
        "pruned (#633)"
    )
    widened_stale = _compute_widened_stale(grandfathered, pre_rescue_widened_offenders, corpus)
    return _apply_widened_scope_exemptions(pre_rescue_widened_offenders, all_literal_decls, corpus, grandfathered), widened_stale


_ALLOWLIST_FILE_REF = "`tests/architectural/dead_symbol_allowlist.yaml`"
_BULLET = "\n  - "


def _offender_message(offenders: list[str]) -> str:
    """The failure text for new offenders, with the fix options in order of preference."""
    return (
        "Symbol-level dead-code gate FAILED (#470: scope is __all__ UNION "
        "every public module-level name). The following public symbols "
        "have no other src/ caller, no intra-module reference, and no "
        "T013 structural auto-exemption:" + _BULLET + _BULLET.join(offenders) + "\n\nFix options (in order of preference):\n"
        "  1) Wire the symbol from a runtime caller.\n"
        "  2) If declared in __all__, remove it from __all__ (it stays "
        "in the module as an unexported internal) -- otherwise, if it "
        "is a widened-in (non-__all__) name, mark it underscore-private.\n"
        "  3) Delete the symbol entirely if it is truly dead.\n"
        f"  4) If declared in __all__, add a `(module, name)` entry to {_ALLOWLIST_FILE_REF} "
        "with category and rationale (and issue where the category requires it). "
        "If it is a widened-in (non-__all__) name, add it to that file's "
        "`widened_grandfathered_470` section instead (FR-303).\n"
    )


def _stale_message(stale: list[StaleFinding]) -> str:
    """The failure text for stale ``__all__``-scope entries, one rendered verdict per line."""
    return (
        f"Stale `entries` in {_ALLOWLIST_FILE_REF} detected. Each entry below no longer "
        "earns its place (verdict and fix hint per line):" + _BULLET + _BULLET.join(finding.render() for finding in stale)
    )


def _widened_stale_message(widened_stale: list[str]) -> str:
    """The failure text for stale widened grandfather entries."""
    return (
        f"Stale `widened_grandfathered_470` entries in {_ALLOWLIST_FILE_REF} detected. "
        "The following grandfathered names no longer need the exemption and "
        "must be removed from the section:" + _BULLET + _BULLET.join(widened_stale)
    )


def _gate_failure_messages(offenders: list[str], stale: list[StaleFinding], widened_stale: list[str]) -> list[str]:
    """Build one message per failing ratchet direction (empty when the gate is green)."""
    messages: list[str] = []
    if offenders:
        messages.append(_offender_message(offenders))
    if stale:
        messages.append(_stale_message(stale))
    if widened_stale:
        messages.append(_widened_stale_message(widened_stale))
    return messages


def test_no_public_symbol_in_all_is_unimported() -> None:
    """Every public module-level name must have at least one caller in src/
    (#470: widened beyond ``__all__`` -- see the module docstring's "Scope"
    section).

    Failure means a public symbol is declared but no other ``src/`` file
    imports it, and it is not rescued by an intra-module reference, a T013
    structural auto-exemption, or the allowlist; or an allowlist entry (either
    section) no longer earns its place. That's the WP08 cycle-1 "library
    written but never wired" failure mode at symbol level.

    Both allowlist sections come from ONE parsed ``DeadSymbolAllowlist``.
    """
    inputs = _real_tree_inputs()
    floor_shortfall = _corpus_floor_shortfall(inputs.all_literal_decls)
    assert not floor_shortfall, "the dead-symbol gate scanned too little of src/ to be meaningful (§2.1 floor): " + "; ".join(floor_shortfall)

    allowlist = ALLOWLIST
    evaluation = _evaluate_allowlist(
        inputs.all_literal_decls,
        inputs.per_symbol,
        inputs.star_targets,
        inputs.corpus,
        allowlist,
        inputs.collision_index,
    )
    widened_offenders, widened_stale = _evaluate_widened(
        inputs.decls,
        inputs.all_literal_decls,
        inputs.per_symbol,
        inputs.star_targets,
        inputs.corpus,
        inputs.collision_index,
        allowlist.widened_qualified,
    )

    messages = _gate_failure_messages(sorted(evaluation.offenders + widened_offenders), evaluation.stale, widened_stale)
    assert not messages, "\n\n".join(messages)


# ---------------------------------------------------------------------------
# #470 mutation-proofing — the widening's own rescue/detection mechanism has
# to be able to fail. Found by squad review of #470 (spec-kitty#638):
# `_used_within_own_module` mutated to an unconditional `return True`, or
# `_extract_public_module_level_names` mutated to an unconditional
# `return frozenset()`, left every test in this file passing. Each helper
# below gets a synthetic-fixture unit test, plus a sibling to
# `test_no_public_symbol_in_all_is_unimported` that proves the widened scan
# actually finds and flags a synthetic zero-caller widened-in name.
# ---------------------------------------------------------------------------


def test_extract_public_module_level_names_scoping() -> None:
    """Unit test for `_extract_public_module_level_names` (#470 mutation-proofing).

    Module-level public `def`/`class`/`Assign`/`AnnAssign` `Name` targets are
    collected; underscore-prefixed names, names nested inside a function or
    class body, and non-`Name` assignment targets (tuple/attribute) are all
    excluded.
    """
    source = (
        "def public_func():\n"
        "    def _nested_helper():\n"
        "        pass\n"
        "    inner_var = 1\n"
        "    return inner_var\n"
        "\n"
        "\n"
        "class PublicClass:\n"
        "    def method(self):\n"
        "        pass\n"
        "\n"
        "\n"
        "def _private_func():\n"
        "    pass\n"
        "\n"
        "\n"
        "PUBLIC_CONST = 1\n"
        "_PRIVATE_CONST = 2\n"
        "PUBLIC_ANN: int = 3\n"
        "a, b = (1, 2)\n"
        "obj.attr = 4\n"
    )
    tree = ast.parse(source)
    names = _extract_public_module_level_names(tree)
    assert names == frozenset({"public_func", "PublicClass", "PUBLIC_CONST", "PUBLIC_ANN"}), f"got {sorted(names)!r}"

    # The mutation the squad demonstrated: collapsing the whole widening to
    # an unconditional empty set. A real implementation must never do this.
    assert _extract_public_module_level_names(ast.parse("")) == frozenset()
    assert names != frozenset(), "the widening must surface at least one public module-level name from a non-empty module"


def test_used_within_own_module() -> None:
    """Unit test for `_used_within_own_module` (#470 mutation-proofing).

    True iff *name* is referenced as an ``ast.Name`` Load that can resolve to
    the module-level binding. A Store-only reference, no reference at all, or
    a load shadowed by a local binding in an enclosing function or class
    body scope must return False -- the mutation the squad demonstrated (an unconditional
    `return True`) would rescue every widened-in offender regardless of real
    intra-module use.
    """
    referenced_tree = ast.parse("logger = get_logger()\ndef use():\n    return logger\n")
    unreferenced_tree = ast.parse("logger = get_logger()\n")
    local_shadow_tree = ast.parse("logger = get_logger()\ndef use():\n    logger = logging.getLogger(__name__)\n    return logger\n")
    parameter_shadow_tree = ast.parse("logger = get_logger()\ndef use(logger):\n    return logger\n")
    nested_shadow_tree = ast.parse(
        "logger = get_logger()\ndef outer():\n    logger = logging.getLogger(__name__)\n    def inner():\n        return logger\n    return inner\n"
    )
    comprehension_shadow_tree = ast.parse("logger = get_logger()\nvalues = [logger for logger in loggers]\n")
    class_shadow_tree = ast.parse("logger = get_logger()\nclass Runner:\n    logger = logging.getLogger(__name__)\n    uses = logger\n")
    class_pre_binding_tree = ast.parse("logger = get_logger()\nclass Runner:\n    uses = logger\n    logger = logging.getLogger(__name__)\n")
    class_method_tree = ast.parse("logger = get_logger()\nclass Runner:\n    logger = logging.getLogger(__name__)\n    def use(self):\n        return logger\n")
    assert _used_within_own_module(referenced_tree, "logger") is True
    assert _used_within_own_module(unreferenced_tree, "logger") is False
    assert _used_within_own_module(local_shadow_tree, "logger") is False
    assert _used_within_own_module(parameter_shadow_tree, "logger") is False
    assert _used_within_own_module(nested_shadow_tree, "logger") is False
    assert _used_within_own_module(comprehension_shadow_tree, "logger") is False
    assert _used_within_own_module(class_shadow_tree, "logger") is False
    assert _used_within_own_module(class_pre_binding_tree, "logger") is True
    assert _used_within_own_module(class_method_tree, "logger") is True
    assert _used_within_own_module(unreferenced_tree, "nonexistent_name") is False


def test_apply_widened_scope_exemptions() -> None:
    """Unit test for `_apply_widened_scope_exemptions` (#470 mutation-proofing).

    Covers all rescue paths plus the "still caught" controls: an ``__all__``
    member stays caught even when only referenced within its own module
    (unchanged pre-#470 semantics); a non-``__all__`` name referenced within
    its own module is rescued; a real ``_WIDENED_SCOPE_GRANDFATHERED_470``
    entry is rescued when its module is absent from ``corpus`` (so the
    intra-module check cannot mask which rescue actually fired); and a
    non-``__all__`` name with neither rescue stays caught.
    """
    all_member_source = "__all__ = ['AllMember']\nAllMember = 1\ndef use():\n    return AllMember\n"
    all_member_tree = ast.parse(all_member_source)
    all_member_module = CorpusModule(tree=all_member_tree, source=all_member_source, containing_pkg="synthetic")

    intra_used_source = "helper = 1\ndef use():\n    return helper\n"
    intra_used_tree = ast.parse(intra_used_source)
    intra_used_module = CorpusModule(tree=intra_used_tree, source=intra_used_source, containing_pkg="synthetic")

    truly_dead_source = "truly_dead = 1\n"
    truly_dead_tree = ast.parse(truly_dead_source)
    truly_dead_module = CorpusModule(tree=truly_dead_tree, source=truly_dead_source, containing_pkg="synthetic")

    corpus = {
        "synthetic.all_mod": all_member_module,
        "synthetic.intra_mod": intra_used_module,
        "synthetic.dead_mod": truly_dead_module,
        # deliberately no entry for the grandfathered module -- the rescue
        # must fire from the flat name set alone, never the intra-module path.
    }
    all_literal_decls = {"synthetic.all_mod": frozenset({"AllMember"})}

    grandfathered_qualified = next(iter(_WIDENED_SCOPE_GRANDFATHERED_470))
    offenders = [
        "synthetic.all_mod::AllMember",
        "synthetic.intra_mod::helper",
        grandfathered_qualified,
        "synthetic.dead_mod::truly_dead",
    ]
    kept = _apply_widened_scope_exemptions(offenders, all_literal_decls, corpus, _WIDENED_SCOPE_GRANDFATHERED_470)
    assert kept == ["synthetic.all_mod::AllMember", "synthetic.dead_mod::truly_dead"], f"got {kept!r}"


def test_compute_widened_stale() -> None:
    """Unit test for `_compute_widened_stale`, the per-entry grandfather ratchet.

    A grandfathered name that the widened pass still reports and nothing else
    rescues is kept. One the pass no longer reports (it gained a caller) is
    stale, and so is one the intra-module rescue already exempts.
    """
    dead_source = "still_dead = 1\n"
    intra_source = "helper = 1\ndef use():\n    return helper\n"
    corpus = {
        "synthetic.dead_mod": CorpusModule(tree=ast.parse(dead_source), source=dead_source, containing_pkg="synthetic"),
        "synthetic.intra_mod": CorpusModule(tree=ast.parse(intra_source), source=intra_source, containing_pkg="synthetic"),
    }
    grandfathered = frozenset({"synthetic.dead_mod::still_dead", "synthetic.intra_mod::helper", "synthetic.wired_mod::now_wired"})
    reported = ["synthetic.dead_mod::still_dead", "synthetic.intra_mod::helper"]
    stale = _compute_widened_stale(grandfathered, reported, corpus)
    assert stale == [
        "synthetic.intra_mod::helper (already rescued: used within its own module)",
        "synthetic.wired_mod::now_wired (no longer a widened offender)",
    ], f"got {stale!r}"


def test_widened_scope_flags_synthetic_zero_caller_symbol() -> None:
    """Sibling to `test_no_public_symbol_in_all_is_unimported` (#470 mutation-proofing).

    Drives a synthetic module through the exact `_extract_public_module_level_names`
    -> widened-``decls`` -> `_compute_offenders` -> `_apply_widened_scope_exemptions`
    pipeline the production gate uses on ``_walk_modules``'s output, with a
    public module-level name that has no ``__all__`` entry, no caller, and no
    intra-module reference -- and asserts the widened scan actually finds and
    flags it. `test_no_public_symbol_in_all_is_unimported` alone only fails on
    *new* live-tree offenders; it has no assertion that the widened scan finds
    anything at all, which is exactly how the squad's two mutations (collapsing
    `_extract_public_module_level_names` to `frozenset()`, or
    `_used_within_own_module` to unconditional `True`) passed every test here.
    """
    source = "def orphan_widened_helper():\n    return 1\n"
    tree = ast.parse(source)
    module = CorpusModule(tree=tree, source=source, containing_pkg="synthetic")
    corpus = {"synthetic.widened_mod": module}
    collision_index = classify_collisions(corpus)

    all_literal = _extract_all_literal(tree) or frozenset()
    widened = all_literal | _extract_public_module_level_names(tree)
    assert "orphan_widened_helper" in widened, "sanity: the widening must surface the synthetic public name"

    decls = {"synthetic.widened_mod": widened}
    all_literal_decls: dict[str, frozenset[str]] = {}
    widened_only_decls = {mod: leftover for mod, names in decls.items() if (leftover := names - all_literal_decls.get(mod, frozenset()))}

    offenders = _compute_offenders(widened_only_decls, {}, set(), frozenset(), corpus, collision_index)
    offenders = _apply_widened_scope_exemptions(offenders, all_literal_decls, corpus, _WIDENED_SCOPE_GRANDFATHERED_470)

    assert offenders == ["synthetic.widened_mod::orphan_widened_helper"], (
        f"the widened scan must flag a zero-caller, unreferenced, non-grandfathered widened-in name; got {offenders!r}"
    )


def test_walk_modules_widening_contributes_on_live_tree() -> None:
    """`_walk_modules()`'s LIVE wiring must actually widen `decls` past
    `all_literal_decls` (#470 mutation-proofing, squad pass 2 on
    sk-squad-spec-kitty-638).

    `test_widened_scope_flags_synthetic_zero_caller_symbol` above proves the
    helpers are individually correct, but only through a hand-built pipeline
    that reimplements line 2278's union itself (``widened = all_literal |
    _extract_public_module_level_names(tree)``) rather than calling
    `_walk_modules()`. A mutation to that live line (dropping the union down
    to `widened = all_literal`) leaves every other test in this file
    passing. This calls the real `_walk_modules()` and asserts the widening
    contributes at least one non-`__all__` public name somewhere on the
    actual `src/` tree.
    """
    inputs = _real_tree_inputs()  # built by the real _walk_modules(), cached once per file (G7)
    decls, all_literal_decls = inputs.decls, inputs.all_literal_decls
    widened_contribution = sum(len(decls[mod] - all_literal_decls.get(mod, frozenset())) for mod in decls)
    assert widened_contribution > 0, (
        "_walk_modules()'s live decls contained zero names beyond __all__ -- the #470 widening at line 2278 may have been unwired from the real gate"
    )


# ---------------------------------------------------------------------------
# T001 regression — _extract_all_literal parser bug fix
# ---------------------------------------------------------------------------


def test_extract_all_literal_skips_non_all_annassign() -> None:
    """A non-``__all__`` AnnAssign before ``__all__`` must not blind the parser.

    Regression for the T001 bug: a top-level ``MESSAGES: dict[...] = {...}``
    (ast.AnnAssign whose target is NOT ``__all__``) was falling through to
    ``if value is None: return frozenset()``, silently zeroing the module's
    ``__all__``.  After the fix, such nodes are skipped with ``continue``.
    """
    src = 'MESSAGES: dict[str, str] = {"x": "y"}\n__all__ = ["Foo", "Bar"]'
    tree = ast.parse(src)
    result = _extract_all_literal(tree)
    assert result == frozenset({"Foo", "Bar"}), f"Expected frozenset({{Foo, Bar}}), got {result!r}"


def test_extract_all_literal_typed_all_annassign() -> None:
    """A typed ``__all__: list[str] = [...]`` AnnAssign is parsed correctly."""
    src = '__all__: list[str] = ["Alpha", "Beta"]'
    tree = ast.parse(src)
    result = _extract_all_literal(tree)
    assert result == frozenset({"Alpha", "Beta"})


def test_extract_all_literal_bare_annassign_returns_frozenset_empty() -> None:
    """``__all__: list[str]`` with no value is treated as dynamic (frozenset())."""
    src = "__all__: list[str]"
    tree = ast.parse(src)
    result = _extract_all_literal(tree)
    assert result == frozenset()


# ---------------------------------------------------------------------------
# T004 no-false-negative guard — detectors must bind to RESOLVED module only
# ---------------------------------------------------------------------------


def test_no_false_negative_module_attr_detector() -> None:
    """Detector (a) must rescue the resolved module's symbol, not a coincidental one.

    This is the binding invariant from the WP01 spec: ``alias.Foo`` where
    ``alias`` resolves to ``other_pkg`` rescues **only** ``other_pkg::Foo``,
    NOT any different module that happens to declare a symbol named ``Foo``.
    """
    src = "import other_pkg as alias\nalias.Foo"
    tree = ast.parse(src)
    alias_map, _ = _build_alias_map_and_consts(tree, "")
    ps: dict[str, set[str]] = {}
    _record_module_attr_edges(tree, alias_map, ps, frozenset({"other_pkg"}))
    sub_idx = _submodule_index(ps)

    # The resolved module IS rescued.
    assert _symbol_has_caller("Foo", "other_pkg", ps, sub_idx), "other_pkg::Foo must be rescued by alias.Foo access"
    # A different module with the same symbol name is NOT rescued.
    assert not _symbol_has_caller("Foo", "declaring_module", ps, sub_idx), "declaring_module::Foo must NOT be rescued by alias.Foo where alias→other_pkg"


def test_no_false_negative_unaliased_submodule_attr_detector() -> None:
    """An unaliased submodule import rescues only that real submodule."""
    src = "from parent import target_mod\ntarget_mod.Bar"
    tree = ast.parse(src)
    alias_map, _ = _build_alias_map_and_consts(tree, "")
    ps: dict[str, set[str]] = {}
    _record_module_attr_edges(tree, alias_map, ps, frozenset({"parent.target_mod"}))
    sub_idx = _submodule_index(ps)

    assert _symbol_has_caller("Bar", "parent.target_mod", ps, sub_idx)

    collision_src = "from parent import SomeClass\nSomeClass.NAME"
    collision_tree = ast.parse(collision_src)
    collision_alias_map, _ = _build_alias_map_and_consts(collision_tree, "")
    collision_ps: dict[str, set[str]] = {}
    _record_module_attr_edges(collision_tree, collision_alias_map, collision_ps, frozenset({"parent"}))
    collision_sub_idx = _submodule_index(collision_ps)

    assert not _symbol_has_caller("NAME", "parent", collision_ps, collision_sub_idx)


def test_no_false_negative_getattr_detector() -> None:
    """Detector (d) must rescue the resolved module's symbol only."""
    src = "import target_mod\ngetattr(target_mod, 'Bar')"
    tree = ast.parse(src)
    alias_map, _ = _build_alias_map_and_consts(tree, "")
    ps: dict[str, set[str]] = {}
    _record_getattr_str_edges(tree, alias_map, ps, frozenset({"target_mod"}))
    sub_idx = _submodule_index(ps)

    assert _symbol_has_caller("Bar", "target_mod", ps, sub_idx), "target_mod::Bar must be rescued by getattr(target_mod, 'Bar')"
    assert not _symbol_has_caller("Bar", "unrelated_mod", ps, sub_idx), "unrelated_mod::Bar must NOT be rescued"


def test_no_false_negative_facade_detector() -> None:
    """Detector (b) must rescue only the submodule the facade re-exports from."""
    src = (
        '_PREFIX = ".sub"\n'
        "_LAZY = {\n"
        '    "Cls": (_PREFIX, "Cls"),\n'
        '    "fn": (".other", "fn"),\n'
        "}\n"
        "def __getattr__(name):\n"
        "    mod_path, attr = _LAZY[name]\n"
        "    return attr\n"
    )
    tree = ast.parse(src)
    _, str_consts = _build_alias_map_and_consts(tree, "mypkg")
    ps: dict[str, set[str]] = {}
    _record_facade_edges(tree, "mypkg", str_consts, ps, frozenset({"mypkg.sub", "mypkg.other"}))
    sub_idx = _submodule_index(ps)

    # Cls is exported from mypkg.sub
    assert _symbol_has_caller("Cls", "mypkg.sub", ps, sub_idx), "mypkg.sub::Cls must be rescued by the facade"
    # fn is exported from mypkg.other
    assert _symbol_has_caller("fn", "mypkg.other", ps, sub_idx)
    # Neither rescues an unrelated module
    assert not _symbol_has_caller("Cls", "mypkg.unrelated", ps, sub_idx), "mypkg.unrelated::Cls must NOT be rescued"


def test_no_false_negative_aliased_symbol_import_does_not_reblind() -> None:
    """T004 regression: ``from M import Cls as C; C.NAME`` must NOT rescue ``M::NAME``.

    This is the re-blinding vector the ``known_modules`` guard closes. ``C``
    binds to the synthetic path ``M.SomeClass`` (a symbol, not a module);
    a class-attribute access ``C.NAME`` must not be mistaken for a
    module-attribute access on ``M``. ``M`` is a real module, but
    ``M.SomeClass`` is not — so no edge may be recorded, and a genuinely-dead
    ``M::NAME`` stays flagged.
    """
    src = "from M import SomeClass as C\nC.NAME"
    tree = ast.parse(src)
    alias_map, _ = _build_alias_map_and_consts(tree, "")
    # ``M`` is a real module; ``M.SomeClass`` (the alias target) is NOT.
    known_modules = frozenset({"M"})
    ps: dict[str, set[str]] = {}
    _record_module_attr_edges(tree, alias_map, ps, known_modules)
    sub_idx = _submodule_index(ps)

    assert not _symbol_has_caller("NAME", "M", ps, sub_idx), (
        "M::NAME must NOT be rescued by the class-attribute access C.NAME "
        "(C = SomeClass imported from M); recording that edge would re-blind "
        "the gate via _submodule_index rule 3."
    )
    # Sanity: without the guard the collision DOES rescue — proves the guard
    # is the load-bearing difference, not a vacuous assertion.
    ps_unguarded: dict[str, set[str]] = {}
    _record_module_attr_edges(tree, alias_map, ps_unguarded, frozenset({"M", "M.SomeClass"}))
    assert _symbol_has_caller("NAME", "M", ps_unguarded, _submodule_index(ps_unguarded)), (
        "control: with M.SomeClass treated as a module, the collision rescues M::NAME"
    )


def test_no_false_negative_call_accessor_detector_direct_chain() -> None:
    """Detector (e) -- dynamic-access→live, direct call-chain shape (IC-01/#2559).

    ``factory().attr`` -- a zero-arg module-scope function whose body
    resolves ``target_mod`` via ``importlib.import_module(...)``, called and
    immediately attribute-accessed with no intermediate local -- rescues
    ``target_mod::Live`` exactly as a plain ``alias.Live`` import-bound
    access would. Resolved generally (no name special-case for
    ``runtime_bridge`` anywhere in the resolver).
    """
    src = "import importlib\ndef _factory():\n    return importlib.import_module('target_mod')\n_factory().Live\n"
    tree = ast.parse(src)
    alias_map, str_consts = _build_alias_map_and_consts(tree, "")
    known_modules = frozenset({"target_mod"})
    factories = find_module_factory_functions(tree, alias_map, str_consts, "", known_modules, _resolve_relative_module)
    ps: dict[str, set[str]] = {}
    record_call_chain_attr_edges(tree, factories, ps)
    sub_idx = _submodule_index(ps)

    assert _symbol_has_caller("Live", "target_mod", ps, sub_idx), (
        "target_mod::Live must be rescued by _factory().Live where _factory() dynamically resolves target_mod via importlib.import_module"
    )
    assert not _symbol_has_caller("Live", "unrelated_mod", ps, sub_idx), (
        "unrelated_mod::Live must NOT be rescued -- the resolver must not widen liveness to any attribute access (contract anti-goal)"
    )


def test_no_false_negative_call_accessor_detector_bound_local() -> None:
    """Detector (e) -- dynamic-access→live, the bound-local two-step shape
    actually used by the known ``_runtime_bridge_module()`` call sites in
    ``next_cmd.py`` (``bridge = _runtime_bridge_module(); bridge.attr``).
    """
    src = "import importlib\ndef _factory():\n    return importlib.import_module('target_mod')\nbridge = _factory()\nbridge.Live\n"
    tree = ast.parse(src)
    alias_map, str_consts = _build_alias_map_and_consts(tree, "")
    known_modules = frozenset({"target_mod"})
    factories = find_module_factory_functions(tree, alias_map, str_consts, "", known_modules, _resolve_relative_module)
    merged_alias_map = {**alias_map, **bind_call_accessor_aliases(tree, factories)}
    ps: dict[str, set[str]] = {}
    _record_module_attr_edges(tree, merged_alias_map, ps, known_modules)
    sub_idx = _submodule_index(ps)

    assert _symbol_has_caller("Live", "target_mod", ps, sub_idx), (
        "target_mod::Live must be rescued by bridge.Live where bridge = _factory() and _factory() dynamically resolves target_mod via importlib.import_module"
    )
    assert not _symbol_has_caller("Live", "unrelated_mod", ps, sub_idx)


def test_no_false_negative_call_accessor_detector_unreferenced_stays_dead() -> None:
    """Negative direction (contract dead-code-dynamic-access.md): a symbol with
    no static import AND no first-party dynamic access must still be
    classified dead -- the new detector rescues only the SPECIFIC attribute
    actually accessed through the recognised factory, not every symbol that
    happens to live in the factory's resolved module.
    """
    src = (
        "import importlib\n"
        "def _factory():\n"
        "    return importlib.import_module('target_mod')\n"
        "bridge = _factory()\n"
        "bridge.Live\n"  # only ``Live`` is actually accessed
    )
    tree = ast.parse(src)
    alias_map, str_consts = _build_alias_map_and_consts(tree, "")
    known_modules = frozenset({"target_mod"})
    factories = find_module_factory_functions(tree, alias_map, str_consts, "", known_modules, _resolve_relative_module)
    merged_alias_map = {**alias_map, **bind_call_accessor_aliases(tree, factories)}
    ps: dict[str, set[str]] = {}
    _record_module_attr_edges(tree, merged_alias_map, ps, known_modules)
    record_call_chain_attr_edges(tree, factories, ps)
    sub_idx = _submodule_index(ps)

    assert _symbol_has_caller("Live", "target_mod", ps, sub_idx)
    assert not _symbol_has_caller("NeverAccessed", "target_mod", ps, sub_idx), (
        "target_mod::NeverAccessed must stay dead -- the gate must not go "
        "blind and rescue every symbol reachable from a recognised factory's "
        "module, only the ones actually attribute-accessed"
    )


def test_wp01_runtime_bridge_facade_symbols_recognised_live_without_allowlist() -> None:
    """IC-01/WP05 DoD (FR-001/FR-002): the 4 known ``runtime.next.runtime_bridge``
    façade symbols are recognised-live via their dynamic
    ``_runtime_bridge_module()`` accessor call sites in ``next_cmd.py`` --
    with NO permanent allowlist entry
    (the runtime-bridge compat-surface allowlist category no longer carries
    these 4 rows as of WP05). This test proves the gate's caller-detection
    sees them via the now-wired :func:`_imports_by_target` -- driven
    through the REAL live ``src/`` corpus, not a fixture.
    """
    inputs = _real_tree_inputs()  # the real _walk_modules() + _imports_by_target(), cached once per file (G7)
    decls, per_symbol = inputs.decls, inputs.per_symbol
    submodule_index = _submodule_index(per_symbol)

    mod_dotted = "runtime.next.runtime_bridge"
    for name in (
        "get_or_start_run",
        "query_current_state",
        "answer_decision_via_runtime",
        "QueryModeValidationError",
    ):
        assert name in decls.get(mod_dotted, frozenset()), (
            f"{mod_dotted}::{name} must still be declared in __all__ -- this test targets the real live corpus, not a stale fixture"
        )
        assert _symbol_has_caller(name, mod_dotted, per_symbol, submodule_index), (
            f"{mod_dotted}::{name} must be recognised-live via the _runtime_bridge_module() dynamic accessor WITHOUT its allowlist row (IC-01 / FR-001 / FR-002)"
        )


# ---------------------------------------------------------------------------
# Self-mutation battery (contracts/dead-symbol-allowlist.md §3), through the
# production `_compute_offenders` / `_evaluate_allowlist` / `_evaluate_widened`
# path (C-007), never a standalone re-derivation. M1, M7, M8 and M11(a/b) live
# in `test_dead_symbol_allowlist_contract.py`; M12 in the loader tests.
# ---------------------------------------------------------------------------

_BATTERY_CATEGORY = "category_bite_battery"


def _allowlist_of(*keys: DeadSymbolKey) -> DeadSymbolAllowlist:
    """An in-memory allowlist whose ``entries`` are exactly *keys* (no widened section)."""
    category = AllowlistCategory(id=_BATTERY_CATEGORY, rationale="bite-battery fixture", requires_issue=False, target=None)
    return DeadSymbolAllowlist(
        categories=MappingProxyType({_BATTERY_CATEGORY: category}),
        entries=tuple(AllowlistEntry(key=key, category=_BATTERY_CATEGORY, rationale=None, issue=None) for key in keys),
        widened_entries=(),
        widened_rationale="bite-battery fixture",
        widened_issue="#5346",
    )


def _synthetic_inputs(modules: Mapping[str, str]) -> tuple[dict[str, frozenset[str]], dict[str, CorpusModule]]:
    """``(all_literal_decls, corpus)`` for ``{dotted_module: source}`` (plain modules, package = dotted parent)."""
    all_literal_decls: dict[str, frozenset[str]] = {}
    corpus: dict[str, CorpusModule] = {}
    for dotted, source in modules.items():
        tree = ast.parse(source)
        corpus[dotted] = CorpusModule(tree=tree, source=source, containing_pkg=dotted.rpartition(".")[0])
        declared = _extract_all_literal(tree) or frozenset()
        if declared:
            all_literal_decls[dotted] = declared
    return all_literal_decls, corpus


def _verdicts(evaluation: AllowlistEvaluation) -> list[tuple[str, StaleVerdict]]:
    return [(str(finding.key), finding.verdict) for finding in evaluation.stale]


def test_gate_still_flags_a_truly_dead_symbol() -> None:
    """M2 -- a new dead symbol reds and is named; the gate is not a silent no-op (NFR-001 / DoD a).

    Four additive caller-detectors can only ADD rescues, so a self-test must
    prove the aggregate path still FLAGS a symbol that nothing imports -- and
    still PASSES one that has a real caller or a keyable ``(module, name)``
    allowlist entry. Driven through the same ``_compute_offenders`` path the
    production gate uses. M2 proper: a NEW dead name beside an allowlisted one
    in the same module is named as an offender, not covered by its neighbour.
    """
    decls = {"synthetic.deadmod": frozenset({"NeverImported"})}
    empty_corpus: dict[str, CorpusModule] = {}
    empty_index: dict[str, list[Location]] = {}

    # No caller of any kind → still flagged.
    flagged = _compute_offenders(decls, {}, set(), frozenset(), empty_corpus, empty_index)
    assert flagged == ["synthetic.deadmod::NeverImported"], f"gate must flag a symbol with zero callers; got {flagged!r}"

    # A real direct importer → not flagged (control).
    with_caller = {"synthetic.deadmod": {"NeverImported"}}
    assert _compute_offenders(decls, with_caller, set(), frozenset(), empty_corpus, empty_index) == [], "a symbol with a real caller must NOT be flagged"

    # Allowlisted with a keyable corpus → not flagged (control for the exception path).
    allow = frozenset({DeadSymbolKey("synthetic.deadmod", "NeverImported")})
    source = "NeverImported = object()\n"
    corpus = {"synthetic.deadmod": CorpusModule(tree=ast.parse(source), source=source, containing_pkg="synthetic")}
    collision_index = classify_collisions(corpus)
    assert _compute_offenders(decls, {}, set(), allow, corpus, collision_index) == []

    # G1 keyability: the same entry over a corpus that cannot key the name exempts nothing.
    assert _compute_offenders(decls, {}, set(), allow, empty_corpus, empty_index) == ["synthetic.deadmod::NeverImported"]

    # M2: a new dead `New` in the allowlisted module is an offender, named.
    m2_decls, m2_corpus = _synthetic_inputs({"synthetic.deadmod": "__all__ = ['NeverImported', 'New']\nNeverImported = object()\nNew = 1\n"})
    result = _evaluate_allowlist(m2_decls, {}, set(), m2_corpus, _allowlist_of(DeadSymbolKey("synthetic.deadmod", "NeverImported")))
    assert result.offenders == ["synthetic.deadmod::New"]
    assert result.stale == [], [finding.render() for finding in result.stale]


def test_auto_exempt_disjoint_from_hand_allowlist() -> None:
    """T013 disjointness, on the real tree: auto_exempt ∩ hand_allowlist = ∅.

    An entry must not be BOTH auto-derived (registered migration class /
    Typer sub-app / Typer command / re-export shim) AND listed in the
    allowlist's ``entries`` -- redundant bookkeeping that would let the two
    drift. The gate reports such an entry SUPERSEDED; this check is
    independent of the classifier's verdict order (a SUPERSEDED entry that is
    also REVIVED is only reported REVIVED there).
    """
    inputs = _real_tree_inputs()
    submodule_index = _submodule_index(inputs.per_symbol)

    overlaps: list[str] = []
    for key in sorted(_SYMBOL_ALLOWLIST):
        if key.module in inputs.star_targets or key.name not in inputs.decls.get(key.module, frozenset()):
            continue
        module = inputs.corpus.get(key.module)
        final_key = _resolve_final_key(key.name, key.module, module, inputs.corpus, inputs.collision_index)
        if _is_auto_exempt(key.module, key.name, module, final_key, inputs.per_symbol, submodule_index):
            overlaps.append(str(key))
    assert not overlaps, f"auto-exempt/hand-allowlist overlap violates T013 disjointness (auto_exempt ∩ hand_allowlist must be ∅): {overlaps}"


def test_bite_c_same_name_fan_out_dead_sibling_still_caught() -> None:
    """M3 (DoD c, T004) -- an allowlisted name does not cover a same-name dead sibling.

    ``(synthetic.mod_a, Shared)`` is allowlisted; ``synthetic.mod_b`` declares
    its own ``Shared`` with a different body and no caller. The sibling has a
    different ``(module, name)`` key, so it is caught -- no collision logic
    is involved. The fan-out control (the live sibling has a real caller, no
    allowlist) keeps the original DoD (c) shape.
    """
    decls, corpus = _synthetic_inputs(
        {
            "synthetic.mod_a": "__all__ = ['Shared']\nShared = 1\n",
            "synthetic.mod_b": "__all__ = ['Shared']\nShared = 2\n",
        }
    )
    result = _evaluate_allowlist(decls, {}, set(), corpus, _allowlist_of(DeadSymbolKey("synthetic.mod_a", "Shared")))
    assert result.offenders == ["synthetic.mod_b::Shared"], "the dead same-name sibling must be caught"
    assert result.stale == [], [finding.render() for finding in result.stale]

    per_symbol = {"synthetic.mod_a": {"Shared"}}  # mod_a::Shared has a real caller
    offenders = _compute_offenders(decls, per_symbol, set(), frozenset(), corpus, classify_collisions(corpus))
    assert offenders == ["synthetic.mod_b::Shared"], "the dead fan-out sibling must be caught, the live one must not"


def test_bite_e_dead_migration_helper_still_caught() -> None:
    """DoD (e) -- a dead helper in a migration file is still caught despite FR-010.

    T013's ``_is_registered_migration_class`` auto-exempts ONLY the
    ``@MigrationRegistry.register``-decorated class, never anything else in
    the same ``m_*.py`` file.
    """
    source = (
        "class MigrationRegistry:\n"
        "    @classmethod\n"
        "    def register(cls, k):\n"
        "        return k\n"
        "\n"
        "\n"
        "@MigrationRegistry.register\n"
        "class SyntheticMigration:\n"
        "    pass\n"
        "\n"
        "\n"
        "DEAD_HELPER = 1\n"
    )
    tree = ast.parse(source)
    mod_dotted = "specify_cli.upgrade.migrations.m_9_9_9_synthetic"
    corpus = {mod_dotted: CorpusModule(tree, source, "specify_cli.upgrade.migrations")}
    collision_index = classify_collisions(corpus)
    decls = {mod_dotted: frozenset({"SyntheticMigration", "DEAD_HELPER"})}
    offenders = _compute_offenders(decls, {}, set(), frozenset(), corpus, collision_index)
    assert offenders == [f"{mod_dotted}::DEAD_HELPER"], (
        "the registered migration class must be auto-exempt but the dead helper constant beside it must still be caught"
    )


def test_bite_f_undecidable_key_fails_closed() -> None:
    """M9 (DoD f) -- an allowlisted un-keyable name stays an offender AND its entry is INVALID.

    ``Ghost`` is declared in ``__all__`` but has no ClassDef/FunctionDef/
    Assign/AnnAssign/ImportFrom/facade shape at all -- the resolver returns
    ``None``, so the ``(module, name)`` entry cannot exempt it (G1, fail-closed)
    and is reported INVALID.
    """
    decls, corpus = _synthetic_inputs({"synthetic.ghostmod": "__all__ = ['Ghost']\n"})
    assert resolve_symbol_key("Ghost", "synthetic.ghostmod", corpus["synthetic.ghostmod"], corpus=corpus) is None, (
        "sanity: this shape must be genuinely undecidable"
    )

    result = _evaluate_allowlist(decls, {}, set(), corpus, _allowlist_of(DeadSymbolKey("synthetic.ghostmod", "Ghost")))
    assert result.offenders == ["synthetic.ghostmod::Ghost"], "an un-keyable symbol must fail closed (flagged), never silently exempted"
    assert _verdicts(result) == [("synthetic.ghostmod::Ghost", StaleVerdict.INVALID)]


def test_bite_i_byte_identical_rogue_sibling_still_caught() -> None:
    """M4 (DoD i, the Defect-1 / T004 re-blinding guard) -- a byte-identical rogue sibling is caught.

    Two modules each declare a class ``GateDecision`` with the IDENTICAL body
    (the future ``GateDecision``-collapse vector). ``(synthetic.sanctioned,
    GateDecision)`` is allowlisted; the rogue sibling has no caller. Its
    ``(module, name)`` key differs, so it is caught with no tier escalation
    or any other collision logic involved.
    """
    body = "class GateDecision:\n    pass\n"
    decls, corpus = _synthetic_inputs(
        {
            "synthetic.sanctioned": body + "\n\n__all__ = ['GateDecision']\n",
            "synthetic.rogue": body + "\n\n__all__ = ['GateDecision']\n",
        }
    )
    result = _evaluate_allowlist(decls, {}, set(), corpus, _allowlist_of(DeadSymbolKey("synthetic.sanctioned", "GateDecision")))
    assert result.offenders == ["synthetic.rogue::GateDecision"], "the unsanctioned byte-identical sibling must still be caught"
    assert result.stale == [], [finding.render() for finding in result.stale]


def test_bite_k_full_keyability_hand_and_auto_exempt() -> None:
    """M9 at corpus scale (DoD k) -- 0 un-keyable entries, hand or auto.

    Every allowlist entry whose name is still declared resolves to a real key
    on the live corpus (no INVALID verdict), and every symbol the T013
    structural auto-exempt mechanism claims to cover resolves to a real key
    too (never a claimed-but-unproven exemption).
    """
    inputs = _real_tree_inputs()
    submodule_index = _submodule_index(inputs.per_symbol)
    ctx = _StaleContext(
        all_literal_decls=inputs.all_literal_decls,
        corpus=inputs.corpus,
        collision_index=inputs.collision_index,
        per_symbol=inputs.per_symbol,
        submodule_index=submodule_index,
        star_targets=inputs.star_targets,
    )
    invalid = [str(key) for key in sorted(_SYMBOL_ALLOWLIST) if _classify_entry(key, ctx) is StaleVerdict.INVALID]
    assert not invalid, f"allowlist entries whose name binds nothing keyable (INVALID): {invalid}"

    unkeyable_auto_exempt: list[str] = []
    for mod_dotted, names in inputs.decls.items():
        if mod_dotted in inputs.star_targets:
            continue
        module = inputs.corpus.get(mod_dotted)
        for name in names:
            final_key = _resolve_final_key(name, mod_dotted, module, inputs.corpus, inputs.collision_index)
            if not _is_auto_exempt(mod_dotted, name, module, final_key, inputs.per_symbol, submodule_index):
                continue
            if module is None or resolve_symbol_key(name, mod_dotted, module, corpus=inputs.corpus) is None:
                unkeyable_auto_exempt.append(f"{mod_dotted}::{name}")
    assert not unkeyable_auto_exempt, f"auto-exempt mechanism claims coverage for an un-keyable symbol (fail-closed violation): {unkeyable_auto_exempt}"


def test_bite_d_wired_allowlisted_symbol_reports_revived() -> None:
    """M5 (DoD d) -- an allowlisted symbol that gains a direct caller is stale REVIVED.

    Both shapes of the old tiered identity are covered, since keyability
    still runs through the runtime tiering: a plain symbol, and one of a
    byte-identical same-name pair (only the wired one is REVIVED; its dead
    unlisted twin is an offender).
    """
    decls, corpus = _synthetic_inputs({"synthetic.wiredmod": "__all__ = ['Const']\nConst = 1\n"})
    result = _evaluate_allowlist(decls, {"synthetic.wiredmod": {"Const"}}, set(), corpus, _allowlist_of(DeadSymbolKey("synthetic.wiredmod", "Const")))
    assert result.offenders == []
    assert _verdicts(result) == [("synthetic.wiredmod::Const", StaleVerdict.REVIVED)]
    assert result.stale[0].render() == f"synthetic.wiredmod::Const [REVIVED] {_HINT_REVIVED}"

    body = "class Dup:\n    pass\n"
    dup_decls, dup_corpus = _synthetic_inputs(
        {
            "synthetic.dup_a": body + "\n\n__all__ = ['Dup']\n",
            "synthetic.dup_b": body + "\n\n__all__ = ['Dup']\n",
        }
    )
    dup_result = _evaluate_allowlist(dup_decls, {"synthetic.dup_a": {"Dup"}}, set(), dup_corpus, _allowlist_of(DeadSymbolKey("synthetic.dup_a", "Dup")))
    assert dup_result.offenders == ["synthetic.dup_b::Dup"]
    assert _verdicts(dup_result) == [("synthetic.dup_a::Dup", StaleVerdict.REVIVED)]


def test_m6_deleted_allowlisted_symbol_reports_gone() -> None:
    """M6 -- an allowlisted symbol that is deleted is stale GONE (replaces ``bite_g``'s dangling arms).

    Both deletion shapes: the name is gone from a module that still exists,
    and the whole module is gone. No offender of the same name exists, so no
    "probably moved" hint is given.
    """
    decls, corpus = _synthetic_inputs({"synthetic.m": "__all__ = ['Other']\nOther = 1\n"})
    allowlist = _allowlist_of(
        DeadSymbolKey("synthetic.m", "Deleted"),
        DeadSymbolKey("synthetic.m", "Other"),
        DeadSymbolKey("synthetic.removed_module", "Anything"),
    )
    result = _evaluate_allowlist(decls, {}, set(), corpus, allowlist)
    assert result.offenders == []
    assert _verdicts(result) == [
        ("synthetic.m::Deleted", StaleVerdict.GONE),
        ("synthetic.removed_module::Anything", StaleVerdict.GONE),
    ]
    assert [finding.hint for finding in result.stale] == [_HINT_GONE, _HINT_GONE]


def test_m10_name_dropped_from_all_reports_gone() -> None:
    """M10 -- an allowlisted name removed from ``__all__``, symbol still defined, is stale GONE.

    The symbol now belongs to the #470 widened scope, which the ``entries``
    section never covers, so the entry exempts nothing and must go.
    """
    source = "__all__ = ['Kept']\nKept = 1\nDropped = 2\n"
    decls, corpus = _synthetic_inputs({"synthetic.m": source})
    assert definition_span(corpus["synthetic.m"].tree, "Dropped") is not None, "sanity: the symbol itself is still defined"

    result = _evaluate_allowlist(decls, {}, set(), corpus, _allowlist_of(DeadSymbolKey("synthetic.m", "Kept"), DeadSymbolKey("synthetic.m", "Dropped")))
    assert result.offenders == []
    assert _verdicts(result) == [("synthetic.m::Dropped", StaleVerdict.GONE)]


def test_stale_superseded_and_moot_verdicts() -> None:
    """SUPERSEDED and MOOT (data-model §1.5 rules 4-5), each through ``_evaluate_allowlist``.

    SUPERSEDED: an allowlisted Typer command is covered by the T013
    auto-exemption. MOOT: an allowlisted name in a star-imported module --
    the offender pass skips the module, so the entry exempts nothing.
    """
    decls, corpus = _synthetic_inputs({"synthetic.cli": "__all__ = ['run']\n@app.command()\ndef run():\n    pass\n"})
    superseded = _evaluate_allowlist(decls, {}, set(), corpus, _allowlist_of(DeadSymbolKey("synthetic.cli", "run")))
    assert superseded.offenders == []
    assert [finding.render() for finding in superseded.stale] == [f"synthetic.cli::run [SUPERSEDED] {_HINT_SUPERSEDED}"]

    star_decls, star_corpus = _synthetic_inputs({"synthetic.starred": "__all__ = ['Thing']\nThing = 1\n"})
    moot = _evaluate_allowlist(star_decls, {}, {"synthetic.starred"}, star_corpus, _allowlist_of(DeadSymbolKey("synthetic.starred", "Thing")))
    assert moot.offenders == [], "the offender pass skips a star-imported module"
    assert _verdicts(moot) == [("synthetic.starred::Thing", StaleVerdict.MOOT)]


def test_gone_hint_names_every_candidate_new_home() -> None:
    """The GONE hint lists each other module where a same-name offender now lives; render drops trailing space."""
    key = DeadSymbolKey("pkg.old", "N")
    assert _gone_hint(key, ["pkg.old::N", "pkg.x::Other"]) == _HINT_GONE
    assert _gone_hint(key, ["pkg.c::N", "pkg.b::N"]) == "probably moved to `pkg.b` or `pkg.c`; update `module:`"
    assert StaleFinding(key=key, verdict=StaleVerdict.GONE, hint="").render() == "pkg.old::N [GONE]"


def test_real_tree_inputs_are_read_only() -> None:
    """F-06 -- the file-cached walk cannot be mutated by a test.

    A test that added a caller to the cached ``per_symbol`` would silently
    rescue dead symbols for every later real-tree test on the same worker.
    """
    inputs = _real_tree_inputs()
    assert inputs is _real_tree_inputs(), "the real-tree walk must be cached for the file"
    for mapping in (inputs.decls, inputs.all_literal_decls, inputs.corpus, inputs.per_symbol, inputs.collision_index):
        assert isinstance(mapping, MappingProxyType)
    assert isinstance(inputs.star_targets, frozenset)
    assert inputs.per_symbol, "sanity: the live tree has import edges"
    assert all(isinstance(names, frozenset) for names in inputs.per_symbol.values())
    writable: Any = inputs.per_symbol  # the static type forbids the write; the runtime view must refuse it too
    with pytest.raises(TypeError):
        writable["synthetic.planted"] = frozenset({"Planted"})


def test_m13_corpus_floor_reds_on_a_quarter_of_the_modules() -> None:
    """M13 -- the §2.1 non-vacuity floor reds when the walker returns a quarter of the modules.

    Driven through the same ``_corpus_floor_shortfall`` the real gate asserts
    on, over a truncated COPY of the cached walk (never a monkeypatched walker,
    which would poison or bypass the per-file cache).
    """
    live = _real_tree_inputs().all_literal_decls
    assert _corpus_floor_shortfall(live) == [], "control: the live corpus meets the floor"

    modules = sorted(live)
    quarter = {module: live[module] for module in modules[: len(modules) // 4]}
    shortfall = _corpus_floor_shortfall(quarter)
    assert len(shortfall) == 2, shortfall
    assert f"floor {_CORPUS_FLOOR_NAMES}" in shortfall[0]
    assert f"floor {_CORPUS_FLOOR_MODULES}" in shortfall[1]


def test_m11c_gate_reads_the_widened_section_it_is_given(tmp_path: Path) -> None:
    """M11(c) (F-05) -- the widened pass reads the widened section of the file it is given.

    A scratch copy of the real allowlist with one ``widened_grandfathered_470``
    entry popped, loaded through the real loader and evaluated over the real
    cached corpus, reports exactly that entry as an offender. The control (the
    committed file's single parse) is clean.
    """
    inputs = _real_tree_inputs()

    def evaluate(grandfathered: AbstractSet[str]) -> tuple[list[str], list[str]]:
        return _evaluate_widened(
            inputs.decls,
            inputs.all_literal_decls,
            inputs.per_symbol,
            inputs.star_targets,
            inputs.corpus,
            inputs.collision_index,
            grandfathered,
        )

    assert evaluate(ALLOWLIST.widened_qualified) == ([], []), "control: the committed widened section is clean"

    raw = yaml.safe_load(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    scratch_doc = copy.deepcopy(raw)
    widened_entries = scratch_doc["widened_grandfathered_470"]["entries"]
    popped = min(widened_entries, key=lambda entry: (entry["module"], entry["name"]))
    widened_entries.remove(popped)
    scratch_path = tmp_path / "widened_popped.yaml"
    scratch_path.write_text(yaml.safe_dump(scratch_doc, sort_keys=False), encoding="utf-8")
    scratch = load_allowlist(scratch_path)
    popped_qualified = f"{popped['module']}::{popped['name']}"
    assert scratch.widened_qualified == ALLOWLIST.widened_qualified - {popped_qualified}, "sanity: the loader read the scratch file"

    offenders, widened_stale = evaluate(scratch.widened_qualified)
    assert offenders == [popped_qualified]
    assert widened_stale == []


def test_annassign_symbol_stays_keyable() -> None:
    """G1 keyability of an ``AnnAssign`` target, before and after annotation-whitespace reformatting.

    The surviving arm of the retired ``bite_j`` AnnAssign test: an annotated
    constant must bind a keyable name in both spellings, or its
    ``(module, name)`` entry could never exempt it.
    """
    for source in ("TTL_SECONDS:int=3600\n", "TTL_SECONDS : int = 3600\n"):
        decls, corpus = _synthetic_inputs({"synthetic.home": "__all__ = ['TTL_SECONDS']\n" + source})
        module = corpus["synthetic.home"]
        assert _resolve_final_key("TTL_SECONDS", "synthetic.home", module, corpus, classify_collisions(corpus)) is not None, source
        result = _evaluate_allowlist(decls, {}, set(), corpus, _allowlist_of(DeadSymbolKey("synthetic.home", "TTL_SECONDS")))
        assert (result.offenders, result.stale) == ([], []), source


def test_bite_j_gate_single_alias_sibling_edit_zero_false_red() -> None:
    """DoD (j) gate-side, non-relocation arm -- a single-alias ``ImportFrom`` entry survives sibling edits.

    ``B`` is bound by ``from foo.bar import Alpha, Beta as B, Gamma`` and
    allowlisted as ``(synthetic.home, B)``. Renaming both sibling aliases
    leaves ``B`` keyable and exempt: zero false red through the production
    path. (The relocation arm was retired with the old identity: a move is
    now reported, see M8.)
    """
    for source in ("from foo.bar import Alpha, Beta as B, Gamma\n", "from foo.bar import AlphaRenamedCompletely, Beta as B, GammaRenamedToo\n"):
        decls, corpus = _synthetic_inputs({"synthetic.home": "__all__ = ['B']\n" + source})
        result = _evaluate_allowlist(decls, {}, set(), corpus, _allowlist_of(DeadSymbolKey("synthetic.home", "B")))
        assert result.offenders == [], f"B must not be caught: {source!r}"
        assert result.stale == [], [finding.render() for finding in result.stale]


def test_real_tree_inputs_cleared_at_file_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-006: the walk's trees + source are bounded to this file by a module-scoped finalizer.

    The finalizer's generator is driven directly (set-up half, then teardown
    half) against a stub cache, so the real ``_real_tree_inputs`` is never cleared
    mid-file (that would force a second ``src/`` walk for every later consumer).
    Deleting the release call from the fixture, or from ``_release_real_tree_inputs``,
    leaves the stub populated and fails this test.
    """

    @functools.lru_cache(maxsize=1)
    def _stub() -> int:
        return 1

    _stub()
    assert _stub.cache_info().currsize == 1
    monkeypatch.setattr(sys.modules[__name__], "_real_tree_inputs", _stub)  # resolved at call time by the release

    finalizer = inspect.unwrap(_clear_real_tree_inputs)()
    assert next(finalizer) is None
    assert _stub.cache_info().currsize == 1, "set-up must not clear the cache; only teardown does"
    with pytest.raises(StopIteration):
        next(finalizer)

    assert _stub.cache_info().currsize == 0
