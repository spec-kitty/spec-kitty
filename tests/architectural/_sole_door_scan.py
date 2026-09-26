"""Shared sole-door scan machinery (mission
``charter-sole-door-bypass-closure-01KZ3WAA``, landing-fold gate hardening).

**Not a test module.** This is a plain library module living under
``tests/architectural/`` purely so it can sit next to the gates that consume
it and share their relative-import root; pytest collects zero tests from it
(no ``def test_`` functions, no ``Test*`` classes). Production code still
cannot import it (``src/`` cannot import from ``tests/`` — see
``specify_cli.contracts.anchoring``'s docstring for the same constraint
applied to the composite-key primitive), which is fine: every consumer here is
itself a ``tests/architectural/`` gate.

Why this module exists
-----------------------
Before this fold, Gates 1/2/3 shared this machinery by having Gates 2 and 3
import it from Gate 1's ``test_`` module (``test_charter_sole_door_agent_profile_repository.py``),
and Gates 4 and 5 each rolled an **independent, drifting copy** of the same
primitives (``iter_source_files``, ``parent_map``/``_parent_map``, and the
repo-root derivation duplicated under three different names —
``REPO_ROOT``, ``_REPO_ROOT``/``SRC_ROOT``, ``_REPO_ROOT``/``_SRC_ROOT``).
Gate 4's copy had already lost Gate 1's docstring rationale for
``iter_source_files``'s wholesale ``rglob`` walk — a live drift, not a
hypothetical one. Library code living inside a ``test_`` module is collected
by pytest as a test module (and cannot be imported by non-test code), so a
"shared" copy bolted onto Gate 1 was never a stable foundation. This module is
the promoted, non-test home all five gates import from — mirroring the
existing convention of ``tests/architectural/_ratchet_keys.py``.

The qualname-resolution machinery (NFR-001)
--------------------------------------------
:func:`scan_file_constructions` / :func:`scan_constructions` resolve a call
site's bound name to its canonical ``__module__``.``__qualname__`` via AST
import analysis — module-level **and** function-local **and** nested
``try``/``except`` imports, plus ``as``-aliases, module-qualified calls, and
**per-scope** re-bindings (see :func:`_alias_rebinds_by_scope` below) — and
then asks Python itself where the object came from via
:func:`resolve_canonical`. A rename, a new facade re-export, or an alias
therefore cannot slip past it, and a same-named unrelated class cannot
false-positive into it. Gates 1 and 2 are the two direct consumers; Gate 3
(``charter.offering.resolver`` import ban) and Gates 4/5 (path-hardcode / ``._inner``
reach-around) use the lower-level ``iter_source_files``/``rel_to_repo``/
``parent_map``/``enclosing_scope``/``_scope_chain`` primitives without the
qualname-resolution layer, since their detection shapes differ.

"""

from __future__ import annotations

import ast
import functools
import importlib
from dataclasses import dataclass, field
from pathlib import Path

