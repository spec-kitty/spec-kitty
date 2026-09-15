"""AST writes-gate for ``status.events.jsonl`` (FR-011, R14).

Mission ``fsm-write-path-integrity-01M1TZV6`` WP03 (contract
``contracts/write-gates.md`` sections 2 and 3). ``status/store.py`` is the
only module that may write the mission event log. This gate scans every
``src/**/*.py`` for write-mode file operations whose path resolves
statically to a ``status.events.jsonl`` file and fails when one lives
anywhere else:

* ``open(p, "a" | "w" | ...)``, ``p.open("ab")``, ``p.write_text(...)``,
  ``p.write_bytes(...)``;
* ``os.open(p, O_WRONLY | O_APPEND | O_TRUNC | ...)``;
* ``os.replace(tmp, p)`` / ``os.rename(tmp, p)`` / ``shutil.move(tmp, p)``
  -- the atomic-rename landing step IS the durable write, so a destination
  that is the event log counts.

The out-of-store sites that legitimately exist are ledgered in
``ALLOWED_OUT_OF_STORE_WRITE_SITES`` with a per-key site COUNT, so a second
write of an already-ledgered shape in the same module is reported (WP07).

Path resolution is static and best-effort. Resolved shapes: string
constants; f-strings; ``Path(...) / "status.events.jsonl"``; ``feature_dir /
EVENTS_FILENAME`` (the store constant under any import alias, or a module
constant holding the literal); names assigned in the same function or at
module level; ``self.<attr>`` assigned anywhere in the module; calls to
same-module functions whose every ``return`` resolves; and function
PARAMETERS, resolved through every same-module call site of that function
(all callers must agree). A write whose path the scanner still cannot
resolve is NOT a pass (contract section 2): every unresolved write whose
path expression is event-named (``events_path``, ``self._events_path``,
...) is pinned in ``EXPECTED_UNRESOLVED_EVENT_NAMED_WRITE_SITES``, and the
dynamic event-log writers that rule cannot name are pinned in
``KNOWN_DYNAMIC_EVENT_LOG_WRITE_SITES`` (each must still be live).

Positive census (section 2): the scanner must find the store's own writes;
a scan that matches zero writers anywhere is itself a failure.

Lock-composition census (R14): every module with a ``feature_status_lock(``
call site is pinned in ``EXPECTED_LOCK_COMPOSITION_SITES``. A new
lock-plus-append composition anywhere else is a new writer shell and fails
with a pointer to ``contracts/emit-pipeline.md`` section 2.

Non-vacuity floor (section 3): synthetic sources for every write shape and
every path-resolution rule are fed to the SAME scanner and must each
report exactly one event-log write.
"""

from __future__ import annotations

import ast
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

import pytest

from tests.architectural.conftest import SourceFile

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"

EVENTS_LOG = "status.events.jsonl"
STORE_MODULE = "specify_cli.status.store"
_EVENTS_CONST_HOMES = frozenset({"specify_cli.status", "specify_cli.status.store", "specify_cli.status._unsafe"})
_EVENTS_CONST_NAME = "EVENTS_FILENAME"
_WRITE_FLAG_TOKENS = ("O_WRONLY", "O_RDWR", "O_APPEND", "O_TRUNC", "O_CREAT")
_RENAME_KINDS = frozenset({"os.replace", "os.rename", "shutil.move"})
_PATH_WRAPPERS = frozenset({"Path", "PurePath", "PurePosixPath", "PureWindowsPath", "str"})
_PATH_PASSTHROUGH_METHODS = frozenset({"resolve", "absolute", "expanduser"})
_SELF_NAMES = frozenset({"self", "cls"})
_MAX_DEPTH = 16

#: Resolved event-log writes outside ``store.py`` that exist today, each with
#: the number of sites the ledger covers. Keyed on (module, kind, path
#: expression) -- line numbers move, expressions do not -- and COUNTED, so a
#: second write of the same shape in an allowed module is a new site the
#: gate reports, not a free ride on the ledger (WP03 review finding, closed
#: in WP07). Shrink-only (``test_allowed_out_of_store_sites_are_live`` drops
#: stale or under-counted entries): each entry says why the site is not an
#: FSM append bypass.
ALLOWED_OUT_OF_STORE_WRITE_SITES: Mapping[tuple[str, str, str], int] = MappingProxyType(
    {
        # Rollback truncates (not appends): restore the log byte-for-byte to
        # the pre-emit size after a failed commit. Run inside the shells'
        # own failure paths.
        ("specify_cli.coordination.transaction", "Path.open", "self._events_path"): 1,
        ("specify_cli.coordination.status_transition", "Path.open", "events_path"): 1,
        # Checkout materializations (not appends): write bytes git already
        # holds for the log into a worktree so materialize() can read them
        # (sparse-checkout hydration from the index).
        ("specify_cli.lanes.auto_rebase", "write_text", "events_path"): 1,
        # Legacy whole-log rebuild migration (writer census family 9, WP07):
        # rewrites a reconciled log atomically (tmp + ``os.replace``) with
        # the read -> reconcile -> rewrite under ONE acquisition of the
        # mission status lock keyed on the mission directory name, so a
        # concurrent locked append waits and lands after the rewrite. Not an
        # append, so not a store primitive; the rename shape stays here.
        ("specify_cli.migration.rebuild_state", "os.replace", "str(events_file)"): 1,
        # ``specify_cli.decisions.emit`` (family 8) left this ledger in WP07:
        # its raw ``open("a")`` became ``append_raw_rows_atomic`` under L1
        # behind ``status/_unsafe`` (see ``test_status_unsafe_allowlist.py``).
    }
)

