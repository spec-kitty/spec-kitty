"""Detector — manual global-state mutation over ``tests/``.

Five targets: cwd (``os.chdir``/``os.fchdir``), ``sys.path``, ``sys.modules``,
``os.environ`` (+ ``os.putenv``/``os.unsetenv``), ``sys.argv``. Forms: mutating
method call, subscript/slice store, subscript ``del``, augassign, rebind
(assign/annassign/``del`` of the attribute), ``setattr``/``delattr(sys|os,
"<attr>", ...)``.

Alias resolution: ``import os as _o``, ``import sys as _s``, ``from os import
chdir, environ``, ``from sys import path, modules, argv``, and
flow-insensitive local rebinding (``env = os.environ``).

Excluded (owned by an existing gate): ``SPEC_KITTY_HOME`` writes matched by
``_home_pin_scan.find_write_sites`` (reused, never re-implemented). Never
matches ``patch.dict(...)`` / ``monkeypatch.*`` / ``MonkeyPatch.context`` /
``contextlib.chdir`` / ``mock.patch.*`` / reads, because their receiver is not
a target object. ``patch.dict(sys.modules, ...)`` specifically is its own
banned sub-class, owned and enforced by
``tests/architectural/test_no_sys_modules_patch_dict.py`` -- not by this
detector.

This module reproduces a hand-verified classification of every manual
global-state mutation site under ``tests/``. See
``tests/architectural/test_home_pin_seam_no_second_copy.py``: any module
importing ``_home_pin_scan`` must hold zero ``ast.parse`` calls and zero
``ast.NodeVisitor``/``NodeTransformer`` subclasses — hence parsing always
routes through ``_home_pin_scan.parse_module`` and the walk is a plain
``ast.walk`` over a list, never a visitor class.
"""

from __future__ import annotations

import ast as _ast
import re
from dataclasses import dataclass
from pathlib import Path

from specify_cli.contracts.anchoring import _build_qualname_map, code_tokens_by_line
from tests.architectural import _home_pin_scan as home

#: An explicit, reviewed list of file globs excluded from the walk because
#: they hold fixture data that is deliberately unparseable (never a way to
#: dodge a real site). Empty today — no such fixture directory exists yet;
#: add an entry only with a comment naming why that file cannot parse.
FIXTURE_DATA_EXCLUSIONS: tuple[str, ...] = ()

#: The four attribute targets, keyed by ``(module, attribute)`` -> display kind.
_TARGET_ATTRS: dict[tuple[str, str], str] = {
    ("os", "environ"): "os.environ",
    ("sys", "path"): "sys.path",
    ("sys", "modules"): "sys.modules",
    ("sys", "argv"): "sys.argv",
}
#: The two ``cwd``-mutating free functions.
_CWD_FUNCS: frozenset[tuple[str, str]] = frozenset({("os", "chdir"), ("os", "fchdir")})
#: The two ``os.environ``-mutating free functions.
_ENV_FUNCS: frozenset[tuple[str, str]] = frozenset({("os", "putenv"), ("os", "unsetenv")})
#: Mutating attribute-call method names, per target kind.
_MUTATORS: dict[str, frozenset[str]] = {
    "os.environ": frozenset({"update", "pop", "setdefault", "clear", "popitem", "__setitem__", "__delitem__", "__ior__"}),
    "sys.modules": frozenset({"update", "pop", "setdefault", "clear", "popitem", "__setitem__", "__delitem__", "__ior__"}),
    "sys.path": frozenset(
        {
            "insert",
            "append",
            "extend",
            "remove",
            "pop",
            "clear",
            "reverse",
            "sort",
            "__setitem__",
            "__delitem__",
            "__iadd__",
        }
    ),
    "sys.argv": frozenset(
        {
            "insert",
            "append",
            "extend",
            "remove",
            "pop",
            "clear",
            "reverse",
            "sort",
            "__setitem__",
            "__delitem__",
            "__iadd__",
        }
    ),
}
#: The gate's scoped-replacement message per kind (contract "Scoped replacements").
_REPLACEMENT: dict[str, str] = {
    "cwd": "monkeypatch.chdir(...) or contextlib.chdir(...) for block scope",
    "os.environ": "monkeypatch.setenv/delenv(...) or mock.patch.dict(os.environ, ...)",
    "sys.path": "monkeypatch.syspath_prepend(...) or remove (rootdir + pythonpath=src already cover repo/src)",
    "sys.modules": "monkeypatch.setitem/delitem(sys.modules, ..., raising=False) (+ parent-package attribute)",
    "sys.argv": "monkeypatch.setattr(sys, 'argv', [...]) or mock.patch.object(sys, 'argv', [...])",
}

