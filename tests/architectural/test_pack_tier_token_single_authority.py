"""Single-authority gate for the Charter Pack tier token (#5825 / #5961).

Why this gate exists
--------------------
The Charter Pack tier token (``built-in`` / ``org`` / ``project``) has exactly
one home: :mod:`kernel.pack_tiers` and its derived tables. Before WP04 the tier
tuple, the ``PackTier`` ``Literal`` and the per-tier layer-segment tuple were
hand-copied across ``charter.offering.pack_paths``, ``charter.offering.packs.presets``,
``charter.activation.pack_manager`` and the charter ``list`` command -- the exact
drift class #5825 / #5961 call out. Each mirror could silently diverge (a fourth
tier, a reordering, a dropped token) with nothing red.

This replaces that hand-copying with a **structural invariant**: no tier-token
*display* -- a ``Literal[...]`` type alias, or a set / tuple / list / dict
whose string constants (or keys) restate the full canonical tier tuple -- may
exist anywhere under ``src/`` outside :mod:`kernel.pack_tiers`. Every such
construct must instead *derive* from the authority (a reference to
``PACK_TIERS`` / ``PackTier`` / the token constants, or a comprehension over
them), so drift is impossible by construction.

The canonical token set is read from the authority itself
(``frozenset(kernel.pack_tiers.PACK_TIERS)``), never hand-copied here -- the gate
cannot drift from the thing it protects.

Scope -- the canonical ``"built-in"`` spelling only (NFR-003)
------------------------------------------------------------
The gate recognises a tier-token display only in the canonical **hyphenated**
spelling the authority enforces (``"built-in"``). The parallel no-hyphen
``"builtin"`` provenance/layer/rank vocabulary -- ``base.BaseArtifactRepository``'s
provenance value, ``agent_profiles``/``pack_skills`` rank maps and ``Tier``
alias, and the ``_charter_pack_health`` layer-order tuple -- is a
persisted-and-compared value frozen by NFR-003 (serialized into the charter
context JSON, compared in-memory by many out-of-scope consumers, pinned by that
spelling across the test suite). Those displays use ``"builtin"``, so they are
NOT tier-token restatements of this authority and are deliberately out of scope
(see :func:`test_gate_leaves_the_frozen_builtin_provenance_vocabulary_alone`).
The gate does not police them; folding that vocabulary onto the authority is a
separate, NFR-003-gated mission.

Per the ratchet policy (Stijn, 2026-09-30) this gate closes with an **empty
allowlist**: every canonical tier-token mirror was migrated in the WP04 mission
rather than grandfathered. A new entry here is a regression, not a fix.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kernel import pack_tiers

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_AUTHORITY_FILE = Path(pack_tiers.__file__).resolve()
_SRC_ROOT = _AUTHORITY_FILE.parents[1]  # src/

#: The canonical tier tokens, read from the authority -- never hand-copied.
_TIER_TOKENS: frozenset[str] = frozenset(pack_tiers.PACK_TIERS)

#: Non-vacuity floor: the packages the gate must reach. A scan that silently
#: stopped covering one of them (a moved root, a broken glob) fails loudly.
_REQUIRED_PACKAGES = frozenset({"charter", "specify_cli", "kernel", "glossary", "runtime", "mission_runtime"})
_MIN_FILES_SCANNED = 1000

#: Empty by policy (Stijn 2026-09-30): every canonical tier-token mirror was
#: migrated, so no file is exempted. A new entry here is a regression.
_ALLOWLIST: frozenset[str] = frozenset()

_COLLECTION_CTORS = frozenset({"frozenset", "set", "tuple", "list"})


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


def _literal_restates_tiers(node: ast.expr) -> bool:
    """True iff *node* is a ``Literal[...]`` whose string members cover every tier token."""
    if not isinstance(node, ast.Subscript):
        return False
    base = node.value
    base_name = base.id if isinstance(base, ast.Name) else base.attr if isinstance(base, ast.Attribute) else None
    if base_name != "Literal":
        return False
    slice_node = node.slice
    elts = list(slice_node.elts) if isinstance(slice_node, ast.Tuple) else [slice_node]
    return _str_consts(elts) >= _TIER_TOKENS


def _violation(node: ast.expr) -> str | None:
    """Classify *node*; return a reason if it restates the canonical tier tuple.

    A restatement is a display whose string constants (collection) or string
    keys (dict) cover the FULL canonical tier set, or a ``Literal[...]`` of the
    same -- never a scalar ``"built-in"`` marker, a two-token ``("org",
    "project")`` subset, or a ``"builtin"``-spelled display (a different,
    frozen vocabulary).
    """
    if _literal_restates_tiers(node):
        return "Literal[...] tier-token alias restating the canonical tier tuple"

    members = _display_elements(node)
    if members is not None and _str_consts(members) >= _TIER_TOKENS:
        kind = type(node.args[0]).__name__ if isinstance(node, ast.Call) else type(node).__name__
        return f"{kind} display restating the canonical tier tuple"

    if isinstance(node, ast.Dict):
        keys = {k.value for k in node.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}
        if keys >= _TIER_TOKENS:
            return "dict display keyed by the canonical tier tuple"
    return None


#: Displays reached by the walk. A constructor call wraps a display the walk
#: reaches on its own, so it is not re-classified as a Call here; a
#: ``Literal[...]`` is an ``ast.Subscript`` handled by ``_violation`` directly.
_DISPLAY_NODES = (ast.Set, ast.Tuple, ast.List, ast.Dict, ast.Subscript)


def _assignment_names(tree: ast.AST) -> dict[int, str]:
    names: dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            name = next((t.id for t in node.targets if isinstance(t, ast.Name)), None)
            value: ast.expr | None = node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            name = node.target.id if isinstance(node.target, ast.Name) else None
            value = node.value
        else:
            continue
        if name is None or value is None:
            continue
        names[id(value)] = name
    return names


def _scan_source(source: str, filename: str = "<planted>") -> list[tuple[int, str, str]]:
    """Return ``(lineno, name, reason)`` for every tier-token mirror in *source*."""
    tree = ast.parse(source, filename)
    names = _assignment_names(tree)
    findings: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, _DISPLAY_NODES):
            continue
        reason = _violation(node)
        if reason is None:
            continue
        findings.append((node.lineno, names.get(id(node), "<unbound display>"), reason))
    return findings


def _scan_file(path: Path) -> list[tuple[int, str, str]]:
    return _scan_source(path.read_text(encoding="utf-8"), str(path))


def _scanned_files() -> list[Path]:
    return [path for path in sorted(_SRC_ROOT.rglob("*.py")) if path.resolve() != _AUTHORITY_FILE]


def test_no_hand_authored_tier_token_literal_under_src() -> None:
    violations: list[str] = []
    for path in _scanned_files():
        rel = path.relative_to(_SRC_ROOT.parent).as_posix()
        if rel in _ALLOWLIST:
            continue
        for lineno, name, reason in _scan_file(path):
            violations.append(f"{rel}:{lineno}  {name}: {reason}")

    assert not violations, (
        "The Charter Pack tier token must derive from the single kernel authority "
        "(src/kernel/pack_tiers.py), never a hand-copied literal. Replace each with "
        "a reference to PACK_TIERS / PackTier / the token constants, or a "
        "comprehension over them. Offenders:\n  " + "\n  ".join(violations)
    )


def test_gate_reaches_every_package_under_src() -> None:
    """Non-vacuity floor: the scan covers every package and a real file count."""
    files = _scanned_files()
    packages = {path.relative_to(_SRC_ROOT).parts[0] for path in files}
    assert packages >= _REQUIRED_PACKAGES, sorted(_REQUIRED_PACKAGES - packages)
    assert len(files) >= _MIN_FILES_SCANNED, len(files)


def test_allowlist_is_empty() -> None:
    """The gate closes with an empty allowlist (Stijn ratchet policy, 2026-09-30)."""
    assert frozenset() == _ALLOWLIST


@pytest.mark.parametrize(
    ("form", "template"),
    [
        ("tuple display", "X = ({tokens})\n"),
        ("set display", "X = {{{tokens}}}\n"),
        ("list display", "X = [{tokens}]\n"),
        ("frozenset constructor", "X = frozenset([{tokens}])\n"),
    ],
)
def test_gate_detects_a_planted_tier_tuple(form: str, template: str) -> None:
    """Self-mutation: a hand-authored canonical tier-tuple display is flagged."""
    tokens = ", ".join(f'"{t}"' for t in pack_tiers.PACK_TIERS)
    assert _scan_source(template.format(tokens=tokens)), f"gate must flag a {form}"


def test_gate_detects_a_planted_literal_alias() -> None:
    """Self-mutation: a hand-authored ``Literal`` tier alias is flagged."""
    tokens = ", ".join(f'"{t}"' for t in pack_tiers.PACK_TIERS)
    assert _scan_source(f"X = Literal[{tokens}]\n"), "gate must flag a Literal tier alias"


def test_gate_detects_a_planted_rank_map() -> None:
    """Self-mutation: a dict keyed by the canonical tier tuple (a rank/identity map)."""
    pairs = ", ".join(f'"{t}": {i}' for i, t in enumerate(pack_tiers.PACK_TIERS))
    assert _scan_source("X = {" + pairs + "}\n"), "gate must flag a tier-keyed dict"


def test_gate_detects_a_mirror_at_any_depth() -> None:
    """A mirror is caught wherever it is written -- module, class, or function body."""
    tokens = ", ".join(f'"{t}"' for t in pack_tiers.PACK_TIERS)
    for scope, template in (
        ("module level", "X = ({tokens})\n"),
        ("class body", "class H:\n    X = ({tokens})\n"),
        ("function local", "def f():\n    x = ({tokens})\n    return x\n"),
        ("bare return", "def f():\n    return ({tokens})\n"),
    ):
        assert _scan_source(template.format(tokens=tokens)), f"gate must flag a {scope} mirror"


def test_gate_leaves_legitimate_constructs_alone() -> None:
    """No false positives on the kind-adjacent shapes that are NOT tier restatements."""
    # A scalar built-in marker (dir segment / layer tag / kwarg) is not a display.
    assert _scan_source('X = "built-in"\n') == []
    assert _scan_source('f(source_type="built-in")\n') == []
    # A two-token subset is a selection, not the full tier tuple.
    assert _scan_source('X = ("org", "project")\n') == []
    # A derived comprehension over the authority is the form the gate asks for.
    assert _scan_source("X = {t: t for t in PACK_TIERS}\n") == []
    assert _scan_source("X = tuple(PACK_TIERS)\n") == []


def test_gate_leaves_the_frozen_builtin_provenance_vocabulary_alone() -> None:
    """NFR-003: the no-hyphen ``"builtin"`` provenance vocabulary is out of scope.

    ``base``/``agent_profiles``/``pack_skills`` emit and compare a persisted
    ``"builtin"`` provenance/layer value frozen by NFR-003. Displays in that
    spelling are a different vocabulary -- not tier-token restatements of this
    authority -- so the gate must leave them alone, by construction.
    """
    assert _scan_source('X = ("builtin", "org", "project")\n') == []
    assert _scan_source('X = {"builtin": 0, "org": 1, "project": 2}\n') == []
    assert _scan_source('Tier = Literal["builtin", "org", "project"]\n') == []
    assert _scan_source('X = {"builtin", "org", "project"}\n') == []
