"""Tests for the glossary anchor generator and term linker (FR-011, FR-012, NFR-004).

Covers the two contracts under
``kitty-specs/docs-ia-onboarding-overhaul-01KY02JB/contracts/``:

* ``glossary-anchor-contract.md`` — stable, unique, ASCII slug ``anchor_id`` per
  term, with numeric-suffix collision handling in seed-file order.
* ``glossary-linker-contract.md`` — first-mention-only linking, longest-match-first
  on overlapping term surfaces, and skipping ``<code>``/``<pre>``/``<script>``/
  ``<style>``/``<a>`` content.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.docs import glossary_linker
from scripts.docs.generate_kitty_specs_docs import GLOSSARY_SEED, assign_anchor_ids, slugify

pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# T033/T034 — anchor id generation + collision handling
# ---------------------------------------------------------------------------


def test_anchor_id_slug_matches_contract_example() -> None:
    assert slugify("branch strategy gate", fallback="term") == "branch-strategy-gate"


def test_assign_anchor_ids_produces_unique_stable_ids() -> None:
    terms = [
        {"surface": "branch strategy gate", "definition": "d1", "status": "active", "confidence": 0.9},
        {"surface": "work package", "definition": "d2", "status": "active", "confidence": 0.9},
    ]
    result = assign_anchor_ids(terms)
    assert [t["anchor_id"] for t in result] == ["branch-strategy-gate", "work-package"]
    # Re-running against the same input is deterministic (stable, not random/order-dependent).
    assert assign_anchor_ids(terms) == result


def test_assign_anchor_ids_handles_collisions_with_numeric_suffix_in_seed_order() -> None:
    # Two distinct surfaces that slugify to the same base ("api").
    terms = [
        {"surface": "API!", "definition": "first", "status": "active", "confidence": 0.9},
        {"surface": "API?", "definition": "second", "status": "active", "confidence": 0.9},
        {"surface": "API...", "definition": "third", "status": "active", "confidence": 0.9},
    ]
    result = assign_anchor_ids(terms)
    anchor_ids = [t["anchor_id"] for t in result]
    assert anchor_ids == ["api", "api-2", "api-3"], anchor_ids
    assert len(set(anchor_ids)) == len(anchor_ids)
    # The winner of the un-suffixed slug is whichever term came first in seed order.
    assert result[0]["definition"] == "first"
    assert result[1]["definition"] == "second"
    assert result[2]["definition"] == "third"


def test_real_glossary_seed_yields_one_unique_anchor_per_term() -> None:
    from scripts.docs.generate_kitty_specs_docs import parse_glossary_seed

    parsed = parse_glossary_seed(GLOSSARY_SEED)
    terms = assign_anchor_ids(parsed)
    assert parsed
    # Relational, not absolute: no term is dropped by anchor assignment.
    assert len(terms) == len(parsed)
    anchor_ids = [t["anchor_id"] for t in terms]
    assert len(set(anchor_ids)) == len(anchor_ids), "real glossary seed must not collide today"


def test_glossary_page_renders_stable_per_term_anchor_ids() -> None:
    from scripts.docs.generate_kitty_specs_docs import glossary_page

    rendered = glossary_page([])
    # The card-creation snippet is patched to set a stable id="term-{anchor_id}"
    # (and a data-surface attribute) on every rendered term card, per
    # contracts/glossary-anchor-contract.md.
    assert "card.id = 'term-' + t.anchor_id;" in rendered
    assert "card.dataset.surface = t.surface;" in rendered
    # The static TERMS payload carries an anchor_id for the real glossary seed's
    # "branch strategy gate" alias-family term, matching glossary_linker's href.
    assert '"anchor_id": "action-context"' in rendered or "'anchor_id': 'action-context'" in rendered


# ---------------------------------------------------------------------------
# T035/T036 — glossary_linker.py: loading, matching, linking
# ---------------------------------------------------------------------------


def _term(surface: str, anchor_id: str, definition: str = "def") -> glossary_linker.LinkTerm:
    return glossary_linker.LinkTerm(surface=surface, anchor_id=anchor_id, definition=definition)


def test_load_link_terms_from_real_seed() -> None:
    from scripts.docs.generate_kitty_specs_docs import parse_glossary_seed

    # The real seed never contains a term with a blank surface (anchor_id is
    # always populated by assign_anchor_ids' fallback), so load_link_terms'
    # surface/anchor_id filter is a no-op against it: the count matches the
    # raw parse directly, with no need to duplicate glossary_linker.py's
    # filter condition here.
    terms = glossary_linker.load_link_terms(GLOSSARY_SEED)
    assert len(terms) == len(parse_glossary_seed(GLOSSARY_SEED))
    assert all(t.surface and t.anchor_id for t in terms)


def test_load_link_terms_missing_file_warns_and_returns_empty(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "does-not-exist.yaml"
    terms = glossary_linker.load_link_terms(missing)
    assert terms == []
    assert "WARNING" in capsys.readouterr().err


def test_process_directory_with_no_terms_skips_without_crashing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    site = tmp_path / "_site"
    site.mkdir()
    (site / "page.html").write_text("<html><body>hello</body></html>", encoding="utf-8")
    total = glossary_linker.process_directory(site, [])
    assert total == 0
    assert "WARNING" in capsys.readouterr().err
    # File is untouched.
    assert (site / "page.html").read_text(encoding="utf-8") == "<html><body>hello</body></html>"


def test_link_page_html_links_only_first_mention() -> None:
    terms = [_term("work package", "work-package", "A unit of implementation.")]
    pattern = glossary_linker.build_pattern(terms)
    assert pattern is not None
    term_by_key = {t.surface.lower(): t for t in terms}
    markup = "<body><p>A work package is scoped work. Another work package follows.</p></body>"

    result, added = glossary_linker.link_page_html(markup, pattern, term_by_key)

    assert added == 1
    assert result.count('href="/kitty-specs/glossary.html#term-work-package"') == 1
    assert result.count("work package") == 2  # one linked, one plain
    assert '<a href="/kitty-specs/glossary.html#term-work-package" class="glossary-link" title="A unit of implementation.">work package</a>' in result
    # The second mention stays plain text (not wrapped).
    assert "follows.</p>" in result and "</a> follows" not in result


def test_link_page_html_skips_code_and_pre_blocks() -> None:
    terms = [_term("work package", "work-package", "def")]
    pattern = glossary_linker.build_pattern(terms)
    assert pattern is not None
    term_by_key = {t.surface.lower(): t for t in terms}
    markup = (
        "<body>"
        "<pre><code>work package = load()</code></pre>"
        "<p>See the work package docs.</p>"
        "</body>"
    )

    result, added = glossary_linker.link_page_html(markup, pattern, term_by_key)

    assert added == 1
    assert "<pre><code>work package = load()</code></pre>" in result  # untouched inside code/pre
    assert '<a href="/kitty-specs/glossary.html#term-work-package"' in result  # linked in prose


def test_link_page_html_skips_head_and_title() -> None:
    """Metadata must stay plain: a <title> must not be linked (invalid HTML and
    it would desync from the og:title the SEO verifier pins to the plain title).
    """
    terms = [_term("work package", "work-package", "def")]
    pattern = glossary_linker.build_pattern(terms)
    assert pattern is not None
    term_by_key = {t.surface.lower(): t for t in terms}
    markup = (
        "<html><head><title>Work Package Frontmatter</title></head>"
        "<body><p>See the work package docs.</p></body></html>"
    )

    result, added = glossary_linker.link_page_html(markup, pattern, term_by_key)

    assert added == 1  # only the prose mention is linked
    assert "<title>Work Package Frontmatter</title>" in result  # title untouched
    assert '<a href="/kitty-specs/glossary.html#term-work-package"' in result  # linked in prose


def test_link_page_html_skips_existing_anchor_text() -> None:
    terms = [_term("work package", "work-package", "def")]
    pattern = glossary_linker.build_pattern(terms)
    assert pattern is not None
    term_by_key = {t.surface.lower(): t for t in terms}
    markup = '<body><p>See <a href="/other.html">work package</a> for details.</p></body>'

    result, added = glossary_linker.link_page_html(markup, pattern, term_by_key)

    assert added == 0
    assert result == markup


def test_link_page_html_longest_match_first_on_real_overlapping_terms() -> None:
    # Real overlapping terms from the 104-term glossary: "main repository" is a
    # strict prefix of "main repository root". The longer surface must win when
    # both are present at the same text position.
    terms = [
        _term("main repository", "main-repository", "shorter"),
        _term("main repository root", "main-repository-root", "longer"),
    ]
    pattern = glossary_linker.build_pattern(terms)
    assert pattern is not None
    term_by_key = {t.surface.lower(): t for t in terms}
    markup = "<body><p>Run this from the main repository root, not a worktree.</p></body>"

    result, added = glossary_linker.link_page_html(markup, pattern, term_by_key)

    assert added == 1
    assert '#term-main-repository-root"' in result
    assert '#term-main-repository"' not in result
    assert ">main repository root</a>" in result


def test_link_page_html_case_insensitive_preserves_original_casing() -> None:
    terms = [_term("mission", "mission", "def")]
    pattern = glossary_linker.build_pattern(terms)
    assert pattern is not None
    term_by_key = {t.surface.lower(): t for t in terms}
    markup = "<body><p>A Mission has work packages.</p></body>"

    result, added = glossary_linker.link_page_html(markup, pattern, term_by_key)

    assert added == 1
    assert ">Mission</a>" in result  # original casing preserved in the wrapped text


def test_process_directory_excludes_glossary_page_itself(tmp_path: Path) -> None:
    site = tmp_path / "_site"
    kitty_specs = site / "kitty-specs"
    kitty_specs.mkdir(parents=True)
    (kitty_specs / "glossary.html").write_text(
        "<body><p>work package appears here too.</p></body>", encoding="utf-8"
    )
    other = site / "guides"
    other.mkdir()
    (other / "index.html").write_text("<body><p>Read about a work package.</p></body>", encoding="utf-8")

    terms = [_term("work package", "work-package", "def")]
    total = glossary_linker.process_directory(site, terms)

    assert total == 1
    glossary_markup = (kitty_specs / "glossary.html").read_text(encoding="utf-8")
    assert "glossary-link" not in glossary_markup  # untouched
    other_markup = (other / "index.html").read_text(encoding="utf-8")
    assert "glossary-link" in other_markup


def test_process_directory_never_writes_a_markdown_file(tmp_path: Path) -> None:
    # Guards the "HTML-only post-processing, never mutate markdown source"
    # decision (01KY03YGX7GQEBKV45Q2Q8FXK3): stage a markdown file alongside
    # the HTML output and prove the linker never touches it, even though its
    # text also contains the glossary term.
    site = tmp_path / "_site"
    site.mkdir()
    (site / "page.html").write_text("<body><p>See the work package guide.</p></body>", encoding="utf-8")
    markdown_sidecar = tmp_path / "page.md"
    markdown_sidecar.write_text("See the work package guide.\n", encoding="utf-8")

    terms = [_term("work package", "work-package", "def")]
    glossary_linker.process_directory(site, terms)

    assert markdown_sidecar.read_text(encoding="utf-8") == "See the work package guide.\n"
