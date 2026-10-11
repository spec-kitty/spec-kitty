"""Single-authority gate for the ``pack_level`` field vocabulary (#6048, FR-020).

Why this gate exists
--------------------
The v2 ``pack.yaml`` descriptor gains a ``pack_level`` field whose allowed values
are exactly the Charter Pack tiers owned by :mod:`kernel.pack_tiers` (``built-in``
/ ``org`` / ``project``). The field MUST reuse that single authority
(``pack_level: PackTier``) — a hand-authored ``Literal["built-in", "org",
"project"]`` annotation, or a ``pack_level``-named set/tuple/list/dict restating
the full tier set, would be a second home for the level vocabulary that could
silently drift from the kernel authority (a fourth tier, a reordering, a dropped
token). Per DIRECTIVE_043 this gate ships **non-vacuous in the same mission as
the field it protects**, with an **empty allowlist**.

Scope — the ``pack_level`` / level surface only (NOT the generic tier scan)
--------------------------------------------------------------------------
This gate is deliberately NOT a copy of
``tests/architectural/test_pack_tier_token_single_authority.py`` (WP06 owns the
generic, value-driven scan that flags *any* tier-tuple restatement anywhere under
``src/``). This gate is **identifier-scoped**: it flags a full-tier-set
restatement only where it is tied to the ``pack_level`` surface —

* the **annotation** of a field / variable / parameter named ``pack_level``, or
* a set / tuple / list / dict / ``Literal`` **bound to** a ``pack_level``-family
  name (``pack_level``, ``pack_levels``, ``PACK_LEVELS``, ``_PACK_LEVEL_*`` …).

A tier tuple bound to a non-level name is left to the tier-token gate, so the two
gates do not duplicate each other (see
:func:`test_gate_leaves_a_level_tuple_under_a_non_level_name_to_the_tier_gate`).

The canonical level tokens are read from the authority itself
(``frozenset(kernel.pack_tiers.PACK_TIERS)``), never hand-copied here — the gate
cannot drift from the thing it protects.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from kernel import pack_tiers

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_AUTHORITY_FILE = Path(pack_tiers.__file__).resolve()
_SRC_ROOT = _AUTHORITY_FILE.parents[1]  # src/

#: The descriptor module the ``pack_level`` field lives on — a non-vacuity anchor
#: specific to this gate (the scan must actually reach the field's home).
_DESCRIPTOR_FILE = _SRC_ROOT / "charter" / "offering" / "packs" / "pack_descriptor.py"

#: The canonical level tokens, read from the authority -- never hand-copied.
_LEVEL_TOKENS: frozenset[str] = frozenset(pack_tiers.PACK_TIERS)

#: Names that mark the ``pack_level`` vocabulary surface: the field/parameter
#: itself (``pack_level``) and any constant restating it (``PACK_LEVELS``,
#: ``_PACK_LEVEL_TOKENS`` …). Case-insensitive; a leading underscore is allowed.
_LEVEL_NAME_RE = re.compile(r"^_?pack_levels?$|^_?pack_level_[a-z0-9_]+$", re.IGNORECASE)

#: Non-vacuity floor: the packages the gate must reach. A scan that silently
#: stopped covering one of them (a moved root, a broken glob) fails loudly.
_REQUIRED_PACKAGES = frozenset({"charter", "specify_cli", "kernel", "glossary", "runtime", "mission_runtime"})
_MIN_FILES_SCANNED = 1000

#: Empty by policy (Stijn ratchet policy, 2026-09-30): the ``pack_level`` field
#: derives from the kernel authority from the first commit, so no file is
#: exempted. A new entry here is a regression, not a fix.
_ALLOWLIST: frozenset[str] = frozenset()

_COLLECTION_CTORS = frozenset({"frozenset", "set", "tuple", "list"})


def _is_level_name(name: str | None) -> bool:
    return name is not None and _LEVEL_NAME_RE.match(name) is not None


def _str_consts(elts: list[ast.expr]) -> set[str]:
    return {e.value for e in elts if isinstance(e, ast.Constant) and isinstance(e.value, str)}


def _display_elements(node: ast.expr) -> list[ast.expr] | None:
    """Return element nodes of a set/tuple/list display or a constructor over one."""
    if isinstance(node, (ast.Set, ast.Tuple, ast.List)):
        return list(node.elts)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _COLLECTION_CTORS
        and node.args
        and isinstance(node.args[0], (ast.Set, ast.List, ast.Tuple))
    ):
        return list(node.args[0].elts)
    return None


def _literal_restates_levels(node: ast.expr) -> bool:
    """True iff *node* is a ``Literal[...]`` whose string members cover every tier token."""
    if not isinstance(node, ast.Subscript):
        return False
    base = node.value
    base_name = base.id if isinstance(base, ast.Name) else base.attr if isinstance(base, ast.Attribute) else None
    if base_name != "Literal":
        return False
    slice_node = node.slice
    elts = list(slice_node.elts) if isinstance(slice_node, ast.Tuple) else [slice_node]
    return _str_consts(elts) >= _LEVEL_TOKENS


def _restates_levels(node: ast.expr) -> str | None:
    """Classify *node*; return a reason if it restates the full canonical tier set.

    A restatement is a ``Literal[...]`` alias, or a collection/dict display whose
    string constants (or keys) cover the FULL canonical tier set — never a scalar
    ``"built-in"`` marker, a ``PackTier`` reference, or a comprehension over the
    authority.
    """
    if _literal_restates_levels(node):
        return "Literal[...] restating the canonical tier set"

    members = _display_elements(node)
    if members is not None and _str_consts(members) >= _LEVEL_TOKENS:
        kind = type(node.args[0]).__name__ if isinstance(node, ast.Call) else type(node).__name__
        return f"{kind} display restating the canonical tier set"

    if isinstance(node, ast.Dict):
        keys = {k.value for k in node.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}
        if keys >= _LEVEL_TOKENS:
            return "dict display keyed by the canonical tier set"
    return None


def _candidates(tree: ast.AST) -> list[tuple[int, str, ast.expr]]:
    """Return ``(lineno, name, node)`` for every construct on the ``pack_level`` surface.

    A construct is on the surface when it is the annotation of a ``pack_level``
    field / variable / parameter, or a value bound to a ``pack_level``-family
    name. Each node is then classified by :func:`_restates_levels`.
    """
    found: list[tuple[int, str, ast.expr]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and _is_level_name(node.target.id):
            found.append((node.annotation.lineno, node.target.id, node.annotation))
            if node.value is not None:
                found.append((node.value.lineno, node.target.id, node.value))
        elif isinstance(node, ast.Assign):
            name = next((t.id for t in node.targets if isinstance(t, ast.Name) and _is_level_name(t.id)), None)
            if name is not None:
                found.append((node.value.lineno, name, node.value))
        elif isinstance(node, ast.arg) and _is_level_name(node.arg) and node.annotation is not None:
            found.append((node.annotation.lineno, node.arg, node.annotation))
    return found


def _scan_source(source: str, filename: str = "<planted>") -> list[tuple[int, str, str]]:
    """Return ``(lineno, name, reason)`` for every ``pack_level`` mirror in *source*."""
    tree = ast.parse(source, filename)
    findings: list[tuple[int, str, str]] = []
    for lineno, name, node in _candidates(tree):
        reason = _restates_levels(node)
        if reason is not None:
            findings.append((lineno, name, reason))
    return findings


def _scan_file(path: Path) -> list[tuple[int, str, str]]:
    return _scan_source(path.read_text(encoding="utf-8"), str(path))


def _scanned_files() -> list[Path]:
    return [path for path in sorted(_SRC_ROOT.rglob("*.py")) if path.resolve() != _AUTHORITY_FILE]


def test_no_hand_authored_pack_level_literal_under_src() -> None:
    violations: list[str] = []
    for path in _scanned_files():
        rel = path.relative_to(_SRC_ROOT.parent).as_posix()
        if rel in _ALLOWLIST:
            continue
        for lineno, name, reason in _scan_file(path):
            violations.append(f"{rel}:{lineno}  {name}: {reason}")

    assert not violations, (
        "The pack_level vocabulary must derive from the single kernel authority "
        "(src/kernel/pack_tiers.py) -- annotate the field `pack_level: PackTier` "
        "and reference PACK_TIERS / the token constants, never a hand-copied "
        "Literal or tier display. Offenders:\n  " + "\n  ".join(violations)
    )


def test_gate_reaches_the_descriptor_and_every_package() -> None:
    """Non-vacuity floor: the scan reaches the field's home and every package."""
    files = _scanned_files()
    assert _DESCRIPTOR_FILE.resolve() in {f.resolve() for f in files}, _DESCRIPTOR_FILE
    packages = {path.relative_to(_SRC_ROOT).parts[0] for path in files}
    assert packages >= _REQUIRED_PACKAGES, sorted(_REQUIRED_PACKAGES - packages)
    assert len(files) >= _MIN_FILES_SCANNED, len(files)


