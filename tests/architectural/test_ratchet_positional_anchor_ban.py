"""IC-METAGUARD — standing positional-anchor ban (FR-004, FR-014, #2077).

Mission ``content-address-ratchet-allowlists-01KX8M4D`` WP05. Generalizes
DIR-041's ``FORBIDDEN_POSITIONAL_FIELDS`` / ``is_file_line_anchor`` guard
(today scoped to the Contract Registry) to every ratchet allow-list under
``tests/architectural/``, delivering #2077's recurrence guard: once WP03+WP04
migrate every ``(rel, N)`` line seed to a content-addressed
:class:`ContentDescriptor` (``contracts/descriptor-resolver.md``), this test
STANDS WATCH so a future edit cannot reintroduce a positional line anchor into
an authoritative comparand.

The ban is **int-to-line-sink**, not "positional anchor" in general and NOT
``module::Name`` / ``path::qualname`` — the latter would be circular with
WS2's relocation-proof symbol-identity key and unsatisfiable against FR-014's
permanent census-list deferral (``contracts/positional-anchor-ban.md``).

Two predicates, mechanically decidable (no fragile heuristic):

* **Python** — an AST *int-to-line-sink* detector. Flags an int literal that
  reaches (a) the 2nd positional arg of ``composite_key(source, N)`` /
  ``composite_key_from_file(path, N)``, or (b) a subscript / ``.get()`` into a
  ``code_tokens_by_line(...)`` result (the direct call chain, or a variable
  previously assigned straight from that call). Also reuses
  :func:`specify_cli.contracts.anchoring.is_file_line_anchor` to flag a
  ``path:NNN`` string literal embedded in a module-level allow-list seed
  constant (tuple/list/set/frozenset/dict) — the string-shaped twin of the
  same DIR-041 rot. **#2564 seed-tuple-laundering hole**: also flags a
  module-level seed constant holding raw ``(rel, int, ...)`` row tuples whose
  int element is unpacked by a ``for``/comprehension clause into a bare loop
  variable that then reaches ``composite_key(...)``'s / ``composite_key_from_
  file(...)``'s 2nd positional arg — the laundering vector that evades both
  (a) (the 2nd arg there is a ``Name``, not an ``ast.Constant``) and the
  ``file.py:NNN`` grep (the seed spans multiple source lines).
* **Python (raw file:line tuple key — CT7 #2853, widened by #5085)** — bans
  the *regrowth* of the file:line-drift engine in its most direct form: a
  ratchet-key / allow-list seed built as a raw tuple instead of via
  ``composite_key`` / :class:`ContentDescriptor`. The arm is
  **import-agnostic** (#5085 removed the former "file imports the ratchet
  substrate" context gate, which let 94 line pins escape) and fires on any
  module-level **or class-body** seed container (tuple / list / set / dict /
  ``frozenset(...)``) holding:

  - a tuple of >= 2 elements whose first element is path-ish — a str literal,
    a ``Path`` / ``PurePath`` / ``PurePosixPath`` / ``PureWindowsPath`` call
    over one, or a ``/`` join with any path-ish leaf — and any later element a
    bare int literal: ``("a.py", 3)``, ``(Path("src/a.py"), 12)``,
    ``("a.py", "mod.f", 3)``;
  - a str constant that whole-matches an embedded ``[PREFIX:]path:line[:suffix]``
    key (the census ``"src/x.py:98:reset_hard"`` form);
  - a record constructor with a ``line`` / ``lineno`` / ``line_no`` /
    ``file_line`` / ``fileline`` keyword bound to a bare int literal
    (``occurrence=`` / ``op_ordinal=`` are scan ordinals and stay allowed).
* **Text (#5085)** — every non-blank, non-``#`` line of
  ``tests/architectural/**/*.txt`` (the ``_exemptions/`` lists) that
  whole-matches the same ``[PREFIX:]path:line[:suffix]`` key
  (``CALL:src/x.py:12``, ``src/kernel/locks.py:96``). ``IMPORT:<path>`` has no
  line and content-shaped ``path::qualname::token`` entries stay green.

**Exemption lifecycle (FR-003)**: findings are identified by content
``(relpath, symbol, site)``, never by line. WP01 lands one interim row per
flagged site in :data:`_POSITIONAL_ANCHOR_EXEMPTIONS` (94 rows: join 6, kernel
2, destructive 22, mutation 56, overwrite 2, os-detect text 6); WP02-WP04
migrated the underlying allow-lists to content identity; WP13 deleted every row
and pinned the set to ``frozenset()`` (SC-001). A stale row now FAILS. Row
matching is not hand-rolled here: :func:`_partition_exemptions` feeds the
D-OP-9 matcher :func:`tests.architectural._content_identity.partition_findings`.

**Out of scope (#5085), each with a negative fixture below**: ``{path: int}``
dicts (the ints in ``test_timing_coverage_invariant.py::BASELINE_FUNCTIONAL_
ASSERTIONS`` are counts, not lines); function-local containers; the SHA-pinned
/ non-authoritative YAMLs ``census/spec_kitty_home_pin_anchor.yaml`` and
``charter_path_literal_allowlist.yaml``; prose evidence such as
``"decision.py:401; empty stdout"``.
* **YAML** — a field-name rule over the YAML allow-list
  ``inline_meta_read_allowlist.yaml``: an int is permitted ONLY as a ``line`` locator (documented
  non-authoritative — no comparison/membership/count logic reads it), a
  ``count`` floor, or any ``*_baseline`` ceiling. Any other int-valued field
  (a comparand key smuggling a hidden position) is a violation.

**Explicitly OUT of the ban** (enumerate-only, FR-014): ``module::Name`` /
``path::qualname`` name-anchors and ``occurrence`` ordinals (a scan index,
never a lineno) are structurally never caught by either predicate above — they
do not reach either sink shape. The deferred ``path::qualname`` census
allow-list is enumerated by :data:`_FR014_DEFERRED_CENSUS_ALLOWLISTS` and
folded into this guard's failure report.

**Escape hatch**: a genuinely new diagnostic int that is not a line-locator
sink may carry an inline ``# diagnostic-locator`` comment on its own source
line to opt out explicitly (contracts/positional-anchor-ban.md
"Authoritative-vs-diagnostic detection").

**Sequencing (NFR-004)**: written red-first; goes GREEN only once every
in-scope WS1 line seed is migrated (WP03+WP04, merged into this lane per the
WP05 dependency edge). If this test reds on a real (non-fixture) file, that
file still carries an un-migrated positional line seed — report it, do not
force the guard green by weakening the predicate.

Spec source: spec.md FR-004/FR-014; plan.md IC-METAGUARD;
contracts/positional-anchor-ban.md; research.md Decision (deferred census).
"""

from __future__ import annotations

import ast
import re
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeGuard

import pytest
import yaml

from specify_cli.contracts.anchoring import (
    has_diagnostic_locator_marker,
    is_file_line_anchor,
)
from tests.architectural._ast_scan import parse_source, read_source
from tests.architectural._content_identity import partition_findings

# FR-006: `fast` marks this sub-second gate for the fast tier; `architectural`
# is retained as the gate's home marker. Dual-marking adds a home.
pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ARCH_ROOT = _REPO_ROOT / "tests" / "architectural"
_GUARD_FILE = Path(__file__).resolve()

# The two line-locator sink call names (DIR-041 / IC-DESCRIPTOR substrate).
_LINE_SINK_CALL_NAMES: frozenset[str] = frozenset({"composite_key", "composite_key_from_file"})
_TOKENS_BY_LINE_CALL_NAME = "code_tokens_by_line"

# #5085 (FR-001) — the pathlib constructors whose first argument makes a
# ``(Path("src/x.py"), 12)`` tuple element path-ish.
_PATH_CONSTRUCTOR_NAMES: frozenset[str] = frozenset({"Path", "PurePath", "PurePosixPath", "PureWindowsPath"})

# #5085 (FR-001) — keyword names that bind a positional line number inside a
# record constructor (``Entry(path="a.py", lineno=3)``). Mirrors
# ``specify_cli.contracts.anchoring.FORBIDDEN_POSITIONAL_FIELDS`` minus ``file``
# (never int-bound). ``occurrence`` / ``op_ordinal`` are deliberately absent:
# they are scan ordinals, never line numbers (FR-014 carve-out).
_LINE_KEYWORD_NAMES: frozenset[str] = frozenset({"line", "lineno", "line_no", "file_line", "fileline"})

# #5085 (FR-001) — a whole-string embedded ``path:line[:suffix]`` key, with an
# optional upper-case ``PREFIX:`` (the clock gate's ``CALL:<path>:<line>``).
# Whole-string anchoring plus ``\S`` in the suffix keep prose evidence such as
# ``"decision.py:401; empty stdout"`` green.
_EMBEDDED_LINE_KEY_RE = re.compile(r"^(?:[A-Z]+:)?[^\s:]+\.[A-Za-z0-9]+:\d+(?::\S*)?$")

# The os-detect exemption text files whose entry lines the text-universe floor
# counts (FR-001 / NFR-002).
_OS_DETECT_TXT_PREFIX = "os-detect-ban-"

# A path-ish string literal: contains a path separator, or ends in a file
# extension (``.py`` / ``.yaml`` / ...). Mirrors the prefix test in
# ``specify_cli.contracts.anchoring.is_file_line_anchor`` so the tuple form
# ``("file.py", 42)`` and the string form ``"file.py:42"`` share one notion of
# "looks like a source path".
_PATHISH_SUFFIX_RE = re.compile(r"\.[A-Za-z0-9]+$")

# The ratchet allow-list YAMLs this guard's field-name rule scans (FR-012
# retired the orphaned resolution-gate YAML whose consuming gate was deleted).
_YAML_ALLOWLISTS: tuple[str, ...] = ("inline_meta_read_allowlist.yaml",)

# Field names an int is PERMITTED in: the documented non-authoritative ``line``
# locator and any ``count`` floor. Anything ending in ``_baseline`` (a
# count-floor ceiling, e.g. ``canonicalizer_baseline: 3``) is also permitted.
_YAML_INT_PERMITTED_EXACT: frozenset[str] = frozenset({"line", "count"})
_YAML_INT_PERMITTED_SUFFIX = "_baseline"

