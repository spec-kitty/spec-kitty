"""Unit tests for the content-identity matching authority (``_content_identity``)."""

from __future__ import annotations

import ast
from collections import Counter

import pytest

from tests.architectural._content_identity import (
    parse_descriptor_line,
    partition_findings,
    render_descriptor_line,
    resolve_allowlist,
    with_blank_line_at_top,
    with_probe_above_statement,
)
from tests.architectural._ratchet_keys import CompositeKey, ContentDescriptor, composite_key

pytestmark = [pytest.mark.architectural]

_A = "src/a.py"
_B = "src/b.py"
_WHY = "test rationale"

_TWO_JOINS = "def scan(root):\n    x = root / 'built-in'\n    y = root / 'built-in'\n    return x, y\n"


# ---------------------------------------------------------------------------
# partition_findings
# ---------------------------------------------------------------------------


def test_partition_is_a_multiset() -> None:
    key: CompositeKey = (_A, "scan", "x = root /")
    unexpected, unused = partition_findings([(key, 1), (key, 2)], Counter({key: 1}))
    assert unexpected == [2]
    assert unused == Counter()


def test_partition_keys_never_cross_files() -> None:
    in_a: CompositeKey = (_A, "scan", "x = root /")
    in_b: CompositeKey = (_B, "scan", "x = root /")
    unexpected, unused = partition_findings([(in_b, "b:2")], Counter({in_a: 1}))
    assert unexpected == ["b:2"]
    assert unused == Counter({in_a: 1})


def test_partition_reports_unused_and_keeps_finding_order() -> None:
    used: CompositeKey = (_A, "f", "one")
    dead: CompositeKey = (_A, "g", "two")
    findings = [((_A, "h", "three"), 30), (used, 10), ((_A, "i", "four"), 20)]
    unexpected, unused = partition_findings(findings, Counter({used: 1, dead: 1}))
    assert unexpected == [30, 20]
    assert unused == Counter({dead: 1})


def test_partition_is_generic_in_the_key_type() -> None:
    unexpected, unused = partition_findings([("k", "x"), ("k", "y")], Counter({"k": 2}))
    assert unexpected == []
    assert unused == Counter()


def test_partition_does_not_mutate_allowed() -> None:
    allowed: Counter[str] = Counter({"k": 1})
    partition_findings([("k", 1)], allowed)
    assert allowed == Counter({"k": 1})


# ---------------------------------------------------------------------------
# resolve_allowlist
# ---------------------------------------------------------------------------


def test_resolve_allowlist_builds_a_multiset() -> None:
    first = ContentDescriptor(_A, "scan", "x = root /", None, _WHY)
    second = ContentDescriptor(_A, "scan", "y = root /", None, _WHY)
    allowed, errors = resolve_allowlist([first, second], {_A: _TWO_JOINS}.__getitem__)
    assert errors == []
    assert allowed == Counter({(_A, "scan", "x = root /"): 1, (_A, "scan", "y = root /"): 1})


def test_resolve_allowlist_reports_zero_candidates() -> None:
    missing = ContentDescriptor(_A, "scan", "z = root /", None, _WHY)
    allowed, errors = resolve_allowlist([missing], {_A: _TWO_JOINS}.__getitem__)
    assert allowed == Counter()
    assert [descriptor for descriptor, _ in errors] == [missing]
    assert "0 finding" in errors[0][1]


def test_resolve_allowlist_reports_ambiguous_candidates() -> None:
    ambiguous = ContentDescriptor(_A, "scan", "= root /", None, _WHY)
    allowed, errors = resolve_allowlist([ambiguous], {_A: _TWO_JOINS}.__getitem__)
    assert allowed == Counter()
    assert [descriptor for descriptor, _ in errors] == [ambiguous]
    assert "2 finding" in errors[0][1]


def test_resolve_allowlist_occurrence_disambiguates() -> None:
    second = ContentDescriptor(_A, "scan", "= root /", 1, _WHY)
    allowed, errors = resolve_allowlist([second], {_A: _TWO_JOINS}.__getitem__)
    assert errors == []
    assert allowed == Counter({(_A, "scan", "y = root /"): 1})


def test_resolve_allowlist_reports_unavailable_source() -> None:
    orphan = ContentDescriptor(_B, "scan", "x = root /", None, _WHY)
    allowed, errors = resolve_allowlist([orphan], {_A: _TWO_JOINS}.__getitem__)
    assert allowed == Counter()
    assert [descriptor for descriptor, _ in errors] == [orphan]
    assert "source unavailable" in errors[0][1]


# ---------------------------------------------------------------------------
# Drift mutators
# ---------------------------------------------------------------------------


def _line_of(source: str, fragment: str) -> int:
    """1-based number of the one line of *source* containing *fragment* (content anchor)."""
    (lineno,) = [number for number, text in enumerate(source.splitlines(), start=1) if fragment in text]
    return lineno