def test_allowlist_is_empty() -> None:
    """The gate closes with an empty allowlist (Stijn ratchet policy, 2026-09-30)."""
    assert frozenset() == _ALLOWLIST


@pytest.mark.parametrize(
    ("form", "template"),
    [
        ("field Literal annotation", "class D:\n    pack_level: Literal[{tokens}]\n"),
        ("parameter Literal annotation", "def f(pack_level: Literal[{tokens}]) -> None:\n    pass\n"),
        ("variable Literal annotation", "pack_level: Literal[{tokens}]\n"),
    ],
)
def test_gate_detects_a_planted_level_literal_annotation(form: str, template: str) -> None:
    """Self-mutation: a hand-authored ``pack_level`` Literal annotation is flagged."""
    tokens = ", ".join(f'"{t}"' for t in pack_tiers.PACK_TIERS)
    assert _scan_source(template.format(tokens=tokens)), f"gate must flag a {form}"


@pytest.mark.parametrize(
    ("form", "template"),
    [
        ("tuple", "PACK_LEVELS = ({tokens})\n"),
        ("set", "PACK_LEVELS = {{{tokens}}}\n"),
        ("list", "_PACK_LEVEL_TOKENS = [{tokens}]\n"),
        ("frozenset constructor", "PACK_LEVELS = frozenset([{tokens}])\n"),
    ],
)
def test_gate_detects_a_planted_level_named_display(form: str, template: str) -> None:
    """Self-mutation: a ``pack_level``-named tier display is flagged."""
    tokens = ", ".join(f'"{t}"' for t in pack_tiers.PACK_TIERS)
    assert _scan_source(template.format(tokens=tokens)), f"gate must flag a {form}"