#: A cheap textual prefilter: only files that plausibly bind ``os``/``sys`` at
#: all can ever resolve a target — this is what keeps the run fast (measured
#: ~3.9s over the whole tree).
_IMPORT_RE = re.compile(
    r"^[ \t]*(?:import[ \t]+(?:[\w.]+[ \t]*(?:as[ \t]+\w+)?[ \t]*,[ \t]*)*(?:os|sys)\b"
    r"|from[ \t]+(?:os|sys)[ \t]+import)",
    re.M,
)
_CANDIDATE_NODE_TYPES = (_ast.Call, _ast.Assign, _ast.AnnAssign, _ast.AugAssign, _ast.Delete)


@dataclass(frozen=True)
class Site:
    """One manual global-state mutation site."""

    file: str
    qualname: str
    kind: str
    form: str
    lineno: int
    token_line: str


#: ``(file, qualname, kind)`` — the allowlist row identity. Never includes a
#: line number: a site's identity must survive a blank-line insertion
#: elsewhere in the same scope.
SiteKey = tuple[str, str, str]


@dataclass(frozen=True)
class ScanResult:
    """The outcome of one :func:`scan` call."""

    sites: tuple[Site, ...]
    parse_failures: tuple[tuple[str, str], ...]
    scanned_files: int


def site_key(site: Site) -> SiteKey:
    """The allowlist row identity for ``site``."""
    return (site.file, site.qualname, site.kind)


def replacement_for(kind: str) -> str:
    """The scoped-replacement message for ``kind`` (contract "Scoped replacements")."""
    return _REPLACEMENT[kind]


class _Bindings:
    """Per-file alias resolution: local names bound to ``os``/``sys``, to a
    target object (``os.environ``, ...), or to a mutating free function.

    Deliberately not an ``ast.NodeVisitor`` subclass (banned in any module
    importing ``_home_pin_scan`` — see the module docstring): built from a
    single ``ast.walk`` node list the caller already collected.
    """

    def __init__(self, nodes: list[_ast.AST]) -> None:
        self.mod: dict[str, str] = {}
        self.obj: dict[str, str] = {}
        self.func: dict[str, tuple[str, str]] = {}
        for node in nodes:
            self._bind_import(node)
        for node in nodes:
            self._bind_local_alias(node)

    def _bind_import(self, node: _ast.AST) -> None:
        if isinstance(node, _ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in ("os", "sys") and (alias.asname is None or alias.name in ("os", "sys")):
                    self.mod[alias.asname or root] = root
        elif isinstance(node, _ast.ImportFrom) and node.module in ("os", "sys") and node.level == 0:
            for alias in node.names:
                bound = alias.asname or alias.name
                key = (node.module, alias.name)
                if key in _TARGET_ATTRS:
                    self.obj[bound] = _TARGET_ATTRS[key]
                elif key in _CWD_FUNCS or key in _ENV_FUNCS:
                    self.func[bound] = key

    def _bind_local_alias(self, node: _ast.AST) -> None:
        # Flow-insensitive local aliasing: ``NAME = os.environ``.
        if not (isinstance(node, _ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], _ast.Name)):
            return
        target = self.target_of(node.value)
        if target is not None:
            self.obj.setdefault(node.targets[0].id, target)

    def target_of(self, node: _ast.AST) -> str | None:
        if isinstance(node, _ast.Attribute) and isinstance(node.value, _ast.Name):
            module = self.mod.get(node.value.id)
            if module is not None:
                return _TARGET_ATTRS.get((module, node.attr))
        if isinstance(node, _ast.Name):
            return self.obj.get(node.id)
        return None

    def func_of(self, node: _ast.AST) -> tuple[str, str] | None:
        if isinstance(node, _ast.Attribute) and isinstance(node.value, _ast.Name):
            module = self.mod.get(node.value.id)
            if module is not None and ((module, node.attr) in _CWD_FUNCS or (module, node.attr) in _ENV_FUNCS):
                return (module, node.attr)
        if isinstance(node, _ast.Name):
            return self.func.get(node.id)
        return None

    def module_of(self, node: _ast.AST) -> str | None:
        return self.mod.get(node.id) if isinstance(node, _ast.Name) else None