#: Unresolved write sites whose path expression is event-named. Pinned so a
#: new dynamic event-log write cannot slip in as "unresolved" (contract
#: section 2). Each is explained; a change here is a change to the write
#: surface and must be reviewed, not absorbed.
EXPECTED_UNRESOLVED_EVENT_NAMED_WRITE_SITES: frozenset[tuple[str, str, str]] = frozenset(
    {
        # Merge-time union projection: writes source-union-original bytes of
        # the log onto the trusted target checkout. The path comes from a
        # trust helper called with several filenames, so callers disagree.
        ("specify_cli.merge.bookkeeping_projection", "write_bytes", "trusted_target_events_path"),
        # Workflow-commit rollback truncate (keyword-only parameter; the
        # in-module callers pass a path the scanner cannot trace).
        ("specify_cli.cli.commands.agent.workflow", "Path.open", "events_path"),
        # The glossary's OWN event log (``_local_append_event``), not the
        # mission status log: parameter path, callers span modules.
        ("glossary.events", "Path.open", "event_log_path"),
    }
)

#: Dynamic event-log writers the event-name rule cannot see (parameter
#: paths named ``path`` / ``target``). Each must still be found unresolved
#: on the tree; a resolved or vanished entry fails the live check.
KNOWN_DYNAMIC_EVENT_LOG_WRITE_SITES: frozenset[tuple[str, str, str]] = frozenset(
    {
        # Lifecycle-envelope migration: whole-file atomic replace over a
        # parameter path (mission log or project canonical log).
        ("specify_cli.status.migrate_lifecycle_envelope", "os.replace", "path"),
        # Three-way event-log merge driver output (``output_path or ours``).
        ("specify_cli.status.event_log_merge", "Path.open", "target"),
        # #2804 gate-artifact restore after a squash merge (the log is one of
        # the preserved gate artifacts).
        ("specify_cli.merge.executor", "write_bytes", "path"),
    }
)

#: Modules with a ``feature_status_lock(`` call site (R14 census). Built
#: from the tree at the WP03 landing; each line says what the shell is.
EXPECTED_LOCK_COMPOSITION_SITES: frozenset[str] = frozenset(
    {
        # Family 1 flat shell + batch door + emit_inner_state_changed.
        "specify_cli.status.emit",
        # Family 2 lifecycle appender (_lifecycle_write_lock).
        "specify_cli.status.lifecycle_events",
        # Family 3 BookkeepingTransaction (lock held for the txn lifetime).
        "specify_cli.coordination.transaction",
        # Coord fallback: L1 covers snapshot, emit, commit and rollback.
        "specify_cli.coordination.status_transition",
        # Family 5 retro_status_lock helper (family 4 composes through it).
        "specify_cli.retrospective.lifecycle_events",
        # Family 6 verdict-provenance backfill (one-shot migration).
        "specify_cli.migration.verdict_provenance_backfill",
        # Family 7 runtime-state backfill (one-shot migration).
        "specify_cli.migration.backfill_runtime_state",
        # Family 8 decision-point rows (WP07 census addendum): one L1 take
        # around ``append_raw_rows_atomic`` + the Lamport readback.
        "specify_cli.decisions.emit",
        # Family 9 legacy whole-log rebuild (WP07 census addendum): one L1
        # take around the read -> reconcile -> ``os.replace`` rewrite.
        "specify_cli.migration.rebuild_state",
        # Work-package lifecycle helpers (WP01 lock-key audit section 4).
        "specify_cli.status.work_package_lifecycle",
        # Lifecycle-envelope migration lock (already key-compliant).
        "specify_cli.status.migrate_lifecycle_envelope",
        # Verdict-save-queue scopes: bounded L1 takes (lock rule a).
        "specify_cli.review.cycle",
        # CLI command shells that hold L1 around a status commit.
        "specify_cli.cli.commands.agent.status",
        "specify_cli.cli.commands.agent.workflow_executor",
        "specify_cli.cli.commands.agent.tasks_mark_status",
        "specify_cli.cli.commands.agent.tasks_move_task",
    }
)


