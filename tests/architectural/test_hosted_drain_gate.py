"""Architectural gate: every hosted relay/gateway network edge sits behind the drain gate.

Mission ``hosted-opt-in-drain-ledger-01M3FFEV`` (#4971). Contract:
``kitty-specs/hosted-opt-in-drain-ledger-01M3FFEV/contracts/hosted-posture.md``;
gate placement: ``plan.md`` post-plan squad folds **F-1** (relay edges) and
**F-2** (capability-gateway edges), plus post-tasks fold **G2** (the widen
prereq probe).

NFR-002, verbatim: *"An architectural test proves every hosted network edge
sits behind the drain gate (concrete floor = relay opener used by the control
POST, stream GET ×2 and history GET, plus the capability-gateway HTTP client; a
self-mutation check shows removing a gate call turns the test red; allowlist
shrink-only)."*

Known limits: an opener reached by string (``getattr``/``importlib``) is
invisible to AST scanning, as in the sibling gate. Likewise, a module-level
assignment (``OPENER = budget.NoRedirects.build``, outside any function), a
lambda bound to an opener call, or a class-attribute opener reference
(``class C: opener = budget.NoRedirects.build``) sits outside
:func:`_top_level_functions`'s function/class-method walk, so
:func:`discover_edges`'s "holds_opener" check never sees it -- only a
function body use is discovered. None of the four registered relay/gateway
edges are shaped this way today (all four are plain function-body opener
calls), so this is a documented gap, not a live miss; a future opener
reference of this shape needs either a scanner widening or a new registered
edge added by hand. The *caller-side*
pre-flights (the adapters fan-out, ``resolve_credentials`` /
``resolve_focus_capability`` pre-cache, the runtime producer, retrospective,
live-work publisher and hook, the zeitgeist CLI and MCP tools, the interview
widen callers) are gated **behaviourally** by their own suites and by
``tests/integration/test_hosted_posture_matrix.py``, not structurally here.

What this gate checks (a *gate-call* scan, not a sink scan)
-----------------------------------------------------------
For every function in :data:`_GATED_EDGES` it AST-parses the live source and
requires that the function body

1. consults the drain posture through the real authority
   (:mod:`specify_cli.core.hosted_posture` -- ``require_drain(...)`` or
   ``drain_posture()``), resolved through the module's own imports, so a local
   look-alike named ``require_drain`` does not count (authority-parse
   vacuity, tactic ``architectural-gate-non-vacuity`` step 5);
2. does so in an *unconditional* position -- a bare statement of the function
   body, or of a ``try`` body directly under it **provided every handler that
   can catch the refusal** (``DrainDisabled``, ``RuntimeError``,
   ``Exception``, ``BaseException``, a bare ``except``, or a tuple holding one)
   ends in ``return``/``raise`` and no ``finally`` returns -- a handler that
   falls through to the opener un-gates it; or a top-level
   ``if not drain_posture().enabled:`` -- exactly that test, nothing
   short-circuiting it -- whose body ends in ``return``/``raise``. A call
   buried in a branch that may never run is not a gate;
3. does so on a source line *before* the first hosted network opener in that
   same function (nested helpers such as ``offer``'s ``_post`` included). An
   opener is any *reference* to a relay opener symbol (``NoRedirects``,
   ``open_bounded``) or a raw stdlib opener (``urlopen``, ``build_opener``,
   ``http.client.HTTP(S)Connection``), resolved through import aliases
   (``from ...budget import NoRedirects as NR``, function-local imports) and
   plain assignment aliases, plus the gateway client's ``self._http.<verb>``
   sends and any use of a ``SaasClient``-typed parameter.

A **discovery sweep** then walks all of ``src/specify_cli/`` for relay opener
references (aliases resolved) and, inside ``zeitgeist_client`` only, raw
stdlib openers and the capability gateway's HTTP client sends
(``self._http.<verb>``): any function
holding one that is neither a registered edge, the opener's own definition,
nor in the shrink-only :data:`_UNGATED_EDGE_ALLOWLIST` is a red build. That is
what makes a *new* ungated edge visible rather than silently unregistered.

Relationship to ``test_egress_consent_boundary.py`` (#3030)
-----------------------------------------------------------
That sibling gate is a **sink** scan, allowlisted per *file* with a named
consent seam; its vocabulary (HTTP verbs, ``urlopen``, websocket sends, any
``headers=`` + body call) is broader but does not see the relay opener's
``opener.open(req)`` shape at all. This gate's vocabulary is deliberately
narrower (only the relay/gateway openers) and asks a different question: does
the named function call the drain check before it opens. Drain is a narrower
precondition layered in front of the same consent answer -- neither gate
subsumes the other.

Non-vacuity (tactic ``architectural-gate-non-vacuity``)
-------------------------------------------------------
* Concrete floor: :data:`_NFR002_NAMED_EDGES` maps NFR-002's five named edges
  to registry members; each must be *verified gated in live source* (not
  merely listed), and the count of verified edges must reach
  :data:`_NFR002_FLOOR` (5).
* Self-mutation: :class:`TestSelfMutation` copies each real gated file into
  ``tmp_path``, strips every gate statement with an AST transform and asserts
  the scanner now reports the edge ungated (observed red-first when authored).
* Negative controls: a synthetic gated module classifies as gated; a module
  whose ``require_drain`` is a local look-alike, whose gate sits after the
  opener, or inside a conditional branch, classifies as ungated.
* Shrink-only allowlist: :data:`_UNGATED_EDGE_ALLOWLIST` is registered in
  ``tests/architectural/_baselines.yaml``
  (``test_hosted_drain_gate.ungated_edge_allowlist``) and is empty.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = [pytest.mark.architectural]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"
_SWEEP_ROOT = _SRC / "specify_cli"

_AUTHORITY_MODULE = "specify_cli.core.hosted_posture"
_AUTHORITY_PARENT = "specify_cli.core"
_AUTHORITY_ATTR = "hosted_posture"
_GATE_RAISING = "require_drain"
_GATE_READING = "drain_posture"
_GATE_NAMES = frozenset({_GATE_RAISING, _GATE_READING})

#: Relay opener symbols (``zeitgeist_client.budget``). ANY reference counts --
#: a call, an attribute (``b.NoRedirects.build()``), an import alias
#: (``from ...budget import NoRedirects as NR``), an assignment alias
#: (``OPENER = NoRedirects``) or a callback (``run(budget.open_bounded, req)``).
_RELAY_OPENER_SYMBOLS = frozenset({"NoRedirects", "open_bounded"})
#: Raw stdlib openers. Counted only inside the relay client package (and in a
#: registered edge): elsewhere in ``src/`` they are the #3030 egress gate's
#: business (loopback dashboard probes etc.), not this gate's.
_STDLIB_OPENER_SYMBOLS = frozenset({"urlopen", "build_opener", "HTTPConnection", "HTTPSConnection"})
#: Exception types a ``DrainDisabled`` (a ``RuntimeError``) is caught by.
_DRAIN_CATCHING_TYPES = frozenset({"DrainDisabled", "RuntimeError", "Exception", "BaseException"})
#: Builtin/stdlib exception names the scanner can positively clear as NOT
#: catching a ``DrainDisabled`` -- none of these sit on its ancestor chain
#: (``BaseException`` -> ``Exception`` -> ``RuntimeError`` -> ``DrainDisabled``).
#: Deliberately excludes ``NotImplementedError``/``RecursionError`` (real
#: ``RuntimeError`` subclasses) -- an unrecognized name is NOT assumed safe
#: just because it looks like a builtin; only a name on this explicit list is.
_KNOWN_UNRELATED_EXCEPTION_NAMES = frozenset(
    {
        "ValueError", "TypeError", "KeyError", "IndexError", "AttributeError", "LookupError",
        "StopIteration", "StopAsyncIteration", "OSError", "IOError", "FileNotFoundError",
        "FileExistsError", "PermissionError", "ImportError", "ModuleNotFoundError", "NameError",
        "UnboundLocalError", "ZeroDivisionError", "ArithmeticError", "OverflowError",
        "FloatingPointError", "AssertionError", "SyntaxError", "IndentationError", "TabError",
        "UnicodeError", "UnicodeDecodeError", "UnicodeEncodeError", "UnicodeTranslateError",
        "EOFError", "MemoryError", "SystemExit", "KeyboardInterrupt", "GeneratorExit",
        "ConnectionError", "ConnectionResetError", "ConnectionAbortedError", "ConnectionRefusedError",
        "BrokenPipeError", "TimeoutError", "BlockingIOError", "ChildProcessError", "InterruptedError",
        "IsADirectoryError", "NotADirectoryError", "ProcessLookupError", "ReferenceError",
        "SystemError", "BufferError", "EnvironmentError", "WindowsError",
    }
)  # fmt: skip
_ALL_OPENER_SYMBOLS = _RELAY_OPENER_SYMBOLS | _STDLIB_OPENER_SYMBOLS
#: The capability gateway's injected ``httpx.Client`` (``self._http``) send verbs.
_HTTP_CLIENT_ATTR = "_http"
_GATEWAY_PACKAGE = "specify_cli.zeitgeist_client."
_HTTP_SEND_VERBS = frozenset({"get", "post", "put", "patch", "delete", "request", "send", "stream"})
#: A parameter annotated with this class makes every call through it an opener
#: (the widen prereq probe: its hosted calls all go through the injected client).
_SAAS_CLIENT_CLASS = "SaasClient"


@dataclass(frozen=True)
class GatedEdge:
    """One registered hosted network edge: the function that must gate."""

    module: str  # dotted module, e.g. "specify_cli.zeitgeist_client.transport"
    qualname: str  # e.g. "ZeitgeistClient.offer"
    opener: str  # the network call it guards, for the failure message

    @property
    def key(self) -> str:
        return f"{self.module}.{self.qualname}"

    @property
    def path(self) -> Path:
        return _SRC / Path(*self.module.split(".")).with_suffix(".py")


# Confirmed against the live source (2026-09-27): these are the real names,
# not the contract's descriptive ones.
_GATED_EDGE_LIST: tuple[GatedEdge, ...] = (
    GatedEdge("specify_cli.zeitgeist_client.transport", "ZeitgeistClient.offer", "budget.open_bounded (control POST)"),
    GatedEdge("specify_cli.zeitgeist_client.filtered_stream", "FilteredStream.seed_from_snapshot", "NoRedirects.build (snapshot GET)"),
    GatedEdge("specify_cli.zeitgeist_client.filtered_stream", "FilteredStream.watch", "NoRedirects.build (stream GET)"),
    GatedEdge("specify_cli.zeitgeist_client.history", "read_history", "NoRedirects.build (history GET)"),
    GatedEdge("specify_cli.zeitgeist_client.resolution", "SaasCapabilityGateway.check_repo_admission", "self._http.get (admission)"),
    GatedEdge("specify_cli.zeitgeist_client.resolution", "SaasCapabilityGateway.mint_capability", "self._http.post (mint)"),
    GatedEdge("specify_cli.widen.prereq", "check_prereqs", "SaasClient probe (G2)"),
)
_GATED_EDGES: dict[str, GatedEdge] = {edge.key: edge for edge in _GATED_EDGE_LIST}

# NFR-002's concrete floor, named edge by named edge. The integer is the count
# of edges the acceptance text enumerates -- "the control POST" (1), "stream
# GET ×2" (2, 3), "history GET" (4), "the capability-gateway HTTP client" (5) --
# NOT len(_GATED_EDGES): the registry also carries the widen prereq probe (G2)
# and splits the gateway client into its two sending methods.
_NFR002_FLOOR = 5
_NFR002_NAMED_EDGES: dict[str, frozenset[str]] = {
    "control POST": frozenset({"specify_cli.zeitgeist_client.transport.ZeitgeistClient.offer"}),
    "stream GET (snapshot)": frozenset({"specify_cli.zeitgeist_client.filtered_stream.FilteredStream.seed_from_snapshot"}),
    "stream GET (watch)": frozenset({"specify_cli.zeitgeist_client.filtered_stream.FilteredStream.watch"}),
    "history GET": frozenset({"specify_cli.zeitgeist_client.history.read_history"}),
    "capability-gateway HTTP client": frozenset(
        {
            "specify_cli.zeitgeist_client.resolution.SaasCapabilityGateway.check_repo_admission",
            "specify_cli.zeitgeist_client.resolution.SaasCapabilityGateway.mint_capability",
        }
    ),
}

#: The opener's own definitions: their bodies *are* the sink the edges call, so
#: they are not edges. Pinned by equality below -- widening costs a visible diff.
_OPENER_DEFINITIONS: frozenset[str] = frozenset(
    {
        "specify_cli.zeitgeist_client.budget.open_bounded",  # NoRedirects.build().open(...)
        "specify_cli.zeitgeist_client.budget.NoRedirects.build",  # urllib.request.build_opener(...)
    }
)

#: Shrink-only: hosted edges intentionally exempt from the drain gate. Empty at
#: authoring time -- an ungated edge is a finding to fix, never to list here.
#: Size registered in _baselines.yaml (test_hosted_drain_gate.ungated_edge_allowlist).
_UNGATED_EDGE_ALLOWLIST: frozenset[str] = frozenset()


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EdgeVerdict:
    """What the scanner concluded about one function."""

    found: bool
    gate_line: int | None
    opener_line: int | None

    @property
    def gated(self) -> bool:
        return self.found and self.gate_line is not None and self.opener_line is not None and self.gate_line < self.opener_line

    def describe(self) -> str:
        if not self.found:
            return "function not found in source (stale registry entry?)"
        if self.opener_line is None:
            return "no hosted network opener found (registry entry no longer an edge?)"
        if self.gate_line is None:
            return f"UNGATED: opener at line {self.opener_line} with no unconditional drain gate before it"
        if self.gate_line >= self.opener_line:
            return f"UNGATED: drain gate at line {self.gate_line} comes after the opener at line {self.opener_line}"
        return f"gated: drain gate line {self.gate_line} < opener line {self.opener_line}"


@dataclass(frozen=True)
class _AuthorityBindings:
    """How this module can reach the real drain authority."""

    direct: dict[str, str]  # local name -> "require_drain" | "drain_posture"
    module_aliases: frozenset[str]  # local names bound to hosted_posture itself


def _authority_bindings(tree: ast.Module) -> _AuthorityBindings:
    direct: dict[str, str] = {}
    aliases: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.level == 0:
            for alias in node.names:
                local = alias.asname or alias.name
                if node.module == _AUTHORITY_MODULE and alias.name in _GATE_NAMES:
                    direct[local] = alias.name
                elif node.module == _AUTHORITY_PARENT and alias.name == _AUTHORITY_ATTR:
                    aliases.add(local)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == _AUTHORITY_MODULE and alias.asname:
                    aliases.add(alias.asname)
    # A later top-level def/assignment of the same name shadows the import.
    for node in tree.body:
        shadowed: list[str] = []
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            shadowed = [node.name]
        elif isinstance(node, ast.Assign):
            shadowed = [t.id for t in node.targets if isinstance(t, ast.Name)]
        for name in shadowed:
            direct.pop(name, None)
            aliases.discard(name)
    return _AuthorityBindings(direct=direct, module_aliases=frozenset(aliases))


def _gate_kind(call: ast.Call, bindings: _AuthorityBindings) -> str | None:
    """``require_drain``/``drain_posture`` when ``call`` reaches the real authority."""
    func = call.func
    if isinstance(func, ast.Name):
        return bindings.direct.get(func.id)
    if isinstance(func, ast.Attribute) and func.attr in _GATE_NAMES and isinstance(func.value, ast.Name) and func.value.id in bindings.module_aliases:
        return func.attr
    return None


def _dotted_tail(func: ast.expr) -> tuple[str, ...]:
    parts: list[str] = []
    node: ast.expr = func
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return tuple(reversed(parts))


def _opener_symbol(expr: ast.expr, aliases: dict[str, str], symbols: frozenset[str]) -> str | None:
    """The opener symbol ``expr`` refers to, through any import/assignment alias."""
    if isinstance(expr, ast.Name):
        return aliases.get(expr.id) or (expr.id if expr.id in symbols else None)
    if isinstance(expr, ast.Attribute) and expr.attr in symbols:
        return expr.attr
    return None


def _opener_aliases(tree: ast.Module, symbols: frozenset[str]) -> dict[str, str]:
    """Local names bound to an opener symbol anywhere in the module: ``from X
    import <symbol> as <name>`` (module level or function-local) and plain
    ``<name> = <opener reference>`` assignments, followed to a fixpoint."""
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in symbols:
                    aliases[alias.asname or alias.name] = alias.name
    assigns = [node for node in ast.walk(tree) if isinstance(node, ast.Assign)]
    changed = True
    while changed:
        changed = False
        for node in assigns:
            symbol = _opener_symbol(node.value, aliases, symbols)
            if symbol is None:
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id not in aliases:
                    aliases[target.id] = symbol
                    changed = True
    return aliases


def _opener_reference_lines(fn: ast.AST, aliases: dict[str, str], symbols: frozenset[str]) -> list[int]:
    return [
        node.lineno
        for node in ast.walk(fn)
        if isinstance(node, (ast.Name, ast.Attribute)) and isinstance(node.ctx, ast.Load) and _opener_symbol(node, aliases, symbols) is not None
    ]


def _is_http_client_send(call: ast.Call) -> bool:
    tail = _dotted_tail(call.func)
    return len(tail) == 3 and tail[0] == "self" and tail[1] == _HTTP_CLIENT_ATTR and tail[2] in _HTTP_SEND_VERBS


def _saas_client_params(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> frozenset[str]:
    names: set[str] = set()
    for arg in [*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs]:
        if arg.annotation is not None and _dotted_tail(arg.annotation)[-1:] == (_SAAS_CLIENT_CLASS,):
            names.add(arg.arg)
    return frozenset(names)


def _uses_saas_client(call: ast.Call, params: frozenset[str]) -> bool:
    if not params:
        return False
    head = _dotted_tail(call.func)[:1]
    if head and head[0] in params and isinstance(call.func, ast.Attribute):
        return True
    operands = [*call.args, *(kw.value for kw in call.keywords)]
    return any(isinstance(arg, ast.Name) and arg.id in params for arg in operands)


def _first_opener_line(fn: ast.FunctionDef | ast.AsyncFunctionDef, aliases: dict[str, str]) -> int | None:
    params = _saas_client_params(fn)
    lines = _opener_reference_lines(fn, aliases, _ALL_OPENER_SYMBOLS)
    lines += [node.lineno for node in ast.walk(fn) if isinstance(node, ast.Call) and (_is_http_client_send(node) or _uses_saas_client(node, params))]
    return min(lines) if lines else None


def _calls_in(node: ast.AST) -> list[ast.Call]:
    return [sub for sub in ast.walk(node) if isinstance(sub, ast.Call)]


def _terminates(body: list[ast.stmt]) -> bool:
    return bool(body) and isinstance(body[-1], (ast.Return, ast.Raise))


def _is_drain_off_test(test: ast.expr, bindings: _AuthorityBindings) -> bool:
    """Exactly ``not <authority>.drain_posture(...).enabled`` -- no other operand.

    A looser match (any gate call somewhere in the test) is defeatable by
    short-circuiting it away, e.g. ``if False and not drain_posture().enabled``.
    """
    if not (isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not)):
        return False
    operand = test.operand
    return (
        isinstance(operand, ast.Attribute)
        and operand.attr == "enabled"
        and isinstance(operand.value, ast.Call)
        and _gate_kind(operand.value, bindings) == _GATE_READING
    )


def _exception_aliases(tree: ast.Module) -> dict[str, str]:
    """Local names bound to one of :data:`_DRAIN_CATCHING_TYPES`, resolved
    through an import alias (``from ...hosted_posture import DrainDisabled as
    DD``) or a plain assignment alias (``Err = Exception``, followed to a
    fixpoint exactly like :func:`_opener_aliases`). This is what lets
    :func:`_catches_drain_disabled` recognize ``except DD:`` / ``except Err:``
    as catching without hand-waving every unrecognized name as safe."""
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == _AUTHORITY_MODULE:
            for alias in node.names:
                if alias.name == "DrainDisabled":
                    aliases[alias.asname or alias.name] = "DrainDisabled"
    assigns = [node for node in ast.walk(tree) if isinstance(node, ast.Assign)]
    changed = True
    while changed:
        changed = False
        for node in assigns:
            tail = _dotted_tail(node.value) if isinstance(node.value, (ast.Name, ast.Attribute)) else ()
            if not tail:
                continue
            source = aliases.get(tail[-1]) or (tail[-1] if tail[-1] in _DRAIN_CATCHING_TYPES else None)
            if source is None:
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id not in aliases:
                    aliases[target.id] = source
                    changed = True
    return aliases


def _catches_drain_disabled(handler: ast.ExceptHandler, exception_aliases: dict[str, str]) -> bool:
    """Whether ``handler`` can catch a ``DrainDisabled`` (a ``RuntimeError``).

    Fails closed (assumes it CAN catch) on any type this scanner cannot
    positively clear: an unresolvable expression (e.g. a call/subscript,
    where ``_dotted_tail`` returns nothing), or a name/attribute that is
    neither one of :data:`_DRAIN_CATCHING_TYPES`, an alias of one of them
    (:func:`_exception_aliases`), nor a builtin explicitly cleared by
    :data:`_KNOWN_UNRELATED_EXCEPTION_NAMES`. Only a name the scanner can
    positively prove is unrelated is treated as not catching -- an unknown
    custom exception class is assumed to catch, since the scanner cannot see
    its base classes.
    """
    if handler.type is None:
        return True
    types = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    for t in types:
        tail = _dotted_tail(t)
        if not tail:
            return True  # unresolvable handler-type expression -- fail closed
        name = tail[-1]
        if name in _DRAIN_CATCHING_TYPES or exception_aliases.get(name) in _DRAIN_CATCHING_TYPES:
            return True
        if name not in _KNOWN_UNRELATED_EXCEPTION_NAMES:
            return True  # unrecognized type -- fail closed, cannot clear it
    return False


def _try_keeps_the_refusal(stmt: ast.Try, exception_aliases: dict[str, str]) -> bool:
    """A ``require_drain`` in ``stmt.body`` still stops the function only if
    every handler that can catch the refusal ends in ``return``/``raise``
    (never falls through to the opener) and no ``finally`` returns (which
    would swallow it)."""
    if any(isinstance(node, ast.Return) for fin in stmt.finalbody for node in ast.walk(fin)):
        return False
    return all(_terminates(handler.body) for handler in stmt.handlers if _catches_drain_disabled(handler, exception_aliases))


def _unconditional_gate_lines(stmts: list[ast.stmt], bindings: _AuthorityBindings, exception_aliases: dict[str, str]) -> list[int]:
    """Lines of gate calls that run unconditionally on entry to ``stmts``."""
    lines: list[int] = []
    for stmt in stmts:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call) and _gate_kind(stmt.value, bindings) == _GATE_RAISING:
            lines.append(stmt.lineno)
        elif isinstance(stmt, ast.Try) and _try_keeps_the_refusal(stmt, exception_aliases):
            lines.extend(_unconditional_gate_lines(stmt.body, bindings, exception_aliases))
        elif isinstance(stmt, ast.If) and _terminates(stmt.body) and _is_drain_off_test(stmt.test, bindings):
            lines.append(stmt.lineno)
    return lines


def _find_function(tree: ast.Module, qualname: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    scope: list[ast.stmt] = tree.body
    parts = qualname.split(".")
    for index, part in enumerate(parts):
        match = next(
            (n for n in scope if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == part),
            None,
        )
        if match is None:
            return None
        if index == len(parts) - 1:
            return match if isinstance(match, (ast.FunctionDef, ast.AsyncFunctionDef)) else None
        scope = match.body
    return None


def scan_edge(source: str, qualname: str) -> EdgeVerdict:
    """Classify ``qualname`` in ``source``: is its first opener preceded by a real drain gate?"""
    tree = ast.parse(source)
    fn = _find_function(tree, qualname)
    if fn is None:
        return EdgeVerdict(found=False, gate_line=None, opener_line=None)
    bindings = _authority_bindings(tree)
    exception_aliases = _exception_aliases(tree)
    gate_lines = _unconditional_gate_lines(fn.body, bindings, exception_aliases)
    opener_line = _first_opener_line(fn, _opener_aliases(tree, _ALL_OPENER_SYMBOLS))
    return EdgeVerdict(found=True, gate_line=min(gate_lines) if gate_lines else None, opener_line=opener_line)


def _top_level_functions(tree: ast.Module) -> list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    """(qualname, node) for module functions and class methods (nested defs fold into their parent)."""
    found: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]] = []

    def visit(scope: list[ast.stmt], prefix: str) -> None:
        for node in scope:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found.append((f"{prefix}{node.name}", node))
            elif isinstance(node, ast.ClassDef):
                visit(node.body, f"{prefix}{node.name}.")

    visit(tree.body, "")
    return found


def discover_edges(root: Path, *, src_root: Path = _SRC) -> set[str]:
    """Every function under ``root`` holding a relay opener or a gateway client send.

    ``src_root`` is the import root the dotted module names are computed from."""
    edges: set[str] = set()
    for path in sorted(root.rglob("*.py")):
        module = ".".join(path.relative_to(src_root).with_suffix("").parts)
        # `self._http` and the raw stdlib openers are in scope only inside the
        # relay client package; elsewhere (e.g. saas_client.SaasClient's own
        # `self._http`, the loopback dashboard's urlopen) they belong to other
        # clients whose gating is out of this gate's relay/gateway scope.
        in_relay_package = f"{module}.".startswith(_GATEWAY_PACKAGE)
        symbols = _ALL_OPENER_SYMBOLS if in_relay_package else _RELAY_OPENER_SYMBOLS
        source = path.read_text(encoding="utf-8")
        if not any(token in source for token in (*symbols, "self._http.")):
            continue
        tree = ast.parse(source)
        aliases = _opener_aliases(tree, symbols)
        for qualname, fn in _top_level_functions(tree):
            holds_opener = bool(_opener_reference_lines(fn, aliases, symbols))
            if holds_opener or (in_relay_package and any(isinstance(n, ast.Call) and _is_http_client_send(n) for n in ast.walk(fn))):
                edges.add(f"{module}.{qualname}")
    return edges


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


class TestDrainGate:
    @pytest.mark.parametrize("edge", _GATED_EDGE_LIST, ids=lambda e: e.key)
    def test_registered_edge_is_gated_before_its_opener(self, edge: GatedEdge) -> None:
        verdict = scan_edge(edge.path.read_text(encoding="utf-8"), edge.qualname)
        assert verdict.gated, (
            f"{edge.key} ({edge.opener}): {verdict.describe()}. Every hosted network edge must call "
            f"hosted_posture.require_drain(...) (or branch on hosted_posture.drain_posture().enabled and "
            f"return) before it opens -- contracts/hosted-posture.md, plan.md F-1/F-2. Do NOT add the edge "
            f"to _UNGATED_EDGE_ALLOWLIST to silence this."
        )

    def test_concrete_floor_is_met_by_verified_edges(self) -> None:
        assert len(_NFR002_NAMED_EDGES) == _NFR002_FLOOR, "NFR-002 names exactly five edges; the map must name each"
        verified: list[str] = []
        for name, keys in _NFR002_NAMED_EDGES.items():
            assert keys, f"NFR-002 edge {name!r} maps to no registry member"
            assert keys <= set(_GATED_EDGES), f"NFR-002 edge {name!r} maps outside the registry: {sorted(keys - set(_GATED_EDGES))}"
            if all(scan_edge(_GATED_EDGES[k].path.read_text(encoding="utf-8"), _GATED_EDGES[k].qualname).gated for k in keys):
                verified.append(name)
        assert len(verified) >= _NFR002_FLOOR, (
            f"NFR-002 floor: expected >= {_NFR002_FLOOR} named edges verified gated in live source; got {len(verified)}: {verified}"
        )

    def test_widen_prereq_probe_is_registered(self) -> None:
        """G2: the automatic hosted probe at interview startup is an edge too."""
        assert "specify_cli.widen.prereq.check_prereqs" in _GATED_EDGES

    def test_no_unregistered_hosted_edge_exists(self) -> None:
        discovered = discover_edges(_SWEEP_ROOT)
        # Routed-count floor: the sweep itself must still see the relay/gateway
        # edges, or it has gone blind (e.g. the opener was renamed).
        registered_relay_or_gateway = {k for k in _GATED_EDGES if k != "specify_cli.widen.prereq.check_prereqs"}
        assert registered_relay_or_gateway <= discovered, (
            f"discovery sweep no longer sees registered edges {sorted(registered_relay_or_gateway - discovered)} -- "
            "the opener vocabulary drifted; update _RELAY_OPENER_SYMBOLS/_HTTP_SEND_VERBS rather than the registry"
        )
        assert discovered >= _OPENER_DEFINITIONS, f"stale opener definitions: {sorted(_OPENER_DEFINITIONS - discovered)}"
        unregistered = discovered - set(_GATED_EDGES) - _OPENER_DEFINITIONS - _UNGATED_EDGE_ALLOWLIST
        assert not unregistered, (
            f"hosted network edge(s) not registered with the drain gate: {sorted(unregistered)}. Gate each with "
            "hosted_posture.require_drain(...) before its opener and add it to _GATED_EDGE_LIST."
        )


class TestAllowlistDiscipline:
    def test_opener_definitions_are_pinned(self) -> None:
        assert frozenset({"specify_cli.zeitgeist_client.budget.open_bounded", "specify_cli.zeitgeist_client.budget.NoRedirects.build"}) == _OPENER_DEFINITIONS

    def test_allowlist_is_empty_and_carries_no_registered_edge(self) -> None:
        assert not (_UNGATED_EDGE_ALLOWLIST & set(_GATED_EDGES)), "a registered edge cannot also be exempt"
        assert frozenset() == _UNGATED_EDGE_ALLOWLIST, (
            "_UNGATED_EDGE_ALLOWLIST grew. An ungated hosted edge is a drain-contract defect; gate it instead. "
            "If an exemption is genuinely required, it needs a _baselines.yaml bump with a # justification: line."
        )

    def test_no_stale_allowlist_entry(self) -> None:
        stale = _UNGATED_EDGE_ALLOWLIST - discover_edges(_SWEEP_ROOT)
        assert not stale, f"allowlisted edges no longer exist: {sorted(stale)}"


# ---------------------------------------------------------------------------
# Self-mutation (red-first) and negative controls
# ---------------------------------------------------------------------------


class _StripDrainGates(ast.NodeTransformer):
    """Replace every statement that consults the drain authority with ``pass``."""

    def __init__(self, bindings: _AuthorityBindings) -> None:
        self._bindings = bindings
        self.stripped = 0

    def _consults(self, node: ast.AST) -> bool:
        return any(_gate_kind(call, self._bindings) is not None for call in _calls_in(node))

    def visit_Expr(self, node: ast.Expr) -> ast.AST:
        if self._consults(node):
            self.stripped += 1
            return ast.copy_location(ast.Pass(), node)
        return node

    def visit_If(self, node: ast.If) -> ast.AST:
        if self._consults(node.test):
            self.stripped += 1
            return ast.copy_location(ast.Pass(), node)
        self.generic_visit(node)
        return node


class _NeutraliseDrainHandlers(ast.NodeTransformer):
    """Replace every handler body of a gate-bearing ``try`` with ``pass``."""

    def __init__(self, bindings: _AuthorityBindings) -> None:
        self._bindings = bindings
        self.neutralised = 0

    def visit_Try(self, node: ast.Try) -> ast.AST:
        self.generic_visit(node)
        if any(_gate_kind(call, self._bindings) is not None for stmt in node.body for call in _calls_in(stmt)):
            for handler in node.handlers:
                handler.body = [ast.copy_location(ast.Pass(), handler)]
                self.neutralised += 1
        return node


def _neutralise_drain_handlers(source: str) -> tuple[str, int]:
    tree = ast.parse(source)
    mutator = _NeutraliseDrainHandlers(_authority_bindings(tree))
    mutated = ast.fix_missing_locations(mutator.visit(tree))
    return ast.unparse(mutated), mutator.neutralised


def _strip_gates(source: str) -> tuple[str, int]:
    tree = ast.parse(source)
    stripper = _StripDrainGates(_authority_bindings(tree))
    mutated = ast.fix_missing_locations(stripper.visit(tree))
    return ast.unparse(mutated), stripper.stripped


_GATED_FILES = sorted({edge.path for edge in _GATED_EDGE_LIST})


class TestSelfMutation:
    @pytest.mark.parametrize("path", _GATED_FILES, ids=lambda p: str(p.relative_to(_SRC)))
    def test_stripping_the_gate_turns_each_edge_red(self, path: Path, tmp_path: Path) -> None:
        source = path.read_text(encoding="utf-8")
        edges = [e for e in _GATED_EDGE_LIST if e.path == path]
        # Pre-condition: the unmutated copy is green (otherwise a red after the
        # mutation proves nothing).
        assert all(scan_edge(source, e.qualname).gated for e in edges)

        mutated_source, stripped = _strip_gates(source)
        assert stripped >= len(edges), f"mutation stripped {stripped} gate statement(s) for {len(edges)} edge(s) -- vacuous mutation"
        mutated_path = tmp_path / path.name
        mutated_path.write_text(mutated_source, encoding="utf-8")

        for edge in edges:
            verdict = scan_edge(mutated_path.read_text(encoding="utf-8"), edge.qualname)
            assert verdict.found and verdict.opener_line is not None, f"mutation destroyed {edge.key} itself: {verdict.describe()}"
            assert not verdict.gated, f"self-mutation: stripping the drain gate from {edge.key} left it classified gated"

    def test_neutralising_a_drain_handler_turns_the_edge_red(self, tmp_path: Path) -> None:
        """Review cycle 1, BLOCKING 1: a ``try: require_drain() except
        DrainDisabled: pass`` falls through to the opener. Neutralise every
        handler of every gate-bearing ``try`` in the real files; each such edge
        must report ungated. At least one live edge (``offer``) has this shape,
        so the mutation cannot be vacuous."""
        mutated_edges: list[str] = []
        for path in _GATED_FILES:
            source = path.read_text(encoding="utf-8")
            mutated_source, neutralised = _neutralise_drain_handlers(source)
            if not neutralised:
                continue
            mutated_path = tmp_path / path.name
            mutated_path.write_text(mutated_source, encoding="utf-8")
            for edge in (e for e in _GATED_EDGE_LIST if e.path == path):
                if scan_edge(mutated_source, edge.qualname) == scan_edge(source, edge.qualname):
                    continue  # this edge does not gate through a try
                verdict = scan_edge(mutated_path.read_text(encoding="utf-8"), edge.qualname)
                assert not verdict.gated, f"neutralising the drain handler of {edge.key} left it classified gated"
                mutated_edges.append(edge.key)
        assert "specify_cli.zeitgeist_client.transport.ZeitgeistClient.offer" in mutated_edges, mutated_edges


def _try_gated(handler_body: str, *, caught: str | None = "hp.DrainDisabled", extra_handler: str = "", finally_body: str = "") -> str:
    """``f`` gating in a ``try`` whose ``except <caught>`` handler runs ``handler_body``."""
    clause = "    except:\n" if caught is None else f"    except {caught}:\n"
    tail = f"    finally:\n{finally_body}" if finally_body else ""
    return (
        "from specify_cli.core import hosted_posture as hp\nfrom x import budget\ndef f(req):\n"
        "    try:\n        hp.require_drain('relay')\n"
        f"{clause}{handler_body}{extra_handler}{tail}"
        "    return budget.open_bounded(req, timeout=1)\n"
    )


_GATED_SOURCE = """
from specify_cli.core.hosted_posture import require_drain
from specify_cli.zeitgeist_client import budget

