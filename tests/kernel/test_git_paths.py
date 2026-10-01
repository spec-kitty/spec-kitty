"""Fast unit tests for :class:`kernel.git.paths.GitPath` (component-wise relations)."""

from __future__ import annotations

import pytest

from kernel.git.paths import GitPath

pytestmark = pytest.mark.fast

P = GitPath.parse


@pytest.mark.parametrize(
    ("text", "parts"),
    [
        ("src/store", ("src", "store")),
        ("src/store/", ("src", "store")),
        ("a b/é/p -> q", ("a b", "é", "p -> q")),
        ("", ()),
    ],
)
def test_parse(text: str, parts: tuple[str, ...]) -> None:
    assert P(text).parts == parts


@pytest.mark.parametrize("text", ["/abs/path", "a//b", "a/./b", "a/../b", "..", "./a"])
def test_parse_rejects_non_normalized(text: str) -> None:
    with pytest.raises(ValueError, match="path"):
        P(text)


@pytest.mark.parametrize("text", ["src/store", "a b/c", "é", "x/y/z"])
def test_round_trip(text: str) -> None:
    assert P(str(P(text))) == P(text)
    assert P(text).as_posix() == text


def test_name() -> None:
    assert P("src/store/local.txt").name == "local.txt"
    assert P("").name == ""


def test_ancestry_is_component_wise() -> None:
    store = P("src/store")
    assert store.is_ancestor_of(P("src/store/local.txt"))
    assert store.is_ancestor_of(P("src/store/a/b"))
    assert not store.is_ancestor_of(store)
    assert not store.is_ancestor_of(P("src/storehouse/x"))
    assert not store.is_ancestor_of(P("src"))


def test_contains() -> None:
    store = P("src/store")
    assert store.contains(store)
    assert store.contains(P("src/store/local.txt"))
    assert not store.contains(P("src/storehouse"))


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        ("src/store/local.txt", "src/store", True),  # #5400: directory replaced by a file
        ("src/store", "src/store/local.txt", True),  # local dir vs incoming leaf
        ("src/store/local.txt", "src/store/local.txt", True),  # exact leaf
        ("src/store", "src/storehouse", False),
        ("src/storehouse/x", "src/store", False),
        ("src/a", "src/b", False),
    ],
)
def test_overlaps(left: str, right: str, expected: bool) -> None:
    assert P(left).overlaps(P(right)) is expected
    assert P(right).overlaps(P(left)) is expected


def test_root_relates_to_nothing() -> None:
    root = P("")
    assert not root.overlaps(P("src"))
    assert not P("src").overlaps(root)
    assert not root.contains(root)
    assert not root.is_ancestor_of(P("src"))


def test_ordering_and_hashing() -> None:
    assert sorted([P("b"), P("a/c"), P("a")]) == [P("a"), P("a/c"), P("b")]
    assert len({P("a/b"), P("a/b/")}) == 1
