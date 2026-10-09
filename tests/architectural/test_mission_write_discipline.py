"""Mission write-discipline gate (#5819, #5883): the one-writer rules, by construction.

AST rules over ``src/specify_cli/**/*.py`` (and, for rule 1, ``src/runtime``) close
the defect class behind concurrent writers of one Mission checkout losing each
other's data:

1. **Status and run logs are only rewritten by construction-safe code.**
   * Any ``truncate`` / ``ftruncate`` shape and any ``.unlink(`` of an expression
     naming the event log is flagged outside the primitive
     ``src/specify_cli/status/mission_write.py``.
   * A *whole-file rewrite* of a status log (``status.events.jsonl``) or a run
     log / run state (``run.events.jsonl`` / ``state.json``) is flagged. The
     sinks are ``write_text`` / ``write_bytes``, a clobbering ``open`` (a mode
     with ``w`` or ``r+`` — never append ``a`` nor exclusive-create ``x``, which
     cannot clobber), ``shutil.move`` / ``os.replace`` onto the log, and
     ``atomic_write`` onto the log. A target is recognised by dataflow (a name
     assigned from a ``<dir> / "<logfile>"`` join, or an alias of one),
     plus the variable-name hints ``events_path`` / ``events_file`` and the
     filename-constant identifiers ``EVENTS_FILENAME`` / ``STATE_FILE`` (A7).
     ``src/runtime`` is scanned with the run-log and run-state names (FR-008).

   **Stated structural non-sinks** (each has a near-miss test):
   * an append-only ``open(..., "a")`` — the engine's ``_append_event`` and
     ``status/store.py``'s canonical append never clobber;
   * an exclusive create ``open(..., "x")`` — it fails if the file exists, so it
     cannot clobber an earlier writer's log (the lane auto-rebase hydrate uses
     this);
   * the tmp-then-``os.replace`` publish of a freshly built file — when the
     ``os.replace`` / ``shutil.move`` source is a name opened ``"w"``/``"x"`` in
     the same function, the replace publishes fresh content and clobbers nothing
     the function re-read from the target (the engine's ``_write_snapshot``,
     ``migration/rebuild_state.py``). A replace whose source was NOT freshly
     written is still a sink;
   * a rewrite inside a lexical Mission-lock region (``with mission_write_lock``
     / ``feature_status_lock`` / ``coord_status_lock``) — a serialised rewrite is
     the legitimate read-modify-write pattern (the consolidation bookkeeping
     projection does this under the status lock);
   * the primitive itself.

   **Stated exclusion — the git merge driver** (``consolidation/drivers.py``):
   its writers (``ours.write_text(...)``) target the ``%A`` path git hands the
   driver as *argv* (a function parameter), never a name derived from a logfile
   constant, so no target is tracked and the driver is excluded by construction,
   never by an allowlist entry.

2. **Read/sink pairs in one locked region (FR-006, A11).** A registered sink
   (``append_activity_log``, ``_append_entry``) must sit in a *locked region*. A
   callable passed into a lock region is accepted only when its reference is
   *solely* the function of a call: passing it as an argument or keyword
   (``Thread(target=f)``, ``submit(f)``, ``partial(f)``), returning it, assigning
   it or capturing it in a nested ``def`` / ``lambda`` is an escape, and an
   unresolvable callee fails closed.
3. **Locks use the canonical key and path (A6).**
   * ``feature_status_lock(<root>, <key>)``: ``<key>`` is accepted only as
     ``mission_lock_key(...)`` — directly, as a function parameter, or as a name
     assigned from ``mission_lock_key(...)``. A bare ``.name``, a subscript, or a
     ``slug``-named value is refused.
   * ``mission_write_lock(<path>, ...)`` / ``hold_mission_write_lock(<path>,
     ...)``: the first argument's shape is checked. A bare ``.name`` string, a
     subscript, or a ``slug``-named value is refused (a Mission *directory*, a
     ``mission_write_lock_dir(...)`` result, or a parameter is accepted).
   * **One-frame limit (known, pinned as a strict ``xfail`` in the rule-3 offender
     table):** a bare parameter is trusted as canonical and its callers are not
     followed, so ``def helper(root, slug_key): feature_status_lock(root, slug_key)``
     passes even when a caller hands it a non-canonical key (same for a
     ``mission_write_lock`` path parameter). Following callers would need
     cross-module call resolution (the real tree's parameter keys are passed in
     from other modules), which is disproportionate here.
4. **``meta.json`` / work-package / ``tasks.md`` writes stay inside the lock
   (FR-019, A5, D5).** The sinks are ``write_meta``, ``restore_meta_text``,
   ``write_frontmatter`` and ``update_fields`` (the last two only when a path
   argument resolves to ``tasks/WP*.md`` or ``tasks.md``, so
   ``review/prompt_metadata.py``'s temporary file is a near-miss, C-007), plus
   ``write_text`` / ``write_bytes`` / ``atomic_write`` whose target resolves to
   ``meta.json`` / ``tasks/WP*.md`` / ``tasks.md``. A sink is accepted when it
   sits in a *lock region* — a lexical ``with`` of a lock context manager, a
   ``with <name>`` whose name was assigned from one, ``ExitStack.enter_context``
   of one, a manual ``__enter__`` … ``__exit__`` span, or
   ``locked_acceptance_verdict_guard`` — or when its enclosing function is a
   self-locking named sink (``restore_meta_text``), or when EVERY same-module
   call site of its enclosing function sits in a region (the status-core emit
   lock and ``BookkeepingTransaction`` are recognised this way, structurally).
   A callee whose call sites cannot be resolved fails closed. The git merge
   driver writes the ``%A`` argv path (a parameter), so no target is tracked and
   it is excluded by construction, never by an allowlist entry.

All allowlists are EMPTY; the only excluded file is the primitive's own module. A
hit is a finding to fix, not to list.
"""

from __future__ import annotations

import ast
import copy
import functools
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SPECIFY_CLI = _REPO_ROOT / "src" / "specify_cli"
_RUNTIME = _REPO_ROOT / "src" / "runtime"
_PRIMITIVE = "src/specify_cli/status/mission_write.py"
_TASKS = "src/specify_cli/cli/commands/agent/tasks.py"
_TRACER = "src/specify_cli/retrospective/tracer_writer.py"
_BOOKKEEPING = "src/specify_cli/consolidation/bookkeeping_projection.py"
_AUTO_REBASE = "src/specify_cli/lanes/auto_rebase.py"
_MIN_SCANNED_FILES = 300

_TRUNCATE_NAMES = frozenset({"truncate", "ftruncate"})
_TRUNCATE_HOSTS = frozenset({"os", "posix"})
_STRING_LOOKUPS = frozenset({"getattr", "methodcaller"})
_EVENT_LOG_TOKENS = ("events_path", "EVENTS_FILENAME", "status.events.jsonl")
_LOCK_CMS = frozenset({"mission_write_lock", "feature_status_lock", "coord_status_lock"})
_TRANSFORM_PRIMITIVE = "locked_rewrite_text"
_STATUS_LOCK = "feature_status_lock"
_PATH_LOCKS = frozenset({"mission_write_lock", "hold_mission_write_lock"})
_KEY_FACTORY = "mission_lock_key"
_PATH_FACTORY = "mission_write_lock_dir"
_TRANSFORM = "transform"
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
_Scope = ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda

