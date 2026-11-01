"""Self-test for the frontmatter backfill tooling (FR-010 / NFR-004).

FR-010 is **derivation**, not a mechanical drift-close: the inventory carries
0 ``doc_status`` / 0 ``description`` / 0 ``related`` values, so the backfill
must *author* them from the live ``tag`` and the in-body link graph. These
tests pin the three load-bearing contracts:

* the ``tag -> doc_status`` mapping table is correct **per tag**, including the
  ``internal -> active|draft`` disambiguation signal (T065);
* the tool **carries** the inventory fields and **derives** ``doc_status`` onto
  a page, and is **idempotent** — re-rendering its own output is a no-op (T066);
* ``related:`` derivation emits **only resolvable** edges and flags the rest for
  WP12, never a dangling edge (T068).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.docs._inventory import (
    DivioType,
    PageInventoryEntry,
    VersionTag,
    load_inventory,
)
from scripts.docs.frontmatter_backfill import (
    TAG_DOC_STATUS,
    DocStatus,
    apply_backfill,
    build_backfill,
    derive_doc_status,
    derive_related,
    plan_backfill,
    render_page,
)

pytestmark = pytest.mark.architectural

# A fixed resolver so ``updated`` is deterministic in tests (no git dependency).
_STUB_UPDATED = "2026-06-27"


def _resolver(_rel: str) -> str:
    return _STUB_UPDATED


# --- T065: the tag -> doc_status mapping table -----------------------------


def test_published_tiers_map_through_the_table() -> None:
    """current/migration -> active, archival -> deprecated, supported -> active."""
    assert TAG_DOC_STATUS[VersionTag.CURRENT] is DocStatus.ACTIVE
    assert TAG_DOC_STATUS[VersionTag.MIGRATION] is DocStatus.ACTIVE
    assert TAG_DOC_STATUS[VersionTag.ARCHIVAL] is DocStatus.DEPRECATED
    assert TAG_DOC_STATUS[VersionTag.SUPPORTED] is DocStatus.ACTIVE


def test_derive_doc_status_per_published_tier() -> None:
    """``derive_doc_status`` returns the table value for each published tier."""
    assert derive_doc_status(VersionTag.CURRENT, current_target=True) is DocStatus.ACTIVE
    assert derive_doc_status(VersionTag.MIGRATION, current_target=False) is DocStatus.ACTIVE
    assert derive_doc_status(VersionTag.ARCHIVAL, current_target=False) is DocStatus.DEPRECATED


def test_internal_is_disambiguated_by_current_target_signal() -> None:
    """``internal`` -> active when a current target, draft otherwise (the signal)."""
    assert derive_doc_status(VersionTag.INTERNAL, current_target=True) is DocStatus.ACTIVE
    assert derive_doc_status(VersionTag.INTERNAL, current_target=False) is DocStatus.DRAFT
    # ``internal`` is deliberately NOT a static entry — its lifecycle is a
    # function of the signal, not of the tag alone.
    assert VersionTag.INTERNAL not in TAG_DOC_STATUS


# --- T066: carry inventory fields + idempotence ----------------------------


def _entry(
    path: str,
    *,
    tag: VersionTag,
    divio_type: DivioType = DivioType.REFERENCE,
    owning_workstream: str = "runtime",
    current_target: bool,
    notes: str | None = None,
) -> PageInventoryEntry:
    return PageInventoryEntry(
        path=path,
        tag=tag,
        divio_type=divio_type,
        owning_workstream=owning_workstream,
        current_target=current_target,
        notes=notes,
    )


def _write_page(repo: Path, rel: str, body: str = "# Heading\n") -> Path:
    page = repo / rel
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(f"---\ntitle: \"A page\"\n---\n\n{body}", encoding="utf-8")
    return page


def test_backfill_derives_status_and_carries_inventory_fields(tmp_path: Path) -> None:
    """doc_status is derived; version_tag/divio_type/owning_workstream are carried."""
    repo = tmp_path
    _write_page(repo, "docs/guides/lanes.md")
    entry = _entry(
        "docs/guides/lanes.md",
        tag=VersionTag.CURRENT,
        divio_type=DivioType.HOW_TO,
        owning_workstream="orchestration",
        current_target=True,
        notes="Lane allocation guide.",
    )

    backfill = build_backfill(
        entry, repo_root=repo, docs_root=repo / "docs", updated_resolver=_resolver
    )

    assert backfill.doc_status is DocStatus.ACTIVE
    assert backfill.version_tag is VersionTag.CURRENT
    assert backfill.divio_type is DivioType.HOW_TO
    assert backfill.owning_workstream == "orchestration"
    assert backfill.updated == _STUB_UPDATED
    assert backfill.notes == "Lane allocation guide."
    # The tool never invents a description — that is WP12's authoring step.
    assert backfill.description is None


def test_carried_fields_land_in_rendered_frontmatter(tmp_path: Path) -> None:
    """Rendering writes the derived/carried keys into the page frontmatter."""
    repo = tmp_path
    page = _write_page(repo, "docs/architecture/1.x/old.md")
    entry = _entry(
        "docs/architecture/1.x/old.md",
        tag=VersionTag.INTERNAL,
        divio_type=DivioType.EXPLANATION,
        owning_workstream="architecture",
        current_target=False,
    )
    backfill = build_backfill(
        entry, repo_root=repo, docs_root=repo / "docs", updated_resolver=_resolver
    )

    rendered = render_page(page.read_text(encoding="utf-8"), backfill)

    assert "doc_status: draft" in rendered  # internal + not current_target
    assert "version_tag: internal" in rendered
    assert "kind: Explanation" in rendered  # divio axis lives under `kind:` (#6931)
    assert "type:" not in rendered  # doc-kitty owns `type` (the section name)
    assert "owning_workstream: architecture" in rendered
    # ruamel quotes the date-shaped string; the value still lands verbatim.
    assert _STUB_UPDATED in rendered
    assert "# Heading" in rendered  # body preserved


def test_backfill_is_idempotent(tmp_path: Path) -> None:
    """Re-rendering an already-backfilled page reproduces it byte-for-byte."""
    repo = tmp_path
    page = _write_page(repo, "docs/guides/lanes.md")
    entry = _entry("docs/guides/lanes.md", tag=VersionTag.CURRENT, current_target=True)
    backfill = build_backfill(
        entry, repo_root=repo, docs_root=repo / "docs", updated_resolver=_resolver
    )

    once = render_page(page.read_text(encoding="utf-8"), backfill)
    twice = render_page(once, backfill)

    assert once == twice


def test_apply_backfill_is_a_noop_second_time(tmp_path: Path) -> None:
    """apply_backfill changes the page once, then reports no change (idempotent)."""
    repo = tmp_path
    page = _write_page(repo, "docs/guides/lanes.md")
    entry = _entry("docs/guides/lanes.md", tag=VersionTag.CURRENT, current_target=True)
    backfill = build_backfill(
        entry, repo_root=repo, docs_root=repo / "docs", updated_resolver=_resolver
    )

    assert apply_backfill(page, backfill) is True
    assert apply_backfill(page, backfill) is False


# --- T068: related derivation emits only resolvable edges ------------------


def test_related_derivation_emits_only_resolvable_edges(tmp_path: Path) -> None:
    """In-body links to existing docs pages become resolved related edges."""
    repo = tmp_path
    _write_page(repo, "docs/guides/target.md")
    body = (
        "See the [target](target.md) and the [missing one](nope.md).\n"
        "External [link](https://example.com/x.md) is ignored.\n"
    )
    source = _write_page(repo, "docs/guides/source.md", body=body)

    derivation = derive_related(source, repo_root=repo, docs_root=repo / "docs")

    assert derivation.resolved == ["docs/guides/target.md"]
    assert derivation.unresolved == ["nope.md"]


def test_related_derivation_ignores_self_and_anchors(tmp_path: Path) -> None:
    """A self-link and an anchor suffix do not create a spurious edge."""
    repo = tmp_path
    _write_page(repo, "docs/guides/target.md")
    body = (
        "Back to [self](source.md#section) and over to [t](target.md#top).\n"
    )
    source = _write_page(repo, "docs/guides/source.md", body=body)

    derivation = derive_related(source, repo_root=repo, docs_root=repo / "docs")

    assert derivation.resolved == ["docs/guides/target.md"]
    assert "source.md" not in derivation.unresolved


def test_resolved_related_edges_land_in_frontmatter(tmp_path: Path) -> None:
    """Derived resolvable edges are written to the page's ``related:`` list."""
    repo = tmp_path
    _write_page(repo, "docs/guides/target.md")
    source = _write_page(
        repo, "docs/guides/source.md", body="[t](target.md)\n"
    )
    entry = _entry("docs/guides/source.md", tag=VersionTag.CURRENT, current_target=True)
    backfill = build_backfill(
        entry, repo_root=repo, docs_root=repo / "docs", updated_resolver=_resolver
    )

    rendered = render_page(source.read_text(encoding="utf-8"), backfill)

    assert backfill.related == ["docs/guides/target.md"]
    assert "related:" in rendered
    assert "docs/guides/target.md" in rendered


