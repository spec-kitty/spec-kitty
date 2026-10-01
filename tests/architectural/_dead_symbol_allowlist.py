"""Schema-enforcing loader for the dead-symbol ``(module, name)`` allowlist (#5346, FR-009).

The exemption data of ``tests/architectural/test_no_dead_symbols.py`` lives in
``dead_symbol_allowlist.yaml`` next to this module. This loader is the one
authority that reads it. It turns what used to be free comments into enforced
fields (a required category rationale -- an entry's own is optional, falling
back to its category's per L6 -- a required issue where the category demands
one, whole-file uniqueness, no tombstone categories) and implements rules
L1–L10 of ``kitty-specs/test-suite-remediation-01M3SSDW/contracts/
dead-symbol-allowlist.md`` §1:

* **L1** the file exists and parses as YAML (through a ``yaml.SafeLoader``
  subclass);
* **L2** the top level is a mapping with exactly the keys ``schema_version``,
  ``categories``, ``entries`` and ``widened_grandfathered_470``;
* **L3** a repeated mapping key is rejected at every level (plain PyYAML
  silently keeps the last one);
* **L4** ``schema_version`` is the int ``1`` (a bool is refused);
* **L5** every record carries only its allowed keys, and its required ones.
  This refuses positional (``line``) and content (``body_hash``) identity and
  the retired provenance field;
* **L6** every rationale (and note) that is present is a non-empty string, so
  the effective rationale of an entry is never empty;
* **L7** an entry's ``category`` is declared; ``requires_issue`` is a real
  bool; an ``issue`` is present where the category requires one and the
  widened section always has one; every ``issue`` matches ``#N`` or
  ``owner/repo#N``;
* **L8** ``(module, name)`` is unique across ``entries`` and the widened
  entries together; the error names both locations;
* **L9** every declared category has at least one entry (no tombstones). A
  fully burned-down file has ``entries: []`` *and* ``categories: {}``, so L9
  then holds vacuously; ``entries: []`` beside a declared category is a
  tombstone and is refused;
* **L10** ``module`` is a dotted ASCII identifier path and ``name`` a bare
  identifier;
* **category-id** every category id matches ``^category_[a-z0-9_]+$``.

The loader is **pure**: it imports no ``src/`` package and no other test
module, and never walks the corpus. Errors are :class:`AllowlistSchemaError`
with the message ``"{path}: {pointer}: [{rule}] {detail}"``.

The allowlist *size* is deliberately not recorded in the YAML. It lives only in
``_baselines.yaml`` (one authority per count).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Hashable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from functools import cached_property
from pathlib import Path
from types import MappingProxyType
from typing import Final, NoReturn, cast

import yaml

__all__ = [
    # The single parse of the committed file; the gate evaluates both sections from it.
    "ALLOWLIST",
    "ALLOWLIST_PATH",
    "AllowlistCategory",
    "AllowlistEntry",
    "AllowlistSchemaError",
    "DeadSymbolAllowlist",
    "DeadSymbolKey",
    # Views of ALLOWLIST (not a second read): the entries' keys and the widened "module::name" strings.
    "SYMBOL_ALLOWLIST",
    # Shared verdict vocabulary; assigned only by the gate; no loader rule depends on it.
    "StaleVerdict",
    "WIDENED_SCOPE_GRANDFATHERED_470",
    "WidenedEntry",
    "load_allowlist",
]

ALLOWLIST_PATH: Final[Path] = Path(__file__).with_name("dead_symbol_allowlist.yaml")

_SCHEMA_VERSION: Final = 1

# Document keys.
_SCHEMA_VERSION_KEY: Final = "schema_version"
_CATEGORIES: Final = "categories"
_ENTRIES: Final = "entries"
_WIDENED: Final = "widened_grandfathered_470"
_RATIONALE: Final = "rationale"
_REQUIRES_ISSUE: Final = "requires_issue"
_TARGET: Final = "target"
_MODULE: Final = "module"
_NAME: Final = "name"
_CATEGORY: Final = "category"
_ISSUE: Final = "issue"
_NOTE: Final = "note"

_TOP_LEVEL_KEYS: Final = frozenset({_SCHEMA_VERSION_KEY, _CATEGORIES, _ENTRIES, _WIDENED})

# (allowed, required) key sets per record kind (rule L5). ``issue`` is never
# L5-required: its presence is an L7 decision (category ``requires_issue``).
_CATEGORY_KEYS: Final = (frozenset({_RATIONALE, _REQUIRES_ISSUE, _TARGET}), frozenset({_RATIONALE, _REQUIRES_ISSUE}))
_ENTRY_KEYS: Final = (frozenset({_MODULE, _NAME, _CATEGORY, _RATIONALE, _ISSUE}), frozenset({_MODULE, _NAME, _CATEGORY}))
_WIDENED_KEYS: Final = (frozenset({_RATIONALE, _ISSUE, _ENTRIES}), frozenset({_RATIONALE, _ENTRIES}))
_WIDENED_ENTRY_KEYS: Final = (frozenset({_MODULE, _NAME, _NOTE}), frozenset({_MODULE, _NAME}))

# Rule ids, as printed in ``[rule]`` of every error message.
_L1: Final = "L1"
_L2: Final = "L2"
_L3: Final = "L3"
_L4: Final = "L4"
_L5: Final = "L5"
_L6: Final = "L6"
_L7: Final = "L7"
_L8: Final = "L8"
_L9: Final = "L9"
_L10: Final = "L10"
_CATEGORY_ID_RULE: Final = "category-id"

_ROOT_POINTER: Final = "<root>"
_NON_EMPTY_STRING: Final = "must be a non-empty string"

# ``fullmatch`` everywhere: ``$`` would also accept a trailing newline.
_ISSUE_PATTERN: Final = re.compile(r"#\d+|[\w.-]+/[\w.-]+#\d+", re.ASCII)
_MODULE_PATTERN: Final = re.compile(r"[A-Za-z_]\w*(\.[A-Za-z_]\w*)*", re.ASCII)
_CATEGORY_ID_PATTERN: Final = re.compile(r"category_[a-z0-9_]+")


class AllowlistSchemaError(ValueError):
    """The allowlist file violates the schema; names the file, the location and the rule."""

    def __init__(self, path: Path, pointer: str, rule: str, detail: str) -> None:
        self.path = path
        self.pointer = pointer
        self.rule = rule
        self.detail = detail
        super().__init__(f"{path}: {pointer}: [{rule}] {detail}")


class StaleVerdict(StrEnum):
    """Why an allowlist entry no longer earns its place, in precedence order (data-model §1.5).

    Shared verdict vocabulary; assigned only by the gate; no loader rule
    depends on it. It lives here so the import graph stays gate -> loader,
    with the loader a pure leaf.
    """

    INVALID = "INVALID"
    GONE = "GONE"
    REVIVED = "REVIVED"
    SUPERSEDED = "SUPERSEDED"
    MOOT = "MOOT"


@dataclass(frozen=True, order=True)
class DeadSymbolKey:
    """The identity of one allowlisted symbol: its ``__all__``-declaring module and bare name."""

    module: str
    name: str

    def __str__(self) -> str:
        return f"{self.module}::{self.name}"


@dataclass(frozen=True)
class AllowlistCategory:
    """One declared category: a shared rationale, the issue policy and an optional burn-down target."""

    id: str
    rationale: str
    requires_issue: bool
    target: str | None


@dataclass(frozen=True)
class AllowlistEntry:
    """One ``__all__``-scope exemption."""

    key: DeadSymbolKey
    category: str
    rationale: str | None
    issue: str | None

    def effective_rationale(self, categories: Mapping[str, AllowlistCategory]) -> str:
        """The entry's own rationale, or else its category's (never empty, rule L6)."""
        return self.rationale or categories[self.category].rationale


@dataclass(frozen=True)
class WidenedEntry:
    """One entry of the folded #470 widened grandfather list (non-``__all__`` scope)."""

    key: DeadSymbolKey
    note: str | None


