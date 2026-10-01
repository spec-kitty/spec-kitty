"""IC-KEY — relocation-tolerant ``SymbolKey`` resolver + live collision classifier.

Mission: ``relocation-hardened-dead-code-scanners-01KX958P``, WP01 (keystone).
Consumed by ``test_no_dead_symbols.py`` (WP02/WP-REKEY) for live keyability
classification and auto-exempt condition (1), via a relocation-tolerant
runtime identity. The persisted dead-symbol allow-list
(``dead_symbol_allowlist.yaml``) keys its entries by ``(module, name)``
(schema: ``_dead_symbol_allowlist.py``, contract:
``contracts/dead-symbol-allowlist.md``, IC-12) — this module's key is
runtime-only and does not re-key that allow-list. See
``kitty-specs/relocation-hardened-dead-code-scanners-01KX958P/``
(spec.md FR-001..005/009, plan.md IC-KEY, research.md D-1..D-6,
contracts/symbol-key-resolver.md) for the full design record.

.. warning::
   **Test-infra scaffolding, NOT a src/ module.** ``_``-prefixed, non-collected
   by pytest, and lives under ``tests/architectural/`` exactly like
   ``_ratchet_keys.py``: a ``src/`` module imported only by tests would RED
   ``test_no_dead_modules`` (zero non-test callers). This module lifted the
   proven ``ClassDef``/``FunctionDef`` logic from the retired WP06 spike
   (``_symbol_identity.py``, deleted once this resolver and
   ``tests/unit/test_symbol_key.py`` covered the same contract) and fixes its
   gaps: the spike's ``definition_span`` had NO ``AnnAssign`` branch and hashed
   the *whole* ``ImportFrom`` statement. This module carries its own stability
   proofs (spec.md Assumptions).

Honest downscope (C-001, load-bearing)
---------------------------------------
There is no single correct key tier. A pure-content key ``(bare_name,
body_hash)`` re-blinds the T004 no-false-negative invariant for byte-identical
same-name re-exports (the ``ArtifactKind`` trio: ``charter.offering.directives`` /
``charter.offering.procedures`` / ``charter.offering.tactics`` each do
``from charter.offering.artifact_kinds import ArtifactKind``). A module_path-bearing
key forfeits relocation tolerance for every entry that carries it. This module
therefore implements a **two-tier, live-classified** key (D-1):

* **content tier** (default): ``(bare_name, body_hash)``, relocation-proof.
* **module_path tier** (escalated only for a *live* collision — D-2/D-3):
  ``(bare_name, module_path, body_hash)``, relocation-FORFEIT for that entry
  (documented, not a bug — spec.md's downscope table).
* **fail-closed** (``None``): the resolver could not span the shape, or the
  content key resolves to a collision it cannot disambiguate via
  ``module_path`` either. Never silently exempted (FR-009 / D-3 /
  [[no_legacy_resolver_paths]]).

The collision set is **recomputed on every call to** :func:`classify_collisions`
— it is NOT a frozen authoring-time split (D-2). Today's collision set is
exactly the ``ArtifactKind`` trio, but nothing here hard-codes that; a future
byte-identical same-name pair is caught automatically because the index is
rebuilt from the live corpus each run.

Body-sensitivity (deliberate, tested)
--------------------------------------
Because the content-tier key hashes the symbol's own body text, **editing a
dead symbol's body changes its runtime content key**. No persisted
allow-list entry depends on that key — the allow-list is keyed by
``(module, name)`` — so a body edit costs 0 allow-list edits (FR-009 /
SC-003), not the price this module used to describe.
"""

from __future__ import annotations

import ast
import hashlib
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from specify_cli.ast_analysis.imports import extract_static_all
from specify_cli.contracts.anchoring import code_tokens_by_line

