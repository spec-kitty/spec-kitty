"""Mission write-discipline gate (#5819, plan amendment A12): the one-writer rules, by construction.

Three AST rules over ``src/specify_cli/**/*.py`` close the defect class behind
#5819 (concurrent writers of one Mission checkout losing each other's data):

1. **Truncate / unlink of the status log only in the primitive.** Every
   ``truncate`` / ``ftruncate`` shape (attribute, ``getattr`` string, ``methodcaller``
   string, ``from os import ftruncate as t``) and every ``.unlink(`` of an
   expression naming the event log is flagged outside
   ``src/specify_cli/status/mission_write.py``. Accepted over-fire: any
   unrelated ``.truncate`` attribute (rich ``Text.truncate``; none in scope).
2. **Read/sink pairs in one locked region.** A registered sink
   (``append_activity_log``, ``_append_entry``) must sit in a *locked region*:
   (a) the body of ``with mission_write_lock/feature_status_lock/coord_status_lock``
   without crossing a nested ``def``/``lambda``; (b) a function/lambda passed as
   ``transform`` to ``locked_rewrite_text`` (its read is the primitive's); or (c) a
   function/lambda passed as an argument to a call that is itself in (a). A named
   function must have exactly one reference. Where the sink is not in a
   transform, each read of the pair in the same outermost function must share a
   region with it. A non-call reference to a sink (``functools.partial``) fails as
   unclassifiable. Accepted over-accept: a callable passed to a call inside the
   ``with`` that stores it and runs it after the lock is released.
3. **No slug-keyed status lock.** ``feature_status_lock(<root>, <key>)`` whose key
   is a Name/Attribute with ``slug`` in its identifier is flagged.

Known residuals (not caught): rule 3 sees only Name/Attribute keys, so a subscript
key such as ``meta["mission_slug"]`` passes; rule 1 does not catch truncation by
``open(events_path, "w")`` or ``write_text("")``.

Out of scope by design: ``src/runtime`` (``run.events.jsonl``) and ``src/kernel``
(lock files). All allowlists are EMPTY; a hit is a finding to fix, not to list.
"""

from __future__ import annotations

import ast
import copy
import functools
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SPECIFY_CLI = _REPO_ROOT / "src" / "specify_cli"
_PRIMITIVE = "src/specify_cli/status/mission_write.py"
_TASKS = "src/specify_cli/cli/commands/agent/tasks.py"
_TRACER = "src/specify_cli/retrospective/tracer_writer.py"
_MIN_SCANNED_FILES = 300

_TRUNCATE_NAMES = frozenset({"truncate", "ftruncate"})
_TRUNCATE_HOSTS = frozenset({"os", "posix"})
_STRING_LOOKUPS = frozenset({"getattr", "methodcaller"})
_EVENT_LOG_TOKENS = ("events_path", "EVENTS_FILENAME", "status.events.jsonl")
_LOCK_CMS = frozenset({"mission_write_lock", "feature_status_lock", "coord_status_lock"})
_TRANSFORM_PRIMITIVE = "locked_rewrite_text"
_STATUS_LOCK = "feature_status_lock"
_TRANSFORM = "transform"
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
_Scope = ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda

# Allowlists are intentionally empty (shrink-only at zero).
_ALLOWED_TRUNCATE_FILES: frozenset[str] = frozenset({_PRIMITIVE})
_ALLOWED_SLUG_KEYED_LOCKS: frozenset[str] = frozenset()


@dataclass(frozen=True)
class SinkPair:
    """A registered read/sink pair: where the sink may be called and what read pairs with it."""

    sink: str
    read: str
    path: str
    rationale: str


#: Extendable registry. Each sink is called at exactly one site, under a lock.
SINK_PAIRS: tuple[SinkPair, ...] = (
    SinkPair(
        sink="append_activity_log",
        read="locate_work_package",
        path=_TASKS,
        rationale="add-history: the append runs inside the locked_rewrite_text transform, whose read is the primitive's",
    ),
    SinkPair(
        sink="_append_entry",
        read="_read_current_coord_content",
        path=_TRACER,
        rationale="tracer-append: read and merge happen in the stage thunk run under mission_write_lock",
    ),
)

Finding = tuple[str, int, str]


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}


# --------------------------------------------------------------------------- rule 1


def _first_const_str(call: ast.Call) -> str | None:
    for arg in call.args[:2]:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
    return None