# --- plan_backfill: end-to-end over a small inventory ----------------------


def _write_inventory(repo: Path, rows: list[str]) -> Path:
    inventory = repo / "inventory.yaml"
    inventory.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return inventory


def test_plan_backfill_walks_the_inventory(tmp_path: Path) -> None:
    """plan_backfill yields one PageBackfill per inventory row, status derived."""
    repo = tmp_path
    _write_page(repo, "docs/current.md")
    _write_page(repo, "docs/archive.md")
    inventory = _write_inventory(
        repo,
        [
            "- path: docs/current.md",
            "  tag: current",
            "  divio_type: reference",
            "  owning_workstream: runtime",
            "  current_target: true",
            "  notes: null",
            "- path: docs/archive.md",
            "  tag: archival",
            "  divio_type: none",
            "  owning_workstream: none",
            "  current_target: false",
            "  notes: null",
        ],
    )
    # Sanity: the inventory loads under the real loader.
    assert frozenset(e.path for e in load_inventory(inventory)) == frozenset(
        {"docs/current.md", "docs/archive.md"}
    )

    plan = plan_backfill(
        inventory_path=inventory,
        repo_root=repo,
        docs_root=repo / "docs",
        updated_resolver=_resolver,
    )

    statuses = {bf.path: bf.doc_status for bf in plan}
    assert statuses == {
        "docs/current.md": DocStatus.ACTIVE,
        "docs/archive.md": DocStatus.DEPRECATED,
    }