__all__ = [
    "CorpusModule",
    "Location",
    "SymbolKey",
    "alias_body_hash",
    "bind_call_accessor_aliases",
    "body_hash",
    "classify_collisions",
    "definition_span",
    "find_module_factory_functions",
    "key_tier",
    "perf_budget_seconds",
    "record_call_chain_attr_edges",
    "resolve_symbol_key",
    "timed_classify_collisions",
    "unresolved_reason",
]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SymbolKey:
    """The relocation-tolerant, runtime-only identity for one ``__all__``-declared symbol.

    ``module_path is None`` -> content tier (default, relocation-proof).
    ``module_path`` set -> escalated module_path tier (collision-safe,
    relocation-forfeit for this entry only — D-1).

    This key serves live keyability (:func:`resolve_symbol_key`), collision
    classification (:func:`classify_collisions`) and auto-exempt condition (1)
    in ``test_no_dead_symbols.py``. It carries no persisted provenance: the
    dead-symbol allow-list identifies an entry by ``(module, name)`` in
    ``dead_symbol_allowlist.yaml`` and never stores a body hash.
    """

    bare_name: str
    body_hash: str
    module_path: str | None = None

    @property
    def is_content_tier(self) -> bool:
        return self.module_path is None

    def as_tuple(self) -> tuple[str, str] | tuple[str, str, str]:
        """The allow-list-serializable shape: 2-tuple (content) or 3-tuple (escalated)."""
        if self.module_path is None:
            return (self.bare_name, self.body_hash)
        return (self.bare_name, self.module_path, self.body_hash)


@dataclass(frozen=True)
class Location:
    """One live ``__all__`` declaration site, as seen by :func:`classify_collisions`."""

    module_path: str
    bare_name: str
    body_hash: str


@dataclass(frozen=True)
class CorpusModule:
    """One ``src/`` module's parsed tree + source + containing package.

    ``containing_pkg`` follows the exact semantics the gate's ``_package_of``
    uses for relative-import resolution: for a plain module
    ``specify_cli/runtime/bootstrap.py`` it is ``"specify_cli.runtime"``; for
    a package ``__init__.py`` (e.g. ``specify_cli/sync/__init__.py``, whose
    OWN dotted ``module_path`` is already ``"specify_cli.sync"``) it is
    likewise ``"specify_cli.sync"``. The two are NOT interchangeable and are
    supplied explicitly by the caller rather than derived from
    ``module_path`` via a ``rsplit(".", 1)`` heuristic — that heuristic is
    WRONG for ``__init__.py`` facades, which is exactly where both real
    facade dicts (``sync._LAZY_IMPORTS`` / ``runtime._EXPORT_MODULES``) live.
    """

    tree: ast.Module
    source: str
    containing_pkg: str


# ---------------------------------------------------------------------------
# T001 — body-hash normalizer + definition_span (Class/Func/Assign)
# T002 — AnnAssign branch (FR-002, HIGHEST priority)
# ---------------------------------------------------------------------------


def definition_span(tree: ast.Module, bare_name: str) -> tuple[int, int] | None:
    """Return the top-level ``(start_line, end_line)`` binding ``bare_name``.

    Handles ``ClassDef`` / ``FunctionDef`` / ``AsyncFunctionDef`` (lifted from
    the WP06 spike), a plain module-level ``Assign`` (lifted), and
    ``AnnAssign`` (T002 — the ``CACHE_PATH: Path = ...`` / ``TTL_SECONDS: int
    = 3600`` typed-constant shape the spike does not handle; without this
    branch those <=14 entries are un-keyable and re-introduce the T001 bug
    the gate side already fixed).

    Deliberately does NOT handle ``Import`` / ``ImportFrom`` — those are
    single-alias-scoped by :func:`_find_import_alias` instead (T004); a
    whole-statement span here would sibling-contaminate multi-target imports.
    """
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == bare_name:
                return (node.lineno, node.end_lineno or node.lineno)
            continue
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == bare_name:
                    return (node.lineno, node.end_lineno or node.lineno)
            continue
        if isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == bare_name:
                return (node.lineno, node.end_lineno or node.lineno)
            continue
    return None


def _hash_text(normalized: str) -> str:
    # noqa justification (TID251 / Gap 3): this is a body-checksum use case,
    # not charter content — charter.hasher.hash_content() is charter-markdown
    # specific (BOM/CRLF normalization, "sha256:" prefix format) and is the
    # wrong domain for a source-code token-span digest. TID251's own message
    # names "body checksums" as a sanctioned non-charter exception. Mirrors
    # the identical, reviewed rationale of the retired WP06 spike.
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()  # noqa: TID251


