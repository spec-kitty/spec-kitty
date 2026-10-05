"""Patch census: how tests patch the ``mission_creation`` module family.

Reporting tool. Not a gate (no size or count gates: ADR
``docs/adr/4.x/2026-09-30-1``). Never add a threshold, a ratchet or a
baseline file here, and never wire this module into ``conftest.py`` or
``pytest.ini``. It runs only when invoked:

* static: ``python -m tests._support.patch_census --report [--json]``
* runtime: ``pytest -p tests._support.patch_census ...`` with
  ``SPEC_KITTY_PATCH_CENSUS_OUT=<path>`` (workers write ``<path>.<worker>.json``;
  ``--report --runtime <path>`` merges them).

What a *site* is: one patched name at one call (``patch.multiple`` and
``patch.dict`` contribute one site per name). Each site is classified into a
bucket by the namespace it patches:

``family``
    a module named by ``family_prefix*`` (the facade and every future sibling).
    Counted in the patch budget.
``source``
    the module a family module imports the patched name from, for example
    ``specify_cli.core.git_ops.get_current_branch``. This is a patch laundered
    onto the source module.
``stdlib``
    a process-global stdlib name the family reads (``subprocess``, ``os`` ...).
    Outside the patch budget.
``namespace_other``
    the same name patched on some unrelated module (reported, not budgeted).

Supported static forms (each has a positive control in ``test_patch_census.py``):
string targets (literals, f-strings and ``+`` over string constants, including
``<alias>.__name__``); ``monkeypatch.setattr/delattr``; ``patch``,
``patch.object``, ``patch.multiple``; ``patch.dict`` and
``monkeypatch.setitem/delitem`` over ``<module>.__dict__`` / ``vars(<module>)``;
``patch.dict(sys.modules, ...)`` and ``setitem(sys.modules, ...)``; plain
attribute assignment ``<alias>.<name> = ...``; and module aliases bound by
``import``, ``from pkg import module`` or ``importlib.import_module`` at module
or function scope. A target the scanner cannot resolve is reported in
``CensusReport.unresolved``, never dropped.

Runtime limits: plain attribute assignment is invisible to the runtime counter,
and a patch applied to an object reached through a family module
(``patch.object(mission_creation.subprocess, "run")``) is seen as the object's
own namespace (``subprocess``), not as the family.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import itertools
import re
import sys
import unittest.mock as _mock
from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from tests.architectural._ast_scan import read_and_parse

DEFAULT_FAMILY_PREFIX = "specify_cli.core.mission_creation"
ENV_OUT = "SPEC_KITTY_PATCH_CENSUS_OUT"

BUCKET_FAMILY = "family"
BUCKET_SOURCE = "source"
BUCKET_STDLIB = "stdlib"
BUCKET_OTHER = "namespace_other"
BUCKETS = (BUCKET_FAMILY, BUCKET_SOURCE, BUCKET_STDLIB, BUCKET_OTHER)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOTTED = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+$")
_PARAM_ROW_CAP = 64
_PATCH_RECEIVERS: frozenset[tuple[str, ...]] = frozenset({(), ("mock",), ("mocker",), ("unittest", "mock")})
_MOCK_RECEIVERS: frozenset[tuple[str, ...]] = frozenset({("mock",), ("mocker",), ("unittest", "mock")})
_MODULE_ATTR = "<module>"
_DYNAMIC_ATTR = "<dynamic>"
_SYS_MODULES = "sys.modules"
_DICT_SUFFIX = ".__dict__"
_STDLIB: frozenset[str] = frozenset(sys.stdlib_module_names)


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PatchSite:
    """One patched name at one call site."""

    file: str
    line: int
    module: str
    attr: str
    form: str
    bucket: str

    @property
    def name(self) -> str:
        """First segment of the patched attribute chain (``subprocess.run`` -> ``subprocess``)."""
        return self.attr.split(".")[0]


@dataclass(frozen=True)
class UnresolvedSite:
    """A patch call whose target the scanner could not resolve."""

    file: str
    line: int
    expr: str
    form: str
    family_suspect: bool


@dataclass(frozen=True)
class FamilyReads:
    """Names the family modules import, with the modules they come from."""

    names: frozenset[str]
    sources: Mapping[str, frozenset[str]] = field(default_factory=dict)

    @property
    def source_modules(self) -> frozenset[str]:
        return frozenset(m for mods in self.sources.values() for m in mods)


@dataclass(frozen=True)
class CensusReport:
    """Static census result. ``sites`` holds only budget-relevant buckets."""

    sites: tuple[PatchSite, ...]
    unresolved: tuple[UnresolvedSite, ...]

    def _select(self, bucket: str | None) -> Iterator[PatchSite]:
        return (s for s in self.sites if bucket is None or s.bucket == bucket)

    def count(self, bucket: str | None = None) -> int:
        return sum(1 for _ in self._select(bucket))

    def by_name(self, bucket: str | None = None) -> Counter[str]:
        return Counter(s.attr for s in self._select(bucket))

    def by_file(self, bucket: str | None = None) -> Counter[str]:
        return Counter(s.file for s in self._select(bucket))

    def by_namespace(self, bucket: str | None = None) -> Counter[str]:
        return Counter(s.module for s in self._select(bucket))

    def by_form(self, bucket: str | None = None) -> Counter[str]:
        return Counter(s.form for s in self._select(bucket))

    def restricted_to(self, files: Iterable[str]) -> CensusReport:
        """The same report limited to an explicit file list (repo-relative paths)."""
        keep = frozenset(files)
        return CensusReport(
            sites=tuple(s for s in self.sites if s.file in keep),
            unresolved=tuple(u for u in self.unresolved if u.file in keep),
        )

    def family_targeting_unresolved(self) -> tuple[UnresolvedSite, ...]:
        return tuple(u for u in self.unresolved if u.family_suspect)

    def summary(self) -> dict[str, Any]:
        return {
            "totals": {b: self.count(b) for b in BUCKETS},
            "by_name": {b: dict(self.by_name(b).most_common()) for b in BUCKETS},
            "by_namespace": {b: dict(self.by_namespace(b).most_common()) for b in BUCKETS},
            "by_file": {b: dict(self.by_file(b).most_common()) for b in BUCKETS},
            "by_form": {b: dict(self.by_form(b).most_common()) for b in BUCKETS},
            "unresolved_total": len(self.unresolved),
            "unresolved_family_targeting": [{"file": u.file, "line": u.line, "expr": u.expr, "form": u.form} for u in self.family_targeting_unresolved()],
        }


# --------------------------------------------------------------------------- #
# Module-path resolution and bucket classification
# --------------------------------------------------------------------------- #


class _Resolver:
    """Splits a dotted target into (module, attribute chain) and classifies it."""

    def __init__(self, src_root: Path, family_prefix: str, reads: FamilyReads) -> None:
        self._src = src_root
        self._prefix = family_prefix
        self._family_last = family_prefix.rsplit(".", 1)[-1]
        self._reads = reads
        self._cache: dict[str, bool] = {}

    @property
    def family_token(self) -> str:
        return self._family_last

    def is_family(self, module: str) -> bool:
        """``family_prefix`` exactly, a ``family_prefix_*`` sibling, or a submodule of either."""
        return module == self._prefix or module.startswith((self._prefix + "_", self._prefix + "."))

    def is_module(self, dotted: str) -> bool:
        if dotted not in self._cache:
            rel = Path(*dotted.split("."))
            self._cache[dotted] = (
                self.is_family(dotted)
                and "." not in dotted[len(self._prefix) :]
                or (self._src / rel).with_suffix(".py").is_file()
                or (self._src / rel / "__init__.py").is_file()
            )
        return self._cache[dotted]

    def split(self, dotted: str) -> tuple[str, str]:
        """Longest importable module prefix, and the attribute chain after it."""
        parts = dotted.split(".")
        family_at = self._family_index(parts)
        if family_at is not None:
            return ".".join(parts[: family_at + 1]), ".".join(parts[family_at + 1 :])
        for n in range(len(parts), 0, -1):
            if self.is_module(".".join(parts[:n])):
                return ".".join(parts[:n]), ".".join(parts[n:])
        if parts[0] in _STDLIB or len(parts) == 1:
            return parts[0], ".".join(parts[1:])
        return ".".join(parts[:-1]), parts[-1]

    def _family_index(self, parts: list[str]) -> int | None:
        for i in range(len(parts)):
            if self.is_family(".".join(parts[: i + 1])) and _is_family_stem(parts[i], self._family_last):
                return i
        return None

    def bucket(self, module: str, attr: str) -> str | None:
        """Bucket for a patched ``module.attr``; ``None`` when irrelevant."""
        if self.is_family(module):
            return BUCKET_FAMILY
        first = attr.split(".")[0]
        names = self._reads.names
        hits = [h for h in (first, module if module in names else "") if h and h in names]
        if not hits:
            return None
        return self._bucket_for_hit(hits[0], module, attr)

    def _bucket_for_hit(self, hit: str, module: str, attr: str) -> str:
        sources = self._reads.sources.get(hit)
        module_top = module.split(".")[0]
        if sources is None:
            return BUCKET_STDLIB if module_top in _STDLIB else BUCKET_SOURCE
        if all(s.split(".")[0] in _STDLIB for s in sources):
            return BUCKET_STDLIB if (module_top in _STDLIB or "." in attr) else BUCKET_OTHER
        return BUCKET_SOURCE if module in sources else BUCKET_OTHER

    def may_target_family(self, module: str) -> bool:
        return self.is_family(module) or module in self._reads.source_modules


def derive_family_reads(src_root: Path, family_prefix: str = DEFAULT_FAMILY_PREFIX) -> FamilyReads:
    """Names imported by every ``mission_creation*.py`` family source file.

    Scans module-level and function-local ``Import``/``ImportFrom``. A bound
    name maps to the module it is imported from (``import a.b as x`` -> ``a.b``;
    ``import a.b`` -> ``a``). Both the bound and the original name of
    ``from m import n as k`` are recorded.
    """
    parent, _, stem = family_prefix.rpartition(".")
    folder = src_root.joinpath(*parent.split("."))
    files = sorted(
        {
            *(f for f in folder.glob(f"{stem}*.py") if _is_family_stem(f.stem, stem)),
            *(f for f in folder.glob(f"{stem}*/**/*.py") if _is_family_stem(f.relative_to(folder).parts[0], stem)),
        }
    )
    sources: dict[str, set[str]] = {}
    for path in files:
        module = ".".join(path.relative_to(src_root).with_suffix("").parts)
        package = module.rsplit(".", 1)[0] if path.name != "__init__.py" else module
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            for name, origin in _import_bindings(node, package):
                sources.setdefault(name, set()).add(origin)
    return FamilyReads(
        names=frozenset(sources),
        sources={k: frozenset(v) for k, v in sources.items()},
    )


def _is_family_stem(name: str, stem: str) -> bool:
    """``mission_creation`` or ``mission_creation_*`` exactly (never ``mission_creationXYZ``)."""
    return name == stem or name.startswith(stem + "_")


def _import_bindings(node: ast.AST, package: str) -> Iterator[tuple[str, str]]:
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.asname:
                yield alias.asname, alias.name
            else:
                yield alias.name.split(".")[0], alias.name.split(".")[0]
    elif isinstance(node, ast.ImportFrom):
        base = _absolute_module(node, package)
        for alias in node.names:
            yield alias.name, base
            if alias.asname:
                yield alias.asname, base


def _absolute_module(node: ast.ImportFrom, package: str) -> str:
    if node.level == 0:
        return node.module or ""
    parts = package.split(".")
    base = parts[: len(parts) - (node.level - 1)]
    return ".".join([*base, *([node.module] if node.module else [])])


# --------------------------------------------------------------------------- #
# Static scanner
# --------------------------------------------------------------------------- #


def _chain(node: ast.AST) -> tuple[str, ...] | None:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return tuple(reversed(parts))
    return None


def _call_kind(chain: tuple[str, ...] | None) -> str | None:
    """Patch-call family of a callee chain, or ``None`` when it is not one."""
    if not chain:
        return None
    last = chain[-1]
    if last in {"setattr", "delattr"}:
        return last
    if last in {"setitem", "delitem"} and len(chain) > 1:
        return last
    if last == "patch" and chain[:-1] in _PATCH_RECEIVERS:
        return "patch"
    if last in {"object", "multiple", "dict"} and len(chain) >= 2 and chain[-2] == "patch" and chain[:-2] in _PATCH_RECEIVERS:
        return last
    return None


def _target_names(target: ast.expr) -> list[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        return [n for elt in target.elts for n in _target_names(elt)]
    return []


def _row_parts(item: ast.expr, width: int) -> list[ast.expr]:
    """Components of one iteration item: a tuple/list/``pytest.param(...)`` unpacks, anything else is one value."""
    if width > 1 or isinstance(item, (ast.Tuple, ast.List)):
        if isinstance(item, (ast.Tuple, ast.List)):
            return list(item.elts)
        if isinstance(item, ast.Call) and (_chain(item.func) or ("",))[-1] == "param":
            return list(item.args)
        return []
    if isinstance(item, ast.Call) and (_chain(item.func) or ("",))[-1] == "param":
        return list(item.args[:1])
    return [item]


def _parametrize_names(node: ast.expr) -> list[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [n.strip() for n in node.value.split(",") if n.strip()]
    if isinstance(node, (ast.List, ast.Tuple)):
        return [e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    return []


def _bind(node: ast.Call, names: Sequence[str]) -> dict[str, ast.expr]:
    bound = dict(zip(names, node.args, strict=False))
    for kw in node.keywords:
        if kw.arg is not None and kw.arg in names:
            bound[kw.arg] = kw.value
    return bound


_SHADOWED = ""  # an alias rebound to a non-module value in this scope


@dataclass
class _Scope:
    consts: dict[str, str] = field(default_factory=dict)
    aliases: dict[str, str] = field(default_factory=dict)
    patch_names: set[str] = field(default_factory=set)  # names bound to the ``patch`` callable
    mock_names: set[str] = field(default_factory=set)  # names bound to the ``unittest.mock`` module / ``mocker``
    literals: dict[str, ast.expr] = field(default_factory=dict)  # names bound to literal list/tuple/dict displays
    tainted: set[str] = field(default_factory=set)  # loop/parametrize names fed by an unresolved family-mentioning iterable


class _FileScanner(ast.NodeVisitor):
    """One AST pass over one test file."""

    def __init__(self, rel: str, source: str, resolver: _Resolver, tree: ast.Module) -> None:
        self._rel = rel
        self._res = resolver
        self._family_imports = _family_imported_names(tree, resolver)
        self._seen_unresolved: set[tuple[int, str, str]] = set()
        self._scopes: list[_Scope] = [_Scope()]
        self.sites: list[PatchSite] = []
        self.unresolved: list[UnresolvedSite] = []
        for stmt in tree.body:  # hoist module-level constants and imports
            self._bind_statement(stmt)
        self._tree = tree

    def run(self) -> None:
        self.visit(self._tree)

    # -- environment ------------------------------------------------------- #

    def _lookup(self, table: str, key: str) -> str | None:
        for scope in reversed(self._scopes):
            value = getattr(scope, table).get(key)
            if value is not None:
                return str(value) if value != _SHADOWED else None
        return None

    def _has_name(self, table: str, key: str) -> bool:
        return any(key in getattr(scope, table) for scope in reversed(self._scopes))

    def _canonical_chain(self, node: ast.AST) -> tuple[str, ...] | None:
        """Callee chain with ``patch`` / ``mock`` aliases resolved to their canonical heads."""
        chain = _chain(node)
        if not chain:
            return chain
        if self._has_name("patch_names", chain[0]):
            return ("patch", *chain[1:])
        if self._has_name("mock_names", chain[0]):
            return ("mock", *chain[1:])
        return chain

    def _bind_statement(self, stmt: ast.stmt) -> None:
        scope = self._scopes[-1]
        if isinstance(stmt, ast.Import):
            for a in stmt.names:
                scope.aliases[a.asname or a.name.split(".")[0]] = a.name if a.asname else a.name.split(".")[0]
                if a.asname and a.name == "unittest.mock":
                    scope.mock_names.add(a.asname)
        elif isinstance(stmt, ast.ImportFrom) and stmt.module and stmt.level == 0:
            for a in stmt.names:
                full = f"{stmt.module}.{a.name}"
                if self._res.is_module(full):
                    scope.aliases[a.asname or a.name] = full
                self._bind_mock_import(scope, stmt.module, a)
        elif isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            self._bind_assign(scope, stmt.targets[0].id, stmt.value)

    @staticmethod
    def _bind_mock_import(scope: _Scope, module: str, alias: ast.alias) -> None:
        bound = alias.asname or alias.name
        if module == "unittest.mock" and alias.name == "patch":
            scope.patch_names.add(bound)
        elif module == "unittest" and alias.name == "mock":
            scope.mock_names.add(bound)

    def _bind_assign(self, scope: _Scope, name: str, value: ast.expr) -> None:
        if isinstance(value, (ast.List, ast.Tuple, ast.Dict)):
            scope.literals[name] = value
        text = self._str_value(value)
        if text is not None:
            scope.consts[name] = text
            return
        if self._bind_mock_alias(scope, name, value):
            return
        target = self._module_of(value)
        if target is not None and not target[1]:
            scope.aliases[name] = target[0]
        elif name in scope.aliases or self._lookup("aliases", name) is not None:
            scope.aliases[name] = _SHADOWED  # rebound to a non-module value

    def _bind_mock_alias(self, scope: _Scope, name: str, value: ast.expr) -> bool:
        chain = self._canonical_chain(value) if isinstance(value, (ast.Name, ast.Attribute)) else None
        if _call_kind(chain) == "patch":
            scope.patch_names.add(name)
        elif chain in _MOCK_RECEIVERS:
            scope.mock_names.add(name)
        else:
            return False
        return True

    # -- expression evaluation -------------------------------------------- #

    def _str_value(self, node: ast.AST) -> str | None:
        if isinstance(node, ast.Constant):
            return node.value if isinstance(node.value, str) else None
        if isinstance(node, ast.Name):
            return self._lookup("consts", node.id)
        if isinstance(node, ast.JoinedStr):
            return self._join_fstring(node)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, right = self._str_value(node.left), self._str_value(node.right)
            return left + right if left is not None and right is not None else None
        if isinstance(node, ast.Attribute) and node.attr == "__name__":
            target = self._module_of(node.value)
            return target[0] if target is not None and not target[1] else None
        return None

    def _join_fstring(self, node: ast.JoinedStr) -> str | None:
        out = ""
        for part in node.values:
            piece = self._str_value(part.value if isinstance(part, ast.FormattedValue) else part)
            if piece is None:
                return None
            out += piece
        return out

    def _module_of(self, node: ast.AST) -> tuple[str, str] | None:
        """(module, attribute chain) an expression denotes, or ``None``."""
        if isinstance(node, (ast.Name, ast.Attribute)):
            chain = _chain(node)
            base = self._lookup("aliases", chain[0]) if chain else None
            if chain is None or base is None:
                return None
            return self._res.split(".".join([base, *chain[1:]]))
        if isinstance(node, ast.Call) and node.args and (_chain(node.func) or ("",))[-1] in {"import_module", "__import__"}:
            text = self._str_value(node.args[0])
            return self._res.split(text) if text else None
        if isinstance(node, ast.Subscript) and _chain(node.value) == ("sys", "modules"):
            text = self._str_value(node.slice)
            return self._res.split(text) if text else None
        return None

    # -- recording --------------------------------------------------------- #

    def _emit(self, node: ast.expr | ast.stmt, module: str, attr: str, form: str) -> None:
        bucket = self._res.bucket(module, attr or _MODULE_ATTR)
        if bucket is not None:
            self.sites.append(PatchSite(self._rel, node.lineno, module, attr or _MODULE_ATTR, form, bucket))

    def _unresolved(self, node: ast.expr | ast.stmt, form: str, *, suspect: bool = False) -> None:
        text = ast.unparse(node)
        key = (node.lineno, form, text)
        if key in self._seen_unresolved:  # a literal loop / parametrize body is visited once per row
            return
        self._seen_unresolved.add(key)
        flagged = suspect or (isinstance(node, ast.Call) and self._target_depends_on_family(node, form))
        self.unresolved.append(UnresolvedSite(self._rel, node.lineno, text[:160], form, flagged))

    def _target_depends_on_family(self, node: ast.Call, form: str) -> bool:
        """Whether the target expression itself (not the rest of the file) references the family."""
        single = form in {"patch", "patch.multiple"}
        parts: list[ast.expr] = list(node.args[: 1 if single else 2])
        parts.extend(kw.value for kw in node.keywords if kw.arg in _TARGET_KEYWORDS)
        return any(self._mentions_family(part) for part in parts)

    def _mentions_family(self, expr: ast.AST) -> bool:
        token = self._res.family_token
        for sub in ast.walk(expr):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str) and token in sub.value:
                return True
            if isinstance(sub, ast.Name) and self._name_is_family(sub.id):
                return True
        return False

    def _name_is_family(self, name: str) -> bool:
        if name in self._family_imports or self._has_name("tainted", name):
            return True
        const, alias = self._lookup("consts", name), self._lookup("aliases", name)
        return (const is not None and self._res.family_token in const) or (alias is not None and self._res.is_family(alias))

    def _emit_dotted(self, node: ast.expr | ast.stmt, dotted: str, form: str) -> None:
        module, attr = self._res.split(dotted)
        self._emit(node, module, attr, form)

    def _emit_object(self, node: ast.expr | ast.stmt, target: tuple[str, str], name: str, form: str) -> None:
        module, prefix = target
        self._emit(node, module, f"{prefix}.{name}" if prefix else name, form)

    # -- visiting ----------------------------------------------------------- #

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._scoped(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._scoped(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._scoped(node)

    def _scoped(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> None:
        self._scopes.append(_Scope())
        try:
            rows = self._parametrize_rows(node) if not isinstance(node, ast.ClassDef) else []
            if rows:
                self._visit_rows(node.body, rows)
            else:
                self.generic_visit(node)
        finally:
            self._scopes.pop()

    def visit_For(self, node: ast.For) -> None:
        self.visit(node.iter)
        names = _target_names(node.target)
        self._taint(names, node.iter)  # a row the literal cannot resolve may still target the family
        rows = self._literal_rows(node.iter, names)
        if rows:
            self._visit_rows(node.body, rows)
        else:
            for stmt in node.body:
                self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)

    def _visit_rows(self, body: Sequence[ast.stmt], rows: list[dict[str, str]]) -> None:
        """Visit ``body`` once per resolved row, with the row's string bindings as constants."""
        for row in rows:
            self._scopes.append(_Scope(consts=dict(row)))
            try:
                for stmt in body:
                    self.visit(stmt)
            finally:
                self._scopes.pop()

    def _taint(self, names: Sequence[str], iterable: ast.expr) -> None:
        if self._mentions_family(iterable) or self._literal_mentions_family(iterable):
            self._scopes[-1].tainted.update(names)

    def _literal_mentions_family(self, node: ast.expr) -> bool:
        literal = self._literal_node(node)
        return literal is not None and self._mentions_family(literal)

    def _literal_node(self, node: ast.expr) -> ast.expr | None:
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"items", "keys", "values"}:
            node = node.func.value
        if isinstance(node, ast.Name):
            for scope in reversed(self._scopes):
                if node.id in scope.literals:
                    return scope.literals[node.id]
            return None
        return node if isinstance(node, (ast.List, ast.Tuple, ast.Dict)) else None

    def _literal_rows(self, iterable: ast.expr, names: Sequence[str]) -> list[dict[str, str]]:
        """Per-iteration string bindings of ``names`` over a literal list/tuple/dict, or ``[]``."""
        literal = self._literal_node(iterable)
        if literal is None:
            return []
        method = iterable.func.attr if isinstance(iterable, ast.Call) and isinstance(iterable.func, ast.Attribute) else None
        if isinstance(literal, ast.Dict):
            if any(k is None for k in literal.keys):
                return []
            items: list[ast.expr] = (
                [ast.Tuple(elts=[k, v], ctx=ast.Load()) for k, v in zip(literal.keys, literal.values, strict=True) if k is not None]
                if method == "items"
                else list(literal.values if method == "values" else (k for k in literal.keys if k is not None))
            )
        elif isinstance(literal, (ast.List, ast.Tuple)):
            items = list(literal.elts)
        else:
            return []
        return self._rows_from(items, names)

    def _rows_from(self, items: Sequence[ast.expr], names: Sequence[str]) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for item in items:
            parts = _row_parts(item, len(names))
            row = {n: t for n, p in zip(names, parts, strict=False) if (t := self._str_value(p)) is not None}
            rows.append(row)
        return rows if any(rows) else []

    def _parametrize_rows(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[dict[str, str]]:
        per_decorator: list[list[dict[str, str]]] = []
        for deco in node.decorator_list:
            if not (isinstance(deco, ast.Call) and (_chain(deco.func) or ("",))[-1] == "parametrize" and len(deco.args) >= 2):
                continue
            names = _parametrize_names(deco.args[0])
            values = deco.args[1]
            self._taint(names, values)
            rows = self._rows_from(values.elts, names) if isinstance(values, (ast.List, ast.Tuple)) and names else []
            if rows:
                per_decorator.append(rows)
        if not per_decorator:
            return []
        product = itertools.islice(itertools.product(*per_decorator), _PARAM_ROW_CAP)
        return [{k: v for part in combo for k, v in part.items()} for combo in product]

    def visit_Import(self, node: ast.Import) -> None:
        self._bind_statement(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self._bind_statement(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        self.generic_visit(node)
        self._bind_statement(node)
        for target in node.targets:
            self._on_attribute_assignment(node, target)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self.generic_visit(node)
        self._on_attribute_assignment(node, node.target)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.generic_visit(node)
        if node.value is not None:
            self._on_attribute_assignment(node, node.target)

    def _on_attribute_assignment(self, stmt: ast.stmt, target: ast.expr) -> None:
        if not isinstance(target, ast.Attribute):
            return
        resolved = self._module_of(target)
        if resolved is not None and resolved[1]:
            self._emit(stmt, resolved[0], resolved[1], "assign")

    def visit_Call(self, node: ast.Call) -> None:
        self.generic_visit(node)
        kind = _call_kind(self._canonical_chain(node.func))
        if kind is None:
            return
        handler: Callable[[ast.Call], None] = {
            "setattr": self._on_setattr,
            "delattr": self._on_delattr,
            "setitem": self._on_setitem,
            "delitem": self._on_setitem,
            "patch": self._on_patch,
            "object": self._on_object,
            "multiple": self._on_multiple,
            "dict": self._on_dict,
        }[kind]
        handler(node)

    # -- call handlers ------------------------------------------------------ #

    def _string_target(self, node: ast.Call, target: ast.expr | None, form: str) -> bool:
        """Handle a dotted-string target. Returns ``True`` when ``target`` was a string."""
        if target is None:
            return False
        text = self._str_value(target)
        if text is None:
            return False
        if _DOTTED.match(text):
            self._emit_dotted(node, text, form)
        return True

    def _on_setattr(self, node: ast.Call) -> None:
        a = _bind(node, ("target", "name", "value"))
        target, name = a.get("target"), a.get("name")
        if target is None or name is None:
            return
        if "value" not in a:  # string form: setattr("pkg.mod.attr", value)
            if not self._string_target(node, target, "setattr"):
                self._unresolved(node, "setattr")
            return
        self._on_object_form(node, target, name, "setattr")

    def _on_delattr(self, node: ast.Call) -> None:
        a = _bind(node, ("target", "name"))
        target, name = a.get("target"), a.get("name")
        if target is None:
            return
        if self._string_target(node, target, "delattr"):
            return
        if name is not None:
            self._on_object_form(node, target, name, "delattr")
        else:
            self._unresolved(node, "delattr")

    def _on_object_form(self, node: ast.Call, target: ast.expr, name: ast.expr, form: str) -> None:
        resolved = self._module_of(target)
        if resolved is None:
            return
        text = self._str_value(name)
        if text is None:
            if self._res.may_target_family(resolved[0]):
                self._unresolved(node, form, suspect=True)
            return
        self._emit_object(node, resolved, text, form)

    def _on_patch(self, node: ast.Call) -> None:
        a = _bind(node, ("target",))
        target = a.get("target")
        if target is not None and not self._string_target(node, target, "patch"):
            self._unresolved(node, "patch")

    def _on_object(self, node: ast.Call) -> None:
        a = _bind(node, ("target", "attribute"))
        target, name = a.get("target"), a.get("attribute")
        if target is not None and name is not None:
            self._on_object_form(node, target, name, "patch.object")

    def _on_multiple(self, node: ast.Call) -> None:
        a = _bind(node, ("target",))
        target = a.get("target")
        if target is None:
            return
        names = [kw.arg for kw in node.keywords if kw.arg and kw.arg not in {"spec", "create", "spec_set", "autospec", "new_callable"}]
        text = self._str_value(target)
        resolved = self._module_of(target) if text is None else None
        if text is None and resolved is None:
            return
        for name in names:
            if text is not None:
                self._emit_dotted(node, f"{text}.{name}", "patch.multiple")
            elif resolved is not None:
                self._emit_object(node, resolved, name, "patch.multiple")

    def _on_setitem(self, node: ast.Call) -> None:
        a = _bind(node, ("dic", "name", "value"))
        dic, name = a.get("dic"), a.get("name")
        if dic is None or name is None:
            return
        text = self._str_value(name)
        if _is_sys_modules(dic):
            if text is not None:
                self._emit_dotted(node, text, "sys_modules")
            return
        module = self._dict_module(dic)
        if module is None:
            return
        if text is None:
            self._unresolved(node, "setitem", suspect=self._res.may_target_family(module))
            return
        self._emit(node, module, text, "setitem")

    def _dict_module(self, node: ast.expr) -> str | None:
        """Module whose ``__dict__`` an expression denotes (``vars(m)``, ``m.__dict__``)."""
        if isinstance(node, ast.Call) and _chain(node.func) == ("vars",) and node.args:
            resolved = self._module_of(node.args[0])
        elif isinstance(node, ast.Attribute) and node.attr == "__dict__":
            resolved = self._module_of(node.value)
        else:
            text = self._str_value(node)
            return self._res.split(text[: -len(_DICT_SUFFIX)])[0] if text and text.endswith(_DICT_SUFFIX) else None
        return resolved[0] if resolved is not None and not resolved[1] else None

    def _on_dict(self, node: ast.Call) -> None:
        a = _bind(node, ("in_dict", "values"))
        in_dict = a.get("in_dict")
        if in_dict is None:
            return
        keys = self._dict_keys(node, a.get("values"))
        if _is_sys_modules(in_dict):
            self._emit_dict_names(node, None, keys, "sys_modules")
            return
        module = self._dict_module(in_dict)
        if module is not None:
            self._emit_dict_names(node, module, keys, "patch.dict")
            return
        resolved = self._module_of(in_dict) or self._string_module(in_dict)
        if resolved is not None and resolved[1]:  # e.g. patch.dict(os.environ, ...)
            self._emit_object(node, (resolved[0], ""), resolved[1], "patch.dict")

    def _string_module(self, node: ast.expr) -> tuple[str, str] | None:
        text = self._str_value(node)
        return self._res.split(text) if text and _DOTTED.match(text) else None

    def _dict_keys(self, node: ast.Call, values: ast.expr | None) -> list[str] | None:
        keys = [kw.arg for kw in node.keywords if kw.arg and kw.arg not in {"values", "clear"}]
        if isinstance(values, ast.Dict):
            literal = [self._str_value(k) if k is not None else None for k in values.keys]
            if any(k is None for k in literal):
                return None
            keys.extend(k for k in literal if k is not None)
            return keys
        if isinstance(values, ast.Call) and _chain(values.func) == ("dict",):
            return [kw.arg for kw in values.keywords if kw.arg] or None
        return keys or None

    def _emit_dict_names(self, node: ast.Call, module: str | None, keys: list[str] | None, form: str) -> None:
        if keys is None:
            self._unresolved(node, form, suspect=module is None or self._res.may_target_family(module))
            return
        for key in keys:
            if module is None:
                self._emit_dotted(node, key, form)
            else:
                self._emit(node, module, key, form)


_TARGET_KEYWORDS = frozenset({"target", "attribute", "name", "dic", "in_dict"})


def _family_imported_names(tree: ast.Module, resolver: _Resolver) -> frozenset[str]:
    """Names a test file binds to the family module (or something imported from it) by an import."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            for a in node.names:
                if resolver.is_family(node.module) or resolver.is_family(f"{node.module}.{a.name}"):
                    names.add(a.asname or a.name)
        elif isinstance(node, ast.Import):
            names.update((a.asname or a.name.split(".")[0]) for a in node.names if resolver.is_family(a.name))
    return frozenset(names)


def _is_sys_modules(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return node.value == _SYS_MODULES
    return _chain(node) == ("sys", "modules")


#: The census self-test patches the facade on purpose; it is not part of the measured test suite.
DEFAULT_EXCLUDED_FILES: frozenset[str] = frozenset({"tests/_support/test_patch_census.py"})


def scan_static(
    tests_root: Path,
    *,
    family_prefix: str = DEFAULT_FAMILY_PREFIX,
    family_read_names: frozenset[str] | None = None,
    read_sources: Mapping[str, frozenset[str]] | None = None,
    src_root: Path | None = None,
    exclude_files: frozenset[str] = DEFAULT_EXCLUDED_FILES,
) -> CensusReport:
    """Count every static patch site that targets the family (and, when given, its read names).

    ``family_read_names`` (optionally with ``read_sources`` mapping each name to
    the modules it is imported from; see :func:`derive_family_reads`) enables the
    source, stdlib and other-namespace buckets. Paths in the report are relative
    to ``tests_root.parent``; ``exclude_files`` (relative paths) are not scanned.
    """
    root = tests_root.resolve()
    reads = FamilyReads(family_read_names or frozenset(), read_sources or {})
    resolver = _Resolver((src_root or root.parent / "src").resolve(), family_prefix, reads)
    sites: list[PatchSite] = []
    unresolved: list[UnresolvedSite] = []
    for path in sorted(root.rglob("*.py")):
        if path.relative_to(root.parent).as_posix() in exclude_files:
            continue
        scanner = _scan_file(path, root.parent, resolver)
        sites.extend(scanner.sites)
        unresolved.extend(scanner.unresolved)
    return CensusReport(tuple(sites), tuple(unresolved))


def _scan_file(path: Path, base: Path, resolver: _Resolver) -> _FileScanner:
    """Scan one test source; an unparseable file fails the census closed rather than vanishing from it."""
    source, tree = read_and_parse(path)
    scanner = _FileScanner(path.relative_to(base).as_posix(), source, resolver, tree)
    scanner.run()
    return scanner


def patched_names_on(module: str, tests_root: Path, *, src_root: Path | None = None) -> frozenset[str]:
    """Attribute names patched on exactly ``module`` (first chain segment).

    ``subprocess.run`` patched through ``module`` yields ``subprocess``. The family
    routing check uses this for set equality between the facade's patched names and its routing table.
    Callers must filter ``subprocess``: it is a process-global stdlib patch, which
    the routing rule excludes from the routing set. Placeholder entries (``<module>`` for a
    whole-module ``sys.modules`` patch, ``<dynamic>``) are never returned.
    """
    report = scan_static(tests_root, family_prefix=module, src_root=src_root)
    return frozenset(s.name for s in report.sites if s.module == module and not s.name.startswith("<"))


# --------------------------------------------------------------------------- #
# Runtime counter (opt-in pytest plugin)
# --------------------------------------------------------------------------- #

_NOTSET = object()


@dataclass
class _RuntimeState:
    resolver: _Resolver
    current: str | None = None
    by_name: Counter[str] = field(default_factory=Counter)
    by_bucket: Counter[str] = field(default_factory=Counter)
    by_test: Counter[str] = field(default_factory=Counter)
    outcomes: Counter[str] = field(default_factory=Counter)
    collected: int = 0

    def record(self, module: str, attr: str) -> None:
        bucket = self.resolver.bucket(module, attr or _MODULE_ATTR)
        if bucket is None:
            return
        self.by_name[attr or _MODULE_ATTR] += 1
        self.by_bucket[bucket] += 1
        self.by_test[self.current or "<outside-test>"] += 1

    def record_dotted(self, dotted: str) -> None:
        module, attr = self.resolver.split(dotted)
        self.record(module, attr)

    def record_object(self, target: object, name: str) -> None:
        module, prefix = _describe_target(target)
        self.record(module, f"{prefix}.{name}" if prefix else name)

    def to_json(self) -> dict[str, Any]:
        return {
            "applications_total": sum(self.by_bucket.values()),
            "budget_applications": _budget(self.by_bucket),
            "by_name": dict(self.by_name.most_common()),
            "by_bucket": dict(self.by_bucket),
            "tests_with_patches": len({t for t in self.by_test if t != "<outside-test>"}),
            "by_test": dict(self.by_test.most_common()),
            "collected_tests": self.collected,
            "outcomes": dict(self.outcomes),
        }


def _budget(by_bucket: Mapping[str, int]) -> int:
    """Runtime patch-budget number: family + source applications only (stdlib and other namespaces are outside it)."""
    return int(by_bucket.get(BUCKET_FAMILY, 0)) + int(by_bucket.get(BUCKET_SOURCE, 0))


def _describe_target(target: object) -> tuple[str, str]:
    if isinstance(target, ModuleType):
        return target.__name__, ""
    if isinstance(target, type):
        return target.__module__, target.__qualname__
    owner = getattr(target, "__module__", None)
    if isinstance(owner, str):
        return owner, str(getattr(target, "__qualname__", ""))
    kind = type(target)
    return kind.__module__, kind.__qualname__


def _arg(args: tuple[Any, ...], kwargs: dict[str, Any], index: int, key: str) -> Any:
    if len(args) > index:
        return args[index]
    return kwargs.get(key, _NOTSET)


class _TaggedGetter:
    """A mock target getter that also remembers the dotted module string it was built from."""

    def __init__(self, getter: Callable[[], Any], census_target: str) -> None:
        self._getter = getter
        self.census_target = census_target

    def __call__(self) -> Any:
        return self._getter()


class _Installer:
    """Installs and exactly restores the recording wrappers."""

    def __init__(self, state: _RuntimeState) -> None:
        self._state = state
        self._saved: list[tuple[Any, str, Any]] = []

    def _swap(self, owner: Any, name: str, replacement: Any) -> None:
        self._saved.append((owner, name, getattr(owner, name)))
        setattr(owner, name, replacement)

    def install(self) -> None:
        mp = pytest.MonkeyPatch
        self._wrap_monkeypatch(mp)
        self._wrap_mock_enter()
        self._wrap_mock_dict()
        self._wrap_target_capture()

    def uninstall(self) -> None:
        for owner, name, original in reversed(self._saved):
            setattr(owner, name, original)
        self._saved.clear()

    def _wrap_monkeypatch(self, mp: type[pytest.MonkeyPatch]) -> None:
        state = self._state
        original_setattr, original_delattr, original_setitem = mp.setattr, mp.delattr, mp.setitem

        def setattr_(self: Any, *args: Any, **kwargs: Any) -> Any:
            result = original_setattr(self, *args, **kwargs)
            target, name = _arg(args, kwargs, 0, "target"), _arg(args, kwargs, 1, "name")
            if _arg(args, kwargs, 2, "value") is _NOTSET and isinstance(target, str):
                state.record_dotted(target)
            elif isinstance(name, str):
                state.record_object(target, name)
            return result

        def delattr_(self: Any, *args: Any, **kwargs: Any) -> Any:
            result = original_delattr(self, *args, **kwargs)
            target, name = _arg(args, kwargs, 0, "target"), _arg(args, kwargs, 1, "name")
            if name is _NOTSET and isinstance(target, str):
                state.record_dotted(target)
            elif isinstance(name, str):
                state.record_object(target, name)
            return result

        def setitem_(self: Any, *args: Any, **kwargs: Any) -> Any:
            result = original_setitem(self, *args, **kwargs)
            _record_dict_item(state, _arg(args, kwargs, 0, "dic"), _arg(args, kwargs, 1, "name"))
            return result

        self._swap(mp, "setattr", setattr_)
        self._swap(mp, "delattr", delattr_)
        self._swap(mp, "setitem", setitem_)

    def _wrap_mock_enter(self) -> None:
        state = self._state
        original = _mock._patch.__enter__

        def enter(self: Any) -> Any:
            result = original(self)
            dotted = getattr(self, "census_target", None) or getattr(self.getter, "census_target", None)
            if isinstance(dotted, str):
                state.record_dotted(f"{dotted}.{self.attribute}")
            else:
                state.record_object(self.target, str(self.attribute))
            return result

        self._swap(_mock._patch, "__enter__", enter)

    def _wrap_mock_dict(self) -> None:
        state = self._state
        original = _mock._patch_dict.__enter__

        def enter(self: Any) -> Any:
            result = original(self)
            values = self.values if isinstance(self.values, Mapping) else {}
            _record_patch_dict(state, self.in_dict, [str(k) for k in values])
            return result

        self._swap(_mock._patch_dict, "__enter__", enter)

    def _wrap_target_capture(self) -> None:
        """Remember the dotted string a ``patch("a.b.c")`` / ``patch.multiple("a.b")`` was given."""
        module_vars = vars(_mock)
        original_get_target = module_vars["_get_target"]
        original_multiple = _mock.patch.multiple

        def get_target(target: str) -> Any:
            getter, attribute = original_get_target(target)
            dotted = target.rpartition(".")[0]

            return _TaggedGetter(getter, dotted), attribute

        def multiple(target: Any, *args: Any, **kwargs: Any) -> Any:
            patcher = original_multiple(target, *args, **kwargs)
            if isinstance(target, str):
                for each in (patcher, *getattr(patcher, "additional_patchers", ())):
                    each.census_target = target
            return patcher

        self._swap(_mock, "_get_target", get_target)
        self._swap(_mock.patch, "multiple", multiple)


def _record_dict_item(state: _RuntimeState, dic: object, name: object) -> None:
    if not isinstance(name, str) or not isinstance(dic, dict):
        return
    if dic is sys.modules:
        state.record_dotted(name)
    elif isinstance(dic.get("__name__"), str) and "__spec__" in dic:
        state.record(dic["__name__"], name)


def _record_patch_dict(state: _RuntimeState, in_dict: object, keys: list[str]) -> None:
    if isinstance(in_dict, str):
        if in_dict == _SYS_MODULES:
            in_dict = sys.modules
        elif in_dict.endswith(_DICT_SUFFIX):
            for key in keys:
                state.record(state.resolver.split(in_dict[: -len(_DICT_SUFFIX)])[0], key)
            return
        else:
            state.record_dotted(in_dict)
            return
    for key in keys:
        _record_dict_item(state, in_dict, key)


_STATE: _RuntimeState | None = None
_INSTALLER: _Installer | None = None


def _out_path(config: pytest.Config) -> Path | None:
    raw = os.environ.get(ENV_OUT)
    if not raw:
        return None
    worker = getattr(config, "workerinput", {}).get("workerid")
    return Path(f"{raw}.{worker}.json") if worker else Path(raw)


def _is_xdist_controller(config: pytest.Config) -> bool:
    return not hasattr(config, "workerinput") and bool(getattr(config.option, "numprocesses", 0))


def pytest_configure(config: pytest.Config) -> None:
    global _STATE, _INSTALLER
    reads = derive_family_reads(_REPO_ROOT / "src")
    resolver = _Resolver(_REPO_ROOT / "src", DEFAULT_FAMILY_PREFIX, reads)
    _STATE = _RuntimeState(resolver)
    _INSTALLER = _Installer(_STATE)
    if not _is_xdist_controller(config):
        _INSTALLER.install()


def pytest_unconfigure(config: pytest.Config) -> None:
    global _STATE, _INSTALLER
    if _INSTALLER is not None:
        _INSTALLER.uninstall()
    _STATE = _INSTALLER = None


@pytest.hookimpl(wrapper=True)
def pytest_runtest_protocol(item: pytest.Item, nextitem: pytest.Item | None) -> Iterator[None]:
    if _STATE is not None:
        _STATE.current = item.nodeid
    try:
        return (yield)
    finally:
        if _STATE is not None:
            _STATE.current = None


def pytest_collection_finish(session: pytest.Session) -> None:
    if _STATE is not None:
        _STATE.collected = len(session.items)


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if _STATE is not None and (report.when == "call" or report.outcome != "passed"):
        _STATE.outcomes[f"{report.when}:{report.outcome}"] += 1


def pytest_sessionfinish(session: pytest.Session) -> None:
    out = _out_path(session.config)
    if _STATE is None or out is None or _is_xdist_controller(session.config):
        return
    out.write_text(json.dumps(_STATE.to_json(), indent=1), encoding="utf-8")


def load_runtime(path: Path) -> dict[str, Any]:
    """Merge ``path`` and every per-worker ``path.<worker>.json`` into one summary."""
    parts = [json.loads(p.read_text(encoding="utf-8")) for p in sorted([path, *path.parent.glob(f"{path.name}.*.json")]) if p.is_file()]
    merged: dict[str, Any] = {
        "applications_total": 0,
        "by_name": Counter(),
        "by_bucket": Counter(),
        "by_test": Counter(),
        "outcomes": Counter(),
        "collected_tests": 0,
        "workers": len(parts),
    }
    for part in parts:
        merged["applications_total"] += part["applications_total"]
        for key in ("by_name", "by_bucket", "by_test", "outcomes"):
            merged[key].update(part[key])
        merged["collected_tests"] = max(merged["collected_tests"], part["collected_tests"])
    merged["budget_applications"] = _budget(merged["by_bucket"])
    merged["tests_with_patches"] = len({t for t in merged["by_test"] if t != "<outside-test>"})
    return {k: (dict(v.most_common()) if isinstance(v, Counter) else v) for k, v in merged.items()}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


_APPENDIX_MARKER = "## Appendix — covering test set"


def _read_file_list(path: Path) -> list[str]:
    """``tests/...`` paths from a text file, or from the covering-set appendix of a markdown file."""
    text = path.read_text(encoding="utf-8")
    if _APPENDIX_MARKER in text:
        text = text.split(_APPENDIX_MARKER, 1)[1].split("```")[1] if text.count("```", text.index(_APPENDIX_MARKER)) >= 2 else text
    return [line.strip() for line in text.splitlines() if line.strip().startswith("tests/")]


def _top(counter: Mapping[str, int], limit: int = 25) -> list[str]:
    ranked = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    return [f"    {n:4d}  {k}" for k, n in ranked[:limit]] + ([f"    ... {len(ranked) - limit} more"] if len(ranked) > limit else [])


def format_report(report: CensusReport, source_report: CensusReport, files_note: str) -> str:
    """Human-readable static report. ``source_report`` is the (possibly file-restricted) view for buckets b/c."""
    lines = ["STATIC PATCH CENSUS (reporting tool, not a gate)", ""]
    lines.append(f"family facade sites (bucket a, whole tree): {report.count(BUCKET_FAMILY)}")
    lines.append(f"  files: {len(report.by_file(BUCKET_FAMILY))}   distinct names: {len(report.by_name(BUCKET_FAMILY))}")
    lines.append(f"  forms: {dict(report.by_form(BUCKET_FAMILY))}")
    lines.append("  by name:")
    lines.extend(_top(report.by_name(BUCKET_FAMILY)))
    lines.append("  by namespace:")
    lines.extend(_top(report.by_namespace(BUCKET_FAMILY)))
    lines.append("  by file:")
    lines.extend(_top(report.by_file(BUCKET_FAMILY)))
    lines.append(
        f"whole tree, other buckets: source {report.count(BUCKET_SOURCE)}, stdlib {report.count(BUCKET_STDLIB)}, "
        f"unrelated-namespace same-name {report.count(BUCKET_OTHER)}"
    )
    lines.append("")
    lines.append(f"source-namespace sites (bucket b, {files_note}): {source_report.count(BUCKET_SOURCE)}")
    lines.append("  by namespace:")
    lines.extend(_top(source_report.by_namespace(BUCKET_SOURCE)))
    lines.append("  by name:")
    lines.extend(_top(source_report.by_name(BUCKET_SOURCE)))
    lines.append("")
    lines.append(f"stdlib process-global sites (own bucket, outside the budget; {files_note}): {source_report.count(BUCKET_STDLIB)}")
    lines.extend(_top(source_report.by_name(BUCKET_STDLIB)))
    lines.append(f"same-name patches on unrelated namespaces (not budgeted; {files_note}): {source_report.count(BUCKET_OTHER)}")
    lines.append("")
    suspects = report.family_targeting_unresolved()
    lines.append(f"unresolved patch targets (whole tree): {len(report.unresolved)}; that may target the family: {len(suspects)}")
    lines.extend(f"    {u.file}:{u.line}  [{u.form}] {u.expr}" for u in suspects)
    return "\n".join(lines)


def format_runtime(runtime: Mapping[str, Any]) -> str:
    buckets = runtime.get("by_bucket", {})
    by_test = runtime.get("by_test", {})
    lines = [
        "RUNTIME PATCH APPLICATIONS",
        f"collected tests: {runtime['collected_tests']}   outcomes: {runtime.get('outcomes', {})}",
        f"patch budget applications (family + source): {_budget(buckets)}",
        f"applications total (all buckets, informational): {runtime['applications_total']}   by bucket: {buckets}",
        f"tests with patches: {runtime['tests_with_patches']}   max in one test: {max(by_test.values(), default=0)}",
        "  by name:",
        *_top(runtime["by_name"]),
    ]
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m tests._support.patch_census", description=__doc__.split("\n")[0] if __doc__ else "")
    parser.add_argument("--report", action="store_true", help="print the static census")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--tests-root", type=Path, default=_REPO_ROOT / "tests")
    parser.add_argument("--family-prefix", default=DEFAULT_FAMILY_PREFIX)
    parser.add_argument("--files", nargs="*", default=[], help="repo-relative test files for the source-namespace count")
    parser.add_argument("--files-from", type=Path, help="text/markdown file listing tests/... paths (e.g. the covering-set appendix)")
    parser.add_argument("--runtime", type=Path, help="merge and print the runtime JSON written via " + ENV_OUT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if not args.report and args.runtime is None:
        print("nothing to do: pass --report and/or --runtime PATH", file=sys.stderr)
        return 2
    out: dict[str, Any] = {}
    text: list[str] = []
    if args.report:
        src = args.tests_root.resolve().parent / "src"
        reads = derive_family_reads(src, args.family_prefix)
        report = scan_static(args.tests_root, family_prefix=args.family_prefix, family_read_names=reads.names, read_sources=reads.sources)
        files = [*args.files, *(_read_file_list(args.files_from) if args.files_from else [])]
        view = report.restricted_to(files) if files else report
        note = f"{len(files)}-file list" if files else "whole tree"
        out["static"] = {**report.summary(), "source_view": view.summary(), "source_view_files": len(files)}
        text.append(format_report(report, view, note))
    if args.runtime is not None:
        runtime = load_runtime(args.runtime)
        out["runtime"] = runtime
        text.append(format_runtime(runtime))
    print(json.dumps(out, indent=1) if args.json else "\n\n".join(text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
