"""Tests for the published-page-set resolver (``scripts/docs/_published_pages.py``).

The resolver exists because "which source pages are published" had two answers —
``docs/docfx.json`` and a hardcoded glob list in ``tests/docs/test_docs_seo.py``
— that silently diverged, leaving the SEO gate guarding 16 of 674 pages.

Two families of assertion carry the weight here:

* **Membership, not reasoning** — DocFX glob semantics differ from ``pathlib``
  semantics, and a mistranslation under-collects silently. So the translation is
  proved by asserting that specific, known live pages are members
  (:func:`test_live_tree_membership`), never by arguing about globs.
* **The regression proof** —
  :func:`test_would_have_caught_the_original_regression` replays the retired
  pre-move glob list against the live tree and asserts the resolver refuses it.
  It encodes *this specific historical failure* so a future reorganisation
  cannot reproduce it silently.

Small synthetic trees would trip the non-vacuity floor, so the shared fixture
builds a tree comfortably above :data:`MINIMUM_EXPECTED_PAGES`. That keeps the
resolver's public surface exactly as contracted — there is deliberately no
"skip the floor" parameter, because such a parameter would be a code path that
returns a degraded set.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.docs._published_pages import (
    DEFAULT_EXCLUSIONS,
    MINIMUM_EXPECTED_PAGES,
    Exclusion,
    PublishedPageSet,
    resolve_published_pages,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE_DOCS_ROOT = REPO_ROOT / "docs"

#: Pages measured as published at the time this gate was built (research R-002).
MEASURED_PAGE_COUNT = 674

#: Tolerance around :data:`MEASURED_PAGE_COUNT`. Wide enough to absorb ordinary
#: authoring churn, narrow enough that a glob mistranslation (which collapses
#: the count by hundreds) cannot hide inside it.
COUNT_TOLERANCE = 150

#: Pages known to be published. A mistranslated ``<dir>/**.md`` drops the ones
#: that sit directly inside a globbed directory, so the canaries deliberately
#: mix depths: ``docs/README.md`` (repo root of the tree), ``api/…`` and
#: ``guides/…`` (one level down, the shape the naive ``**/*.md`` misses), and
#: ``adr/3.x/…`` (two levels down).
CANARY_PAGES = (
    Path("docs/api/slash-commands.md"),
    Path("docs/guides/how-to/installation/install-spec-kitty.md"),
    Path("docs/adr/3.x/2026-07-08-1-mission-resolver-port.md"),
    Path("docs/README.md"),
)

#: The glob list retired from ``tests/docs/test_docs_seo.py``. It predates the
#: ``how-to/`` → ``guides/`` and ``reference/slash-commands`` → ``api/`` moves
#: and resolves 16 pages against today's tree.
RETIRED_PRE_MOVE_GLOBS = [
    "README.md",
    "tutorials/*.md",
    "how-to/*.md",
    "how-to/harnesses/*.md",
    "reference/*.md",
    "explanation/*.md",
    "recovery/*.md",
    "3x/**/*.md",
    "archive/**/*.md",
    "migration/**/*.md",
]

_SYNTHETIC_PAGE_COUNT = MINIMUM_EXPECTED_PAGES + 20
_SYNTHETIC_EXTRA_COUNT = 5


@pytest.fixture(scope="session")
def synthetic_docs(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A read-only docs tree large enough to clear the non-vacuity floor.

    Layout (``context/`` holds pages at two depths so the ``<dir>/**.md`` shape
    is exercised on both)::

        docs/context/page_*.md      (half at depth 1, half under nested/)
        docs/context/_draft.md      (underscore-prefixed, publishable only if
                                     docfx.json omits the "**/_*.md" exclude)
        docs/context/toc.yml        (navigation, never a page)
        docs/extra/extra_*.md       (a directory a second glob can add)
    """
    root = tmp_path_factory.mktemp("published_pages") / "docs"
    nested = root / "context" / "nested"
    nested.mkdir(parents=True)
    for index in range(_SYNTHETIC_PAGE_COUNT):
        target = root / "context" if index % 2 else nested
        (target / f"page_{index:04d}.md").write_text("# page\n", encoding="utf-8")
    (root / "context" / "_draft.md").write_text("# draft\n", encoding="utf-8")
    (root / "context" / "toc.yml").write_text("items: []\n", encoding="utf-8")

    extra = root / "extra"
    extra.mkdir()
    for index in range(_SYNTHETIC_EXTRA_COUNT):
        (extra / f"extra_{index:02d}.md").write_text("# extra\n", encoding="utf-8")
    return root