# Rule 1 whole-file targets: the status log and the run log / run state. meta.json
# and work-package frontmatter are Rule 4's targets (WP15), not rule 1's.
_LOG_LITERAL_TOKENS = frozenset({"status.events.jsonl", "run.events.jsonl", "state.json"})
_LOG_NAME_TOKENS = ("EVENTS_FILENAME", "STATE_FILE")
_LOG_VAR_HINTS = ("events_path", "events_file")
_WRAP_CALLS = frozenset({"str", "Path", "fspath"})
_OS_HOSTS = frozenset({"os", "posix"})

# Allowlists are intentionally empty (shrink-only at zero). The only exclusion is
# the primitive's own module, per NFR-004 ("the primitive's own sites").
_ALLOWED_TRUNCATE_FILES: frozenset[str] = frozenset({_PRIMITIVE})
_RULE1_EXCLUDED_FILES: frozenset[str] = frozenset({_PRIMITIVE})
_RULE3_EXCLUDED_FILES: frozenset[str] = frozenset({_PRIMITIVE})
_RULE4_EXCLUDED_FILES: frozenset[str] = frozenset({_PRIMITIVE})

# ------------------------------------------------------------------- rule 4 vocabulary (A5/D5)
_META_MODULE = "src/specify_cli/mission_metadata.py"
#: Lock context managers recognised by rule 4's region analysis (A5).
_RULE4_LOCK_CMS = frozenset({"mission_write_lock", "hold_mission_write_lock", "feature_status_lock", "coord_status_lock", "locked_acceptance_verdict_guard"})
#: Named sinks that always write ``meta.json``.
_META_SINK_NAMES = frozenset({"write_meta", "restore_meta_text"})
#: Named sinks that write a work-package / ``tasks.md`` file only when a path argument resolves to one.
_WP_SINK_NAMES = frozenset({"write_frontmatter", "update_fields"})
_NAMED_SINK_NAMES = _META_SINK_NAMES | _WP_SINK_NAMES
_RAW_WRITE_ATTRS = frozenset({"write_text", "write_bytes"})
_ATOMIC_WRITE_NAME = "atomic_write"
_MISSION_FILE_LITERALS = frozenset({"meta.json", "tasks.md"})
_MISSION_FILE_NAME_TOKENS = ("META_FILENAME",)
#: Variable-name hints for a tracked Mission-file target (A7-style dataflow hint).
_MISSION_FILE_VAR_HINTS = ("meta_path", "meta_file", "wp_file", "wp_path", "task_file", "tasks_md", "wp_md", "work_package_file")
_WP_FILE_LITERAL = re.compile(r"WP[\w-]*\.md")
_ENTER = "__enter__"
_EXIT = "__exit__"
_ENTER_CONTEXT = "enter_context"


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


# --------------------------------------------------------------------------- rule 1: truncate/unlink


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


# --------------------------------------------------------------------------- rule 1: whole-file rewrites


def _unwrap_wrap(node: ast.AST) -> ast.AST:
    """Peel ``str(...)`` / ``Path(...)`` / ``os.fspath(...)`` single-arg wrappers off *node*."""
    while isinstance(node, ast.Call) and _call_name(node.func) in _WRAP_CALLS and len(node.args) == 1:
        node = node.args[0]
    return node


def _mentions_exact_literal(node: ast.AST) -> bool:
    """True when *node* contains a string constant equal to a log filename (never a ``.tmp`` variant)."""
    return any(isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value in _LOG_LITERAL_TOKENS for n in ast.walk(node))


def _is_filename_join(node: ast.AST) -> bool:
    """True when *node* is a ``<dir> / "<logfile>"`` (or ``/ EVENTS_FILENAME``) path join."""
    if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)):
        return False
    if _mentions_exact_literal(node):
        return True
    text = ast.unparse(node)
    return any(tok in text for tok in _LOG_NAME_TOKENS)


def _assigned_names(stmt: ast.AST) -> list[str]:
    if isinstance(stmt, ast.Assign):
        return [t.id for t in stmt.targets if isinstance(t, ast.Name)]
    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value is not None:
        return [stmt.target.id]
    return []


def _assign_value(stmt: ast.AST) -> ast.AST | None:
    return getattr(stmt, "value", None)


def _tracked_log_names(func: ast.AST) -> frozenset[str]:
    """Names in *func* that hold a status/run log: assigned from a filename join, or an alias of one."""
    tracked: set[str] = set()
    assigns = [n for n in ast.walk(func) if isinstance(n, ast.Assign | ast.AnnAssign)]
    changed = True
    while changed:
        changed = False
        for stmt in assigns:
            value = _assign_value(stmt)
            if value is None:
                continue
            if not _value_is_log_source(value, tracked):
                continue
            for name in _assigned_names(stmt):
                if name not in tracked:
                    tracked.add(name)
                    changed = True
    return frozenset(tracked)


def _value_is_log_source(value: ast.AST, tracked: frozenset[str] | set[str]) -> bool:
    inner = _unwrap_wrap(value)
    if isinstance(inner, ast.Name) and inner.id in tracked:
        return True
    return _is_filename_join(inner)


def _is_log_target(expr: ast.AST, tracked: frozenset[str]) -> bool:
    """True when the sink target *expr* denotes a status log or a run log / run state."""
    inner = _unwrap_wrap(expr)
    if isinstance(inner, ast.Name) and inner.id in tracked:
        return True
    text = ast.unparse(expr)
    if any(hint in text for hint in _LOG_VAR_HINTS):
        return True
    if any(tok in text for tok in _LOG_NAME_TOKENS):
        return True
    return _mentions_exact_literal(expr)


def _str_arg(call: ast.Call, index: int, keyword: str) -> str | None:
    candidates: list[ast.expr] = []
    if len(call.args) > index:
        candidates.append(call.args[index])
    candidates.extend(kw.value for kw in call.keywords if kw.arg == keyword)
    for node in candidates:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            result: str = node.value
            return result
    return None


def _open_target_and_mode(call: ast.Call) -> tuple[ast.AST, str] | None:
    """For ``open(target, mode)`` or ``target.open(mode)`` return ``(target, mode)`` (default ``"r"``)."""
    func = call.func
    if isinstance(func, ast.Name) and func.id == "open":
        if not call.args:
            return None
        return call.args[0], _str_arg(call, 1, "mode") or "r"
    if isinstance(func, ast.Attribute) and func.attr == "open":
        return func.value, _str_arg(call, 0, "mode") or "r"
    return None


