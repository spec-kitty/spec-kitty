"""Tests for the built-output SEO verifier and the description backstop.

Every fixture is a synthetic ``_site`` tree under ``tmp_path``: no DocFX build is
required, so these stay in the fast tier despite asserting against build output.

The point of this suite is that each rule can go **red**. A gate that cannot fail
is decoration, so every rule below has a fixture that violates exactly it, and
``test_clean_site_is_green`` pins the complementary case.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pytest

from scripts.docs import seo_postprocess, seo_verify

_REPO_ROOT = Path(__file__).resolve().parents[2]

pytestmark = [pytest.mark.unit, pytest.mark.fast]

BASE_URL = "https://docs.spec-kitty.ai/"
IMAGE = "assets/images/logo_small.webp"

HOME_DESCRIPTION = "The Spec Kitty documentation home page, covering install, missions, and CLI workflows."
INSTALL_DESCRIPTION = "Install Spec Kitty on macOS, Linux, and Windows, then run your first governed mission."


def _rendered_page(
    *,
    title: str | None,
    description: str | None,
    canonical: str,
    og_title: str | None = None,
    og_description: str | None = None,
) -> str:
    """Render an indexable page. ``og:*`` default to agreeing with the page."""
    head = ["<!doctype html>", "<html>", "<head>"]
    if title is not None:
        head.append(f"  <title>{title}</title>")
    if description is not None:
        head.append(f'  <meta name="description" content="{description}">')
    head.append(f'  <link rel="canonical" href="{canonical}">')
    effective_title = title if title is not None else seo_postprocess.DEFAULT_TITLE
    effective_description = description if description is not None else seo_postprocess.FALLBACK_DESCRIPTION
    head.append(f'  <meta property="og:title" content="{effective_title if og_title is None else og_title}">')
    head.append(f'  <meta property="og:description" content="{effective_description if og_description is None else og_description}">')
    head += ["</head>", "<body><h1>Page</h1></body>", "</html>", ""]
    return "\n".join(head)


def _redirect_stub(target: str) -> str:
    """A redirect stub, matching ``redirect_stub_generator.STUB_TEMPLATE``."""
    return (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n<title>Page moved</title>\n'
        f'<meta http-equiv="refresh" content="0; url={target}">\n'
        f'<link rel="canonical" href="{target}">\n'
        '<meta name="robots" content="noindex">\n'
        "</head>\n<body><p>Moved.</p></body>\n</html>\n"
    )


def _write(site: Path, relative_path: str, markup: str) -> None:
    target = site / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markup, encoding="utf-8")


def _write_sitemap(site: Path, urls: list[str]) -> None:
    entries = "\n".join(f"  <url><loc>{url}</loc></url>" for url in urls)
    _write(
        site,
        "sitemap.xml",
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{entries}\n</urlset>\n',
    )


@pytest.fixture()
def clean_site(tmp_path: Path) -> Path:
    """A fully compliant ``_site``: two indexable pages, a toc, and a stub."""
    site = tmp_path / "_site"
    site.mkdir()
    _write(site, "index.html", _rendered_page(title="Spec Kitty Docs", description=HOME_DESCRIPTION, canonical=BASE_URL))
    _write(
        site,
        "guides/install.html",
        _rendered_page(
            title="Install Spec Kitty",
            description=INSTALL_DESCRIPTION,
            canonical=f"{BASE_URL}guides/install.html",
        ),
    )
    _write(site, "toc.html", '<html><head><title>TOC</title><meta name="robots" content="noindex, follow"></head></html>')
    _write(site, "how-to/install-spec-kitty.html", _redirect_stub(f"{BASE_URL}guides/install.html"))
    _write_sitemap(site, [BASE_URL, f"{BASE_URL}guides/install.html"])
    return site


def _violations(site: Path, rule: str) -> list[seo_verify.Violation]:
    record = seo_verify.verify_site(site_dir=site, base_url=BASE_URL)
    return [violation for violation in record.violations if violation.rule == rule]


def _tree_snapshot(root: Path) -> dict[str, bytes]:
    """Byte-exact snapshot of a tree.

    Deliberately *not* ``charter.hasher.hash_content``: that helper normalizes
    BOMs, line endings, and outer whitespace, which is exactly the class of
    mutation this test has to catch. Comparing raw bytes is strictly stronger
    than comparing a digest and needs no hashing primitive.
    """
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


# --- V-06 … V-10 red paths --------------------------------------------------


def test_missing_description_is_red(clean_site: Path) -> None:
    """V-06: an indexable page with no description tag is a defect."""
    _write(
        clean_site,
        "guides/install.html",
        _rendered_page(title="Install Spec Kitty", description=None, canonical=f"{BASE_URL}guides/install.html"),
    )
    violations = _violations(clean_site, "V-06")
    assert [violation.path for violation in violations] == ["guides/install.html"]
    assert "description" in (violations[0].detail or "")


def test_boilerplate_description_is_red(clean_site: Path) -> None:
    """V-07: the backstop string is treated as equivalent to missing."""
    _write(
        clean_site,
        "guides/install.html",
        _rendered_page(
            title="Install Spec Kitty",
            description=seo_postprocess.FALLBACK_DESCRIPTION,
            canonical=f"{BASE_URL}guides/install.html",
        ),
    )
    violations = _violations(clean_site, "V-07")
    assert [violation.path for violation in violations] == ["guides/install.html"]


def test_wrong_canonical_is_red(clean_site: Path) -> None:
    """V-08: the canonical must address the page it sits on."""
    _write(
        clean_site,
        "guides/install.html",
        _rendered_page(
            title="Install Spec Kitty",
            description=INSTALL_DESCRIPTION,
            canonical=f"{BASE_URL}somewhere/else.html",
        ),
    )
    violations = _violations(clean_site, "V-08")
    assert [violation.path for violation in violations] == ["guides/install.html"]
    assert "somewhere/else.html" in (violations[0].detail or "")


def test_og_mismatch_is_red(clean_site: Path) -> None:
    """V-09: Open Graph values diverging from the page's own metadata."""
    _write(
        clean_site,
        "guides/install.html",
        _rendered_page(
            title="Install Spec Kitty",
            description=INSTALL_DESCRIPTION,
            canonical=f"{BASE_URL}guides/install.html",
            og_description="Something else entirely.",
        ),
    )
    violations = _violations(clean_site, "V-09")
    assert [violation.path for violation in violations] == ["guides/install.html"]
    assert "og:description" in (violations[0].detail or "")