def _classify_call(node: _ast.Call, bindings: _Bindings) -> list[tuple[str, str]]:
    """Classify one ``ast.Call`` node: a free-function call, a mutating
    attribute-method call, or a ``setattr``/``delattr(sys|os, ...)`` call."""
    hits: list[tuple[str, str]] = []
    func = bindings.func_of(node.func)
    if func is not None:
        hits.append(("cwd" if func in _CWD_FUNCS else "os.environ", f"call:{func[0]}.{func[1]}"))
    elif isinstance(node.func, _ast.Attribute):
        target = bindings.target_of(node.func.value)
        if target is not None and node.func.attr in _MUTATORS[target]:
            hits.append((target, f"call:.{node.func.attr}"))
    if isinstance(node.func, _ast.Name) and node.func.id in ("setattr", "delattr") and len(node.args) >= 2:
        module = bindings.module_of(node.args[0])
        attr_arg = node.args[1]
        if module and isinstance(attr_arg, _ast.Constant) and isinstance(attr_arg.value, str):
            target = _TARGET_ATTRS.get((module, attr_arg.value))
            if target or (module, attr_arg.value) in _CWD_FUNCS:
                hits.append((target or "cwd", node.func.id))
    return hits


def _flatten_targets(targets: list[_ast.expr]) -> list[_ast.expr]:
    """Expand ``a, (b, c) = ...``-style tuple/list targets into their leaves."""
    flat: list[_ast.expr] = []
    for target in targets:
        if isinstance(target, (_ast.Tuple, _ast.List)):
            flat.extend(_flatten_targets(list(target.elts)))
        else:
            flat.append(target)
    return flat


_VERB_BY_NODE_TYPE: dict[type[_ast.AST], str] = {
    _ast.Assign: "store",
    _ast.AnnAssign: "store",
    _ast.AugAssign: "augassign",
    _ast.Delete: "del",
}


def _classify_mutation(node: _ast.Assign | _ast.AnnAssign | _ast.AugAssign | _ast.Delete, bindings: _Bindings) -> list[tuple[str, str]]:
    """Classify one assign/annassign/augassign/delete node's target(s)."""
    targets: list[_ast.expr] = list(node.targets) if isinstance(node, (_ast.Assign, _ast.Delete)) else [node.target]
    verb = _VERB_BY_NODE_TYPE[type(node)]
    hits: list[tuple[str, str]] = []
    for leaf in _flatten_targets(targets):
        hits.extend(_classify_mutation_leaf(leaf, node, bindings, verb))
    return hits


def _classify_mutation_leaf(
    leaf: _ast.expr,
    node: _ast.Assign | _ast.AnnAssign | _ast.AugAssign | _ast.Delete,
    bindings: _Bindings,
    verb: str,
) -> list[tuple[str, str]]:
    if isinstance(leaf, _ast.Subscript):
        target = bindings.target_of(leaf.value)
        if target is None:
            return []
        shape = "slice" if isinstance(leaf.slice, _ast.Slice) else "subscript"
        return [(target, f"{shape}-{verb}")]
    if isinstance(leaf, _ast.Attribute):
        module = bindings.module_of(leaf.value)
        if module is None:
            return []
        target = _TARGET_ATTRS.get((module, leaf.attr))
        return [(target, f"rebind-{verb}")] if target else []
    if isinstance(leaf, _ast.Name) and isinstance(node, _ast.AugAssign):
        target = bindings.target_of(leaf)
        return [(target, "augassign-name")] if target is not None else []
    return []


def _classify(node: _ast.AST, bindings: _Bindings) -> list[tuple[str, str]]:
    """Classify one candidate node into zero or more ``(kind, form)`` hits."""
    if isinstance(node, _ast.Call):
        return _classify_call(node, bindings)
    if isinstance(node, (_ast.Assign, _ast.AnnAssign, _ast.AugAssign, _ast.Delete)):
        return _classify_mutation(node, bindings)
    return []