def _is_clobber_mode(mode: str) -> bool:
    """True for an ``open`` mode that can overwrite existing content.

    ``a`` (append) and ``x`` (exclusive create) never clobber an existing file,
    so they are not sinks; ``w`` truncates and ``r+`` overwrites in place.
    """
    if "a" in mode or "x" in mode:
        return False
    return "w" in mode or "+" in mode


def _is_os_replace(func: ast.AST) -> bool:
    return isinstance(func, ast.Attribute) and func.attr == "replace" and isinstance(func.value, ast.Name) and func.value.id in _OS_HOSTS


def _is_shutil_move(func: ast.AST) -> bool:
    return isinstance(func, ast.Attribute) and func.attr == "move" and isinstance(func.value, ast.Name) and func.value.id == "shutil"


def _wholefile_sinks(func: ast.AST) -> list[tuple[ast.Call, ast.AST, str, ast.AST | None]]:
    """Yield ``(node, target, kind, source)`` whole-file write sinks in *func*; ``source`` set for move/replace."""
    sinks: list[tuple[ast.Call, ast.AST, str, ast.AST | None]] = []
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute) and node.func.attr in ("write_text", "write_bytes"):
            sinks.append((node, node.func.value, node.func.attr, None))
        opened = _open_target_and_mode(node)
        if opened is not None and _is_clobber_mode(opened[1]):
            sinks.append((node, opened[0], f"open({opened[1]!r})", None))
        if _is_os_replace(node.func) and len(node.args) >= 2:
            sinks.append((node, node.args[1], "os.replace", node.args[0]))
        if _is_shutil_move(node.func) and len(node.args) >= 2:
            sinks.append((node, node.args[1], "shutil.move", node.args[0]))
        if _call_name(node.func) == "atomic_write" and node.args:
            sinks.append((node, node.args[0], "atomic_write", None))
    return sinks


def _tuple_or_name_target_ids(target: ast.AST) -> set[str]:
    """The ``Name`` ids bound by one assignment target: a bare name or a tuple/list unpack.

    Distinct from the statement-level :func:`_assigned_names` (bare names only);
    this one reaches the tuple elements of ``fd, tmp_name = tempfile.mkstemp(...)``.
    """
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, ast.Tuple | ast.List):
        return {elt.id for elt in target.elts if isinstance(elt, ast.Name)}
    return set()


def _freshly_written_names(func: ast.AST) -> frozenset[str]:
    """Names in *func* that hold a freshly-created file, not a name re-read from a target.

    Two seeds, then alias propagation:

    * a name opened ``"w"``/``"x"`` (``open(name, "w")`` / ``name.open("w")``);
    * a name bound from ``tempfile.mkstemp(...)`` -- the secure unique-temp idiom
      (``fd, tmp_name = tempfile.mkstemp(...)``), whose staged file the caller then
      writes through the returned fd (``os.fdopen(fd, "w")``) and publishes with
      ``os.replace`` (the engine's ``_write_snapshot``, #5854 concurrency form).

    An alias assigned solely from a fresh name -- ``tmp = Path(tmp_name)`` -- is
    itself fresh, so the ``os.replace`` source resolves to a staged temp and the
    publish is recognised as a non-sink.
    """
    names: set[str] = set()
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        opened = _open_target_and_mode(node)
        if opened is not None:
            target, mode = opened
            if "w" in mode or "x" in mode:
                inner = _unwrap_wrap(target)
                if isinstance(inner, ast.Name):
                    names.add(inner.id)
    for node in ast.walk(func):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and _call_name(node.value.func) == "mkstemp":
            for tgt in node.targets:
                names |= _tuple_or_name_target_ids(tgt)
    # Propagate: a name assigned solely from a fresh name (optionally through a
    # ``Path(...)`` / ``str(...)`` wrapper) is itself fresh. Iterate to a fixpoint
    # so a chain of aliases resolves regardless of source order.
    changed = True
    while changed:
        changed = False
        for node in ast.walk(func):
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            lhs = node.targets[0]
            if not isinstance(lhs, ast.Name) or lhs.id in names:
                continue
            inner = _unwrap_wrap(node.value)
            if isinstance(inner, ast.Name) and inner.id in names:
                names.add(lhs.id)
                changed = True
    return frozenset(names)


def _functions(tree: ast.AST) -> list[ast.AST]:
    return [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)]