def test_og_title_mismatch_is_red(clean_site: Path) -> None:
    """V-09 guards og:title as well as og:description.

    The two comparisons are independent branches; a suite that only ever
    perturbs the description leaves the title half of the rule unguarded.
    """
    _write(
        clean_site,
        "guides/install.html",
        _rendered_page(
            title="Install Spec Kitty",
            description=INSTALL_DESCRIPTION,
            canonical=f"{BASE_URL}guides/install.html",
            og_title="A completely different page",
        ),
    )
    violations = _violations(clean_site, "V-09")
    assert [violation.path for violation in violations] == ["guides/install.html"]
    assert "og:title" in (violations[0].detail or "")


def test_missing_title_is_red(clean_site: Path) -> None:
    """NFR-001: titles must exist and must not be the bare site default."""
    _write(
        clean_site,
        "guides/install.html",
        _rendered_page(
            title=seo_postprocess.DEFAULT_TITLE,
            description=INSTALL_DESCRIPTION,
            canonical=f"{BASE_URL}guides/install.html",
        ),
    )
    violations = _violations(clean_site, "NFR-001")
    assert [violation.path for violation in violations] == ["guides/install.html"]


def test_absent_title_is_red(clean_site: Path) -> None:
    """NFR-001 has two failure modes, and the absent one is not the default one.

    A page with no ``<title>`` at all never compares equal to
    :data:`DEFAULT_TITLE`, so the "title is the site default" branch cannot
    catch it. Pinning both keeps either branch from being dropped silently.
    """
    _write(
        clean_site,
        "guides/install.html",
        _rendered_page(title=None, description=INSTALL_DESCRIPTION, canonical=f"{BASE_URL}guides/install.html"),
    )
    violations = _violations(clean_site, "NFR-001")
    assert [violation.path for violation in violations] == ["guides/install.html"]
    assert "missing" in (violations[0].detail or "")


