"""Totality guard for module-level dict tables keyed by ArtifactKind/NodeKind.

WP07 / T029-T030 (C-005, FR-012). This module supersedes the narrower subset
guard in ``test_nodekind_artifactkind.py::test_node_kind_remains_superset_of_artifact_kind``
(kept for its own regression value; not duplicated here).

Rationale: every time a new :class:`~charter.offering.artifact_kinds.ArtifactKind` /
:class:`~charter.offering.drg.models.NodeKind` member is added (this mission added
``TEMPLATE`` and ``ASSET``), any module-level dict table keyed by one of these
enums silently becomes a trap for the *next* new kind unless it is either:

1. **Total** -- an entry for every enum member, so a missing key is a
   ``KeyError`` (or, worse, a caught-and-swallowed bug) rather than a
   compile-time fact anyone can check; or
2. **An explicitly allow-listed `.get`-defaulted partial** -- every call site
   reads it via ``.get(kind, <safe-default>)``, so an absent key is a
   deliberate, safe fallback rather than an oversight.

Naive totality ("every such dict must have every key") is provably wrong: it
false-fails on four pre-existing, legitimately-partial tables
(``charter.activation.kind_vocabulary::_ID_FIELD_BY_KIND``/``_PROJECT_KIND_DIRS`` and
``charter.activation.pack_manager::_ID_FIELD_BY_KIND``/``_PROJECT_KIND_DIRS``). This guard
distinguishes the two cases via :data:`_EXEMPT_GET_PARTIALS`, an explicit
allow-list keyed by ``"<dotted.module>::<CONSTANT_NAME>"`` -- the exemption
mechanism chosen over an inline marker comment because it puts the entire
partial-tables surface in one auditable place (this file) rather than
scattered across the tree.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import pytest

from charter.offering.artifact_kinds import CHARTER_ACTIVATABLE_KINDS, ArtifactKind
from charter.offering.drg.models import NodeKind

pytestmark = [pytest.mark.doctrine, pytest.mark.fast]

_SRC_ROOT = Path(__file__).resolve().parents[3] / "src"

#: The two enum classes this guard understands. Keyed by the bare name used
#: in source (``ArtifactKind.FOO`` / ``NodeKind.FOO``) since the AST scan
#: works on unresolved names, not imported objects.
_ENUM_CLASSES: dict[str, type[Enum]] = {
    "ArtifactKind": ArtifactKind,
    "NodeKind": NodeKind,
}

#: Module-level dict tables keyed by ArtifactKind/NodeKind that are
#: intentionally partial: every call site reads them via ``.get(kind,
#: <default>)`` so a missing kind falls back safely rather than raising.
#: Entries are ``"<dotted.module.path>::<CONSTANT_NAME>"``, resolved from the
#: file path relative to ``src/``.
#:
#: Adding a new dict here is only correct when every read site is
#: `.get`-defaulted. If a read site does a plain ``table[kind]`` lookup,
#: the table must be made total instead of exempted.
_EXEMPT_GET_PARTIALS: frozenset[str] = frozenset(
    {
        # _id_field_for() / _declared_id() fall back to the "id" default field
        # for every kind that doesn't override it.
        "charter.activation.kind_vocabulary::_ID_FIELD_BY_KIND",
        "charter.activation.pack_manager::_ID_FIELD_BY_KIND",
        # NOTE (WP03 T014): the two charter `_PROJECT_KIND_DIRS` partials were
        # retired here -- both modules now import the single total authority
        # `charter.offering.artifact_kinds.PROJECT_KIND_DIRS` (guard-visible, total), so
        # there is no local partial left to exempt.
        # WP01 (doctrine-tension-edges-01KY1WPC) added ArtifactKind.ANTI_PATTERN.
        # The sole read site (`executor.py`'s step-contract kind resolution)
        # reads via `_ARTIFACT_TO_NODE_KIND.get(kind)` and treats a miss as
        # "no delegatable node kind" -- correct here, since an anti-pattern
        # node is never a mission-step-contract delegation target (D2).
        "specify_cli.mission_step_contracts.executor::_ARTIFACT_TO_NODE_KIND",
        # WP01 (deliver-loaded-doctrine): the delivery table's exclusion-reason
        # sidecar is a partial NodeKind map BY CONSTRUCTION -- it carries a
        # stated reason for every `slot=None` kind and nothing for the delivered
        # kinds. It is an audit sidecar to the total `_ACTION_BUNDLE_DELIVERY_BY_KIND`
        # (never read via a plain `[kind]` lookup on a delivered kind), and its
        # exact coverage of the None-slot set is machine-checked by
        # `tests/charter/test_action_bundle_delivery.py::
        # test_every_none_slot_kind_has_a_machine_checkable_stated_reason`, so a
        # future None row without a reason still reddens -- just there, not here.
        "charter.activation.context_renderers.delivery_table::_DELIVERY_REASON_BY_KIND",
        # WP03 (T016): the `doctrine new` scaffolder's per-kind stub table.
        # Intentionally partial -- `template` (empty glob, unscaffoldable),
        # `glossary_pack` and `anti_pattern` (hand-authored) carry no stub. The
        # sole read site (`new()` -> `_stub_template`) is gated by the
        # `_resolve_scaffoldable_kind` membership check, so a missing kind is a
        # deliberate "not scaffoldable" rejection, never a silent KeyError. This
        # table's keys ARE the set of scaffoldable kinds. It was formerly an
        # eight-arm if-chain no dict-scanning guard could see; converting it to a
        # dict makes the projection guard-visible (this exemption is the
        # documented reason it stays partial).
        "specify_cli.cli.commands.doctrine::_STUB_TEMPLATES",
        # M6 (#3038): the emittable-project-tier-kind allowlist. Its keys are the
        # kinds emitted as project-overlay DRG nodes (directive/tactic/styleguide/
        # agent_profile); every other kind's absence is contractual (asset stays
        # reference-only, procedure/paradigm/... are not emitted at the project
        # tier). The sole read site `_node_kind_for` reads it via `.get` and
        # treats a miss as "kind not emitted at project tier" -- a deliberate
        # partial. It is enum-keyed (not string-keyed) precisely so THIS guard is
        # guard-visible to it. Being exempt, this entry never reddens the
        # enum-keyed guard itself; the protection is indirect -- a future
        # ArtifactKind reddens the non-exempt authorities (PROJECT_KIND_DIRS et
        # al.), forcing a deliberate emit-or-not decision through the kind surface.
        "charter.activation.synthesizer.project_drg::_KIND_TO_NODE_KIND",
    }
)


@dataclass(frozen=True)
class _KindKeyedDict:
    """A discovered module-level dict literal keyed by an enum's members."""

    qualified_name: str
    enum_name: str
    keys: frozenset[str]
    lineno: int


