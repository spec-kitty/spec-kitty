"""Acceptance tests for the standing docsite ledgers (#6927, absorbs #2358, folds #3914).

``site/url-baseline.txt`` lists every route the docsite has published and
``site/moves.yaml`` is the append-only ``from -> to`` moves ledger (ADR
``2026-10-31-1`` D-5). The doc-kitty redirect map (``site/legacy-redirects.json``)
is derived from them by ``scripts/docs/site_redirects.py``, whose own tests pin the
map against the published set. These tests pin the ledgers themselves:

* every moved route is in the baseline (FR-002);
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
    route_to_source,
    source_pairs,
    source_to_route,
)

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
# Read here as evidence of #3914 only: no script reads a Mission's occurrence map.
_ISSUE_3914_MAP = _REPO_ROOT / "kitty-specs" / "common-docs-convergence-01KZMTR9" / "occurrence_map.yaml"
_DOCS_PREFIX = "docs/"


def _baseline() -> set[str]:
    return set(load_baseline(DEFAULT_URL_BASELINE))


def _collapsed() -> dict[str, str]:
    return collapse(load_moves(DEFAULT_MOVES_LEDGER))


# --- Committed ledgers -------------------------------------------------------


def test_baseline_contains_every_moved_route() -> None:
    moved = set(_collapsed())
    assert len(moved) >= 163  # non-vacuous: the redirect map the ledger was seeded from
    missing = sorted(moved - _baseline())
    assert missing == [], f"moved routes missing from the baseline: {missing[:10]}"


def test_issue_3914_forward_reconcile_clean() -> None:
    raw = yaml.safe_load(_ISSUE_3914_MAP.read_text(encoding="utf-8"))
    keys = set(_collapsed())
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
            if route not in keys:
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


def test_collapse_refuses_a_cycle() -> None:
    moves = [Move("/a.html", "/b.html", "#1"), Move("/b.html", "/a.html", "#2")]
    with pytest.raises(MovesLedgerError, match="cycle"):
        collapse(moves)


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
