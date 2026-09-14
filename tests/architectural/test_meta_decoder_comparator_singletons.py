"""NFR-002 — VCS-lock comparator + field-set singleton gate.

Mission ``meta-json-fail-closed-routing-01KZPJ1F`` / WP05 / T024.
Requirements: NFR-002, SC-003.
Data model: ``kitty-specs/meta-json-fail-closed-routing-01KZPJ1F/data-model.md``
(VCS-lock comparator table).

The mission unified two forked VCS-lock comparators and their duplicated
field-sets onto one canonical authority in the zero-dependency kernel:

* :func:`kernel.vcs_lock.is_vcs_lock_only_change` — the single comparator
  (sentinel semantics: **absent != present-but-``None``**, C-005); and
* :data:`kernel.vcs_lock.VCS_LOCK_META_FIELDS` — the single *named* field-set
  ``frozenset({"vcs", "vcs_locked_at"})``.

Retired by the mission: ``ref_advance._VCS_LOCK_META_FIELDS`` /
``ref_advance._is_vcs_lock_only_meta_change`` (old ``.get()`` semantics) and
``implement_cores._VCS_LOCK_META_FIELDS`` /
``implement_cores._is_vcs_lock_only_meta_diff``.

The spec (NFR-002 / SC-003) promises this is "verified by enumeration", but no
structural gate existed — a manual grep is not a regression guard. This module is
that gate: a re-introduced fork (a second comparator def, a second named
field-set, or an inline ``frozenset({"vcs", ...})`` literal) must red the build.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = pytest.mark.architectural

# --------------------------------------------------------------------------- #
# Source-tree roots (repo-root independent).
# this file: <root>/tests/architectural/test_meta_decoder_comparator_singletons.py
# --------------------------------------------------------------------------- #
_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parents[2]
SRC_ROOT = _REPO_ROOT / "src"

#: The canonical homes (repo-relative) of the two singletons.
CANONICAL_COMPARATOR = "is_vcs_lock_only_change"
CANONICAL_FIELD_SET = "VCS_LOCK_META_FIELDS"
_CANONICAL_REL = "src/kernel/vcs_lock.py"

#: The VCS-lock field constants; a set/frozenset literal carrying BOTH is a
#: VCS-lock field-set literal (precise enough to avoid matching unrelated sets
#: that merely happen to contain the string ``"vcs"``).
_VCS_LOCK_FIELD_CONSTANTS: frozenset[str] = frozenset({"vcs", "vcs_locked_at"})


# --------------------------------------------------------------------------- #
# AST helpers.
# --------------------------------------------------------------------------- #
def _iter_source_files(src_root: Path) -> list[Path]:
    return [p for p in sorted(src_root.rglob("*.py")) if "__pycache__" not in p.parts]


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:  # pragma: no cover - defensive, all scanned files are under root
        return path.as_posix()


def _is_vcs_lock_field_set_name(name: str) -> bool:
    """True for an identifier that names a VCS-lock field-set (canonical or forked)."""
    return "vcs_lock_meta_fields" in name.lower()


def _constants_in_collection(node: ast.expr) -> set[str]:
    """Return the string constants of a set/list/tuple literal (else empty)."""
    if not isinstance(node, (ast.Set, ast.List, ast.Tuple)):
        return set()
    return {elt.value for elt in node.elts if isinstance(elt, ast.Constant) and isinstance(elt.value, str)}


def _is_frozenset_call(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "frozenset"


def _is_vcs_lock_field_literal(node: ast.expr) -> bool:
    """True for the EXACT ``{"vcs", "vcs_locked_at"}`` field-set literal.

    Matches a bare set/list/tuple literal or a ``frozenset({...})`` wrapping one,
    requiring the constants to equal :data:`_VCS_LOCK_FIELD_CONSTANTS` EXACTLY. A
    broader collection that merely *contains* both fields (e.g.
    ``ACCEPTANCE_PROVENANCE_FIELDS``, a 7-tuple of provenance keys) is a different
    construct, not a duplicated VCS-lock field-set, so equality (not subset)
    keeps it out.
    """
    if _is_frozenset_call(node):
        assert isinstance(node, ast.Call)  # narrowed by _is_frozenset_call
        inner = node.args[0] if node.args else None
        return inner is not None and _constants_in_collection(inner) == _VCS_LOCK_FIELD_CONSTANTS
    return _constants_in_collection(node) == _VCS_LOCK_FIELD_CONSTANTS


def _references_field_set(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True when *fn*'s body inspects a VCS-lock field-set to decide its verdict.

    A genuine comparator READS the field-set — either a named identifier
    (``VCS_LOCK_META_FIELDS`` / a forked ``_VCS_LOCK_META_FIELDS``) or an inline
    ``{"vcs", "vcs_locked_at"}`` literal. A thin routing wrapper (e.g.
    ``ref_advance._meta_change_is_vcs_lock_only``) instead CALLS
    :func:`kernel.vcs_lock.is_vcs_lock_only_change` and never touches the
    field-set, so it is correctly NOT a comparator.
    """
    for node in ast.walk(fn):
        if isinstance(node, ast.Name) and _is_vcs_lock_field_set_name(node.id):
            return True
        if isinstance(node, ast.expr) and _is_vcs_lock_field_literal(node):
            return True
    return False