def _dotted_module_name(path: Path) -> str:
    """Return the dotted import path of *path* relative to ``src/``."""
    parts = path.relative_to(_SRC_ROOT).with_suffix("").parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _enum_key(node: ast.expr) -> tuple[str, str] | None:
    """Return ``(EnumName, MEMBER)`` if *node* is an ``EnumName.MEMBER`` access."""
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in _ENUM_CLASSES:
        return node.value.id, node.attr
    return None


def _dict_target_and_value(stmt: ast.stmt) -> tuple[ast.Name, ast.expr] | None:
    """Return ``(target, value)`` for a module-level ``NAME = {...}`` / ``NAME: T = {...}``."""
    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
        return stmt.targets[0], stmt.value
    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value is not None:
        return stmt.target, stmt.value
    return None


def _kind_keyed_dicts_in_module(tree: ast.Module, module_name: str) -> list[_KindKeyedDict]:
    """Find module-level dict literals keyed entirely by one enum's members.

    Raises ``AssertionError`` (rather than silently skipping) if a dict mixes
    enum-keyed and non-enum-keyed entries, or keys from two different enums --
    an unrecognized shape this guard should be taught about explicitly, not
    paper over.
    """
    found: list[_KindKeyedDict] = []
    for stmt in tree.body:
        pair = _dict_target_and_value(stmt)
        if pair is None:
            continue
        target, value = pair
        if not isinstance(value, ast.Dict):
            continue
        resolved = [_enum_key(k) for k in value.keys if k is not None]
        matched = [m for m in resolved if m is not None]
        if not matched:
            continue  # Not an enum-keyed dict (e.g. `_PLURALS: dict[str, str]`).
        enum_names_seen = {m[0] for m in matched}
        if len(enum_names_seen) != 1 or len(matched) != len(value.keys):
            raise AssertionError(
                f"{module_name}::{target.id} (line {stmt.lineno}) mixes enum-keyed "
                "and non-enum-keyed (or multi-enum) dict entries; the totality "
                "guard does not understand this shape -- give it explicit handling."
            )
        found.append(
            _KindKeyedDict(
                qualified_name=f"{module_name}::{target.id}",
                enum_name=enum_names_seen.pop(),
                keys=frozenset(m[1] for m in matched),
                lineno=stmt.lineno,
            )
        )
    return found