def _nearest_function(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> ast.AST | None:
    cur = parents.get(node)
    while cur is not None:
        if isinstance(cur, ast.FunctionDef | ast.AsyncFunctionDef):
            return cur
        cur = parents.get(cur)
    return None


def _is_tmp_publish(source: ast.AST, fresh: frozenset[str]) -> bool:
    inner = _unwrap_wrap(source)
    return isinstance(inner, ast.Name) and inner.id in fresh


def find_wholefile_rewrite_sites(tree: ast.AST) -> list[tuple[int, str]]:
    """Whole-file rewrites of a status/run log that are not locked and not a structural non-sink."""
    parents = _parents(tree)
    scopes = [*_functions(tree), tree]
    tracked_by_scope: dict[ast.AST, frozenset[str]] = {scope: _tracked_log_names(scope) for scope in scopes}
    fresh_by_scope: dict[ast.AST, frozenset[str]] = {scope: _freshly_written_names(scope) for scope in scopes}
    findings: list[tuple[int, str]] = []
    for scope in _functions(tree):
        tracked, fresh = tracked_by_scope[scope], fresh_by_scope[scope]
        findings += _scope_wholefile_findings(scope, parents, tracked, fresh)
    findings += _module_level_wholefile_findings(tree, parents, tracked_by_scope[tree], fresh_by_scope[tree])
    return sorted(set(findings))


def _scope_wholefile_findings(
    scope: ast.AST,
    parents: dict[ast.AST, ast.AST],
    tracked: frozenset[str],
    fresh: frozenset[str],
) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    for node, target, kind, source in _wholefile_sinks(scope):
        if _nearest_function(node, parents) is not scope:
            continue
        if not _is_log_target(target, tracked):
            continue
        if _lock_withs_enclosing(node, parents):
            continue
        if source is not None and _is_tmp_publish(source, fresh):
            continue
        findings.append((getattr(node, "lineno", 0), f"{kind} whole-file rewrite of a status/run log outside a Mission-lock region"))
    return findings


def _module_level_wholefile_findings(
    tree: ast.AST,
    parents: dict[ast.AST, ast.AST],
    tracked: frozenset[str],
    fresh: frozenset[str],
) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    for node, target, kind, source in _wholefile_sinks(tree):
        if _nearest_function(node, parents) is not None:
            continue
        if not _is_log_target(target, tracked):
            continue
        if _lock_withs_enclosing(node, parents):
            continue
        if source is not None and _is_tmp_publish(source, fresh):
            continue
        findings.append((getattr(node, "lineno", 0), f"{kind} whole-file rewrite of a status/run log outside a Mission-lock region"))
    return findings


# --------------------------------------------------------------------------- rule 2 (owned by WP15)


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


# --------------------------------------------------------------------------- rule 3: canonical lock key/path


def _lock_key(call: ast.Call) -> ast.AST | None:
    if len(call.args) > 1:
        return call.args[1]
    return next((k.value for k in call.keywords if k.arg == "lock_key"), None)


def _func_params(func: ast.AST | None) -> frozenset[str]:
    if not isinstance(func, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
        return frozenset()
    args = func.args
    names = {p.arg for p in (*args.posonlyargs, *args.args, *args.kwonlyargs)}
    if args.vararg:
        names.add(args.vararg.arg)
    if args.kwarg:
        names.add(args.kwarg.arg)
    return frozenset(names)


def _assignments_of(func: ast.AST, name: str) -> list[ast.AST]:
    values: list[ast.AST] = []
    for node in ast.walk(func):
        value = _assign_value(node)
        if value is not None and name in _assigned_names(node):
            values.append(value)
    return values


def _is_key_factory_call(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and _call_name(node.func) == _KEY_FACTORY


def _key_is_canonical(key: ast.AST, func: ast.AST | None) -> bool:
    """True when *key* is ``mission_lock_key(...)`` directly, a parameter, or a name assigned from it."""
    if _is_key_factory_call(key):
        return True
    if isinstance(key, ast.Name) and func is not None:
        if key.id in _func_params(func):
            return True
        assigns = _assignments_of(func, key.id)
        return bool(assigns) and all(_is_key_factory_call(value) for value in assigns)
    return False


def _path_refusal(path: ast.AST) -> str | None:
    """Why *path* is an unacceptable Mission-write-lock path argument, or ``None`` when acceptable."""
    if isinstance(path, ast.Attribute) and path.attr == "name":
        return "a bare .name string, not the Mission directory"
    if isinstance(path, ast.Subscript):
        return "a subscript, not the Mission directory"
    ident = _call_name(path)
    if ident is not None and "slug" in ident.lower():
        return "a slug-named value, not the Mission directory"
    return None


def find_lock_shape_findings(tree: ast.AST) -> list[tuple[int, str]]:
    """Rule 3 findings: non-canonical ``feature_status_lock`` keys and bad ``mission_write_lock`` paths."""
    parents = _parents(tree)
    findings: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node.func)
        if name == _STATUS_LOCK:
            key = _lock_key(node)
            if key is not None and not _key_is_canonical(key, _enclosing_scope(node, parents)):
                findings.append((node.lineno, f"{_STATUS_LOCK} key must be {_KEY_FACTORY}(...): {ast.unparse(key)}"))
        elif name in _PATH_LOCKS and node.args:
            reason = _path_refusal(node.args[0])
            if reason is not None:
                findings.append((node.lineno, f"{name} path is {reason}: {ast.unparse(node.args[0])}"))
    return sorted(findings)


# --------------------------------------------------------------------------- rule 4 (owned by WP15): meta/frontmatter/tasks writers


def _mentions_mission_literal(node: ast.AST) -> bool:
    """True when *node* holds a string constant equal to ``meta.json`` or ``tasks.md``."""
    return any(isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value in _MISSION_FILE_LITERALS for n in ast.walk(node))


def _is_mission_filename_join(node: ast.AST) -> bool:
    """True when *node* is a ``<dir> / "<mission file>"`` join (meta.json / tasks.md / ``WP*.md`` / META_FILENAME)."""
    if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)):
        return False
    if _mentions_mission_literal(node):
        return True
    text = ast.unparse(node)
    return any(tok in text for tok in _MISSION_FILE_NAME_TOKENS) or bool(_WP_FILE_LITERAL.search(text))


def _rule4_value_is_source(value: ast.AST, tracked: frozenset[str] | set[str]) -> bool:
    inner = _unwrap_wrap(value)
    if isinstance(inner, ast.Name) and inner.id in tracked:
        return True
    return _is_mission_filename_join(inner)


def _rule4_tracked_names(scope: ast.AST) -> frozenset[str]:
    """Names in *scope* holding a Mission file: assigned from a filename join, or an alias of one (A7)."""
    tracked: set[str] = set()
    assigns = [n for n in ast.walk(scope) if isinstance(n, ast.Assign | ast.AnnAssign)]
    changed = True
    while changed:
        changed = False
        for stmt in assigns:
            value = _assign_value(stmt)
            if value is None or not _rule4_value_is_source(value, tracked):
                continue
            for name in _assigned_names(stmt):
                if name not in tracked:
                    tracked.add(name)
                    changed = True
    return frozenset(tracked)


def _is_mission_file_expr(expr: ast.AST, tracked: frozenset[str] = frozenset()) -> bool:
    """True when sink target *expr* resolves to ``meta.json`` / ``tasks/WP*.md`` / ``tasks.md``."""
    inner = _unwrap_wrap(expr)
    if isinstance(inner, ast.Name) and inner.id in tracked:
        return True
    text = ast.unparse(inner)
    if any(hint in text for hint in _MISSION_FILE_VAR_HINTS):
        return True
    if any(tok in text for tok in _MISSION_FILE_NAME_TOKENS):
        return True
    if _mentions_mission_literal(inner):
        return True
    return bool(_WP_FILE_LITERAL.search(text))


def _rule4_arg_is_mission_file(node: ast.Call, tracked: frozenset[str]) -> bool:
    candidates: list[ast.expr] = [*node.args, *(kw.value for kw in node.keywords)]
    return any(_is_mission_file_expr(c, tracked) for c in candidates)


def _rule4_sink_kind(node: ast.Call, tracked: frozenset[str]) -> str | None:
    """The sink kind of *node* (a named sink or a raw write onto a Mission file), or ``None``."""
    name = _call_name(node.func)
    if name in _META_SINK_NAMES:
        return name
    if name in _WP_SINK_NAMES and _rule4_arg_is_mission_file(node, tracked):
        return name
    if isinstance(node.func, ast.Attribute) and node.func.attr in _RAW_WRITE_ATTRS and _is_mission_file_expr(node.func.value, tracked):
        return node.func.attr
    if name == _ATOMIC_WRITE_NAME and node.args and _is_mission_file_expr(node.args[0], tracked):
        return _ATOMIC_WRITE_NAME
    return None


def _rule4_sinks(scope: ast.AST, tracked: frozenset[str]) -> list[tuple[ast.Call, str]]:
    sinks: list[tuple[ast.Call, str]] = []
    for node in ast.walk(scope):
        if isinstance(node, ast.Call):
            kind = _rule4_sink_kind(node, tracked)
            if kind is not None:
                sinks.append((node, kind))
    return sinks


def _rule4_with_is_lock(node: ast.With | ast.AsyncWith, lock_names: frozenset[str]) -> bool:
    """A ``with`` opens a lock region: a lock-CM call, a name assigned from one, or an ``enter_context`` of one (A5)."""
    for item in node.items:
        expr = item.context_expr
        if isinstance(expr, ast.Call) and _call_name(expr.func) in _RULE4_LOCK_CMS:
            return True
        if isinstance(expr, ast.Name) and expr.id in lock_names:
            return True
    return _with_body_enters_lock(node)