def test_gate_detects_a_planted_level_named_map() -> None:
    """Self-mutation: a ``pack_level``-named dict keyed by the tier set is flagged."""
    pairs = ", ".join(f'"{t}": {i}' for i, t in enumerate(pack_tiers.PACK_TIERS))
    assert _scan_source("PACK_LEVEL_RANKS = {" + pairs + "}\n"), "gate must flag a level-keyed dict"


def test_gate_detects_a_mirror_in_a_function_body() -> None:
    """Self-mutation: a ``pack_level`` mirror is caught inside a function body too."""
    tokens = ", ".join(f'"{t}"' for t in pack_tiers.PACK_TIERS)
    source = f"def build():\n    pack_levels = ({tokens})\n    return pack_levels\n"
    assert _scan_source(source), "gate must flag a function-local level mirror"


def test_gate_leaves_the_derived_field_annotation_alone() -> None:
    """The form the gate asks for -- ``pack_level: PackTier`` -- is not flagged."""
    assert _scan_source("class D:\n    pack_level: PackTier\n") == []
    assert _scan_source("PACK_LEVELS = tuple(PACK_TIERS)\n") == []
    assert _scan_source("_LEVELS = frozenset(PACK_TIERS)\n") == []


def test_gate_leaves_a_scalar_and_subset_alone() -> None:
    """A scalar level marker or a two-token subset is not a full-set restatement."""
    assert _scan_source('pack_level = "built-in"\n') == []
    assert _scan_source('PACK_LEVELS = ("org", "project")\n') == []


def test_gate_leaves_a_level_tuple_under_a_non_level_name_to_the_tier_gate() -> None:
    """Non-duplication: a tier tuple NOT on the pack_level surface is out of scope.

    The generic, value-driven tier-token gate
    (``test_pack_tier_token_single_authority.py``) owns a tier-tuple restatement
    bound to any other name; this identifier-scoped gate deliberately leaves it
    alone so the two do not duplicate each other.
    """
    tokens = ", ".join(f'"{t}"' for t in pack_tiers.PACK_TIERS)
    assert _scan_source(f"TIER_RANKS = ({tokens})\n") == []
    assert _scan_source(f"def f(tier: Literal[{tokens}]) -> None:\n    pass\n") == []