def _write_config(
    directory: Path,
    files: list[str],
    *,
    exclude: list[str] | None = None,
    name: str = "docfx.json",
) -> Path:
    """Write a minimal ``docfx.json`` and return its path."""
    entry: dict[str, object] = {"files": files}
    if exclude is not None:
        entry["exclude"] = exclude
    config_path = directory / name
    config_path.write_text(json.dumps({"build": {"content": [entry]}}), encoding="utf-8")
    return config_path


def _resolve_live() -> PublishedPageSet:
    """Resolve the real repository documentation tree."""
    return resolve_published_pages(docs_root=LIVE_DOCS_ROOT)


def test_resolves_from_docfx_not_a_constant(synthetic_docs: Path, tmp_path: Path) -> None:
    """Adding a glob to docfx.json changes the result — the read is live (C-R1, I-03)."""
    narrow = _write_config(tmp_path, ["context/**.md"], exclude=["**/_*.md"], name="narrow.json")
    widened = _write_config(
        tmp_path, ["context/**.md", "extra/**.md"], exclude=["**/_*.md"], name="widened.json"
    )

    before = resolve_published_pages(docs_root=synthetic_docs, docfx_config=narrow)
    after = resolve_published_pages(docs_root=synthetic_docs, docfx_config=widened)

    assert before.pages != after.pages, "resolver ignored the widened docfx.json — globs are shadowed by a constant"
    assert after.pages > before.pages
    assert len(after.pages) == len(before.pages) + _SYNTHETIC_EXTRA_COUNT
    assert "extra/**.md" in after.source_globs
    assert "extra/**.md" not in before.source_globs


def test_underscore_prefixed_pages_excluded(synthetic_docs: Path, tmp_path: Path) -> None:
    """``**/_*.md`` from docfx.json is honoured, not hardcoded (C-R2)."""
    honoured = _write_config(tmp_path, ["context/**.md"], exclude=["**/_*.md"], name="honoured.json")
    unfiltered = _write_config(tmp_path, ["context/**.md"], name="unfiltered.json")
    draft = Path("docs/context/_draft.md")

    with_exclude = resolve_published_pages(docs_root=synthetic_docs, docfx_config=honoured)
    without_exclude = resolve_published_pages(docs_root=synthetic_docs, docfx_config=unfiltered)

    assert draft not in with_exclude.pages
    assert Path("docs/context/page_0001.md") in with_exclude.pages
    # Proves the exclusion came from the config rather than a literal in the module.
    assert draft in without_exclude.pages


def test_every_exclusion_carries_a_reason() -> None:
    """Exclusions are enumerated, reasoned, and actually applied (I-04, I-05, FR-013)."""
    resolved = _resolve_live()

    assert resolved.exclusions == DEFAULT_EXCLUSIONS
    assert resolved.exclusions, "the resolver must enumerate its exclusions, not apply them anonymously"
    for exclusion in resolved.exclusions:
        assert exclusion.reason.strip(), f"exclusion {exclusion.pattern!r} states no reason"

    excluded_roots = tuple(exclusion.pattern.split("/", 1)[0] for exclusion in resolved.exclusions)
    for page in resolved.pages:
        assert page.parts[1] not in excluded_roots, f"{page} survived an enumerated exclusion"

    with pytest.raises(ValueError, match="non-empty reason"):
        Exclusion(pattern="whatever/**", reason="   ")


def test_empty_resolution_raises(synthetic_docs: Path, tmp_path: Path) -> None:
    """An empty resolution raises instead of returning a vacuous set (I-01)."""
    config = _write_config(tmp_path, ["nowhere/**.md"], exclude=["**/_*.md"], name="empty.json")

    with pytest.raises(ValueError, match="is empty"):
        resolve_published_pages(docs_root=synthetic_docs, docfx_config=config)


def test_below_floor_raises(synthetic_docs: Path, tmp_path: Path) -> None:
    """Under-collection raises, naming both the observed and expected counts (I-02)."""
    config = _write_config(tmp_path, ["extra/**.md"], exclude=["**/_*.md"], name="floor.json")

    with pytest.raises(ValueError) as excinfo:
        resolve_published_pages(docs_root=synthetic_docs, docfx_config=config)

    message = str(excinfo.value)
    assert str(_SYNTHETIC_EXTRA_COUNT) in message, message
    assert str(MINIMUM_EXPECTED_PAGES) in message, message


