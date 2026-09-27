"""PROTOTYPE (FR-007) — manual global-state mutation detector over tests/.

Five targets: cwd (os.chdir/fchdir), sys.path, sys.modules, os.environ (+ putenv/unsetenv),
sys.argv. Forms: mutating method call, subscript/slice store, subscript del, augassign,
rebind (assign/annassign/del of the attribute), setattr/delattr(sys|os, "<attr>", ...).

Alias resolution: ``import os as _o``, ``import sys as _s``, ``from os import chdir, environ``,
``from sys import path, modules, argv``, and flow-insensitive local rebinding
``env = os.environ`` (Name bound directly to a target object).

Excluded (owned by existing gates): SPEC_KITTY_HOME writes as matched by
``_home_pin_scan.find_write_sites`` (reused, never re-implemented).  ``patch.dict(...)`` and
``monkeypatch.*`` / ``MonkeyPatch.context`` / ``contextlib.chdir`` / ``mock.patch.*`` are never
matched because their receiver is not a target object.

NOTE for the real module: files importing ``_home_pin_scan`` must not call ``ast.parse`` nor
subclass ``NodeVisitor`` (test_home_pin_seam_no_second_copy) — hence parse via
``scan.parse_module`` and a plain ``ast.walk`` + parent map.
"""

from __future__ import annotations

import ast
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve()
REPO_ROOT = Path.cwd()  # run from the repository root
sys.path.insert(0, str(REPO_ROOT))  # prototype only
sys.path.insert(0, str(REPO_ROOT / "src"))

from specify_cli.contracts.anchoring import _build_qualname_map, code_tokens_by_line  # noqa: E402
from tests.architectural import _home_pin_scan as home  # noqa: E402

TARGET_ATTRS = {("os", "environ"): "os.environ", ("sys", "path"): "sys.path",
                ("sys", "modules"): "sys.modules", ("sys", "argv"): "sys.argv"}
CWD_FUNCS = {("os", "chdir"), ("os", "fchdir")}
ENV_FUNCS = {("os", "putenv"), ("os", "unsetenv")}
MUTATORS = {
    "os.environ": {"update", "pop", "setdefault", "clear", "popitem", "__setitem__", "__delitem__", "__ior__"},
    "sys.modules": {"update", "pop", "setdefault", "clear", "popitem", "__setitem__", "__delitem__", "__ior__"},
    "sys.path": {"insert", "append", "extend", "remove", "pop", "clear", "reverse", "sort",
                 "__setitem__", "__delitem__", "__iadd__"},
    "sys.argv": {"insert", "append", "extend", "remove", "pop", "clear", "reverse", "sort",
                 "__setitem__", "__delitem__", "__iadd__"},
}
REPLACEMENT = {
    "cwd": "monkeypatch.chdir(path) (or contextlib.chdir(path) for a block-scoped change)",
    "os.environ": "monkeypatch.setenv/delenv (or mock.patch.dict(os.environ, ...))",
    "sys.path": "monkeypatch.syspath_prepend(path)",
    "sys.modules": "monkeypatch.setitem/delitem(sys.modules, name, ...) (+ parent attr via setattr)",
    "sys.argv": "monkeypatch.setattr(sys, 'argv', [...])",
}


import re

_IMPORT_RE = re.compile(r"^[ \t]*(?:import[ \t]+(?:[\w.]+[ \t]*(?:as[ \t]+\w+)?[ \t]*,[ \t]*)*(?:os|sys)\b|from[ \t]+(?:os|sys)[ \t]+import)", re.M)
_CANDIDATES = (ast.Call, ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Delete)


@dataclass(frozen=True)
class Site:
    rel: str
    qualname: str
    lineno: int
    target: str  # cwd | os.environ | sys.path | sys.modules | sys.argv
    form: str
    token_line: str


class Bindings:
    def __init__(self, nodes: list[ast.AST]) -> None:
        self.mod: dict[str, str] = {}          # local name -> "os"/"sys"
        self.obj: dict[str, str] = {}          # local name -> target ("os.environ", ...)
        self.func: dict[str, tuple[str, str]] = {}  # local name -> ("os","chdir")
        for node in nodes:
            if isinstance(node, ast.Import):
                for a in node.names:
                    root = a.name.split(".")[0]
                    if root in ("os", "sys") and (a.asname is None or a.name in ("os", "sys")):
                        self.mod[a.asname or root] = root
            elif isinstance(node, ast.ImportFrom) and node.module in ("os", "sys") and node.level == 0:
                for a in node.names:
                    bound = a.asname or a.name
                    key = (node.module, a.name)
                    if key in TARGET_ATTRS:
                        self.obj[bound] = TARGET_ATTRS[key]
                    elif key in CWD_FUNCS or key in ENV_FUNCS:
                        self.func[bound] = key
        # flow-insensitive local aliasing: NAME = os.environ
        for node in nodes:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                t = self.target_of(node.value)
                if t is not None:
                    self.obj.setdefault(node.targets[0].id, t)

    def target_of(self, node: ast.AST) -> str | None:
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            m = self.mod.get(node.value.id)
            if m is not None:
                return TARGET_ATTRS.get((m, node.attr))
        if isinstance(node, ast.Name):
            return self.obj.get(node.id)
        return None

    def func_of(self, node: ast.AST) -> tuple[str, str] | None:
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            m = self.mod.get(node.value.id)
            if m is not None and ((m, node.attr) in CWD_FUNCS or (m, node.attr) in ENV_FUNCS):
                return (m, node.attr)
        if isinstance(node, ast.Name):
            return self.func.get(node.id)
        return None

    def is_module(self, node: ast.AST) -> str | None:
        return self.mod.get(node.id) if isinstance(node, ast.Name) else None


