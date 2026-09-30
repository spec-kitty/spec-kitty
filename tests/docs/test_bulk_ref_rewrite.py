"""WP08 — contract tests for the occurrence-map-driven bulk reference rewriter.

Mission B (*Common Docs Structural Move*, ``01KW3SBK``), IC-05b.  These tests
drive the real rewriter (``scripts/docs/bulk_ref_rewrite.py``) against a
synthetic repo so the four load-bearing invariants are pinned to observable
behaviour, not implementation details:

1. a ``moves:`` prefix **is** rewritten (and to the *real* landed destination);
2. a ``kitty-specs/`` reference is **left untouched** (immutable snapshot);
3. a ``do_not_change``-category literal (import path, serialized ``toc.yml``
   href, markdown frontmatter field) is **left untouched**;
4. the run is **idempotent** — a second pass rewrites nothing.

Plus the incremental-safety guard (a move whose ``from`` still exists on disk is
skipped) and the subdir/rename landing-resolution that the coarse map ``to:``
cannot express.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.docs.bulk_ref_rewrite import (
    build_substitutions,
    find_dead_twinned_adr_links,
    load_moves,
    reconcile_adr_era_twins,
    resolve_adr_era_twin,
    resolve_destination,
    run,
    split_frontmatter,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.fast


_OCCURRENCE_MAP = """\
target:
  term: "architecture/"
  replacement: "docs/"
  operation: rename
moves:
  - from: ["architecture/3.x/adr"]
    to: docs/adr/3.x
    reason: "Era ADRs -> docs/adr/3.x (flattened landing)."
  - from: ["architecture/audits"]
    to: docs/architecture
    reason: "Audits -> docs/architecture (subdir preserved on landing)."
  - from: ["glossary/contexts"]
    to: docs/context
    reason: "Glossary -> docs/context (flattened)."
  - from: ["docs/engineering_notes"]
    to: docs/plans
    reason: "Engineering notes -> docs/plans/engineering-notes (renamed)."
  - from: ["architecture/2.x/README.md"]
    to: docs/architecture
    reason: "Per-era README -> README-<era>.md (disambiguated)."
  - from: ["docs/development"]
    to: docs/operations
    reason: "Re-section NOT yet landed in this fixture (from still exists)."
  - from: ["CHANGELOG.md"]
    to: docs/changelog
    kind: relocate-with-alias
    reason: "Root alias persists -> skipped by SKIP_MOVE_FROMS."