@dataclass(frozen=True)
class DeadSymbolAllowlist:
    """The loaded allowlist: both sections of the one YAML file."""

    categories: Mapping[str, AllowlistCategory]
    entries: tuple[AllowlistEntry, ...]
    widened_entries: tuple[WidenedEntry, ...]
    widened_rationale: str
    widened_issue: str

    @cached_property
    def keys(self) -> frozenset[DeadSymbolKey]:
        """The ``(module, name)`` keys of the ``__all__``-scope entries."""
        return frozenset(entry.key for entry in self.entries)

    @cached_property
    def widened_qualified(self) -> frozenset[str]:
        """The widened entries as ``"module::name"`` strings."""
        return frozenset(str(entry.key) for entry in self.widened_entries)


# ---------------------------------------------------------------------------
# L1 / L3: parsing
# ---------------------------------------------------------------------------


class _DuplicateKeyError(yaml.YAMLError):
    """A mapping key repeated within one mapping (rule L3)."""

    def __init__(self, key: Hashable, mark: yaml.Mark) -> None:
        super().__init__(f"duplicate mapping key {key!r}")
        self.key = key
        self.mark = mark


class _UniqueKeyLoader(yaml.SafeLoader):
    """A ``SafeLoader`` that refuses a repeated mapping key at any level (L3)."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Hashable, object]:
        seen: set[Hashable] = set()
        # The PyYAML stub declares ``construct_object`` without annotations; the
        # cast states its real contract (node in, constructed value out) so the
        # call is typed under ``mypy --strict`` without a suppression.
        construct_object = cast(Callable[..., object], self.construct_object)
        for key_node, _value_node in node.value:
            key = construct_object(key_node, deep=deep)
            if not isinstance(key, Hashable):
                continue  # the base constructor refuses an unhashable key (an L1 YAMLError)
            if key in seen:
                raise _DuplicateKeyError(key, key_node.start_mark)
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


def _parse(path: Path) -> object:
    """Read and parse *path* with :class:`_UniqueKeyLoader` (L1, L3)."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise AllowlistSchemaError(path, _ROOT_POINTER, _L1, f"cannot read the allowlist file: {exc}") from exc
    try:
        # A SafeLoader subclass: only the L3 duplicate-key check is added.
        return yaml.load(text, Loader=_UniqueKeyLoader)
    except _DuplicateKeyError as exc:
        pointer = f"line {exc.mark.line + 1}, column {exc.mark.column + 1}"
        raise AllowlistSchemaError(path, pointer, _L3, f"duplicate mapping key {exc.key!r}") from exc
    except yaml.YAMLError as exc:
        raise AllowlistSchemaError(path, _ROOT_POINTER, _L1, f"not valid YAML: {exc}") from exc