def test_duplicate_description_is_red(clean_site: Path) -> None:
    """V-10: two indexable pages sharing a description flags *both*."""
    _write(
        clean_site,
        "guides/install.html",
        _rendered_page(
            title="Install Spec Kitty",
            description=HOME_DESCRIPTION,
            canonical=f"{BASE_URL}guides/install.html",
        ),
    )
    violations = _violations(clean_site, "V-10")
    assert sorted(violation.path for violation in violations) == ["guides/install.html", "index.html"]


def test_duplicate_violation_names_peer(clean_site: Path) -> None:
    """I-07: a uniqueness failure reporting one side is not actionable."""
    _write(
        clean_site,
        "guides/install.html",
        _rendered_page(
            title="Install Spec Kitty",
            description=HOME_DESCRIPTION,
            canonical=f"{BASE_URL}guides/install.html",
        ),
    )
    peers = {violation.path: violation.peer for violation in _violations(clean_site, "V-10")}
    assert peers == {"guides/install.html": "index.html", "index.html": "guides/install.html"}


# --- Stub / sitemap invariants ---------------------------------------------


def test_stub_is_not_indexable(clean_site: Path) -> None:
    """Refresh-stub markup classifies as REDIRECT_STUB and skips the rules."""
    record = seo_verify.verify_site(site_dir=clean_site, base_url=BASE_URL)
    classes = {page.relative_path: page.classification for page in record.pages}
    assert classes["how-to/install-spec-kitty.html"] is seo_verify.PageClass.REDIRECT_STUB
    assert classes["toc.html"] is seo_verify.PageClass.TOC_PAGE
    # The stub carries no description and a canonical pointing elsewhere; if the
    # rules were applied to it, V-06 and V-08 would fire against its path.
    assert not [v for v in record.violations if v.path == "how-to/install-spec-kitty.html"]


def test_stub_absent_from_sitemap(clean_site: Path) -> None:
    """C-B6/I-09: a stub address appearing in the sitemap is a violation."""
    assert not _violations(clean_site, "I-09")
    _write_sitemap(
        clean_site,
        [BASE_URL, f"{BASE_URL}guides/install.html", f"{BASE_URL}how-to/install-spec-kitty.html"],
    )
    violations = _violations(clean_site, "I-09")
    assert [violation.path for violation in violations] == ["how-to/install-spec-kitty.html"]


def test_stub_without_noindex_is_red(clean_site: Path) -> None:
    """I-09: a stub that lost its noindex directive is a violation."""
    stub = clean_site / "how-to/install-spec-kitty.html"
    stub.write_text(
        stub.read_text(encoding="utf-8").replace('<meta name="robots" content="noindex">\n', ""),
        encoding="utf-8",
    )
    violations = _violations(clean_site, "I-09")
    assert [violation.path for violation in violations] == ["how-to/install-spec-kitty.html"]


def test_sitemap_set_mismatch_is_red(clean_site: Path) -> None:
    """C-B6: sitemap entries and indexable pages must be the same set."""
    _write_sitemap(clean_site, [BASE_URL])
    violations = _violations(clean_site, "C-B6")
    assert [violation.path for violation in violations] == ["guides/install.html"]


