"""IC-KEY — focused unit tests for ``tests/architectural/_symbol_key.py`` (WP01).

Not under ``tests/architectural/`` -- these are focused, fast unit probes of the
resolver + classifier PRIMITIVES on synthetic fixtures (no shard-map tax); the
(a-k) bite battery through the production ``_compute_offenders``/stale path
(C-007) belongs to WP-REKEY, driven against the real corpus.

Covers (WP01 T007):
* content-tier relocation invariance: module move + sibling reorder +
  blank/comment insertion (NFR-001).
* DoD-j key-invariance: AnnAssign annotation-whitespace, single-alias
  ``ImportFrom`` (distinct from an edited sibling), and the 3.11<->3.12
  ``code_tokens_by_line`` f-string parity dimension, exercised through the
  NEW branches (the WP06 spike only proved ``ClassDef``/``FunctionDef``).
* facade-dict resolution, BOTH shapes (sync 2-tuple + runtime 1-value).
* the live collision classifier: a synthetic reproduction of the real
  ``ArtifactKind`` trio shape (three modules each doing
  ``from charter.offering.artifact_kinds import ArtifactKind``) -> module_path
  escalation or fail-closed.
* ``None``-key fail-closed (never silently exempted) + ``unresolved_reason``.
* a perf-budget assertion on ``classify_collisions``.
"""

from __future__ import annotations

import ast
import dataclasses

import pytest

from specify_cli.contracts.anchoring import code_tokens_by_line
from tests.architectural._symbol_key import (
    CorpusModule,
    Location,
    SymbolKey,
    alias_body_hash,
    body_hash,
    classify_collisions,
    definition_span,
    key_tier,
    perf_budget_seconds,
    resolve_symbol_key,
    timed_classify_collisions,
    unresolved_reason,
)

pytestmark = [pytest.mark.unit]


def _module(source: str, containing_pkg: str = "pkg") -> CorpusModule:
    return CorpusModule(tree=ast.parse(source), source=source, containing_pkg=containing_pkg)


# ---------------------------------------------------------------------------
# SymbolKey / as_tuple
# ---------------------------------------------------------------------------


def test_symbol_key_content_tier_as_tuple() -> None:
    key = SymbolKey(bare_name="Foo", body_hash="abc123")
    assert key.is_content_tier
    assert key.as_tuple() == ("Foo", "abc123")


def test_symbol_key_module_path_tier_as_tuple() -> None:
    key = SymbolKey(bare_name="Foo", body_hash="abc123", module_path="pkg.mod")
    assert not key.is_content_tier
    assert key.as_tuple() == ("Foo", "pkg.mod", "abc123")


# ---------------------------------------------------------------------------
# T001 — ClassDef / FunctionDef / Assign body_hash + definition_span
# ---------------------------------------------------------------------------

_BASE_CLASS_SRC = '''class Sample:
    """Doc."""

    field_one: int
    field_two: str
'''


def test_definition_span_class_def() -> None:
    tree = ast.parse(_BASE_CLASS_SRC)
    span = definition_span(tree, "Sample")
    assert span == (1, 5)


def test_body_hash_stable_under_blank_line_insertion() -> None:
    mutated = '''class Sample:
    """Doc."""


    field_one: int

    field_two: str
'''
    tree_a, tree_b = ast.parse(_BASE_CLASS_SRC), ast.parse(mutated)
    span_a = definition_span(tree_a, "Sample")
    span_b = definition_span(tree_b, "Sample")
    assert span_a is not None
    assert span_b is not None
    assert body_hash(_BASE_CLASS_SRC, span_a) == body_hash(mutated, span_b)


def test_body_hash_changes_on_genuine_field_edit() -> None:
    """Negative control (NFR-002 bite): a real semantic change must change the hash."""
    mutated = '''class Sample:
    """Doc."""

    field_one: int
    field_two: bool
'''
    tree_a, tree_b = ast.parse(_BASE_CLASS_SRC), ast.parse(mutated)
    span_a = definition_span(tree_a, "Sample")
    span_b = definition_span(tree_b, "Sample")
    assert span_a is not None
    assert span_b is not None
    assert body_hash(_BASE_CLASS_SRC, span_a) != body_hash(mutated, span_b)


