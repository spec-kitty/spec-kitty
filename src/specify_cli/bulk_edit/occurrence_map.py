"""Occurrence map schema, loading, validation, and admissibility checking.

An occurrence map is a YAML file that describes how a bulk rename/remove/deprecate
operation should be classified across different occurrence categories. Each category
carries an ``action`` that tells the executor how to handle occurrences of that kind.

The canonical schema lives in ``src/charter/offering/schemas/occurrence-map.schema.yaml``
and the user-facing starter template lives in
``src/charter/offering/templates/occurrence-map-template.yaml``. Both are loaded at import
time via :mod:`charter.offering.shared.schema_utils` so the constants below stay in lock
step with the published schema — there is no second source of truth to drift.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import cache
from importlib.resources import files
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from kernel.schema_utils import SchemaUtilities
from specify_cli.core.constants import OCCURRENCE_MAP_FILENAME

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema + template accessors
# ---------------------------------------------------------------------------

SCHEMA_NAME: str = "occurrence-map"
TEMPLATE_FILENAME: str = "occurrence-map-template.yaml"


def load_schema() -> dict[str, Any]:
    """Return the JSON Schema dict for ``occurrence_map.yaml``.

    The schema lives in ``src/charter/offering/schemas/occurrence-map.schema.yaml``
    and is loaded (and cached) by :class:`charter.offering.shared.schema_utils.SchemaUtilities`.
    """
    return SchemaUtilities.load_schema(SCHEMA_NAME)


def template_path() -> Path:
    """Return the filesystem path to the starter template YAML."""
    try:
        resource = files("charter.offering") / "templates" / TEMPLATE_FILENAME
        return Path(str(resource))
    except (ModuleNotFoundError, TypeError):
        # Development fallback for non-resource contexts.
        return (
            Path(__file__).resolve().parents[2]
            / "charter"
            / "offering"
            / "templates"
            / TEMPLATE_FILENAME
        )


def load_template_text() -> str:
    """Return the starter template YAML as a string."""
    return template_path().read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Schema-derived constants
# ---------------------------------------------------------------------------


@cache
def _schema_definitions() -> dict[str, Any]:
    defs: dict[str, Any] = load_schema().get("definitions", {})
    return defs


@cache
def _valid_actions() -> frozenset[str]:
    return frozenset(_schema_definitions().get("action", {}).get("enum", []))


@cache
def _valid_operations() -> frozenset[str]:
    return frozenset(_schema_definitions().get("operation", {}).get("enum", []))


@cache
def _standard_categories() -> frozenset[str]:
    return frozenset(
        _schema_definitions().get("standard_category", {}).get("enum", [])
    )


# The 8 standard occurrence categories required by FR-004 — sourced from the
# schema so adding/removing a category in one place is a single edit. An
# admissible occurrence map must classify every one of these, even when the
# action is ``do_not_change`` (omitting a category silently whitelists it).
VALID_ACTIONS: frozenset[str] = _valid_actions()
VALID_OPERATIONS: frozenset[str] = _valid_operations()
STANDARD_CATEGORIES: frozenset[str] = _standard_categories()

PLACEHOLDER_TERMS: frozenset[str] = frozenset(
    {"TODO", "TBD", "FIXME", "XXX", "PLACEHOLDER", ""}
)

MIN_ADMISSIBLE_CATEGORIES: int = 3

_KNOWN_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
    {"target", "categories", "exceptions", "moves", "structural_targets", "status"}
)

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of a validation or admissibility check."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FieldPathException:
    """A single field-scoped exemption (WP02, FR-002/C-005).

    ``exceptions[]`` entries match by *path glob* alone, which cannot express
    Mission B2's exemption set: every one of its 17 GOVERNANCE files, and 5 of
    its 7 RAW_MATERIAL files, also carry MIGRATE entries in the SAME file —
    so a path-only exception would either whitelist the migration in those
    files or block it outright.

    A field-scoped entry narrows the exemption to one YAML field path inside
    files matching ``path``. The file's OTHER fields (including migrating
    ones) are still classified by the category-level action; this entry only
    additionally records that ``field_path`` is pinned to ``action``. See
    :func:`specify_cli.bulk_edit.diff_check.assess_file`, which surfaces the
    pin as a targeted warning rather than using it to override the whole
    file's verdict — a blanket override is exactly what made the exemption
    inexpressible in the first place.
    """

    path: str
    field_path: str
    action: str
    reason: str | None = None


@dataclass(frozen=True)
class MoveEntry:
    """A single multi-path structural move (IC-10, #1815).

    Maps one or more ``from`` source paths to a single ``to`` destination
    path. Expresses a structural relocation that the eight single-term-rename
    categories cannot capture.
    """

    sources: list[str]
    destination: str
    reason: str | None = None


@dataclass(frozen=True)
class StructuralTarget:
    """A single declared structural-edit exemption (bulk-edit review gate).

    Unlike :class:`MoveEntry` (a relocation with distinct ``from``/``to``
    paths), a structural target names ONE path (file or glob) whose changes
    in THIS mission are a genuine structural code edit — a new function, a
    refactor — rather than a bulk find/replace occurrence. Declaring it here
    is the reviewer-approved, narrow, per-file escape hatch from the
    ``do_not_change`` path heuristic (see
    :func:`specify_cli.bulk_edit.diff_check._structural_target_for`); it is
    deliberately NOT a blanket exemption for a whole category or extension —
    only paths named here, one at a time, are exempted.
    """

    path: str
    reason: str | None = None


@dataclass(frozen=True)
class OccurrenceMap:
    """Parsed representation of an ``occurrence_map.yaml`` file."""

    target_term: str
    target_replacement: str | None
    target_operation: str
    categories: dict[str, dict[str, str]]
    exceptions: list[dict[str, str]]
    status: dict[str, Any] | None
    raw: dict[str, Any]
    moves: list[MoveEntry] = field(default_factory=list)
    field_path_exceptions: list[FieldPathException] = field(default_factory=list)
    structural_targets: list[StructuralTarget] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_occurrence_map(feature_dir: Path) -> OccurrenceMap | None:
    """Read and parse ``occurrence_map.yaml`` from *feature_dir*.

    Returns ``None`` when the file does not exist.
    """
    yaml_path = feature_dir / OCCURRENCE_MAP_FILENAME
    if not yaml_path.exists():
        return None

    yaml = YAML(typ="safe")
    with open(yaml_path) as fh:
        data: dict[str, Any] = yaml.load(fh)

    if data is None:
        return None

    target = data.get("target", {})
    categories = data.get("categories", {})
    exceptions = data.get("exceptions", [])
    status = data.get("status")
    moves = _parse_moves(data.get("moves"))
    field_path_exceptions = _parse_field_path_exceptions(exceptions)
    structural_targets = _parse_structural_targets(data.get("structural_targets"))

    return OccurrenceMap(
        target_term=target.get("term", ""),
        target_replacement=target.get("replacement"),
        target_operation=target.get("operation", ""),
        categories=categories,
        exceptions=exceptions if exceptions is not None else [],
        status=status,
        raw=data,
        moves=moves,
        field_path_exceptions=field_path_exceptions,
        structural_targets=structural_targets,
    )


def _parse_field_path_exceptions(raw_exceptions: Any) -> list[FieldPathException]:
    """Parse the field-scoped subset of ``exceptions:`` (WP02, FR-002).

    An entry is field-scoped when it carries a non-empty ``field_path``.
    Malformed entries are skipped here — surfaced as human-readable errors by
    :func:`validate_occurrence_map` — so a missing/absent ``exceptions``
    block, or a legacy exceptions list with no ``field_path`` keys, yields an
    empty list (C-OMAP-1 backward compatibility).
    """
    if not isinstance(raw_exceptions, list):
        return []

    parsed: list[FieldPathException] = []
    for entry in raw_exceptions:
        if not isinstance(entry, dict):
            continue
        field_path_raw = entry.get("field_path")
        if not isinstance(field_path_raw, str) or field_path_raw.strip() == "":
            continue
        path_raw = entry.get("path")
        action_raw = entry.get("action")
        if not isinstance(path_raw, str) or not isinstance(action_raw, str):
            continue
        reason_raw = entry.get("reason")
        reason = reason_raw if isinstance(reason_raw, str) else None
        parsed.append(
            FieldPathException(
                path=path_raw,
                field_path=field_path_raw,
                action=action_raw,
                reason=reason,
            )
        )
    return parsed


def _parse_moves(raw_moves: Any) -> list[MoveEntry]:
    """Parse the optional ``moves:`` block into :class:`MoveEntry` objects.

    Tolerant by design: malformed entries are skipped here and surfaced by
    :func:`validate_occurrence_map`, which reports human-readable errors. A
    missing or null block yields an empty list so legacy single-term maps are
    unaffected (C-OMAP-1).
    """
    if not isinstance(raw_moves, list):
        return []

    parsed: list[MoveEntry] = []
    for entry in raw_moves:
        if not isinstance(entry, dict):
            continue
        sources_raw = entry.get("from")
        sources = (
            [str(s) for s in sources_raw] if isinstance(sources_raw, list) else []
        )
        destination_raw = entry.get("to")
        destination = destination_raw if isinstance(destination_raw, str) else ""
        reason_raw = entry.get("reason")
        reason = reason_raw if isinstance(reason_raw, str) else None
        parsed.append(
            MoveEntry(sources=sources, destination=destination, reason=reason)
        )
    return parsed


def _parse_structural_targets(raw_targets: Any) -> list[StructuralTarget]:
    """Parse the optional ``structural_targets:`` block into entries.

    Tolerant by design, mirroring :func:`_parse_moves`: malformed entries are
    skipped here and surfaced by :func:`validate_occurrence_map`, which
    reports human-readable errors. A missing or null block yields an empty
    list so maps predating this declaration are unaffected (C-OMAP-1
    precedent).
    """
    if not isinstance(raw_targets, list):
        return []

    parsed: list[StructuralTarget] = []
    for entry in raw_targets:
        if not isinstance(entry, dict):
            continue
        path_raw = entry.get("path")
        if not isinstance(path_raw, str) or path_raw.strip() == "":
            continue
        reason_raw = entry.get("reason")
        reason = reason_raw if isinstance(reason_raw, str) else None
        parsed.append(StructuralTarget(path=path_raw, reason=reason))
    return parsed


# ---------------------------------------------------------------------------
# Structural validation
# ---------------------------------------------------------------------------


def validate_occurrence_map(omap: OccurrenceMap) -> ValidationResult:
    """Validate an :class:`OccurrenceMap` for structural correctness.

    Checks:
    * ``target`` section exists with a non-empty ``term``
    * ``target.operation`` is one of :data:`VALID_OPERATIONS`
    * ``categories`` section exists with at least one entry
    * Every category has an ``action`` key whose value is in :data:`VALID_ACTIONS`

    Warns on unknown top-level keys.
    """
    errors: list[str] = []
    warnings: list[str] = []

    errors.extend(_validate_target(omap.raw.get("target", _MISSING)))
    errors.extend(_validate_categories(omap.raw.get("categories", _MISSING)))
    errors.extend(_validate_exceptions(omap.raw.get("exceptions")))
    errors.extend(_validate_moves(omap.raw.get("moves")))
    errors.extend(_validate_structural_targets(omap.raw.get("structural_targets")))

    for key in omap.raw:
        if key not in _KNOWN_TOP_LEVEL_KEYS:
            warnings.append(f"Unknown top-level key '{key}'")

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


# Sentinel distinguishing an absent section from an explicit ``None`` value.
_MISSING: Any = object()


def _validate_target(target: Any) -> list[str]:
    """Validate the required ``target`` section."""
    if target is _MISSING:
        return ["Missing required 'target' section"]
    if not isinstance(target, dict):
        return ["'target' must be a mapping"]

    errors: list[str] = []
    term = target.get("term")
    if term is None:
        errors.append("Missing required 'target.term'")
    elif not isinstance(term, str) or term.strip() == "":
        errors.append("'target.term' must be a non-empty string")

    operation = target.get("operation")
    if operation is not None and operation not in VALID_OPERATIONS:
        errors.append(
            f"Invalid target.operation '{operation}'; "
            f"must be one of {sorted(VALID_OPERATIONS)}"
        )
    return errors


def _validate_categories(cats: Any) -> list[str]:
    """Validate the required ``categories`` section."""
    if cats is _MISSING:
        return ["Missing required 'categories' section"]
    if not isinstance(cats, dict) or len(cats) == 0:
        return ["'categories' must be a non-empty mapping"]

    errors: list[str] = []
    for cat_name, cat_value in cats.items():
        if not isinstance(cat_value, dict):
            errors.append(f"Category '{cat_name}' must be a mapping")
            continue
        action = cat_value.get("action")
        if action is None:
            errors.append(f"Category '{cat_name}' missing required 'action' key")
        elif action not in VALID_ACTIONS:
            errors.append(
                f"Category '{cat_name}' has invalid action '{action}'; "
                f"must be one of {sorted(VALID_ACTIONS)}"
            )
    return errors


def _validate_exceptions(exceptions_raw: Any) -> list[str]:
    """Validate the optional ``exceptions`` section, including field-path
    entries (WP02, FR-002).

    A missing or ``None`` block produces no errors — legacy maps may omit
    ``exceptions`` entirely (C-OMAP-1).
    """
    if exceptions_raw is None:
        return []
    if not isinstance(exceptions_raw, list):
        return ["'exceptions' must be a list when present"]

    errors: list[str] = []
    for index, entry in enumerate(exceptions_raw):
        errors.extend(_validate_exception_entry(index, entry))
    return errors


def _validate_exception_entry(index: int, entry: Any) -> list[str]:
    """Validate a single ``exceptions[]`` entry; return human-readable errors."""
    errors: list[str] = []
    label = f"exceptions[{index}]"
    if not isinstance(entry, dict):
        return [f"{label} must be a mapping with 'path' and 'action'"]

    path = entry.get("path")
    if path is None:
        errors.append(f"{label} missing required 'path' key")
    elif not isinstance(path, str) or path.strip() == "":
        errors.append(f"{label}.path must be a non-empty string")

    action = entry.get("action")
    if action is None:
        errors.append(f"{label} missing required 'action' key")
    elif action not in VALID_ACTIONS:
        errors.append(
            f"{label} has invalid action '{action}'; "
            f"must be one of {sorted(VALID_ACTIONS)}"
        )

    field_path = entry.get("field_path")
    if field_path is not None and (
        not isinstance(field_path, str) or field_path.strip() == ""
    ):
        errors.append(f"{label}.field_path must be a non-empty string when present")

    return errors


def _validate_moves(moves_raw: Any) -> list[str]:
    """Validate the optional ``moves`` section (IC-10 / C-OMAP-1).

    A missing or ``None`` block produces no errors so legacy single-term maps
    are unaffected.
    """
    if moves_raw is None:
        return []
    if not isinstance(moves_raw, list):
        return ["'moves' must be a list when present"]

    errors: list[str] = []
    for index, entry in enumerate(moves_raw):
        errors.extend(_validate_move_entry(index, entry))
    return errors


def _validate_move_entry(index: int, entry: Any) -> list[str]:
    """Validate a single ``moves[]`` entry; return human-readable errors."""
    errors: list[str] = []
    label = f"moves[{index}]"
    if not isinstance(entry, dict):
        return [f"{label} must be a mapping with 'from' and 'to'"]

    sources = entry.get("from")
    if sources is None:
        errors.append(f"{label} missing required 'from' key")
    elif not isinstance(sources, list) or len(sources) == 0:
        errors.append(f"{label}.from must be a non-empty list of paths")
    else:
        for src in sources:
            if not isinstance(src, str) or src.strip() == "":
                errors.append(f"{label}.from entries must be non-empty strings")
                break

    destination = entry.get("to")
    if destination is None:
        errors.append(f"{label} missing required 'to' key")
    elif not isinstance(destination, str) or destination.strip() == "":
        errors.append(f"{label}.to must be a non-empty string")

    return errors


def _validate_structural_targets(raw: Any) -> list[str]:
    """Validate the optional ``structural_targets`` section.

    A missing or ``None`` block produces no errors — maps predating this
    declaration are unaffected (C-OMAP-1 precedent).
    """
    if raw is None:
        return []
    if not isinstance(raw, list):
        return ["'structural_targets' must be a list when present"]

    errors: list[str] = []
    for index, entry in enumerate(raw):
        errors.extend(_validate_structural_target_entry(index, entry))
    return errors


# A structural target must never degrade into a blanket exemption. These two
# tokens, as the WHOLE (stripped) path string, are unbounded — they name no
# file at all, only "everything".
_UNBOUNDED_GLOB_TOKENS: frozenset[str] = frozenset({"*", "**"})


def _basename_extension_is_fixed(basename: str) -> bool:
    """Return ``True`` when *basename* ends in a concrete, non-wildcard extension.

    ``basename`` is the final ``/``-separated path segment. A fixed extension
    is the load-bearing narrowness signal: it is what turns ``src/foo/*.py``
    or ``**/bar_*.py`` into an "extension-bounded glob" rather than an
    unconstrained sweep — the NAME part may carry a wildcard, but the
    EXTENSION must not (``file.*`` is rejected: the extension itself is
    wildcarded, so nothing about it constrains the match).
    """
    if basename in _UNBOUNDED_GLOB_TOKENS:
        return False
    dot_index = basename.rfind(".")
    if dot_index <= 0:
        return False
    extension = basename[dot_index + 1 :]
    return extension != "" and "*" not in extension and "?" not in extension


def _is_narrow_structural_path(path: str) -> bool:
    """Return ``True`` when *path* is narrow enough for a ``structural_targets``
    entry: a concrete file (with an extension) or an extension-bounded glob
    whose DIRECTORY portion carries no ``**`` recursion.

    This is the load-bearing narrowness invariant. A first cut checked only
    the basename's extension, which a second-opinion squad (architect-alphonso
    + reviewer-renata) proved live-exploitable: :func:`_path_matches` in
    ``diff_check.py`` resolves ``**`` via recursive glob, so
    ``path: "src/**/*.py"`` passed the basename-only check (basename ``*.py``
    has a fixed extension) while matching EVERY ``.py`` file under ``src/`` —
    a blanket "ignore all src/*.py" reopening the exact defect class
    (Directive 043) the review gate exists to close. ``**`` anywhere in the
    path — not just the basename — is now rejected. Rejected here,
    structurally, before such an entry can ever reach
    :func:`specify_cli.bulk_edit.diff_check._structural_target_for` (which
    also re-checks this predicate directly, so a broad entry that reaches the
    map by any OTHER route — e.g. hand-edited after finalize — still cannot
    grant an exemption at review time):

    * a bare directory / directory-prefix (``"src"``, ``"src/specify_cli"``,
      or any path with a trailing ``/``) — no filename component at all;
    * unbounded directory recursion — ``**`` anywhere in the path
      (``"**"``, ``"**/*"``, ``"**/bar_*.py"``, ``"src/**/*.py"``,
      ``"src/**"``) — even when the basename itself names a fixed extension,
      ``**`` still matches an unbounded number of directories;
    * an unbounded glob with no extension constraint at all (``"*"``).

    Accepted: a concrete file path (``"src/foo/bar.py"``) or an
    extension-bounded glob confined to a SINGLE directory level
    (``"src/foo/*.py"``) — the last path segment must name a fixed
    extension, the filename part may still carry a (non-recursive) wildcard,
    but no path segment may be ``**``.
    """
    normalized = path.strip()
    if not normalized or normalized.endswith("/"):
        return False
    posix = Path(normalized).as_posix()
    if posix in _UNBOUNDED_GLOB_TOKENS:
        return False
    if "**" in posix:
        return False
    basename = posix.rsplit("/", 1)[-1]
    return _basename_extension_is_fixed(basename)


def _validate_structural_target_entry(index: int, entry: Any) -> list[str]:
    """Validate a single ``structural_targets[]`` entry; return human-readable errors."""
    label = f"structural_targets[{index}]"
    if not isinstance(entry, dict):
        return [f"{label} must be a mapping with 'path' and 'reason'"]

    errors: list[str] = []
    path = entry.get("path")
    if path is None:
        errors.append(f"{label} missing required 'path' key")
    elif not isinstance(path, str) or path.strip() == "":
        errors.append(f"{label}.path must be a non-empty string")
    elif not _is_narrow_structural_path(path):
        errors.append(
            f"{label}.path {path!r} is too broad for a structural-target "
            "exemption: it must be a concrete file path with an extension "
            "(e.g. 'src/foo/bar.py') or an extension-bounded glob (e.g. "
            "'src/foo/*.py', '**/bar_*.py'). Bare directories, "
            "directory-prefixes, and unbounded globs ('*', '**', '**/*') "
            "are rejected — a structural-target exemption must name specific "
            "file(s), never a whole directory tree."
        )

    reason = entry.get("reason")
    if reason is None:
        errors.append(f"{label} missing required 'reason' key")
    elif not isinstance(reason, str) or reason.strip() == "":
        errors.append(f"{label}.reason must be a non-empty string")

    return errors


# ---------------------------------------------------------------------------
# JSON Schema validation
# ---------------------------------------------------------------------------


def validate_against_schema(raw: dict[str, Any]) -> ValidationResult:
    """Validate the raw map dict against the JSON Schema.

    This is a machine-enforced contract check — if the schema file changes, the
    bounds of what this function accepts change with it. Use this alongside
    :func:`validate_occurrence_map` (which produces human-readable errors tuned
    for the runtime gate's output panels).
    """
    errors: list[str] = []
    # #4409: imported here, not at module scope — ``jsonschema`` eagerly
    # loads format checkers (``rfc3987_syntax.syntax_helpers``, ~1.8s) that
    # every CLI invocation would otherwise pay for without validating
    # anything. Same deferral as the charter validation modules.
    import jsonschema  # noqa: PLC0415 — deferred: see the cost note above

    validator = jsonschema.Draft202012Validator(load_schema())
    for err in sorted(validator.iter_errors(raw), key=lambda e: list(e.absolute_path)):
        path = ".".join(str(p) for p in err.absolute_path) or "<root>"
        errors.append(f"{path}: {err.message}")
    return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=[])


# ---------------------------------------------------------------------------
# Admissibility checking
# ---------------------------------------------------------------------------


def check_admissibility(omap: OccurrenceMap) -> ValidationResult:
    """Check whether the occurrence map is *admissible* for execution.

    An admissible map:
    * Has a ``target.term`` that is not a well-known placeholder
    * Has at least :data:`MIN_ADMISSIBLE_CATEGORIES` categories
    * Classifies every :data:`STANDARD_CATEGORIES` entry (FR-004 —
      omitting a standard category silently whitelists that risk surface)
    """
    errors: list[str] = []
    warnings: list[str] = []

    term = omap.target_term.strip()
    if term.upper() in {p.upper() for p in PLACEHOLDER_TERMS}:
        errors.append(
            f"target.term '{omap.target_term}' is a placeholder; "
            "provide a real term before execution"
        )

    num_categories = len(omap.categories)
    if num_categories < MIN_ADMISSIBLE_CATEGORIES:
        errors.append(
            f"Need at least {MIN_ADMISSIBLE_CATEGORIES} categories, "
            f"got {num_categories}"
        )

    # FR-004: every standard category must be explicitly classified.
    missing = sorted(STANDARD_CATEGORIES - set(omap.categories.keys()))
    if missing:
        errors.append(
            "Occurrence map is missing required standard categories: "
            f"{missing}. Every category must be present — use action "
            "'do_not_change' for risk surfaces that must not be modified."
        )

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
