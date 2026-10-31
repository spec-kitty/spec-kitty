"""``yaml_documents_equal`` must decide exactly what the pre-change implementation decided.

The writer in :mod:`charter.activation.charter_yaml_io` leans on this comparison twice per
rendered document: once to decide "nothing changed, hand back the original bytes", and once
as the "Cannot preserve YAML aliases or section boundaries" guard. Both are load-bearing, so
the comparison was made cheaper (#6506) without being made *different*: the whole-document
serialise-and-reparse fallback became a structural walk that only round-trips the values that
genuinely differ.

This module freezes the pre-change decision rule as :func:`_event_only_equal` — the exact
``bool(left == right) or _yaml_value_events(left) == _yaml_value_events(right)`` that shipped
— and asserts the current implementation returns the same verdict for every pair in a corpus
that reaches every clause:

* identical copies (the ``==`` short-circuit);
* one changed leaf, one removed key, one permuted mapping (the structural walk);
* explicit tags, anchors and aliases, and non-string keys (the opaque-node fallback, where
  ruamel's constructed values compare by identity rather than by content).

Non-vacuity is asserted per category: a category that exists to be *told apart* from an equal
copy must contain a pair the reference calls unequal, and the equal-only categories must
contain one it calls equal. A corpus that was all one verdict would pass the equivalence
check without proving anything.

Finally, :func:`test_the_new_rule_answers_where_the_old_one_raised` records a pre-existing
defect the corpus exposed: the frozen rule *raised* on some documents rather than answering,
because serialising them and re-parsing the result produced invalid YAML. The leaf-level walk
answers instead.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml.error import YAMLError

from charter.activation.charter_yaml_io import _yaml_loader, _yaml_value_events, yaml_documents_equal

pytestmark = [pytest.mark.unit]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_REPO_CHARTER = _REPO_ROOT / ".kittify" / "charter" / "charter.yaml"
_PACKS = _REPO_ROOT / "packs" / "built-in"

#: Shipped pack documents in the corpus, strided across the sorted list so it reaches several
#: kinds. The cap keeps this a fast unit test: the frozen reference serialises and re-parses
#: each side of every pair, which is linear in document size.
_PACK_DOCUMENT_CAP = 12

#: Above this size a document contributes the two cheap categories only (identical, one
#: changed leaf). The expensive categories are carried by the small documents, where the
#: frozen reference costs microseconds.
_LARGE_DOCUMENT_CHARS = 4096

#: Categories where the pair must differ, so the reference must say *unequal*. Each is the
#: discriminating half of the check.
_DISCRIMINATING = ("leaf", "removed-key", "tagged", "anchored", "non-string-key")

#: Categories where the pair is content-equal, so the reference must say *equal* — the
#: positive control for the ones above.
_EQUAL_ONLY = ("identical", "permuted")

_CATEGORIES = _EQUAL_ONLY + _DISCRIMINATING


@dataclass(frozen=True)
class _Pair:
    """One comparison case, with the frozen rule's verdict already computed once."""

    category: str
    label: str
    left: Any
    right: Any
    expected: bool | None  # None when the frozen rule raised instead of deciding


def _event_only_equal(left: Any, right: Any) -> bool:
    """The decision rule this module froze, verbatim from the pre-#6506 implementation.

    Kept as its own function on purpose: it is the specification the cheaper implementation
    is measured against, not a restatement of it.
    """
    return bool(left == right) or _yaml_value_events(left) == _yaml_value_events(right)


def _reference_verdict(left: Any, right: Any) -> bool | None:
    """The frozen rule's verdict, or ``None`` when it raised instead of deciding."""
    try:
        return _event_only_equal(left, right)
    except YAMLError:
        return None


def _load(text: str) -> Any:
    return _yaml_loader().load(text)


# --------------------------------------------------------------------------- #
# Corpus construction
# --------------------------------------------------------------------------- #