def body_hash(source: str, span: tuple[int, int]) -> str:
    """Hash the normalized token lines of ``span`` in ``source``.

    Reuses ``anchoring.code_tokens_by_line`` (interpreter-independent,
    3.11<->3.12 PEP 701 f-string parity already proven there) rather than
    forking a second normalizer (S3776 / canonical-source discipline).
    """
    start, end = span
    tokens_by_line = code_tokens_by_line(source)
    ordered = [tokens_by_line[ln] for ln in range(start, end + 1) if ln in tokens_by_line]
    return _hash_text("\n".join(ordered))


# ---------------------------------------------------------------------------
# T004 — single-alias ImportFrom/Import hash (FR-004)
# ---------------------------------------------------------------------------


def _find_import_alias(tree: ast.Module, bare_name: str) -> ast.alias | None:
    """Locate the single ``ast.alias`` binding ``bare_name`` at module scope.

    Covers ``import X as Name`` / ``from M import X as Name`` / bare
    ``from M import Name``. Returns the ``alias`` node itself (not the
    enclosing ``Import``/``ImportFrom`` statement) so the caller can scope
    the hash to just this alias's own source columns (T004) rather than the
    whole statement — a multi-target import's siblings must never
    contaminate this alias's identity (FR-004 acceptance).
    """
    for node in tree.body:
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for alias in node.names:
            if alias.name == "*":
                continue
            bound = alias.asname or alias.name.split(".")[-1]
            if bound == bare_name:
                return alias
    return None


def _alias_source_text(source: str, alias: ast.alias) -> str:
    """The exact source substring covering only this one alias.

    ``ast.alias`` carries its own ``lineno``/``col_offset``/``end_lineno``/
    ``end_col_offset`` (stable since Python 3.10), so — even for a same-line
    multi-target import (``from M import A, B, C``) — this slices out only
    ``B``'s own columns, never a sibling's text.
    """
    lines = source.splitlines()
    end_lineno = alias.end_lineno or alias.lineno
    if alias.lineno == end_lineno and alias.end_col_offset is not None:
        return lines[alias.lineno - 1][alias.col_offset : alias.end_col_offset]
    # Defensive fallback for an alias spanning multiple physical lines (not
    # observed in practice for a bare name/asname pair, but the column info
    # is optional per the ast grammar) — join the covered whole lines;
    # code_tokens_by_line's normalization still absorbs incidental whitespace.
    return "\n".join(lines[alias.lineno - 1 : end_lineno])


def alias_body_hash(source: str, alias: ast.alias) -> str:
    """Body-hash scoped to a SINGLE ``ImportFrom``/``Import`` alias (T004).

    Reuses ``code_tokens_by_line`` on the alias's own sliced text (not the
    whole statement) — this is what makes it immune to sibling edits.
    """
    text = _alias_source_text(source, alias)
    tokens_by_line = code_tokens_by_line(text)
    ordered = [tokens_by_line[ln] for ln in sorted(tokens_by_line)]
    return _hash_text("\n".join(ordered))


# ---------------------------------------------------------------------------
# T003 — facade-dict KEY-side resolver, by shape (FR-003, rescoped)
# ---------------------------------------------------------------------------


def _assign_targets_and_value(
    node: ast.stmt,
) -> tuple[list[ast.expr], ast.expr | None] | tuple[None, None]:
    """Normalize ``Assign``/``AnnAssign`` into ``(targets, value)`` or ``(None, None)``."""
    if isinstance(node, ast.Assign):
        targets: list[ast.expr] = list(node.targets)
        return targets, node.value
    if isinstance(node, ast.AnnAssign):
        ann_targets: list[ast.expr] = [node.target]
        return ann_targets, node.value
    return None, None


def _extract_str_consts(tree: ast.Module) -> dict[str, str]:
    """Top-level ``NAME = "string"`` (or typed ``AnnAssign``) constants.

    Re-derived (not imported) per T003's KEY-side instruction — small,
    top-level-only, and independent of the gate's caller-graph-shaped
    ``_extract_str_consts_from_body`` (which is not one of the two pure
    helpers this module is pinned to reuse).
    """
    consts: dict[str, str] = {}
    for node in tree.body:
        targets, value = _assign_targets_and_value(node)
        if targets is None or not (isinstance(value, ast.Constant) and isinstance(value.value, str)):
            continue
        for tgt in targets:
            if isinstance(tgt, ast.Name):
                consts[tgt.id] = value.value
    return consts


