"""Acceptance tests for the standing docsite ledgers (#6927, absorbs #2358, folds #3914).

``site/url-baseline.txt`` lists every route the docsite has published and
``site/moves.yaml`` is the append-only ``from -> to`` moves ledger (ADR
``2026-10-31-1`` D-5). The doc-kitty redirect map (``site/legacy-redirects.json``)
is derived from them by ``scripts/docs/site_redirects.py``, whose own tests pin the
map against the published set. These tests pin the ledgers themselves:

* every moved route is in the baseline (FR-002), except an index rename, which keeps
  its directory URL;
* every section index renamed to ``README.md`` (#6939) is recorded;
* every file move #3914 found without a redirect now has one (FR-006);
* the reader's unit behaviour: chains, cycles, duplicates, malformed entries.

The legacy redirect map and URL manifest these tests also compared against were
retired with the legacy site build (#6943).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.docs.moves_ledger import (
    DEFAULT_MOVES_LEDGER,
    DEFAULT_URL_BASELINE,
    LEDGER_KIND,
    Move,
    MovesLedgerError,
    collapse,
    load_baseline,
    load_moves,
    is_index_rename,
    returned_routes,
    route_to_source,
    source_pairs,
    source_to_route,
)

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
# Read here as evidence of #3914 only: no script reads a Mission's occurrence map.
_ISSUE_3914_MAP = _REPO_ROOT / "kitty-specs" / "common-docs-convergence-01KZMTR9" / "occurrence_map.yaml"
_DOCS_PREFIX = "docs/"
_RENAME_REF = "#6939"


def _baseline() -> set[str]:
    return set(load_baseline(DEFAULT_URL_BASELINE))


def _collapsed() -> dict[str, str]:
    return collapse(load_moves(DEFAULT_MOVES_LEDGER))


# --- Committed ledgers -------------------------------------------------------


def test_baseline_contains_every_moved_route() -> None:
    collapsed = _collapsed()
    assert len(collapsed) >= 163  # non-vacuous: the redirect map the ledger was seeded from
    # An index rename (``/x/index.html -> /x/README.html``) keeps the directory URL ``/x/``,
    # whose built file the page itself serves, so it creates no URL to protect.
    moved = {route for route, target in collapsed.items() if not is_index_rename(route, target)}
    missing = sorted(moved - _baseline())
    assert missing == [], f"moved routes missing from the baseline: {missing[:10]}"


def test_every_section_index_rename_is_recorded() -> None:
    """#6939: each ``docs/**/README.md`` that replaced an ``index.md`` is a ledger move."""
    renames = [move for move in load_moves(DEFAULT_MOVES_LEDGER) if move.ref == _RENAME_REF]
    assert len(renames) >= 59  # non-vacuous: the 59 section indexes left after #6943
    for move in renames:
        assert is_index_rename(move.from_route, move.to_route), move
        old, new = route_to_source(move.from_route), route_to_source(move.to_route)
        assert old is not None and new is not None
        assert not (_REPO_ROOT / old).exists(), f"{old} still exists"
        assert (_REPO_ROOT / new).is_file(), f"{new} is missing"
    recorded = {route_to_source(move.to_route) for move in renames}
    readmes = {path.relative_to(_REPO_ROOT).as_posix() for path in (_REPO_ROOT / "docs").rglob("README.md")}
    assert recorded <= readmes


def test_issue_3914_forward_reconcile_clean() -> None:
    raw = yaml.safe_load(_ISSUE_3914_MAP.read_text(encoding="utf-8"))
    keys = set(_collapsed())
    returned = returned_routes(load_moves(DEFAULT_MOVES_LEDGER))
    examined = 0
    missing: list[str] = []
    for entry in raw["moves"]:
        if entry["to"] == "RETIRE":
            continue
        for source in entry["from"]:
            route = source_to_route(source)
            if not source.startswith(_DOCS_PREFIX) or route is None:
                continue
            examined += 1
            # A route the ledger records a later move back into (#6939: README -> index -> README)
            # is a live page again; nothing else excuses a missing redirect.
            if route not in keys and route not in returned:
                missing.append(route)
    assert examined >= 124  # non-vacuous: #3914's population
    assert missing == [], f"{len(missing)} file moves without a redirect: {missing[:10]}"


def test_the_ledger_header_names_its_kind() -> None:
    assert f"kind: {LEDGER_KIND}" in DEFAULT_MOVES_LEDGER.read_text(encoding="utf-8")


# --- moves_ledger unit behaviour ----------------------------------------------


def _write_ledger(tmp_path: Path, moves: list[dict[str, str]], **top: object) -> Path:
    path = tmp_path / "moves.yaml"
    body = {"kind": LEDGER_KIND, "version": 1, "moves": moves, **top}
    path.write_text(yaml.safe_dump(body), encoding="utf-8")
    return path


