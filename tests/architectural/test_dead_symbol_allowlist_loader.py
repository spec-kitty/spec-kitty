"""Loader tests for the dead-symbol ``(module, name)`` allowlist (#5346, FR-009).

Covers ``tests/architectural/_dead_symbol_allowlist.py``, the pure,
schema-enforcing loader of ``tests/architectural/dead_symbol_allowlist.yaml``
(``contracts/dead-symbol-allowlist.md`` §1, rules L1–L10):

* **M12**, the schema battery: one scratch-YAML plant per rule, each raising
  ``AllowlistSchemaError`` that names the rule id and the location. M12
  replaces the gate's cross-category duplicate guards and closes the
  intra-category blind spot (the duplicate ``check_push_safety`` literal that a
  frozenset union silently collapsed).
* a valid minimal document loads into the documented in-memory model;
* real-file invariants that must survive the gate switch (WP12). The allowlist
  *size* is deliberately not asserted here: it lives only in
  ``_baselines.yaml``.

The loader is imported **inside** every test (through :func:`_loader`), never
at module scope, so this file collects cleanly before the loader exists and
each test is red on its own (charter C-011, failing-first).
"""

from __future__ import annotations

import ast
import copy
import importlib
from collections.abc import Callable, Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

pytestmark = [pytest.mark.architectural]

_LOADER_MODULE = "tests.architectural._dead_symbol_allowlist"
_LOADER_FILE = Path(__file__).with_name("_dead_symbol_allowlist.py")

_ENTRIES = "entries"
_CATEGORIES = "categories"
_WIDENED = "widened_grandfathered_470"
_RATIONALE = "rationale"
_ISSUE = "issue"
_CATEGORY = "category"
_MODULE = "module"
_NAME = "name"
_ALPHA = "category_alpha"
_BETA = "category_beta"

# Keys that re-invite positional or content identity. The loader refuses them
# at every level (rule L5); the real-file test asserts it on the raw document.
_FORBIDDEN_KEYS = frozenset({"line", "body_hash", "source_module"})

# Packages the loader must never import: it is a pure leaf (contract §1).
_PRODUCT_PACKAGES = frozenset({"specify_cli", "charter", "kernel", "glossary", "runtime", "mission_runtime", "doctrine"})


def _loader() -> ModuleType:
    """The loader module; raises ``ModuleNotFoundError`` until it exists (the C-011 red)."""
    return importlib.import_module(_LOADER_MODULE)


def _minimal() -> dict[str, Any]:
    """A valid schema-v1 document with two categories, three entries and two widened entries."""
    return {
        "schema_version": 1,
        _CATEGORIES: {
            _ALPHA: {_RATIONALE: "Alpha category rationale", "requires_issue": False},
            _BETA: {_RATIONALE: "Beta category rationale", "requires_issue": True, "target": "0 by the next slice"},
        },
        _ENTRIES: [
            {_MODULE: "pkg.alpha", _NAME: "AlphaThing", _CATEGORY: _ALPHA},
            {_MODULE: "pkg.alpha", _NAME: "OtherThing", _CATEGORY: _ALPHA, _RATIONALE: "its own rationale"},
            {_MODULE: "pkg.beta", _NAME: "beta_func", _CATEGORY: _BETA, _ISSUE: "#1234"},
        ],
        _WIDENED: {
            _RATIONALE: "Widened debt, triaged per entry",
            _ISSUE: "#633",
            _ENTRIES: [
                {_MODULE: "pkg.gamma", _NAME: "gamma_helper", "note": "kept as a test seam"},
                {_MODULE: "pkg.gamma", _NAME: "GAMMA"},
            ],
        },
    }


def _dump(tmp_path: Path, doc_or_text: dict[str, Any] | str) -> Path:
    """Write a scratch allowlist; raw text is needed for duplicate-key plants."""
    text = doc_or_text if isinstance(doc_or_text, str) else yaml.safe_dump(doc_or_text, sort_keys=False)
    path = tmp_path / "allowlist.yaml"
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# M12 plants: (id, mutation of the minimal document, rule, pointers the message names)
# ---------------------------------------------------------------------------

_Mutation = Callable[[dict[str, Any]], None]


def _append_entry(entry: dict[str, Any]) -> _Mutation:
    def mutate(doc: dict[str, Any]) -> None:
        doc[_ENTRIES].append(entry)

    return mutate


def _set_field(section: str, index: int, field: str, value: object) -> _Mutation:
    def mutate(doc: dict[str, Any]) -> None:
        doc[section][index][field] = value

    return mutate