def test_sitemap_entry_without_a_page_is_red(clean_site: Path) -> None:
    """C-B6 is a set *equality*, so the orphan direction must fail too.

    An entry pointing at a page that no longer exists is a 404 advertised to
    crawlers. Only checking "every page is listed" would let it ship.
    """
    _write_sitemap(
        clean_site,
        [BASE_URL, f"{BASE_URL}guides/install.html", f"{BASE_URL}guides/deleted.html"],
    )
    violations = _violations(clean_site, "C-B6")
    assert [violation.path for violation in violations] == ["sitemap.xml"]
    assert "guides/deleted.html" in (violations[0].detail or "")


def test_non_indexable_pages_are_labelled_by_reason(clean_site: Path) -> None:
    """Each non-indexable class names *why* the page is out of scope.

    The labels are diagnostic, not cosmetic. Folding an ``assets/`` page or a
    page carrying an explicit ``robots: noindex`` into a neighbouring bucket
    would report a real misconfiguration as something benign — which is the
    same silent-mislabelling failure this mission exists to remove.
    """
    _write(clean_site, "assets/stopwords.html", "<html><head><title>Stopwords</title></head><body></body></html>")
    _write(
        clean_site,
        "guides/draft.html",
        '<html><head><title>Draft</title><meta name="robots" content="noindex, follow"></head><body></body></html>',
    )
    record = seo_verify.verify_site(site_dir=clean_site, base_url=BASE_URL)
    classes = {page.relative_path: page.classification for page in record.pages}
    assert classes["assets/stopwords.html"] is seo_verify.PageClass.ASSET
    assert classes["guides/draft.html"] is seo_verify.PageClass.NOINDEX
    assert classes["toc.html"] is seo_verify.PageClass.TOC_PAGE
    assert classes["how-to/install-spec-kitty.html"] is seo_verify.PageClass.REDIRECT_STUB
    assert record.counts["ASSET"] == 1
    assert record.counts["NOINDEX"] == 1


def test_verifier_does_not_mutate_site(clean_site: Path, tmp_path: Path) -> None:
    """C-B6: a tool that can fix what it checks can pass itself."""
    before = _tree_snapshot(clean_site)
    exit_code = seo_verify.main(["--site-dir", str(clean_site), "--base-url", BASE_URL, "--json", str(tmp_path / "report.json")])
    assert exit_code == 0
    assert _tree_snapshot(clean_site) == before


def test_json_report_inside_site_dir_is_refused(clean_site: Path) -> None:
    """The read-only guarantee is enforced, not merely documented."""
    with pytest.raises(SystemExit):
        seo_verify.main(["--site-dir", str(clean_site), "--json", str(clean_site / "report.json")])


# --- Exit contract, determinism, evidence -----------------------------------


def test_clean_site_is_green(clean_site: Path) -> None:
    """A compliant fixture produces zero violations and exit 0 under --strict."""
    record = seo_verify.verify_site(site_dir=clean_site, base_url=BASE_URL)
    assert record.violations == ()
    assert record.counts["INDEXABLE"] == 2
    assert seo_verify.main(["--site-dir", str(clean_site), "--base-url", BASE_URL, "--strict"]) == 0


def test_strict_exits_nonzero(clean_site: Path) -> None:
    """Report-only exits 0; --strict exits non-zero on the same input."""
    _write(
        clean_site,
        "guides/install.html",
        _rendered_page(title="Install Spec Kitty", description=None, canonical=f"{BASE_URL}guides/install.html"),
    )
    argv = ["--site-dir", str(clean_site), "--base-url", BASE_URL]
    assert seo_verify.main(argv) == 0
    assert seo_verify.main([*argv, "--strict"]) == 1


def test_report_is_deterministic(clean_site: Path, tmp_path: Path) -> None:
    """I-06: two runs over identical input produce byte-identical reports."""
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    argv = ["--site-dir", str(clean_site), "--base-url", BASE_URL]
    seo_verify.main([*argv, "--json", str(first)])
    seo_verify.main([*argv, "--json", str(second)])
    assert first.read_bytes() == second.read_bytes()