@dataclass(frozen=True)
class _Located:
    """One discovered symbol/literal, for diagnostics."""

    rel_path: str
    name: str
    lineno: int


def _assign_targets(node: ast.AST) -> tuple[ast.expr | None, list[ast.expr]]:
    """Return ``(value, targets)`` for an assignment-shaped node, else ``(None, [])``."""
    if isinstance(node, ast.Assign):
        return node.value, list(node.targets)
    if isinstance(node, ast.AnnAssign) and node.value is not None:
        return node.value, [node.target]
    return None, []


def scan_comparator_defs(src_root: Path) -> list[_Located]:
    """Find every VCS-lock comparator function definition tree-wide.

    A comparator is a function that INSPECTS a VCS-lock field-set
    (:func:`_references_field_set`) to compute a lock-only verdict — the logic
    the mission unified. Routing wrappers that merely delegate to the kernel
    comparator are excluded (they do not read the field-set), so the count
    reflects genuine comparators, not call sites.
    """
    found: list[_Located] = []
    repo_root = src_root.parent
    for path in _iter_source_files(src_root):
        rel = _rel(path, repo_root)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:  # pragma: no cover - defensive
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _references_field_set(node):
                found.append(_Located(rel, node.name, node.lineno))
    return found


def scan_field_set_declarations(src_root: Path) -> list[_Located]:
    """Find every ``*VCS_LOCK_META_FIELDS`` named declaration tree-wide."""
    found: list[_Located] = []
    repo_root = src_root.parent
    for path in _iter_source_files(src_root):
        rel = _rel(path, repo_root)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:  # pragma: no cover - defensive
            continue
        for node in ast.walk(tree):
            _value, targets = _assign_targets(node)
            for tgt in targets:
                if isinstance(tgt, ast.Name) and _is_vcs_lock_field_set_name(tgt.id):
                    found.append(_Located(rel, tgt.id, tgt.lineno))
    return found


def scan_inline_field_literals(src_root: Path) -> list[_Located]:
    """Find inline VCS-lock field-set literals that are NOT the canonical declaration.

    The single canonical ``VCS_LOCK_META_FIELDS = frozenset({"vcs",
    "vcs_locked_at"})`` assignment is excluded (its RHS is the legitimate one
    declaration). Every OTHER ``frozenset({"vcs", ...})`` / ``{"vcs",
    "vcs_locked_at"}`` literal is a duplicate the mission forbids (NFR-002).
    """
    found: list[_Located] = []
    repo_root = src_root.parent
    for path in _iter_source_files(src_root):
        rel = _rel(path, repo_root)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:  # pragma: no cover - defensive
            continue
        found.extend(_scan_tree_for_inline_literals(tree, rel))
    return found