def _set_category_field(category: str, field: str, value: object) -> _Mutation:
    def mutate(doc: dict[str, Any]) -> None:
        doc[_CATEGORIES][category][field] = value

    return mutate


def _drop_entry_field(index: int, field: str) -> _Mutation:
    def mutate(doc: dict[str, Any]) -> None:
        del doc[_ENTRIES][index][field]

    return mutate


def _append_widened(entry: dict[str, Any]) -> _Mutation:
    def mutate(doc: dict[str, Any]) -> None:
        doc[_WIDENED][_ENTRIES].append(entry)

    return mutate


def _set_widened_field(field: str, value: object) -> _Mutation:
    def mutate(doc: dict[str, Any]) -> None:
        doc[_WIDENED][field] = value

    return mutate


def _drop_widened_field(field: str) -> _Mutation:
    def mutate(doc: dict[str, Any]) -> None:
        del doc[_WIDENED][field]

    return mutate


def _set_top(key: str, value: object) -> _Mutation:
    def mutate(doc: dict[str, Any]) -> None:
        doc[key] = value

    return mutate


def _drop_top(key: str) -> _Mutation:
    def mutate(doc: dict[str, Any]) -> None:
        del doc[key]

    return mutate


def _add_tombstone(doc: dict[str, Any]) -> None:
    doc[_CATEGORIES]["category_gamma"] = {_RATIONALE: "declared but empty", "requires_issue": False}


def _empty_entries_with_categories(doc: dict[str, Any]) -> None:
    doc[_ENTRIES] = []


def _rename_alpha_to_bad_id(doc: dict[str, Any]) -> None:
    doc[_CATEGORIES]["cat_x"] = doc[_CATEGORIES].pop(_ALPHA)
    for entry in doc[_ENTRIES]:
        if entry[_CATEGORY] == _ALPHA:
            entry[_CATEGORY] = "cat_x"


_DUPLICATE_ALPHA = {_MODULE: "pkg.alpha", _NAME: "AlphaThing"}
_WIDENED_1 = "widened_grandfathered_470.entries[1]"
_WIDENED_2 = "widened_grandfathered_470.entries[2]"