"""


def _build_fixture_repo(root: Path) -> Path:
    """Lay out a synthetic post-move tree + the occurrence map; return map path."""

    occ_map = root / "kitty-specs" / "mission" / "occurrence_map.yaml"
    occ_map.parent.mkdir(parents=True, exist_ok=True)
    occ_map.write_text(_OCCURRENCE_MAP, encoding="utf-8")

    # New (landed) homes — `from`-exists guard relies on the OLD dirs being gone.
    for landed in (
        "docs/adr/3.x",
        "docs/architecture/audits",  # subdir preserved
        "docs/context",
        "docs/plans/engineering-notes",  # renamed _ -> -
        "docs/development",  # OLD home still present -> move NOT landed -> skip
    ):
        (root / landed).mkdir(parents=True, exist_ok=True)
    (root / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    (root / "docs/architecture/README-2.x.md").write_text("era readme\n", encoding="utf-8")

    return occ_map


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# --------------------------------------------------------------------------- #
# (1) a moves: prefix IS rewritten — to the real landed destination
# --------------------------------------------------------------------------- #


class TestMovesPrefixRewritten:
    def test_flattened_dir_prefix_rewritten(self, tmp_path: Path) -> None:
        occ = _build_fixture_repo(tmp_path)
        src = tmp_path / "src" / "mod.py"
        _write(src, 'DOC = "architecture/3.x/adr/2026-01-01-1-x.md"\n')
        run(tmp_path, occ, roots=("src",), include_root_md=False)
        assert "docs/adr/3.x/2026-01-01-1-x.md" in src.read_text()
        assert "architecture/3.x/adr" not in src.read_text()

    def test_subdir_preserving_landing_resolved(self, tmp_path: Path) -> None:
        """architecture/audits -> docs/architecture/audits (subdir kept), not flattened."""
        occ = _build_fixture_repo(tmp_path)
        page = tmp_path / "docs" / "guide.md"
        _write(page, "See [audit](architecture/audits/2026-05-x.md).\n")
        run(tmp_path, occ, roots=("docs",), include_root_md=False)
        assert "docs/architecture/audits/2026-05-x.md" in page.read_text()

    def test_relative_parent_reference_rewritten(self, tmp_path: Path) -> None:
        occ = _build_fixture_repo(tmp_path)
        page = tmp_path / "docs" / "sub" / "p.md"
        _write(page, "[x](../../architecture/3.x/adr/y.md)\n")
        run(tmp_path, occ, roots=("docs",), include_root_md=False)
        assert "../../docs/adr/3.x/y.md" in page.read_text()

    def test_renamed_landing_underscore_to_dash(self, tmp_path: Path) -> None:
        occ = _build_fixture_repo(tmp_path)
        page = tmp_path / "docs" / "p.md"
        _write(page, "see docs/engineering_notes/note.md\n")
        run(tmp_path, occ, roots=("docs",), include_root_md=False)
        assert "docs/plans/engineering-notes/note.md" in page.read_text()

    def test_per_era_readme_disambiguation_override(self, tmp_path: Path) -> None:
        occ = _build_fixture_repo(tmp_path)
        page = tmp_path / "docs" / "p.md"
        _write(page, "old root: architecture/2.x/README.md\n")
        run(tmp_path, occ, roots=("docs",), include_root_md=False)
        assert "docs/architecture/README-2.x.md" in page.read_text()


# --------------------------------------------------------------------------- #
# (2) a kitty-specs/ reference is left untouched
# --------------------------------------------------------------------------- #


def test_kitty_specs_reference_untouched(tmp_path: Path) -> None:
    occ = _build_fixture_repo(tmp_path)
    snapshot = tmp_path / "kitty-specs" / "old-mission" / "notes.md"
    body = "Historical: architecture/3.x/adr/2026-01-01-1-x.md\n"
    _write(snapshot, body)
    # kitty-specs is outside the swept roots AND excluded; prove both by sweeping all.
    run(tmp_path, occ, roots=("src", "tests", "docs", "kitty-specs"))
    assert snapshot.read_text() == body


# --------------------------------------------------------------------------- #
# (3) do_not_change-category literals are left untouched
# --------------------------------------------------------------------------- #


class TestDoNotChangeCategoriesUntouched:
    def test_import_path_literal_untouched(self, tmp_path: Path) -> None:
        """Dotted import paths carry no slash doc-path, so are never matched."""
        occ = _build_fixture_repo(tmp_path)
        src = tmp_path / "src" / "m.py"
        body = "from specify_cli.compat.registry import load_registry\n"
        _write(src, body)
        run(tmp_path, occ, roots=("src",), include_root_md=False)
        assert src.read_text() == body

    def test_serialized_toc_href_untouched(self, tmp_path: Path) -> None:
        occ = _build_fixture_repo(tmp_path)
        toc = tmp_path / "docs" / "toc.yml"
        body = "- href: architecture/3.x/adr/x.md\n"
        _write(toc, body)
        run(tmp_path, occ, roots=("docs",), include_root_md=False)
        assert toc.read_text() == body

    def test_markdown_frontmatter_field_untouched(self, tmp_path: Path) -> None:
        occ = _build_fixture_repo(tmp_path)
        page = tmp_path / "docs" / "p.md"
        _write(
            page,
            "---\nrelated: [architecture/3.x/adr/x.md]\n---\nBody link architecture/3.x/adr/x.md here.\n",
        )
        run(tmp_path, occ, roots=("docs",), include_root_md=False)
        text = page.read_text()
        # Frontmatter field preserved (WP12 territory) ...
        assert "related: [architecture/3.x/adr/x.md]" in text
        # ... but the BODY reference is rewritten.
        assert "Body link docs/adr/3.x/x.md here." in text

    def test_inventory_lockfile_untouched(self, tmp_path: Path) -> None:
        occ = _build_fixture_repo(tmp_path)
        lock = tmp_path / "docs" / "development" / "page-inventory.yaml"
        body = "- path: architecture/3.x/adr/x.md\n"
        _write(lock, body)
        run(tmp_path, occ, roots=("docs",), include_root_md=False)
        assert lock.read_text() == body


# --------------------------------------------------------------------------- #
# (4) idempotency
# --------------------------------------------------------------------------- #


def test_rewrite_is_idempotent(tmp_path: Path) -> None:
    occ = _build_fixture_repo(tmp_path)
    page = tmp_path / "docs" / "p.md"
    _write(page, "a architecture/3.x/adr/x.md and architecture/audits/y.md\n")
    first = run(tmp_path, occ, roots=("docs",), include_root_md=False)
    after_first = page.read_text()
    second = run(tmp_path, occ, roots=("docs",), include_root_md=False)
    assert first.total_rewrites >= 2
    assert second.total_rewrites == 0
    assert page.read_text() == after_first


# --------------------------------------------------------------------------- #
# incremental-safety guard + dry-run + unit helpers
# --------------------------------------------------------------------------- #


def test_unlanded_move_is_skipped(tmp_path: Path) -> None:
    """docs/development still exists in the fixture -> its refs are NOT rewritten."""
    occ = _build_fixture_repo(tmp_path)
    page = tmp_path / "docs" / "p.md"
    body = "guide at docs/development/ssh-deploy-keys.md\n"
    _write(page, body)
    run(tmp_path, occ, roots=("docs",), include_root_md=False)
    assert page.read_text() == body


def test_changelog_alias_skipped(tmp_path: Path) -> None:
    occ = _build_fixture_repo(tmp_path)
    subs = build_substitutions(load_moves(occ), tmp_path)
    assert all(s.old != "CHANGELOG.md" for s in subs)


def test_dry_run_does_not_write(tmp_path: Path) -> None:
    occ = _build_fixture_repo(tmp_path)
    page = tmp_path / "docs" / "p.md"
    body = "x architecture/3.x/adr/x.md\n"
    _write(page, body)
    report = run(tmp_path, occ, roots=("docs",), include_root_md=False, dry_run=True)
    assert report.total_rewrites == 1
    assert page.read_text() == body  # unchanged on disk


def test_resolve_destination_variants(tmp_path: Path) -> None:
    (tmp_path / "docs/architecture/audits").mkdir(parents=True)
    (tmp_path / "docs/plans/engineering-notes").mkdir(parents=True)
    # subdir preserved
    assert resolve_destination("architecture/audits", "docs/architecture", tmp_path) == "docs/architecture/audits"
    # flattened (no docs/adr/3.x/adr subdir)
    (tmp_path / "docs/adr/3.x").mkdir(parents=True)
    assert resolve_destination("architecture/3.x/adr", "docs/adr/3.x", tmp_path) == "docs/adr/3.x"
    # underscore -> dash rename
    assert resolve_destination("docs/engineering_notes", "docs/plans", tmp_path) == "docs/plans/engineering-notes"
    # file move, `to` is a directory root -> to/basename
    assert resolve_destination("architecture/2.x/shim-registry.yaml", "docs/migrations", tmp_path) == "docs/migrations/shim-registry.yaml"
    # file move, `to` is the full destination FILE path -> used verbatim
    # (regression: appending the basename doubled it, e.g. …/x.md/x.md)
    assert (
        resolve_destination(
            "docs/archive/architecture/feature-detection.md",
            "docs/plans/engineering-notes/feature-detection.md",
            tmp_path,
        )
        == "docs/plans/engineering-notes/feature-detection.md"
    )


def test_split_frontmatter() -> None:
    fm, body = split_frontmatter("---\na: 1\n---\nbody\n")
    assert fm == "---\na: 1\n---\n"
    assert body == "body\n"
    assert split_frontmatter("no frontmatter\n") == ("", "no frontmatter\n")


# --------------------------------------------------------------------------- #
# ADR era-twin resolution (cycle-2 defect: deduped late-2.x ADRs)
# --------------------------------------------------------------------------- #
#
# WP06 deduped the late-2.x ADRs that existed as symlink twins under BOTH
# architecture/2.x/adr/ and architecture/3.x/adr/ down to a single survivor at
# docs/adr/3.x/<file>.  The mechanical prefix rewrite turns an
# architecture/2.x/adr/<file> reference into a now-dead docs/adr/2.x/<file>.
# These tests pin the era-twin reroute and the on-disk-resolution teeth check.

# A real 2.x ADR that survived under docs/adr/2.x/ (era dir is NOT empty).
_REAL_2X = "2026-03-15-1-vertical-slice.md"
# A deduped late-2.x ADR whose only survivor lives under docs/adr/3.x/.
_DEDUPED = "2026-05-16-1-doctrine-layer-merge-semantics.md"

_ERA_TWIN_MAP = """\
target:
  term: "architecture/"
  replacement: "docs/"
  operation: rename