@dataclass(frozen=True)
class WriteSite:
    """One write-mode file operation found by the scanner."""

    module: str
    lineno: int
    kind: str
    mode: str
    path_expr: str
    path_text: str | None

    @property
    def targets_events_log(self) -> bool:
        return self.path_text is not None and self.path_text.endswith(EVENTS_LOG)

    @property
    def is_event_named(self) -> bool:
        return "event" in self.path_expr.lower()

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.module, self.kind, self.path_expr)


# ---------------------------------------------------------------------------
# Module context: what the resolver may consult besides the expression itself
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _ModuleContext:
    functions: Mapping[str, ast.FunctionDef]
    module_assignments: Mapping[str, ast.expr]
    self_attributes: Mapping[str, tuple[ast.expr, ast.FunctionDef | None]]
    events_aliases: frozenset[str]
    parents: Mapping[ast.AST, ast.AST]
    calls: tuple[ast.Call, ...]


def _assignment_targets(node: ast.AST) -> Iterable[tuple[ast.expr, ast.expr]]:
    if isinstance(node, ast.Assign):
        return ((target, node.value) for target in node.targets)
    if isinstance(node, ast.AnnAssign) and node.value is not None:
        return ((node.target, node.value),)
    return ()


def _events_aliases(tree: ast.Module) -> frozenset[str]:
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module in _EVENTS_CONST_HOMES or (node.level and node.module in {"store", None})):
            aliases.update(alias.asname or alias.name for alias in node.names if alias.name == _EVENTS_CONST_NAME)
    return frozenset(aliases)


def _enclosing(parents: Mapping[ast.AST, ast.AST], node: ast.AST, kind: type) -> ast.AST | None:
    current = parents.get(node)
    while current is not None and not isinstance(current, kind):
        current = parents.get(current)
    return current


def _enclosing_function(parents: Mapping[ast.AST, ast.AST], node: ast.AST) -> ast.FunctionDef | None:
    found = _enclosing(parents, node, ast.FunctionDef)
    return found if isinstance(found, ast.FunctionDef) else None


def _build_context(tree: ast.Module) -> _ModuleContext:
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    module_assignments: dict[str, ast.expr] = {}
    for node in tree.body:
        for target, value in _assignment_targets(node):
            if isinstance(target, ast.Name):
                module_assignments[target.id] = value
    self_attributes: dict[str, tuple[ast.expr, ast.FunctionDef | None]] = {}
    for node in ast.walk(tree):
        for target, value in _assignment_targets(node):
            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id in _SELF_NAMES:
                self_attributes[target.attr] = (value, _enclosing_function(parents, node))
    calls = tuple(node for node in ast.walk(tree) if isinstance(node, ast.Call))
    return _ModuleContext(functions, module_assignments, self_attributes, _events_aliases(tree), parents, calls)


# ---------------------------------------------------------------------------
# Static path resolution
# ---------------------------------------------------------------------------