def _class_body_hash(source: str) -> str:
    span = definition_span(ast.parse(source), "Sample")
    assert span is not None
    return body_hash(source, span)


def test_body_hash_stable_under_intra_class_comment_insertion() -> None:
    """A comment inserted inside the class body must not move the key (NFR-001)."""
    mutated = '''class Sample:
    """Doc."""

    field_one: int
    # a comment describing field_two, added later
    field_two: str
'''
    assert _class_body_hash(_BASE_CLASS_SRC) == _class_body_hash(mutated)


def test_body_hash_stable_under_intra_line_whitespace_reformat() -> None:
    """Intra-line whitespace reformatting must not move the key (NFR-001)."""
    mutated = '''class Sample:
    """Doc."""

    field_one   :    int
    field_two:str
'''
    assert _class_body_hash(_BASE_CLASS_SRC) == _class_body_hash(mutated)


def test_body_hash_control_real_edit_alters_key_despite_noise() -> None:
    """Control: comment + whitespace noise PLUS a real edit still changes the key."""
    mutated = '''class Sample:
    """Doc."""

    field_one   :    int
    # noise
    field_two:bool
'''
    assert _class_body_hash(_BASE_CLASS_SRC) != _class_body_hash(mutated)


def test_definition_span_plain_assign() -> None:
    src = "TIMEOUT = 30\n"
    tree = ast.parse(src)
    assert definition_span(tree, "TIMEOUT") == (1, 1)


# ---------------------------------------------------------------------------
# T002 — AnnAssign branch (FR-002, HIGHEST priority)
# ---------------------------------------------------------------------------


def test_definition_span_ann_assign_typed_constant() -> None:
    src = "TTL_SECONDS: int = 3600\n"
    tree = ast.parse(src)
    assert definition_span(tree, "TTL_SECONDS") == (1, 1)


def test_ann_assign_bare_annotation_is_still_hashable() -> None:
    """A bare ``X: int`` (no value) still has line tokens and is hashable."""
    src = "SENTINEL: int\n"
    tree = ast.parse(src)
    span = definition_span(tree, "SENTINEL")
    assert span is not None
    assert body_hash(src, span)  # non-empty digest, does not raise


def test_ann_assign_not_confused_by_non_all_ann_assign_before_it() -> None:
    """T001-regression guard: a leading, unrelated AnnAssign must not blind
    the walker to a LATER real binding (mirrors the gate's own T001 fix)."""
    src = 'MESSAGES: dict[str, str] = {"x": "y"}\nTTL_SECONDS: int = 3600\n'
    tree = ast.parse(src)
    assert definition_span(tree, "TTL_SECONDS") == (2, 2)


def test_resolve_symbol_key_none_without_ann_assign_support_would_be_a_regression() -> None:
    """Positive control proving FR-002 is wired end-to-end via resolve_symbol_key,
    not just definition_span in isolation."""
    # Inert test-data literal (the path value is irrelevant -- only its AnnAssign
    # shape is under test). Uses a non-shared-temp absolute sentinel so the
    # tmp-literal burndown gate (test_no_tmp_paths_in_tests) stays green
    # (relocation-hardened-dead-code-scanners-01KX958P WP02: WP01 shipped a
    # bare shared-temp literal here that tripped the gate).
    src = "CACHE_PATH: str = '/opt/app-cache'\n"
    module = _module(src)
    key = resolve_symbol_key("CACHE_PATH", "pkg.consts", module)
    assert key is not None
    assert key.bare_name == "CACHE_PATH"


# --- DoD-j: AnnAssign annotation-whitespace key-invariance -----------------


def test_dod_j_ann_assign_annotation_whitespace_invariance() -> None:
    """DoD-j: ``X:int`` vs ``X : int`` must produce an identical body_hash --
    the spike never proved this (no AnnAssign branch existed)."""
    tight = "TTL_SECONDS:int=3600\n"
    spaced = "TTL_SECONDS : int = 3600\n"
    tree_tight, tree_spaced = ast.parse(tight), ast.parse(spaced)
    span_tight = definition_span(tree_tight, "TTL_SECONDS")
    span_spaced = definition_span(tree_spaced, "TTL_SECONDS")
    assert span_tight is not None
    assert span_spaced is not None
    assert body_hash(tight, span_tight) == body_hash(spaced, span_spaced)


