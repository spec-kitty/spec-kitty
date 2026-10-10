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
(``charter/offering/packs/pack_validator.py``'s plural→singular map) or inside a
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
* **R1' — padded universe literal** (#5823): the same universe-scale display
  (``>= 8`` kind-name string constants) tolerating a SINGLE non-kind padding
  string — the pack-layout dir set (8 plurals + ``"drg"``) and the selector set
  (8 singulars + ``"section"``) are exactly this shape and slipped past R1.
* **R2 — plural alias map**: a ``dict`` display with ``>= 8`` artifact-kind-name
  string *keys* and at least one artifact-kind-name string *value* (a
  kind→kind universe/alias map, e.g. the org-pack canonical-kind map).
* **R3 — singular→plural map**: a ``dict`` display, ``>= 2`` entries, where every
  string key is an artifact-kind **singular** and its value equals that kind's
  canonical **plural** — a restatement of the authority's own
  singular→plural relationship.
* **R4 — plural→glob map** (#5823): a ``dict`` display, ``>= 8`` entries, whose
  every string key is a kind **plural** and whose value equals that kind's
  ``glob_pattern`` — the pack-assembler's dirs/globs restatement.
* **R5 — operator-token→singular map** (#5823): a ``dict`` display, ``>= 8``
  entries, whose every string key is a kind **operator token** (the hyphenated
  CLI surface) mapping to that kind's canonical singular — the
  CLI-kind→DRG-singular restatement that R2 misses because hyphenated tokens are
  not kind *names*.
* **R6 — ArtifactKind→NodeKind identity map** (#5823): a ``dict`` display whose
  every key is an ``ArtifactKind`` member and every value a ``NodeKind`` member
  (attribute form ``ArtifactKind.X`` or constructor form ``ArtifactKind("x")``) —
  a per-member restatement of the kind↔node-kind identity.

Deliberately NOT flagged (a different concern, not the kind universe):
per-kind dispatch tables whose values are callables / ``NodeKind`` members /
``activated_<kind>`` field names keyed by non-kind strings (only the *keys* are
kinds, or only the values are node kinds — never both-as-members); small curated
plural subsets (``< 8``) used for ordered rendering; singular→singular subdir
maps; a ``str``→``NodeKind`` legacy-field map (keys are plural strings, not
``ArtifactKind`` members, so not R6); and a ``typing.Literal[...]`` kind alias
(its slice tuple cannot consume a derived ``frozenset``, so it is exempt — see
:func:`_literal_slice_tuples`). These do not restate the kind universe or any
authority-owned relationship, so they are not drift mirrors.
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

#: Authority relationships the dict rules check a literal's values against.
_PLURAL_TO_GLOB: dict[str, str] = {k.plural: k.glob_pattern for k in ArtifactKind}  # R4
_OPERATOR_TOKEN_TO_SINGULAR: dict[str, str] = {k.operator_token: k.value for k in ArtifactKind}  # R5

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


def _is_member_ref(node: ast.expr, enum_name: str) -> bool:
    """True iff *node* references a member of the enum called *enum_name*.

    Matches both the attribute form (``ArtifactKind.DIRECTIVE``) and the
    constructor-call form (``ArtifactKind("directive")``). Used by R6 to tell
    an ``ArtifactKind``→``NodeKind`` identity map (a kind-vocabulary mirror)
    from a dispatch table keyed by strings or valued by callables.
    """
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == enum_name:
        return True
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == enum_name


def _string_pairs(value: ast.Dict) -> list[tuple[str, str]]:
    """Return the ``(key, value)`` pairs of *value* whose key AND value are string constants."""
    return [
        (k.value, v.value)
        for k, v in zip(value.keys, value.values, strict=True)
        if isinstance(k, ast.Constant) and isinstance(v, ast.Constant) and isinstance(k.value, str) and isinstance(v.value, str)
    ]


def _violation(value: ast.expr) -> str | None:
    """Classify *value* (an assignment RHS); return a reason string if it is a mirror."""
    members = _display_elements(value)
    if members is not None:
        strings = _str_consts(members)
        # A universe-scale membership restatement: >= 8 of the 12 kinds appear
        # as string elements (singular OR plural — the plural forms name the
        # repository/universe axis, but a hand-authored singular universe set is
        # equally a mirror). R1' tolerates a SINGLE non-kind padding string
        # (``"drg"`` in the pack-layout dir set, ``"section"`` in the selector
        # set) that the #5409 R1 required to be absent.
        distinct = set(strings)
        kinds = {s for s in distinct if s in _KIND_NAMES}
        non_kind = len(distinct) - len(kinds)
        if len(kinds) >= _UNIVERSE_SCALE and non_kind <= 1:
            label = "R1 universe membership literal" if non_kind == 0 else "R1' padded universe membership literal"
            return f"{label} of {len(kinds)} kind names"

    if isinstance(value, ast.Dict):
        key_strings = [k.value for k in value.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)]
        val_strings = [v.value for v in value.values if isinstance(v, ast.Constant) and isinstance(v.value, str)]
        kind_keys = [s for s in key_strings if s in _KIND_NAMES]
        kind_vals = [s for s in val_strings if s in _KIND_NAMES]
        if len(kind_keys) >= _UNIVERSE_SCALE and kind_vals:
            return f"R2 kind→kind alias map with {len(kind_keys)} kind keys"
        # R3: every string key is a kind singular mapped to its canonical plural.
        if len(key_strings) >= 2 and all(k in _KIND_SINGULARS for k in key_strings):
            pairs = _string_pairs(value)
            if pairs and all(_SINGULAR_TO_PLURAL.get(k) == v for k, v in pairs):
                return f"R3 singular→plural map of {len(pairs)} kinds"
        # R4: a universe-scale plural→glob map whose every value equals that
        # kind's canonical ``glob_pattern`` (the pack-assembler dirs/globs map).
        if len(key_strings) >= _UNIVERSE_SCALE and all(k in _KIND_PLURALS for k in key_strings):
            pairs = _string_pairs(value)
            if len(pairs) == len(value.keys) and all(_PLURAL_TO_GLOB.get(k) == v for k, v in pairs):
                return f"R4 plural→glob map of {len(pairs)} kinds"
        # R5: a universe-scale operator-token→canonical-singular map (the
        # hyphenated CLI surface restated — the CLI-kind→DRG-singular map).
        if len(key_strings) >= _UNIVERSE_SCALE and all(k in _OPERATOR_TOKEN_TO_SINGULAR for k in key_strings):
            pairs = _string_pairs(value)
            if len(pairs) == len(value.keys) and all(_OPERATOR_TOKEN_TO_SINGULAR.get(k) == v for k, v in pairs):
                return f"R5 operator-token→singular map of {len(pairs)} kinds"
        # R6: an ``ArtifactKind``→``NodeKind`` identity map — keys are
        # ArtifactKind members, values NodeKind members (attribute or
        # constructor-call form). A dispatch table keyed by strings, or valued
        # by callables / field-name strings, is NOT this shape.
        keys_are_artifact_kinds = bool(value.keys) and all(k is not None and _is_member_ref(k, "ArtifactKind") for k in value.keys)
        vals_are_node_kinds = bool(value.values) and all(_is_member_ref(v, "NodeKind") for v in value.values)
        if keys_are_artifact_kinds and vals_are_node_kinds:
            return f"R6 ArtifactKind→NodeKind identity map of {len(value.keys)} kinds"
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


def _literal_slice_tuples(tree: ast.AST) -> set[int]:
    """Return the ``id()`` of every tuple that is the slice of a ``Literal[...]``.

    A ``typing.Literal[...]`` with two or more members carries an
    :class:`ast.Tuple` slice of string constants (e.g.
    ``Literal["directive", "tactic", "styleguide"]``). That tuple is a type
    alias, not a runtime collection — a ``Literal`` cannot consume a derived
    ``frozenset`` over ``ArtifactKind``, so it is the one display the gate must
    exempt rather than demand be migrated. Keyed by node identity so only the
    Literal's own slice is skipped, never an unrelated tuple at the same depth.
    """
    skip: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Subscript):
            continue
        base = node.value
        base_name = base.id if isinstance(base, ast.Name) else base.attr if isinstance(base, ast.Attribute) else None
        if base_name == "Literal" and isinstance(node.slice, ast.Tuple):
            skip.add(id(node.slice))
    return skip


def _scan_source(source: str, filename: str = "<planted>") -> list[tuple[int, str, str]]:
    """Return ``(lineno, name, reason)`` for every mirror display in *source*.

    Walks every expression node, so a display is classified wherever it sits:
    module or class attribute, function-local variable, or a bare ``return``
    / subscript display that is never bound to a name at all. The slice of a
    ``typing.Literal[...]`` kind alias is exempt (see
    :func:`_literal_slice_tuples`).
    """
    tree = ast.parse(source, filename)
    names = _assignment_names(tree)
    exempt = _literal_slice_tuples(tree)
    findings: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, _DISPLAY_NODES) or id(node) in exempt:
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
    assert packages >= _REQUIRED_PACKAGES, sorted(_REQUIRED_PACKAGES - packages)
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


# ---------------------------------------------------------------------------
# #5823: the five previously-unrecognised mirror shapes (R1' / R4 / R5 / R6),
# each with a red-first self-mutation test planting a mirror built from the
# authority and asserting the classifier flags it.
# ---------------------------------------------------------------------------


def test_gate_detects_a_padded_universe_set() -> None:
    """R1': a universe-scale membership set padded with one non-kind string.

    The #5409 R1 rule only caught a set whose every element is a kind name;
    a padded universe set (e.g. ``RECOGNISED_ARTIFACT_DIRS`` = the built-in
    content-dir plurals + ``"drg"``, ``_VALID_SELECTOR_KINDS`` = the
    activatable singulars + ``"section"``) carries one non-kind padding
    element, so it slipped through. R1' closes that. (Both live sites are now
    derived comprehensions, so this rule guards against a hand-authored
    regression rather than the live values.)
    """
    plurals = ", ".join(f'"{p}"' for p in sorted(_KIND_PLURALS))
    padded = "X = {" + plurals + ', "drg"}'
    assert _violation(ast.parse(padded).body[0].value) is not None, "R1' must flag a padded universe set"  # type: ignore[attr-defined]

    singulars = ", ".join(f'"{s}"' for s in sorted(_KIND_SINGULARS))
    padded_singular = "X = {" + singulars + ', "section"}'
    assert _violation(ast.parse(padded_singular).body[0].value) is not None, "R1' must flag a padded singular universe set"  # type: ignore[attr-defined]


def test_gate_detects_a_plural_to_glob_map() -> None:
    """R4: a plural→glob map whose values are each the kind's glob pattern."""
    pairs = ", ".join(f'"{k.plural}": "{k.glob_pattern}"' for k in ArtifactKind if k.has_built_in_content_dir)
    planted = "X = {" + pairs + "}"
    assert _violation(ast.parse(planted).body[0].value) is not None, "R4 must flag a plural→glob map"  # type: ignore[attr-defined]


def test_gate_detects_an_operator_token_to_singular_map() -> None:
    """R5: an operator-token→canonical-singular map (universe-scale restatement).

    Mirrors the live ``_CLI_KIND_TO_DRG_SINGULAR`` shape: the hyphenated
    operator tokens (``agent-profile``, ``mission-step-contract``,
    ``glossary-pack``) are NOT kind *names*, so fewer than eight bare kind
    names appear as keys and the #5409 R2 rule cannot see it — R5, which keys
    off the operator-token surface, must.
    """
    drg_kinds = [k for k in ArtifactKind if k not in {ArtifactKind.TEMPLATE, ArtifactKind.ASSET, ArtifactKind.ANTI_PATTERN, ArtifactKind.SKILL}]
    pairs = ", ".join(f'"{k.operator_token}": "{k.value}"' for k in drg_kinds)
    planted = "X = {" + pairs + "}"
    assert _violation(ast.parse(planted).body[0].value) is not None, "R5 must flag an operator-token→singular map"  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("form", "render"),
    [
        ("attribute", lambda k: f"ArtifactKind.{k.name}: NodeKind.{k.name}"),
        ("constructor-call", lambda k: f'ArtifactKind("{k.value}"): NodeKind("{k.value}")'),
    ],
)
def test_gate_detects_an_artifactkind_to_nodekind_map(form: str, render: object) -> None:
    """R6: an ``ArtifactKind``→``NodeKind`` identity map, attribute or call form."""
    pairs = ", ".join(render(k) for k in ArtifactKind if k not in {ArtifactKind.ANTI_PATTERN, ArtifactKind.SKILL})  # type: ignore[operator]
    planted = "X = {" + pairs + "}"
    assert _violation(ast.parse(planted).body[0].value) is not None, f"R6 must flag an ArtifactKind→NodeKind map ({form})"  # type: ignore[attr-defined]