def _discover_kind_keyed_dicts() -> list[_KindKeyedDict]:
    """Scan every ``src/**/*.py`` module for kind-enum-keyed dict literals."""
    found: list[_KindKeyedDict] = []
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        found.extend(_kind_keyed_dicts_in_module(tree, _dotted_module_name(path)))
    return found


def _missing_members(entry: _KindKeyedDict) -> set[str]:
    enum_cls = _ENUM_CLASSES[entry.enum_name]
    member_names = {member.name for member in enum_cls}
    return member_names - entry.keys


# ---------------------------------------------------------------------------
# T029 -- the totality guard itself
# ---------------------------------------------------------------------------


def test_kind_keyed_dicts_are_total_or_exempt() -> None:
    """Every ArtifactKind/NodeKind-keyed module dict must be total or exempt.

    Supersedes the narrower ``artifact_values <= node_values`` subset check:
    this asserts exhaustiveness of every *consumer* mapping table, not just
    that ``NodeKind`` is a superset of ``ArtifactKind``.
    """
    discovered = _discover_kind_keyed_dicts()
    # Sanity: the scan must actually find something, or this test would pass
    # vacuously if the AST-matching logic silently broke.
    assert discovered, "expected to discover at least one kind-keyed dict table"

    violations = [
        f"{entry.qualified_name} (line {entry.lineno}) is missing {sorted(_missing_members(entry))} and is not in _EXEMPT_GET_PARTIALS"
        for entry in discovered
        if entry.qualified_name not in _EXEMPT_GET_PARTIALS and _missing_members(entry)
    ]
    assert not violations, "\n".join(violations)


# ---------------------------------------------------------------------------
# T030 -- prove the four pre-existing `.get`-partials are exempted, not just
# asserted: they must (a) actually be discovered by the scan, and (b) actually
# be non-total, or the exemption is either vacuous or stale.
# ---------------------------------------------------------------------------


def test_authority_missing_a_member_is_flagged_by_the_guard() -> None:
    """T017: a future ArtifactKind added without a PROJECT_KIND_DIRS entry fails.

    Simulates the exact regression the hoist protects against: the authority
    dropping (or never gaining) an entry for a kind. Against a synthetic copy of
    the authority missing ``ASSET``, the discovery + totality building blocks
    must report it by name — the same machinery ``test_kind_keyed_dicts_are_
    total_or_exempt`` runs over the real ``PROJECT_KIND_DIRS`` (which, being
    string-keyed before WP03, no scan could have caught).
    """
    source = (
        "from charter.offering.artifact_kinds import ArtifactKind\n"
        "PROJECT_KIND_DIRS: dict[ArtifactKind, str] = {\n"
        + "".join(f"    ArtifactKind.{member.name}: 'x',\n" for member in ArtifactKind if member is not ArtifactKind.ASSET)
        + "}\n"
    )
    tree = ast.parse(source, filename="<synthetic-authority>")
    found = {entry.qualified_name: entry for entry in _kind_keyed_dicts_in_module(tree, "synthetic")}
    entry = found["synthetic::PROJECT_KIND_DIRS"]
    assert _missing_members(entry) == {"ASSET"}