def fetch(req):
    require_drain("relay")
    return budget.NoRedirects.build().open(req)
"""


class TestGuardBites:
    def test_synthetic_gated_edge_is_classified_gated(self) -> None:
        assert scan_edge(_GATED_SOURCE, "fetch").gated

    @pytest.mark.parametrize(
        "source",
        [
            pytest.param(
                "from specify_cli.core import hosted_posture\nclass G:\n    def mint(self):\n"
                "        if not hosted_posture.drain_posture().enabled:\n            return None\n"
                "        return self._http.post('u')\n",
                id="module-alias-drain-posture-early-return",
            ),
            pytest.param(
                "from specify_cli.core import hosted_posture as hp\nfrom x import budget\ndef f(req):\n"
                "    try:\n        hp.require_drain('relay')\n    except hp.DrainDisabled:\n        return None\n"
                "    return budget.open_bounded(req, timeout=1)\n",
                id="aliased-module-require-in-try",
            ),
            pytest.param(_try_gated("        raise\n", caught="Exception"), id="broad-handler-reraises"),
            pytest.param(_try_gated("        return None\n", extra_handler="    except ValueError:\n        pass\n"), id="unrelated-handler-may-fall-through"),
            pytest.param(_try_gated("        return None\n", finally_body="        cleanup()\n"), id="finally-without-return"),
            pytest.param(
                "from specify_cli.core.hosted_posture import DrainDisabled as DD\n"
                "from specify_cli.core import hosted_posture as hp\nfrom x import budget\ndef f(req):\n"
                "    try:\n        hp.require_drain('relay')\n    except DD:\n        return None\n"
                "    return budget.open_bounded(req, timeout=1)\n",
                id="import-alias-of-drain-disabled-terminates",
            ),
            pytest.param(
                "from specify_cli.core import hosted_posture as hp\nfrom x import budget\nErr = Exception\ndef f(req):\n"
                "    try:\n        hp.require_drain('relay')\n    except Err:\n        return None\n"
                "    return budget.open_bounded(req, timeout=1)\n",
                id="assignment-alias-of-exception-terminates",
            ),
        ],
    )
    def test_other_legitimate_gate_shapes_classify_gated(self, source: str) -> None:
        qualname = "G.mint" if "class G" in source else "f"
        assert scan_edge(source, qualname).gated

    @pytest.mark.parametrize(
        "source",
        [
            pytest.param(_GATED_SOURCE.replace('    require_drain("relay")\n', ""), id="no-gate"),
            pytest.param(
                _GATED_SOURCE.replace(
                    '    require_drain("relay")\n    return budget.NoRedirects.build().open(req)\n',
                    '    opener = budget.NoRedirects.build()\n    require_drain("relay")\n    return opener.open(req)\n',
                ),
                id="gate-after-opener",
            ),
            pytest.param(_GATED_SOURCE.replace('    require_drain("relay")\n', '    if req:\n        require_drain("relay")\n'), id="gate-in-branch"),
            pytest.param(_GATED_SOURCE + "\ndef require_drain(_ctx):\n    return None\n", id="local-look-alike-shadows-authority"),
            pytest.param(
                _GATED_SOURCE.replace("from specify_cli.core.hosted_posture import require_drain", "from elsewhere import require_drain"),
                id="look-alike-from-wrong-module",
            ),
            pytest.param(
                "from specify_cli.core import hosted_posture\nclass G:\n    def mint(self):\n"
                "        hosted_posture.drain_posture()\n        return self._http.post('u')\n",
                id="drain-posture-read-but-ignored",
            ),
            pytest.param(
                "from specify_cli.core import hosted_posture\nclass G:\n    def mint(self):\n"
                "        if False and not hosted_posture.drain_posture().enabled:\n            return None\n"
                "        return self._http.post('u')\n",
                id="drain-posture-test-short-circuited",
            ),
            pytest.param(
                "from specify_cli.core import hosted_posture\nclass G:\n    def mint(self):\n"
                "        if hosted_posture.drain_posture().enabled:\n            return None\n"
                "        return self._http.post('u')\n",
                id="drain-posture-test-inverted",
            ),
            pytest.param(_try_gated("        pass\n"), id="try-handler-swallows"),
            pytest.param(_try_gated("        log.debug('drain off')\n"), id="try-handler-logs-and-falls-through"),
            pytest.param(_try_gated("        pass\n", caught="Exception"), id="broad-except-swallows"),
            pytest.param(_try_gated("        pass\n", caught=None), id="bare-except-swallows"),
            pytest.param(_try_gated("        pass\n", caught="RuntimeError"), id="runtime-error-base-swallows"),
            pytest.param(_try_gated("        pass\n", caught="(ValueError, BaseException)"), id="tuple-with-base-swallows"),
            pytest.param(
                _try_gated("        return None\n", extra_handler="    except Exception:\n        pass\n", caught="hp.DrainDisabled"),
                id="second-broad-handler-swallows",
            ),
            pytest.param(_try_gated("        return None\n", finally_body="        return None\n"), id="finally-return-swallows"),
            pytest.param(
                "from specify_cli.core import hosted_posture as hp\nimport contextlib\nfrom x import budget\ndef f(req):\n"
                "    with contextlib.suppress(hp.DrainDisabled):\n        hp.require_drain('relay')\n"
                "    return budget.open_bounded(req, timeout=1)\n",
                id="suppress-context-manager",
            ),
            pytest.param(
                "from specify_cli.core.hosted_posture import DrainDisabled as DD\n"
                "from specify_cli.core import hosted_posture as hp\nfrom x import budget\ndef f(req):\n"
                "    try:\n        hp.require_drain('relay')\n    except DD:\n        pass\n"
                "    return budget.open_bounded(req, timeout=1)\n",
                id="import-alias-of-drain-disabled-swallows",
            ),
            pytest.param(
                "from specify_cli.core import hosted_posture as hp\nfrom x import budget\nErr = Exception\ndef f(req):\n"
                "    try:\n        hp.require_drain('relay')\n    except Err:\n        pass\n"
                "    return budget.open_bounded(req, timeout=1)\n",
                id="assignment-alias-of-exception-swallows",
            ),
            pytest.param(_try_gated("        pass\n", caught="SomeCustomError"), id="unresolvable-custom-exception-type-swallows"),
            pytest.param(_try_gated("        pass\n", caught="get_exc_type()"), id="unresolvable-handler-type-expression-swallows"),
        ],
    )
    def test_scanner_bites(self, source: str) -> None:
        qualname = "G.mint" if "class G" in source else ("f" if "def f(" in source else "fetch")
        verdict = scan_edge(source, qualname)
        assert verdict.found and verdict.opener_line is not None
        assert not verdict.gated, verdict.describe()

    def test_discovery_sees_a_new_ungated_relay_edge(self, tmp_path: Path) -> None:
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "rogue.py").write_text(
            "from specify_cli.zeitgeist_client import budget\ndef leak(req):\n    return budget.open_bounded(req, timeout=1)\n",
            encoding="utf-8",
        )
        found = {edge.rsplit(".", 1)[-1] for edge in discover_edges(pkg, src_root=tmp_path)}
        assert found == {"leak"}

    @pytest.mark.parametrize(
        "body",
        [
            pytest.param(
                "from specify_cli.zeitgeist_client.budget import NoRedirects as NR\ndef leak(req):\n    return NR.build().open(req)\n",
                id="aliased-class",
            ),
            pytest.param(
                "from specify_cli.zeitgeist_client.budget import open_bounded as ob\ndef leak(req):\n    return ob(req, timeout=1)\n",
                id="aliased-function",
            ),
            pytest.param("from . import budget as b\ndef leak(req):\n    return b.NoRedirects.build().open(req)\n", id="relative-module-alias"),
            pytest.param(
                "import specify_cli.zeitgeist_client.budget as bb\ndef leak(req):\n    return bb.open_bounded(req, timeout=1)\n",
                id="import-as-module-alias",
            ),
            pytest.param(
                "from .budget import NoRedirects\nOPENER = NoRedirects\ndef leak(req):\n    return OPENER.build().open(req)\n",
                id="assignment-alias",
            ),
            pytest.param(
                "def leak(req):\n    from specify_cli.zeitgeist_client.budget import open_bounded as ob\n    return ob(req, timeout=1)\n",
                id="function-local-import-alias",
            ),
            pytest.param("from x import budget\ndef leak(req, run):\n    return run(budget.open_bounded, req)\n", id="opener-passed-as-callback"),
            pytest.param("import urllib.request\ndef leak(req):\n    return urllib.request.urlopen(req)\n", id="stdlib-urlopen"),
            pytest.param("from urllib.request import urlopen as u\ndef leak(req):\n    return u(req)\n", id="stdlib-urlopen-aliased"),
            pytest.param("import urllib.request as ur\ndef leak(req):\n    return ur.build_opener().open(req)\n", id="stdlib-build-opener"),
            pytest.param("from urllib import request\ndef leak(req):\n    return request.build_opener().open(req)\n", id="stdlib-build-opener-module"),
            pytest.param("from http.client import HTTPSConnection as C\ndef leak(host):\n    return C(host).request('GET', '/')\n", id="stdlib-http-client"),
        ],
    )
    def test_discovery_sees_aliased_and_raw_openers(self, body: str, tmp_path: Path) -> None:
        pkg = tmp_path / "specify_cli" / "zeitgeist_client"
        pkg.mkdir(parents=True)
        (pkg / "rogue.py").write_text(body, encoding="utf-8")
        found = {edge.rsplit(".", 1)[-1] for edge in discover_edges(pkg, src_root=tmp_path)}
        assert found == {"leak"}

    def test_stdlib_openers_outside_the_relay_package_are_out_of_scope(self, tmp_path: Path) -> None:
        pkg = tmp_path / "specify_cli" / "dashboard"
        pkg.mkdir(parents=True)
        (pkg / "probe.py").write_text("import urllib.request\ndef health(url):\n    return urllib.request.urlopen(url)\n", encoding="utf-8")
        assert discover_edges(pkg, src_root=tmp_path) == set()

    def test_an_aliased_opener_in_a_registered_shape_needs_the_gate(self) -> None:
        source = (
            "from specify_cli.core.hosted_posture import require_drain\n"
            "from specify_cli.zeitgeist_client.budget import NoRedirects as NR\n"
            "def fetch(req):\n    opener = NR.build()\n    require_drain('relay')\n    return opener.open(req)\n"
        )
        verdict = scan_edge(source, "fetch")
        assert verdict.opener_line == 4 and not verdict.gated

    def test_widen_prereq_opener_is_seen_through_the_saas_client_parameter(self) -> None:
        source = "from x import SaasClient\ndef probe(client: SaasClient) -> bool:\n    return client.health()\n"
        assert scan_edge(source, "probe").opener_line == 3