def _find_dict_assign(tree: ast.Module, dict_name: str) -> ast.Dict | None:
    for node in tree.body:
        targets, value = _assign_targets_and_value(node)
        if targets is None:
            continue
        if any(isinstance(t, ast.Name) and t.id == dict_name for t in targets) and isinstance(
            value, ast.Dict
        ):
            return value
    return None


def _resolve_str_const(expr: ast.expr, str_consts: dict[str, str]) -> str | None:
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return expr.value
    if isinstance(expr, ast.Name) and expr.id in str_consts:
        return str_consts[expr.id]
    return None


def _facade_target(val_expr: ast.expr, bare_name: str, str_consts: dict[str, str]) -> tuple[str, str] | None:
    """Parse ONE dict value by shape: 2-tuple ``(module, attr)`` or 1-value ``module``.

    * sync-style ``_LAZY_IMPORTS`` -> ``{name: (module, attr)}`` (2-tuple):
      ``attr`` is the literal string in the tuple (may differ from the dict
      key / bound local name).
    * runtime-style ``_EXPORT_MODULES`` -> ``{name: module_const}`` (1-value,
      the gate's ``_record_facade_edges`` guard ``len != 2: continue`` skips
      this shape entirely — the 6 ``specify_cli.runtime::*`` entries): the
      attribute IS the dict key / bound name (``getattr(module, name)``).
    """
    if isinstance(val_expr, (ast.Tuple, ast.List)) and len(val_expr.elts) == 2:
        mod_expr, attr_expr = val_expr.elts
        if not (isinstance(attr_expr, ast.Constant) and isinstance(attr_expr.value, str)):
            return None
        attr = attr_expr.value
    elif isinstance(val_expr, (ast.Constant, ast.Name)):
        mod_expr = val_expr
        attr = bare_name
    else:
        return None
    mod_path = _resolve_str_const(mod_expr, str_consts)
    if mod_path is None:
        return None
    return (mod_path, attr)


def _lookup_facade_dict(
    dict_node: ast.Dict,
    bare_name: str,
    str_consts: dict[str, str],
    containing_pkg: str,
    resolve_relative_module: Callable[[str, str], str],
) -> tuple[str, str] | None:
    # strict=True is safe: ast.Dict always parses keys/values as equal-length
    # lists (a dict literal cannot have a mismatched key/value count).
    for key_expr, val_expr in zip(dict_node.keys, dict_node.values, strict=True):
        if not (isinstance(key_expr, ast.Constant) and isinstance(key_expr.value, str)):
            continue
        if key_expr.value != bare_name:
            continue
        target = _facade_target(val_expr, bare_name, str_consts)
        if target is None:
            return None
        mod_path, attr = target
        return (resolve_relative_module(mod_path, containing_pkg), attr)
    return None


def _resolve_facade_entry(tree: ast.Module, containing_pkg: str, bare_name: str) -> tuple[str, str] | None:
    """Re-derived dict-parse KEY-side (FR-003) -> ``(resolved_module, attr)`` or ``None``.

    Reuses ONLY the two PURE helpers ``_find_facade_lazy_dict_name`` +
    ``_resolve_relative_module`` from the gate's ``test_no_dead_symbols.py``
    (LOW-5 pin — do not mutate their signatures). Deliberately does NOT
    reuse/edit ``_record_facade_edges`` (byte-frozen C-005, caller-graph-
    shaped, discards the name).

    ⚠️ Imported via a FUNCTION-LOCAL (deferred) import, not a top-level one:
    ``test_no_dead_symbols.py`` imports ``SymbolKey``/``classify_collisions``/
    ``key_tier`` from THIS module at ITS top level, so a top-level import of
    the gate module here would be circular at load time (post-tasks squad
    DEFECT 1). By the time this function is actually CALLED (never during
    either module's own import), both modules are already fully loaded.
    """
    from tests.architectural.test_no_dead_symbols import (
        _find_facade_lazy_dict_name,
        _resolve_relative_module,
    )

    dict_name = _find_facade_lazy_dict_name(tree)
    if dict_name is None:
        return None
    dict_node = _find_dict_assign(tree, dict_name)
    if dict_node is None:
        return None
    str_consts = _extract_str_consts(tree)
    return _lookup_facade_dict(dict_node, bare_name, str_consts, containing_pkg, _resolve_relative_module)