def test_mixed_enum_and_plain_keys_raise_instead_of_silently_skipping() -> None:
    """An unrecognized dict shape must fail loudly, not be swallowed."""
    source = "from charter.offering.artifact_kinds import ArtifactKind\n_MIXED: dict = {\n    ArtifactKind.DIRECTIVE: 'x',\n    'plain-string-key': 'y',\n}\n"
    tree = ast.parse(source, filename="<synthetic>")
    with pytest.raises(AssertionError, match="mixes enum-keyed"):
        _kind_keyed_dicts_in_module(tree, "synthetic")


# ---------------------------------------------------------------------------
# WP05 / T025 -- STRING-KEYED kind-map coverage.
#
# The enum-keyed guard above is blind to string-keyed kind maps (keys are string
# literals, not ``ArtifactKind.MEMBER`` accesses). Those maps -- the artifact_kinds
# authority tables ``_PLURALS`` / ``_PATTERNS`` / ``_HAS_BUILT_IN_CONTENT_DIR`` --
# escaped totality entirely (the #2981 drift class: a copy silently missing a
# kind). (``charter.activation.synthesizer.project_drg._KIND_TO_NODE_KIND`` was also a
# string-keyed escapee until M6 (#3038) re-keyed it on ``ArtifactKind``; it is
# now covered by the enum-keyed guard above via ``_EXEMPT_GET_PARTIALS``.)
# This section extends the same AST machinery to string-keyed kind-map
# LITERALS: a module-level dict whose keys are all string constants drawn from
# the kind vocabulary. Such a map must be total over its key-family (all singular
# ArtifactKind values, or all plurals) unless it is an explicitly allow-listed
# intentional partial. (Collapsed authorities that are dict *comprehensions*, not
# literals -- e.g. ``CHARTER_ACTIVATABLE_SINGULAR_TO_PLURAL`` -- are ``ast.DictComp``
# nodes, not ``ast.Dict``, so they are naturally out of scope here and covered by
# their own WP03 tests.)
# ---------------------------------------------------------------------------

_KIND_SINGULARS: frozenset[str] = frozenset(kind.value for kind in ArtifactKind)
_KIND_PLURALS: frozenset[str] = frozenset(kind.plural for kind in ArtifactKind)

#: Minimum number of kind-token keys before a string-keyed dict is treated as a
#: kind map (avoids matching an incidental 1-2 entry dict that merely happens to
#: use a kind word as a key).
_MIN_STRING_KIND_KEYS = 3

#: String-keyed kind-map LITERALS that are the canonical kind *authorities* and
#: MUST therefore be total over every :class:`ArtifactKind` (a new kind added
#: without an entry here is a silent trap the enum-keyed guard cannot see because
#: the keys are strings). Keyed ``"<dotted.module>::<CONSTANT>"``.
#:
#: Scope note (no silent caps): the string-keyed scan *discovers* every string
#: kind-map literal in the tree, but many are legitimately partial consumer maps
#: (subsets of kinds for a specific purpose) -- forcing all of them total is out
#: of scope for M1 (that is the cascade/kind-admission work of M5/M6). This gate
#: enforces totality on the declared canonical authorities only; the broader
#: discovery is proven non-vacuous by
#: :func:`test_string_keyed_authority_maps_are_total` (the authorities are
#: discovered) and :func:`test_string_keyed_scan_flags_a_dropped_kind` (a
#: dropped kind is reported).
_STRING_KEYED_MUST_BE_TOTAL: frozenset[str] = frozenset(
    {
        "charter.offering.artifact_kinds::_PLURALS",
        "charter.offering.artifact_kinds::_PATTERNS",
        "charter.offering.artifact_kinds::_HAS_BUILT_IN_CONTENT_DIR",
    }
)


@dataclass(frozen=True)
class _StringKindKeyedDict:
    """A discovered module-level dict literal keyed by kind-token string constants."""

    qualified_name: str
    key_family: str  # "singular" | "plural"
    keys: frozenset[str]
    lineno: int


def _string_constant_keys(value: ast.Dict) -> list[str] | None:
    """Return the string-constant keys of *value*, or ``None`` if any key is not one."""
    keys: list[str] = []
    for key in value.keys:
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            keys.append(key.value)
        else:
            return None
    return keys