def _with_body_enters_lock(node: ast.With | ast.AsyncWith) -> bool:
    for n in ast.walk(node):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == _ENTER_CONTEXT):
            continue
        if n.args and isinstance(n.args[0], ast.Call) and _call_name(n.args[0].func) in _RULE4_LOCK_CMS:
            return True
    return False


def _rule4_lock_var_names(func: ast.AST | None) -> frozenset[str]:
    """Names in *func* assigned from a lock-CM call, so ``with <name>`` is a lock region (A5)."""
    if func is None:
        return frozenset()
    names: set[str] = set()
    for stmt in ast.walk(func):
        value = _assign_value(stmt)
        if isinstance(value, ast.Call) and _call_name(value.func) in _RULE4_LOCK_CMS:
            names.update(_assigned_names(stmt))
    return frozenset(names)


def _rule4_lock_withs(node: ast.AST, parents: dict[ast.AST, ast.AST], func: ast.AST | None) -> bool:
    lock_names = _rule4_lock_var_names(func)
    child, cur = node, parents.get(node)
    while cur is not None and not isinstance(cur, (*_SCOPES, ast.ClassDef)):
        if isinstance(cur, ast.With | ast.AsyncWith) and child in cur.body and _rule4_with_is_lock(cur, lock_names):
            return True
        child, cur = cur, parents.get(cur)
    return False


def _is_dunder_on_lock(node: ast.AST, attr: str, lock_names: frozenset[str]) -> bool:
    """A manual ``<lock cm>(...).<attr>()`` or ``<lock var>.<attr>()`` call (A5)."""
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == attr):
        return False
    target = node.func.value
    if isinstance(target, ast.Call):
        return _call_name(target.func) in _RULE4_LOCK_CMS
    return isinstance(target, ast.Name) and target.id in lock_names


def _rule4_manual_lock_covers(node: ast.AST, func: ast.AST) -> bool:
    """A manual ``__enter__`` … ``__exit__`` span in *func* enclosing *node* by line (A5)."""
    lock_names = _rule4_lock_var_names(func)
    opens = [getattr(n, "lineno", 0) for n in ast.walk(func) if _is_dunder_on_lock(n, _ENTER, lock_names)]
    closes = [getattr(n, "lineno", 0) for n in ast.walk(func) if _is_dunder_on_lock(n, _EXIT, lock_names)]
    line = getattr(node, "lineno", 0)
    return any(opened < line and not any(opened < closed < line for closed in closes) for opened in opens)


def _rule4_in_region(node: ast.AST, func: ast.AST | None, parents: dict[ast.AST, ast.AST]) -> bool:
    """True when *node* sits lexically inside a lock region of its enclosing function (A5)."""
    if _rule4_lock_withs(node, parents, func):
        return True
    return func is not None and _rule4_manual_lock_covers(node, func)


def _rule4_call_sites_by_name(tree: ast.AST) -> dict[str, list[ast.Call]]:
    sites: dict[str, list[ast.Call]] = defaultdict(list)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _call_name(node.func)
            if name is not None:
                sites[name].append(node)
    return sites


def _rule4_call_covered(call: ast.Call, parents: dict[ast.AST, ast.AST], covered: set[ast.AST]) -> bool:
    fn = _nearest_function(call, parents)
    if fn is not None and fn in covered:
        return True
    return _rule4_in_region(call, fn, parents)


def _rule4_covered_functions(tree: ast.AST, parents: dict[ast.AST, ast.AST]) -> set[ast.AST]:
    """Functions whose EVERY same-module call site sits in a lock region (fixpoint; fail-closed if unresolvable)."""
    funcs = _functions(tree)
    sites = _rule4_call_sites_by_name(tree)
    covered: set[ast.AST] = set()
    changed = True
    while changed:
        changed = False
        for func in funcs:
            if func in covered:
                continue
            calls = sites.get(getattr(func, "name", ""), [])
            if calls and all(_rule4_call_covered(call, parents, covered) for call in calls):
                covered.add(func)
                changed = True
    return covered


def _rule4_accepted(node: ast.AST, func: ast.AST | None, kind: str, parents: dict[ast.AST, ast.AST], covered: set[ast.AST], self_locked: frozenset[str]) -> bool:
    if _rule4_in_region(node, func, parents):
        return True
    if kind in self_locked:
        return True
    return func is not None and func in covered


def collect_self_locked_named_sinks(trees: tuple[ast.AST, ...]) -> frozenset[str]:
    """Named sinks whose own definition wraps every Mission-file write in a lock region (a self-locking helper)."""
    found: set[str] = set()
    for tree in trees:
        parents = _parents(tree)
        for func in _functions(tree):
            name = getattr(func, "name", "")
            if name not in _NAMED_SINK_NAMES:
                continue
            tracked = _rule4_tracked_names(func)
            own = [(n, k) for (n, k) in _rule4_sinks(func, tracked) if _nearest_function(n, parents) is func]
            if own and all(_rule4_in_region(n, func, parents) for (n, _k) in own):
                found.add(name)
    return frozenset(found)


def _rule4_scope_findings(
    scope: ast.AST, parents: dict[ast.AST, ast.AST], tracked: frozenset[str], covered: set[ast.AST], self_locked: frozenset[str]
) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    for node, kind in _rule4_sinks(scope, tracked):
        if _nearest_function(node, parents) is not scope:
            continue
        if _rule4_accepted(node, scope, kind, parents, covered, self_locked):
            continue
        findings.append((getattr(node, "lineno", 0), f"{kind}: Mission-file write outside a Mission-lock region or a locked helper"))
    return findings


def _rule4_module_findings(
    tree: ast.AST, parents: dict[ast.AST, ast.AST], tracked: frozenset[str], covered: set[ast.AST], self_locked: frozenset[str]
) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    for node, kind in _rule4_sinks(tree, tracked):
        if _nearest_function(node, parents) is not None:
            continue
        if _rule4_accepted(node, None, kind, parents, covered, self_locked):
            continue
        findings.append((getattr(node, "lineno", 0), f"{kind}: Mission-file write outside a Mission-lock region or a locked helper"))
    return findings


def find_mission_file_sink_findings(tree: ast.AST, *, self_locked: frozenset[str]) -> list[tuple[int, str]]:
    """Rule 4 findings for one parsed module: ``meta.json`` / work-package / ``tasks.md`` writes outside the lock."""
    parents = _parents(tree)
    covered = _rule4_covered_functions(tree, parents)
    scopes = [*_functions(tree), tree]
    tracked_by_scope: dict[ast.AST, frozenset[str]] = {scope: _rule4_tracked_names(scope) for scope in scopes}
    findings: list[tuple[int, str]] = []
    for scope in _functions(tree):
        findings += _rule4_scope_findings(scope, parents, tracked_by_scope[scope], covered, self_locked)
    findings += _rule4_module_findings(tree, parents, tracked_by_scope[tree], covered, self_locked)
    return sorted(set(findings))


