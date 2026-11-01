"""Acceptance tests for the standing docsite ledgers (#6927, absorbs #2358, folds #3914).

``site/url-baseline.txt`` lists every route the docsite has published and
``site/moves.yaml`` is the append-only ``from -> to`` moves ledger (ADR
``2026-10-31-1`` D-5). ``scripts/docs/redirect_map.yaml``, which DocFX reads, is
derived from the moves ledger alone. These tests pin that contract:

* the baseline contains every URL of the old 180-URL manifest and every key of
  the derived redirect map (FR-002);
* the committed map is exactly the ledger's derivation (FR-004, NFR-002);
* every file move #3914 found without a redirect now has one (FR-006);
* no redirect key is a published page and every target is published (FR-005);
* every baseline route resolves on the source tree, the PR-time mirror of the
  deploy job's ``coverage`` step (NFR-001).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from scripts.docs.capture_baseline_urls import (
    DEFAULT_DOCFX_JSON,
    DEFAULT_DOCS_DIR,
    SITE_URL,
    derive_urls_from_source,
)
from scripts.docs.moves_ledger import (
    DEFAULT_MOVES_LEDGER,
    DEFAULT_URL_BASELINE,
    LEDGER_KIND,
    Move,
    MovesLedgerError,
    collapse,
    derive_redirect_map,
    load_baseline,
    load_moves,
    route_to_source,
    source_pairs,
    source_to_route,
    validate,
)
from scripts.docs.redirect_stub_generator import (
    DEFAULT_REDIRECT_MAP,
    load_redirect_map,
    render_redirect_map,
)

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_OLD_MANIFEST = _REPO_ROOT / "scripts" / "docs" / "redirect_baseline_urls.json"
# Read here as evidence of #3914 only: no script reads a Mission's occurrence map.
_ISSUE_3914_MAP = _REPO_ROOT / "kitty-specs" / "common-docs-convergence-01KZMTR9" / "occurrence_map.yaml"
_DOCS_PREFIX = "docs/"


def _route(path: str) -> str:
    return path if path.startswith("/") else f"/{path}"


def _baseline() -> set[str]:
    return set(load_baseline(DEFAULT_URL_BASELINE))


def _committed_map() -> dict[str, str]:
    return load_redirect_map(DEFAULT_REDIRECT_MAP)


def _published_routes() -> set[str]:
    """Routes the docs tree publishes (derive-from-source, ``.html`` pages only)."""
    urls = derive_urls_from_source(DEFAULT_DOCS_DIR, DEFAULT_DOCFX_JSON)
    routes = {_route(u[len(SITE_URL) :]) for u in urls if u.endswith(".html")}
    return {r for r in routes if not r.startswith("/kitty-specs/")}


# --- Committed ledgers -------------------------------------------------------


def test_baseline_contains_old_manifest() -> None:
    data = json.loads(_OLD_MANIFEST.read_text(encoding="utf-8"))
    site_url = str(data["site_url"])
    old = {_route(str(u)[len(site_url) :]) for u in data["urls"]}
    assert len(old) >= 150  # non-vacuous: the 180-URL manifest
    missing = sorted(old - _baseline())
    assert missing == [], f"old manifest URLs missing from the baseline: {missing[:10]}"


def test_baseline_contains_every_redirect_key() -> None:
    keys = {_route(k) for k in _committed_map()}
    assert len(keys) >= 163  # non-vacuous: the redirect map before this Mission
    missing = sorted(keys - _baseline())
    assert missing == [], f"redirect keys missing from the baseline: {missing[:10]}"


def test_committed_map_is_the_ledger_derivation() -> None:
    derived = derive_redirect_map(load_moves(DEFAULT_MOVES_LEDGER))
    assert derived == _committed_map(), "redirect_map.yaml is stale: run regenerate-map"
    rendered = render_redirect_map(derived)
    assert rendered == render_redirect_map(derived)  # deterministic (NFR-002)
    assert rendered == DEFAULT_REDIRECT_MAP.read_text(encoding="utf-8")


def test_issue_3914_forward_reconcile_clean() -> None:
    raw = yaml.safe_load(_ISSUE_3914_MAP.read_text(encoding="utf-8"))
    keys = set(_committed_map())
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
            if route.lstrip("/") not in keys:
                missing.append(route)
    assert examined >= 124  # non-vacuous: #3914's population
    assert missing == [], f"{len(missing)} file moves without a redirect: {missing[:10]}"


def test_no_redirect_key_is_a_published_page() -> None:
    published = _published_routes()
    live_keys = sorted(_route(k) for k in _committed_map() if _route(k) in published)
    assert live_keys == [], f"a stub would overwrite these live pages: {live_keys}"


def test_every_redirect_target_is_published() -> None:
    published = _published_routes()
    dead = sorted(f"{k} -> {v}" for k, v in _committed_map().items() if _route(v) not in published)
    assert dead == [], f"redirect targets that are not published: {dead[:10]}"


def test_every_baseline_route_is_published_or_redirected() -> None:
    published = _published_routes()
    assert len(published) >= 500  # non-vacuous: about 670 pages today
    redirect = {_route(k): _route(v) for k, v in _committed_map().items()}
    broken = sorted(r for r in _baseline() if r not in published and redirect.get(r) not in published)
    assert broken == [], f"baseline routes that would break: {broken[:10]}"


def test_ledger_header_records_manifest_amendments() -> None:
    header = DEFAULT_MOVES_LEDGER.read_text(encoding="utf-8")
    data = json.loads(_OLD_MANIFEST.read_text(encoding="utf-8"))
    for amendment in data["amendments"]:
        assert str(amendment["date"]) in header
        assert str(amendment["pr"]) in header
    assert f"kind: {LEDGER_KIND}" in header


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
    assert derive_redirect_map(load_moves(ledger)) == {"a.html": "c.html", "b.html": "c.html"}


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


def test_validate_reports_a_live_source_and_a_dead_target() -> None:
    mapping = {"live.html": "target.html", "gone.html": "missing.html"}
    published = {"/live.html", "/target.html"}
    problems = validate(mapping, published)
    assert any("live.html" in p and "published page" in p for p in problems)
    assert any("missing.html" in p and "not published" in p for p in problems)
    # Positive control: a well-formed mapping on the same published set is clean.
    assert validate({"old.html": "target.html"}, published) == []


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