def _string_kind_keyed_dicts_in_module(tree: ast.Module, module_name: str) -> list[_StringKindKeyedDict]:
    """Find module-level dict literals keyed entirely by kind-token strings.

    A candidate is a dict all of whose keys are string constants and where at
    least :data:`_MIN_STRING_KIND_KEYS` of them are drawn from ONE key-family
    (all singular :class:`ArtifactKind` values, or all plurals). A dict that
    mixes singular and plural kind keys, or mixes kind and non-kind keys, is not
    a clean kind map and is skipped (the enum-keyed guard's mixed-shape rule has
    the analogous strictness).
    """
    found: list[_StringKindKeyedDict] = []
    for stmt in tree.body:
        pair = _dict_target_and_value(stmt)
        if pair is None:
            continue
        target, value = pair
        if not isinstance(value, ast.Dict):
            continue
        keys = _string_constant_keys(value)
        if keys is None or len(keys) < _MIN_STRING_KIND_KEYS:
            continue
        key_set = frozenset(keys)
        singular_hits = key_set & _KIND_SINGULARS
        plural_hits = key_set & _KIND_PLURALS
        # Require a homogeneous, fully-kind-token key set of one family.
        if key_set <= _KIND_SINGULARS and len(singular_hits) >= _MIN_STRING_KIND_KEYS:
            family = "singular"
        elif key_set <= _KIND_PLURALS and len(plural_hits) >= _MIN_STRING_KIND_KEYS:
            family = "plural"
        else:
            continue
        found.append(
            _StringKindKeyedDict(
                qualified_name=f"{module_name}::{target.id}",
                key_family=family,
                keys=key_set,
                lineno=stmt.lineno,
            )
        )
    return found


def _discover_string_kind_keyed_dicts() -> list[_StringKindKeyedDict]:
    found: list[_StringKindKeyedDict] = []
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        found.extend(_string_kind_keyed_dicts_in_module(tree, _dotted_module_name(path)))
    return found


def _string_missing_members(entry: _StringKindKeyedDict) -> set[str]:
    family = _KIND_SINGULARS if entry.key_family == "singular" else _KIND_PLURALS
    return set(family) - entry.keys


def test_string_keyed_authority_maps_are_total() -> None:
    """The canonical string-keyed kind authorities must be total over every kind.

    Catches the #2981 drift class at its source: a canonical authority table
    (``_PLURALS`` / ``_PATTERNS`` / ``_HAS_BUILT_IN_CONTENT_DIR``) silently
    missing a kind fails here, naming the missing kinds -- coverage the
    enum-keyed guard cannot provide because these maps are string-keyed.
    """
    by_name = {e.qualified_name: e for e in _discover_string_kind_keyed_dicts()}
    violations: list[str] = []
    for authority in _STRING_KEYED_MUST_BE_TOTAL:
        assert authority in by_name, f"authority {authority!r} was not discovered by the string-keyed scan (renamed/relocated? update _STRING_KEYED_MUST_BE_TOTAL)"
        missing = _string_missing_members(by_name[authority])
        if missing:
            violations.append(f"{authority} is missing {sorted(missing)}")
    assert not violations, "\n".join(violations)


#: Pre-existing charter ``plural↔singular`` kind-map literals that predate M1 and
#: sit outside its named scope. ``charter.drg::_SINGULAR_TO_PLURAL`` is a fifth
#: hand copy (identical 10 kinds to the derived authority) surfaced by the M1
#: review squad; it lives on the golden-adjacent DRG activation-filter path and
#: imports ``ArtifactKind`` via ``doctrine.api`` (a public-wheel boundary), so it
#: is left un-collapsed under C-004 discipline. Follow-up: collapse onto
#: :data:`charter.offering.artifact_kinds.CHARTER_ACTIVATABLE_SINGULAR_TO_PLURAL`.
_CHARTER_PLURAL_SINGULAR_LITERAL_EXEMPT: frozenset[str] = frozenset({"charter.offering.artifact_kinds::_PLURALS"})