# --------------------------------------------------------------------------- tree walk


def _rel(path: Path) -> str:
    return path.relative_to(_REPO_ROOT).as_posix()


@functools.lru_cache(maxsize=1)
def _src_files() -> tuple[Path, ...]:
    return tuple(sorted(_SPECIFY_CLI.rglob("*.py")))


@functools.lru_cache(maxsize=1)
def _runtime_files() -> tuple[Path, ...]:
    return tuple(sorted(_RUNTIME.rglob("*.py")))


@functools.lru_cache(maxsize=1)
def _rule1_files() -> tuple[Path, ...]:
    return tuple(sorted({*_src_files(), *_runtime_files()}))


@functools.cache
def _parse(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


@functools.lru_cache(maxsize=1)
def _self_locked_named_sinks() -> frozenset[str]:
    """The self-locking named sinks of the real tree (a whole-tree pre-pass for rule 4)."""
    return collect_self_locked_named_sinks(tuple(_parse(path) for path in _src_files()))


@functools.lru_cache(maxsize=1)
def _scan_tree() -> dict[str, list[Finding]]:
    report: dict[str, list[Finding]] = {"truncate": [], "wholefile": [], "sink": [], "lockshape": [], "metafile": []}
    for path in _rule1_files():
        rel, tree = _rel(path), _parse(path)
        if rel in _RULE1_EXCLUDED_FILES:
            continue
        report["truncate"] += [(rel, line, why) for line, why in find_truncate_sites(tree)]
        report["wholefile"] += [(rel, line, why) for line, why in find_wholefile_rewrite_sites(tree)]
    self_locked = _self_locked_named_sinks()
    for path in _src_files():
        rel, tree = _rel(path), _parse(path)
        report["sink"] += [(rel, line, why) for line, why in find_sink_findings(tree, rel)]
        if rel not in _RULE3_EXCLUDED_FILES:
            report["lockshape"] += [(rel, line, why) for line, why in find_lock_shape_findings(tree)]
        if rel not in _RULE4_EXCLUDED_FILES:
            report["metafile"] += [(rel, line, why) for line, why in find_mission_file_sink_findings(tree, self_locked=self_locked)]
    return report


def _fmt(findings: list[Finding]) -> str:
    return "\n".join(f"  {rel}:{line}: {why}" for rel, line, why in findings)


# --------------------------------------------------------------------------- real-tree tests


def test_scan_floor_is_met() -> None:
    assert len(_src_files()) > _MIN_SCANNED_FILES, "scanner is scanning too few files; the gate would pass vacuously"
    assert _runtime_files(), "the src/runtime scan is empty; rule 1 would not cover the run log"


def test_allowlists_are_empty() -> None:
    assert {_PRIMITIVE} == _ALLOWED_TRUNCATE_FILES == _RULE1_EXCLUDED_FILES == _RULE3_EXCLUDED_FILES == _RULE4_EXCLUDED_FILES


def test_rule1_truncate_only_in_the_primitive() -> None:
    found = _scan_tree()["truncate"]
    assert not found, f"truncate/unlink of the status log outside {_PRIMITIVE}:\n{_fmt(found)}"


def test_rule1_wholefile_rewrites_are_locked_or_structural() -> None:
    found = _scan_tree()["wholefile"]
    assert not found, f"whole-file rewrite of a status/run log outside a lock or the primitive:\n{_fmt(found)}"


def test_rule1_floor_primitive_holds_its_sites() -> None:
    """Non-vacuity: the scanner still sees both kinds of site in the primitive (a rename of either would blind rule 1)."""
    reasons = Counter(why for _, why in find_truncate_sites(_parse(_REPO_ROOT / _PRIMITIVE)))
    assert reasons["attribute .ftruncate"] >= 1
    assert reasons["unlink of the event log"] >= 1


def test_rule1_floor_runtime_engine_is_scanned() -> None:
    """Non-vacuity: the engine's append / snapshot sinks are seen (and classified as structural non-sinks)."""
    engine = _RUNTIME / "next" / "_internal_runtime" / "engine.py"
    tree = _parse(engine)
    sink_kinds = {kind for _, _, kind, _ in _wholefile_sinks(tree)}
    assert any(kind.startswith("os.replace") for kind in sink_kinds), "engine _write_snapshot os.replace should be seen"
    assert find_wholefile_rewrite_sites(tree) == [], "the engine's append + tmp-replace publish are structural non-sinks"


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


def test_rule3_locks_use_canonical_key_and_path() -> None:
    found = _scan_tree()["lockshape"]
    assert not found, f"feature_status_lock keyed off mission_lock_key, or a mission_write_lock path that is a .name/subscript/slug:\n{_fmt(found)}"


def test_rule4_meta_and_frontmatter_writes_are_locked() -> None:
    found = _scan_tree()["metafile"]
    assert not found, f"meta.json / work-package / tasks.md write outside a Mission-lock region or a locked helper:\n{_fmt(found)}"


def test_rule4_floor_meta_writers_are_seen() -> None:
    """Non-vacuity: rule 4 still sees the canonical ``meta.json`` physical writers in ``mission_metadata.py``."""
    tree = _parse(_REPO_ROOT / _META_MODULE)
    tracked = _rule4_tracked_names(next(f for f in _functions(tree) if getattr(f, "name", "") == "write_meta"))
    kinds = {kind for _node, kind in _rule4_sinks(tree, tracked)}
    assert "write_meta" in kinds, "the write_meta call sites must be seen as sinks"
    assert _ATOMIC_WRITE_NAME in kinds, "write_meta's own atomic_write(meta.json) must be seen as a sink"


def test_rule4_floor_restore_meta_text_self_locks() -> None:
    """Non-vacuity: ``restore_meta_text`` is recognised as a self-locking helper, so its callers are accepted."""
    assert "restore_meta_text" in _self_locked_named_sinks()
    assert "write_meta" not in _self_locked_named_sinks(), "write_meta does not lock its own write; its callers must"


# --------------------------------------------------------------------------- non-vacuity: rule 1 truncate offenders

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
def test_rule1_flags_each_truncate_offender(source: str) -> None:
    assert find_truncate_sites(ast.parse(source))


# --------------------------------------------------------------------------- non-vacuity: rule 1 whole-file offenders

_WHOLEFILE_OFFENDERS = {
    "write_text events_path": "def f():\n    events_path.write_text('x')\n",
    "write_bytes events_path": "def f():\n    events_path.write_bytes(b'x')\n",
    "write_text joined literal": "def f():\n    (run_dir / 'state.json').write_text('x')\n",
    "write_bytes run log join": "def f():\n    p = run_dir / 'run.events.jsonl'\n    p.write_bytes(b'x')\n",
    "open w on events_path": "def f():\n    open(events_path, 'w').write('x')\n",
    "open r+ on events_path": "def f():\n    open(events_path, 'r+').write('x')\n",
    "open wb on tracked state": "def f():\n    p = run_dir / 'state.json'\n    open(p, 'wb')\n",
    "method open w": "def f():\n    events_path.open('w')\n",
    "shutil.move onto events_path": "def f():\n    import shutil\n    shutil.move(src, events_path)\n",
    "os.replace non-fresh onto state": "def f():\n    import os\n    target = run_dir / 'state.json'\n    os.replace(backup, target)\n",
    "atomic_write onto events_path": "def f():\n    atomic_write(events_path, b'x')\n",
    "EVENTS_FILENAME join write": "def f():\n    p = d / EVENTS_FILENAME\n    p.write_text('x')\n",
    "aliased tracked name": "def f():\n    p = run_dir / 'state.json'\n    q = p\n    q.write_bytes(b'x')\n",
}


@pytest.mark.parametrize("source", _WHOLEFILE_OFFENDERS.values(), ids=_WHOLEFILE_OFFENDERS.keys())
def test_rule1_flags_each_wholefile_offender(source: str) -> None:
    assert find_wholefile_rewrite_sites(ast.parse(source)), source


_WHOLEFILE_NEAR_MISSES = {
    "write_text config file": "def f():\n    config_path.write_text('x')\n",
    "unlink of an unrelated path": "def f():\n    tmp_path.unlink()\n",
    "append open a": "def f():\n    events_path.open('a')\n",
    "append builtin open a": "def f():\n    open(events_path, 'a').write('x')\n",
    "exclusive create x": "def f():\n    events_path.open('x')\n",
    "exclusive create builtin x": "def f():\n    open(events_path, 'x')\n",
    "read open rb": "def f():\n    events_path.open('rb')\n",
    "tmp then replace fresh": (
        "def f():\n    import os\n    tmp = run_dir / 'state.json.tmp'\n    target = run_dir / 'state.json'\n"
        "    with open(tmp, 'w') as h:\n        h.write('x')\n    os.replace(tmp, target)\n"
    ),
    "write under mission lock": "def f():\n    with mission_write_lock(d):\n        events_path.write_bytes(b'x')\n",
    "write under feature_status_lock": "def f():\n    with feature_status_lock(r, k):\n        events_path.write_text('x')\n",
    "move fresh tmp": (
        "def f():\n    import shutil\n    tmp = d / 'state.json.tmp'\n    target = d / 'state.json'\n"
        "    with open(tmp, 'w') as h:\n        h.write('x')\n    shutil.move(tmp, target)\n"
    ),
}


@pytest.mark.parametrize("source", _WHOLEFILE_NEAR_MISSES.values(), ids=_WHOLEFILE_NEAR_MISSES.keys())
def test_rule1_accepts_each_wholefile_near_miss(source: str) -> None:
    tree = ast.parse(source)
    assert find_wholefile_rewrite_sites(tree) == [], source
    assert not find_truncate_sites(tree), source


# --------------------------------------------------------------------------- non-vacuity: rule 2 (owned by WP15)

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
    # A11 escapes: any reference other than as the function of a call escapes the lock, even inside it.
    "escape: Thread target keyword": "import threading\ndef f():\n    with mission_write_lock(d):\n        threading.Thread(target=sink).start()\n",
    "escape: submit positional": "def f():\n    with mission_write_lock(d):\n        pool.submit(sink)\n",
    "escape: returned": "def f():\n    with mission_write_lock(d):\n        return sink\n",
    "escape: assigned then called later": "def f():\n    with mission_write_lock(d):\n        g = sink\n    g()\n",
}