from tests.architectural._ast_scan import parse_source, read_source
from tests.architectural._ratchet_keys import (
    CompositeKey,
    ContentDescriptor,
    composite_key,
    resolve_descriptor,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"

#: The sole door (NFR-001).
SOLE_DOOR_REL_PATH = "src/charter/activation/resolver.py"
#: The ONE unified builder (FR-008).
UNIFIED_BUILDER_REL_PATH = "src/charter/activation/doctrine_service_builder.py"
#: The doctrine layer owns the wrapped subject (Gate 1/Gate 2's shared
#: rationale: the raw charter.offering.service.DoctrineService construction inside
#: doctrine/service.py IS the thing the sole door wraps, not a bypass of it).
DOCTRINE_LAYER_PREFIX = "src/charter/offering/"

#: Files entitled to construct a watched doctrine class natively. Shared by
#: Gate 1 (AgentProfileRepository) and Gate 2 (DoctrineService), which each
#: police a different watched class against the same two authorities.
SOLE_DOOR_EXEMPT_FILES = frozenset({SOLE_DOOR_REL_PATH, UNIFIED_BUILDER_REL_PATH})
SOLE_DOOR_EXEMPT_PREFIXES = (DOCTRINE_LAYER_PREFIX,)

_MIN_RATIONALE_CHARS = 80


@dataclass(frozen=True)
class ConstructionSite:
    """One resolved construction call of a watched class.

    ``rel_path``/``qualname``/``token`` form the authoritative composite key.
    ``lineno`` is a **non-authoritative** locator carried for jump-to
    diagnostics only — nothing compares, counts, or keys on it.
    """

    rel_path: str
    qualname: str
    token: str
    lineno: int
    canonical: str

    @property
    def key(self) -> CompositeKey:
        """The authoritative ``(rel_path, qualname, token)`` composite key."""
        return (self.rel_path, self.qualname, self.token)

    def describe(self) -> str:
        return f"{self.rel_path}:{self.lineno} ({self.qualname}) -> {self.canonical}"


@dataclass(frozen=True)
class ScanResult:
    """Resolved construction sites plus the sites resolution could not decide."""

    sites: list[ConstructionSite]
    unresolved: list[ConstructionSite]


@dataclass
class _Bindings:
    """Names bound in one lexical scope to an importable ``(module, name)``."""

    #: local name -> (module, original_name)
    from_imports: dict[str, tuple[str, str]] = field(default_factory=dict)
    #: local alias -> real dotted module path
    module_aliases: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class _Origin:
    """Where a callee name came from.

    ``local`` marks a class defined in the scanned file itself, whose canonical
    qualname is derived statically (``<module_of_file>.<name>``) rather than by
    import — so the scanner works on scratch modules that are not importable.
    """

    module: str
    name: str
    local: bool


def iter_source_files(src_root: Path) -> list[Path]:
    """Every ``*.py`` under *src_root*, ``__pycache__`` excluded.

    Derived wholesale from ``rglob`` — no hardcoded package list that a newly
    added subpackage could silently fall outside of.
    """
    return [p for p in sorted(src_root.rglob("*.py")) if "__pycache__" not in p.parts]


def rel_to_repo(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def module_name_for(rel_path: str) -> str:
    """Dotted module name for a repo-relative ``src/`` path."""
    stem = rel_path.removeprefix("src/").removesuffix(".py").removesuffix("/__init__")
    return stem.replace("/", ".")


@functools.cache
def resolve_canonical(module: str, name: str) -> str | None:
    """Return ``"<obj.__module__>.<obj.__qualname__>"`` for ``module.name``.

    This is the qualname resolution NFR-001 demands: it asks the interpreter
    where the object actually came from, so any depth of facade re-export
    (``charter.profiles`` -> ``charter.offering.agent_profiles`` ->
    ``charter.offering.agent_profiles.repository``) collapses to one canonical answer.

    Returns ``None`` when the module or attribute does not exist. Callers must
    treat ``None`` as an unresolved blind spot, never as "clean".
    """
    try:
        mod = importlib.import_module(module)
    except Exception:  # noqa: BLE001 - any import failure means "unresolved"
        return None
    obj = getattr(mod, name, None)
    obj_module = getattr(obj, "__module__", None)
    obj_qualname = getattr(obj, "__qualname__", None)
    if not isinstance(obj_module, str) or not isinstance(obj_qualname, str):
        return None
    return f"{obj_module}.{obj_qualname}"


def _scope_nodes(tree: ast.Module) -> list[ast.AST]:
    scopes: list[ast.AST] = [tree]
    scopes.extend(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    )
    return scopes


def _own_scope_statements(scope: ast.AST) -> list[ast.AST]:
    """Nodes lexically inside *scope*, not descending into nested scopes.

    A ``try:``/``if:``/``with:`` block inside a function still belongs to that
    function's scope — exactly the shape the real violations use (``org_layer.py``
    imports the wrapper inside a ``try``/``except ImportError``). Only a nested
    ``def``/``class`` starts a new scope.
    """
    out: list[ast.AST] = []
    stack: list[ast.AST] = list(ast.iter_child_nodes(scope))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        out.append(node)
        stack.extend(ast.iter_child_nodes(node))
    return out


def _bindings_for_scope(statements: list[ast.AST]) -> _Bindings:
    """Bindings introduced by *statements* — one scope's own statements.

    Perf note (landing-fold gate hardening, 2026-08): takes the
    already-computed :func:`_own_scope_statements` result rather than a raw
    ``scope`` and re-walking it, so callers that also need
    :func:`_alias_rebinds_by_scope` for the same scope compute the walk once,
    not twice. ``_own_scope_statements`` itself keeps its original signature
    (``scope: ast.AST``) since Gate 4 (missions-root hardcode) imports and
    calls it directly.
    """
    bindings = _Bindings()
    for node in statements:
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            for alias in node.names:
                bindings.from_imports[alias.asname or alias.name] = (
                    node.module,
                    alias.name,
                )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                bindings.module_aliases[alias.asname or alias.name] = alias.name
    return bindings


def parent_map(tree: ast.Module) -> dict[int, ast.AST]:
    parents: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node
    return parents


def enclosing_scope(
    parents: dict[int, ast.AST], node: ast.AST, tree: ast.Module
) -> ast.AST:
    """The innermost ``def``/``class`` containing *node*, else the module."""
    cur: ast.AST | None = node
    while cur is not None:
        cur = parents.get(id(cur))
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return cur
    return tree


def _scope_chain(
    parents: dict[int, ast.AST], node: ast.AST, tree: ast.Module
) -> list[ast.AST]:
    """Scopes containing *node*, innermost first, module scope last."""
    chain: list[ast.AST] = []
    cur: ast.AST | None = node
    while cur is not None:
        cur = parents.get(id(cur))
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            chain.append(cur)
    chain.append(tree)
    return chain


def _dotted_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted_name(node.value)
        return None if base is None else f"{base}.{node.attr}"
    return None


def _lookup_module(dotted: str, chain: list[_Bindings]) -> str:
    """Resolve an attribute-chain base to a real dotted module path."""
    for bindings in chain:
        alias = bindings.module_aliases.get(dotted)
        if alias is not None:
            return alias
        # ``from pkg import sub`` then ``sub.Cls(...)``
        from_hit = bindings.from_imports.get(dotted)
        if from_hit is not None:
            return f"{from_hit[0]}.{from_hit[1]}"
    head, _, tail = dotted.partition(".")
    if tail:
        for bindings in chain:
            alias = bindings.module_aliases.get(head)
            if alias is not None:
                return f"{alias}.{tail}"
    return dotted


def _alias_rebinds_by_scope(
    statements: list[ast.AST], bindings: _Bindings, candidate_names: frozenset[str]
) -> dict[str, tuple[str, str]]:
    """``Alias = AgentProfileRepository`` style re-bindings, for ONE scope.

    A1 fix (landing-fold gate hardening): the predecessor
    ``_module_level_rebinds`` walked ``ast.iter_child_nodes(tree)`` — module
    scope only — so a function-local rebind
    (``def build(): ... ; Local = AgentProfileRepository; return Local()``)
    evaded it, even though every real violation these gates close lives at
    function-local or nested scope (NFR-003). This computes the identical
    rebind detection per scope over *statements* — the same
    :func:`_own_scope_statements` result the caller already computed once for
    :func:`_bindings_for_scope`, so the ``try``/``if``/``with``-aware walk
    itself is not repeated a second time for the same scope (perf note,
    landing-fold gate hardening 2026-08).
    """
    rebinds: dict[str, tuple[str, str]] = {}
    for node in statements:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        origin = bindings.from_imports.get(_dotted_name(node.value) or "")
        if origin is not None and origin[1] in candidate_names:
            rebinds[target.id] = origin
    return rebinds


def _locally_defined_names(tree: ast.Module) -> frozenset[str]:
    return frozenset(
        node.name
        for node in ast.iter_child_nodes(tree)
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    )


def callee_simple_name(call: ast.Call) -> str | None:
    """The trailing identifier of ``call``'s callee, ignoring any dotted base."""
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    if isinstance(call.func, ast.Name):
        return call.func.id
    return None


def _resolve_callee(
    call: ast.Call,
    chain: list[_Bindings],
    rebinds_chain: list[dict[str, tuple[str, str]]],
    self_module: str,
    locally_defined: frozenset[str],
) -> _Origin | None:
    """Resolve ``call``'s callee to an importable or file-local origin.

    ``rebinds_chain`` is consulted scope-by-scope (innermost first), exactly
    the way ``chain`` (``_Bindings.from_imports``) already is — the A1 fix
    that lets a function-local ``Alias = AgentProfileRepository`` rebind
    resolve, not just a module-level one.
    """
    func = call.func
    if isinstance(func, ast.Name):
        for bindings in chain:
            hit = bindings.from_imports.get(func.id)
            if hit is not None:
                return _Origin(hit[0], hit[1], local=False)
        for rebinds in rebinds_chain:
            rebound = rebinds.get(func.id)
            if rebound is not None:
                return _Origin(rebound[0], rebound[1], local=False)
        if func.id in locally_defined:
            return _Origin(self_module, func.id, local=True)
        return None
    if isinstance(func, ast.Attribute):
        base = _dotted_name(func.value)
        if base is None:
            return None
        return _Origin(_lookup_module(base, chain), func.attr, local=False)
    return None


def _canonical_for(origin: _Origin) -> str | None:
    """Canonical qualname for *origin* — statically for file-local classes."""
    if origin.local:
        return f"{origin.module}.{origin.name}"
    return resolve_canonical(origin.module, origin.name)


@dataclass(frozen=True)
class FileScan:
    """A parsed file plus everything needed to resolve calls inside it.

    ``matches`` pairs each flagged :class:`ast.Call` node with its resolved
    site. Consumers that need to reason about a call's *surroundings* (Gate 2's
    wrap-flow analysis) must key off these node objects — never off
    ``(lineno, qualname)``, which is ambiguous when two watched constructions
    share a line (``Wrapper(Raw(...))`` in ``charter/compiler.py``).
    """

    rel_path: str
    source: str
    tree: ast.Module
    parents: dict[int, ast.AST]
    matches: tuple[tuple[ast.Call, ConstructionSite], ...]
    result: ScanResult


def _index_file(tree: ast.Module) -> tuple[dict[int, ast.AST], list[ast.AST], list[ast.Call]]:
    """Parents map, scope nodes, and call nodes — computed in one traversal.

    Perf note (landing-fold gate hardening, 2026-08): :func:`scan_file_constructions`
    used to compute this via three independent whole-tree traversals —
    ``parent_map(tree)`` (its own ``ast.walk`` + ``iter_child_nodes`` pass),
    ``_scope_nodes(tree)`` (another ``ast.walk``), and a third ``ast.walk``
    to filter ``ast.Call`` nodes. All three visit every node in the file; this
    walks the tree exactly once via ``ast.iter_child_nodes`` directly (the
    same primitive ``ast.walk`` itself wraps) and buckets each child into all
    three outputs as it goes. Output is identical to calling
    ``parent_map``/``_scope_nodes``/an ``ast.walk`` `Call` filter separately —
    only the traversal count changes. Not exported: ``parent_map`` and
    ``_scope_nodes`` keep their standalone signatures and behaviour unchanged
    for Gate 4 (``test_charter_sole_door_hardcoded_paths.py``), which imports
    and calls them directly.
    """
    parents: dict[int, ast.AST] = {}
    scopes: list[ast.AST] = [tree]
    calls: list[ast.Call] = []
    stack: list[ast.AST] = [tree]
    while stack:
        node = stack.pop()
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                scopes.append(child)
            elif isinstance(child, ast.Call):
                calls.append(child)
            stack.append(child)
    return parents, scopes, calls


def scan_file_constructions(
    path: Path,
    rel_path: str,
    *,
    candidate_names: frozenset[str],
    target_qualnames: frozenset[str],
) -> FileScan | None:
    """Resolve every construction call of any *target_qualnames* in one file.

    Passing more than one target lets a caller classify sibling classes that
    share a source spelling in a **single parse**, so the resulting node
    identities are comparable (Gate 2 needs exactly that for
    ``charter.offering.service.DoctrineService`` vs ``charter.activation.resolver.DoctrineService``).

    Returns ``None`` when a cheap substring pre-check (below) proves the file
    holds no possible match — every caller treats that as "nothing here" (see e.g.
    ``scan_file_raw_sites``'s ``if scan is None: return [], ScanResult([], [])``).
    """
    source = read_source(path, display=rel_path)
    # Perf pre-filter (landing-fold gate hardening, 2026-08): every route that
    # can produce a match — an ``import``/``from``-import of the name, a
    # ``getattr``/local-rebind of an already-imported name, or a file-local
    # class/function literally named one of *candidate_names* — requires that
    # name's exact characters to appear somewhere in the source text first
    # (as an identifier token, or as a string literal for a dynamic-lookup
    # spelling). A file whose raw text contains none of *candidate_names* at
    # all therefore cannot contain a match by construction, so skipping the
    # parse and the whole-tree walk for it is real work avoided, not a cache
    # — 96%+ of src/**/*.py never mention either doctrine-service candidate
    # name, measured against this landing pass's widened scan.
    if not any(name in source for name in candidate_names):
        return None
    # A file that cannot be parsed fails closed (#5139) — never "nothing here".
    tree = parse_source(source, display=rel_path)

    parents, scopes, calls = _index_file(tree)
    # Perf: compute each scope's own-statement walk exactly once and hand the
    # same list to both the binding pass and the rebind pass, instead of
    # letting each call ``_own_scope_statements(scope)`` independently (that
    # duplicate walk was ~half of this scan's measured cost — see
    # test_gate_runs_under_fast_tier_budget's landing-fold history).
    statements_by_scope = {id(scope): _own_scope_statements(scope) for scope in scopes}
    bindings_by_scope = {
        id(scope): _bindings_for_scope(statements_by_scope[id(scope)]) for scope in scopes
    }
    rebinds_by_scope = {
        id(scope): _alias_rebinds_by_scope(
            statements_by_scope[id(scope)], bindings_by_scope[id(scope)], candidate_names
        )
        for scope in scopes
    }
    self_module = module_name_for(rel_path)
    locally_defined = _locally_defined_names(tree)

    matches: list[tuple[ast.Call, ConstructionSite]] = []
    unresolved: list[ConstructionSite] = []
    for node in calls:
        simple_name = callee_simple_name(node)
        if simple_name is None:
            continue
        scope_chain = _scope_chain(parents, node, tree)
        chain = [
            bindings_by_scope[id(scope)]
            for scope in scope_chain
            if id(scope) in bindings_by_scope
        ]
        rebinds_chain = [
            rebinds_by_scope[id(scope)]
            for scope in scope_chain
            if id(scope) in rebinds_by_scope
        ]
        origin = _resolve_callee(
            node, chain, rebinds_chain, self_module, locally_defined
        )
        # Only names that could possibly be a watched class are worth a
        # canonical lookup. The check is on the *original* imported name so an
        # ``as``-alias cannot dodge it (every live site aliases the import).
        if (origin.name if origin else simple_name) not in candidate_names:
            continue
        qualname, token = composite_key(source, node.lineno)
        if origin is None:
            unresolved.append(
                ConstructionSite(rel_path, qualname, token, node.lineno, "<unbound>")
            )
            continue
        canonical = _canonical_for(origin)
        if canonical is None:
            unresolved.append(
                ConstructionSite(
                    rel_path,
                    qualname,
                    token,
                    node.lineno,
                    f"<unimportable {origin.module}.{origin.name}>",
                )
            )
            continue
        if canonical in target_qualnames:
            matches.append(
                (node, ConstructionSite(rel_path, qualname, token, node.lineno, canonical))
            )
    return FileScan(
        rel_path,
        source,
        tree,
        parents,
        tuple(matches),
        ScanResult([site for _, site in matches], unresolved),
    )


def scan_constructions(
    src_root: Path, *, candidate_names: frozenset[str], target_qualnames: frozenset[str]
) -> ScanResult:
    """Whole-tree census of *target_qualnames* constructions under *src_root*.

    Returns **every** site, exemptions included, so a caller can first prove the
    scanner really sees the sanctioned ones (anti-vacuity) and only then filter.
    """
    sites: list[ConstructionSite] = []
    unresolved: list[ConstructionSite] = []
    for path in iter_source_files(src_root):
        scan = scan_file_constructions(
            path,
            rel_to_repo(path),
            candidate_names=candidate_names,
            target_qualnames=target_qualnames,
        )
        if scan is None:
            continue
        sites.extend(scan.result.sites)
        unresolved.extend(scan.result.unresolved)
    return ScanResult(sites, unresolved)


def structurally_exempt(rel_path: str) -> bool:
    """True for the sole door, the unified builder, and the doctrine layer."""
    return rel_path in SOLE_DOOR_EXEMPT_FILES or rel_path.startswith(
        SOLE_DOOR_EXEMPT_PREFIXES
    )


def resolve_exclusion_keys(
    descriptors: tuple[ContentDescriptor, ...],
) -> dict[CompositeKey, ContentDescriptor]:
    """Resolve each descriptor against the live tree to its composite key.

    :func:`resolve_descriptor` RAISES unless a descriptor matches **exactly
    one** live site, so a stale entry (site closed, moved, or edited) fails
    loudly instead of silently widening the exclusion set. That is the staleness
    half of the twin-guard.
    """
    return {
        resolve_descriptor(
            (REPO_ROOT / descriptor.rel_path).read_text(encoding="utf-8"), descriptor
        ): descriptor
        for descriptor in descriptors
    }


def assert_rationales_are_substantive(descriptors: tuple[ContentDescriptor, ...]) -> None:
    """C-002: an exclusion without a written justification is a silent allowlist."""
    for descriptor in descriptors:
        assert len(descriptor.rationale.strip()) > _MIN_RATIONALE_CHARS, descriptor


def scratch_scan(
    tmp_path: Path,
    rel_name: str,
    source: str,
    *,
    candidate_names: frozenset[str],
    target_qualnames: frozenset[str],
) -> FileScan:
    """Write *source* to a scratch module and scan it. Never touches ``src/``."""
    module = tmp_path / Path(rel_name).name
    module.write_text(source, encoding="utf-8")
    scan = scan_file_constructions(
        module,
        rel_name,
        candidate_names=candidate_names,
        target_qualnames=target_qualnames,
    )
    assert scan is not None, f"scratch module {rel_name} failed to parse"
    return scan