def test_blank_line_at_top_shifts_by_one_and_keeps_key() -> None:
    fragment = "x = root"
    mutated = with_blank_line_at_top(_TWO_JOINS)
    before, after = _line_of(_TWO_JOINS, fragment), _line_of(mutated, fragment)
    assert after == before + 1
    assert composite_key(mutated, after) == composite_key(_TWO_JOINS, before)


def _assert_probe_keeps_site(source: str, fragment: str) -> list[str]:
    before = _line_of(source, fragment)
    mutated = with_probe_above_statement(source, before)
    ast.parse(mutated)
    after = _line_of(mutated, fragment)
    assert after == before + 2
    assert composite_key(mutated, after) == composite_key(source, before)
    return mutated.splitlines()


def test_probe_inside_multiline_call() -> None:
    source = "def f(root):\n    x = g(\n        root / 'built-in',\n    )\n    return x\n"
    lines = _assert_probe_keeps_site(source, "root / 'built-in'")
    assert lines[1:4] == ["    # drift-probe", "    pass", "    x = g("]


def test_probe_inside_nested_function() -> None:
    source = "def outer():\n    def inner(root):\n        return root / 'built-in'\n    return inner\n"
    lines = _assert_probe_keeps_site(source, "return root")
    assert lines[2:5] == ["        # drift-probe", "        pass", "        return root / 'built-in'"]


def test_probe_on_elif_line_climbs_to_the_enclosing_if() -> None:
    source = "def f(a):\n    if a == 1:\n        return 1\n    elif a == 2:\n        return 2\n    elif a == 3:\n        return 3\n"
    lines = _assert_probe_keeps_site(source, "elif a == 3")
    assert lines[1:4] == ["    # drift-probe", "    pass", "    if a == 1:"]


def test_probe_on_decorator_line_goes_above_the_first_decorator() -> None:
    source = "class C:\n    @staticmethod\n    @other\n    def x():\n        return 1\n"
    lines = _assert_probe_keeps_site(source, "@other")
    assert lines[1:4] == ["    # drift-probe", "    pass", "    @staticmethod"]


def test_probe_on_decorated_def_line_goes_above_the_decorators() -> None:
    source = "@wrap\ndef x():\n    return 1\n"
    lines = _assert_probe_keeps_site(source, "def x")
    assert lines[0:3] == ["# drift-probe", "pass", "@wrap"]


def test_probe_outside_any_statement_raises() -> None:
    source = "# only a comment\nx = 1\n"
    with pytest.raises(ValueError, match="not inside any statement"):
        with_probe_above_statement(source, _line_of(source, "# only"))


# ---------------------------------------------------------------------------
# render / parse
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "descriptor",
    [
        ContentDescriptor(_A, "scan", "x = root /", None, _WHY),
        ContentDescriptor(_A, "Outer.inner", "= root / / /", 0, _WHY),
        ContentDescriptor(_A, "detect", "if sys . platform == :", 2, _WHY),
        ContentDescriptor(_A, "detect", "if sys . platform == :", None, _WHY),
        ContentDescriptor(_A, "detect", ": leading colon", 1, _WHY),
    ],
)
def test_render_parse_round_trip(descriptor: ContentDescriptor) -> None:
    line = render_descriptor_line(descriptor)
    assert parse_descriptor_line(line, _WHY) == descriptor
    assert parse_descriptor_line(line + "\n", _WHY) == descriptor


def test_render_form() -> None:
    assert render_descriptor_line(ContentDescriptor(_A, "f", "tok", None, _WHY)) == f"{_A}::f::tok"
    assert render_descriptor_line(ContentDescriptor(_A, "f", "tok", 3, _WHY)) == f"{_A}::f::tok::3"


def test_render_rejects_double_colon_field() -> None:
    with pytest.raises(ValueError, match="::"):
        render_descriptor_line(ContentDescriptor(_A, "f", "a :: b", None, _WHY))


@pytest.mark.parametrize(
    ("line", "reason"),
    [
        ("src/a.py:12", "3 or 4"),
        ("src/a.py::f", "3 or 4"),
        ("src/a.py::::tok", "empty field"),
        ("src/a.py::f::", "empty field"),
        ("src/a.py::f::tok::", "empty field"),
        ("src/a.py::f::tok::x", "not an integer"),
        ("src/a.py::f::tok::1::2", "3 or 4"),
        ("src/a.py::f::tok::-1", "negative"),
    ],
)
def test_parse_rejections_name_the_line(line: str, reason: str) -> None:
    with pytest.raises(ValueError, match=reason) as excinfo:
        parse_descriptor_line(line, _WHY)
    assert repr(line) in str(excinfo.value)