# FR-014: the deferred path::qualname census allow-list this guard's
# report MUST enumerate as known-relocation-anchored-but-out-of-scope. A
# migrate-or-defer ruling on these lives in FR-014 (default: DEFER — low-churn
# census, not the high-tax line-seed class); a follow-up tracker issue is
# filed at merge time per that ruling.
_FR014_DEFERRED_CENSUS_ALLOWLISTS: tuple[tuple[str, str], ...] = (
    (
        "tests/architectural/test_coord_read_residuals_closeout.py",
        "_IDENTITY_CALLSHAPE_KNOWN_RESIDUALS",
    ),
)


@dataclass(frozen=True)
class LineSinkViolation:
    """One int-to-line-sink (or path:NNN seed-string) finding.

    ``symbol`` (the enclosing binding, or the ``.txt`` file name) and ``site``
    (``ast.unparse`` of the offending node, or the stripped text line) identify
    the finding by CONTENT; ``lineno`` / ``col`` are diagnostic only and never
    participate in exemption matching (DIR-041).
    """

    relpath: str
    lineno: int
    detail: str
    symbol: str
    site: str
    col: int = 0

    @property
    def exemption_key(self) -> tuple[str, str, str]:
        """The content identity an exemption row matches: ``(relpath, symbol, site)``."""
        return (self.relpath, self.symbol, self.site)

    def __str__(self) -> str:  # pragma: no cover - trivial formatting
        return f"{self.relpath}:{self.lineno} [{self.symbol}] {self.site} — {self.detail}"


# ---------------------------------------------------------------------------
# Small, pure, directly-testable AST predicates (S3776 pre-extraction).
# ---------------------------------------------------------------------------


def _is_int_constant(node: ast.AST) -> TypeGuard[ast.Constant]:
    """True when ``node`` is a bare (non-bool) int literal."""
    return isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool)


def _call_func_name(node: ast.AST) -> str | None:
    """Return the callee's bare name (``Name.id`` or ``Attribute.attr``)."""
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _is_composite_key_line_arg(call: ast.Call) -> ast.Constant | None:
    """Sink shape 1: ``composite_key(source, N)`` / ``composite_key_from_file(path, N)``.

    Returns the offending int-literal node when ``call``'s 2nd positional arg
    is a bare int literal — the exact DIR-041 line-locator sink shape FR-004
    names. Returns ``None`` for the compliant shape (a variable/attribute
    2nd arg, e.g. ``composite_key(source, self.lineno)``).
    """
    if _call_func_name(call) not in _LINE_SINK_CALL_NAMES:
        return None
    if len(call.args) < 2:
        return None
    second = call.args[1]
    return second if _is_int_constant(second) else None


def _is_tokens_by_line_call(node: ast.AST) -> bool:
    return _call_func_name(node) == _TOKENS_BY_LINE_CALL_NAME


def _is_tokens_by_line_target(node: ast.AST, tokens_vars: frozenset[str]) -> bool:
    """True when ``node`` is a ``code_tokens_by_line(...)`` call, or a Name
    previously assigned straight from one (see :func:`_collect_tokens_by_line_vars`).
    """
    if _is_tokens_by_line_call(node):
        return True
    return isinstance(node, ast.Name) and node.id in tokens_vars


def _is_tokens_by_line_index(node: ast.AST, tokens_vars: frozenset[str]) -> ast.Constant | None:
    """Sink shape 2: a subscript or ``.get()`` indexing a ``code_tokens_by_line``
    result with a bare int-literal key.

    Handles both the direct call chain (``code_tokens_by_line(source)[42]``)
    and the one-hop variable chain (``tokens = code_tokens_by_line(source);
    tokens[42]``). Returns ``None`` for the compliant shape (a variable/
    attribute key, e.g. ``token_map.get(node.lineno, "")``).
    """
    if isinstance(node, ast.Subscript):
        if not _is_tokens_by_line_target(node.value, tokens_vars):
            return None
        key = node.slice
        return key if _is_int_constant(key) else None
    if isinstance(node, ast.Call) and _call_func_name(node) == "get":
        func = node.func
        if not isinstance(func, ast.Attribute) or not _is_tokens_by_line_target(func.value, tokens_vars):
            return None
        if not node.args:
            return None
        key = node.args[0]
        return key if _is_int_constant(key) else None
    return None