# ---------------------------------------------------------------------------
# Field and record validation (one small function per rule family)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Context:
    """The file being validated; builds located errors."""

    path: Path

    def fail(self, pointer: str, rule: str, detail: str) -> NoReturn:
        raise AllowlistSchemaError(self.path, pointer, rule, detail)


def _sorted_keys(keys: set[object] | frozenset[object]) -> list[str]:
    return sorted(str(key) for key in keys)


def _require_mapping(value: object, pointer: str, rule: str, ctx: _Context) -> dict[object, object]:
    if not isinstance(value, dict):
        ctx.fail(pointer, rule, f"must be a mapping, got {type(value).__name__}")
    return value


def _require_list(value: object, pointer: str, rule: str, ctx: _Context) -> list[object]:
    if not isinstance(value, list):
        ctx.fail(pointer, rule, f"must be a list, got {type(value).__name__}")
    return value


def _check_record_keys(value: object, pointer: str, key_sets: tuple[frozenset[str], frozenset[str]], ctx: _Context) -> dict[object, object]:
    """L5: *value* is a mapping carrying only its allowed keys and all its required ones."""
    allowed, required = key_sets
    record = _require_mapping(value, pointer, _L5, ctx)
    unknown = set(record) - allowed
    if unknown:
        ctx.fail(pointer, _L5, f"unknown key(s) {_sorted_keys(unknown)}; allowed: {sorted(allowed)}")
    missing = required - set(record)
    if missing:
        ctx.fail(pointer, _L5, f"missing required key(s) {sorted(missing)}")
    return record


def _require_text(value: object, pointer: str, ctx: _Context) -> str:
    """L6: a present free-text field is a non-empty (stripped) string."""
    if not isinstance(value, str) or not value.strip():
        ctx.fail(pointer, _L6, f"{_NON_EMPTY_STRING}, got {value!r}")
    return value.strip()


def _optional_text(record: Mapping[object, object], key: str, pointer: str, ctx: _Context) -> str | None:
    if key not in record:
        return None
    return _require_text(record[key], f"{pointer}.{key}", ctx)


def _check_issue(value: object, pointer: str, ctx: _Context) -> str:
    """L7: an issue reference is ``#N`` or ``owner/repo#N``."""
    if not isinstance(value, str) or not _ISSUE_PATTERN.fullmatch(value):
        ctx.fail(pointer, _L7, f"must match '#N' or 'owner/repo#N', got {value!r}")
    return value