# ---------------------------------------------------------------------------
# T004 — single-alias ImportFrom hash (FR-004)
# ---------------------------------------------------------------------------


def _find_alias(tree: ast.Module, bare_name: str) -> ast.alias:
    node = tree.body[0]
    assert isinstance(node, ast.ImportFrom)
    for alias in node.names:
        if (alias.asname or alias.name) == bare_name:
            return alias
    raise AssertionError(f"alias {bare_name!r} not found")


def test_dod_j_single_alias_distinct_from_edited_sibling() -> None:
    """FR-004 acceptance: editing sibling ``Alpha`` must NOT change ``B``'s hash
    (a whole-statement hash would be sibling-contaminated -- zero relocation
    tolerance for multi-target ImportFrom)."""
    src = "from foo.bar import Alpha, Beta as B, Gamma\n"
    tree = ast.parse(src)
    original = alias_body_hash(src, _find_alias(tree, "B"))

    mutated_src = "from foo.bar import AlphaRenamedCompletely, Beta as B, GammaRenamedToo\n"
    mutated_tree = ast.parse(mutated_src)
    mutated = alias_body_hash(mutated_src, _find_alias(mutated_tree, "B"))

    assert original == mutated


def test_single_alias_hash_stable_across_reflow_to_multiline() -> None:
    """Relocation-tolerance dimension: reflowing a single-line multi-import into
    a parenthesized one-per-line style must not change the target alias's hash."""
    single_line = "from foo.bar import Alpha, Beta as B, Gamma\n"
    multiline = "from foo.bar import (\n    Alpha,\n    Beta as B,\n    Gamma,\n)\n"
    tree_single, tree_multi = ast.parse(single_line), ast.parse(multiline)
    single_hash = alias_body_hash(single_line, _find_alias(tree_single, "B"))
    multi_hash = alias_body_hash(multiline, _find_alias(tree_multi, "B"))
    assert single_hash == multi_hash


def test_single_alias_hash_differs_for_different_bound_names() -> None:
    """Negative control: distinct aliases must not collapse to the same hash."""
    src = "from foo.bar import Alpha, Beta as B, Gamma\n"
    tree = ast.parse(src)
    assert alias_body_hash(src, _find_alias(tree, "Alpha")) != alias_body_hash(src, _find_alias(tree, "Gamma"))


def test_resolve_symbol_key_bare_import_from_single_name() -> None:
    """The real ArtifactKind-trio shape: a bare ``from M import Name`` (no
    asname) must resolve via the single-alias path, not fall through to None."""
    src = "from charter.offering.artifact_kinds import ArtifactKind\n"
    module = _module(src)
    key = resolve_symbol_key("ArtifactKind", "charter.offering.directives", module)
    assert key is not None
    assert key.bare_name == "ArtifactKind"


# ---------------------------------------------------------------------------
# T003 — facade-dict KEY-side resolver, both shapes (FR-003, rescoped)
# ---------------------------------------------------------------------------

_SYNC_STYLE_FACADE_SRC = """
_EVENTS_MODULE = ".events"
_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "Foo": (".bar", "Foo"),
    "Baz": (_EVENTS_MODULE, "Baz"),
}


def __getattr__(name):
    module_path, attr = _LAZY_IMPORTS[name]
"""

_SYNC_TARGET_BAR_SRC = '''class Foo:
    """Doc."""

    x: int
'''

_SYNC_TARGET_EVENTS_SRC = '''class Baz:
    """Doc."""

    y: int
'''


def _sync_style_corpus() -> dict[str, CorpusModule]:
    return {
        "pkg": _module(_SYNC_STYLE_FACADE_SRC, containing_pkg="pkg"),
        "pkg.bar": _module(_SYNC_TARGET_BAR_SRC, containing_pkg="pkg"),
        "pkg.events": _module(_SYNC_TARGET_EVENTS_SRC, containing_pkg="pkg"),
    }


