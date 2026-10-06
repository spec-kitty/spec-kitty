"""Single-authority gate for the doctrine artifact-kind vocabulary (#5409).

Why this gate exists
--------------------
The doctrine artifact-kind vocabulary (``directive``/``directives``, …,
``anti_pattern``/``anti_patterns``) has exactly one home: the
:class:`~charter.offering.artifact_kinds.ArtifactKind` enum and its derived
tables. Issue #5409 was a drift bug: the activation registry's ``_ALLOWED_KINDS``
was a hand-copied literal that omitted ``anti_patterns`` while the
authority-derived alias map advertised it — a self-contradicting rejection. The
kind vocabulary lived in several hand-kept lists that drifted apart, guarded
only by a brittle three-way equality assertion between three of the mirrors.

This replaces that drift guard with a **structural invariant**: no
kind-vocabulary *literal* may exist anywhere under ``src/`` outside
``artifact_kinds.py``. Every such set/map must instead be *derived* from
``ArtifactKind`` (a comprehension over the enum, or a reference to an
authority-owned constant), so drift is impossible by construction rather than
detected after the fact.

Per the ratchet policy (Stijn, 2026-09-30) this gate closes with an **empty
allowlist**: allowlist ratchets are expensive CI debt, so every mirror was
migrated in the #5409 mission rather than grandfathered.

Scope (#5538): the #5409 gate scanned only ``src/charter`` and only module- and
class-level assignments, so a mirror in a consumer package
(``specify_cli/doctrine/pack_validator.py``'s plural→singular map) or inside a
function body survived ungoverned. The gate now scans **every package under
``src/``** and **every collection display at any depth** — module, class,
function-local, and bare ``return``/subscript displays alike. A mirror cannot
escape by moving into a function. ``scripts/`` is not a package and stays out
of scope.

What counts as a forbidden "kind-vocabulary mirror literal"
-----------------------------------------------------------
Any collection display under ``src/`` (excluding ``artifact_kinds.py``) that is
one of:

* **R1 — universe membership literal**: a ``set`` / ``frozenset`` / ``tuple`` /
  ``list`` *display* — or a ``frozenset``/``set``/``tuple``/``list`` constructor
  call over one — whose string constants are ALL artifact-kind names (singular
  OR plural), with ``>= 8`` distinct (``8/12`` — a universe-scale restatement, as
  opposed to a small curated selection).
* **R2 — plural alias map**: a ``dict`` display with ``>= 8`` artifact-kind-name
  string *keys* and at least one artifact-kind-name string *value* (a
  kind→kind universe/alias map, e.g. the org-pack canonical-kind map).
* **R3 — singular→plural map**: a ``dict`` display, ``>= 2`` entries, where every
  string key is an artifact-kind **singular** and its value equals that kind's
  canonical **plural** — a restatement of the authority's own
  singular→plural relationship.

Deliberately NOT flagged (a different concern, not the kind universe):
per-kind dispatch tables whose values are callables / ``NodeKind`` members /
``activated_<kind>`` field names (only the *keys* are kinds); small curated
plural subsets (``< 8``) used for ordered rendering; and singular→singular
subdir maps. These do not restate the kind universe or its singular↔plural
relationship, so they are not drift mirrors. Known shapes the rules do not yet
recognise (hyphenated operator-token maps, ``ArtifactKind``→``NodeKind``
identity maps, glob-valued maps, universe sets padded with one non-kind
string) are tracked as a follow-up rather than allowlisted here.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from charter.offering import artifact_kinds
from charter.offering.artifact_kinds import ArtifactKind

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

_SRC_ROOT = Path(artifact_kinds.__file__).resolve().parents[2]  # src/
_AUTHORITY_FILE = Path(artifact_kinds.__file__).resolve()

#: Non-vacuity floor: the packages the gate must reach. A scan that silently
#: stopped covering one of them (a moved root, a broken glob) fails loudly
#: instead of passing over nothing.
_REQUIRED_PACKAGES = frozenset({"charter", "specify_cli", "kernel", "glossary", "runtime", "mission_runtime"})
_MIN_FILES_SCANNED = 1000

_KIND_SINGULARS: frozenset[str] = frozenset(k.value for k in ArtifactKind)
_KIND_PLURALS: frozenset[str] = frozenset(k.plural for k in ArtifactKind)
_KIND_NAMES: frozenset[str] = _KIND_SINGULARS | _KIND_PLURALS
_SINGULAR_TO_PLURAL: dict[str, str] = {k.value: k.plural for k in ArtifactKind}

_UNIVERSE_SCALE = 8  # 8 of 12 kinds -> a universe restatement, not a curated subset

#: Empty by policy (Stijn 2026-09-30): every mirror was migrated, so no file is
#: exempted. A new entry here is a regression, not a fix.
_ALLOWLIST: frozenset[str] = frozenset()


def _str_consts(elts: list[ast.expr]) -> list[str]:
    return [e.value for e in elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]


_COLLECTION_CTORS = frozenset({"frozenset", "set", "tuple", "list"})


def _display_elements(node: ast.expr) -> list[ast.expr] | None:
    """Return the element nodes of a set/tuple/list display or a
    ``frozenset``/``set``/``tuple``/``list`` constructor call over a display."""
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


def _violation(value: ast.expr) -> str | None:
    """Classify *value* (an assignment RHS); return a reason string if it is a mirror."""
    members = _display_elements(value)
    if members is not None:
        strings = _str_consts(members)
        # A universe-scale membership restatement: every string element is an
        # artifact-kind name (singular OR plural — the plural forms name the
        # repository/universe axis, but a hand-authored singular universe set is
        # equally a mirror) and >= 8 of the 12 kinds appear.
        kinds = {s for s in strings if s in _KIND_NAMES}
        if len(kinds) >= _UNIVERSE_SCALE and len(kinds) == len(set(strings)):
            return f"R1 universe membership literal of {len(kinds)} kind names"

    if isinstance(value, ast.Dict):
        key_strings = [k.value for k in value.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)]
        val_strings = [v.value for v in value.values if isinstance(v, ast.Constant) and isinstance(v.value, str)]
        kind_keys = [s for s in key_strings if s in _KIND_NAMES]
        kind_vals = [s for s in val_strings if s in _KIND_NAMES]
        if len(kind_keys) >= _UNIVERSE_SCALE and kind_vals:
            return f"R2 kind→kind alias map with {len(kind_keys)} kind keys"
        # R3: every string key is a kind singular mapped to its canonical plural.
        if len(key_strings) >= 2 and all(k in _KIND_SINGULARS for k in key_strings):
            pairs = [
                (k.value, v.value)
                for k, v in zip(value.keys, value.values, strict=True)
                if isinstance(k, ast.Constant) and isinstance(v, ast.Constant) and isinstance(k.value, str) and isinstance(v.value, str)
            ]
            if pairs and all(_SINGULAR_TO_PLURAL.get(k) == v for k, v in pairs):
                return f"R3 singular→plural map of {len(pairs)} kinds"
    return None


def _assignment_names(tree: ast.AST) -> dict[int, str]:
    """Map the ``id()`` of each assigned value node to its target name."""
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
        # ``frozenset({...})``: the display inside the constructor is the node
        # the walk classifies, so bind the name to it as well.
        if isinstance(value, ast.Call) and value.args:
            names[id(value.args[0])] = name
    return names


#: Constructor calls are not walked separately: the display they wrap is
#: reached by the walk on its own, so classifying both would double-report.
_DISPLAY_NODES = (ast.Set, ast.Tuple, ast.List, ast.Dict)


def _scan_source(source: str, filename: str = "<planted>") -> list[tuple[int, str, str]]:
    """Return ``(lineno, name, reason)`` for every mirror display in *source*.

    Walks every expression node, so a display is classified wherever it sits:
    module or class attribute, function-local variable, or a bare ``return``
    / subscript display that is never bound to a name at all.
    """
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


def test_no_hand_authored_kind_vocabulary_literal_under_src() -> None:
    violations: list[str] = []
    for path in _scanned_files():
        rel = path.relative_to(_SRC_ROOT.parent).as_posix()
        if rel in _ALLOWLIST:
            continue
        for lineno, name, reason in _scan_file(path):
            violations.append(f"{rel}:{lineno}  {name}: {reason}")

    assert not violations, (
        "Artifact-kind vocabulary must derive from the single ArtifactKind "
        "authority (src/charter/offering/artifact_kinds.py), never a hand-copied "
        "literal. Replace each with a comprehension over ArtifactKind or a "
        "reference to an authority-owned constant. Offenders:\n  " + "\n  ".join(violations)
    )


def test_gate_reaches_every_package_under_src() -> None:
    """Non-vacuity floor: the scan covers every package and a real file count."""
    files = _scanned_files()
    packages = {path.relative_to(_SRC_ROOT).parts[0] for path in files}
    assert _REQUIRED_PACKAGES <= packages, sorted(_REQUIRED_PACKAGES - packages)
    assert len(files) >= _MIN_FILES_SCANNED, len(files)


def test_allowlist_is_empty() -> None:
    """The gate closes with an empty allowlist (Stijn ratchet policy, 2026-09-30)."""
    assert frozenset() == _ALLOWLIST


@pytest.mark.parametrize(
    ("form", "names"),
    [
        ("plural display set", sorted(_KIND_PLURALS)),
        ("singular display set", sorted(_KIND_SINGULARS)),
    ],
)
def test_gate_detects_a_planted_membership_literal(form: str, names: list[str]) -> None:
    """Self-mutation: the classifier flags a hand-authored universe literal.

    Both the plural (repository/universe) axis and a singular restatement are
    caught — the #5409 drift was a plural display missing one kind, but a
    singular universe set is an equally forbidden mirror.
    """
    planted = "X = {" + ", ".join(f'"{n}"' for n in names) + "}"
    value = ast.parse(planted).body[0].value  # type: ignore[attr-defined]
    assert _violation(value) is not None, f"gate must flag an all-kind {form}"


def test_gate_detects_planted_constructor_and_singular_to_plural_map() -> None:
    """Self-mutation: constructor-call form and a singular→plural map are caught."""
    ctor = "X = frozenset([" + ", ".join(f'"{p}"' for p in sorted(_KIND_PLURALS)) + "])"
    assert _violation(ast.parse(ctor).body[0].value) is not None  # type: ignore[attr-defined]

    pairs = ", ".join(f'"{k.value}": "{k.plural}"' for k in ArtifactKind if k.activatable)
    s2p = "X = {" + pairs + "}"
    assert _violation(ast.parse(s2p).body[0].value) is not None  # type: ignore[attr-defined]


def _planted_plural_to_singular_map() -> str:
    pairs = ", ".join(f'"{k.plural}": "{k.value}"' for k in ArtifactKind if k.activatable)
    return "{" + pairs + "}"


@pytest.mark.parametrize(
    ("scope", "template"),
    [
        ("module level", "MAPPING = {display}\n"),
        ("class body", "class Holder:\n    MAPPING = {display}\n"),
        ("function local", "def lookup(plural):\n    mapping = {display}\n    return mapping.get(plural)\n"),
        ("bare return", "def lookup():\n    return {display}\n"),
        ("subscripted display", "def lookup(plural):\n    return {display}[plural]\n"),
    ],
)
def test_gate_detects_a_mirror_at_any_depth(scope: str, template: str) -> None:
    """Self-mutation (#5538): a mirror is caught wherever it is written.

    The #5538 mirror was a function-local dict, the one placement the #5409
    gate skipped. Each placement here must be flagged.
    """
    source = template.format(display=_planted_plural_to_singular_map())
    assert _scan_source(source), f"gate must flag a {scope} mirror"


def test_gate_leaves_a_derived_map_alone() -> None:
    """The derived form the gate asks for is not itself flagged."""
    source = "MAPPING = {k.plural: k.value for k in ArtifactKind}\n"
    assert _scan_source(source) == []