def test_violations_are_ordered_by_path_not_by_rule_group(tmp_path: Path) -> None:
    """I-06: ordering is canonical, not an accident of evaluation order.

    Per-page rules are evaluated before the whole-site sitemap rule, so without
    an explicit sort the report is grouped by *which rule ran first* rather than
    by page. Two runs of one process agree either way — which is why
    ``test_report_is_deterministic`` cannot see this — but the diff between two
    builds becomes unreadable, and a reordering counts as a spurious change.
    """
    site = tmp_path / "_site"
    site.mkdir()
    # ``aaa`` is compliant but unlisted (C-B6); ``zzz`` is listed but has no
    # description (V-06). Evaluation order emits zzz first; path order is aaa.
    _write(site, "aaa.html", _rendered_page(title="Alpha", description=HOME_DESCRIPTION, canonical=f"{BASE_URL}aaa.html"))
    _write(site, "zzz.html", _rendered_page(title="Omega", description=None, canonical=f"{BASE_URL}zzz.html"))
    _write_sitemap(site, [f"{BASE_URL}zzz.html"])
    record = seo_verify.verify_site(site_dir=site, base_url=BASE_URL)
    assert [(v.path, v.rule) for v in record.violations] == [("aaa.html", "C-B6"), ("zzz.html", "V-06")]


def test_report_keys_are_sorted(clean_site: Path) -> None:
    """I-06: JSON key order must not track Python declaration order.

    ``counts`` is built from :class:`PageClass` in declaration order, which is
    not alphabetical. Serializing without ``sort_keys`` therefore leaks the enum
    definition into the artifact, so reordering the enum would rewrite every
    stored report.
    """
    record = seo_verify.verify_site(site_dir=clean_site, base_url=BASE_URL)
    payload = json.loads(record.to_json())
    assert list(payload) == sorted(payload)
    assert list(payload["counts"]) == sorted(payload["counts"])
    # Guard: this assertion only has teeth while the enum's declaration order
    # differs from alphabetical. Reordering PageClass fails here loudly rather
    # than letting the check above decay into a tautology.
    assert [member.value for member in seo_verify.PageClass] != sorted(payload["counts"])


def test_report_records_stale_url_finding(clean_site: Path) -> None:
    """FR-011/C-B8: the audit names both the reported and the current address."""
    record = seo_verify.verify_site(site_dir=clean_site, base_url=BASE_URL)
    findings = {finding["reported_address"]: finding for finding in record.findings}
    assert set(findings) == {"how-to/install-spec-kitty.html", "reference/slash-commands.html"}
    install = findings["how-to/install-spec-kitty.html"]
    assert install["current_address"] == "guides/install-spec-kitty.html"
    assert install["reported_classification"] == "REDIRECT_STUB"
    assert "1652" in str(install["issue_url"])


def test_stale_url_finding_note_states_only_what_was_observed(clean_site: Path) -> None:
    """FR-011: the note is evidence, so it must not confirm an unobserved page."""

    def note(site: Path) -> str:
        record = seo_verify.verify_site(site_dir=site, base_url=BASE_URL)
        finding = next(f for f in record.findings if f["reported_address"] == "how-to/install-spec-kitty.html")
        return str(finding["note"])

    # The live page is absent from the fixture: no confirmation may be claimed.
    assert note(clean_site).startswith("Not observed")

    _write(
        clean_site,
        "guides/install-spec-kitty.html",
        _rendered_page(
            title="Install Spec Kitty",
            description="Step-by-step Spec Kitty installation for every supported operating system.",
            canonical=f"{BASE_URL}guides/install-spec-kitty.html",
        ),
    )
    assert note(clean_site).startswith("Confirmed")

    # Third branch: both addresses resolve, but the reported one is an ordinary
    # indexable page rather than a redirect stub. That is neither "absent" nor
    # the migration shape the finding claims, so the note must say so instead of
    # silently falling back to either of the other two sentences.
    _write(
        clean_site,
        "how-to/install-spec-kitty.html",
        _rendered_page(
            title="Install Spec Kitty (old address)",
            description="An install page still served at the pre-move address instead of a redirect stub.",
            canonical=f"{BASE_URL}how-to/install-spec-kitty.html",
        ),
    )
    unexpected = note(clean_site)
    assert unexpected.startswith("Both addresses are present")
    assert unexpected not in {seo_verify._NOTE_CONFIRMED, seo_verify._NOTE_NOT_OBSERVED}


