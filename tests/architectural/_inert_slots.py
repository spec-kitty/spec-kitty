"""Checker behind ``test_no_inert_schema_slots`` — declared slots with no producer.

This module is the single home of the definition: a *slot* is a key under a
schema ``properties:`` mapping or a Pydantic ``models.py`` field in the doctrine
tree, and it is *inert* when no shipped artefact or doctrine code writes it.
``tests/architectural/test_no_inert_schema_slots.py`` only runs the gate.

The three rules that carry all the weight, restated because getting any of them
wrong silently empties the report:

1. A schema ``definitions/`` entry is **not** a slot — it is a ``$ref`` target. Only
   keys under a ``properties:`` mapping are slots, wherever that mapping appears
   (including inside a ``definitions/`` entry, whose properties *are* places data
   goes).
2. The generated schemas are **not** producers. They are the thing being checked.
3. A class-body annotated assignment is a *declaration*, not a production. Counting
   it as a producer would make every model field its own producer — the same
   by-construction vacuity as rule 2.

Reader/writer asymmetry falls out of the AST rules: ``cfg["x"] = v`` is a store
target and produces ``x``; ``cfg["x"]`` and ``cfg.get("x")`` are loads and produce
nothing.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import yaml

__all__ = [
    "BASELINE_PATH",
    "BASELINE_SLOTS",
    "DISPOSITIONS",
    "MINIMUM_MODEL_SLOT_NAMES",
    "MINIMUM_SCHEMA_SLOT_NAMES",
    "Baseline",
    "BaselineEntry",
    "BaselineError",
    "InertSlot",
    "find_inert_slots",
    "is_schema_declared",
    "load_baseline",
    "ratchet",
    "scanned_slots",
]

_SRC = "src"
#: Relocated doctrine source root (mission ``charter-code-topology-01M152G1``):
#: ``src/doctrine/`` moved to ``src/charter/offering/``; ``src/doctrine.py`` is
#: a legacy-import compat shim (a module, not a package) and carries no
#: schemas, models, or templates of its own.
_CHARTER = "charter"
_OFFERING = "offering"
_PACKS = "packs"
_BUILT_IN = "built-in"
_SCHEMAS = "schemas"
_SCHEMA_GLOB = "*.schema.yaml"
_MODELS_FILENAME = "models.py"
_PROPERTIES_KEY = "properties"
_ARTEFACT_SUFFIXES = frozenset({".yaml", ".yml", ".json"})
_PYDANTIC_BASE = "BaseModel"
_PYDANTIC_CONFIG_FIELD = "model_config"

#: Schemas this module structurally cannot assess, so their slots are never
#: harvested at all. ``occurrence-map.schema.yaml`` describes
#: ``occurrence_map.yaml`` — a per-MISSION planning artifact authored under
#: ``kitty-specs/<mission>/`` (see ``specify_cli.bulk_edit.occurrence_map``).
#: That directory is outside the src-only producer scope this checker walks
#: (``_producer_roots``: ``src/doctrine/`` and ``packs/built-in/``), and it
#: always will be — occurrence maps are not shipped doctrine artefacts, they
#: are mission-scoped classification documents. No schema property here can
#: ever be seen as "populated": the checker is not looking in the one place
#: a producer could exist. That is a scope mismatch in the checker, not a
#: property of the schema, so the fix is this exclusion rather than a
#: baseline row — the baseline's own header reserves rows for genuine debt
#: with a structural fix; a false positive from checker scope is
#: ``fix-the-lint-definition``, and this constant IS that fix. (Adjudicated
#: for the schema's `from`/`moves`/`to` properties in
#: ``doctrine-silence-guards-01KYFV7Q``; ``structural_targets`` — added by a
#: later PR — is the same class of false positive, not a new kind of debt.)
_NON_DOCTRINE_SCHEMAS = frozenset({"occurrence-map.schema.yaml"})


def _load_keys_verbatim(text: str) -> list[object]:
    """Parse YAML with every scalar left as its source token.

    ``safe_load`` applies YAML 1.1 implicit typing, which turns a key named ``on``
    into the boolean ``True`` — a slot named ``on`` would then be reported as
    ``True`` and, worse, would fail to match an artefact that authors the same key
    under a different spelling (``yes``, ``On``). Key harvesting wants the token.
    ``BaseLoader`` constructs strings only, so it is as safe as ``safe_load``.
    """
    return list(yaml.load_all(text, Loader=yaml.BaseLoader))


@dataclass(frozen=True)
class InertSlot:
    """A declared slot that nothing in the tree populates."""

    name: str
    declared_at: Path


# --------------------------------------------------------------------------- slots


def _iter_schema_slot_names(node: object) -> Iterator[str]:
    """Yield every key under a ``properties:`` mapping, at any depth.

    Definition *names* are never yielded: they are only reached as keys of
    ``definitions``, which this never harvests. The properties *inside* a
    definition are yielded — they are real places data goes.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            if key == _PROPERTIES_KEY and isinstance(value, dict):
                yield from (str(name) for name in value)
            yield from _iter_schema_slot_names(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_schema_slot_names(item)


def _schema_slots(root: Path) -> Iterator[InertSlot]:
    schemas = root / _SRC / _CHARTER / _OFFERING / _SCHEMAS
    for path in sorted(schemas.glob(_SCHEMA_GLOB)):
        if path.name in _NON_DOCTRINE_SCHEMAS:
            continue
        for document in _load_keys_verbatim(path.read_text(encoding="utf-8")):
            for name in _iter_schema_slot_names(document):
                yield InertSlot(name=name, declared_at=path.relative_to(root))


def _pydantic_model_classes(tree: ast.Module) -> Iterator[ast.ClassDef]:
    """Yield classes that are Pydantic models, following in-file subclassing."""
    model_names: set[str] = {_PYDANTIC_BASE}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if any(_base_name(base) in model_names for base in node.bases):
            model_names.add(node.name)
            yield node


def _base_name(base: ast.expr) -> str | None:
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    return None


def _iter_model_field_names(tree: ast.Module) -> Iterator[str]:
    for class_def in _pydantic_model_classes(tree):
        for statement in class_def.body:
            if not isinstance(statement, ast.AnnAssign):
                continue
            if not isinstance(statement.target, ast.Name):
                continue
            name = statement.target.id
            if name.startswith("_") or name == _PYDANTIC_CONFIG_FIELD:
                continue
            yield name


def _model_slots(root: Path) -> Iterator[InertSlot]:
    doctrine = root / _SRC / _CHARTER / _OFFERING
    if not doctrine.is_dir():
        return
    for path in sorted(doctrine.rglob(_MODELS_FILENAME)):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for name in _iter_model_field_names(tree):
            yield InertSlot(name=name, declared_at=path.relative_to(root))


# ----------------------------------------------------------------------- producers


def _producer_roots(root: Path) -> list[Path]:
    """Directories that make up the doctrine tree for producer harvesting.

    Two roots, both the doctrine layer proper. Mission
    ``relocate-builtin-doctrine-packs-01KYT87F`` relocated the shipped built-in
    *artefacts* (and the ``docs_structural_lint.py`` code producer) out of
    ``src/doctrine/<kind>/built-in/`` into a flattened ``packs/built-in/<kind>/``;
    the ``schemas/``, ``models.py``, ``templates/`` and the remaining ``.py`` code
    stayed under ``src/doctrine/``. Producers therefore live in *both* trees now, so
    both are walked.

    This is emphatically **not** the whole-``src`` widening the docstring warns
    against. That hole (bare-name collisions from unrelated CLI code masking a
    doctrine slot — it defeated the ``aliases``/``overrides`` guards) came from
    harvesting all of ``src/``. ``packs/built-in`` is where the doctrine artefacts
    now physically live; scanning it restores the *same* producer set the move
    displaced, no more. The slot walks are deliberately left pointed at
    ``src/charter/offering/`` alone — schemas and models did not move relative
    to each other, only the whole doctrine tree relocated wholesale from
    ``src/doctrine/`` to ``src/charter/offering/`` (mission
    ``charter-code-topology-01M152G1``).
    """
    candidates = (root / _SRC / _CHARTER / _OFFERING, root / _PACKS / _BUILT_IN)
    return [base for base in candidates if base.is_dir()]


def _iter_mapping_keys(node: object) -> Iterator[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            yield str(key)
            yield from _iter_mapping_keys(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_mapping_keys(item)


def _artefact_producers(root: Path) -> set[str]:
    """Keys carried by shipped doctrine artefacts — the dominant producer form here.

    Walks both doctrine roots (see :func:`_producer_roots`) — the artefacts now live
    under ``packs/built-in/`` after the relocation, while a few still-authored trees
    (missions, templates, workflows, the routing catalog) remain under
    ``src/charter/offering/``. Excludes ``src/charter/offering/schemas/``: the
    generated schemas are what is being checked, and admitting them makes every
    schema property self-producing.
    """
    schemas = root / _SRC / _CHARTER / _OFFERING / _SCHEMAS
    produced: set[str] = set()
    for base in _producer_roots(root):
        for path in sorted(base.rglob("*")):
            if path.suffix not in _ARTEFACT_SUFFIXES or schemas in path.parents:
                continue
            for document in _load_keys_verbatim(path.read_text(encoding="utf-8")):
                produced.update(_iter_mapping_keys(document))
    return produced


def _target_names(target: ast.expr) -> Iterator[str]:
    """Names written by an assignment target — stores only, never loads."""
    if isinstance(target, ast.Name):
        yield target.id
    elif isinstance(target, ast.Attribute):
        yield target.attr
    elif isinstance(target, ast.Subscript):
        key = target.slice
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            yield key.value
    elif isinstance(target, ast.Starred):
        yield from _target_names(target.value)
    elif isinstance(target, ast.Tuple | ast.List):
        for element in target.elts:
            yield from _target_names(element)


def _declaration_nodes(tree: ast.Module) -> set[int]:
    """Class-body annotated assignments: declarations, not productions (rule 3)."""
    declared: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            declared.update(id(statement) for statement in node.body if isinstance(statement, ast.AnnAssign))
    return declared


def _iter_code_producer_names(tree: ast.Module) -> Iterator[str]:
    declarations = _declaration_nodes(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                yield from _target_names(target)
        elif isinstance(node, ast.AugAssign | ast.AnnAssign) and id(node) not in declarations:
            # ``declarations`` only ever holds ``AnnAssign`` ids, so the membership
            # test is a no-op for ``AugAssign`` and the two branches are one rule.
            yield from _target_names(node.target)
        elif isinstance(node, ast.Call):
            yield from (kw.arg for kw in node.keywords if kw.arg is not None)
        elif isinstance(node, ast.Dict):
            yield from (key.value for key in node.keys if isinstance(key, ast.Constant) and isinstance(key.value, str))


def _code_producers(root: Path) -> set[str]:
    """Names written by code **in the doctrine tree** — the tree the slots live in.

    Scoped to ``src/doctrine/`` rather than all of ``src/``, and that scope is
    load-bearing rather than a tidiness preference. Matching is by bare name with
    no namespacing, so a wider scan means any unrelated local variable anywhere in
    the CLI masks a doctrine slot of the same name. Whole-``src`` harvesting
    produced 12,742 names against 807 here, and among the 11,935 it added were
    ``aliases`` and ``overrides`` — i.e. it defeated SC-001's ``aliases`` guard
    outright and hid half of the FR-028 ``enhances``/``overrides`` pair. Widening
    this back is not a refactor; it is a hole.

    Both doctrine roots are walked (see :func:`_producer_roots`): the
    ``docs_structural_lint.py`` code producer relocated to ``packs/built-in/assets/``,
    while the rest of the doctrine ``.py`` code stayed under ``src/doctrine/``.
    ``packs/built-in`` is the doctrine layer's new home, not the whole-``src``
    widening the paragraph above forbids.
    """
    produced: set[str] = set()
    for base in _producer_roots(root):
        for path in sorted(base.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            produced.update(_iter_code_producer_names(tree))
    return produced


# ------------------------------------------------------------------------- the gate


def scanned_slots(root: Path) -> set[InertSlot]:
    """Every slot the walk finds under *root*, before producers are considered.

    Exposed so the concrete floor can pin that the scan saw the tree at all. The
    findings list cannot do that job: it is empty both when the tree is clean and
    when the walk found nothing.
    """
    return {*_schema_slots(root), *_model_slots(root)}


def _unproduced(slots: set[InertSlot], producers: set[str]) -> list[InertSlot]:
    """Slots *producers* does not cover, deterministically ordered."""
    return sorted(
        (slot for slot in slots if slot.name not in producers),
        key=lambda slot: (slot.name, str(slot.declared_at)),
    )


def find_inert_slots(root: Path) -> list[InertSlot]:
    """Return every declared slot under *root* that no producer populates.

    Deterministic and sorted by ``(name, declared_at)``. Works against an arbitrary
    tree — the non-vacuity test points it at a planted ``tmp_path``, which is the
    only reason that test proves anything about the shipped-tree assertion.
    """
    producers = _artefact_producers(root) | _code_producers(root)
    return _unproduced(scanned_slots(root), producers)


# ------------------------------------------------- the frozen shrink-only baseline
#
# The baseline is debt, not an exemption: every row carries a structural
# disposition that clears it. See the baseline file's header.

BASELINE_PATH = Path(__file__).with_name("_inert_slots_baseline.yaml")

#: Exactly three structural answers. There is deliberately no ``accepted``, no
#: ``wont-fix``, no ``by-design`` — "leave it alone" is not a disposition.
DISPOSITIONS = frozenset({"wire-the-producer", "delete-the-declaration", "fix-the-lint-definition"})

#: Concrete floors (charter §5, ``architectural-gate-non-vacuity`` failure mode #1).
#: The shipped-tree assertion in this gate is an *absence* assertion (``new ==
#: []``), so it passes on a scan that saw nothing at all.
#:
#: **Floored per walk, deliberately.** A single union floor caught total collapse
#: and missed *partial* collapse: renaming the ``models.py`` convention kills the
#: model walk entirely, and the surviving schema side alone cleared a union floor
#: calibrated as a round fraction of the total. Review disproved the union floor
#: with a four-line mutation.
#:
#: The floors are absolute: they pin each walk against wholesale collapse (a
#: renamed convention, a moved directory) and have no reason to track the
#: baseline file's size. ``test_live_scan_meets_per_walk_floors`` checks them
#: through the real :func:`scanned_slots` walk.
MINIMUM_SCHEMA_SLOT_NAMES = 150
MINIMUM_MODEL_SLOT_NAMES = 120


class BaselineError(ValueError):
    """The baseline file is malformed. Fail loud: a silently-skipped entry is a hole."""


@dataclass(frozen=True)
class BaselineEntry:
    """One frozen finding: what it is and how it must be cleared."""

    name: str
    declared_at: Path
    disposition: str
    note: str

    @property
    def slot(self) -> InertSlot:
        return InertSlot(name=self.name, declared_at=self.declared_at)


@dataclass(frozen=True)
class Baseline:
    """The parsed baseline file."""

    entries: tuple[BaselineEntry, ...]

    @property
    def slots(self) -> frozenset[InertSlot]:
        return frozenset(entry.slot for entry in self.entries)


def _require_str(raw: object, field: str, index: int) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise BaselineError(f"baseline entry {index}: {field!r} must be a non-empty string, got {raw!r}. Quote YAML-ambiguous names such as 'on' and 'yes'.")
    return raw


#: The only keys a baseline row may carry. Retired keys (``owner``,
#: ``provisional``) are refused rather than ignored, so a copy-pasted old row
#: cannot smuggle dead data back in.
_ENTRY_KEYS = frozenset({"name", "declared_at", "disposition", "note"})

#: The only top-level keys the baseline file may carry. ``mission`` and
#: ``code_only_suppressions`` are retired and refused.
_TOP_LEVEL_KEYS = frozenset({"entries"})


def _reject_unknown_keys(raw: dict[object, object], allowed: frozenset[str], where: str) -> None:
    for key in raw:
        if key not in allowed:
            raise BaselineError(f"{where}: unknown key {key!r}; allowed keys are {sorted(allowed)}")


def _parse_entry(raw: object, index: int) -> BaselineEntry:
    if not isinstance(raw, dict):
        raise BaselineError(f"baseline entry {index} is not a mapping: {raw!r}")
    _reject_unknown_keys(raw, _ENTRY_KEYS, f"baseline entry {index}")
    disposition = _require_str(raw.get("disposition"), "disposition", index)
    if disposition not in DISPOSITIONS:
        raise BaselineError(f"baseline entry {index}: illegal disposition {disposition!r}. Legal values are {sorted(DISPOSITIONS)} — there is no 'accepted'.")
    return BaselineEntry(
        name=_require_str(raw.get("name"), "name", index),
        declared_at=Path(_require_str(raw.get("declared_at"), "declared_at", index)),
        disposition=disposition,
        note=_require_str(raw.get("note"), "note", index),
    )


def load_baseline(path: Path = BASELINE_PATH) -> Baseline:
    """Parse and validate the frozen baseline, raising on anything malformed."""
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise BaselineError(f"{path} does not contain a mapping")
    _reject_unknown_keys(document, _TOP_LEVEL_KEYS, str(path))
    raw_entries = document.get("entries")
    if not isinstance(raw_entries, list):
        raise BaselineError(f"{path}: 'entries' must be a list")
    entries = tuple(_parse_entry(raw, index) for index, raw in enumerate(raw_entries))
    seen: set[InertSlot] = set()
    for entry in entries:
        if entry.slot in seen:
            raise BaselineError(f"duplicate baseline entry for {entry.name!r} at {entry.declared_at}")
        seen.add(entry.slot)
    return Baseline(entries=entries)


def ratchet(found: list[InertSlot], baseline: Baseline) -> tuple[list[InertSlot], list[BaselineEntry]]:
    """Split findings against the baseline into ``(new, cleared)``.

    ``new`` — findings absent from the baseline. Growth: the gate FAILS.
    ``cleared`` — baseline entries no longer found. Shrinkage: the gate WARNS and
    the entry should be deleted from the file.
    """
    frozen = baseline.slots
    new = [slot for slot in found if slot not in frozen]
    still_found = set(found)
    cleared = [entry for entry in baseline.entries if entry.slot not in still_found]
    return new, cleared


#: Module-scope frozenset so the charter-named ratchet meta-test
#: (``test_ratchet_baselines.py`` against ``tests/architectural/_baselines.yaml``)
#: can introspect this baseline's size exactly as it does every other gated
#: allowlist: growth above the recorded number FAILS, shrinkage WARNS. Without
#: this registration nothing pins the file's size at all.
BASELINE_SLOTS: frozenset[InertSlot] = load_baseline().slots


def is_schema_declared(slot: InertSlot) -> bool:
    """True when *slot* was declared by the schema walk rather than the model walk.

    Exposed so the floor test can pin each walk independently. Deriving this in
    the test would let the two definitions drift, which is the failure mode this
    module exists to catch.
    """
    return f"/{_SCHEMAS}/" in str(slot.declared_at).replace("\\", "/")