class _Resolver:
    """Best-effort static text of a path expression (only its tail matters)."""

    def __init__(self, ctx: _ModuleContext) -> None:
        self._ctx = ctx

    def resolve(self, expr: ast.expr, fn: ast.FunctionDef | None, depth: int = 0) -> str | None:
        if depth > _MAX_DEPTH:
            return None
        handler = self._handlers.get(type(expr))
        return handler(self, expr, fn, depth + 1) if handler else None

    def _constant(self, expr: ast.Constant, _fn: ast.FunctionDef | None, _depth: int) -> str | None:
        return expr.value if isinstance(expr.value, str) else None

    def _joined(self, expr: ast.JoinedStr, fn: ast.FunctionDef | None, depth: int) -> str | None:
        parts: list[str] = []
        for value in expr.values:
            if isinstance(value, ast.Constant):
                parts.append(str(value.value))
            elif isinstance(value, ast.FormattedValue):
                parts.append(self.resolve(value.value, fn, depth) or "{}")
        return "".join(parts)

    def _binop(self, expr: ast.BinOp, fn: ast.FunctionDef | None, depth: int) -> str | None:
        if isinstance(expr.op, ast.Div):
            return self.resolve(expr.right, fn, depth)
        if isinstance(expr.op, ast.Add):
            right = self.resolve(expr.right, fn, depth)
            return None if right is None else (self.resolve(expr.left, fn, depth) or "{}") + right
        if isinstance(expr.op, ast.Mod):
            return self.resolve(expr.left, fn, depth)
        return None

    def _call(self, expr: ast.Call, fn: ast.FunctionDef | None, depth: int) -> str | None:
        func = expr.func
        if isinstance(func, ast.Name):
            return self._call_by_name(func.id, expr, fn, depth)
        if isinstance(func, ast.Attribute):
            return self._call_by_method(func, expr, fn, depth)
        return None

    def _call_by_name(self, name: str, expr: ast.Call, fn: ast.FunctionDef | None, depth: int) -> str | None:
        if name in _PATH_WRAPPERS and expr.args:
            return self.resolve(expr.args[0], fn, depth)
        target = self._ctx.functions.get(name)
        return self._function_return(target, depth) if target is not None else None

    def _call_by_method(self, func: ast.Attribute, expr: ast.Call, fn: ast.FunctionDef | None, depth: int) -> str | None:
        if isinstance(func.value, ast.Name) and func.value.id == "pathlib" and func.attr in _PATH_WRAPPERS and expr.args:
            return self.resolve(expr.args[0], fn, depth)
        if func.attr in _PATH_PASSTHROUGH_METHODS:
            return self.resolve(func.value, fn, depth)
        if func.attr in {"joinpath", "with_name"} and expr.args:
            return self.resolve(expr.args[-1], fn, depth)
        return None

    def _function_return(self, target: ast.FunctionDef, depth: int) -> str | None:
        returns = [node for node in ast.walk(target) if isinstance(node, ast.Return) and node.value is not None]
        return self._agree(self.resolve(node.value, target, depth) for node in returns)

    def _attribute(self, expr: ast.Attribute, _fn: ast.FunctionDef | None, depth: int) -> str | None:
        if isinstance(expr.value, ast.Name) and expr.value.id in _SELF_NAMES and expr.attr in self._ctx.self_attributes:
            value, owner = self._ctx.self_attributes[expr.attr]
            return self.resolve(value, owner, depth)
        return None

    def _name(self, expr: ast.Name, fn: ast.FunctionDef | None, depth: int) -> str | None:
        if expr.id in self._ctx.events_aliases:
            return EVENTS_LOG
        local = _last_local_assignment(fn, expr.id) if fn is not None else None
        if local is not None:
            return self.resolve(local, fn, depth)
        module_value = self._ctx.module_assignments.get(expr.id)
        if module_value is not None:
            return self.resolve(module_value, None, depth)
        return self._parameter(fn, expr.id, depth) if fn is not None else None

    def _parameter(self, fn: ast.FunctionDef, name: str, depth: int) -> str | None:
        """A parameter resolves when every same-module call site passes the same static tail."""
        position = _parameter_position(fn, name)
        if position is None:
            return None
        arguments = [_argument_for(call, name, position) for call in _call_sites_of(self._ctx, fn)]
        if not arguments or any(argument is None for argument in arguments):
            return None
        return self._agree(self.resolve(argument, _enclosing_function(self._ctx.parents, argument), depth) for argument in arguments if argument is not None)

    @staticmethod
    def _agree(values: Iterable[str | None]) -> str | None:
        distinct = set(values)
        return distinct.pop() if len(distinct) == 1 else None

    _handlers = {
        ast.Constant: _constant,
        ast.JoinedStr: _joined,
        ast.BinOp: _binop,
        ast.Call: _call,
        ast.Attribute: _attribute,
        ast.Name: _name,
    }


def _last_local_assignment(fn: ast.FunctionDef, name: str) -> ast.expr | None:
    found: ast.expr | None = None
    for node in ast.walk(fn):
        for target, value in _assignment_targets(node):
            if isinstance(target, ast.Name) and target.id == name and not (isinstance(value, ast.Name) and value.id == name):
                found = value
    return found


def _parameter_position(fn: ast.FunctionDef, name: str) -> int | None:
    """Positional index of ``name`` among the caller-visible arguments (``-1`` = keyword-only)."""
    positional = [arg.arg for arg in fn.args.posonlyargs + fn.args.args]
    if positional and positional[0] in _SELF_NAMES:
        positional = positional[1:]
    if name in positional:
        return positional.index(name)
    return -1 if name in {arg.arg for arg in fn.args.kwonlyargs} else None


def _argument_for(call: ast.Call, name: str, position: int) -> ast.expr | None:
    keyword = next((kw.value for kw in call.keywords if kw.arg == name), None)
    if keyword is not None:
        return keyword
    if 0 <= position < len(call.args) and not isinstance(call.args[position], ast.Starred):
        return call.args[position]
    return None