def _truncate_reason(node: ast.AST) -> str | None:
    if isinstance(node, ast.Attribute) and node.attr in _TRUNCATE_NAMES:
        return f"attribute .{node.attr}"
    if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in _TRUNCATE_HOSTS:
        hit = [a.name for a in node.names if a.name in _TRUNCATE_NAMES]
        return f"import of {hit[0]}" if hit else None
    if isinstance(node, ast.Call) and _call_name(node.func) in _STRING_LOOKUPS:
        looked_up = _first_const_str(node)
        if looked_up in _TRUNCATE_NAMES:
            return f"{_call_name(node.func)}(..., {looked_up!r})"
    return None


def _unlink_reason(node: ast.AST) -> str | None:
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "unlink"):
        return None
    target = ast.unparse(node.func.value)
    return "unlink of the event log" if any(token in target for token in _EVENT_LOG_TOKENS) else None


def find_truncate_sites(tree: ast.AST) -> list[tuple[int, str]]:
    """Every truncate/unlink-of-event-log shape in *tree* as ``(line, reason)``."""
    sites: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        reason = _truncate_reason(node) or _unlink_reason(node)
        if reason is not None:
            sites.append((getattr(node, "lineno", 0), reason))
    return sorted(sites)


# --------------------------------------------------------------------------- rule 2


def _is_lock_with(node: ast.AST) -> bool:
    if not isinstance(node, ast.With | ast.AsyncWith):
        return False
    return any(isinstance(i.context_expr, ast.Call) and _call_name(i.context_expr.func) in _LOCK_CMS for i in node.items)