def test_gate_leaves_legitimate_constructs_alone() -> None:
    """None of the known-good shapes are mirror literals (no false positives).

    Pins the tight scoping of R1'/R4/R5/R6 against the six shapes that look
    kind-adjacent but restate neither the kind universe nor a singular↔plural/
    glob/node-kind relationship the authority owns (#5823).
    """
    # DIRECT_WRITE_KINDS: a curated 5-tuple (< 8) — a selection, not a universe.
    direct_write = 'X = ("directive", "tactic", "styleguide", "procedure", "agent_profile")\n'
    assert _scan_source(direct_write) == [], "curated 5-tuple is not a universe restatement"

    # PROJECT_KIND_DIRS: the intentionally-total ArtifactKind→str directory map.
    project_dirs = "X = {" + ", ".join(f"ArtifactKind.{k.name}: {k.value!r}" for k in ArtifactKind) + "}\n"
    assert _scan_source(project_dirs) == [], "ArtifactKind→str dir map is not a kind-vocabulary mirror"

    # _KIND_BY_LEGACY_FIELD: a str(plural)→NodeKind map (NOT R6 — keys are strings).
    legacy = "X = {" + ", ".join(f"{k.plural!r}: NodeKind.{k.name}" for k in ArtifactKind) + "}\n"
    assert _scan_source(legacy) == [], "str→NodeKind map is not an ArtifactKind→NodeKind identity map"

    # typing.Literal[...] kind aliases: a Literal cannot consume a runtime
    # frozenset, so even an 8+-kind Literal slice is exempt (ast.Subscript).
    literal = "X = Literal[" + ", ".join(f'"{p}"' for p in sorted(_KIND_PLURALS)) + "]\n"
    assert _scan_source(literal) == [], "Literal[...] kind alias must be exempt"

    # Per-kind dispatch table: NodeKind values keyed by non-kind strings.
    dispatch = 'X = {"first": NodeKind.DIRECTIVE, "second": NodeKind.TACTIC, "third": NodeKind.STYLEGUIDE}\n'
    assert _scan_source(dispatch) == [], "a dispatch table keyed by non-kind strings is not a mirror"