def test_collapse_follows_chains(tmp_path: Path) -> None:
    ledger = _write_ledger(
        tmp_path,
        [
            {"from": "/a.html", "to": "/b.html", "ref": "#1"},
            {"from": "/b.html", "to": "/c.html", "ref": "#2"},
        ],
    )
    assert collapse(load_moves(ledger)) == {"/a.html": "/c.html", "/b.html": "/c.html"}


def test_collapse_reads_a_return_as_superseding_the_earlier_move_away() -> None:
    """Append-only: a page that moves back is a later entry into the route it left.

    The route is live again, so its earlier move away no longer applies (#6939: eight
    folders moved ``README.md -> index.md`` in #3914 and #6928, then back).
    """
    moves = [
        Move("/x/README.html", "/x/index.html", "#1"),
        Move("/y.html", "/x/index.html", "#2"),
        Move("/x/index.html", "/x/README.html", "#3"),
    ]
    assert collapse(moves) == {"/y.html": "/x/README.html", "/x/index.html": "/x/README.html"}


def test_returned_routes_are_the_routes_a_later_entry_moves_back_into() -> None:
    moves = [
        Move("/x/README.html", "/x/index.html", "#1"),
        Move("/z.html", "/y.html", "#2"),
        Move("/x/index.html", "/x/README.html", "#3"),
        Move("/y.html", "/w.html", "#4"),
    ]
    assert returned_routes(moves) == frozenset({"/x/README.html"})


def test_collapse_keeps_a_move_away_that_no_later_entry_returns_from() -> None:
    """The return rule reads file order: an earlier entry into a route never supersedes a later move away."""
    moves = [Move("/b.html", "/a.html", "#1"), Move("/a.html", "/c.html", "#2")]
    assert collapse(moves) == {"/b.html": "/c.html", "/a.html": "/c.html"}


def test_collapse_refuses_a_route_that_moves_to_itself() -> None:
    with pytest.raises(MovesLedgerError, match="cycle"):
        collapse([Move("/a.html", "/a.html", "#1")])


@pytest.mark.parametrize(
    ("source", "target", "expected"),
    [
        ("/x/index.html", "/x/README.html", True),
        ("/index.html", "/README.html", True),
        ("/x/README.html", "/x/index.html", True),
        ("/x/index.html", "/y/README.html", False),
        ("/x/a.html", "/x/README.html", False),
        ("/x/index.html", "/x/index.html", False),
    ],
)
def test_is_index_rename(source: str, target: str, expected: bool) -> None:
    assert is_index_rename(source, target) is expected


def test_load_refuses_a_duplicate_from(tmp_path: Path) -> None:
    ledger = _write_ledger(
        tmp_path,
        [
            {"from": "/a.html", "to": "/b.html", "ref": "#1"},
            {"from": "/a.html", "to": "/c.html", "ref": "#2"},
        ],
    )
    with pytest.raises(MovesLedgerError, match="duplicate"):
        load_moves(ledger)


@pytest.mark.parametrize(
    "top",
    [{"kind": "something-else"}, {"version": 2}],
)
def test_load_refuses_an_unknown_kind_or_version(tmp_path: Path, top: dict[str, object]) -> None:
    ledger = _write_ledger(tmp_path, [{"from": "/a.html", "to": "/b.html", "ref": "#1"}], **top)
    with pytest.raises(MovesLedgerError):
        load_moves(ledger)


@pytest.mark.parametrize(
    "entry",
    [
        {"from": "a.html", "to": "/b.html", "ref": "#1"},
        {"from": "/a.html", "to": "b.html", "ref": "#1"},
        {"from": "/a.html", "to": "/b.html", "ref": ""},
    ],
)
def test_load_refuses_a_malformed_entry(tmp_path: Path, entry: dict[str, str]) -> None:
    with pytest.raises(MovesLedgerError):
        load_moves(_write_ledger(tmp_path, [entry]))


def test_load_baseline_skips_comments_and_refuses_bare_paths(tmp_path: Path) -> None:
    good = tmp_path / "good.txt"
    good.write_text("# header\n\n/b.html\n/a.html\n/a.html\n", encoding="utf-8")
    assert load_baseline(good) == ["/a.html", "/b.html"]
    bad = tmp_path / "bad.txt"
    bad.write_text("a.html\n", encoding="utf-8")
    with pytest.raises(MovesLedgerError):
        load_baseline(bad)


def test_route_and_source_convert_both_ways() -> None:
    assert route_to_source("/a/b.html") == "docs/a/b.md"
    assert source_to_route("docs/a/b.md") == "/a/b.html"
    assert source_to_route("docs/assets/x.png") is None
    assert source_to_route("src/x.md") is None


def test_source_pairs_are_docs_paths() -> None:
    moves = [Move("/a/old.html", "/b/new.html", "#1"), Move("/c/old.html", "/b/new.html", "#2")]
    assert source_pairs(moves) == [
        ("docs/a/old.md", "docs/b/new.md"),
        ("docs/c/old.md", "docs/b/new.md"),
    ]