#: Synthetic documents carrying ruamel's opaque constructed nodes: a tagged scalar (which has
#: no ``__eq__``), an anchor plus an alias of it, and non-string keys.
_SYNTHETIC: dict[str, str] = {
    "tagged": "a: !!str 12\nb: plain\n",
    "tagged-custom": "a: !custom value\nb: plain\n",
    "anchored": "base: &b\n  x: 1\n  y: 2\ncopy: *b\n",
    "non-string-key": "1: one\n2.5: two-and-a-half\n~: nullish\n",
    # A tagged KEY and a float key: both defeat ``==`` on the key list while comparing
    # equal under the event rule (a ``.nan`` key is never equal to itself).
    "tagged-key": "!custom key: user-value\n.nan: nan-key\n",
}

_SYNTHETIC_CATEGORY = {
    "tagged": "tagged",
    "tagged-custom": "tagged",
    "tagged-key": "tagged",
    "anchored": "anchored",
    "non-string-key": "non-string-key",
}


def _document_sources() -> list[tuple[str, str]]:
    """Text sources for the corpus, as ``(label, yaml_text)``, sorted for determinism."""
    if not _REPO_CHARTER.is_file():  # pragma: no cover - an installed sdist has no project charter
        pytest.skip(f"no project charter at {_REPO_CHARTER}")
    sources: list[tuple[str, str]] = [("repo-charter", _REPO_CHARTER.read_text(encoding="utf-8"))]
    if _PACKS.is_dir():
        small = []
        for path in sorted(_PACKS.rglob("*.yaml")):
            try:
                if path.stat().st_size > _LARGE_DOCUMENT_CHARS:
                    continue
                small.append((str(path.relative_to(_PACKS)), path.read_text(encoding="utf-8")))
            except (OSError, UnicodeDecodeError):  # pragma: no cover - unreadable pack file
                continue
        stride = max(1, len(small) // _PACK_DOCUMENT_CAP)
        sources.extend(small[::stride][:_PACK_DOCUMENT_CAP])
    return sources


def _mutate_leaf(document: Any) -> Any | None:
    """A deep copy with one scalar leaf changed, or ``None`` when there is none to change."""
    if not isinstance(document, dict):
        return None
    clone = copy.deepcopy(document)
    for key in clone:
        value = clone[key]
        if isinstance(value, str):
            clone[key] = value + "-changed"
            return clone
        if isinstance(value, list) and value and isinstance(value[0], str):
            value[0] = value[0] + "-changed"
            return clone
        if isinstance(value, dict) and value:
            for inner in value:
                if isinstance(value[inner], str):
                    value[inner] = value[inner] + "-changed"
                    return clone
    return None


def _drop_one_top_level(document: Any) -> Any | None:
    if not isinstance(document, dict) or not document:
        return None
    clone = copy.deepcopy(document)
    clone.pop(next(iter(clone)))
    return clone


def _permute_top_level(document: Any) -> Any | None:
    """The same entries in the reverse top-level order, or ``None`` when order is trivial.

    The result is a plain ``dict``: a reassembled ruamel ``CommentedMap`` keeps the original
    line/column and comment positions of values it did not author, and emitting those produces
    broken YAML. A plain mapping still exercises the ordering question the category is about.
    """
    if not isinstance(document, dict) or len(document) < 2:
        return None
    keys = list(document)
    if not all(isinstance(key, str) for key in keys):
        return None
    permuted: dict[str, Any] = {}
    for key in reversed(keys):
        permuted[key] = copy.deepcopy(document[key])
    return permuted


def _pairs() -> list[_Pair]:
    out: list[_Pair] = []

    def add(category: str, label: str, left: Any, right: Any) -> None:
        out.append(_Pair(category, label, left, right, _reference_verdict(left, right)))

    for label, text in _document_sources():
        document = _load(text)
        add("identical", label, document, copy.deepcopy(document))
        mutated = _mutate_leaf(document)
        if mutated is not None:
            add("leaf", label, document, mutated)
        if len(text) > _LARGE_DOCUMENT_CHARS:
            continue
        pruned = _drop_one_top_level(document)
        if pruned is not None:
            add("removed-key", label, document, pruned)
        permuted = _permute_top_level(document)
        if permuted is not None:
            add("permuted", label, document, permuted)

    for name, text in _SYNTHETIC.items():
        category = _SYNTHETIC_CATEGORY[name]
        left = _load(text)
        # A same-shape copy with one structurally added entry: the opaque node under test is
        # left exactly as it is, so the only difference between the pair is a plain extra key.
        changed = _load(text)
        changed["appended-by-test"] = 1
        add(category, f"{name}/equal", left, _load(text))
        add(category, f"{name}/changed", left, changed)

    return out


@pytest.fixture(scope="module")
def corpus() -> list[_Pair]:
    return _pairs()


# --------------------------------------------------------------------------- #
# The equivalence itself
# --------------------------------------------------------------------------- #


def test_verdicts_match_the_pre_change_rule(corpus: list[_Pair]) -> None:
    mismatches = []
    compared = 0
    for pair in corpus:
        if pair.expected is None:  # the frozen rule raised; covered by its own test below
            continue
        compared += 1
        actual = yaml_documents_equal(pair.left, pair.right)
        if actual is not pair.expected:
            mismatches.append((pair.category, pair.label, pair.expected, actual))
    assert compared >= 30, f"only {compared} pairs had a reference verdict; the corpus is too thin"
    assert mismatches == [], (
        f"yaml_documents_equal diverged from the pre-#6506 decision rule. Each entry is (category, document, reference verdict, actual verdict): {mismatches[:10]}"
    )


def test_corpus_is_not_vacuous(corpus: list[_Pair]) -> None:
    """Every category carries the verdict it exists for, on a same-fixture pair."""
    verdicts: dict[str, set[bool]] = {}
    for pair in corpus:
        if pair.expected is None:
            continue
        verdicts.setdefault(pair.category, set()).add(pair.expected)

    assert set(_CATEGORIES) <= set(verdicts), f"categories never built: {sorted(set(_CATEGORIES) - set(verdicts))}"
    equal_only = sorted(category for category in _EQUAL_ONLY if True not in verdicts[category])
    assert equal_only == [], f"equal-only categories with no equal pair: {equal_only}"
    discriminating = sorted(category for category in _DISCRIMINATING if False not in verdicts[category])
    assert discriminating == [], f"discriminating categories with no unequal pair: {discriminating}"


def test_event_fallback_still_reached_for_opaque_nodes() -> None:
    """The corpus must exercise the fallback, not only the ``==`` short-circuit.

    A tagged scalar compares by identity, so ``==`` is ``False`` while the content is equal.
    If the corpus stopped covering that, the equivalence test would be checking the cheap
    clause only.
    """
    left = _load("a: !!str 12\n")
    right = _load("a: !!str 12\n")
    assert left != right, "a TaggedScalar is expected to compare by identity"
    assert _event_only_equal(left, right)
    assert yaml_documents_equal(left, right)


def test_the_new_rule_answers_where_the_old_one_raised() -> None:
    """A pre-existing round-trip failure is a refusal, not a verdict, and must not survive.

    A comment immediately before a block sequence inside a mapping makes the frozen rule's
    serialise-and-reparse emit ``key: -`` — invalid YAML — so it raised ``ScannerError``
    instead of answering. Comparing leaf by leaf never serialises the surrounding document,
    so it answers ``False`` (the documents differ). Asserted both ways on one fixture so the
    two halves cannot drift apart.
    """
    text = "required_by_step:\n  discovery:\n    # no required artifacts at this step\n    []\n  specify:\n    - artifact_key: input.spec.main\n"
    left = _load(text)
    right = _load(text)
    right["required_by_step"]["specify"].append({"artifact_key": "input.plan.main"})

    with pytest.raises(YAMLError):
        _event_only_equal(left, right)

    assert yaml_documents_equal(left, right) is False


@pytest.mark.parametrize(
    ("left_text", "right_text", "expected"),
    [
        ("a: 1\n", "a: 1\n", True),
        ("a: 1\n", "a: 2\n", False),
        ("a: [1, 2]\n", "a: [1, 2]\n", True),
        ("a: [1, 2]\n", "a: [2, 1]\n", False),
        ("a: 1\nb: 2\n", "b: 2\na: 1\n", True),  # mapping order alone does not decide it
        ("", "a: 1\n", False),
    ],
)
def test_cheap_clause_unchanged(left_text: str, right_text: str, expected: bool) -> None:
    """The ``bool(left == right)`` clause stays first and stays authoritative."""
    assert yaml_documents_equal(_load(left_text), _load(right_text)) is expected