_M12_PLANTS: list[tuple[str, _Mutation, str, tuple[str, ...]]] = [
    # L8: whole-file (module, name) uniqueness; the error names both locations.
    ("dup-same-category", _append_entry({**_DUPLICATE_ALPHA, _CATEGORY: _ALPHA}), "L8", ("entries[3]", "entries[0]")),
    (
        "dup-cross-category",
        _append_entry({**_DUPLICATE_ALPHA, _CATEGORY: _BETA, _ISSUE: "#1"}),
        "L8",
        ("entries[3]", "entries[0]"),
    ),
    ("dup-entries-and-widened", _append_widened(dict(_DUPLICATE_ALPHA)), "L8", (_WIDENED_2, "entries[0]")),
    ("dup-within-widened", _append_widened({_MODULE: "pkg.gamma", _NAME: "GAMMA"}), "L8", (_WIDENED_2, _WIDENED_1)),
    # L7: category references, requires_issue, issue pattern.
    ("undeclared-category", _set_field(_ENTRIES, 0, _CATEGORY, "category_missing"), "L7", ("entries[0].category",)),
    ("requires-issue-without-issue", _drop_entry_field(2, _ISSUE), "L7", ("entries[2].issue",)),
    ("malformed-issue", _set_field(_ENTRIES, 2, _ISSUE, "1234"), "L7", ("entries[2].issue",)),
    ("malformed-optional-issue", _set_field(_ENTRIES, 0, _ISSUE, "issue 5"), "L7", ("entries[0].issue",)),
    ("requires-issue-not-bool", _set_category_field(_BETA, "requires_issue", "yes"), "L7", ("categories.category_beta.requires_issue",)),
    ("widened-issue-missing", _drop_widened_field(_ISSUE), "L7", ("widened_grandfathered_470.issue",)),
    ("widened-issue-malformed", _set_widened_field(_ISSUE, "633"), "L7", ("widened_grandfathered_470.issue",)),
    # L6: rationales are non-empty strings.
    ("empty-category-rationale", _set_category_field(_ALPHA, _RATIONALE, "   "), "L6", ("categories.category_alpha.rationale",)),
    ("empty-entry-rationale", _set_field(_ENTRIES, 1, _RATIONALE, ""), "L6", ("entries[1].rationale",)),
    ("empty-widened-rationale", _set_widened_field(_RATIONALE, ""), "L6", ("widened_grandfathered_470.rationale",)),
    # L5: unknown (and missing) keys in every record kind.
    ("unknown-key-line", _set_field(_ENTRIES, 0, "line", 12), "L5", ("entries[0]", "line")),
    ("unknown-key-body-hash", _set_field(_ENTRIES, 0, "body_hash", "ab" * 32), "L5", ("entries[0]", "body_hash")),
    ("unknown-key-retired-provenance", _append_widened({_MODULE: "pkg.delta", _NAME: "D", "source_module": "pkg.delta"}), "L5", (_WIDENED_2,)),
    ("unknown-category-key", _set_category_field(_ALPHA, "line", 3), "L5", ("categories.category_alpha", "line")),
    ("unknown-widened-key", _set_widened_field("body_hash", "x"), "L5", ("widened_grandfathered_470", "body_hash")),
    ("missing-entry-module", _drop_entry_field(0, _MODULE), "L5", ("entries[0]", _MODULE)),
    # L9: no tombstone categories.
    ("tombstone-category", _add_tombstone, "L9", ("categories.category_gamma",)),
    ("empty-entries-with-categories", _empty_entries_with_categories, "L9", ("categories.category_alpha",)),
    # L4: schema version is exactly the int 1.
    ("schema-version-2", _set_top("schema_version", 2), "L4", ("schema_version",)),
    ("schema-version-bool", _set_top("schema_version", True), "L4", ("schema_version",)),
    # L2: exact top-level key set and section types.
    ("missing-top-level-section", _drop_top(_WIDENED), "L2", (_WIDENED,)),
    ("extra-top-level-section", _set_top("allowlist_size", 3), "L2", ("allowlist_size",)),
    ("entries-not-a-list", _set_top(_ENTRIES, {"a": 1}), "L2", (_ENTRIES,)),
    # L10: module is a dotted ASCII identifier path; name a bare identifier.
    ("bad-module-path", _set_field(_ENTRIES, 0, _MODULE, "specify_cli..x"), "L10", ("entries[0].module",)),
    ("non-ascii-module-path", _set_field(_ENTRIES, 0, _MODULE, "pkg.été"), "L10", ("entries[0].module",)),
    ("dotted-name", _set_field(_ENTRIES, 0, _NAME, "a.b"), "L10", ("entries[0].name",)),
    ("widened-bad-name", _append_widened({_MODULE: "pkg.delta", _NAME: "not an identifier"}), "L10", (f"{_WIDENED_2}.name",)),
    # Category-id pattern (data-model §1.2).
    ("bad-category-id", _rename_alpha_to_bad_id, "category-id", ("categories.cat_x",)),
]


@pytest.mark.parametrize(
    ("mutation", "rule", "pointers"),
    [pytest.param(mutation, rule, pointers, id=plant_id) for plant_id, mutation, rule, pointers in _M12_PLANTS],
)
def test_m12_schema_plant_is_rejected(tmp_path: Path, mutation: _Mutation, rule: str, pointers: tuple[str, ...]) -> None:
    """M12: every single-rule plant raises ``AllowlistSchemaError`` naming the rule and the location."""
    loader = _loader()
    document = _minimal()
    mutation(document)
    path = _dump(tmp_path, document)

    with pytest.raises(loader.AllowlistSchemaError) as excinfo:
        loader.load_allowlist(path)

    error = excinfo.value
    message = str(error)
    assert error.rule == rule, message
    assert isinstance(error, ValueError), "AllowlistSchemaError must stay a ValueError"
    assert f"[{rule}]" in message, message
    assert str(path) in message, message
    for pointer in pointers:
        assert pointer in message, f"{pointer!r} not named in: {message}"


_DUPLICATE_CATEGORY_TEXT = """\
schema_version: 1
categories:
  category_alpha:
    rationale: first declaration
    requires_issue: false
  category_alpha:
    rationale: second declaration silently wins under plain PyYAML
    requires_issue: false
entries:
- module: pkg.alpha
  name: AlphaThing
  category: category_alpha
widened_grandfathered_470:
  rationale: widened
  issue: "#633"
  entries: []
"""

_DUPLICATE_TOP_LEVEL_TEXT = """\
schema_version: 1
categories:
  category_alpha:
    rationale: alpha
    requires_issue: false
entries:
- module: pkg.alpha
  name: AlphaThing
  category: category_alpha
entries:
- module: pkg.alpha
  name: OtherThing
  category: category_alpha
widened_grandfathered_470:
  rationale: widened
  issue: "#633"
  entries: []
"""