def _scan_tree_for_inline_literals(tree: ast.Module, rel: str) -> list[_Located]:
    """Inline VCS-lock field literals in one module (canonical declaration excluded)."""
    parents: dict[int, ast.AST] = {
        id(child): node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)
    }
    # Node ids belonging to a canonical ``*VCS_LOCK_META_FIELDS = <rhs>``
    # assignment RHS — the one sanctioned literal, excluded from the scan.
    sanctioned: set[int] = set()
    for node in ast.walk(tree):
        value, targets = _assign_targets(node)
        if value is not None and any(
            isinstance(t, ast.Name) and _is_vcs_lock_field_set_name(t.id) for t in targets
        ):
            sanctioned.update(id(sub) for sub in ast.walk(value))
    found: list[_Located] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.expr):
            continue
        if id(node) in sanctioned or not _is_vcs_lock_field_literal(node):
            continue
        # Dedup: a bare set/list/tuple that is the argument of a matched
        # ``frozenset({...})`` call is already counted via the call node — skip it.
        if isinstance(node, (ast.Set, ast.List, ast.Tuple)) and _is_frozenset_call(parents.get(id(node))):
            continue
        found.append(_Located(rel, ast.dump(node)[:60], node.lineno))
    return found


# =========================================================================== #
# TESTS — the NFR-002 enumeration gate on the real tree.
# =========================================================================== #
def test_single_vcs_lock_comparator() -> None:
    """NFR-002 / SC-003: exactly one VCS-lock comparator symbol tree-wide."""
    defs = scan_comparator_defs(SRC_ROOT)
    names = sorted(f"{d.rel_path}:{d.lineno} {d.name}" for d in defs)
    assert len(defs) == 1, (
        "NFR-002: expected exactly one VCS-lock comparator definition; found "
        f"{len(defs)}:\n  " + "\n  ".join(names) + "\nA re-introduced fork (e.g. "
        "ref_advance._is_vcs_lock_only_meta_change) must route onto "
        "kernel.vcs_lock.is_vcs_lock_only_change instead."
    )
    only = defs[0]
    assert only.name == CANONICAL_COMPARATOR and only.rel_path == _CANONICAL_REL, (
        f"the sole comparator must be {_CANONICAL_REL}:{CANONICAL_COMPARATOR}; "
        f"found {only.rel_path}:{only.name}"
    )


def test_single_named_field_set() -> None:
    """NFR-002 / SC-003: exactly one named ``VCS_LOCK_META_FIELDS`` declaration."""
    decls = scan_field_set_declarations(SRC_ROOT)
    where = sorted(f"{d.rel_path}:{d.lineno} {d.name}" for d in decls)
    assert len(decls) == 1, (
        "NFR-002: expected exactly one named VCS-lock field-set declaration; "
        f"found {len(decls)}:\n  " + "\n  ".join(where) + "\nThe retired "
        "_VCS_LOCK_META_FIELDS forks must not return."
    )
    only = decls[0]
    assert only.name == CANONICAL_FIELD_SET and only.rel_path == _CANONICAL_REL, (
        f"the sole field-set must be {_CANONICAL_REL}:{CANONICAL_FIELD_SET}; "
        f"found {only.rel_path}:{only.name}"
    )


def test_no_inline_vcs_lock_field_literals() -> None:
    """NFR-002: zero inline ``frozenset({"vcs", ...})`` field-set literals.

    The one canonical named declaration is excluded; any other inline literal is
    a duplicate that would drift from the single authority.
    """
    literals = scan_inline_field_literals(SRC_ROOT)
    where = sorted(f"{loc.rel_path}:{loc.lineno}" for loc in literals)
    assert literals == [], (
        "NFR-002: inline VCS-lock field-set literal(s) found (use "
        f"kernel.vcs_lock.{CANONICAL_FIELD_SET} instead):\n  " + "\n  ".join(where)
    )


# =========================================================================== #
# Unit coverage for the detectors (Sonar: every new branch/helper is tested).
# =========================================================================== #
def _write_scratch(tmp_path: Path, pkg_name: str, source: str) -> Path:
    pkg = tmp_path / "src" / pkg_name
    pkg.mkdir(parents=True)
    (tmp_path / "src" / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "mod.py").write_text(source, encoding="utf-8")
    return tmp_path / "src"


def _fn_of(source: str) -> ast.FunctionDef:
    tree = ast.parse(source)
    return next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))