# ---------------------------------------------------------------------------
# T001+T002+T003+T004+T006 — the orchestrator
# ---------------------------------------------------------------------------


def resolve_symbol_key(
    bare_name: str,
    module_path: str,
    module: CorpusModule,
    corpus: Mapping[str, CorpusModule] | None = None,
    _seen: frozenset[str] | None = None,
) -> SymbolKey | None:
    """Resolve ``bare_name``'s content-tier :class:`SymbolKey` in ``module``.

    Tries, in order: a local definition/re-export binding (T001/T002), a
    single-alias import (T004), then a facade-dict export (T003 — requires
    ``corpus`` to locate and hash the REAL definition body at the resolved
    ``(module, attr)``; without a corpus, a facade entry cannot be verified
    and fails closed rather than guessed).

    Returns ``None`` (fail-closed, T006) for any shape this resolver cannot
    span. There is deliberately NO ``if key is None: <exempt>`` fallback here
    — callers must fail-close, never silently exempt
    ([[no_legacy_resolver_paths]]). Call :func:`unresolved_reason` for a
    human-readable explanation to surface alongside the ``None``.

    This always returns a CONTENT-tier key (``module_path=None``); escalation
    to the module_path tier is a separate, LIVE decision made by
    :func:`key_tier` against a :func:`classify_collisions` index (D-1/D-2).
    """
    span = definition_span(module.tree, bare_name)
    if span is not None:
        return SymbolKey(bare_name=bare_name, body_hash=body_hash(module.source, span))

    alias = _find_import_alias(module.tree, bare_name)
    if alias is not None:
        return SymbolKey(bare_name=bare_name, body_hash=alias_body_hash(module.source, alias))

    facade_target = _resolve_facade_entry(module.tree, module.containing_pkg, bare_name)
    if facade_target is None:
        return None
    resolved_module, attr = facade_target
    if corpus is None or resolved_module not in corpus:
        return None  # cannot verify the real body without the target module -> fail-closed
    marker = f"{module_path}::{bare_name}"
    seen = _seen or frozenset()
    if marker in seen:
        return None  # cyclical facade chain -> fail-closed, never loop
    inner = resolve_symbol_key(
        attr, resolved_module, corpus[resolved_module], corpus=corpus, _seen=seen | {marker}
    )
    if inner is None:
        return None
    return SymbolKey(bare_name=bare_name, body_hash=inner.body_hash)


def unresolved_reason(bare_name: str, module_path: str, module: CorpusModule) -> str:
    """A clear reason string for why ``resolve_symbol_key`` returned ``None``.

    Re-derives which shape-check failed so a fail-closed consumer (WP02) can
    surface a specific, actionable flag instead of a bare ``None`` (T006).
    Only meaningful to call after ``resolve_symbol_key`` already returned
    ``None`` for the same arguments.
    """
    facade_target = _resolve_facade_entry(module.tree, module.containing_pkg, bare_name)
    if facade_target is not None:
        resolved_module, attr = facade_target
        return (
            f"{bare_name!r} in {module_path!r}: facade dict resolves to "
            f"{resolved_module}::{attr}, but {resolved_module!r} is not present in the "
            "supplied corpus -- cannot verify the real body, fail-closed"
        )
    return (
        f"{bare_name!r} in {module_path!r}: no ClassDef/FunctionDef/AsyncFunctionDef/"
        "Assign/AnnAssign/ImportFrom binding found and no facade dict resolves it -- "
        "undecidable shape, fail-closed (never silently exempted)"
    )


# ---------------------------------------------------------------------------
# T005 — live collision classifier + key_tier (FR-005 + FR-009 >=2-escalation)
# ---------------------------------------------------------------------------


def classify_collisions(corpus: Mapping[str, CorpusModule]) -> dict[str, list[Location]]:
    """Build the ``bare_name -> [live __all__ locations]`` index for ONE run.

    Walks every module's ``__all__`` once (the corpus is assumed already
    parsed/cached by the caller — no new AST walk here, matching the plan's
    perf note). This is LIVE: call it fresh every gate invocation. It is NOT
    a frozen authoring-time split — a future byte-identical same-name pair
    is picked up automatically because the index is rebuilt from the current
    corpus, not hard-coded to today's ``ArtifactKind`` trio (D-2).
    """
    index: dict[str, list[Location]] = {}
    for module_path, module in corpus.items():
        names = extract_static_all(module.tree)
        if not names:
            continue
        for bare_name in names:
            key = resolve_symbol_key(bare_name, module_path, module, corpus=corpus)
            if key is None:
                continue
            index.setdefault(bare_name, []).append(
                Location(module_path=module_path, bare_name=bare_name, body_hash=key.body_hash)
            )
    return index