_DUPLICATE_ENTRY_FIELD_TEXT = """\
schema_version: 1
categories:
  category_alpha:
    rationale: alpha
    requires_issue: false
entries:
- module: pkg.alpha
  name: AlphaThing
  name: OtherThing
  category: category_alpha
widened_grandfathered_470:
  rationale: widened
  issue: "#633"
  entries: []
"""


@pytest.mark.parametrize(
    ("text", "key", "line"),
    [
        pytest.param(_DUPLICATE_CATEGORY_TEXT, "category_alpha", 6, id="dup-category-key"),
        pytest.param(_DUPLICATE_TOP_LEVEL_TEXT, "entries", 10, id="dup-top-level-key"),
        pytest.param(_DUPLICATE_ENTRY_FIELD_TEXT, "name", 9, id="dup-entry-field"),
    ],
)
def test_m12_duplicate_mapping_key_is_rejected(tmp_path: Path, text: str, key: str, line: int) -> None:
    """M12 / L3: a repeated mapping key at any level is refused, not silently last-wins."""
    loader = _loader()
    path = _dump(tmp_path, text)
    assert yaml.safe_load(text) is not None, "plain PyYAML accepts the plant (the silent merge L3 exists to catch)"

    with pytest.raises(loader.AllowlistSchemaError) as excinfo:
        loader.load_allowlist(path)

    message = str(excinfo.value)
    assert excinfo.value.rule == "L3", message
    assert "[L3]" in message and repr(key) in message and f"line {line}" in message, message


@pytest.mark.parametrize(
    ("text", "rule"),
    [
        pytest.param("schema_version: [unclosed\n", "L1", id="not-yaml"),
        pytest.param("- just\n- a list\n", "L2", id="top-level-not-a-mapping"),
    ],
)
def test_m12_unparseable_or_non_mapping_document_is_rejected(tmp_path: Path, text: str, rule: str) -> None:
    """M12 / L1–L2: the file must parse, and its top level must be a mapping."""
    loader = _loader()
    with pytest.raises(loader.AllowlistSchemaError) as excinfo:
        loader.load_allowlist(_dump(tmp_path, text))
    assert excinfo.value.rule == rule, str(excinfo.value)


def test_m12_missing_file_is_rejected(tmp_path: Path) -> None:
    """M12 / L1: a missing allowlist file fails loudly, naming the path."""
    loader = _loader()
    missing = tmp_path / "absent.yaml"
    with pytest.raises(loader.AllowlistSchemaError) as excinfo:
        loader.load_allowlist(missing)
    assert excinfo.value.rule == "L1"
    assert str(missing) in str(excinfo.value)


def test_fully_burned_down_document_loads(tmp_path: Path) -> None:
    """Edge case B4: ``entries: []`` is valid only with an empty ``categories`` mapping (L9 vacuous)."""
    loader = _loader()
    document = _minimal()
    document[_CATEGORIES] = {}
    document[_ENTRIES] = []

    allowlist = loader.load_allowlist(_dump(tmp_path, document))

    assert allowlist.keys == frozenset()
    assert allowlist.entries == ()
    assert len(allowlist.widened_qualified) == 2


def test_valid_minimal_document_loads_into_the_model(tmp_path: Path) -> None:
    """A valid document loads; ``keys`` / ``widened_qualified`` have the documented content and types."""
    loader = _loader()
    key = loader.DeadSymbolKey

    allowlist = loader.load_allowlist(_dump(tmp_path, _minimal()))

    assert isinstance(allowlist.keys, frozenset)
    assert allowlist.keys == frozenset({key("pkg.alpha", "AlphaThing"), key("pkg.alpha", "OtherThing"), key("pkg.beta", "beta_func")})
    assert isinstance(allowlist.widened_qualified, frozenset)
    assert allowlist.widened_qualified == frozenset({"pkg.gamma::gamma_helper", "pkg.gamma::GAMMA"})
    assert all(isinstance(item, str) for item in allowlist.widened_qualified)
    assert str(key("pkg.alpha", "AlphaThing")) == "pkg.alpha::AlphaThing"

    assert list(allowlist.categories) == [_ALPHA, _BETA]
    beta = allowlist.categories[_BETA]
    assert (beta.id, beta.requires_issue, beta.target) == (_BETA, True, "0 by the next slice")
    assert allowlist.categories[_ALPHA].target is None

    first, second, third = allowlist.entries
    assert first.rationale is None and first.issue is None
    assert first.effective_rationale(allowlist.categories) == "Alpha category rationale"
    assert second.effective_rationale(allowlist.categories) == "its own rationale"
    assert (third.category, third.issue) == (_BETA, "#1234")

    assert allowlist.widened_rationale == "Widened debt, triaged per entry"
    assert allowlist.widened_issue == "#633"
    assert [entry.note for entry in allowlist.widened_entries] == ["kept as a test seam", None]