def _parse_issue(record: Mapping[object, object], pointer: str, required_by: str | None, ctx: _Context) -> str | None:
    """L7: the optional issue reference; *required_by* names the owner that demands one."""
    issue_pointer = f"{pointer}.{_ISSUE}"
    if _ISSUE in record:
        return _check_issue(record[_ISSUE], issue_pointer, ctx)
    if required_by is not None:
        ctx.fail(issue_pointer, _L7, f"an issue is required by {required_by}")
    return None


def _parse_key(record: Mapping[object, object], pointer: str, ctx: _Context) -> DeadSymbolKey:
    """L10: a dotted ASCII module path and a bare identifier name."""
    module = record[_MODULE]
    if not isinstance(module, str) or not _MODULE_PATTERN.fullmatch(module):
        ctx.fail(f"{pointer}.{_MODULE}", _L10, f"must be a dotted ASCII identifier path, got {module!r}")
    name = record[_NAME]
    if not isinstance(name, str) or not name.isidentifier():
        ctx.fail(f"{pointer}.{_NAME}", _L10, f"must be a bare identifier (no dots), got {name!r}")
    return DeadSymbolKey(module, name)


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


def _check_top_level(document: object, ctx: _Context) -> dict[object, object]:
    """L2 (exact top-level key set) and L4 (schema version)."""
    top = _require_mapping(document, _ROOT_POINTER, _L2, ctx)
    missing = _TOP_LEVEL_KEYS - set(top)
    unknown = set(top) - _TOP_LEVEL_KEYS
    if missing or unknown:
        ctx.fail(_ROOT_POINTER, _L2, f"top-level keys must be exactly {sorted(_TOP_LEVEL_KEYS)}; missing {sorted(missing)}, unknown {_sorted_keys(unknown)}")
    version = top[_SCHEMA_VERSION_KEY]
    if type(version) is not int or version != _SCHEMA_VERSION:
        ctx.fail(_SCHEMA_VERSION_KEY, _L4, f"must be the int {_SCHEMA_VERSION}, got {version!r}")
    return top


def _parse_category(category_id: object, value: object, ctx: _Context) -> AllowlistCategory:
    pointer = f"{_CATEGORIES}.{category_id}"
    if not isinstance(category_id, str) or not _CATEGORY_ID_PATTERN.fullmatch(category_id):
        ctx.fail(pointer, _CATEGORY_ID_RULE, f"category id must match '^category_[a-z0-9_]+$', got {category_id!r}")
    record = _check_record_keys(value, pointer, _CATEGORY_KEYS, ctx)
    rationale = _require_text(record[_RATIONALE], f"{pointer}.{_RATIONALE}", ctx)
    requires_issue = record[_REQUIRES_ISSUE]
    if not isinstance(requires_issue, bool):
        ctx.fail(f"{pointer}.{_REQUIRES_ISSUE}", _L7, f"must be a YAML bool, got {requires_issue!r}")
    target = _optional_text(record, _TARGET, pointer, ctx)
    return AllowlistCategory(id=category_id, rationale=rationale, requires_issue=requires_issue, target=target)


def _parse_categories(value: object, ctx: _Context) -> dict[str, AllowlistCategory]:
    raw = _require_mapping(value, _CATEGORIES, _L2, ctx)
    categories: dict[str, AllowlistCategory] = {}
    for category_id, record in raw.items():
        category = _parse_category(category_id, record, ctx)
        categories[category.id] = category
    return categories


def _parse_entry(index: int, value: object, categories: Mapping[str, AllowlistCategory], ctx: _Context) -> AllowlistEntry:
    pointer = f"{_ENTRIES}[{index}]"
    record = _check_record_keys(value, pointer, _ENTRY_KEYS, ctx)
    key = _parse_key(record, pointer, ctx)
    category_id = record[_CATEGORY]
    if not isinstance(category_id, str) or category_id not in categories:
        ctx.fail(f"{pointer}.{_CATEGORY}", _L7, f"names an undeclared category {category_id!r}")
    rationale = _optional_text(record, _RATIONALE, pointer, ctx)
    required_by = f"category {category_id!r} (requires_issue: true)" if categories[category_id].requires_issue else None
    issue = _parse_issue(record, pointer, required_by, ctx)
    return AllowlistEntry(key=key, category=category_id, rationale=rationale, issue=issue)