# --- The shared extractors both modules read metadata with -------------------
#
# ``find_title`` / ``find_description`` exist so the emitter and the verifier
# read a page through one parser (I-08). That only holds if the reading itself
# is right: a divergence here does not show up as a verifier bug, it shows up as
# the verifier and the emitter quietly disagreeing about what the page says.


def test_find_title_strips_the_docfx_site_suffix() -> None:
    """DocFX appends ``| Spec Kitty Documentation``; NFR-001 judges the rest.

    Without the strip, every page's title ends in the site name, so the "title
    is the bare site default" rule never fires and ``og:title`` comparisons in
    the verifier drift against the emitter's own value.
    """
    markup = f"<html><head><title>Install Spec Kitty | {seo_postprocess.DEFAULT_TITLE}</title></head></html>"
    assert seo_postprocess.find_title(markup) == "Install Spec Kitty"
    assert seo_postprocess.extract_title(markup) == "Install Spec Kitty"


def test_find_title_reports_absence_where_extract_title_defaults() -> None:
    """The pair differs only in how it reports "the page has no title"."""
    markup = "<html><head></head><body></body></html>"
    assert seo_postprocess.find_title(markup) is None
    assert seo_postprocess.extract_title(markup) == seo_postprocess.DEFAULT_TITLE


def test_find_description_normalizes_whitespace_and_entities() -> None:
    """Two descriptions that render identically must compare identically.

    V-09 compares the description against ``og:description`` and V-10 compares
    pages against each other. Without normalization, a line break inserted by
    the template or an ``&amp;`` in the source would make equal descriptions
    look different — a false green on V-10 and a false red on V-09.
    """
    markup = '<html><head><meta name="description" content="Run\n  spec-kitty &amp; ship.  "></head></html>'
    assert seo_postprocess.find_description(markup) == "Run spec-kitty & ship."


def test_find_description_treats_a_blank_tag_as_absent() -> None:
    """An empty ``content`` is a missing description, not an empty one (V-06)."""
    markup = '<html><head><meta name="description" content="   "></head></html>'
    assert seo_postprocess.find_description(markup) is None
    assert seo_postprocess.extract_description(markup) == seo_postprocess.FALLBACK_DESCRIPTION


# --- T022: the post-processor's description backstop ------------------------


def _postprocess(site: Path) -> None:
    seo_postprocess.process_html(site, BASE_URL, IMAGE)


def test_postprocess_emits_description(tmp_path: Path) -> None:
    """C-B1: a page with no description tag gains one."""
    site = tmp_path / "_site"
    site.mkdir()
    _write(site, "adr/decision.html", "<html><head><title>A decision</title></head><body></body></html>")
    _postprocess(site)
    rendered = (site / "adr/decision.html").read_text(encoding="utf-8")
    assert '<meta name="description" content=' in rendered
    assert seo_postprocess.find_description(rendered) == seo_postprocess.FALLBACK_DESCRIPTION


def test_postprocess_preserves_existing_description(tmp_path: Path) -> None:
    """C-B1: DocFX's frontmatter-derived description stays authoritative."""
    site = tmp_path / "_site"
    site.mkdir()
    _write(
        site,
        "guides/install.html",
        f'<html><head><title>Install</title><meta name="description" content="{INSTALL_DESCRIPTION}"></head><body></body></html>',
    )
    _postprocess(site)
    rendered = (site / "guides/install.html").read_text(encoding="utf-8")
    assert rendered.count('name="description"') == 1
    assert seo_postprocess.find_description(rendered) == INSTALL_DESCRIPTION