def _call_sites_of(ctx: _ModuleContext, fn: ast.FunctionDef) -> list[ast.Call]:
    """Same-module calls of ``fn``: ``name(...)``, ``self.name(...)``, ``Class(...)`` for ``__init__``."""
    owner = _enclosing(ctx.parents, fn, ast.ClassDef)
    names = {fn.name} if fn.name != "__init__" or not isinstance(owner, ast.ClassDef) else {owner.name, *_SELF_NAMES}
    return [call for call in ctx.calls if _is_call_of(call.func, names)]


def _is_call_of(func: ast.expr, names: set[str]) -> bool:
    if isinstance(func, ast.Name):
        return func.id in names
    return isinstance(func, ast.Attribute) and func.attr in names and isinstance(func.value, ast.Name) and func.value.id in _SELF_NAMES


# ---------------------------------------------------------------------------
# Write-site detection
# ---------------------------------------------------------------------------


def _keyword(call: ast.Call, name: str) -> ast.expr | None:
    return next((kw.value for kw in call.keywords if kw.arg == name), None)


def _positional_or_keyword(call: ast.Call, index: int, name: str) -> ast.expr | None:
    if len(call.args) > index:
        return call.args[index]
    return _keyword(call, name)


def _mode_text(expr: ast.expr | None, default: str) -> str:
    if expr is None:
        return default
    return expr.value if isinstance(expr, ast.Constant) and isinstance(expr.value, str) else "?"


def _is_write_mode(mode: str) -> bool:
    return mode == "?" or any(flag in mode for flag in "wax+")


def _dotted(func: ast.expr) -> str | None:
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return f"{func.value.id}.{func.attr}"
    return None


def _classify_call(call: ast.Call) -> tuple[str, str, ast.expr] | None:
    """(kind, mode, path expression) when ``call`` is a write-mode file operation."""
    func = call.func
    dotted = _dotted(func)
    if (isinstance(func, ast.Name) and func.id == "open") or dotted == "io.open":
        path = _positional_or_keyword(call, 0, "file")
        mode = _mode_text(_positional_or_keyword(call, 1, "mode"), "r")
        return ("open", mode, path) if path is not None and _is_write_mode(mode) else None
    if dotted == "os.open":
        flags = _positional_or_keyword(call, 1, "flags")
        flag_text = ast.unparse(flags) if flags is not None else "?"
        writes = flag_text == "?" or any(token in flag_text for token in _WRITE_FLAG_TOKENS)
        return ("os.open", flag_text, call.args[0]) if writes and call.args else None
    if dotted in _RENAME_KINDS:
        destination = _positional_or_keyword(call, 1, "dst")
        return (dotted, "replace", destination) if destination is not None else None
    return _classify_method_call(func, call)


def _classify_method_call(func: ast.expr, call: ast.Call) -> tuple[str, str, ast.expr] | None:
    if not isinstance(func, ast.Attribute):
        return None
    if func.attr in {"write_text", "write_bytes"}:
        return (func.attr, "w", func.value)
    if func.attr == "open":
        mode = _mode_text(_positional_or_keyword(call, 0, "mode"), "r")
        return ("Path.open", mode, func.value) if _is_write_mode(mode) else None
    return None


def scan_write_sites(module: str, tree: ast.Module) -> list[WriteSite]:
    """Every write-mode file operation in ``tree`` with its resolved path text."""
    ctx = _build_context(tree)
    resolver = _Resolver(ctx)
    sites: list[WriteSite] = []
    for node in ctx.calls:
        classified = _classify_call(node)
        if classified is None:
            continue
        kind, mode, path = classified
        text = resolver.resolve(path, _enclosing_function(ctx.parents, node))
        sites.append(WriteSite(module, node.lineno, kind, mode, ast.unparse(path), text))
    return sites


def scan_write_sites_from_source(module: str, source: str) -> list[WriteSite]:
    return scan_write_sites(module, ast.parse(source))