@pytest.mark.parametrize("source", _LOCKED_OK.values(), ids=_LOCKED_OK.keys())
def test_rule2_accepts_each_locked_shape(source: str) -> None:
    assert find_sink_findings(ast.parse(source), "m.py", (_SYNTH_PAIR,)) == []


@pytest.mark.parametrize("source", _LOCKED_BAD.values(), ids=_LOCKED_BAD.keys())
def test_rule2_flags_each_synthetic_offender(source: str) -> None:
    assert find_sink_findings(ast.parse(source), "m.py", (_SYNTH_PAIR,))


def test_rule2_flags_sink_called_outside_its_registered_site() -> None:
    assert find_sink_findings(ast.parse("def f():\n    with mission_write_lock(d):\n        sink()\n"), "other.py", (_SYNTH_PAIR,))


# --------------------------------------------------------------------------- non-vacuity: rule 3 offenders

_KEY_OFFENDERS = {
    "slug name": "feature_status_lock(root, mission_slug)",
    "slug attribute": "feature_status_lock(root, st.mission_slug)",
    "qualified slug call": "_tasks.feature_status_lock(root, slug)",
    "slug keyword": "feature_status_lock(root, lock_key=feature_slug)",
    "bare directory .name": "feature_status_lock(root, feature_dir.name)",
    "attribute .name": "feature_status_lock(root, st.feature_dir.name)",
    "bare name module level": "feature_status_lock(root, mission_dir_name)",
    "subscript key": "feature_status_lock(root, meta['mission_slug'])",
    "name from non-factory": "def f():\n    key = compute_key(d)\n    feature_status_lock(root, key)\n",
    "laundered through a helper parameter (one-frame limit)": pytest.param(
        "def helper(root, slug_key):\n    feature_status_lock(root, slug_key)\n\ndef caller(root, st):\n    helper(root, st.mission_slug)\n",
        marks=pytest.mark.xfail(strict=True, reason="one-frame limit: a bare parameter key is trusted, callers are not followed (module docstring, rule 3)"),
    ),
}


@pytest.mark.parametrize("source", _KEY_OFFENDERS.values(), ids=_KEY_OFFENDERS.keys())
def test_rule3_flags_each_key_offender(source: str) -> None:
    assert find_lock_shape_findings(ast.parse(source)), source


_KEY_ACCEPTED = {
    "direct factory": "feature_status_lock(root, mission_lock_key(feature_dir))",
    "factory with kwargs": "feature_status_lock(root, mission_lock_key(feature_dir, repo_root=lock_root))",
    "name from factory": "def f():\n    key = mission_lock_key(feature_dir, repo_root=lock_root)\n    feature_status_lock(lock_root, key)\n",
    "key is a parameter": "def f(key):\n    feature_status_lock(lock_root, key)\n",
    "keyword from factory": "feature_status_lock(root, lock_key=mission_lock_key(d))",
}


@pytest.mark.parametrize("source", _KEY_ACCEPTED.values(), ids=_KEY_ACCEPTED.keys())
def test_rule3_accepts_each_canonical_key(source: str) -> None:
    assert find_lock_shape_findings(ast.parse(source)) == [], source


_PATH_OFFENDERS = {
    "write lock .name": "mission_write_lock(feature_dir.name)",
    "write lock subscript": "mission_write_lock(meta['slug'])",
    "write lock slug name": "mission_write_lock(mission_slug)",
    "hold lock .name": "hold_mission_write_lock(feature_dir.name)",
}