def test_references_field_set_detects_named_and_inline() -> None:
    """A comparator that reads the named field-set OR an inline literal is detected."""
    named = _fn_of(
        "def cmp(before, after):\n"
        "    return all(k in VCS_LOCK_META_FIELDS for k in before)\n"
    )
    forked_named = _fn_of(
        "def cmp(before, after):\n"
        "    return all(k in _VCS_LOCK_META_FIELDS for k in before)\n"
    )
    inline = _fn_of(
        "def cmp(before, after):\n"
        '    fields = frozenset({"vcs", "vcs_locked_at"})\n'
        "    return fields\n"
    )
    assert _references_field_set(named) is True
    assert _references_field_set(forked_named) is True
    assert _references_field_set(inline) is True


def test_references_field_set_excludes_routing_wrapper() -> None:
    """A wrapper that delegates to the kernel comparator is NOT itself a comparator."""
    wrapper = _fn_of(
        "def wrapper(before, after):\n"
        "    return is_vcs_lock_only_change(before, after)\n"
    )
    assert _references_field_set(wrapper) is False


def test_field_set_name_matcher() -> None:
    assert _is_vcs_lock_field_set_name("VCS_LOCK_META_FIELDS") is True
    assert _is_vcs_lock_field_set_name("_VCS_LOCK_META_FIELDS") is True
    assert _is_vcs_lock_field_set_name("META_FIELDS") is False


def test_field_literal_matcher_requires_both_constants() -> None:
    both = ast.parse('{"vcs", "vcs_locked_at"}', mode="eval").body
    frozen = ast.parse('frozenset({"vcs", "vcs_locked_at"})', mode="eval").body
    partial = ast.parse('{"vcs"}', mode="eval").body
    unrelated = ast.parse('{"a", "b"}', mode="eval").body
    assert _is_vcs_lock_field_literal(both) is True
    assert _is_vcs_lock_field_literal(frozen) is True
    assert _is_vcs_lock_field_literal(partial) is False
    assert _is_vcs_lock_field_literal(unrelated) is False


# --- anti-vacuity canaries: the gate FIRES on a re-introduced fork -----------
def test_canary_flags_second_comparator(tmp_path: Path) -> None:
    """A re-introduced comparator fork surfaces to the scanner.

    A genuine fork re-implements the field comparison, so it reads a field-set
    (its own inline ``frozenset({"vcs", ...})`` here) — exactly what
    :func:`_references_field_set` keys on.
    """
    scratch = _write_scratch(
        tmp_path,
        "canary_comparator_pkg",
        "def _is_vcs_lock_only_meta_diff(before, after):\n"
        '    fields = frozenset({"vcs", "vcs_locked_at"})\n'
        "    return set(before) - fields == set(after) - fields\n",
    )
    defs = scan_comparator_defs(scratch)
    assert any(d.name == "_is_vcs_lock_only_meta_diff" for d in defs)


def test_canary_flags_forked_field_set(tmp_path: Path) -> None:
    """A re-introduced named field-set fork surfaces to the scanner."""
    scratch = _write_scratch(
        tmp_path,
        "canary_fieldset_pkg",
        '_VCS_LOCK_META_FIELDS = frozenset({"vcs", "vcs_locked_at"})\n',
    )
    decls = scan_field_set_declarations(scratch)
    assert any(d.name == "_VCS_LOCK_META_FIELDS" for d in decls)


def test_canary_flags_inline_literal_but_not_canonical(tmp_path: Path) -> None:
    """An inline literal is flagged; the canonical named declaration is NOT.

    Proves the exclusion is scoped to the ``VCS_LOCK_META_FIELDS = ...`` RHS, so
    the gate fires on a bare duplicate literal while the one authority is exempt.
    """
    scratch = _write_scratch(
        tmp_path,
        "canary_literal_pkg",
        'VCS_LOCK_META_FIELDS = frozenset({"vcs", "vcs_locked_at"})\n'
        "def diff(before, after):\n"
        '    fields = frozenset({"vcs", "vcs_locked_at"})\n'
        "    return fields\n",
    )
    literals = scan_inline_field_literals(scratch)
    assert len(literals) == 1, f"expected exactly the inline duplicate, got {literals}"
    assert literals[0].lineno == 3, "the canonical declaration RHS must be excluded, the inline literal flagged"