def module_name_for(path: Path, src_root: Path = _SRC) -> str:
    parts = list(path.relative_to(src_root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


@dataclass(frozen=True)
class TreeScan:
    events_writes: tuple[WriteSite, ...]
    unresolved_writes: tuple[WriteSite, ...]
    lock_composition_modules: frozenset[str]


def has_lock_call_site(tree: ast.AST) -> bool:
    """True when ``tree`` calls ``feature_status_lock(`` bare or as an attribute."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
        if name == "feature_status_lock":
            return True
    return False


def scan_src_tree(src_source_tree: Mapping[Path, SourceFile]) -> TreeScan:
    events_writes: list[WriteSite] = []
    unresolved: list[WriteSite] = []
    lock_modules: set[str] = set()
    for path, entry in src_source_tree.items():
        module = module_name_for(path)
        tree = entry.tree
        assert isinstance(tree, ast.Module)
        sites = scan_write_sites(module, tree)
        events_writes.extend(site for site in sites if site.targets_events_log)
        unresolved.extend(site for site in sites if site.path_text is None)
        if module != "specify_cli.status.locking" and has_lock_call_site(tree):
            lock_modules.add(module)
    return TreeScan(tuple(events_writes), tuple(unresolved), frozenset(lock_modules))


def out_of_store_site_counts(events_writes: Iterable[WriteSite]) -> Counter[tuple[str, str, str]]:
    """How many event-log write sites each (module, kind, path_expr) key carries outside the store."""
    return Counter(site.key for site in events_writes if site.module != STORE_MODULE)


def out_of_store_violations(events_writes: Iterable[WriteSite]) -> list[WriteSite]:
    """Every out-of-store site whose key is absent from the ledger or carries more sites than it allows.

    An over-counted key reports ALL of its sites (the ledger is line-number
    independent, so no single site is "the extra one"); the failure message
    carries the allowed/found counts.
    """
    sites = list(events_writes)
    found = out_of_store_site_counts(sites)
    over = {key for key, count in found.items() if count > ALLOWED_OUT_OF_STORE_WRITE_SITES.get(key, 0)}
    return [site for site in sites if site.key in over]


def ledger_shortfall(events_writes: Iterable[WriteSite]) -> dict[tuple[str, str, str], tuple[int, int]]:
    """Ledger keys with fewer live sites than allowed: ``{key: (allowed, found)}`` (stale or under-counted)."""
    found = out_of_store_site_counts(events_writes)
    return {key: (allowed, found[key]) for key, allowed in ALLOWED_OUT_OF_STORE_WRITE_SITES.items() if found[key] < allowed}


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def tree_scan(src_source_tree: Mapping[Path, SourceFile]) -> TreeScan:
    return scan_src_tree(src_source_tree)


def test_no_out_of_store_writes(tree_scan: TreeScan) -> None:
    """Every resolved write of a status.events.jsonl path lives in store.py (or the ledger)."""
    violations = out_of_store_violations(tree_scan.events_writes)
    found = out_of_store_site_counts(tree_scan.events_writes)
    assert not violations, (
        "status.events.jsonl is written outside specify_cli.status.store:\n"
        + "\n".join(
            f"  {site.module}:{site.lineno} {site.kind}({site.path_expr}, {site.mode!r})"
            f" [ledger allows {ALLOWED_OUT_OF_STORE_WRITE_SITES.get(site.key, 0)}, found {found[site.key]}]"
            for site in violations
        )
        + "\n\nRoute the write through the status FSM (emit_status_transition / BookkeepingTransaction); "
        "raw appends go through store.py behind status/_unsafe.py (FR-010/FR-011)."
    )


def test_store_writes_are_found(tree_scan: TreeScan) -> None:
    """Positive census: the scanner sees the store's own writes, so the gate is not empty."""
    store_sites = [site for site in tree_scan.events_writes if site.module == STORE_MODULE]
    assert store_sites, "the scanner found no status.events.jsonl write in store.py -- the gate matches nothing"
    # append_event's ``path.open("a")`` and append_raw_rows_atomic's ``os.replace(tmp, path)``.
    assert {(site.kind, site.mode) for site in store_sites} == {("Path.open", "a"), ("os.replace", "replace")}, store_sites
    assert {site.module for site in tree_scan.events_writes if site.key not in ALLOWED_OUT_OF_STORE_WRITE_SITES} == {STORE_MODULE}


def test_allowed_out_of_store_sites_are_live(tree_scan: TreeScan) -> None:
    """A ledger entry with fewer live sites than it allows is stale and must shrink (shrink-only)."""
    shortfall = ledger_shortfall(tree_scan.events_writes)
    assert not shortfall, f"stale or over-counted ALLOWED_OUT_OF_STORE_WRITE_SITES entries {{key: (allowed, found)}}: {shortfall}"
    assert all(allowed >= 1 for allowed in ALLOWED_OUT_OF_STORE_WRITE_SITES.values())


def test_unresolved_write_paths_are_pinned(tree_scan: TreeScan) -> None:
    """Unresolved is not a pass: event-named dynamic writes and the known dynamic writers are pinned.

    Contract section 2. A new unresolved write whose path expression is
    event-named is a change to the write surface and must be reviewed; a
    known dynamic writer that resolves (or disappears) must be re-classified.
    """
    unresolved = {site.key for site in tree_scan.unresolved_writes}
    event_named = {site.key for site in tree_scan.unresolved_writes if site.is_event_named}
    assert event_named == EXPECTED_UNRESOLVED_EVENT_NAMED_WRITE_SITES, (
        "event-named unresolved write sites changed.\n"
        f"  new: {sorted(event_named - EXPECTED_UNRESOLVED_EVENT_NAMED_WRITE_SITES)}\n"
        f"  gone: {sorted(EXPECTED_UNRESOLVED_EVENT_NAMED_WRITE_SITES - event_named)}"
    )
    missing = KNOWN_DYNAMIC_EVENT_LOG_WRITE_SITES - unresolved
    assert not missing, f"known dynamic event-log writers no longer found unresolved: {sorted(missing)}"


def test_lock_composition_census(tree_scan: TreeScan) -> None:
    """R14: the set of modules composing ``feature_status_lock(`` is exactly the census."""
    found = tree_scan.lock_composition_modules
    assert found, "no feature_status_lock( call site found anywhere -- the census scan is vacuous"
    assert found == EXPECTED_LOCK_COMPOSITION_SITES, (
        "feature_status_lock composition sites changed.\n"
        f"  new: {sorted(found - EXPECTED_LOCK_COMPOSITION_SITES)}\n"
        f"  gone: {sorted(EXPECTED_LOCK_COMPOSITION_SITES - found)}\n"
        "A new lock + append composition is a new writer shell: route through the two shells in "
        "kitty-specs/fsm-write-path-integrity-01M1TZV6/contracts/emit-pipeline.md section 2, or "
        "update the census here AND design-notes/WP03-gates.md with the justification."
    )


# ---------------------------------------------------------------------------
# Non-vacuity floor (contract section 3)
# ---------------------------------------------------------------------------

_SYNTHETIC_WRITERS: tuple[tuple[str, str, str], ...] = (
    (
        "open-append-local-name",
        'from pathlib import Path\ndef bad(root: Path) -> None:\n    p = root / "status.events.jsonl"\n    with open(p, "a") as fh:\n        fh.write("x")\n',
        "open",
    ),
    ("path-open-ab", 'def bad(root):\n    (root / "status.events.jsonl").open("ab").truncate(0)\n', "Path.open"),
    ("write-text", 'def bad(root):\n    Path(str(root / "status.events.jsonl")).write_text("")\n', "write_text"),
    ("write-bytes-fstring", 'def bad(root):\n    Path(f"{root}/status.events.jsonl").write_bytes(b"")\n', "write_bytes"),
    ("os-open-flags", 'import os\ndef bad(root):\n    os.open(root / "status.events.jsonl", os.O_WRONLY | os.O_APPEND)\n', "os.open"),
    ("os-replace-destination", 'import os\ndef bad(root, tmp):\n    os.replace(tmp, root / "status.events.jsonl")\n', "os.replace"),
    ("shutil-move-keyword", 'import shutil\ndef bad(root, tmp):\n    shutil.move(tmp, dst=str(root / "status.events.jsonl"))\n', "shutil.move"),
    (
        "events-filename-alias",
        'from specify_cli.status import EVENTS_FILENAME as _EV\ndef bad(d):\n    with (d / _EV).open("a") as fh:\n        fh.write("")\n',
        "Path.open",
    ),
    ("module-constant", 'LOG = "status.events.jsonl"\ndef bad(d):\n    open(d / LOG, "w")\n', "open"),
    (
        "self-attribute",
        'class T:\n    def __init__(self, d):\n        self._p = d / "status.events.jsonl"\n    def roll(self):\n        self._p.open("ab").truncate(0)\n',
        "Path.open",
    ),
    (
        "same-module-function-return",
        'EV = "status.events.jsonl"\ndef _p(d):\n    return d / EV\ndef bad(d):\n    with _p(d).open("a") as fh:\n        fh.write("")\n',
        "Path.open",
    ),
    (
        "parameter-via-call-site",
        'def _w(p, row):\n    with p.open("a") as fh:\n        fh.write(row)\ndef bad(d):\n    _w(d / "status.events.jsonl", "x")\n',
        "Path.open",
    ),
    (
        "keyword-only-parameter-via-call-site",
        'def _w(*, events_path):\n    events_path.open("ab").truncate(0)\ndef bad(d):\n    _w(events_path=d / "status.events.jsonl")\n',
        "Path.open",
    ),
    (
        "constructor-parameter-via-self",
        "class T:\n    def __init__(self, events_path):\n        self._e = events_path\n"
        '    def roll(self):\n        self._e.open("ab").truncate(0)\n'
        'def mk(d):\n    return T(d / "status.events.jsonl")\n',
        "Path.open",
    ),
    ("unknown-mode-is-fail-closed", 'def bad(d, mode):\n    open(d / "status.events.jsonl", mode)\n', "open"),
)


@pytest.mark.parametrize(("case", "source", "kind"), _SYNTHETIC_WRITERS, ids=[case for case, _, _ in _SYNTHETIC_WRITERS])
def test_writes_gate_is_not_vacuous(case: str, source: str, kind: str, tree_scan: TreeScan) -> None:
    """Every write shape and resolution rule reports exactly one event-log write in a rogue module."""
    sites = scan_write_sites_from_source("specify_cli.synthetic.rogue_writer", source)
    hits = [site for site in sites if site.targets_events_log]
    assert len(hits) == 1, f"{case}: expected one event-log write, scanner reported {sites}"
    assert hits[0].kind == kind
    assert out_of_store_violations(hits) == hits
    assert tree_scan.events_writes, "real-tree scan matched zero writers"


#: One allowed write shape per ledger kind, as a function template: ``{name}``
#: lets the floor duplicate the SAME site shape (same key) under a second
#: function in the SAME module, which is exactly what a per-key count must catch.
_LEDGERED_SHAPES: tuple[tuple[str, str, tuple[str, str, str]], ...] = (
    (
        "path-open-truncate",
        'def {name}(d):\n    events_path = d / "status.events.jsonl"\n    events_path.open("ab").truncate(0)\n',
        ("specify_cli.coordination.status_transition", "Path.open", "events_path"),
    ),
    (
        "os-replace-rewrite",
        'import os\ndef {name}(d, tmp):\n    events_file = d / "status.events.jsonl"\n    os.replace(str(tmp), str(events_file))\n',
        ("specify_cli.migration.rebuild_state", "os.replace", "str(events_file)"),
    ),
)


@pytest.mark.parametrize(("case", "template", "key"), _LEDGERED_SHAPES, ids=[case for case, _, _ in _LEDGERED_SHAPES])
def test_writes_gate_counts_ledgered_sites(case: str, template: str, key: tuple[str, str, str]) -> None:
    """A second identical write shape in an allowed module is reported; the single ledgered one is not."""
    module = key[0]
    assert ALLOWED_OUT_OF_STORE_WRITE_SITES[key] == 1
    single = scan_write_sites_from_source(module, template.format(name="one"))
    assert [site.key for site in single if site.targets_events_log] == [key], f"{case}: template does not produce the ledger key"
    assert out_of_store_violations(single) == []
    doubled = scan_write_sites_from_source(module, template.format(name="one") + template.format(name="two"))
    hits = [site for site in doubled if site.targets_events_log]
    assert out_of_store_site_counts(hits)[key] == 2
    violations = out_of_store_violations(hits)
    assert violations == hits, f"{case}: a duplicated allowed write shape slipped through on the ledger key"
    assert key not in ledger_shortfall(hits)
    assert ledger_shortfall(single[:0]) == dict.fromkeys(ALLOWED_OUT_OF_STORE_WRITE_SITES, (1, 0)), "an empty scan must report every ledger key short"


def test_writes_gate_ignores_reads_and_other_files() -> None:
    """Reads of the event log and writes of other files are not reported."""
    benign = (
        'def ok(d):\n    with open(d / "status.events.jsonl", "r") as fh:\n        fh.read()\n'
        '    (d / "status.events.jsonl").read_text()\n'
        '    with open(d / "other.jsonl", "a") as fh:\n        fh.write("")\n'
        '    (d / "status.events.jsonl.tmp").open("w").write("")\n'
    )
    sites = scan_write_sites_from_source("specify_cli.synthetic.reader", benign)
    assert [site for site in sites if site.targets_events_log] == []
    assert [site.path_text for site in sites] == ["other.jsonl", "status.events.jsonl.tmp"]


def test_writes_gate_reports_unresolved_paths_instead_of_passing() -> None:
    """A parameter with no or disagreeing call sites is reported unresolved, never as clean."""
    orphan = scan_write_sites_from_source("specify_cli.synthetic.dynamic", 'def w(events_path):\n    with open(events_path, "a") as fh:\n        fh.write("")\n')
    assert len(orphan) == 1 and orphan[0].path_text is None and orphan[0].is_event_named
    disagreeing = 'def w(p):\n    p.write_text("")\ndef a(d):\n    w(d / "status.events.jsonl")\ndef b(d):\n    w(d / "status.json")\n'
    sites = scan_write_sites_from_source("specify_cli.synthetic.dynamic", disagreeing)
    assert len(sites) == 1 and sites[0].path_text is None and not sites[0].targets_events_log


def test_lock_census_scanner_sees_both_call_shapes() -> None:
    """Bare and attribute ``feature_status_lock(`` calls are both census hits."""
    assert has_lock_call_site(ast.parse("with feature_status_lock(root, name):\n    pass\n"))
    assert has_lock_call_site(ast.parse("with _tasks.feature_status_lock(root, name):\n    pass\n"))
    assert not has_lock_call_site(ast.parse("lock = feature_status_lock\nfeature_status_lock_path(root, name)\n"))