def _parse_entries(value: object, categories: Mapping[str, AllowlistCategory], ctx: _Context) -> tuple[AllowlistEntry, ...]:
    raw = _require_list(value, _ENTRIES, _L2, ctx)
    return tuple(_parse_entry(index, record, categories, ctx) for index, record in enumerate(raw))


def _parse_widened_entry(index: int, value: object, ctx: _Context) -> WidenedEntry:
    pointer = f"{_WIDENED}.{_ENTRIES}[{index}]"
    record = _check_record_keys(value, pointer, _WIDENED_ENTRY_KEYS, ctx)
    return WidenedEntry(key=_parse_key(record, pointer, ctx), note=_optional_text(record, _NOTE, pointer, ctx))


def _parse_widened(value: object, ctx: _Context) -> tuple[tuple[WidenedEntry, ...], str, str]:
    """The widened section: ``(entries, rationale, issue)``; the issue is always required (L7)."""
    record = _check_record_keys(value, _WIDENED, _WIDENED_KEYS, ctx)
    rationale = _require_text(record[_RATIONALE], f"{_WIDENED}.{_RATIONALE}", ctx)
    issue_pointer = f"{_WIDENED}.{_ISSUE}"
    if _ISSUE not in record:
        ctx.fail(issue_pointer, _L7, f"an issue is required by the {_WIDENED} section")
    issue = _check_issue(record[_ISSUE], issue_pointer, ctx)
    raw_entries = _require_list(record[_ENTRIES], f"{_WIDENED}.{_ENTRIES}", _L5, ctx)
    entries = tuple(_parse_widened_entry(index, entry, ctx) for index, entry in enumerate(raw_entries))
    return entries, rationale, issue


# ---------------------------------------------------------------------------
# Whole-file rules
# ---------------------------------------------------------------------------


def _check_unique(entries: Sequence[AllowlistEntry], widened: Sequence[WidenedEntry], ctx: _Context) -> None:
    """L8: ``(module, name)`` is unique across ``entries`` and the widened entries."""
    located = [(entry.key, f"{_ENTRIES}[{index}]") for index, entry in enumerate(entries)]
    located += [(entry.key, f"{_WIDENED}.{_ENTRIES}[{index}]") for index, entry in enumerate(widened)]
    first_seen: dict[DeadSymbolKey, str] = {}
    for key, pointer in located:
        if key in first_seen:
            ctx.fail(pointer, _L8, f"duplicate (module, name) {key}; first declared at {first_seen[key]}")
        first_seen[key] = pointer


def _check_no_tombstones(categories: Mapping[str, AllowlistCategory], entries: Sequence[AllowlistEntry], ctx: _Context) -> None:
    """L9: every declared category has at least one entry."""
    used = {entry.category for entry in entries}
    for category_id in categories:
        if category_id not in used:
            ctx.fail(f"{_CATEGORIES}.{category_id}", _L9, "declares no entries (a tombstone); delete the category")


def load_allowlist(path: Path = ALLOWLIST_PATH) -> DeadSymbolAllowlist:
    """Load and validate the allowlist at *path* (rules L1–L10); raise :class:`AllowlistSchemaError`."""
    ctx = _Context(path)
    top = _check_top_level(_parse(path), ctx)
    categories = _parse_categories(top[_CATEGORIES], ctx)
    entries = _parse_entries(top[_ENTRIES], categories, ctx)
    widened_entries, widened_rationale, widened_issue = _parse_widened(top[_WIDENED], ctx)
    _check_unique(entries, widened_entries, ctx)
    _check_no_tombstones(categories, entries, ctx)
    return DeadSymbolAllowlist(
        categories=MappingProxyType(categories),
        entries=entries,
        widened_entries=widened_entries,
        widened_rationale=widened_rationale,
        widened_issue=widened_issue,
    )


# Loaded at import, so a schema error fails collection loudly. One parse; the
# two frozensets are views of it.
ALLOWLIST: Final[DeadSymbolAllowlist] = load_allowlist()
SYMBOL_ALLOWLIST: Final[frozenset[DeadSymbolKey]] = ALLOWLIST.keys
WIDENED_SCOPE_GRANDFATHERED_470: Final[frozenset[str]] = ALLOWLIST.widened_qualified