def test_facade_sync_style_two_tuple_resolves_relative_module() -> None:
    """sync/__init__.py shape: {name: (module, attr)} with a literal relative module."""
    corpus = _sync_style_corpus()
    key = resolve_symbol_key("Foo", "pkg", corpus["pkg"], corpus=corpus)
    target_key = resolve_symbol_key("Foo", "pkg.bar", corpus["pkg.bar"], corpus=corpus)
    assert key is not None
    assert target_key is not None
    # The facade key hashes the REAL definition body at the resolved target,
    # proving cross-module resolution actually located it (not a stub).
    assert key.body_hash == target_key.body_hash
    assert key.bare_name == "Foo"


def test_facade_sync_style_two_tuple_resolves_str_const_module() -> None:
    """sync/__init__.py shape: module expressed via a Name resolved through str_consts."""
    corpus = _sync_style_corpus()
    key = resolve_symbol_key("Baz", "pkg", corpus["pkg"], corpus=corpus)
    target_key = resolve_symbol_key("Baz", "pkg.events", corpus["pkg.events"], corpus=corpus)
    assert key is not None
    assert target_key is not None
    assert key.body_hash == target_key.body_hash


_RUNTIME_STYLE_FACADE_SRC = """
from importlib import import_module

_MIGRATE_MODULE = "pkg.migrate"

_EXPORT_MODULES = {
    "AssetDisposition": _MIGRATE_MODULE,
}


def __getattr__(name):
    module_name = _EXPORT_MODULES[name]
    value = getattr(import_module(module_name), name)
    return value
"""

_RUNTIME_TARGET_MIGRATE_SRC = '''class AssetDisposition:
    """Doc."""

    kind: str
'''


def _runtime_style_corpus() -> dict[str, CorpusModule]:
    return {
        "pkg.runtime": _module(_RUNTIME_STYLE_FACADE_SRC, containing_pkg="pkg"),
        "pkg.migrate": _module(_RUNTIME_TARGET_MIGRATE_SRC, containing_pkg="pkg"),
    }


def test_facade_runtime_style_one_value_dict_is_keyable() -> None:
    """runtime/__init__.py shape: {name: module_const} (1-value) -- the gate's
    _record_facade_edges len!=2 guard SKIPS this shape entirely; the KEY side
    must not."""
    corpus = _runtime_style_corpus()
    key = resolve_symbol_key("AssetDisposition", "pkg.runtime", corpus["pkg.runtime"], corpus=corpus)
    target_key = resolve_symbol_key("AssetDisposition", "pkg.migrate", corpus["pkg.migrate"], corpus=corpus)
    assert key is not None
    assert target_key is not None
    assert key.body_hash == target_key.body_hash
    assert key.bare_name == "AssetDisposition"


def test_facade_without_corpus_fails_closed() -> None:
    """T006: a facade entry cannot be verified without the target module's
    real body -- never guessed, always fail-closed."""
    corpus = _sync_style_corpus()
    key = resolve_symbol_key("Foo", "pkg", corpus["pkg"], corpus=None)
    assert key is None


def test_facade_target_module_absent_from_corpus_fails_closed() -> None:
    corpus = {"pkg": _module(_SYNC_STYLE_FACADE_SRC, containing_pkg="pkg")}
    key = resolve_symbol_key("Foo", "pkg", corpus["pkg"], corpus=corpus)
    assert key is None


def test_non_facade_module_has_no_facade_entry_for_unrelated_name() -> None:
    module = _module("x = 1\n")
    assert resolve_symbol_key("NotThere", "pkg.plain", module, corpus={}) is None


# ---------------------------------------------------------------------------
# T005/T006 — live collision classifier + key_tier
# ---------------------------------------------------------------------------

