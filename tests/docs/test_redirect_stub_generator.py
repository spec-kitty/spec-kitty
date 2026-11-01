"""Tests for the redirect-stub generator + coverage gate (FR-006, NFR-002).

Covers the three contract guarantees from ``contracts/redirect-stub.md``:

* **derivation** — the redirect map is derived from the standing moves ledger
  ``site/moves.yaml`` and matches the committed ``redirect_map.yaml`` (diff-stable);
* **emit + no-404** — ``generate`` writes ``<meta refresh>`` stubs at the old paths
  and refuses to emit a stub whose target is a 404;
* **coverage goes RED on a gap** — a baseline URL with neither a live page nor a
  live-target stub appears in ``uncovered`` (the NFR-002 gate has teeth), and the
  check is non-vacuous against an empty baseline.

Fixtures use realistic published-URL shapes (``3x/index.html``,
``context/charter-overview.html``, ``tutorials/getting-started.html``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from scripts.docs.moves_ledger import (
    DEFAULT_MOVES_LEDGER,
    Move,
    derive_redirect_map,
    load_moves,
)
from scripts.docs.redirect_stub_generator import (
    DEFAULT_BASELINE,
    DEFAULT_REDIRECT_MAP,
    SITE_URL,
    assert_non_vacuous,
    baseline_drift,
    check_coverage,
    generate,
    load_baseline,
    load_redirect_map,
    main,
    render_redirect_map,
)

# Pure generator unit tests (no git/subprocess) — fast developer-loop shard.
pytestmark = pytest.mark.fast

# The move that distilled the ``docs/3x`` charter shadow tree into ``docs/context``,
# in ledger form: one entry per published route.
_MOVE_3X = Move("/3x/charter-overview.html", "/context/charter-overview.html", "#test")

_OLD_MANIFEST = Path(__file__).resolve().parents[2] / "scripts" / "docs" / "redirect_baseline_urls.json"

# Realistic published-URL paths.
_DIRECT_URL = "tutorials/getting-started.html"
_MOVED_URL = "3x/charter-overview.html"
_MOVED_TARGET = "context/charter-overview.html"


def _make_site(tmp_path: Path, pages: list[str]) -> Path:
    """Stage a minimal ``_site`` containing ``pages`` (site-relative paths)."""
    site = tmp_path / "_site"
    for rel in pages:
        page = site / rel
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(f"<html><body>{rel}</body></html>", encoding="utf-8")
    return site


# --- derivation -------------------------------------------------------------


def test_derive_maps_a_ledger_move_to_the_new_url() -> None:
    mapping = derive_redirect_map([_MOVE_3X])
    assert mapping == {_MOVED_URL: _MOVED_TARGET}
    # A page that did not move has no redirect (it resolves directly).
    assert _DIRECT_URL not in mapping


def test_derive_supports_a_same_directory_rename() -> None:
    rename = Move("/guides/your-first-feature.html", "/guides/your-first-mission.html", "#test")
    assert derive_redirect_map([rename]) == {
        "guides/your-first-feature.html": "guides/your-first-mission.html"
    }


def test_committed_redirect_map_is_diff_stable() -> None:
    """Re-deriving from the committed moves ledger reproduces the committed map."""
    derived = derive_redirect_map(load_moves(DEFAULT_MOVES_LEDGER))
    committed = load_redirect_map(DEFAULT_REDIRECT_MAP)
    assert derived == committed
    # And the rendered form round-trips (the on-disk YAML body is canonical).
    rendered = render_redirect_map(derived)
    assert yaml.safe_load(rendered) == committed


# The shadow-tree redirects WP10 must preserve (FR-008): the ``docs/<v>x`` trees.
# These are the *teeth* of this gate — every one must be present and correct in
# the committed map. The committed map is a strict superset (WP08/WP18 added the
# Divio re-section redirects, e.g. ``explanation/* -> architecture/*``); the
# exact, diff-stable identity of the full map is pinned separately by
# ``test_committed_redirect_map_is_diff_stable``.
_SHADOW_TREE_REDIRECTS = {
    # docs/1x snapshot -> archive/1x twin, COMPOSED one hop to changelog/1x by the
    # convergence mission's docs/archive -> docs/changelog twice-move (WP12).
    "1x/artifacts-and-commands.html": "changelog/1x/artifacts-and-commands.html",
    "1x/branches-and-workspaces.html": "changelog/1x/branches-and-workspaces.html",
    "1x/index.html": "changelog/1x/index.html",
    "1x/orchestration-and-api.html": "changelog/1x/orchestration-and-api.html",
    "1x/workflow.html": "changelog/1x/workflow.html",
    # docs/2x snapshot -> archive/2x twin, COMPOSED one hop to changelog/2x (WP12).
    "2x/adr-coverage.html": "changelog/2x/adr-coverage.html",
    "2x/doctrine-and-charter.html": "changelog/2x/doctrine-and-charter.html",
    "2x/glossary-system.html": "changelog/2x/glossary-system.html",
    "2x/index.html": "changelog/2x/index.html",
    "2x/model-discipline-routing.html": "changelog/2x/model-discipline-routing.html",
    "2x/model-to-task_type.html": "changelog/2x/model-to-task_type.html",
    "2x/orchestration-and-api.html": "changelog/2x/orchestration-and-api.html",
    "2x/runtime-and-missions.html": "changelog/2x/runtime-and-missions.html",
    # docs/context live charter content -> distilled into context/
    "3x/charter-overview.html": "context/charter-overview.html",
    "3x/governance-files.html": "context/governance-files.html",
    "3x/index.html": "context/index.html",
}


def test_committed_map_covers_the_shadow_tree_redirects() -> None:
    """The committed map covers every deleted/moved shadow-tree URL (FR-008).

    WP10 resolves the three ``docs/<v>x`` shadow trees: ``docs/1x`` + ``docs/2x``
    (true HTML snapshots) are DELETED and each baseline URL redirects to its
    pre-existing canonical archive twin (``archive/<v>x/*``); ``docs/context`` (live
    charter content) is distilled + moved into ``context/`` and redirected there.
    The committed map grew to a full-coverage map (WP18 re-section redirects
    folded in), so this gate asserts the shadow-tree redirects are a **subset**
    — drop or corrupt any one and it reds — while the full map's exact identity
    is pinned by ``test_committed_redirect_map_is_diff_stable``.
    """
    committed = load_redirect_map(DEFAULT_REDIRECT_MAP)
    missing = {
        old: new
        for old, new in _SHADOW_TREE_REDIRECTS.items()
        if committed.get(old) != new
    }
    assert missing == {}, f"shadow-tree redirects missing/wrong in committed map: {missing}"


# --- emit + no-404 ----------------------------------------------------------


def test_generate_emits_meta_refresh_stub_at_old_path(tmp_path: Path) -> None:
    site = _make_site(tmp_path, [_DIRECT_URL, _MOVED_TARGET])
    result = generate({_MOVED_URL: _MOVED_TARGET}, site)

    stub = site / _MOVED_URL
    assert stub.is_file()
    assert [p.name for p in result.emitted] == [stub.name]
    assert not result.dead_targets

    html = stub.read_text(encoding="utf-8")
    target = f"{SITE_URL}{_MOVED_TARGET}"
    assert f'http-equiv="refresh" content="0; url={target}"' in html
    assert f'<link rel="canonical" href="{target}">' in html


def test_generate_flags_dead_target_and_writes_no_stub(tmp_path: Path) -> None:
    # Target page is absent -> the stub would be a dead link (404).
    site = _make_site(tmp_path, [_DIRECT_URL])
    result = generate({_MOVED_URL: "context/missing.html"}, site)

    assert result.emitted == []
    assert result.dead_targets == [(_MOVED_URL, "context/missing.html")]
    # No 404-pointing stub was written.
    assert not (site / _MOVED_URL).exists()


# --- coverage (RED on a gap) ------------------------------------------------


def test_coverage_green_after_generate(tmp_path: Path) -> None:
    site = _make_site(tmp_path, [_DIRECT_URL, _MOVED_TARGET])
    redirect_map = {_MOVED_URL: _MOVED_TARGET}
    generate(redirect_map, site)
    uncovered = check_coverage([_DIRECT_URL, _MOVED_URL], redirect_map, site)
    assert uncovered == []


def test_coverage_red_when_redirect_removed(tmp_path: Path) -> None:
    """Drop the redirect for a moved page -> its baseline URL goes uncovered."""
    site = _make_site(tmp_path, [_DIRECT_URL, _MOVED_TARGET])
    # Old page is gone (moved) and there is no redirect entry for it.
    uncovered = check_coverage([_DIRECT_URL, _MOVED_URL], redirect_map={}, site_dir=site)
    assert uncovered == [_MOVED_URL]


def test_coverage_red_when_stub_points_at_dead_target(tmp_path: Path) -> None:
    # Map exists but target is a 404 -> not covered (stub would be a dead link).
    site = _make_site(tmp_path, [_DIRECT_URL])
    redirect_map = {_MOVED_URL: "context/missing.html"}
    generate(redirect_map, site)  # writes nothing (dead target)
    uncovered = check_coverage([_DIRECT_URL, _MOVED_URL], redirect_map, site)
    assert uncovered == [_MOVED_URL]


def test_assert_non_vacuous_rejects_empty_baseline() -> None:
    with pytest.raises(ValueError, match="empty"):
        assert_non_vacuous([])
    # A populated baseline passes silently.
    assert_non_vacuous([_DIRECT_URL])


def test_real_baseline_is_non_empty_and_normalised() -> None:
    site_url, baseline = load_baseline(DEFAULT_BASELINE)
    assert DEFAULT_BASELINE.name == "url-baseline.txt"  # the standing ledger
    assert site_url == SITE_URL
    assert len(baseline) >= 900  # non-vacuous: about 970 routes when seeded
    assert all(not p.startswith(("http", "/")) for p in baseline)


def test_old_json_manifest_still_loads() -> None:
    site_url, baseline = load_baseline(_OLD_MANIFEST)
    raw = json.loads(_OLD_MANIFEST.read_text(encoding="utf-8"))
    assert site_url == raw["site_url"]
    assert len(baseline) == raw["url_count"]


def test_load_baseline_reads_the_text_ledger(tmp_path: Path) -> None:
    ledger = tmp_path / "url-baseline.txt"
    ledger.write_text("# header\n/index.html\n/guides/a.html\n", encoding="utf-8")
    assert load_baseline(ledger) == (SITE_URL, ["guides/a.html", "index.html"])


def test_load_baseline_rejects_non_html_entries(tmp_path: Path) -> None:
    """The baseline universe is redirect-protectable (``.html``) only.

    A ``<meta refresh>`` stub is an HTML mechanism — a verbatim resource URL
    (e.g. a resource-block ``*.md`` copied as-is) cannot be redirect-protected,
    so a non-``.html`` entry in the committed baseline is a capture/amendment
    defect that must fail loud, not silently skew the NFR-002 denominator.
    """
    manifest = tmp_path / "baseline.json"
    manifest.write_text(
        json.dumps(
            {
                "site_url": SITE_URL,
                "urls": [
                    f"{SITE_URL}index.html",
                    f"{SITE_URL}assets/index.md",
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"assets/index\.md"):
        load_baseline(manifest)


def test_load_baseline_tolerates_amendments_key(tmp_path: Path) -> None:
    """The ``amendments`` provenance list is additive-safe for all consumers."""
    manifest = tmp_path / "baseline.json"
    manifest.write_text(
        json.dumps(
            {
                "site_url": SITE_URL,
                "urls": [f"{SITE_URL}index.html"],
                "amendments": [{"date": "2026-07-04", "pr": "#2350"}],
            }
        ),
        encoding="utf-8",
    )
    site_url, baseline = load_baseline(manifest)
    assert site_url == SITE_URL
    assert baseline == ["index.html"]


def test_real_baseline_amendments_are_recorded() -> None:
    """Every post-WP03 entry-level amendment carries its provenance record."""
    raw = json.loads(_OLD_MANIFEST.read_text(encoding="utf-8"))
    amendments = raw["amendments"]
    assert isinstance(amendments, list) and amendments
    for record in amendments:
        assert record["date"]
        assert record["pr"]
        assert record["ruling"]
        assert record["removed"] or record["added"]


# --- baseline drift (grow-on-publish report) ---------------------------------


def test_baseline_drift_lists_unlisted_pages_only(tmp_path: Path) -> None:
    site = _make_site(
        tmp_path,
        [_DIRECT_URL, "guides/new-page.html", "toc.html", "kitty-specs/m/index.html"],
    )
    assert baseline_drift([_DIRECT_URL], site) == ["guides/new-page.html"]
    # Positive control: once listed, nothing is reported.
    assert baseline_drift([_DIRECT_URL, "guides/new-page.html"], site) == []


def test_baseline_drift_command_warns_but_never_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    site = _make_site(tmp_path, [_DIRECT_URL, "guides/new-page.html"])
    baseline = tmp_path / "url-baseline.txt"
    baseline.write_text(f"/{_DIRECT_URL}\n", encoding="utf-8")
    code = main(["baseline-drift", "--baseline", str(baseline), "--site-dir", str(site)])
    out = capsys.readouterr().out
    assert code == 0
    assert "::warning title=URL baseline::/guides/new-page.html" in out


def test_regenerate_map_refuses_a_dead_target(tmp_path: Path) -> None:
    ledger = tmp_path / "moves.yaml"
    ledger.write_text(
        "kind: docs-moves-ledger\nversion: 1\nmoves:\n"
        "  - {from: /no-such-old.html, to: /no-such-target.html, ref: '#test'}\n",
        encoding="utf-8",
    )
    out_map = tmp_path / "redirect_map.yaml"
    code = main(["regenerate-map", "--moves", str(ledger), "--redirect-map", str(out_map)])
    assert code == 1
    assert not out_map.exists()