def _classify(node: ast.AST, b: Bindings) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if isinstance(node, ast.Call):
        f = b.func_of(node.func)
        if f is not None:
            out.append(("cwd" if f in CWD_FUNCS else "os.environ", f"call:{f[0]}.{f[1]}"))
        elif isinstance(node.func, ast.Attribute):
            t = b.target_of(node.func.value)
            if t is not None and node.func.attr in MUTATORS[t]:
                out.append((t, f"call:.{node.func.attr}"))
        if isinstance(node.func, ast.Name) and node.func.id in ("setattr", "delattr") and len(node.args) >= 2:
            m = b.is_module(node.args[0])
            a = node.args[1]
            if m and isinstance(a, ast.Constant) and isinstance(a.value, str):
                t = TARGET_ATTRS.get((m, a.value))
                if t or (m, a.value) in CWD_FUNCS:
                    out.append((t or "cwd", f"{node.func.id}"))
    elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Delete)):
        targets = node.targets if isinstance(node, (ast.Assign, ast.Delete)) else [node.target]
        verb = {ast.Assign: "store", ast.AnnAssign: "store", ast.AugAssign: "augassign", ast.Delete: "del"}[type(node)]
        for tg in _flatten(targets):
            if isinstance(tg, ast.Subscript):
                t = b.target_of(tg.value)
                if t is not None:
                    sl = "slice" if isinstance(tg.slice, ast.Slice) else "subscript"
                    out.append((t, f"{sl}-{verb}"))
            elif isinstance(tg, ast.Attribute):
                m = b.is_module(tg.value)
                if m:
                    t = TARGET_ATTRS.get((m, tg.attr))
                    if t:
                        out.append((t, f"rebind-{verb}"))
            elif isinstance(tg, ast.Name) and isinstance(node, ast.AugAssign):
                t = b.target_of(tg)
                if t is not None:
                    out.append((t, "augassign-name"))
    return out


def _flatten(targets: list[ast.expr]) -> list[ast.expr]:
    res: list[ast.expr] = []
    for t in targets:
        if isinstance(t, (ast.Tuple, ast.List)):
            res.extend(_flatten(list(t.elts)))
        else:
            res.append(t)
    return res


def _qualname(qmap: dict[tuple[int, int], str], lineno: int) -> str:
    c = [(e - s, q) for (s, e), q in qmap.items() if s <= lineno <= e]
    return min(c)[1] if c else "<module>"


def scan_file(path: Path, root: Path) -> list[Site]:
    source = path.read_text(encoding="utf-8")
    tree = home.parse_module(path)  # propagates SyntaxError -- EVERY file is parsed (FR-007)
    if not _IMPORT_RE.search(source):
        return []  # sound: every resolvable target needs an ``os``/``sys`` import binding
    nodes = list(ast.walk(tree))  # the ONE walk
    b = Bindings(nodes)
    if not (b.mod or b.obj or b.func):
        return []
    home_lines = (
        {w.lineno for w in home.find_write_sites(tree, key=home.NEEDLE)} if home.NEEDLE in source else set()
    )
    qmap = _build_qualname_map(tree)
    tokens: dict[int, str] | None = None
    sites: list[Site] = []
    rel = path.relative_to(root).as_posix()
    for node in nodes:
        if not isinstance(node, _CANDIDATES):
            continue
        hits = _classify(node, b)
        if not hits:
            continue
        ln = node.lineno
        if ln in home_lines and all(t == "os.environ" for t, _ in hits):
            continue  # owned by _home_pin_scan
        if tokens is None:
            tokens = code_tokens_by_line(source)
        for t, form in hits:
            sites.append(Site(rel, _qualname(qmap, ln), ln, t, form, tokens.get(ln, "")))
    return sites


def scan(root: Path) -> tuple[list[Site], list[tuple[str, str]], int]:
    files = sorted(p for p in (root / "tests").rglob("*.py") if "__pycache__" not in p.parts)
    sites: list[Site] = []
    failures: list[tuple[str, str]] = []
    for p in files:
        try:
            sites.extend(scan_file(p, root))
        except (SyntaxError, UnicodeDecodeError) as exc:
            failures.append((p.relative_to(root).as_posix(), f"{type(exc).__name__}: {exc}"))
    return sites, failures, len(files)


if __name__ == "__main__":
    t0 = time.perf_counter()
    sites, failures, n = scan(REPO_ROOT)
    dt = time.perf_counter() - t0
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    print(f"files={n} sites={len(sites)} files_with_sites={len({s.rel for s in sites})} "
          f"parse_failures={len(failures)} runtime={dt:.2f}s")
    print("by target:", Counter(s.target for s in sites).most_common())
    print("by form:", Counter((s.target, s.form) for s in sites).most_common())
    print("by dir:", Counter("/".join(s.rel.split("/")[:2]) for s in sites).most_common())
    print("keys (rel,qualname,target):", len({(s.rel, s.qualname, s.target) for s in sites}))
    for f, e in failures:
        print("PARSE-FAIL", f, e)
    if out:
        out.write_text("".join(f"{s.rel}\t{s.qualname}\t{s.lineno}\t{s.target}\t{s.form}\t{s.token_line}\n"
                               for s in sites), encoding="utf-8")