def key_tier(
    key: SymbolKey | None,
    module_path: str | None,
    index: Mapping[str, list[Location]],
) -> SymbolKey | None:
    """Decide the FINAL tier for ``key`` against the live collision ``index``.

    * ``key is None`` -> fail-closed (``None``) — T006.
    * ``bare_name`` resolves to exactly one live location sharing this
      ``body_hash`` -> content tier, unchanged (relocation-proof).
    * ``bare_name`` resolves to >=2 live locations sharing this ``body_hash``
      -> escalate to the module_path tier IF ``module_path`` uniquely
      disambiguates among the colliding locations, ELSE fail-closed
      (``None``) — never silently exempt (FR-005/FR-009/D-3).
    """
    if key is None:
        return None
    locations = index.get(key.bare_name, [])
    matches = [loc for loc in locations if loc.body_hash == key.body_hash]
    if len(matches) <= 1:
        return key
    if module_path is None:
        return None
    distinct_modules = {loc.module_path for loc in matches}
    if module_path not in distinct_modules or len(distinct_modules) < len(matches):
        # Either this entry's recorded location no longer participates in the
        # collision, or >=2 colliding locations share the SAME module_path
        # (module_path itself would not disambiguate) -> fail-closed.
        return None
    return SymbolKey(bare_name=key.bare_name, body_hash=key.body_hash, module_path=module_path)


# ---------------------------------------------------------------------------
# IC-01 -- first-party dynamic (call-bound) module-attr access (FR-001/FR-002,
# #2559, test-suite-friction-remediation-01KXDKBX WP01)
# ---------------------------------------------------------------------------
#
# The gate's plain-import module-attr detector (``_record_module_attr_edges``
# in ``test_no_dead_symbols.py``) only sees an alias bound by a STATIC
# ``import``/``from ... import ... as`` statement. A first-party module
# obtained from a local zero-arg factory function -- the
# ``_runtime_bridge_module()`` shape ("Return the patched bridge when
# tests/consumers installed one", `src/specify_cli/cli/commands/next_cmd.py`)
# -- is invisible to that walk: the module reference is bound to a NAME via a
# function CALL, not an import. The two helpers below resolve that shape
# generally (no reference to ``runtime_bridge`` anywhere in this module):
#
# 1. :func:`find_module_factory_functions` recognises a module-scope function
#    whose body resolves a KNOWN first-party module via a
#    ``importlib.import_module("<literal>")`` call (the accessor's own
#    control flow -- a ``sys.modules.get(...) or ...`` short-circuit, a cache
#    check, etc. -- is deliberately NOT pattern-matched, only the presence of
#    that resolvable call).
# 2. :func:`bind_call_accessor_aliases` covers the actual call-site shape used
#    in practice -- ``bridge = _runtime_bridge_module(); bridge.attr`` -- by
#    extending the SAME alias map the plain-import detector already consumes,
#    so ``bridge.attr`` is rescued by the existing ``_record_module_attr_edges``
#    walk with zero new attribute-matching logic.
# 3. :func:`record_call_chain_attr_edges` additionally covers the direct
#    ``factory().attr`` chain (no intermediate local) for completeness.
#
# Scope is deliberately narrow (anti-goal, contracts/dead-code-dynamic-access.md):
# this does NOT widen liveness to *any* attribute access -- only to attribute
# access on a name/call-chain that resolves, via a real ``import_module`` call,
# to a module already present in the corpus (``known_modules``), mirroring the
# no-false-negative guard the sibling detectors already enforce (T004).


def _is_import_module_call(node: ast.AST, alias_map: Mapping[str, str]) -> bool:
    """True iff *node* is a call shaped ``importlib.import_module(...)``.

    ``importlib`` is resolved through *alias_map* (a bare ``import importlib``
    is recorded there under its own name by the caller's alias-map builder),
    so an aliased import (``import importlib as il``) is recognised too.
    """
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "import_module"
        and isinstance(node.func.value, ast.Name)
        and alias_map.get(node.func.value.id) == "importlib"
    )