def _lock_withs_enclosing(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> list[ast.AST]:
    """Lock ``with`` statements whose body holds *node*, stopping at the first function boundary."""
    found: list[ast.AST] = []
    child, cur = node, parents.get(node)
    while cur is not None and not isinstance(cur, (*_SCOPES, ast.ClassDef)):
        if isinstance(cur, ast.With | ast.AsyncWith) and _is_lock_with(cur) and child in cur.body:
            found.append(cur)
        child, cur = cur, parents.get(cur)
    return found


def _enclosing_scope(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> _Scope | None:
    cur = parents.get(node)
    while cur is not None:
        if isinstance(cur, _SCOPES):
            return cur
        cur = parents.get(cur)
    return None


def _outermost_function(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> ast.AST | None:
    outer: ast.AST | None = None
    cur: ast.AST | None = parents.get(node)
    while cur is not None:
        if isinstance(cur, ast.FunctionDef | ast.AsyncFunctionDef):
            outer = cur
        cur = parents.get(cur)
    return outer


def _passing_calls(scope: _Scope, tree: ast.AST, parents: dict[ast.AST, ast.AST]) -> list[ast.Call] | None:
    """Calls receiving *scope* as an argument; ``None`` if the reference set is not exactly one passing call."""
    if isinstance(scope, ast.Lambda):
        holder: ast.AST | None = parents.get(scope)
        if isinstance(holder, ast.keyword):
            holder = parents.get(holder)
        return [holder] if isinstance(holder, ast.Call) and holder.func is not scope else None
    refs = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == scope.name]
    if len(refs) != 1:
        return None
    holder = parents.get(refs[0])
    if isinstance(holder, ast.keyword):
        holder = parents.get(holder)
    return [holder] if isinstance(holder, ast.Call) and holder.func is not refs[0] else None


def _is_transform_arg(call: ast.Call, scope: _Scope, tree: ast.AST) -> bool:
    if _call_name(call.func) != _TRANSFORM_PRIMITIVE:
        return False
    name = None if isinstance(scope, ast.Lambda) else scope.name
    candidates: list[ast.AST] = []
    if len(call.args) > 1:
        candidates.append(call.args[1])
    candidates.extend(k.value for k in call.keywords if k.arg == _TRANSFORM)
    return any(c is scope or (name is not None and isinstance(c, ast.Name) and c.id == name) for c in candidates)


def locked_regions(node: ast.AST, tree: ast.AST, parents: dict[ast.AST, ast.AST]) -> frozenset[object] | None:
    """Regions (a)/(b)/(c) holding *node*: lock-``with`` nodes, plus ``"transform"``; ``None`` if unlocked."""
    direct = _lock_withs_enclosing(node, parents)
    if direct:
        return frozenset(direct)
    scope = _enclosing_scope(node, parents)
    if scope is None:
        return None
    calls = _passing_calls(scope, tree, parents)
    if not calls:
        return None
    call = calls[0]
    if _is_transform_arg(call, scope, tree):
        return frozenset({"transform"})
    held = _lock_withs_enclosing(call, parents)
    return frozenset(held) if held else None


def _is_call_func(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    parent = parents.get(node)
    return isinstance(parent, ast.Call) and parent.func is node


def _references(tree: ast.AST, name: str) -> list[ast.AST]:
    refs: list[ast.AST] = []
    for n in ast.walk(tree):
        if (isinstance(n, ast.Name) and n.id == name) or (isinstance(n, ast.Attribute) and n.attr == name):
            refs.append(n)
    return refs


def _read_shares_region(sink: ast.AST, pair: SinkPair, tree: ast.AST, parents: dict[ast.AST, ast.AST], regions: frozenset[object]) -> bool:
    outer = _outermost_function(sink, parents)
    if outer is None:
        return False
    for ref in _references(outer, pair.read):
        if not _is_call_func(ref, parents):
            continue
        read_regions = locked_regions(parents[ref], tree, parents)
        if read_regions is None or not (read_regions & regions):
            return False
    return True


def find_sink_findings(tree: ast.AST, rel: str, pairs: tuple[SinkPair, ...] = SINK_PAIRS) -> list[tuple[int, str]]:
    """Rule 2 findings for one parsed module: sink references that are unlocked or unclassifiable."""
    parents = _parents(tree)
    findings: list[tuple[int, str]] = []
    for pair in pairs:
        for ref in _references(tree, pair.sink):
            line = getattr(ref, "lineno", 0)
            if not _is_call_func(ref, parents):
                findings.append((line, f"{pair.sink}: non-call reference is unclassifiable"))
                continue
            if rel != pair.path:
                findings.append((line, f"{pair.sink}: call outside its registered site {pair.path}"))
                continue
            regions = locked_regions(parents[ref], tree, parents)
            if regions is None:
                findings.append((line, f"{pair.sink}: not inside a locked region"))
            elif "transform" not in regions and not _read_shares_region(ref, pair, tree, parents, regions):
                findings.append((line, f"{pair.sink}: its read {pair.read} is not in the same locked region"))
    return sorted(findings)


# --------------------------------------------------------------------------- rule 3


def _lock_key(call: ast.Call) -> ast.AST | None:
    if len(call.args) > 1:
        return call.args[1]
    return next((k.value for k in call.keywords if k.arg == "lock_key"), None)


def find_slug_keyed_locks(tree: ast.AST) -> list[int]:
    """Lines of ``feature_status_lock(<root>, <key>)`` calls whose key identifier contains ``slug``."""
    lines: list[int] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and _call_name(node.func) == _STATUS_LOCK):
            continue
        key = _lock_key(node)
        ident = _call_name(key) if key is not None else None
        if ident is not None and "slug" in ident.lower():
            lines.append(node.lineno)
    return sorted(lines)


# --------------------------------------------------------------------------- tree walk


def _rel(path: Path) -> str:
    return path.relative_to(_REPO_ROOT).as_posix()


@functools.lru_cache(maxsize=1)
def _src_files() -> tuple[Path, ...]:
    return tuple(sorted(_SPECIFY_CLI.rglob("*.py")))


@functools.cache
def _parse(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


@functools.lru_cache(maxsize=1)
def _scan_tree() -> dict[str, list[Finding]]:
    report: dict[str, list[Finding]] = {"truncate": [], "sink": [], "slug": []}
    for path in _src_files():
        rel, tree = _rel(path), _parse(path)
        if rel not in _ALLOWED_TRUNCATE_FILES:
            report["truncate"] += [(rel, line, why) for line, why in find_truncate_sites(tree)]
        report["sink"] += [(rel, line, why) for line, why in find_sink_findings(tree, rel)]
        if rel not in _ALLOWED_SLUG_KEYED_LOCKS:
            report["slug"] += [(rel, line, "slug-keyed feature_status_lock") for line in find_slug_keyed_locks(tree)]
    return report


def _fmt(findings: list[Finding]) -> str:
    return "\n".join(f"  {rel}:{line}: {why}" for rel, line, why in findings)


# --------------------------------------------------------------------------- real-tree tests


def test_scan_floor_is_met() -> None:
    assert len(_src_files()) > _MIN_SCANNED_FILES, "scanner is scanning too few files; the gate would pass vacuously"


def test_allowlists_are_empty() -> None:
    assert {_PRIMITIVE} == _ALLOWED_TRUNCATE_FILES
    assert not _ALLOWED_SLUG_KEYED_LOCKS


def test_rule1_truncate_only_in_the_primitive() -> None:
    found = _scan_tree()["truncate"]
    assert not found, f"truncate/unlink of the status log outside {_PRIMITIVE}:\n{_fmt(found)}"


def test_rule1_floor_primitive_holds_its_sites() -> None:
    """Non-vacuity: the scanner still sees both kinds of site in the primitive (a rename of either would blind rule 1)."""
    reasons = Counter(why for _, why in find_truncate_sites(_parse(_REPO_ROOT / _PRIMITIVE)))
    assert reasons["attribute .ftruncate"] >= 1
    assert reasons["unlink of the event log"] >= 1


def test_rule2_sinks_are_in_a_locked_region() -> None:
    found = _scan_tree()["sink"]
    assert not found, f"registered sink outside a locked read/write region:\n{_fmt(found)}"


def test_rule2_floor_every_registered_sink_site_is_visible() -> None:
    """Non-vacuity: each registered sink is still called in its registered module (rule 2 above judges where)."""
    census: Counter[tuple[str, str]] = Counter()
    for path in _src_files():
        tree = _parse(path)
        parents = _parents(tree)
        for pair in SINK_PAIRS:
            census.update((_rel(path), pair.sink) for ref in _references(tree, pair.sink) if _is_call_func(ref, parents))
    assert all(census[(p.path, p.sink)] >= 1 for p in SINK_PAIRS), dict(census)


def test_rule3_no_slug_keyed_status_lock() -> None:
    found = _scan_tree()["slug"]
    assert not found, f"feature_status_lock keyed on a slug-named value (key on the Mission directory name):\n{_fmt(found)}"


# --------------------------------------------------------------------------- non-vacuity: synthetic offenders

_TRUNCATE_OFFENDERS = {
    "attribute": "fh.truncate(0)",
    "os.truncate": "import os\nos.truncate(p, 0)",
    "os.ftruncate": "import os\nos.ftruncate(fd, 0)",
    "alias module": "import os as _os\n_os.ftruncate(fd, 0)",
    "posix": "import posix\nposix.ftruncate(fd, 0)",
    "from-import alias": "from os import ftruncate as t\nt(fd, 0)",
    "getattr string": 'getattr(fh, "truncate")(0)',
    "methodcaller": 'import operator\noperator.methodcaller("truncate", 0)(fh)',
    "unlink events_path": "events_path.unlink()",
    "unlink _events_path attr": "self._events_path.unlink(missing_ok=True)",
    "unlink constant": "Path(d / EVENTS_FILENAME).unlink()",
    "unlink literal": 'Path("status.events.jsonl").unlink()',
}


@pytest.mark.parametrize("source", _TRUNCATE_OFFENDERS.values(), ids=_TRUNCATE_OFFENDERS.keys())
def test_rule1_flags_each_synthetic_offender(source: str) -> None:
    assert find_truncate_sites(ast.parse(source))


def test_rule1_does_not_flag_unrelated_unlink() -> None:
    assert not find_truncate_sites(ast.parse("tmp_path.unlink()"))


_SYNTH_PAIR = SinkPair(sink="sink", read="read", path="m.py", rationale="synthetic")
_LOCKED_OK = {
    "with body": "def f():\n    with mission_write_lock(d):\n        read()\n        sink()\n",
    "attribute lock": "def f():\n    with _t.feature_status_lock(r, k):\n        read()\n        sink()\n",
    "transform lambda": "locked_rewrite_text(p, lambda c: sink(c), feature_dir=d)\n",
    "transform def": "def f():\n    def t(c):\n        return sink(c)\n    locked_rewrite_text(p, t, feature_dir=d)\n",
    "transform keyword": "def f():\n    def t(c):\n        return sink(c)\n    locked_rewrite_text(p, transform=t, feature_dir=d)\n",
    "thunk passed in with": ("def f():\n    def stage():\n        read()\n        sink()\n    with mission_write_lock(d):\n        write_artifact(stage=stage)\n"),
}
_LOCKED_BAD = {
    "bare call": "def f():\n    read()\n    sink()\n",
    "lock released before sink": "def f():\n    with mission_write_lock(d):\n        read()\n    sink()\n",
    "read outside, sink inside": "def f():\n    read()\n    with mission_write_lock(d):\n        sink()\n",
    "separate withs": "def f():\n    with mission_write_lock(d):\n        read()\n    with mission_write_lock(d):\n        sink()\n",
    "def in with, called later": "def f():\n    with mission_write_lock(d):\n        def g():\n            sink()\n    g()\n",
    "lambda in with, called later": "def f():\n    with mission_write_lock(d):\n        g = lambda: sink()\n    g()\n",
    "thunk passed outside lock": "def f():\n    def stage():\n        read()\n        sink()\n    write_artifact(stage=stage)\n",
    "thunk referenced twice": (
        "def f():\n    def stage():\n        read()\n        sink()\n    with mission_write_lock(d):\n        write_artifact(stage=stage)\n    stage()\n"
    ),
    "transform to other call": "locked_other(p, lambda c: sink(c))\n",
    "partial reference": "import functools\ndef f():\n    with mission_write_lock(d):\n        p = functools.partial(sink, 1)\n        p()\n",
    "class body": "class C:\n    sink()\n",
    "unrelated with": "def f():\n    with open(p):\n        sink()\n",
}


@pytest.mark.parametrize("source", _LOCKED_OK.values(), ids=_LOCKED_OK.keys())
def test_rule2_accepts_each_locked_shape(source: str) -> None:
    assert find_sink_findings(ast.parse(source), "m.py", (_SYNTH_PAIR,)) == []


@pytest.mark.parametrize("source", _LOCKED_BAD.values(), ids=_LOCKED_BAD.keys())
def test_rule2_flags_each_synthetic_offender(source: str) -> None:
    assert find_sink_findings(ast.parse(source), "m.py", (_SYNTH_PAIR,))


def test_rule2_flags_sink_called_outside_its_registered_site() -> None:
    assert find_sink_findings(ast.parse("def f():\n    with mission_write_lock(d):\n        sink()\n"), "other.py", (_SYNTH_PAIR,))


_SLUG_OFFENDERS = {
    "name": "feature_status_lock(root, mission_slug)",
    "attribute": "feature_status_lock(root, st.mission_slug)",
    "qualified call": "_tasks.feature_status_lock(root, slug)",
    "keyword": "feature_status_lock(root, lock_key=feature_slug)",
}


@pytest.mark.parametrize("source", _SLUG_OFFENDERS.values(), ids=_SLUG_OFFENDERS.keys())
def test_rule3_flags_each_synthetic_offender(source: str) -> None:
    assert find_slug_keyed_locks(ast.parse(source))


@pytest.mark.parametrize(
    "source",
    ["feature_status_lock(root, feature_dir.name)", "feature_status_lock(root, st.feature_dir.name)", "feature_status_lock(root, mission_dir_name)"],
)
def test_rule3_accepts_directory_name_keys(source: str) -> None:
    assert find_slug_keyed_locks(ast.parse(source)) == []


# --------------------------------------------------------------------------- non-vacuity: self-mutation of the real modules


class _Mutation(ast.NodeTransformer):
    """A source mutation that counts how many nodes it rewrote."""

    def __init__(self) -> None:
        self.changed = 0


class _InlineTransform(_Mutation):
    """``locked_rewrite_text(path, f, ...)`` -> ``f(None)``: the lock is stripped, the sink body is kept."""

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        if _call_name(node.func) == _TRANSFORM_PRIMITIVE and len(node.args) > 1:
            self.changed += 1
            return ast.copy_location(ast.Call(func=node.args[1], args=[ast.Constant(None)], keywords=[]), node)
        return node


class _StripLockWith(_Mutation):
    """``with <lock>: body`` -> ``body``: the same code, unlocked."""

    def visit_With(self, node: ast.With) -> ast.AST | list[ast.stmt]:
        self.generic_visit(node)
        if _is_lock_with(node):
            self.changed += 1
            return node.body
        return node


def _mutate(rel: str, transformer: _Mutation) -> ast.AST:
    tree = ast.fix_missing_locations(transformer.visit(copy.deepcopy(_parse(_REPO_ROOT / rel))))
    assert transformer.changed, f"mutation did not apply to {rel}; the self-mutation test would be vacuous"
    assert isinstance(tree, ast.AST)
    return tree


def test_self_mutation_add_history_without_the_primitive_is_flagged() -> None:
    mutated = _mutate(_TASKS, _InlineTransform())
    assert any("append_activity_log" in why for _, why in find_sink_findings(mutated, _TASKS))


def test_self_mutation_tracer_without_the_lock_is_flagged() -> None:
    mutated = _mutate(_TRACER, _StripLockWith())
    assert any("_append_entry" in why for _, why in find_sink_findings(mutated, _TRACER))
