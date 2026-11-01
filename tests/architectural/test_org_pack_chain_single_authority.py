"""Class gate: no off-authority call to the org-pack chain primitives in the scoped dirs (FR-006, NFR-002).

``charter.activation.layer_roots.resolve_pack_chain`` is the chain authority; this
gate enforces only that the scoped callers do not invoke the chain PRIMITIVES
directly. It does not prove every chain assembly goes through the authority:
``resolve_org_dirs`` (the subdir-joining sibling, called in scope at
``src/charter/activation/mission_type_profiles.py``) is a known in-scope
chain-assembler not yet routed through it, tracked in follow-up #6012.

Mission ``org-pack-chain-authority-01M4JXF5``. Every charter-activation and
charter-CLI caller that needs the ordered org-pack roots asks
``resolve_pack_chain`` (``src/charter/activation/layer_roots.py``). The
primitives that compose a chain by hand are forbidden to those callers:

* a ``Call`` to ``resolve_org_roots`` / ``resolve_existing_org_roots`` /
  ``require_declared_org_roots`` / ``resolve_org_root_chain``;
* iterating ``<registry>.packs`` and collecting BARE ``pack.effective_root(...)``
  Paths on their own into a list/set/mapping (roots-only chain assembly by hand).
  A collection is an ``append``/``add``/``extend`` argument, a comprehension
  element, or the value of an assignment into a subscript (``roots[i] = ...``);
  for a subscript assignment the key is part of the pairing evidence.

**Rule 2 is deliberately roots-only.** The authority owns the ordered, existence-filtered
ROOT chain (``list[Path]``). Code that needs pack NAMES (a ``(pack.name, root)`` pair, a
loop that also collects ``pack.name``, a subscript key that is exactly ``pack.name``, or a dict
comprehension keyed by exactly ``pack.name``; ``len(p.name)`` or the root's basename
``p.effective_root(r).name`` is not the pack name and does not count) or an unfiltered enumeration (the missing-pack
diagnostic) legitimately reads the pack registry, because the Path-only authority cannot
provide names or unfiltered paths. That is a rule-semantics boundary, not an allowlist entry.
The name-pairing test is deliberately one-sided where it can be: a ``DictComp`` is exempt
only when its KEY names the pack, so ``{p.effective_root(r): p.name ...}`` — whose key is
the root itself — is still roots-only assembly.

**Scope** (research.md Decision 5): the whole ``src/`` tree. The one exclusion is a
SCAN-EXCLUSION rule, not an allowlist entry: files under ``src/charter/offering/**``
are not censused, because that tier defines and cross-calls the forbidden primitives
(``org_pack_config``) and cannot import the activation authority above it.

The two name-paired tree-wide readers (``_enumerate_org_pack_paths[_strict]`` and
``pack_context._read_org_packs``) are non-violations under the existing Rule-1/Rule-2
semantics: they read ``load_pack_registry()`` and return name-paired tuples / capture
``pack.name``, which the roots-only authority cannot provide.

**Call-based only**: importing or re-exporting a primitive, or naming it in a
docstring, is not a violation.

**There is no allowlist, and none may be added** (ADR
``2026-09-30-1-allowlist-ratchets-are-priced-debt``): a new hit is fixed by
calling ``resolve_pack_chain``.

Non-vacuity (standing order 5): a scanned-file floor, a planted violation per
rule, and an owner-bypass control proving the owner is exempt by module
ownership while the census can still see it.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCOPE_DIRS: tuple[Path, ...] = (_REPO_ROOT / "src",)
_OWNER = _REPO_ROOT / "src" / "charter" / "activation" / "layer_roots.py"

# NFR-002: the allowlist is literally empty; the test below asserts it stays so.
_ALLOWED: frozenset[str] = frozenset()

_PRIMITIVES: frozenset[str] = frozenset(
    {
        "resolve_org_roots",
        "resolve_existing_org_roots",
        "require_declared_org_roots",
        "resolve_org_root_chain",
    }
)
_COLLECTOR_METHODS: frozenset[str] = frozenset({"append", "add", "extend"})

# Iterator wrappers that hold the registry's ``packs`` while hiding it from a bare
# attribute test (``for i, p in enumerate(registry.packs)").
_ITER_WRAPPERS: frozenset[str] = frozenset({"enumerate", "iter", "list", "reversed", "sorted", "tuple"})
# Wrappers that take several iterables, so ``packs`` may sit in any argument
# (``zip(range(n), registry.packs)``).
_MULTI_ITER_WRAPPERS: frozenset[str] = frozenset({"chain", "zip"})

# ~1320 modules in scope tree-wide (owner and offering tier excluded); leave headroom.
_SCANNED_FILE_FLOOR = 1200

_FIX_HINT = "Call charter.activation.layer_roots.resolve_pack_chain(repo_root, strict=...) instead of assembling org roots by hand"


@dataclass(frozen=True)
class Hit:
    rel: str
    lineno: int
    kind: str


_OFFERING_PARTS: tuple[str, str] = ("charter", "offering")


def _in_offering_tier(path: Path) -> bool:
    """SCAN-EXCLUSION: ``src/charter/offering/**`` defines the primitives and cannot import the authority."""
    parts = path.resolve().relative_to(_REPO_ROOT).parts
    return any(parts[i : i + 2] == _OFFERING_PARTS for i in range(len(parts) - 1))


def _scope_files() -> list[Path]:
    return sorted(p for d in _SCOPE_DIRS for p in d.rglob("*.py") if not _in_offering_tier(p))


def _called_name(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _is_bare_root(node: ast.AST) -> bool:
    """True when *node* is exactly a ``<x>.effective_root(...)`` call (a Path on its own)."""
    return isinstance(node, ast.Call) and _called_name(node) == "effective_root"


def _is_packs_iter(node: ast.expr) -> bool:
    """True for ``<registry>.packs``, also when an iterator wrapper such as ``enumerate(...)`` holds it."""
    if isinstance(node, ast.Attribute) and node.attr == "packs":
        return True
    if isinstance(node, ast.Call) and _called_name(node) in _ITER_WRAPPERS and node.args:
        return _is_packs_iter(node.args[0])
    if isinstance(node, ast.Call) and _called_name(node) in _MULTI_ITER_WRAPPERS:
        return any(_is_packs_iter(a) for a in node.args)
    return False


def _target_names(target: ast.AST) -> set[str]:
    """Variable names bound by a loop/comprehension target (``p`` or ``i, p``)."""
    return {n.id for n in ast.walk(target) if isinstance(n, ast.Name)}


def _is_pack_name(node: ast.AST, loop_vars: set[str]) -> bool:
    """True only for exactly ``<loop variable>.name`` (the name-pairing evidence).

    Not ``p.effective_root(r).name`` (the root's basename) and not ``len(p.name)``:
    those are derived from, not equal to, the pack name.
    """
    return isinstance(node, ast.Attribute) and node.attr == "name" and isinstance(node.value, ast.Name) and node.value.id in loop_vars


def _collector_args(loop: ast.For) -> list[ast.expr]:
    return [
        a
        for stmt in loop.body
        for n in ast.walk(stmt)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in _COLLECTOR_METHODS
        for a in n.args
    ]


def _subscript_assignments(loop: ast.For) -> list[tuple[ast.expr, ast.expr]]:
    """``<x>[<key>] = <value>`` (also annotated) in the loop body, as ``(key, value)`` pairs.

    Assigning into a subscript is a collector too: a preallocated ``roots[i] = ...``
    loop assembles the same roots-only chain as ``roots.append(...)``. The subscript
    key is that collection's name-pairing evidence, so ``roots[p.name] = ...``
    stays name-paired while ``roots[i] = ...`` does not.
    """
    return [
        (target.slice, n.value)
        for stmt in loop.body
        for n in ast.walk(stmt)
        if isinstance(n, (ast.Assign, ast.AnnAssign)) and n.value is not None
        for target in (n.targets if isinstance(n, ast.Assign) else [n.target])
        if isinstance(target, ast.Subscript)
    ]


def _loop_collects_bare_roots(loop: ast.For) -> bool:
    args = _collector_args(loop)
    subscript_pairs = _subscript_assignments(loop)
    collected = args + [value for _, value in subscript_pairs]
    # Pairing evidence: a collected ``*.name`` value (as before), or a subscript key that
    # names the pack. Judged over the loop's collected values and keys, never over the
    # whole body, so a loop that merely reads ``pack.name`` stays a violation.
    loop_vars = _target_names(loop.target)
    captures_name = any(_is_pack_name(a, loop_vars) for a in args) or any(_is_pack_name(key, loop_vars) for key, _ in subscript_pairs)
    return any(_is_bare_root(a) for a in collected) and not captures_name


def _comprehension_collects_bare_roots(node: ast.ListComp | ast.SetComp | ast.GeneratorExp | ast.DictComp) -> bool:
    if not any(_is_packs_iter(g.iter) for g in node.generators):
        return False
    if isinstance(node, ast.DictComp):
        # A dict keyed by a pack name is a name-paired reader (the root-only authority
        # cannot supply names). A dict keyed by the root itself is a roots-only mapping,
        # whatever its values carry.
        if _is_pack_name(node.key, {v for g in node.generators for v in _target_names(g.target)}):
            return False
        return _is_bare_root(node.key) or _is_bare_root(node.value)
    return _is_bare_root(node.elt)


def _hand_assembly_kind(node: ast.AST) -> str | None:
    if isinstance(node, ast.For) and _is_packs_iter(node.iter) and _loop_collects_bare_roots(node):
        return "registry.packs iteration assembling roots"
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)) and _comprehension_collects_bare_roots(node):
        return "registry.packs comprehension assembling roots"
    return None


def _node_hit_kind(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call) and _called_name(node) in _PRIMITIVES:
        return f"call to {_called_name(node)}"
    return _hand_assembly_kind(node)


def _scan_source(source: str, rel: str) -> list[Hit]:
    tree = ast.parse(source)
    hits: list[Hit] = []
    for node in ast.walk(tree):
        kind = _node_hit_kind(node)
        if kind is not None:
            hits.append(Hit(rel, getattr(node, "lineno", 0), kind))
    return hits


def census(files: list[Path], *, skip_owner: bool = True) -> list[Hit]:
    hits: list[Hit] = []
    for path in files:
        if skip_owner and path.resolve() == _OWNER:
            continue
        if _in_offering_tier(path):
            continue
        hits.extend(_scan_source(path.read_text(encoding="utf-8"), path.resolve().relative_to(_REPO_ROOT).as_posix()))
    return hits


def _plant(tmp_path: Path, body: str) -> list[Hit]:
    planted = tmp_path / "planted.py"
    planted.write_text(body, encoding="utf-8")
    return [Hit(h.rel, h.lineno, h.kind) for h in _scan_source(planted.read_text(encoding="utf-8"), "planted.py")]


def test_allowlist_is_empty() -> None:
    assert not _ALLOWED, "the allowlist must stay empty (NFR-002, ADR 2026-09-30-1); fix the caller instead"


def test_no_hand_assembled_org_chain_outside_the_authority() -> None:
    hits = census(_scope_files())
    assert not hits, (
        "Hand-assembled org-pack chain outside charter.activation.layer_roots (there is no allowlist):\n"
        + "\n".join(f"  {h.rel}:{h.lineno}: {h.kind}" for h in hits)
        + f"\n{_FIX_HINT}"
    )


def test_census_scans_enough_files() -> None:
    scanned = [p for p in _scope_files() if p.resolve() != _OWNER]
    assert len(scanned) >= _SCANNED_FILE_FLOOR, f"only {len(scanned)} files scanned; the gate is vacuous below {_SCANNED_FILE_FLOOR}"


def test_owner_bypass_control_census_sees_the_owner() -> None:
    owner_hits = census([_OWNER], skip_owner=False)
    assert any(h.kind.startswith("call to ") for h in owner_hits), "the census is blind to layer_roots.py"
    assert census([_OWNER]) == [], "the owner exemption in census() stopped working"


@pytest.mark.parametrize(
    ("kind", "body"),
    [
        ("call to resolve_existing_org_roots", "def f(r):\n    return resolve_existing_org_roots(r)\n"),
        ("call to resolve_org_roots", "def f(r):\n    return mod.resolve_org_roots(r)\n"),
        ("call to require_declared_org_roots", "def f(r):\n    return require_declared_org_roots(r)\n"),
        ("call to resolve_org_root_chain", "def f(r):\n    return resolve_org_root_chain(r)\n"),
        (
            "registry.packs iteration assembling roots",
            "def f(r):\n    roots = []\n    for p in load_pack_registry(r).packs:\n        roots.append(p.effective_root(r))\n    return roots\n",
        ),
        (
            "registry.packs comprehension assembling roots",
            "def f(r):\n    return [p.effective_root(r) for p in load_pack_registry(r).packs]\n",
        ),
        (
            "registry.packs iteration assembling roots",
            "def f(r):\n    roots = []\n    for i, p in enumerate(load_pack_registry(r).packs):\n        roots[i] = p.effective_root(r)\n    return roots\n",
        ),
        (
            "registry.packs comprehension assembling roots",
            "def f(r):\n    return {p.effective_root(r): p.name for p in load_pack_registry(r).packs}\n",
        ),
        (
            "registry.packs comprehension assembling roots",
            "def f(r):\n    return {i: p.effective_root(r) for i, p in enumerate(load_pack_registry(r).packs)}\n",
        ),
        (
            "registry.packs comprehension assembling roots",
            "def f(r):\n    return {p.effective_root(r).name: p.effective_root(r) for p in load_pack_registry(r).packs}\n",
        ),
        (
            "registry.packs iteration assembling roots",
            "def f(r):\n    roots = {}\n    for p in load_pack_registry(r).packs:\n        roots[len(p.name)] = p.effective_root(r)\n    return roots\n",
        ),
        (
            "registry.packs iteration assembling roots",
            "def f(r):\n    roots = {}\n    for i, p in enumerate(load_pack_registry(r).packs):\n        roots[i]: Path = p.effective_root(r)\n    return roots\n",
        ),
        (
            "registry.packs iteration assembling roots",
            "def f(r):\n    roots = []\n    for i, p in zip(range(3), load_pack_registry(r).packs):\n        roots.append(p.effective_root(r))\n    return roots\n",
        ),
        (
            "registry.packs comprehension assembling roots",
            "def f(r):\n    return [p.effective_root(r) for p in itertools.chain([], load_pack_registry(r).packs)]\n",
        ),
    ],
    ids=[
        "existing",
        "attribute-form",
        "require-declared",
        "root-chain",
        "packs-loop",
        "packs-comprehension",
        "packs-subscript-assignment",
        "root-keyed-dict-comprehension",
        "index-keyed-dict-comprehension",
        "root-basename-keyed-dict-comprehension",
        "len-of-name-subscript-key",
        "annotated-subscript-assignment",
        "zip-hides-packs",
        "chain-hides-packs",
    ],
)
def test_planted_violation_is_reported(tmp_path: Path, kind: str, body: str) -> None:
    assert kind in {h.kind for h in _plant(tmp_path, body)}


@pytest.mark.parametrize(
    "source",
    [
        "from charter.offering.drg.org_pack_config import resolve_existing_org_roots\n__all__ = ['resolve_existing_org_roots']\n",
        '"""Mentions resolve_existing_org_roots(repo_root) in prose."""\n',
        "def f(r):\n    return resolve_pack_chain(r, strict=False)\n",
        "def f(r):\n    return [p.name for p in load_pack_registry(r).packs]\n",
        "def f(r):\n    return [(p.name, p.effective_root(r)) for p in load_pack_registry(r).packs]\n",
        (
            "def f(r):\n    n, roots = [], []\n    for p in load_pack_registry(r).packs:\n"
            "        n.append(p.name)\n        roots.append(p.effective_root(r))\n    return n, roots\n"
        ),
        "def f(r):\n    for p in load_pack_registry(r).packs:\n        use(p.effective_root(r))\n",
        ("def f(r):\n    roots = {}\n    for p in load_pack_registry(r).packs:\n        roots[p.name] = p.effective_root(r)\n    return roots\n"),
        "def f(r):\n    return {p.name: p.effective_root(r) for p in load_pack_registry(r).packs}\n",
    ],
    ids=[
        "reexport",
        "docstring",
        "authority-call",
        "names-only",
        "pair-comprehension",
        "paired-loop",
        "no-collection",
        "name-keyed-subscript",
        "name-keyed-dict-comprehension",
    ],
)
def test_non_violations_are_not_flagged(tmp_path: Path, source: str) -> None:
    assert _plant(tmp_path, source) == []