# Synthetic reproduction of the REAL ArtifactKind trio shape: three modules
# each doing a bare `from <origin> import Name` re-export of the SAME name.
# Under alias_body_hash this text is byte-identical ("ArtifactKind") across
# all three sites, so the live index correctly detects the collision --
# exactly mirroring src/charter/offering/{directives,procedures,tactics}/__init__.py.
_TRIO_MODULES = {
    "charter.offering.directives": "from charter.offering.artifact_kinds import ArtifactKind\n__all__ = ['ArtifactKind']\n",
    "charter.offering.procedures": "from charter.offering.artifact_kinds import ArtifactKind\n__all__ = ['ArtifactKind']\n",
    "charter.offering.tactics": "from charter.offering.artifact_kinds import ArtifactKind\n__all__ = ['ArtifactKind']\n",
}


def _artifact_kind_trio_corpus() -> dict[str, CorpusModule]:
    return {path: _module(src, containing_pkg=path) for path, src in _TRIO_MODULES.items()}


def test_classify_collisions_rederives_artifact_kind_trio() -> None:
    """T005: the classifier is LIVE -- it must DISCOVER the trio collision from
    the corpus, not have it hard-coded."""
    index = classify_collisions(_artifact_kind_trio_corpus())
    assert "ArtifactKind" in index
    locations = index["ArtifactKind"]
    assert len(locations) == 3
    assert {loc.module_path for loc in locations} == set(_TRIO_MODULES)
    # All three share one body_hash -- that IS the collision.
    assert len({loc.body_hash for loc in locations}) == 1


def test_key_tier_escalates_collision_to_module_path_when_disambiguating() -> None:
    corpus = _artifact_kind_trio_corpus()
    index = classify_collisions(corpus)
    module = corpus["charter.offering.directives"]
    candidate = resolve_symbol_key("ArtifactKind", "charter.offering.directives", module, corpus=corpus)
    assert candidate is not None
    escalated = key_tier(candidate, "charter.offering.directives", index)
    assert escalated is not None
    assert escalated.module_path == "charter.offering.directives"
    assert escalated.as_tuple() == ("ArtifactKind", "charter.offering.directives", escalated.body_hash)


def test_key_tier_fails_closed_without_a_module_path_to_disambiguate() -> None:
    """D-3: a collision with no module_path supplied cannot be escalated -- fail-closed."""
    corpus = _artifact_kind_trio_corpus()
    index = classify_collisions(corpus)
    module = corpus["charter.offering.directives"]
    candidate = resolve_symbol_key("ArtifactKind", "charter.offering.directives", module, corpus=corpus)
    assert candidate is not None
    assert key_tier(candidate, None, index) is None


def test_key_tier_fails_closed_when_module_path_does_not_participate() -> None:
    """A module_path that is not even one of the colliding locations cannot
    disambiguate -- fail-closed rather than silently accepted."""
    corpus = _artifact_kind_trio_corpus()
    index = classify_collisions(corpus)
    module = corpus["charter.offering.directives"]
    candidate = resolve_symbol_key("ArtifactKind", "charter.offering.directives", module, corpus=corpus)
    assert candidate is not None
    assert key_tier(candidate, "some.unrelated.module", index) is None


def test_key_tier_content_tier_for_a_non_colliding_bare_name() -> None:
    """The common case: exactly one live location -> content tier, unchanged."""
    src = "class Solo:\n    x: int\n"
    module = _module(src, containing_pkg="pkg.solo")
    corpus = {"pkg.solo": _module(f"{src}__all__ = ['Solo']\n", containing_pkg="pkg.solo")}
    index = classify_collisions(corpus)
    candidate = resolve_symbol_key("Solo", "pkg.solo", module)
    assert candidate is not None
    result = key_tier(candidate, "pkg.solo", index)
    assert result is not None
    assert result.is_content_tier
    assert result == candidate


def test_dod_i_new_byte_identical_pair_is_caught_live() -> None:
    """DoD (i) / D-2 regression guard: a NEW byte-identical same-name pair
    (not the ArtifactKind trio) introduced today must ALSO be dynamically
    escalated -- the classifier is re-derived, never a frozen lookup table."""
    src = "class Twin:\n    value: int\n"
    corpus = {
        "pkg.one": _module(f"{src}__all__ = ['Twin']\n", containing_pkg="pkg.one"),
        "pkg.two": _module(f"{src}__all__ = ['Twin']\n", containing_pkg="pkg.two"),
    }
    index = classify_collisions(corpus)
    assert len(index["Twin"]) == 2
    candidate = resolve_symbol_key("Twin", "pkg.one", corpus["pkg.one"])
    assert candidate is not None
    escalated = key_tier(candidate, "pkg.one", index)
    assert escalated is not None
    assert escalated.module_path == "pkg.one"


