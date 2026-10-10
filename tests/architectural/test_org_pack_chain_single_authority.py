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
  Paths on their own into a list/set (roots-only chain assembly by hand).

**Rule 2 is deliberately roots-only.** The authority owns the ordered, existence-filtered
ROOT chain (``list[Path]``). Code that needs pack NAMES (a ``(pack.name, root)`` pair, or a
loop that also collects ``pack.name``) or an unfiltered enumeration (the missing-pack
diagnostic) legitimately reads the pack registry, because the Path-only authority cannot
provide names or unfiltered paths. That is a rule-semantics boundary, not an allowlist entry.

**Scope** (research.md Decision 5): ``src/charter/activation/**`` and
``src/specify_cli/cli/commands/charter/**``. The ``charter.offering`` tier is
not censused: it cannot import the activation authority, so its chain
authority is its own primitives (``org_pack_config``).

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
_SCOPE_DIRS: tuple[Path, ...] = (
    _REPO_ROOT / "src" / "charter" / "activation",
    _REPO_ROOT / "src" / "specify_cli" / "cli" / "commands" / "charter",
)
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

# 133 modules in scope at the integrated lane; leave headroom.
_SCANNED_FILE_FLOOR = 100

_FIX_HINT = "Call charter.activation.layer_roots.resolve_pack_chain(repo_root, strict=...) instead of assembling org roots by hand"


@dataclass(frozen=True)
class Hit:
    rel: str
    lineno: int
    kind: str


def _scope_files() -> list[Path]:
    return sorted(p for d in _SCOPE_DIRS for p in d.rglob("*.py"))


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
    return isinstance(node, ast.Attribute) and node.attr == "packs"


def _collector_args(loop: ast.For) -> list[ast.expr]:
    return [
        a
        for stmt in loop.body
        for n in ast.walk(stmt)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in _COLLECTOR_METHODS
        for a in n.args
    ]


def _loop_collects_bare_roots(loop: ast.For) -> bool:
    args = _collector_args(loop)
    captures_name = any(isinstance(a, ast.Attribute) and a.attr == "name" for a in args)
    return any(_is_bare_root(a) for a in args) and not captures_name


def _comprehension_collects_bare_roots(node: ast.ListComp | ast.SetComp | ast.GeneratorExp | ast.DictComp) -> bool:
    if not any(_is_packs_iter(g.iter) for g in node.generators):
        return False
    elts = [node.key, node.value] if isinstance(node, ast.DictComp) else [node.elt]
    return any(_is_bare_root(e) for e in elts)


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
    ],
    ids=["existing", "attribute-form", "require-declared", "root-chain", "packs-loop", "packs-comprehension"],
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
    ],
    ids=["reexport", "docstring", "authority-call", "names-only", "pair-comprehension", "paired-loop", "no-collection"],
)
def test_non_violations_are_not_flagged(tmp_path: Path, source: str) -> None:
    assert _plant(tmp_path, source) == []