@pytest.mark.parametrize("source", _PATH_OFFENDERS.values(), ids=_PATH_OFFENDERS.keys())
def test_rule3_flags_each_path_offender(source: str) -> None:
    assert find_lock_shape_findings(ast.parse(source)), source


_PATH_ACCEPTED = {
    "directory parameter": "def f(feature_dir):\n    mission_write_lock(feature_dir)\n",
    "mission_write_lock_dir result": "mission_write_lock(mission_write_lock_dir(repo_root, handle))",
    "parent attribute": "mission_write_lock(point.events_path.parent)",
    "local directory": "mission_write_lock(matrix_dir, repo_root=repo_root)",
    "boolop directory": "mission_write_lock(lock_dir or mission_dir, repo_root=repo_root)",
    "hold lock stack arg": "hold_mission_write_lock(claim_stack, ctx)",
}


@pytest.mark.parametrize("source", _PATH_ACCEPTED.values(), ids=_PATH_ACCEPTED.keys())
def test_rule3_accepts_each_canonical_path(source: str) -> None:
    assert find_lock_shape_findings(ast.parse(source)) == [], source


# --------------------------------------------------------------------------- non-vacuity: rule 4 offenders


def _rule4(source: str, *, self_locked: frozenset[str] = frozenset()) -> list[tuple[int, str]]:
    return find_mission_file_sink_findings(ast.parse(source), self_locked=self_locked)


_META_OFFENDERS = {
    "write_meta outside lock": "def f():\n    write_meta(feature_dir, meta)\n",
    "restore_meta_text no self-lock registered": "def f():\n    restore_meta_text(d, text)\n",
    "atomic_write meta.json literal": "def f():\n    atomic_write(d / 'meta.json', content)\n",
    "write_text on meta_path hint": "def f():\n    meta_path.write_text(content)\n",
    "write_bytes on tracked meta name": "def f():\n    p = d / 'meta.json'\n    p.write_bytes(raw)\n",
    "META_FILENAME join write": "def f():\n    p = d / META_FILENAME\n    p.write_text(content)\n",
    "tasks.md literal write": "def f():\n    (d / 'tasks.md').write_text(content)\n",
    "wp file literal write": "def f():\n    (d / 'tasks' / 'WP01-x.md').write_text(content)\n",
    "write_frontmatter on wp_file": "def f():\n    write_frontmatter(wp_file, fm, body)\n",
    "update_fields on tasks_md": "def f():\n    update_fields(tasks_md, fields)\n",
    "sink in fn called from an unlocked site": ("def helper():\n    atomic_write(meta_path, content)\n\ndef caller():\n    helper()\n"),
    "cross-module callee unresolvable (no same-module call site)": ("def helper():\n    write_meta(feature_dir, meta)\n"),
}


@pytest.mark.parametrize("source", _META_OFFENDERS.values(), ids=_META_OFFENDERS.keys())
def test_rule4_flags_each_offender(source: str) -> None:
    assert _rule4(source), source


_META_NEAR_MISSES = {
    "lexical mission_write_lock": "def f():\n    with mission_write_lock(d):\n        write_meta(feature_dir, meta)\n",
    "lexical feature_status_lock": "def f():\n    with feature_status_lock(r, k):\n        atomic_write(meta_path, content)\n",
    "with name assigned from lock cm": "def f():\n    cm = mission_write_lock(d)\n    with cm:\n        write_meta(feature_dir, meta)\n",
    "ExitStack enter_context lock": (
        "import contextlib\ndef f():\n    with contextlib.ExitStack() as stack:\n"
        "        stack.enter_context(mission_write_lock(d))\n        write_meta(feature_dir, meta)\n"
    ),
    "manual __enter__/__exit__": (
        "def f():\n    lock = mission_write_lock(d)\n    lock.__enter__()\n    write_meta(feature_dir, meta)\n    lock.__exit__(None, None, None)\n"
    ),
    "locked_acceptance_verdict_guard region": "def f():\n    with locked_acceptance_verdict_guard(r, m):\n        atomic_write(meta_path, content)\n",
    "every same-module call site locked": (
        "def helper():\n    atomic_write(meta_path, content)\n\ndef caller():\n    with mission_write_lock(d):\n        helper()\n"
    ),
    "two-level same-module coverage": (
        "def leaf():\n    write_frontmatter(wp_file, fm, body)\n\ndef mid():\n    leaf()\n\ndef top():\n    with feature_status_lock(r, k):\n        mid()\n"
    ),
    "C-007 prompt_metadata temp file": "def f():\n    write_frontmatter(metadata.prompt_path, metadata.to_frontmatter(), body)\n",
    "write_frontmatter on a config path": "def f():\n    write_frontmatter(config_path, fm, body)\n",
    "write_text on a config file": "def f():\n    config_path.write_text(content)\n",
    "merge driver writes the argv path": "def run(ours):\n    ours.write_text(content)\n",
    "self-locking named sink (registered by the pre-pass)": "def revert():\n    restore_meta_text(d, text, expected_current=prev)\n",
}


@pytest.mark.parametrize("source", _META_NEAR_MISSES.values(), ids=_META_NEAR_MISSES.keys())
def test_rule4_accepts_each_near_miss(source: str) -> None:
    # ``restore_meta_text`` self-locks (whole-tree pre-pass, plan A8/D5); unregistered it is an offender, see _META_OFFENDERS.
    assert _rule4(source, self_locked=frozenset({"restore_meta_text"})) == [], source


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


class _ExclusiveCreateToClobber(_Mutation):
    """``open(target, "x")`` -> ``open(target, "w")``: the exclusive create turns into a clobber."""

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        opened = _open_target_and_mode(node)
        if opened is not None and "x" in opened[1]:
            self.changed += 1
            return ast.copy_location(
                ast.Call(func=node.func, args=[node.args[0], ast.Constant("w")], keywords=list(node.keywords)),
                node,
            )
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


def test_self_mutation_bookkeeping_projection_without_the_lock_is_flagged() -> None:
    """The status-log projection passes only because its rewrite sits under the Mission lock."""
    mutated = _mutate(_BOOKKEEPING, _StripLockWith())
    assert find_wholefile_rewrite_sites(mutated), "stripping the lock must expose the projection's status-log rewrite"


def test_self_mutation_auto_rebase_clobber_create_is_flagged() -> None:
    """The lane hydrate passes only because it uses an exclusive create, not a clobbering open."""
    mutated = _mutate(_AUTO_REBASE, _ExclusiveCreateToClobber())
    assert find_wholefile_rewrite_sites(mutated), "turning the exclusive create into a clobber must expose the hydrate rewrite"


def test_self_mutation_meta_writer_without_the_lock_is_flagged() -> None:
    """``mission_metadata.py`` passes rule 4 only because its ``meta.json`` writes sit under the Mission lock."""
    mutated = _mutate(_META_MODULE, _StripLockWith())
    self_locked = collect_self_locked_named_sinks((mutated,))
    assert find_mission_file_sink_findings(mutated, self_locked=self_locked), "stripping the lock must expose the meta.json writers"