def test_key_tier_none_key_fails_closed() -> None:
    """T006: a None key (undecidable shape) must fail-closed through key_tier too."""
    assert key_tier(None, "pkg.whatever", {}) is None


# ---------------------------------------------------------------------------
# T006 — fail-closed for None-key + unresolved_reason
# ---------------------------------------------------------------------------


def test_resolve_symbol_key_returns_none_for_undecidable_shape() -> None:
    """A name that appears in nothing recognizable (no def/assign/import/facade)
    is fail-closed, never guessed."""
    module = _module("x = 1\n")
    assert resolve_symbol_key("Ghost", "pkg.plain", module) is None


def test_unresolved_reason_is_non_empty_and_actionable_for_plain_undecidable() -> None:
    module = _module("x = 1\n")
    reason = unresolved_reason("Ghost", "pkg.plain", module)
    assert "Ghost" in reason
    assert "fail-closed" in reason


def test_unresolved_reason_names_the_missing_facade_target_module() -> None:
    module = _module(_SYNC_STYLE_FACADE_SRC, containing_pkg="pkg")
    reason = unresolved_reason("Foo", "pkg", module)
    assert "pkg.bar" in reason
    assert "fail-closed" in reason


# ---------------------------------------------------------------------------
# Content-tier relocation invariance (NFR-001): module move + sibling reorder
# + blank/comment insertion.
# ---------------------------------------------------------------------------


def test_content_tier_invariant_under_module_move_and_sibling_reorder_and_noise() -> None:
    original_src = '''class Widget:
    """A widget."""

    size: int


class OtherThing:
    pass
'''
    relocated_and_reordered_src = '''class OtherThing:
    pass


# a comment that did not exist before, describing OtherThing
class Widget:
    """A widget."""


    size: int
'''
    original = _module(original_src, containing_pkg="pkg.old_home")
    relocated = _module(relocated_and_reordered_src, containing_pkg="pkg.new_home")

    key_before = resolve_symbol_key("Widget", "pkg.old_home", original)
    key_after = resolve_symbol_key("Widget", "pkg.new_home", relocated)

    assert key_before is not None
    assert key_after is not None
    # Content tier carries no location -- module move + reorder are invisible.
    assert key_before == key_after
    assert key_before.module_path is None


# ---------------------------------------------------------------------------
# DoD-j — 3.11<->3.12 code_tokens_by_line parity, exercised through the NEW
# (AnnAssign / single-alias) branches this module adds -- the spike proved
# this substrate property only for ClassDef/FunctionDef.
# ---------------------------------------------------------------------------

_FSTRING_ANN_ASSIGN_SRC = """GREETING: str = f"hello {name}"
"""


def test_dod_j_ann_assign_fstring_interpolation_stripped_both_interpreters() -> None:
    """code_tokens_by_line drops f-string interpolation content uniformly on
    3.11 (single STRING token) and 3.12+ (PEP 701 FSTRING_* tokens) -- this
    proves the AnnAssign branch inherits that interpreter-independence
    property (the spike never exercised AnnAssign at all)."""
    tokens = code_tokens_by_line(_FSTRING_ANN_ASSIGN_SRC)
    line = tokens[1]
    assert "name" not in line  # the interpolated identifier never leaks
    assert "hello" not in line  # nor the literal text either


def test_dod_j_ann_assign_hash_unaffected_by_fstring_interpolation_change() -> None:
    reinterpolated = _FSTRING_ANN_ASSIGN_SRC.replace('f"hello {name}"', 'f"a totally different greeting {other_var}"')
    assert reinterpolated != _FSTRING_ANN_ASSIGN_SRC  # sanity: a real textual change
    tree_a, tree_b = ast.parse(_FSTRING_ANN_ASSIGN_SRC), ast.parse(reinterpolated)
    span_a = definition_span(tree_a, "GREETING")
    span_b = definition_span(tree_b, "GREETING")
    assert span_a is not None
    assert span_b is not None
    assert body_hash(_FSTRING_ANN_ASSIGN_SRC, span_a) == body_hash(reinterpolated, span_b)