def test_postprocess_is_idempotent(tmp_path: Path) -> None:
    """C-B2: the strip-then-reinsert cycle survives a second pass."""
    site = tmp_path / "_site"
    site.mkdir()
    _write(site, "adr/decision.html", "<html><head><title>A decision</title></head><body></body></html>")
    _postprocess(site)
    once = (site / "adr/decision.html").read_text(encoding="utf-8")
    _postprocess(site)
    assert (site / "adr/decision.html").read_text(encoding="utf-8") == once


# --- C-B2: backslashes in author prose must not be read as group references --
#
# ``_replace_head_close`` substitutes through a callable so ``re.sub`` treats the
# injected block literally. Injecting the block as a replacement *string* instead
# fails in two ways, and only one of them is loud:
#
#   ``\1``      -> re.error: invalid group reference        (the build crashes)
#   ``C:\temp`` -> ``\t`` becomes a TAB in the output; the JSON-LD still parses,
#                  so the corruption ships silently
#
# The second is the reason both fixtures exist: a test covering only the raising
# case would stay green while the emitted metadata quietly differed from what the
# author wrote. Docs in this repo describe regexes and Windows paths, so neither
# input is hypothetical.

BACKSLASH_GROUP_DESCRIPTION = r"Rewrite the matched path to \1 when documenting the redirect regex."
WINDOWS_PATH_DESCRIPTION = r"Point the cache at C:\temp on Windows when the default directory is read-only."


def _og_description(markup: str) -> str:
    """The ``og:description`` the injected block emitted, un-escaped."""
    match = re.search(r'<meta property="og:description" content="(.*?)">', markup)
    assert match is not None, "the injected block emitted no og:description"
    return html.unescape(match.group(1))


def _json_ld_description(markup: str) -> str:
    """The ``description`` of the first JSON-LD node in the injected block."""
    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', markup, re.DOTALL)
    assert match is not None, "the injected block emitted no JSON-LD"
    payload = json.loads(match.group(1))
    return str(payload[0]["description"])


def _page_with_description(site: Path, relative_path: str, description: str) -> str:
    """Write one indexable page carrying ``description``, post-process, re-read."""
    _write(
        site,
        relative_path,
        f'<html><head><title>Install notes</title><meta name="description" content="{description}"></head><body></body></html>',
    )
    _postprocess(site)
    return (site / relative_path).read_text(encoding="utf-8")


def test_postprocess_survives_group_reference_in_description(tmp_path: Path) -> None:
    """A description containing ``\\1`` must not be parsed as a group reference."""
    site = tmp_path / "_site"
    site.mkdir()
    # Under a string-form re.sub this raises re.error and the docs build dies.
    rendered = _page_with_description(site, "guides/regex.html", BACKSLASH_GROUP_DESCRIPTION)
    assert seo_postprocess.find_description(rendered) == BACKSLASH_GROUP_DESCRIPTION
    assert _og_description(rendered) == BACKSLASH_GROUP_DESCRIPTION
    assert _json_ld_description(rendered) == BACKSLASH_GROUP_DESCRIPTION


def test_postprocess_does_not_corrupt_windows_path_in_description(tmp_path: Path) -> None:
    """A description containing ``C:\\temp`` must survive byte-for-byte.

    This is the silent mode: ``\\t`` is a valid JSON escape, so a corrupted
    JSON-LD block still parses — it just yields a TAB where the author wrote a
    backslash. Asserting the parsed value (not merely that parsing succeeded) is
    what makes the corruption visible.
    """
    site = tmp_path / "_site"
    site.mkdir()
    rendered = _page_with_description(site, "guides/windows.html", WINDOWS_PATH_DESCRIPTION)
    assert "\t" not in rendered
    assert seo_postprocess.find_description(rendered) == WINDOWS_PATH_DESCRIPTION
    assert _og_description(rendered) == WINDOWS_PATH_DESCRIPTION
    assert _json_ld_description(rendered) == WINDOWS_PATH_DESCRIPTION