def _qualname_at(qualname_map: dict[tuple[int, int], str], lineno: int) -> str:
    """The innermost qualname whose span contains ``lineno``, else ``"<module>"``."""
    candidates = [(end - start, qn) for (start, end), qn in qualname_map.items() if start <= lineno <= end]
    return min(candidates)[1] if candidates else "<module>"


def _is_excluded(relpath: str) -> bool:
    return any(relpath == pattern or Path(relpath).match(pattern) for pattern in FIXTURE_DATA_EXCLUSIONS)


def _home_owned_node_ids(tree: _ast.Module, source: str) -> frozenset[int]:
    """``id()`` of every AST node that itself constitutes a ``SPEC_KITTY_HOME``
    write recognised by ``_home_pin_scan.find_write_sites`` -- the owning
    ``environ[...] = ...`` assign, or the ``setenv``/``setdefault`` call,
    never its line.

    Matched by object identity through ``WriteSite.value`` (the value
    expression every write form carries) against the SAME parsed ``tree`` --
    never a second copy of the ownership predicate. Node identity (rather
    than line number) is what keeps a sibling mutation sharing the write's
    source line correctly un-excluded, e.g.
    ``os.environ["SPEC_KITTY_HOME"] = os.environ.pop("OTHER")``: the outer
    assign's node matches (owned), but the nested ``.pop("OTHER")`` call is a
    distinct node on the same line and is never touched by this set.
    """
    if home.NEEDLE not in source:
        return frozenset()
    sites = home.find_write_sites(tree, key=home.NEEDLE)
    if not sites:
        return frozenset()
    site_value_ids = {id(site.value) for site in sites}
    owned: set[int] = set()
    for node in _ast.walk(tree):
        is_owned_assign = isinstance(node, _ast.Assign) and id(node.value) in site_value_ids
        is_owned_call = isinstance(node, _ast.Call) and len(node.args) >= 2 and id(node.args[1]) in site_value_ids
        if is_owned_assign or is_owned_call:
            owned.add(id(node))
    return frozenset(owned)


def scan_file(path: Path, root: Path) -> list[Site]:
    """Every manual global-state mutation site in ``path``.

    Parses via ``_home_pin_scan.parse_module`` (propagates ``SyntaxError`` —
    EVERY non-excluded file is parsed) before the cheap textual prefilter
    decides whether the (more expensive) alias/qualname machinery runs at
    all.
    """
    source = path.read_text(encoding="utf-8")
    tree = home.parse_module(path)
    if not _IMPORT_RE.search(source):
        return []  # sound: every resolvable target needs an os/sys import binding
    nodes = list(_ast.walk(tree))
    bindings = _Bindings(nodes)
    if not (bindings.mod or bindings.obj or bindings.func):
        return []
    home_owned_ids = _home_owned_node_ids(tree, source)
    qualname_map = _build_qualname_map(tree)
    tokens: dict[int, str] | None = None
    rel = path.relative_to(root).as_posix()
    sites: list[Site] = []
    for node in nodes:
        if not isinstance(node, _CANDIDATE_NODE_TYPES):
            continue
        hits = _classify(node, bindings)
        if not hits:
            continue
        if id(node) in home_owned_ids:
            continue  # owned by _home_pin_scan (setenv / environ[k]= / .setdefault)
        lineno = node.lineno
        if tokens is None:
            tokens = code_tokens_by_line(source)
        for kind, form in hits:
            sites.append(Site(rel, _qualname_at(qualname_map, lineno), kind, form, lineno, tokens.get(lineno, "")))
    return sites


def scan(root: Path) -> ScanResult:
    """Scan every non-excluded ``*.py`` file under ``root / "tests"``."""
    tests_dir = root / "tests"
    all_files = sorted(p for p in tests_dir.rglob("*.py") if "__pycache__" not in p.parts)
    files = [p for p in all_files if not _is_excluded(p.relative_to(root).as_posix())]
    sites: list[Site] = []
    failures: list[tuple[str, str]] = []
    for path in files:
        try:
            sites.extend(scan_file(path, root))
        except SyntaxError as exc:
            failures.append((path.relative_to(root).as_posix(), f"{type(exc).__name__}: {exc}"))
    return ScanResult(tuple(sites), tuple(failures), len(files))