def test_dod_j_single_alias_hash_unaffected_by_unrelated_fstring_sibling() -> None:
    """The single-alias hash substrate reuses the same code_tokens_by_line
    primitive -- proving the interpreter-independence guarantee also holds
    for the T004 branch, not just AnnAssign/ClassDef."""
    src = 'from foo.bar import Alpha as A\nGREETING = f"hi {name}"\n'
    tree = ast.parse(src)
    alias = _find_alias(tree, "A")
    original_hash = alias_body_hash(src, alias)

    mutated = src.replace('f"hi {name}"', 'f"a wildly different message {other}"')
    mutated_tree = ast.parse(mutated)
    mutated_alias = _find_alias(mutated_tree, "A")
    assert alias_body_hash(mutated, mutated_alias) == original_hash


# ---------------------------------------------------------------------------
# T007 — perf-budget assertion
# ---------------------------------------------------------------------------


def _synthetic_corpus(module_count: int) -> dict[str, CorpusModule]:
    corpus: dict[str, CorpusModule] = {}
    for i in range(module_count):
        src = f'class Thing{i}:\n    """Doc {i}."""\n\n    field: int\n\nCONST_{i}: int = {i}\n\n__all__ = [\'Thing{i}\', \'CONST_{i}\']\n'
        module_path = f"pkg.synthetic_{i}"
        corpus[module_path] = _module(src, containing_pkg=module_path)
    return corpus


def test_classify_collisions_perf_budget() -> None:
    """The body-hash introduces a net-new tokenize pass per __all__ symbol
    (the gate today makes ZERO tokenize calls). This is a generous budget,
    not a tight benchmark -- it exists to catch a gross regression (e.g. an
    accidental O(n^2) re-walk), not to pin exact timing (which would flake
    across CI hardware)."""
    corpus = _synthetic_corpus(200)
    index, elapsed = timed_classify_collisions(corpus)
    assert len(index) == 400  # 200 modules * 2 symbols each
    budget = perf_budget_seconds(len(corpus) * 2)
    assert elapsed < budget, f"classify_collisions took {elapsed:.3f}s, budget was {budget:.3f}s"


# ---------------------------------------------------------------------------
# Location dataclass sanity
# ---------------------------------------------------------------------------


def test_location_is_a_plain_frozen_record() -> None:
    loc = Location(module_path="pkg.mod", bare_name="Foo", body_hash="deadbeef")
    assert loc.module_path == "pkg.mod"
    assert loc.bare_name == "Foo"
    assert loc.body_hash == "deadbeef"


# ---------------------------------------------------------------------------
# G1-G6 -- source_module non-goal guards (#3552 WP01).
# Pins the field's provenance-only, non-hashing contract so a later edit
# cannot silently violate it. See contracts/non-goal-invariants.md.
# ---------------------------------------------------------------------------


def test_source_module_is_non_comparing() -> None:
    """G6 (keystone): the field is declared compare=False. Fails the instant
    someone flips it to comparing -- closing critical risk R1, under which a
    provenance-bearing allowlist entry would stop matching its resolver-minted
    key (final_key in allowlist would false-red for every such entry)."""
    fields_by_name = {f.name: f for f in dataclasses.fields(SymbolKey)}
    assert fields_by_name["source_module"].compare is False


def test_source_module_ignored_by_equality_content_tier() -> None:
    """G1: two content-tier keys equal in (bare_name, body_hash) but differing
    in source_module (None vs set) compare equal."""
    resolver_key = SymbolKey(bare_name="ArtifactKind", body_hash="deadbeef")
    allowlist_key = SymbolKey(bare_name="ArtifactKind", body_hash="deadbeef", source_module="charter.offering.artifact_kinds")
    assert resolver_key == allowlist_key