def test_missing_docfx_raises(synthetic_docs: Path, tmp_path: Path) -> None:
    """A missing authority fails loud rather than degrading to a guess."""
    absent = tmp_path / "absent" / "docfx.json"

    with pytest.raises(FileNotFoundError) as excinfo:
        resolve_published_pages(docs_root=synthetic_docs, docfx_config=absent)

    assert str(absent) in str(excinfo.value)


def test_toc_yml_is_not_a_page(synthetic_docs: Path, tmp_path: Path) -> None:
    """``toc.yml`` appears in build.content but is navigation, not a page."""
    config = _write_config(
        tmp_path,
        ["context/**.md", "context/toc.yml", "toc.yml"],
        exclude=["**/_*.md"],
        name="with_toc.json",
    )

    resolved = resolve_published_pages(docs_root=synthetic_docs, docfx_config=config)

    assert Path("docs/context/toc.yml") not in resolved.pages
    assert all(page.suffix == ".md" for page in resolved.pages)
    assert all(glob.endswith(".md") for glob in resolved.source_globs)


def test_live_tree_membership() -> None:
    """Known live pages are members — the empirical proof of glob fidelity (C-R5)."""
    resolved = _resolve_live()

    for canary in CANARY_PAGES:
        assert (REPO_ROOT / canary).is_file(), f"canary {canary} does not exist on disk — the assertion would pass vacuously"
        assert canary in resolved.pages, f"{canary} is published but the resolver missed it"


def test_live_tree_count_is_realistic() -> None:
    """The live count clears the floor and sits near the measured 674 (C-R5)."""
    resolved = _resolve_live()
    count = len(resolved.pages)

    assert count >= MINIMUM_EXPECTED_PAGES, f"live tree resolved {count} page(s), below the floor"
    assert abs(count - MEASURED_PAGE_COUNT) <= COUNT_TOLERANCE, (
        f"live tree resolved {count} page(s); the measured baseline is {MEASURED_PAGE_COUNT}. "
        "A drift this large usually means the DocFX glob translation is wrong, not that the docs moved."
    )
    assert resolved.source_globs, "source_globs must be retained for diagnostics"


def test_dropped_glob_raises_even_when_aggregate_clears_floor(
    synthetic_docs: Path, tmp_path: Path
) -> None:
    """A single dropped subtree reds the gate even though the union clears the floor.

    ``context/**.md`` alone resolves at or above the non-vacuity floor, so both the
    aggregate check (I-02) and any *per-entry* check pass — the two globs share one
    ``build.content`` entry. The empty ``nowhere/**.md`` glob is invisible to them;
    only the per-*glob* pre-exclusion guard catches that a declared subtree collapsed
    to zero (SC-003/SC-004).
    """
    dropped = _write_config(
        tmp_path, ["context/**.md", "nowhere/**.md"], exclude=["**/_*.md"], name="dropped.json"
    )

    # The populated glob alone clears the aggregate floor, so an aggregate-only
    # (or single-entry) check would report this configuration green.
    aggregate_only = resolve_published_pages(
        docs_root=synthetic_docs,
        docfx_config=_write_config(
            tmp_path, ["context/**.md"], exclude=["**/_*.md"], name="aggregate_only.json"
        ),
    )
    assert len(aggregate_only.pages) >= MINIMUM_EXPECTED_PAGES

    with pytest.raises(ValueError, match=r"nowhere/\*\*\.md"):
        resolve_published_pages(docs_root=synthetic_docs, docfx_config=dropped)


def test_would_have_caught_the_original_regression(tmp_path: Path) -> None:
    """The regression proof: the retired pre-move glob list is refused, not reported green.

    This is the test that matters. The retired list resolves 16 pages against the
    live tree — which is exactly what the old gate did while reporting green over
    the whole tree. Here it must raise.

    The per-glob pre-exclusion guard (FR-003) now refuses the list *even more*
    loudly than the aggregate floor did: the retired globs point at subtrees that
    the ``how-to/`` → ``guides/`` and ``reference/slash-commands`` → ``api/`` moves
    deleted, so the guard trips on the first dropped subtree (``tutorials/*.md``)
    and names it — the aggregate floor never gets a chance to run. Naming the
    specific vanished glob is a stronger diagnosis than "the union collapsed".
    """
    config = _write_config(tmp_path, RETIRED_PRE_MOVE_GLOBS, exclude=["**/_*.md"], name="retired.json")

    with pytest.raises(ValueError) as excinfo:
        resolve_published_pages(docs_root=LIVE_DOCS_ROOT, docfx_config=config)

    message = str(excinfo.value)
    assert "violates I-01" in message, message
    assert "tutorials/*.md" in message, "the failure must name the dropped glob (a vanished pre-move subtree)"