def _collect_tokens_by_line_vars(tree: ast.AST) -> frozenset[str]:
    """Names assigned directly from a ``code_tokens_by_line(...)`` call."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _is_tokens_by_line_call(node.value):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
    return frozenset(names)


def _is_container_literal(node: ast.expr) -> bool:
    """True for a tuple/list/set/dict literal or a ``frozenset(...)`` call —
    the "allow-list seed constant" shape ``contracts/positional-anchor-ban.md``
    scopes the string-locator check to.
    """
    if isinstance(node, (ast.Tuple, ast.List, ast.Set, ast.Dict)):
        return True
    return _call_func_name(node) == "frozenset"


def _class_body_scopes(tree: ast.Module) -> list[tuple[str, list[ast.stmt]]]:
    """``("ClassName.", body)`` for every top-level class (#5085 FR-001): a
    class-attribute allow-list must not evade the ban. Function-local
    containers stay out of scope.
    """
    return [(f"{node.name}.", node.body) for node in tree.body if isinstance(node, ast.ClassDef)]


def _seed_scopes(tree: ast.Module) -> list[tuple[str, list[ast.stmt]]]:
    """The statement lists whose assignments are allow-list seed candidates:
    the module body plus every top-level class body."""
    return [("", tree.body), *_class_body_scopes(tree)]


def _assignment_targets_and_value(stmt: ast.stmt) -> tuple[list[ast.expr], ast.expr] | None:
    """``(targets, value)`` for an ``Assign`` / valued ``AnnAssign``, else ``None``."""
    if isinstance(stmt, ast.Assign):
        return list(stmt.targets), stmt.value
    if isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
        return [stmt.target], stmt.value
    return None


def _symbol_seed_containers(tree: ast.Module) -> list[tuple[str, ast.expr]]:
    """``(symbol, container_literal)`` for every module-level or class-level
    ``Assign``/``AnnAssign`` whose value is a container literal. ``symbol`` is
    the unparsed binding (``_ALLOWLIST`` / ``K.ALLOW``) that names the seed in
    a finding and in an exemption row.
    """
    containers: list[tuple[str, ast.expr]] = []
    for prefix, body in _seed_scopes(tree):
        for stmt in body:
            parts = _assignment_targets_and_value(stmt)
            if parts is None or not _is_container_literal(parts[1]):
                continue
            targets, value = parts
            containers.append((prefix + ", ".join(ast.unparse(t) for t in targets), value))
    return containers


def _module_level_seed_containers(tree: ast.Module) -> list[ast.expr]:
    """RHS exprs of every module-level (or top-level class-body)
    ``Assign``/``AnnAssign`` whose value is a container literal — the
    allow-list seed constants this guard scans for an embedded ``path:NNN``
    anchor string.
    """
    return [container for _, container in _symbol_seed_containers(tree)]


def _stmt_symbol(stmt: ast.stmt, prefix: str) -> str:
    """The binding name a finding inside ``stmt`` is attributed to."""
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return prefix + stmt.name
    parts = _assignment_targets_and_value(stmt)
    if parts is not None:
        return prefix + ", ".join(ast.unparse(t) for t in parts[0])
    return prefix + "<module>" if not prefix else prefix.rstrip(".")


def _enclosing_symbol_index(tree: ast.Module) -> dict[int, str]:
    """``id(node) -> symbol`` for every node, keyed by its enclosing top-level
    (or class-body) statement, so every arm can name a finding's symbol."""
    index: dict[int, str] = {}
    for prefix, body in _seed_scopes(tree):
        for stmt in body:
            symbol = _stmt_symbol(stmt, prefix)
            for node in ast.walk(stmt):
                index[id(node)] = symbol
    return index


# ---------------------------------------------------------------------------
# Thin per-file walkers (compose the predicates; no shape-checking inline).
# ---------------------------------------------------------------------------


def _call_arg_line_sink_violations(tree: ast.Module, source_lines: list[str], relpath: str) -> list[LineSinkViolation]:
    """Walk every ``Call``/``Subscript`` node for the two call-arg sink shapes."""
    tokens_vars = _collect_tokens_by_line_vars(tree)
    symbols: dict[int, str] | None = None  # built lazily: most files have no finding
    violations: list[LineSinkViolation] = []
    for node in ast.walk(tree):
        offender: ast.Constant | None = None
        shape = ""
        if isinstance(node, ast.Call):
            offender = _is_composite_key_line_arg(node)
            shape = "composite_key(...)'s line-locator arg"
            if offender is None:
                offender = _is_tokens_by_line_index(node, tokens_vars)
                shape = "code_tokens_by_line(...).get(...)"
        elif isinstance(node, ast.Subscript):
            offender = _is_tokens_by_line_index(node, tokens_vars)
            shape = "code_tokens_by_line(...)[...]"
        if offender is None or has_diagnostic_locator_marker(source_lines, offender.lineno):
            continue
        if symbols is None:
            symbols = _enclosing_symbol_index(tree)
        violations.append(
            LineSinkViolation(
                relpath,
                offender.lineno,
                f"int literal {offender.value!r} reaches {shape}",
                symbols.get(id(node), "<module>"),
                ast.unparse(node),
                offender.col_offset,
            )
        )
    return violations


def _seed_string_constants(tree: ast.Module, source_lines: list[str]) -> list[tuple[str, ast.Constant, str]]:
    """``(symbol, node, value)`` for every un-escaped str constant inside a
    seed container — the shared input of both string-shaped seed arms."""
    found: list[tuple[str, ast.Constant, str]] = []
    for symbol, container in _symbol_seed_containers(tree):
        for node in ast.walk(container):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            if has_diagnostic_locator_marker(source_lines, node.lineno):
                continue
            found.append((symbol, node, node.value))
    return found


def _seed_string_line_anchor_violations(tree: ast.Module, source_lines: list[str], relpath: str) -> list[LineSinkViolation]:
    """Walk every module-level allow-list seed container for a ``path:NNN`` string
    (registry-predicate parity: :func:`is_file_line_anchor`)."""
    return [
        LineSinkViolation(
            relpath,
            node.lineno,
            f"positional file:line anchor {value!r} in an allow-list seed constant",
            symbol,
            ast.unparse(node),
            node.col_offset,
        )
        for symbol, node, value in _seed_string_constants(tree, source_lines)
        if is_file_line_anchor(value)
    ]


def _is_embedded_line_key(value: str) -> bool:
    """#5085: ``value`` whole-matches an embedded ``[PREFIX:]path:line[:suffix]`` key."""
    return bool(_EMBEDDED_LINE_KEY_RE.match(value.strip()))


def _seed_embedded_line_key_violations(tree: ast.Module, source_lines: list[str], relpath: str) -> list[LineSinkViolation]:
    """#5085 (FR-001): a seed-container string that whole-matches the embedded
    ``path:line[:suffix]`` key shape — the census ``"src/x.py:98:reset_hard"``
    form :func:`is_file_line_anchor` (anchored on a trailing ``:<int>``) misses.
    """
    return [
        LineSinkViolation(
            relpath,
            node.lineno,
            f"embedded path:line key {value!r} in an allow-list seed constant",
            symbol,
            ast.unparse(node),
            node.col_offset,
        )
        for symbol, node, value in _seed_string_constants(tree, source_lines)
        if _is_embedded_line_key(value)
    ]


def _is_line_keyword_record(node: ast.AST) -> bool:
    """#5085: a call carrying a ``line``-family keyword bound to a bare int literal
    (``Entry(path="a.py", lineno=3)``)."""
    if not isinstance(node, ast.Call):
        return False
    return any(kw.arg in _LINE_KEYWORD_NAMES and _is_int_constant(kw.value) for kw in node.keywords)


def _seed_keyword_record_violations(tree: ast.Module, source_lines: list[str], relpath: str) -> list[LineSinkViolation]:
    """#5085 (FR-001): a record constructor inside a seed container that pins a
    line number through a keyword (``lineno=3``)."""
    violations: list[LineSinkViolation] = []
    for symbol, container in _symbol_seed_containers(tree):
        for node in ast.walk(container):
            if not isinstance(node, ast.Call) or not _is_line_keyword_record(node):
                continue
            if has_diagnostic_locator_marker(source_lines, node.lineno):
                continue
            violations.append(
                LineSinkViolation(
                    relpath,
                    node.lineno,
                    "record constructor pins a line number through a line-family keyword",
                    symbol,
                    ast.unparse(node),
                    node.col_offset,
                )
            )
    return violations


def _seed_row_int_position(container: ast.expr) -> int | None:
    """Index of the bare-int-literal element within ``container``'s sub-tuples
    / sub-lists, assuming a uniform positional row shape (row[index] is a
    bare int for every row). ``None`` when no row carries a bare int literal
    (e.g. every row is a ``ContentDescriptor(...)`` call, not a raw tuple —
    the already-clean shape)."""
    for row in getattr(container, "elts", []):
        if not isinstance(row, (ast.Tuple, ast.List)):
            continue
        for index, item in enumerate(row.elts):
            if _is_int_constant(item):
                return index
    return None


def _module_level_named_seed_containers(tree: ast.Module) -> list[tuple[str, ast.expr]]:
    """``(target_name, container_literal)`` for every module-level
    ``Assign``/``AnnAssign`` binding a single ``Name`` to a container literal —
    the subset of :func:`_module_level_seed_containers` that also exposes the
    binding name a ``for``/comprehension clause could iterate by reference.
    """
    named: list[tuple[str, ast.expr]] = []
    for _, body in _seed_scopes(tree):
        for stmt in body:
            parts = _assignment_targets_and_value(stmt)
            if parts is None or not _is_container_literal(parts[1]):
                continue
            targets, value = parts
            named.extend((target.id, value) for target in targets if isinstance(target, ast.Name))
    return named


def _unpack_target_name_at(target: ast.expr, index: int) -> str | None:
    """The bare ``Name`` at position ``index`` of a tuple/list unpacking
    target (a ``for a, b, c in ...`` / comprehension clause target), or
    ``None`` when the target isn't a tuple/list of bare Names wide enough to
    hold ``index``."""
    if not isinstance(target, (ast.Tuple, ast.List)):
        return None
    if not (0 <= index < len(target.elts)):
        return None
    elt = target.elts[index]
    return elt.id if isinstance(elt, ast.Name) else None


def _sink_call_using_name(node: ast.AST, laundered_name: str) -> ast.Call | None:
    """A ``composite_key(...)``/``composite_key_from_file(...)`` call nested in
    ``node`` whose 2nd positional arg is a bare reference to
    ``laundered_name`` — the laundered-seed shape :func:`_is_composite_key_line_arg`
    cannot see (its 2nd arg here is an ``ast.Name``, not an ``ast.Constant``).
    """
    for call in ast.walk(node):
        if not isinstance(call, ast.Call):
            continue
        if _call_func_name(call) not in _LINE_SINK_CALL_NAMES:
            continue
        if len(call.args) < 2:
            continue
        second = call.args[1]
        if isinstance(second, ast.Name) and second.id == laundered_name:
            return call
    return None


def _comprehension_value_exprs(node: ast.AST) -> list[ast.AST]:
    """The element/key/value sub-expressions a comprehension node evaluates
    per iteration — where a laundered sink call would actually appear."""
    if isinstance(node, ast.DictComp):
        return [node.key, node.value]
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
        return [node.elt]
    return []


def _laundering_violation_for_clause(
    iter_name: str,
    target: ast.expr,
    int_positions: dict[str, int],
    search_nodes: Sequence[ast.AST],
    source_lines: list[str],
    relpath: str,
    symbols: dict[int, str],
) -> LineSinkViolation | None:
    """One ``for``/comprehension clause -> at most one laundering violation.

    ``iter_name`` must reference a module-level named seed whose row carries a
    bare int at ``int_positions[iter_name]``; ``target`` must unpack that
    position into a bare loop variable that ``value_exprs`` then feeds into a
    ``composite_key(...)``/``composite_key_from_file(...)`` sink.
    """
    if iter_name not in int_positions:
        return None
    laundered = _unpack_target_name_at(target, int_positions[iter_name])
    if laundered is None:
        return None
    for search_node in search_nodes:
        call = _sink_call_using_name(search_node, laundered)
        if call is None or has_diagnostic_locator_marker(source_lines, call.lineno):
            continue
        return LineSinkViolation(
            relpath,
            call.lineno,
            f"seed-tuple int element (from {iter_name!r}) laundered through loop/comprehension variable {laundered!r} into composite_key(...)'s line-locator arg",
            symbols.get(id(call), "<module>"),
            ast.unparse(call),
            call.col_offset,
        )
    return None


def _seed_tuple_laundering_violations(tree: ast.Module, source_lines: list[str], relpath: str) -> list[LineSinkViolation]:
    """#2564: a module-level ``(rel, int, ...)`` seed tuple whose int element is
    laundered through a ``for``/comprehension unpacking variable into a
    ``composite_key(...)``/``composite_key_from_file(...)`` line-locator sink.

    This is the residual bypass :func:`_is_composite_key_line_arg` cannot see
    (there the 2nd arg is a bare ``ast.Constant``; here it is an ``ast.Name``
    bound by the unpacking clause) and the ``file.py:NNN`` grep cannot see
    (the seed spans multiple source lines, so no single line matches the
    pattern).
    """
    seeds = _module_level_named_seed_containers(tree)
    if not seeds:
        return []
    int_positions = {name: pos for name, container in seeds for pos in [_seed_row_int_position(container)] if pos is not None}
    if not int_positions:
        return []

    symbols = _enclosing_symbol_index(tree)
    violations: list[LineSinkViolation] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            value_exprs = _comprehension_value_exprs(node)
            for gen in node.generators:
                if not isinstance(gen.iter, ast.Name):
                    continue
                violation = _laundering_violation_for_clause(gen.iter.id, gen.target, int_positions, value_exprs, source_lines, relpath, symbols)
                if violation is not None:
                    violations.append(violation)
        elif isinstance(node, ast.For) and isinstance(node.iter, ast.Name):
            violation = _laundering_violation_for_clause(node.iter.id, node.target, int_positions, node.body, source_lines, relpath, symbols)
            if violation is not None:
                violations.append(violation)
    return violations


def _is_pathish_string_literal(node: ast.AST) -> bool:
    """True when ``node`` is a str literal that looks like a source-file path.

    Path-ish = contains a ``/`` or ``\\`` separator, or ends in a file
    extension. This narrows the raw-2-tuple ban to the ``(path, line)`` shape
    (never an innocent ``(label, count)`` 2-tuple that happens to pair a string
    with an int).
    """
    if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
        return False
    text = node.value.strip()
    if not text:
        return False
    return "/" in text or "\\" in text or bool(_PATHISH_SUFFIX_RE.search(text))


def _is_path_constructor_call(node: ast.AST) -> bool:
    """``Path(<pathish>)`` / ``PurePath`` / ``PurePosixPath`` / ``PureWindowsPath``
    (Name or Attribute callee) whose first argument is itself path-ish."""
    if not isinstance(node, ast.Call) or _call_func_name(node) not in _PATH_CONSTRUCTOR_NAMES:
        return False
    return bool(node.args) and _is_pathish_element(node.args[0])


def _is_pathish_element(node: ast.AST) -> bool:
    """#5085 (FR-001): a tuple's path element — a path-ish str literal, a
    ``Path(...)``-family call over one, or a ``/`` join with any path-ish leaf."""
    if _is_pathish_string_literal(node) or _is_path_constructor_call(node):
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _is_pathish_element(node.left) or _is_pathish_element(node.right)
    return False


def _is_file_line_tuple(node: ast.AST) -> bool:
    """Sink shape (CT7 widened by #5085): a tuple of >= 2 elements whose first
    element is path-ish and any later element is a bare int literal —
    ``("file.py", 472)``, ``(Path("src/a.py"), 12)``, ``("a.py", "f", 3)``. The
    raw file:line key that must be a ``composite_key`` / :class:`ContentDescriptor`.
    """
    if not isinstance(node, ast.Tuple) or len(node.elts) < 2:
        return False
    first, *rest = node.elts
    return _is_pathish_element(first) and any(_is_int_constant(elt) for elt in rest)


def _raw_file_line_tuple_seed_violations(tree: ast.Module, source_lines: list[str], relpath: str) -> list[LineSinkViolation]:
    """CT7 (#2853, widened by #5085): a raw ``(path, ..., line)`` tuple used as a
    ratchet key / allow-list seed inside a module-level or class-level seed
    container. Import-agnostic: any file under ``tests/architectural/`` is in
    scope, whatever it imports.
    """
    violations: list[LineSinkViolation] = []
    for symbol, container in _symbol_seed_containers(tree):
        for node in ast.walk(container):
            if not isinstance(node, ast.Tuple) or not _is_file_line_tuple(node):
                continue
            if has_diagnostic_locator_marker(source_lines, node.lineno):
                continue
            site = ast.unparse(node)
            violations.append(
                LineSinkViolation(
                    relpath,
                    node.lineno,
                    f"raw (path, line) {len(node.elts)}-tuple {site} used as a ratchet key / allow-list seed — "
                    "anchor on content via composite_key(...) / ContentDescriptor instead",
                    symbol,
                    site,
                    node.col_offset,
                )
            )
    return violations


def _dedupe_by_site(violations: list[LineSinkViolation]) -> list[LineSinkViolation]:
    """Report one finding per site, not per arm: two arms hitting the same AST
    node (e.g. the registry-parity string arm and the embedded-key arm on
    ``"src/x.py:12"``) collapse to the first finding."""
    seen: set[tuple[int, int, str]] = set()
    unique: list[LineSinkViolation] = []
    for violation in violations:
        key = (violation.lineno, violation.col, violation.site)
        if key in seen:
            continue
        seen.add(key)
        unique.append(violation)
    return unique


def _scan_python_source(source: str, relpath: str) -> list[LineSinkViolation]:
    """Parse ``source`` once and run all Python sink-shape walkers over it."""
    tree = parse_source(source, display=relpath)
    source_lines = source.splitlines()
    return _dedupe_by_site(
        _call_arg_line_sink_violations(tree, source_lines, relpath)
        + _seed_string_line_anchor_violations(tree, source_lines, relpath)
        + _seed_embedded_line_key_violations(tree, source_lines, relpath)
        + _seed_tuple_laundering_violations(tree, source_lines, relpath)
        + _raw_file_line_tuple_seed_violations(tree, source_lines, relpath)
        + _seed_keyword_record_violations(tree, source_lines, relpath)
    )


def _scan_python_file(path: Path) -> list[LineSinkViolation]:
    relpath = path.relative_to(_REPO_ROOT).as_posix()
    return _scan_python_source(read_source(path, display=relpath), relpath)


def _iter_architectural_python_files() -> list[Path]:
    """Every ``tests/architectural/**/*.py`` file, excluding this guard itself
    (whose own predicate helpers legitimately name the sink shapes) and any
    ``__pycache__`` artifact.
    """
    return sorted(p for p in _ARCH_ROOT.rglob("*.py") if "__pycache__" not in p.parts and p.resolve() != _GUARD_FILE)


def _iter_architectural_text_files() -> list[Path]:
    """Every ``tests/architectural/**/*.txt`` file (#5085 FR-001: the
    ``_exemptions/*.txt`` exemption lists are authoritative comparands too)."""
    return sorted(_ARCH_ROOT.rglob("*.txt"))


def _text_entry_lines(text: str) -> list[tuple[int, str]]:
    """``(lineno, stripped)`` for every non-blank, non-``#`` line of an
    exemption text file — the entries a gate actually reads."""
    entries: list[tuple[int, str]] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if stripped and not stripped.startswith("#"):
            entries.append((lineno, stripped))
    return entries


def _is_text_line_anchor(entry: str) -> bool:
    """#5085 text arm: an exemption entry line that is a ``[PREFIX:]path:line`` pin."""
    return _is_embedded_line_key(entry)


def _scan_text_source(text: str, relpath: str) -> list[LineSinkViolation]:
    """#5085 (FR-001): flag every exemption entry line that whole-matches the
    embedded ``[PREFIX:]path:line[:suffix]`` key. ``IMPORT:<path>`` (no line)
    and content-shaped ``path::qualname::token`` entries stay green."""
    symbol = Path(relpath).name
    return [
        LineSinkViolation(relpath, lineno, f"positional path:line exemption entry {entry!r}", symbol, entry)
        for lineno, entry in _text_entry_lines(text)
        if _is_text_line_anchor(entry)
    ]


def _scan_text_file(path: Path) -> list[LineSinkViolation]:
    relpath = path.relative_to(_REPO_ROOT).as_posix()
    return _scan_text_source(path.read_text(encoding="utf-8"), relpath)


def _all_positional_anchor_findings() -> list[LineSinkViolation]:
    """Every live finding (Python + text) across the scan universe, UNFILTERED."""
    findings: list[LineSinkViolation] = []
    for path in _iter_architectural_python_files():
        findings.extend(_scan_python_file(path))
    for path in _iter_architectural_text_files():
        findings.extend(_scan_text_file(path))
    return findings


def _row_budget(rows: frozenset[tuple[str, str, str, str]]) -> Counter[tuple[str, str, str]]:
    """The exemption rows as a multiset of ``(relpath, symbol, site)`` keys."""
    return Counter((relpath, symbol, site) for relpath, symbol, site, _ in rows)


def _partition_exemptions(
    findings: Sequence[LineSinkViolation], rows: frozenset[tuple[str, str, str, str]]
) -> tuple[list[LineSinkViolation], list[tuple[str, str, str]]]:
    """``(unexpected, stale)`` via the D-OP-9 matcher
    :func:`tests.architectural._content_identity.partition_findings`.

    Multiset (FR-003): one row suppresses exactly ONE finding with the same
    ``(relpath, symbol, site)``; ``lineno`` never participates, so two
    textually identical sites in one symbol need two rows. ``stale`` is every
    row key left unconsumed, sorted.
    """
    unexpected, unused = partition_findings(((f.exemption_key, f) for f in findings), _row_budget(rows))
    return unexpected, sorted(unused.elements())


def _unexempted(findings: Sequence[LineSinkViolation], rows: frozenset[tuple[str, str, str, str]]) -> list[LineSinkViolation]:
    """Findings no exemption row suppresses (see :func:`_partition_exemptions`)."""
    return _partition_exemptions(findings, rows)[0]


def _stale_exemption_rows(findings: Sequence[LineSinkViolation], rows: frozenset[tuple[str, str, str, str]]) -> list[tuple[str, str, str]]:
    """Row keys with no live finding left to suppress (see :func:`_partition_exemptions`)."""
    return _partition_exemptions(findings, rows)[1]


def _per_symbol_breakdown(findings: Sequence[LineSinkViolation]) -> str:
    """``relpath::symbol: N`` per symbol — the RED evidence shape (#5068)."""
    counts = Counter((f.relpath, f.symbol) for f in findings)
    return "\n".join(f"  {relpath}::{symbol}: {n}" for (relpath, symbol), n in sorted(counts.items()))


def _yaml_int_field_permitted(key: str) -> bool:
    return key in _YAML_INT_PERMITTED_EXACT or key.endswith(_YAML_INT_PERMITTED_SUFFIX)


def _yaml_int_field_violations(doc: Any, path: str = "") -> list[str]:
    """Recursively flag an int scalar at a disallowed field name in a parsed
    allow-list YAML document. Ints are permitted only as ``line``, ``count``,
    or a ``*_baseline`` field (see module docstring); every other int-valued
    field is a positional-anchor-smuggling violation.
    """
    violations: list[str] = []
    if isinstance(doc, dict):
        for key, value in doc.items():
            child_path = f"{path}.{key}" if path else str(key)
            if isinstance(value, int) and not isinstance(value, bool):
                if not _yaml_int_field_permitted(str(key)):
                    violations.append(f"{child_path} = {value!r}")
                continue
            violations.extend(_yaml_int_field_violations(value, child_path))
    elif isinstance(doc, list):
        for index, item in enumerate(doc):
            violations.extend(_yaml_int_field_violations(item, f"{path}[{index}]"))
    return violations


def _fr014_deferred_census_report() -> str:
    """The FR-014 enumeration folded into this guard's failure report."""
    lines = [
        f"  - {name} ({relpath}) — path::qualname census, known-relocation-anchored-but-out-of-scope (FR-014 default-defer; follow-up tracked separately)"
        for relpath, name in _FR014_DEFERRED_CENSUS_ALLOWLISTS
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# #5085 FR-003 / SC-001 — the positional-anchor exemption set, pinned EMPTY.
#
# A row is ``(relpath, symbol, site, reason)`` named by CONTENT (``site`` is
# ``ast.unparse(node)`` for Python or the stripped entry line for text;
# ``lineno`` never participates). WP01 landed 94 interim rows, WP02-WP04
# migrated every underlying allow-list to content identity, and WP13 deleted
# every row. This set MUST stay ``frozenset()``: the exact-set pin
# ``test_positional_anchor_exemptions_are_pinned_empty`` reds on any re-added
# row, and a future row would need a named open issue plus review to justify
# relaxing that pin. ``test_positional_anchor_exemptions_are_exact`` still
# FAILS on a row whose site no longer produces a finding.
# ---------------------------------------------------------------------------

_POSITIONAL_ANCHOR_EXEMPTIONS: frozenset[tuple[str, str, str, str]] = frozenset()


# ---------------------------------------------------------------------------
# T020 — the standing gate itself.
# ---------------------------------------------------------------------------


def test_architectural_python_universe_is_nonempty() -> None:
    """Anti-vacuity: the walker actually scans a non-trivial file set."""
    files = _iter_architectural_python_files()
    # Concrete floor (NFR-002): 263 on the planning base; WP07 retires one.
    assert len(files) >= 262, f"only {len(files)} tests/architectural/**/*.py files discovered — the walker may be mis-scoped (the guard would pass vacuously)"


def _os_detect_entry_lines_inspected() -> int:
    """Entry lines the text arm inspects across ``_exemptions/os-detect-ban-*.txt``
    only (NOT all 20 text files, which would meet the floor trivially)."""
    return sum(len(_text_entry_lines(path.read_text(encoding="utf-8"))) for path in _iter_architectural_text_files() if path.name.startswith(_OS_DETECT_TXT_PREFIX))


def test_architectural_text_universe_meets_floor() -> None:
    """Anti-vacuity (#5085 NFR-002): the text walker sees the exemption files,
    and the os-detect exemption files still carry the six entry lines the text
    arm inspects (they survive WP03 as content lines)."""
    files = _iter_architectural_text_files()
    assert len(files) >= 20, f"only {len(files)} tests/architectural/**/*.txt files discovered"
    inspected = _os_detect_entry_lines_inspected()
    assert inspected >= 6, f"only {inspected} os-detect exemption entry line(s) inspected"


def test_no_int_line_sink_in_architectural_python_seeds() -> None:
    """Standing gate: no int literal reaches a composite_key(...) /
    code_tokens_by_line(...) line-locator sink, and no module-level allow-list
    seed constant embeds a positional ``path:NNN`` anchor string, anywhere
    under ``tests/architectural/``.

    GREEN today (post WP03+WP04): every WS1 line seed was migrated to a
    ContentDescriptor. A reintroduced ``(rel, N)`` line seed reds this test —
    migrate it to a ContentDescriptor (contracts/descriptor-resolver.md), or
    mark a genuinely non-authoritative diagnostic int with
    ``# diagnostic-locator`` on its own source line.
    """
    findings: list[LineSinkViolation] = []
    for path in _iter_architectural_python_files():
        findings.extend(_scan_python_file(path))
    violations = _unexempted(findings, _POSITIONAL_ANCHOR_EXEMPTIONS)
    assert not violations, (
        "positional line-anchor(s) reached an authoritative comparand "
        "(DIR-041 generalization / IC-METAGUARD, #2077 recurrence guard):\n"
        + "\n".join(f"  - {v}" for v in violations)
        + f"\n\nper-symbol breakdown ({len(violations)} site(s)):\n"
        + _per_symbol_breakdown(violations)
        + "\n\nFR-014 deferred (enumerate-only, NOT part of this ban):\n"
        + _fr014_deferred_census_report()
    )


def test_no_positional_anchor_in_architectural_text_files() -> None:
    """Standing gate (text arm, #5085 FR-001): no ``tests/architectural/**/*.txt``
    exemption entry is a ``[PREFIX:]path:line`` pin (the exemption set
    :data:`_POSITIONAL_ANCHOR_EXEMPTIONS` is pinned empty).
    """
    findings: list[LineSinkViolation] = []
    for path in _iter_architectural_text_files():
        findings.extend(_scan_text_file(path))
    violations = _unexempted(findings, _POSITIONAL_ANCHOR_EXEMPTIONS)
    assert not violations, (
        "positional path:line pin(s) in an architectural exemption text file (#5085):\n"
        + "\n".join(f"  - {v}" for v in violations)
        + f"\n\nper-symbol breakdown ({len(violations)} site(s)):\n"
        + _per_symbol_breakdown(violations)
    )


def _assert_exemptions_exact(findings: Sequence[LineSinkViolation], rows: frozenset[tuple[str, str, str, str]]) -> None:
    """FR-003 exactness over ``rows``: a live finding with no row FAILS (growth
    is a visible diff) and a row with no live finding FAILS (a stale row must be
    deleted, never left masking a future regression at the same site)."""
    for row in rows:
        assert len(row) == 4 and all(row[:3]), f"malformed exemption row {row!r}"
        assert row[3].strip(), f"exemption row without a reason: {row!r}"
    unexpected, stale = _partition_exemptions(findings, rows)
    assert not unexpected, "live positional-anchor finding(s) with no exemption row:\n" + "\n".join(f"  - {v}" for v in unexpected)
    assert not stale, "#5085 exemption row(s) no longer match a live finding — delete them:\n" + "\n".join(f"  - {row!r}" for row in stale)


def test_positional_anchor_exemptions_are_exact() -> None:
    """FR-003 exactness (standing): every live finding has a row AND every row
    still suppresses a live finding. WP13 flipped the stale-row branch from a
    warning to a failure once WP02-WP04 migrated every interim row away.
    """
    _assert_exemptions_exact(_all_positional_anchor_findings(), _POSITIONAL_ANCHOR_EXEMPTIONS)


def test_non_vacuity_stale_exemption_row_fails_exactness(monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-002 self-mutation: a synthetic row whose site does not exist must
    FAIL the standing exactness gate (not merely warn), and the failure names
    that row. Goes through the real gate and its partition function.
    """
    synthetic = (
        "tests/architectural/_no_such_gate.py",
        "_NO_SUCH_ALLOWLIST",
        "('src/no/such/file.py', 1)",
        "WP13 self-mutation fixture",
    )
    monkeypatch.setattr(sys.modules[__name__], "_POSITIONAL_ANCHOR_EXEMPTIONS", frozenset({synthetic}))
    with pytest.raises(AssertionError, match="no longer match a live finding") as excinfo:
        test_positional_anchor_exemptions_are_exact()
    assert repr(synthetic[:3]) in str(excinfo.value)


def _exemption_rows_by_group(rows: frozenset[tuple[str, str, str, str]]) -> str:
    """``relpath::symbol: N`` per exemption-row group (FR-003 pin report)."""
    counts = Counter((relpath, symbol) for relpath, symbol, _, _ in rows)
    return "\n".join(f"  {relpath}::{symbol}: {n}" for (relpath, symbol), n in sorted(counts.items()))


def test_positional_anchor_exemptions_are_pinned_empty() -> None:
    """FR-003 / SC-001 acceptance pin: the positional-anchor exemption set is
    EXACTLY empty. Re-adding any row is a visible diff against ``frozenset()``
    (exact-set equality, never ``len(...) == 0`` over a filtered view).
    """
    assert frozenset() == _POSITIONAL_ANCHOR_EXEMPTIONS, (
        f"{len(_POSITIONAL_ANCHOR_EXEMPTIONS)} positional-anchor exemption row(s) remain; "
        "the set must stay frozenset() (FR-003, SC-001). Remaining rows by "
        "(relpath, symbol):\n" + _exemption_rows_by_group(_POSITIONAL_ANCHOR_EXEMPTIONS)
    )


def test_no_int_field_ban_in_ratchet_allowlist_yaml() -> None:
    """Standing gate (YAML arm): an int is permitted only in ``line`` / ``count``
    / ``*_baseline`` across the ratchet allow-list YAMLs in
    :data:`_YAML_ALLOWLISTS`. Any other
    int-valued field is a smuggled positional anchor.
    """
    violations: list[str] = []
    for name in _YAML_ALLOWLISTS:
        doc = yaml.safe_load((_ARCH_ROOT / name).read_text(encoding="utf-8"))
        violations.extend(f"{name}: {v}" for v in _yaml_int_field_violations(doc))
    assert not violations, "an int reached a non-locator/non-count/non-baseline YAML field in a ratchet allow-list (positional-anchor smuggling):\n" + "\n".join(
        f"  - {v}" for v in violations
    )


# ---------------------------------------------------------------------------
# T021 — FR-014 deferred census enumeration.
# ---------------------------------------------------------------------------


def test_fr014_deferred_census_allowlists_enumerated() -> None:
    """FR-014: the guard's report enumerates the deferred path::qualname
    census allow-list as known-relocation-anchored-but-out-of-scope, and it
    still names a live symbol (drift guard — a rename/relocation must
    update this enumeration too).
    """
    assert len(_FR014_DEFERRED_CENSUS_ALLOWLISTS) == 1
    for relpath, name in _FR014_DEFERRED_CENSUS_ALLOWLISTS:
        target = _REPO_ROOT / relpath
        assert target.exists(), f"{relpath} moved/renamed — update the FR-014 enumeration"
        assert name in target.read_text(encoding="utf-8"), f"{name} no longer appears in {relpath} — update the FR-014 enumeration"
    report = _fr014_deferred_census_report()
    for _, name in _FR014_DEFERRED_CENSUS_ALLOWLISTS:
        assert name in report


# ---------------------------------------------------------------------------
# Direct unit tests for each predicate (squad requirement — S3776 discipline).
# ---------------------------------------------------------------------------


def _parse_call(source: str) -> ast.Call:
    tree = ast.parse(source)
    expr = tree.body[0]
    assert isinstance(expr, ast.Expr)
    call = expr.value
    assert isinstance(call, ast.Call)
    return call


def _parse_expr(source: str) -> ast.expr:
    """Return the value expr of a single-expression-statement source (strict-clean
    accessor: narrows ``body[0]`` to ``ast.Expr`` so ``.value`` is typed)."""
    tree = ast.parse(source)
    stmt = tree.body[0]
    assert isinstance(stmt, ast.Expr)
    return stmt.value


class TestIsCompositeKeyLineArg:
    def test_flags_int_literal_second_arg(self) -> None:
        call = _parse_call("composite_key(source, 347)")
        offender = _is_composite_key_line_arg(call)
        assert offender is not None
        assert offender.value == 347

    def test_flags_composite_key_from_file_int_literal(self) -> None:
        call = _parse_call("composite_key_from_file(path, 42)")
        offender = _is_composite_key_line_arg(call)
        assert offender is not None
        assert offender.value == 42

    def test_permits_variable_second_arg(self) -> None:
        call = _parse_call("composite_key(source, self.lineno)")
        assert _is_composite_key_line_arg(call) is None

    def test_permits_unrelated_call(self) -> None:
        call = _parse_call("some_other_call(source, 42)")
        assert _is_composite_key_line_arg(call) is None

    def test_permits_single_arg_call(self) -> None:
        call = _parse_call("composite_key(source)")
        assert _is_composite_key_line_arg(call) is None


class TestIsTokensByLineIndex:
    def test_flags_direct_chain_subscript(self) -> None:
        node = _parse_expr("code_tokens_by_line(source)[42]")
        assert isinstance(node, ast.Subscript)
        offender = _is_tokens_by_line_index(node, frozenset())
        assert offender is not None
        assert offender.value == 42

    def test_flags_direct_chain_get(self) -> None:
        call = _parse_call('code_tokens_by_line(source).get(42, "")')
        offender = _is_tokens_by_line_index(call, frozenset())
        assert offender is not None
        assert offender.value == 42

    def test_flags_variable_chain_subscript(self) -> None:
        node = _parse_expr("tokens[42]")
        assert isinstance(node, ast.Subscript)
        offender = _is_tokens_by_line_index(node, frozenset({"tokens"}))
        assert offender is not None
        assert offender.value == 42

    def test_flags_variable_chain_get(self) -> None:
        call = _parse_call('token_map.get(42, "")')
        offender = _is_tokens_by_line_index(call, frozenset({"token_map"}))
        assert offender is not None
        assert offender.value == 42

    def test_permits_variable_key(self) -> None:
        call = _parse_call('code_tokens_by_line(source).get(node.lineno, "")')
        assert _is_tokens_by_line_index(call, frozenset()) is None

    def test_permits_untracked_variable_subscript(self) -> None:
        node = _parse_expr("tokens[42]")
        assert isinstance(node, ast.Subscript)
        # "tokens" was never seen assigned from code_tokens_by_line(...).
        assert _is_tokens_by_line_index(node, frozenset()) is None

    def test_permits_items_call(self) -> None:
        call = _parse_call("code_tokens_by_line(source).items()")
        assert _is_tokens_by_line_index(call, frozenset()) is None


class TestCollectTokensByLineVars:
    def test_collects_direct_assignment(self) -> None:
        tree = ast.parse("tokens = code_tokens_by_line(source)")
        assert _collect_tokens_by_line_vars(tree) == frozenset({"tokens"})

    def test_ignores_unrelated_assignment(self) -> None:
        tree = ast.parse("tokens = some_other_call(source)")
        assert _collect_tokens_by_line_vars(tree) == frozenset()


class TestModuleLevelSeedContainers:
    def test_collects_tuple_assignment(self) -> None:
        tree = ast.parse('_SEED: tuple[str, ...] = ("a.py:1", "b.py:2")')
        containers = _module_level_seed_containers(tree)
        assert len(containers) == 1
        assert isinstance(containers[0], ast.Tuple)

    def test_collects_frozenset_call(self) -> None:
        tree = ast.parse('_SEED = frozenset({"a.py:1"})')
        containers = _module_level_seed_containers(tree)
        assert len(containers) == 1

    def test_ignores_function_local_container(self) -> None:
        tree = ast.parse('def f():\n    seed = ("a.py:1",)\n    return seed\n')
        assert _module_level_seed_containers(tree) == []

    def test_ignores_scalar_assignment(self) -> None:
        tree = ast.parse("_BASELINE = 3")
        assert _module_level_seed_containers(tree) == []


class TestFileLineTupleArmIsImportAgnostic:
    """#5085 inversion of the former ``TestImportsRatchetSubstrate``: the SAME four
    import-shaped fixtures, each now carrying a ``("x.py", 12)`` seed, are all
    flagged — the tuple arm no longer keys off what a file imports."""

    _SEED = '\n_SEED = (("x.py", 12),)\n'

    def test_flags_raw_tuple_with_ratchet_keys_module_import(self) -> None:
        source = "from tests.architectural._ratchet_keys import composite_key" + self._SEED
        assert len(_scan_python_source(source, "scratch/a.py")) >= 1

    def test_flags_raw_tuple_with_anchoring_module_import(self) -> None:
        source = "from specify_cli.contracts.anchoring import ContentDescriptor" + self._SEED
        assert len(_scan_python_source(source, "scratch/a.py")) >= 1

    def test_flags_raw_tuple_with_substrate_name_from_any_module(self) -> None:
        source = "from somewhere.shim import composite_key_from_file" + self._SEED
        assert len(_scan_python_source(source, "scratch/a.py")) >= 1

    def test_flags_raw_tuple_in_non_substrate_file(self) -> None:
        # Mirrors test_kernel_no_doctrine_import.py: ast + pathlib + pytest only.
        source = "import ast\nfrom pathlib import Path\nimport pytest\n" + self._SEED
        assert len(_scan_python_source(source, "scratch/a.py")) >= 1


class TestIsPathishStringLiteral:
    def test_flags_py_extension(self) -> None:
        assert _is_pathish_string_literal(_parse_expr('"kernel/schema_utils.py"'))

    def test_flags_bare_extension_no_separator(self) -> None:
        assert _is_pathish_string_literal(_parse_expr('"schema_utils.py"'))

    def test_rejects_plain_label(self) -> None:
        assert not _is_pathish_string_literal(_parse_expr('"some_label"'))

    def test_rejects_int_node(self) -> None:
        assert not _is_pathish_string_literal(_parse_expr("42"))


class TestIsFileLineTuple:
    def test_flags_pathish_str_int_pair(self) -> None:
        assert _is_file_line_tuple(_parse_expr('("some_file.py", 472)'))

    def test_rejects_str_str_pair(self) -> None:
        assert not _is_file_line_tuple(_parse_expr('("a.py", "b.py")'))

    def test_rejects_label_int_pair(self) -> None:
        assert not _is_file_line_tuple(_parse_expr('("label", 3)'))

    def test_flags_path_qualname_int_three_tuple(self) -> None:
        # #5085 inversion of the former test_rejects_three_tuple: same literal.
        assert _is_file_line_tuple(_parse_expr('("a.py", 3, "rationale")'))

    def test_flags_path_constructor_element(self) -> None:
        assert _is_file_line_tuple(_parse_expr('(Path("src/a.py"), 12)'))

    def test_flags_attribute_path_constructor_element(self) -> None:
        assert _is_file_line_tuple(_parse_expr('(pathlib.PurePosixPath("src/a.py"), 12)'))

    def test_flags_div_join_element(self) -> None:
        assert _is_file_line_tuple(_parse_expr('(Path("a") / "b.py", 12)'))

    def test_rejects_bool_line_element(self) -> None:
        assert not _is_file_line_tuple(_parse_expr('("a.py", True)'))

    def test_rejects_non_path_call_element(self) -> None:
        assert not _is_file_line_tuple(_parse_expr('(str("a.py"), 12)'))

    def test_rejects_single_element_tuple(self) -> None:
        assert not _is_file_line_tuple(_parse_expr('("a.py",)'))


class TestIsPathishElement:
    def test_rejects_non_pathish_path_call(self) -> None:
        assert not _is_pathish_element(_parse_expr('Path("label")'))

    def test_rejects_argless_path_call(self) -> None:
        assert not _is_pathish_element(_parse_expr("Path()"))

    def test_rejects_non_div_binop(self) -> None:
        assert not _is_pathish_element(_parse_expr('"a" + "b.py"'))

    def test_flags_nested_div_join(self) -> None:
        assert _is_pathish_element(_parse_expr('ROOT / "src" / "x.py"'))


class TestEmbeddedLineKey:
    def test_flags_census_key(self) -> None:
        assert _is_embedded_line_key("src/x.py:98:reset_hard")

    def test_flags_prefixed_call_key(self) -> None:
        assert _is_embedded_line_key("CALL:src/x.py:12")

    def test_flags_bare_path_line(self) -> None:
        assert _is_embedded_line_key("kernel/locks.py:96")

    def test_rejects_prose_evidence(self) -> None:
        assert not _is_embedded_line_key("decision.py:401; empty stdout")

    def test_rejects_import_prefix_without_line(self) -> None:
        assert not _is_embedded_line_key("IMPORT:src/x.py")

    def test_rejects_qualname_content_key(self) -> None:
        assert not _is_embedded_line_key("src/a.py::f::reset_hard#0")


class TestIsLineKeywordRecord:
    def test_flags_lineno_keyword(self) -> None:
        assert _is_line_keyword_record(_parse_expr('Entry(path="a.py", lineno=3)'))

    def test_rejects_occurrence_keyword(self) -> None:
        assert not _is_line_keyword_record(_parse_expr('ContentDescriptor(rel_path="a.py", occurrence=0)'))

    def test_rejects_op_ordinal_keyword(self) -> None:
        assert not _is_line_keyword_record(_parse_expr('CensusKey(rel="a.py", op_ordinal=1)'))

    def test_rejects_non_int_line_keyword(self) -> None:
        assert not _is_line_keyword_record(_parse_expr("Entry(line=node.lineno)"))

    def test_rejects_non_call(self) -> None:
        assert not _is_line_keyword_record(_parse_expr('("a.py", 3)'))


class TestScanTextSource:
    def test_flags_call_prefixed_line_pin(self) -> None:
        findings = _scan_text_source("CALL:src/x.py:12\n", "t.txt")
        assert len(findings) == 1
        assert findings[0].symbol == "t.txt"
        assert findings[0].site == "CALL:src/x.py:12"

    def test_permits_import_prefix(self) -> None:
        assert _scan_text_source("IMPORT:src/x.py\n", "t.txt") == []

    def test_permits_comment_line(self) -> None:
        assert _scan_text_source("# src/x.py:12\n", "t.txt") == []

    def test_permits_content_shaped_entry(self) -> None:
        assert _scan_text_source("src/x.py::main::if sys . platform ==\n", "t.txt") == []

    def test_entry_lines_skip_blank_and_comment(self) -> None:
        assert _text_entry_lines("# c\n\n  a.py:1  \n") == [(3, "a.py:1")]


class TestSymbolAttribution:
    def test_call_arg_sink_symbol_is_enclosing_binding(self) -> None:
        violations = _scan_python_source("_SEED = composite_key(source, 347)\n", "scratch/s.py")
        assert [(v.symbol, v.site) for v in violations] == [("_SEED", "composite_key(source, 347)")]

    def test_function_symbol(self) -> None:
        violations = _scan_python_source("def f(source):\n    return composite_key(source, 3)\n", "scratch/s.py")
        assert [v.symbol for v in violations] == ["f"]

    def test_bare_module_statement_symbol(self) -> None:
        violations = _scan_python_source("composite_key(source, 3)\n", "scratch/s.py")
        assert [v.symbol for v in violations] == ["<module>"]

    def test_class_level_non_assign_symbol(self) -> None:
        index = _enclosing_symbol_index(ast.parse("class K:\n    composite_key(source, 3)\n"))
        assert set(index.values()) == {"K"}

    def test_laundering_symbol_is_enclosing_binding(self) -> None:
        planted = '_SITES = (("a", 42),)\n_ALLOWLIST = {composite_key_from_file(rel, line) for rel, line in _SITES}\n'
        violations = _scan_python_source(planted, "scratch/s.py")
        assert [v.symbol for v in violations if "laundered" in v.detail] == ["_ALLOWLIST"]


class TestExemptionMultiset:
    def _finding(self) -> LineSinkViolation:
        return LineSinkViolation("t/a.py", 1, "d", "_SEED", "('a.py', 3)")

    def test_one_row_suppresses_exactly_one_identical_finding(self) -> None:
        rows = frozenset({("t/a.py", "_SEED", "('a.py', 3)", "reason")})
        unexpected = _unexempted([self._finding(), self._finding()], rows)
        assert unexpected == [self._finding()]

    def test_lineno_does_not_participate(self) -> None:
        rows = frozenset({("t/a.py", "_SEED", "('a.py', 3)", "reason")})
        moved = LineSinkViolation("t/a.py", 999, "d", "_SEED", "('a.py', 3)")
        assert _unexempted([moved], rows) == []

    def test_stale_row_reported(self) -> None:
        rows = frozenset({("t/a.py", "_SEED", "('a.py', 3)", "reason")})
        assert _stale_exemption_rows([], rows) == [("t/a.py", "_SEED", "('a.py', 3)")]

    def test_partition_reports_unexpected_and_stale_together(self) -> None:
        rows = frozenset({("t/a.py", "_OTHER", "('b.py', 4)", "reason")})
        unexpected, stale = _partition_exemptions([self._finding()], rows)
        assert unexpected == [self._finding()]
        assert stale == [("t/a.py", "_OTHER", "('b.py', 4)")]


class TestYamlIntFieldViolations:
    def test_flags_int_in_disallowed_field(self) -> None:
        doc = {"canonicalizer": [{"qualname": "foo", "occurrence": 2}]}
        violations = _yaml_int_field_violations(doc)
        assert len(violations) == 1
        assert "occurrence" in violations[0]

    def test_permits_line_field(self) -> None:
        doc = {"canonicalizer": [{"qualname": "foo", "line": 453}]}
        assert _yaml_int_field_violations(doc) == []

    def test_permits_count_field(self) -> None:
        doc = {"canonicalizer": [{"qualname": "foo", "count": 2}]}
        assert _yaml_int_field_violations(doc) == []

    def test_permits_baseline_suffixed_field(self) -> None:
        doc = {"canonicalizer_baseline": 3, "coord_authority_baseline": 4}
        assert _yaml_int_field_violations(doc) == []

    def test_permits_non_int_qualname_and_token(self) -> None:
        doc = {"qualname": "foo", "token": "bar ( baz )", "issue": "#2477"}
        assert _yaml_int_field_violations(doc) == []

    def test_flags_nested_list_entries(self) -> None:
        doc = [{"file": "a.py", "line_anchor": 99}]
        violations = _yaml_int_field_violations(doc)
        assert len(violations) == 1
        assert "line_anchor" in violations[0]


# ---------------------------------------------------------------------------
# T024 — non-vacuity (FR-013): plant-and-catch self-test.
# ---------------------------------------------------------------------------


def test_non_vacuity_plants_int_line_sink_and_reds() -> None:
    """A scratch authoritative seed carrying an int-to-line-sink call arg
    is FLAGGED — proving the composite_key(...) arm actually bites and this
    guard is not a vacuous always-pass.
    """
    planted = "from tests.architectural._ratchet_keys import composite_key\n\n_SEED = composite_key(source, 347)\n"
    violations = _scan_python_source(planted, "scratch/planted_seed.py")
    assert violations, "planted int-to-line-sink must be flagged (non-vacuity)"
    assert violations[0].lineno == 3


def test_non_vacuity_plants_tokens_by_line_index_and_reds() -> None:
    """The ``code_tokens_by_line(...)`` subscript arm also bites on a plant."""
    planted = "_TOKEN = code_tokens_by_line(source)[91]\n"
    violations = _scan_python_source(planted, "scratch/planted_index.py")
    assert violations, "planted tokens-by-line index sink must be flagged"


def test_non_vacuity_plants_seed_string_anchor_and_reds() -> None:
    """The module-level seed-string arm bites on a planted ``path:NNN`` seed."""
    planted = '_SEED: tuple[str, ...] = ("src/specify_cli/foo.py:91",)\n'
    violations = _scan_python_source(planted, "scratch/planted_string_seed.py")
    assert violations, "planted path:NNN seed string must be flagged"


def test_non_vacuity_escape_hatch_opts_out() -> None:
    """The ``# diagnostic-locator`` marker suppresses a planted finding —
    proving the escape hatch is live, not decorative.
    """
    planted = "from tests.architectural._ratchet_keys import composite_key\n\n_SEED = composite_key(source, 347)  # diagnostic-locator\n"
    assert _scan_python_source(planted, "scratch/escaped_seed.py") == []


def test_non_vacuity_plants_laundered_seed_tuple_and_reds() -> None:
    """T024/T025 (#2564) -- the seed-tuple-laundering arm bites on a plant.

    Mirrors the EXACT pre-conversion ``test_trio_seam_only._IO_ALLOWLIST_SITES``
    shape: a module-level tuple of ``(rel, int, rationale)`` rows, unpacked by a
    dict-comprehension clause into ``composite_key_from_file(rel, line)``'s 2nd
    positional arg via the ``line`` loop variable. Neither existing predicate
    sees this: the 2nd arg is an ``ast.Name`` (not a bare int literal, so
    :func:`_is_composite_key_line_arg` misses it), and the seed spans multiple
    source lines (so the ``file.py:NNN`` grep misses it too).
    """
    planted = (
        "from tests.architectural._ratchet_keys import composite_key_from_file\n\n"
        "_SEED_SITES = (\n"
        '    ("a.py", 42, "rationale one"),\n'
        '    ("b.py", 91, "rationale two"),\n'
        ")\n\n"
        "_ALLOWLIST = {\n"
        "    composite_key_from_file(rel, line): rationale\n"
        "    for rel, line, rationale in _SEED_SITES\n"
        "}\n"
    )
    violations = _scan_python_source(planted, "scratch/planted_laundered_seed.py")
    assert violations, "planted laundered seed-tuple must be flagged (#2564 non-vacuity)"
    assert "laundered" in violations[0].detail
    assert "line" in violations[0].detail


def test_non_vacuity_laundering_arm_permits_live_line_comprehension() -> None:
    """Paired negative (T025): a comprehension iterating the SAME shaped,
    int-carrying seed row does NOT trip the laundering arm when the sink's 2nd
    arg is a genuine live-line expression (not a bare reference to the
    unpacked int loop variable) -- no false positive on a legitimate
    content-addressed comprehension that merely shares the seed's row shape.
    """
    compliant = (
        "from tests.architectural._ratchet_keys import composite_key_from_file\n\n"
        "_SEED_SITES = (\n"
        '    ("a.py", 42, "rationale one"),\n'
        ")\n\n"
        "_ALLOWLIST = {\n"
        "    composite_key_from_file(rel, resolve_live_line(rel)): rationale\n"
        "    for rel, line, rationale in _SEED_SITES\n"
        "}\n"
    )
    violations = _scan_python_source(compliant, "scratch/live_line_comprehension.py")
    assert [v for v in violations if "laundered" in v.detail] == []
    # #5085: the widened tuple arm now flags the seed ROW itself (a
    # ``(path, int, ...)`` tuple) — that is the tuple arm, not the laundering arm.
    assert [v.site for v in violations] == ["('a.py', 42, 'rationale one')"]


def test_non_vacuity_compliant_snippet_stays_green() -> None:
    """A compliant, content-addressed seed (variable 2nd arg, no bare
    ``path:NNN`` string) stays GREEN — the guard does not over-fire.
    """
    compliant = "from tests.architectural._ratchet_keys import composite_key\n\ndef resolve(source, lineno):\n    return composite_key(source, lineno)\n"
    assert _scan_python_source(compliant, "scratch/compliant_seed.py") == []


# ---------------------------------------------------------------------------
# CT7 (#2853) — raw ``(path, line)`` 2-tuple ratchet-key ban: three directions.
# ---------------------------------------------------------------------------


def test_ct7_raw_file_line_tuple_seed_is_flagged() -> None:
    """RED (direction 1): a raw ``("some_file.py", 472)`` 2-tuple used as a
    ratchet key in a substrate-importing file IS flagged — the file:line-drift
    regression CT7 bans.
    """
    planted = 'from tests.architectural._ratchet_keys import composite_key\n\n_ALLOWLIST = {\n    ("some_file.py", 472): "rationale",\n}\n'
    violations = _scan_python_source(planted, "scratch/planted_raw_tuple.py")
    assert violations, "planted raw (path, line) 2-tuple ratchet key must be flagged (CT7)"
    assert "raw (path, line) 2-tuple" in violations[0].detail
    assert "some_file.py" in violations[0].detail


def test_ct7_content_descriptor_form_stays_green() -> None:
    """GREEN (direction 2): the SAME allow-list entry expressed via
    ``ContentDescriptor`` (content-addressed, not a raw ``(path, int)`` tuple)
    passes — proving the arm rewards the migrated form.
    """
    compliant = (
        "from tests.architectural._ratchet_keys import ContentDescriptor\n\n"
        "_ALLOWLIST: tuple[ContentDescriptor, ...] = (\n"
        "    ContentDescriptor(\n"
        '        rel_path="some_file.py",\n'
        '        qualname="mod.fn",\n'
        '        token_substring="offending_token",\n'
        "        occurrence=None,\n"
        '        rationale="rationale",\n'
        "    ),\n"
        ")\n"
    )
    assert _scan_python_source(compliant, "scratch/content_descriptor_seed.py") == []


def test_ct7_raw_tuple_in_non_substrate_file_is_flagged() -> None:
    """#5085 inversion of the former ``..._stays_green``: the identically-shaped
    raw ``(path, int)`` 2-tuple in a file that imports NO ratchet substrate is
    now IN scope — the exact shape of the #3206 doctrine-import-lineno
    exemption. Both tuples are flagged.
    """
    non_substrate = (
        "import ast\n"
        "from pathlib import Path\n\n"
        "_PRE_EXISTING_EXEMPTIONS = frozenset(\n"
        "    {\n"
        '        ("kernel/schema_utils.py", 88),\n'
        '        ("kernel/schema_utils.py", 96),\n'
        "    }\n"
        ")\n"
    )
    violations = _scan_python_source(non_substrate, "scratch/import_lineno_gate.py")
    assert len(violations) == 2
    assert {v.symbol for v in violations} == {"_PRE_EXISTING_EXEMPTIONS"}


def test_real_kernel_gate_has_no_unexempted_line_pin() -> None:
    """#3206 pointed regression pin: the REAL ``test_kernel_no_doctrine_import.py``
    (whose ``(path, lineno)`` exemptions were the original CT7 target, migrated
    to ContentDescriptors by WP03) produces no finding the pinned-empty
    :data:`_POSITIONAL_ANCHOR_EXEMPTIONS` leaves unexpected.

    The whole-universe gate above already covers this file; this test adds a
    named failure for the #3206 site and fails if the kernel gate moves.
    """
    kernel_gate = _ARCH_ROOT / "test_kernel_no_doctrine_import.py"
    assert kernel_gate.exists(), "the #3206 import-lineno gate moved — repoint this test"
    findings = _scan_python_file(kernel_gate)
    assert _unexempted(findings, _POSITIONAL_ANCHOR_EXEMPTIONS) == []


def test_ct7_escape_hatch_opts_out_raw_tuple() -> None:
    """The ``# diagnostic-locator`` marker suppresses a raw-tuple finding too —
    a genuinely non-anchor ``(path, int)`` pair can opt out explicitly rather
    than forcing the predicate to grow a special case.
    """
    planted = 'from tests.architectural._ratchet_keys import composite_key\n\n_ALLOWLIST = {\n    ("some_file.py", 472): "rationale",  # diagnostic-locator\n}\n'
    assert _scan_python_source(planted, "scratch/escaped_raw_tuple.py") == []


# ---------------------------------------------------------------------------
# #5085 (FR-001) — planted fixtures for the widened arms, each through the
# functions the standing gates call (_scan_python_source / _scan_text_source).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("planted", "symbol"),
    [
        pytest.param('from pathlib import Path\n_SEED = ((Path("src/a.py"), 12),)\n', "_SEED", id="path-constructor"),
        pytest.param('from pathlib import Path\n_SEED = ((Path("a") / "b.py", 12),)\n', "_SEED", id="div-join"),
        pytest.param('class K:\n    ALLOW = (("a.py", 3),)\n', "K.ALLOW", id="class-attribute"),
        pytest.param('_SEED = (Entry(path="a.py", lineno=3),)\n', "_SEED", id="keyword-record"),
        pytest.param('_ALLOWLIST = {"src/x.py:98:reset_hard": "r"}\n', "_ALLOWLIST", id="census-key"),
        pytest.param('_SEED = (("a.py", "mod.f", 3),)\n', "_SEED", id="path-qualname-int"),
    ],
)
def test_widened_python_arm_flags_planted_site(planted: str, symbol: str) -> None:
    violations = _scan_python_source(planted, "scratch/planted.py")
    assert len(violations) == 1, violations
    assert violations[0].symbol == symbol
    assert violations[0].site


def test_widened_text_arm_flags_planted_call_line() -> None:
    violations = _scan_text_source("# header\nIMPORT:src/y.py\nCALL:src/x.py:12\n", "tests/architectural/_exemptions/t.txt")
    assert [(v.symbol, v.site, v.lineno) for v in violations] == [("t.txt", "CALL:src/x.py:12", 3)]


@pytest.mark.parametrize(
    "compliant",
    [
        pytest.param('_SEED = (("label", 3),)\n', id="label-int"),
        pytest.param('_CMDS = {"cmd": "decision.py:401; empty stdout"}\n', id="prose-evidence"),
        pytest.param(
            '_SEED = (ContentDescriptor(rel_path="a.py", qualname="f", token_substring="x", occurrence=0, rationale="r"),)\n',
            id="content-descriptor",
        ),
        pytest.param('_SEED = (CensusKey(rel="a.py", qualname="f", token_line="x", op="o", op_ordinal=1),)\n', id="census-key-ordinal"),
        pytest.param('_COUNTS = {"tests/x.py": 3}\n', id="path-count-dict"),
        pytest.param('_COUNTS: dict[str, dict[str, int]] = {"tests/x.py": {"test_a": 3}}\n', id="nested-count-dict"),
        pytest.param('def f():\n    seed = (("a.py", 3),)\n    return seed\n', id="function-local"),
        pytest.param('_SEED = ("src/a.py::f::reset_hard#0",)\n', id="qualname-content-key"),
    ],
)
def test_widened_arms_leave_out_of_scope_shapes_green(compliant: str) -> None:
    assert _scan_python_source(compliant, "scratch/compliant.py") == []


def test_overlapping_arms_report_one_finding_per_site() -> None:
    """``"src/x.py:12"`` is caught by BOTH the registry-parity string arm and the
    embedded-key arm; it is reported once (per site, not per arm)."""
    violations = _scan_python_source('_SEED = ("src/x.py:12",)\n', "scratch/overlap.py")
    assert len(violations) == 1


# ---------------------------------------------------------------------------
# #5085 NFR-002 — per-arm self-mutation: disable one arm's predicate and the
# arm-EXCLUSIVE planted fixture must drop to exactly 0 findings, proving the
# production scan path (_scan_python_source / _scan_text_source) uses that arm.
# ---------------------------------------------------------------------------

_THIS_MODULE = sys.modules[__name__]


def _never(*_args: object) -> bool:
    return False


def test_arm_disable_file_line_tuple(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exclusive fixture: ``(Path("src/a.py"), 12)`` — no string / keyword arm
    sees it. (Overlap note: a plain ``("a.py:1", ...)`` string would ALSO hit
    the two string arms, so it is not used here.)"""
    planted = 'from pathlib import Path\n_SEED = ((Path("src/a.py"), 12),)\n'
    assert len(_scan_python_source(planted, "scratch/t.py")) == 1
    monkeypatch.setattr(_THIS_MODULE, "_is_file_line_tuple", _never)
    assert _scan_python_source(planted, "scratch/t.py") == []


def test_arm_disable_embedded_line_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exclusive fixture: ``"src/x.py:98:reset_hard"`` — the registry-parity
    :func:`is_file_line_anchor` arm needs a trailing ``:<int>`` and misses it.
    (Overlap note: ``"src/x.py:12"`` is caught by BOTH string arms.)"""
    planted = '_ALLOWLIST = {"src/x.py:98:reset_hard": "r"}\n'
    assert len(_scan_python_source(planted, "scratch/t.py")) == 1
    monkeypatch.setattr(_THIS_MODULE, "_is_embedded_line_key", _never)
    assert _scan_python_source(planted, "scratch/t.py") == []


def test_arm_disable_keyword_record(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exclusive fixture: ``Entry(path="a.py", lineno=3)`` — not a tuple, and no
    string constant in it is a line key."""
    planted = '_SEED = (Entry(path="a.py", lineno=3),)\n'
    assert len(_scan_python_source(planted, "scratch/t.py")) == 1
    monkeypatch.setattr(_THIS_MODULE, "_is_line_keyword_record", _never)
    assert _scan_python_source(planted, "scratch/t.py") == []


def test_arm_disable_class_body_walk(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exclusive fixture: a class-attribute allow-list — reachable ONLY through
    the class-body walk (the tuple arm is what flags it once walked)."""
    planted = 'class K:\n    ALLOW = (("a.py", 3),)\n'
    assert len(_scan_python_source(planted, "scratch/t.py")) == 1
    monkeypatch.setattr(_THIS_MODULE, "_class_body_scopes", lambda _tree: [])
    assert _scan_python_source(planted, "scratch/t.py") == []


def test_arm_disable_text_line_anchor(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exclusive fixture: a ``CALL:<path>:<line>`` exemption text line — only
    the text arm reads ``.txt`` files."""
    planted = "CALL:src/x.py:12\n"
    assert len(_scan_text_source(planted, "t.txt")) == 1
    monkeypatch.setattr(_THIS_MODULE, "_is_text_line_anchor", _never)
    assert _scan_text_source(planted, "t.txt") == []


def test_non_vacuity_real_compliant_yamls_stay_green() -> None:
    """Every real, WS1-compliant YAML in :data:`_YAML_ALLOWLISTS` (``line:``
    locators + count-floor baselines only) stays GREEN through the actual YAML predicate — the
    authoritative-vs-diagnostic distinction the contract requires.
    """
    assert len(_YAML_ALLOWLISTS) >= 1, "the YAML arm scans no allow-list (vacuous)"
    for name in _YAML_ALLOWLISTS:
        doc = yaml.safe_load((_ARCH_ROOT / name).read_text(encoding="utf-8"))
        assert _yaml_int_field_violations(doc) == [], f"{name} unexpectedly failed the compliant-YAML non-vacuity check"


# ---------------------------------------------------------------------------
# T027 -- #2564 non-fakeable DoD: the real converted launderer stays closed.
#
# Part (a), "the extended ban run against the UNCONVERTED _IO_ALLOWLIST_SITES
# MUST FAIL", is proven by test_non_vacuity_plants_laundered_seed_tuple_and_reds
# above: that fixture reproduces the EXACT pre-conversion shape (a raw
# ``(rel, int, rationale)`` tuple unpacked by a dict-comprehension clause into
# ``composite_key_from_file``'s 2nd arg) and asserts the ban flags it. Part
# (b), the structural positive proof, is below: the real, POST-conversion
# ``test_trio_seam_only._IO_ALLOWLIST_SITES`` no longer carries a bare int
# anywhere in its row shape. Part (c) is the ordinary green-on-real-tree run
# of this file (``test_no_int_line_sink_in_architectural_python_seeds``
# scans every tests/architectural/**/*.py file, including
# test_trio_seam_only.py).
# ---------------------------------------------------------------------------


def test_io_allowlist_sites_carry_no_bare_int_element() -> None:
    """Structural proof (#2564 T027): every ``_IO_ALLOWLIST_SITES`` row is
    content-addressed (``ContentDescriptor`` — rel_path/qualname/token_substring
    /occurrence/rationale) with NO bare int line-number member anywhere in its
    shape. Booleans are ``int`` subclasses in Python but are never a
    line-number, so they are excluded from the check.
    """
    from tests.architectural.test_trio_seam_only import _IO_ALLOWLIST_SITES

    assert _IO_ALLOWLIST_SITES, "the real _IO_ALLOWLIST_SITES must be non-empty"
    offenders = [(entry, field) for entry in _IO_ALLOWLIST_SITES for field in entry if isinstance(field, int) and not isinstance(field, bool)]
    assert not offenders, f"_IO_ALLOWLIST_SITES still carries a bare int line-number member — the #2564 seed-tuple laundering hole is not closed: {offenders!r}"