def test_source_module_ignored_by_equality_collision_tier() -> None:
    """G1, escalated tier: an equal (bare_name, module_path, body_hash) triple
    still compares equal regardless of source_module."""
    resolver_key = SymbolKey(bare_name="ArtifactKind", body_hash="deadbeef", module_path="charter.offering.directives")
    allowlist_key = SymbolKey(
        bare_name="ArtifactKind",
        body_hash="deadbeef",
        module_path="charter.offering.directives",
        source_module="charter.offering.artifact_kinds",
    )
    assert resolver_key == allowlist_key


def test_source_module_ignored_by_hash_and_frozenset_membership() -> None:
    """G2: the same two keys hash-equal and are mutual frozenset members --
    this is exactly the `final_key in allowlist` exemption shape (R1): a
    resolver-minted key carrying NO provenance must still be found `in` an
    allowlist frozenset whose entry carries a non-None source_module."""
    resolver_key = SymbolKey(bare_name="ArtifactKind", body_hash="deadbeef")
    allowlist_entry = SymbolKey(bare_name="ArtifactKind", body_hash="deadbeef", source_module="charter.offering.artifact_kinds")
    assert hash(resolver_key) == hash(allowlist_entry)
    allowlist = frozenset({allowlist_entry})
    assert resolver_key in allowlist
    assert allowlist_entry in frozenset({resolver_key})


def test_source_module_does_not_escalate_content_tier() -> None:
    """G3: a content-tier key with source_module set is still is_content_tier;
    key_tier(...) returns it unescalated -- no module_path minted from
    provenance (D-1 relocation-tolerance preserved). Realistic corpus input:
    a single non-colliding __all__ entry, resolved the same way the live
    classifier resolves any real symbol."""
    src = "class Solo:\n    x: int\n__all__ = ['Solo']\n"
    module = _module(src, containing_pkg="pkg.solo")
    corpus = {"pkg.solo": module}
    index = classify_collisions(corpus)
    resolved = resolve_symbol_key("Solo", "pkg.solo", module, corpus=corpus)
    assert resolved is not None

    key = SymbolKey(bare_name=resolved.bare_name, body_hash=resolved.body_hash, source_module="pkg.solo")
    assert key.is_content_tier

    tiered = key_tier(key, "pkg.solo", index)
    assert tiered is not None
    assert tiered.is_content_tier
    assert tiered.module_path is None


def test_source_module_excluded_from_as_tuple_content_and_collision_tier() -> None:
    """G4: as_tuple() excludes source_module in both the content-tier 2-tuple
    and the escalated collision-tier 3-tuple -- provenance never enters the
    allow-list-serializable identity shape."""
    content = SymbolKey(bare_name="Foo", body_hash="h", source_module="pkg.mod")
    assert content.as_tuple() == ("Foo", "h")

    collision = SymbolKey(bare_name="Foo", body_hash="h", module_path="m", source_module="pkg.mod")
    assert collision.as_tuple() == ("Foo", "m", "h")


def test_source_module_does_not_affect_body_hash_and_resolver_key_has_none() -> None:
    """G5: body_hash is identical with/without source_module; a resolver-
    minted key for a still-dead symbol has source_module is None. Adding a
    provenance peer for one bare_name must not change any other key's
    body_hash."""
    src = "class Widget:\n    size: int\n"
    module = _module(src, containing_pkg="pkg.widgets")
    resolved = resolve_symbol_key("Widget", "pkg.widgets", module)
    assert resolved is not None
    assert resolved.source_module is None  # resolver never mints provenance

    with_provenance = SymbolKey(bare_name=resolved.bare_name, body_hash=resolved.body_hash, source_module="pkg.widgets")
    assert with_provenance.body_hash == resolved.body_hash

    # A sibling key (different bare_name) is unaffected by this one gaining provenance.
    other_src = "class Gadget:\n    weight: int\n"
    other_module = _module(other_src, containing_pkg="pkg.widgets")
    other_resolved = resolve_symbol_key("Gadget", "pkg.widgets", other_module)
    assert other_resolved is not None
    assert other_resolved.body_hash != with_provenance.body_hash
    assert other_resolved.source_module is None