def test_cross_repo_issue_reference_is_accepted(tmp_path: Path) -> None:
    """L7: the ``owner/repo#N`` issue form is valid alongside ``#N``."""
    loader = _loader()
    document = _minimal()
    document[_ENTRIES][2][_ISSUE] = "spec-kitty/spec-kitty#5346"

    allowlist = loader.load_allowlist(_dump(tmp_path, document))

    assert allowlist.entries[2].issue == "spec-kitty/spec-kitty#5346"


def test_stale_verdict_vocabulary() -> None:
    """The shared verdict vocabulary has exactly the five upper-case verdicts, in precedence order."""
    loader = _loader()
    assert [verdict.value for verdict in loader.StaleVerdict] == ["INVALID", "GONE", "REVIVED", "SUPERSEDED", "MOOT"]
    assert loader.StaleVerdict.GONE == "GONE"


# ---------------------------------------------------------------------------
# Real-file invariants (must survive the gate switch; never the size)
# ---------------------------------------------------------------------------


def _mapping_keys(node: object) -> Iterator[str]:
    """Every mapping key anywhere in a parsed YAML document."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield str(key)
            yield from _mapping_keys(value)
    elif isinstance(node, list):
        for item in node:
            yield from _mapping_keys(item)


def test_real_allowlist_loads_as_one_parse() -> None:
    """The committed YAML loads; the import-time views come from the single ``ALLOWLIST`` parse."""
    loader = _loader()

    reloaded = loader.load_allowlist()

    assert reloaded.keys == loader.ALLOWLIST.keys
    assert loader.ALLOWLIST.keys == loader.SYMBOL_ALLOWLIST
    assert loader.ALLOWLIST.widened_qualified == loader.WIDENED_SCOPE_GRANDFATHERED_470
    assert loader.ALLOWLIST_PATH.name == "dead_symbol_allowlist.yaml"


def test_real_allowlist_views_are_non_empty_typed_frozensets() -> None:
    """``SYMBOL_ALLOWLIST`` / ``WIDENED_SCOPE_GRANDFATHERED_470`` are non-empty frozensets of the right types."""
    loader = _loader()

    assert isinstance(loader.SYMBOL_ALLOWLIST, frozenset) and loader.SYMBOL_ALLOWLIST
    assert all(isinstance(key, loader.DeadSymbolKey) for key in loader.SYMBOL_ALLOWLIST)
    assert isinstance(loader.WIDENED_SCOPE_GRANDFATHERED_470, frozenset) and loader.WIDENED_SCOPE_GRANDFATHERED_470
    assert all(isinstance(item, str) and item.count("::") == 1 for item in loader.WIDENED_SCOPE_GRANDFATHERED_470)


def test_real_allowlist_has_no_silent_dedupe() -> None:
    """Every entry is a distinct key: the frozenset views are exactly as long as the entry lists."""
    loader = _loader()
    allowlist = loader.ALLOWLIST

    assert len(loader.SYMBOL_ALLOWLIST) == len(allowlist.entries)
    assert len(loader.WIDENED_SCOPE_GRANDFATHERED_470) == len(allowlist.widened_entries)
    assert loader.SYMBOL_ALLOWLIST.isdisjoint(entry.key for entry in allowlist.widened_entries)


def test_real_allowlist_carries_no_forbidden_key() -> None:
    """No positional or content-identity key appears anywhere in the raw committed document."""
    loader = _loader()
    raw = yaml.safe_load(loader.ALLOWLIST_PATH.read_text(encoding="utf-8"))

    found = sorted(set(_mapping_keys(copy.deepcopy(raw))) & _FORBIDDEN_KEYS)

    assert found == [], f"forbidden keys in {loader.ALLOWLIST_PATH.name}: {found}"


def test_loader_is_a_pure_leaf() -> None:
    """The loader imports no product package and no other test module (contract §1: pure)."""
    _loader()
    tree = ast.parse(_LOADER_FILE.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module.split(".")[0])

    assert "yaml" in imported, "the probe must see the loader's own imports"
    assert not imported & (_PRODUCT_PACKAGES | {"tests"}), sorted(imported & (_PRODUCT_PACKAGES | {"tests"}))