moves:
  - from: ["architecture/2.x/adr"]
    to: docs/adr/2.x
    reason: "Era ADRs (2.x) -> docs/adr/2.x."
  - from: ["architecture/3.x/adr"]
    to: docs/adr/3.x
    reason: "Era ADRs (3.x) -> docs/adr/3.x (dedup survivor lives here)."
"""


def _build_era_twin_repo(root: Path) -> Path:
    """Post-move tree where the deduped ADR survives only under 3.x."""

    occ = root / "kitty-specs" / "m" / "occurrence_map.yaml"
    occ.parent.mkdir(parents=True, exist_ok=True)
    occ.write_text(_ERA_TWIN_MAP, encoding="utf-8")
    # 3.x holds the dedup survivor; 2.x is a *populated* era dir (real 2.x ADRs).
    _write(root / "docs/adr/3.x" / _DEDUPED, "# survivor\n")
    _write(root / "docs/adr/2.x" / _REAL_2X, "# genuine 2.x adr\n")
    return occ


class TestAdrEraTwinResolution:
    def test_fresh_rewrite_routes_deduped_adr_to_survivor(self, tmp_path: Path) -> None:
        """architecture/2.x/adr/<deduped> -> docs/adr/3.x/<deduped> (not dead 2.x)."""
        occ = _build_era_twin_repo(tmp_path)
        page = tmp_path / "src" / "mod.py"
        _write(page, f'ADR = "architecture/2.x/adr/{_DEDUPED}"\n')
        run(tmp_path, occ, roots=("src",), include_root_md=False)
        text = page.read_text()
        assert f"docs/adr/3.x/{_DEDUPED}" in text
        assert "docs/adr/2.x/" not in text

    def test_already_landed_dead_residual_is_healed(self, tmp_path: Path) -> None:
        """A prior run already wrote the dead docs/adr/2.x/<deduped>; re-run heals it.

        The idempotency lookbehind means the architecture/ prefix no longer
        matches, so the heal must happen on the already-landed token.
        """
        occ = _build_era_twin_repo(tmp_path)
        page = tmp_path / "docs" / "guide.md"
        _write(page, f"See `docs/adr/2.x/{_DEDUPED}` for details.\n")
        report = run(tmp_path, occ, roots=("docs",), include_root_md=False)
        assert report.total_rewrites == 1
        assert f"docs/adr/3.x/{_DEDUPED}" in page.read_text()

    def test_genuine_2x_reference_is_preserved(self, tmp_path: Path) -> None:
        """A 2.x ADR that really survives at docs/adr/2.x/ must NOT be rerouted."""
        occ = _build_era_twin_repo(tmp_path)
        page = tmp_path / "docs" / "guide.md"
        _write(page, f"see architecture/2.x/adr/{_REAL_2X}\n")
        run(tmp_path, occ, roots=("docs",), include_root_md=False)
        text = page.read_text()
        assert f"docs/adr/2.x/{_REAL_2X}" in text
        assert "docs/adr/3.x/" not in text

    def test_no_twin_placeholder_is_left_untouched(self, tmp_path: Path) -> None:
        """A dead docs/adr/2.x/<file> with no surviving twin is out of scope."""
        occ = _build_era_twin_repo(tmp_path)
        page = tmp_path / "docs" / "guide.md"
        body = "template at docs/adr/2.x/YYYY-MM-DD-N-your-decision.md\n"
        _write(page, body)
        run(tmp_path, occ, roots=("docs",), include_root_md=False)
        assert page.read_text() == body

    def test_relative_and_url_embedded_tokens_are_healed(self, tmp_path: Path) -> None:
        """Tool-owned docs/adr tokens inside relative links / blob URLs heal too."""
        occ = _build_era_twin_repo(tmp_path)
        page = tmp_path / "docs" / "sub" / "p.md"
        _write(
            page,
            f"rel [a](../../docs/adr/2.x/{_DEDUPED}) and url https://example.test/blob/main/docs/adr/2.x/{_DEDUPED}\n",
        )
        run(tmp_path, occ, roots=("docs",), include_root_md=False)
        text = page.read_text()
        assert f"../../docs/adr/3.x/{_DEDUPED}" in text
        assert f"blob/main/docs/adr/3.x/{_DEDUPED}" in text
        assert "docs/adr/2.x/" not in text

    def test_idempotent_after_era_twin_heal(self, tmp_path: Path) -> None:
        occ = _build_era_twin_repo(tmp_path)
        page = tmp_path / "docs" / "guide.md"
        _write(page, f"See architecture/2.x/adr/{_DEDUPED}.\n")
        run(tmp_path, occ, roots=("docs",), include_root_md=False)
        healed = page.read_text()
        second = run(tmp_path, occ, roots=("docs",), include_root_md=False)
        assert second.total_rewrites == 0
        assert page.read_text() == healed


def test_resolve_adr_era_twin_unit(tmp_path: Path) -> None:
    _build_era_twin_repo(tmp_path)
    # deduped survivor is at 3.x -> a 2.x ref resolves to the 3.x twin
    assert resolve_adr_era_twin("2.x", _DEDUPED, tmp_path) == "3.x"
    # a ref that already resolves at its own era -> no reroute
    assert resolve_adr_era_twin("2.x", _REAL_2X, tmp_path) is None
    assert resolve_adr_era_twin("3.x", _DEDUPED, tmp_path) is None
    # no twin anywhere -> no reroute
    assert resolve_adr_era_twin("2.x", "9999-99-99-1-ghost.md", tmp_path) is None


def test_reconcile_adr_era_twins_reports_reroutes(tmp_path: Path) -> None:
    _build_era_twin_repo(tmp_path)
    body = f"a docs/adr/2.x/{_DEDUPED} b docs/adr/2.x/{_REAL_2X}\n"
    new_body, reroutes = reconcile_adr_era_twins(body, tmp_path)
    assert reroutes == [(f"docs/adr/2.x/{_DEDUPED}", f"docs/adr/3.x/{_DEDUPED}")]
    assert f"docs/adr/3.x/{_DEDUPED}" in new_body
    # the genuine 2.x ref is untouched
    assert f"docs/adr/2.x/{_REAL_2X}" in new_body


# --------------------------------------------------------------------------- #
# Teeth: on-disk resolution of tool-owned ADR rewrites
# --------------------------------------------------------------------------- #


def test_teeth_flags_dead_twinned_link(tmp_path: Path) -> None:
    """RED teeth: a dead docs/adr/2.x/<deduped> with a 3.x survivor is reported."""
    _build_era_twin_repo(tmp_path)
    _write(tmp_path / "docs" / "guide.md", f"x docs/adr/2.x/{_DEDUPED}\n")
    dead = find_dead_twinned_adr_links(tmp_path, roots=("docs",), include_root_md=False)
    assert dead == [("docs/guide.md", f"docs/adr/2.x/{_DEDUPED}", f"docs/adr/3.x/{_DEDUPED}")]


def test_teeth_clean_after_run_and_ignores_no_twin_placeholders(
    tmp_path: Path,
) -> None:
    """GREEN teeth: after the heal no dead-twinned link remains; placeholders ignored."""
    occ = _build_era_twin_repo(tmp_path)
    _write(
        tmp_path / "docs" / "guide.md",
        f"dead architecture/2.x/adr/{_DEDUPED} real architecture/2.x/adr/{_REAL_2X} ghost docs/adr/2.x/2099-01-01-1-some-slug.md\n",
    )
    run(tmp_path, occ, roots=("docs",), include_root_md=False)
    assert find_dead_twinned_adr_links(tmp_path, roots=("docs",), include_root_md=False) == []


def test_teeth_skips_frontmatter_fields(tmp_path: Path) -> None:
    """Frontmatter (WP12 territory) is never the tool's rewrite -> not teeth-flagged."""
    _build_era_twin_repo(tmp_path)
    _write(
        tmp_path / "docs" / "guide.md",
        f"---\nrelated: [docs/adr/2.x/{_DEDUPED}]\n---\nbody\n",
    )
    assert find_dead_twinned_adr_links(tmp_path, roots=("docs",), include_root_md=False) == []