def _import_module_literal(call: ast.Call, str_consts: Mapping[str, str]) -> str | None:
    """The dotted module string passed as the first arg to an ``import_module(...)`` call."""
    if not call.args:
        return None
    arg = call.args[0]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    if isinstance(arg, ast.Name) and arg.id in str_consts:
        return str_consts[arg.id]
    return None


def find_module_factory_functions(
    tree: ast.Module,
    alias_map: Mapping[str, str],
    str_consts: Mapping[str, str],
    containing_pkg: str,
    known_modules: frozenset[str],
    resolve_relative_module: Callable[[str, str], str],
) -> dict[str, str]:
    """Map a local zero-arg 'module factory' function name to the first-party
    module dotted path it resolves at call time.

    Scoped to TOP-LEVEL function definitions only (the accessor is a
    module-scope helper, not a nested closure) and to modules already present
    in ``known_modules`` -- the same no-false-negative guard the plain-import
    detector relies on, so a typo'd or non-first-party literal cannot record
    a bogus edge.
    """
    factories: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for call in ast.walk(node):
            if not (isinstance(call, ast.Call) and _is_import_module_call(call, alias_map)):
                continue
            literal = _import_module_literal(call, str_consts)
            if literal is None:
                continue
            resolved = resolve_relative_module(literal, containing_pkg)
            if resolved in known_modules:
                factories[node.name] = resolved
            break
    return factories


def bind_call_accessor_aliases(
    tree: ast.Module,
    factories: Mapping[str, str],
) -> dict[str, str]:
    """Extend an alias map with locals bound from a recognised factory call.

    For every ``name = factory()`` (or annotated ``name: T = factory()``)
    assignment anywhere in the module where ``factory`` is a name in
    *factories* (see :func:`find_module_factory_functions`), maps
    ``name -> factories[factory]``. Merging the result into the alias map the
    plain-import module-attr detector already consumes means a call-bound
    local (``bridge = _runtime_bridge_module()``) is rescued by the SAME
    ``alias.attr`` walk as a real ``import module as alias`` binding -- no
    separate attribute-matching logic is needed for this shape.
    """
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        target: ast.expr | None = None
        value: ast.expr | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign):
            target, value = node.target, node.value
        if not (
            isinstance(target, ast.Name)
            and isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id in factories
        ):
            continue
        aliases[target.id] = factories[value.func.id]
    return aliases


def record_call_chain_attr_edges(
    tree: ast.Module,
    factories: Mapping[str, str],
    per_symbol: dict[str, set[str]],
) -> None:
    """Record caller-edges from a direct ``factory().attr`` call-chain access.

    Covers the general form the IC-01 contract illustrates (no intermediate
    local variable). Complements :func:`bind_call_accessor_aliases`, which
    covers the ``local = factory(); local.attr`` two-step shape actually used
    by the known ``_runtime_bridge_module()`` call sites.
    """
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id in factories
        ):
            per_symbol.setdefault(factories[node.value.func.id], set()).add(node.attr)


# ---------------------------------------------------------------------------
# Perf budget (plan.md IC-KEY perf note / contracts non-negotiables)
# ---------------------------------------------------------------------------


def perf_budget_seconds(symbol_count: int) -> float:
    """A generous linear perf budget for a :func:`classify_collisions` run.

    The body-hash introduces a net-new ``tokenize`` pass per ``__all__``
    symbol (the current gate makes ZERO ``tokenize`` calls). This bound is
    intentionally generous (not a tight benchmark) — its job is to catch a
    gross regression (e.g. an accidental O(n^2) corpus re-walk), not to pin
    exact timing, which would be flaky across CI hardware.
    """
    return max(1.0, symbol_count * 0.01)


def timed_classify_collisions(
    corpus: Mapping[str, CorpusModule],
) -> tuple[dict[str, list[Location]], float]:
    """``classify_collisions`` plus wall-clock elapsed seconds, for perf assertions."""
    start = time.perf_counter()
    index = classify_collisions(corpus)
    elapsed = time.perf_counter() - start
    return index, elapsed