#: The full charter-activatable singular→plural vocabulary (10 kinds). A literal
#: containing EVERY one of these pairs is a complete hand copy of the vocabulary
#: authority — the #2981 re-declaration class. A *partial* singular→plural map
#: (a directory/array map that merely uses some plurals as values, e.g.
#: ``_REFERENCE_KIND_DIRS``) is a legitimate consumer, not a vocabulary copy, and
#: is not flagged.
_FULL_ACTIVATABLE_SINGULAR_PLURAL_PAIRS: frozenset[tuple[str, str]] = frozenset((kind.value, kind.plural) for kind in CHARTER_ACTIVATABLE_KINDS)


def _plural_singular_kind_literals_in_module(tree: ast.Module, module_name: str) -> list[str]:
    """Return qualified names of dict literals that are a COMPLETE plural↔singular
    kind-vocabulary copy (contain every charter-activatable singular→plural pair).

    This is the #2981 re-declaration signature: a full hand copy of the derived
    vocabulary authority. Extra keys (e.g. a ``mission-type`` token) are tolerated
    so a copy carrying one is still recognised; partial maps are not flagged.
    """
    found: list[str] = []
    for stmt in tree.body:
        pair = _dict_target_and_value(stmt)
        if pair is None:
            continue
        target, value = pair
        if not isinstance(value, ast.Dict):
            continue
        pairs = {
            (key.value, val.value)
            for key, val in zip(value.keys, value.values, strict=True)
            if isinstance(key, ast.Constant) and isinstance(key.value, str) and isinstance(val, ast.Constant) and isinstance(val.value, str)
        }
        if pairs >= _FULL_ACTIVATABLE_SINGULAR_PLURAL_PAIRS:
            found.append(f"{module_name}::{target.id}")
    return found


def test_no_charter_module_redeclares_a_plural_singular_kind_literal() -> None:
    """The #2981 class is fail-loud: charter must DERIVE the plural↔singular map.

    A charter module that re-introduces a hand-copied plural↔singular kind-map
    literal (instead of importing the single derived authority) fails here —
    exactly the re-declaration class the enum-keyed guard and the authority-only
    string guard cannot catch. The one pre-existing copy is explicitly exempted
    with a documented follow-up; any NEW one reddens this test.
    """
    charter_root = _SRC_ROOT / "charter"
    offenders: list[str] = []
    for path in sorted(charter_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        offenders.extend(
            name for name in _plural_singular_kind_literals_in_module(tree, _dotted_module_name(path)) if name not in _CHARTER_PLURAL_SINGULAR_LITERAL_EXEMPT
        )
    assert not offenders, (
        "these charter modules re-declare a plural↔singular kind-map literal "
        "instead of importing charter.offering.artifact_kinds.CHARTER_ACTIVATABLE_"
        f"SINGULAR_TO_PLURAL (#2981 re-declaration class): {offenders}"
    )


def test_charter_plural_singular_literal_exemptions_are_real() -> None:
    """Each exempt pre-existing copy must actually be discovered (non-vacuous)."""
    charter_root = _SRC_ROOT / "charter"
    discovered: set[str] = set()
    for path in sorted(charter_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        discovered.update(_plural_singular_kind_literals_in_module(tree, _dotted_module_name(path)))
    for exempt in _CHARTER_PLURAL_SINGULAR_LITERAL_EXEMPT:
        assert exempt in discovered, f"exempt {exempt!r} not found -- collapsed already? drop the exemption"


def test_string_keyed_scan_flags_a_dropped_kind() -> None:
    """A synthetic singular-keyed map missing a kind is reported by name."""
    source = "_TABLE: dict[str, str] = {\n" + "".join(f"    {member.value!r}: 'x',\n" for member in ArtifactKind if member is not ArtifactKind.ASSET) + "}\n"
    tree = ast.parse(source, filename="<synthetic-string-map>")
    found = {e.qualified_name: e for e in _string_kind_keyed_dicts_in_module(tree, "synthetic")}
    entry = found["synthetic::_TABLE"]
    assert _string_missing_members(entry) == {ArtifactKind.ASSET.value}
