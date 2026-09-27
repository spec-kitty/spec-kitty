"""Tests for ``scripts/docs/freshen_adr_inventory.py``.

The tool freshens BOTH ADR indexes the docs-freshness gate enforces:
1. the generated page-inventory lockfile (regenerated from frontmatter), and
2. the era ``README.md`` ADR table (a date-ordered, idempotent row insert).

Fixtures are production-shaped: a real ``docs/adr/3.x/`` tree with genuine
ADR frontmatter, a real era README carrying a ``| Date | Title |`` index
table, and a real committed inventory lockfile rendered by the canonical
generator — so a run exercises the same code path CI does.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from scripts.docs.freshen_adr_inventory import (
    DEFAULT_INVENTORY_PATH,
    detect_missing_adrs,
    freshen,
    main,
)
from scripts.docs.inventory_lockfile import (
    generate_inventory,
    render_lockfile,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]

pytestmark = [pytest.mark.fast]


# --------------------------------------------------------------------------- #
# Fixture builders
# --------------------------------------------------------------------------- #

_README_TEMPLATE = dedent(
    """\
    # 3.x ADRs

    Architectural Decision Records for the 3.x track.

    ## Index

    | Date | Title |
    |---|---|
    | 2026-04-03 | [Execution lanes own worktrees](2026-04-03-1-execution-lanes.md) |
    | 2026-05-16 | [Doctrine layer merge semantics](2026-05-16-1-doctrine-merge.md) |
    | 2026-06-26 | [Single-authority seam](2026-06-26-1-single-authority-seam.md) |
    """
)

_README_REDIRECT_TEMPLATE = dedent(
    """\
    ---
    title: 3.x ADRs
    description: Redirect to the canonical era index.
    doc_status: active
    updated: '2026-08-10'
    ---
    This page has moved to [index.md](index.md).
    """
)

_LEGACY_INDEX_TEMPLATE = dedent(
    """\
    ---
    title: 1.x ADRs
    description: Index and era history for archived 1.x decisions.
    doc_status: active
    updated: '2026-08-10'
    ---

    # 1.x ADRs

    Architectural Decision Records for the legacy 1.x track.

    ## Era history

    These decisions are retained as history. This landing page intentionally
    has no maintained ADR table.

    ## Source of Truth

    This folder is canonical for 1.x decisions.
    """
)


def _adr(title: str, date: str, *, body: str = "Decision body.") -> str:
    return dedent(
        f"""\
        ---
        title: {title}
        status: Accepted
        date: '{date}'
        ---

        ## Context

        {body}
        """
    )


def _write_docs_tree(repo_root: Path) -> Path:
    """Stage a realistic docs tree; return the docs root."""
    docs_root = repo_root / "docs"
    era = docs_root / "adr" / "3.x"
    era.mkdir(parents=True)

    (era / "README.md").write_text(_README_TEMPLATE, encoding="utf-8")

    # Pre-existing ADRs that already have README rows.
    (era / "2026-04-03-1-execution-lanes.md").write_text(_adr("Execution lanes own worktrees", "2026-04-03"), encoding="utf-8")
    (era / "2026-05-16-1-doctrine-merge.md").write_text(_adr("Doctrine layer merge semantics", "2026-05-16"), encoding="utf-8")
    (era / "2026-06-26-1-single-authority-seam.md").write_text(_adr("Single-authority seam", "2026-06-26"), encoding="utf-8")

    # A non-ADR doc so the inventory has more than ADRs in it.
    (docs_root / "index.md").write_text(_adr("Docs home", "2026-01-01"), encoding="utf-8")

    _write_inventory(repo_root, docs_root)
    return docs_root


def _write_inventory(repo_root: Path, docs_root: Path) -> None:
    """Render + commit an inventory matching the current tree (no drift)."""
    inv = repo_root / DEFAULT_INVENTORY_PATH
    inv.parent.mkdir(parents=True, exist_ok=True)
    inv.write_text(
        render_lockfile(generate_inventory(docs_root, repo_root=repo_root)),
        encoding="utf-8",
    )


def _read_readme(docs_root: Path) -> str:
    return (docs_root / "adr" / "3.x" / "README.md").read_text(encoding="utf-8")


def _table_rows(readme_text: str) -> list[str]:
    """Return the ADR table's data rows (between separator and blank/EOF)."""
    rows: list[str] = []
    in_table = False
    for line in readme_text.splitlines():
        if line.startswith("|---"):
            in_table = True
            continue
        if in_table:
            if line.startswith("|"):
                rows.append(line)
            else:
                break
    return rows


# --------------------------------------------------------------------------- #
# 1. Adding a new ADR surfaces both rows
# --------------------------------------------------------------------------- #


def test_new_adr_gets_inventory_and_readme_rows(tmp_path: Path) -> None:
    repo_root = tmp_path
    docs_root = _write_docs_tree(repo_root)
    new_adr = docs_root / "adr" / "3.x" / "2026-06-30-1-new-thing.md"
    new_adr.write_text(_adr("A Brand New Thing", "2026-06-30"), encoding="utf-8")

    result = freshen([new_adr], docs_root=docs_root, repo_root=repo_root, check=False)

    # README row present with the right date/title/link.
    readme = _read_readme(docs_root)
    assert "| 2026-06-30 | [A Brand New Thing](2026-06-30-1-new-thing.md) |" in readme
    assert "2026-06-30-1-new-thing.md" in result.readme_rows_added

    # Inventory row present (path appears in the regenerated lockfile).
    inv = (repo_root / DEFAULT_INVENTORY_PATH).read_text(encoding="utf-8")
    assert "docs/adr/3.x/2026-06-30-1-new-thing.md" in inv
    assert result.inventory_written is True


def test_canonical_index_is_used_when_readme_is_redirect(tmp_path: Path) -> None:
    repo_root = tmp_path
    docs_root = _write_docs_tree(repo_root)
    era = docs_root / "adr" / "3.x"
    index = era / "index.md"
    index.write_text(_README_TEMPLATE, encoding="utf-8")
    readme = era / "README.md"
    readme.write_text(_README_REDIRECT_TEMPLATE, encoding="utf-8")
    redirect_before = readme.read_text(encoding="utf-8")
    new_adr = era / "2026-06-30-1-new-thing.md"
    new_adr.write_text(_adr("A Brand New Thing", "2026-06-30"), encoding="utf-8")
    assert new_adr in detect_missing_adrs(docs_root)

    result = freshen([new_adr], docs_root=docs_root, repo_root=repo_root, check=False)

    assert new_adr.name in result.readme_rows_added
    assert f"]({new_adr.name})" in index.read_text(encoding="utf-8")
    assert readme.read_text(encoding="utf-8") == redirect_before
    check_result = freshen([new_adr], docs_root=docs_root, repo_root=repo_root, check=True)
    assert check_result.is_clean
    assert new_adr not in detect_missing_adrs(docs_root)


def test_all_refuses_malformed_canonical_index(tmp_path: Path) -> None:
    repo_root = tmp_path
    docs_root = _write_docs_tree(repo_root)
    era = docs_root / "adr" / "3.x"
    (era / "index.md").write_text("# 3.x ADRs\n\n## Index\n\nMissing table.\n", encoding="utf-8")
    readme = era / "README.md"
    readme.write_text(_README_REDIRECT_TEMPLATE, encoding="utf-8")
    redirect_before = readme.read_text(encoding="utf-8")

    exit_code = main(["--all", "--repo-root", str(repo_root), "--docs-root", str(docs_root)])

    assert exit_code == 2
    assert readme.read_text(encoding="utf-8") == redirect_before


def test_explicit_check_refuses_malformed_declared_index(tmp_path: Path) -> None:
    repo_root = tmp_path
    docs_root = _write_docs_tree(repo_root)
    era = docs_root / "adr" / "3.x"
    (era / "index.md").write_text("# 3.x ADRs\n\n## Index\n\nMissing table.\n", encoding="utf-8")
    (era / "README.md").write_text(_README_REDIRECT_TEMPLATE, encoding="utf-8")
    _write_inventory(repo_root, docs_root)

    exit_code = main(
        [
            str(era / "2026-04-03-1-execution-lanes.md"),
            "--check",
            "--repo-root",
            str(repo_root),
            "--docs-root",
            str(docs_root),
        ]
    )

    assert exit_code == 2


def test_all_skips_production_shaped_legacy_tableless_index(tmp_path: Path) -> None:
    repo_root = tmp_path
    docs_root = _write_docs_tree(repo_root)
    era = docs_root / "adr" / "3.x"
    readme = era / "README.md"
    readme.write_text(_README_REDIRECT_TEMPLATE, encoding="utf-8")
    (era / "index.md").write_text(_LEGACY_INDEX_TEMPLATE, encoding="utf-8")
    _write_inventory(repo_root, docs_root)

    assert detect_missing_adrs(docs_root) == []
    assert main(["--all", "--repo-root", str(repo_root), "--docs-root", str(docs_root)]) == 0
    assert (
        main(
            [
                "--all",
                "--check",
                "--repo-root",
                str(repo_root),
                "--docs-root",
                str(docs_root),
            ]
        )
        == 0
    )


# --------------------------------------------------------------------------- #
# 2. Idempotency
# --------------------------------------------------------------------------- #


def test_running_twice_is_idempotent(tmp_path: Path) -> None:
    repo_root = tmp_path
    docs_root = _write_docs_tree(repo_root)
    new_adr = docs_root / "adr" / "3.x" / "2026-06-30-1-new-thing.md"
    new_adr.write_text(_adr("A Brand New Thing", "2026-06-30"), encoding="utf-8")

    freshen([new_adr], docs_root=docs_root, repo_root=repo_root, check=False)
    first = _read_readme(docs_root)

    second_result = freshen([new_adr], docs_root=docs_root, repo_root=repo_root, check=False)
    second = _read_readme(docs_root)

    assert first == second  # no duplicate row / no second change
    assert second_result.readme_rows_added == ()
    assert second_result.inventory_written is False
    # Exactly one row references the basename.
    assert second.count("](2026-06-30-1-new-thing.md)") == 1


# --------------------------------------------------------------------------- #
# 3. --check exit codes
# --------------------------------------------------------------------------- #


def test_check_nonzero_when_readme_row_missing(tmp_path: Path) -> None:
    repo_root = tmp_path
    docs_root = _write_docs_tree(repo_root)
    new_adr = docs_root / "adr" / "3.x" / "2026-06-30-1-new-thing.md"
    new_adr.write_text(_adr("A Brand New Thing", "2026-06-30"), encoding="utf-8")
    # Regenerate inventory so ONLY the README row is missing (isolate the cause).
    _write_inventory(repo_root, docs_root)

    exit_code = main(
        [
            str(new_adr),
            "--check",
            "--repo-root",
            str(repo_root),
            "--docs-root",
            str(docs_root),
        ]
    )
    assert exit_code == 1


def test_check_nonzero_when_inventory_stale(tmp_path: Path) -> None:
    repo_root = tmp_path
    docs_root = _write_docs_tree(repo_root)
    # Add an ADR + its README row but leave the inventory stale.
    new_adr = docs_root / "adr" / "3.x" / "2026-06-30-1-new-thing.md"
    new_adr.write_text(_adr("A Brand New Thing", "2026-06-30"), encoding="utf-8")
    freshen([new_adr], docs_root=docs_root, repo_root=repo_root, check=False)
    # Now dirty the tree with another doc so the committed inventory is stale.
    (docs_root / "extra.md").write_text(_adr("Extra", "2026-02-02"), encoding="utf-8")

    exit_code = main(
        [
            str(new_adr),
            "--check",
            "--repo-root",
            str(repo_root),
            "--docs-root",
            str(docs_root),
        ]
    )
    assert exit_code == 1


def test_check_zero_when_clean(tmp_path: Path) -> None:
    repo_root = tmp_path
    docs_root = _write_docs_tree(repo_root)

    exit_code = main(
        [
            "--check",
            "--repo-root",
            str(repo_root),
            "--docs-root",
            str(docs_root),
        ]
    )
    assert exit_code == 0


# --------------------------------------------------------------------------- #
# 4. --all auto-detects README-missing ADRs
# --------------------------------------------------------------------------- #


def test_all_detects_and_adds_missing_row(tmp_path: Path) -> None:
    repo_root = tmp_path
    docs_root = _write_docs_tree(repo_root)
    orphan = docs_root / "adr" / "3.x" / "2026-06-29-1-orphan.md"
    orphan.write_text(_adr("Orphan ADR", "2026-06-29"), encoding="utf-8")

    assert orphan in detect_missing_adrs(docs_root)

    exit_code = main(["--all", "--repo-root", str(repo_root), "--docs-root", str(docs_root)])
    assert exit_code == 0

    readme = _read_readme(docs_root)
    assert "| 2026-06-29 | [Orphan ADR](2026-06-29-1-orphan.md) |" in readme
    assert detect_missing_adrs(docs_root) == []


# --------------------------------------------------------------------------- #
# 5. Title normalization
# --------------------------------------------------------------------------- #


def test_adr_prefix_stripped_from_title(tmp_path: Path) -> None:
    repo_root = tmp_path
    docs_root = _write_docs_tree(repo_root)
    adr = docs_root / "adr" / "3.x" / "2026-06-30-1-prefixed.md"
    adr.write_text(_adr("'ADR: Foo Bar'", "2026-06-30"), encoding="utf-8")

    freshen([adr], docs_root=docs_root, repo_root=repo_root, check=False)

    readme = _read_readme(docs_root)
    assert "| 2026-06-30 | [Foo Bar](2026-06-30-1-prefixed.md) |" in readme
    assert "ADR: Foo Bar" not in readme


def test_folded_multiline_title_collapses(tmp_path: Path) -> None:
    repo_root = tmp_path
    docs_root = _write_docs_tree(repo_root)
    adr = docs_root / "adr" / "3.x" / "2026-06-30-1-folded.md"
    # A single-quoted YAML scalar folded across two lines (real ADR shape).
    adr.write_text(
        "---\n"
        "title: 'ADR: Single-Authority Seam + Call-Site Gate for Resolution\n"
        "  Boundaries (Phase 1)'\n"
        "status: Accepted\n"
        "date: '2026-06-30'\n"
        "---\n\n## Context\n\nBody.\n",
        encoding="utf-8",
    )

    freshen([adr], docs_root=docs_root, repo_root=repo_root, check=False)

    readme = _read_readme(docs_root)
    assert "| 2026-06-30 | [Single-Authority Seam + Call-Site Gate for Resolution Boundaries (Phase 1)](2026-06-30-1-folded.md) |" in readme


# --------------------------------------------------------------------------- #
# 6. Date-ordered insertion
# --------------------------------------------------------------------------- #


def test_midrange_date_inserts_between_neighbours(tmp_path: Path) -> None:
    repo_root = tmp_path
    docs_root = _write_docs_tree(repo_root)
    # Existing dates: 2026-04-03, 2026-05-16, 2026-06-26. Insert 2026-05-20.
    adr = docs_root / "adr" / "3.x" / "2026-05-20-1-midrange.md"
    adr.write_text(_adr("Midrange Decision", "2026-05-20"), encoding="utf-8")

    freshen([adr], docs_root=docs_root, repo_root=repo_root, check=False)

    rows = _table_rows(_read_readme(docs_root))
    dates = [row.split("|")[1].strip() for row in rows]
    assert dates == sorted(dates)  # table stays ascending
    idx = dates.index("2026-05-20")
    assert dates[idx - 1] == "2026-05-16"
    assert dates[idx + 1] == "2026-06-26"


# --------------------------------------------------------------------------- #
# 7. Path-escape safety (Copilot review: _era_readme_for must validate that the
#    ADR lives INSIDE docs_root, not merely that dir names read `adr/<era>`).
# --------------------------------------------------------------------------- #


def test_out_of_tree_adr_is_rejected_and_edits_nothing(tmp_path: Path) -> None:
    repo_root = tmp_path
    docs_root = _write_docs_tree(repo_root)
    # A decoy `adr/3.x/` tree OUTSIDE docs_root — the `<tmpdir>/adr/3.x/foo.md`
    # shape the review flagged as destructively editable.
    outside = repo_root / "outside" / "adr" / "3.x"
    outside.mkdir(parents=True)
    outside_readme = outside / "README.md"
    outside_readme.write_text(_README_TEMPLATE, encoding="utf-8")
    decoy = outside / "2026-06-30-1-decoy.md"
    decoy.write_text(_adr("Decoy", "2026-06-30"), encoding="utf-8")
    before = outside_readme.read_text(encoding="utf-8")

    exit_code = main([str(decoy), "--repo-root", str(repo_root), "--docs-root", str(docs_root)])

    assert exit_code == 2  # FreshenError: path escapes docs_root
    assert outside_readme.read_text(encoding="utf-8") == before  # untouched


# --------------------------------------------------------------------------- #
# 8. Prose-link false-positive (Copilot review: the idempotency check must be
#    table-scoped — a link in README prose must not count as "already in the
#    table" for either write-mode or --check).
# --------------------------------------------------------------------------- #


def _readme_prose_links(basename: str) -> str:
    """The full index table, plus a prose link to ``basename`` ABOVE it.

    The table itself does NOT contain a row for ``basename`` — only prose links
    it. A basename-anywhere check would wrongly treat it as already present.
    """
    return dedent(
        f"""\
        # 3.x ADRs

        Architectural Decision Records for the 3.x track. Background for the new
        work lives in [the brand new thing]({basename}).

        ## Index

        | Date | Title |
        |---|---|
        | 2026-04-03 | [Execution lanes own worktrees](2026-04-03-1-execution-lanes.md) |
        | 2026-05-16 | [Doctrine layer merge semantics](2026-05-16-1-doctrine-merge.md) |
        | 2026-06-26 | [Single-authority seam](2026-06-26-1-single-authority-seam.md) |
        """
    )


def test_prose_link_does_not_block_table_row_insert(tmp_path: Path) -> None:
    repo_root = tmp_path
    docs_root = _write_docs_tree(repo_root)
    basename = "2026-06-30-1-new-thing.md"
    (docs_root / "adr" / "3.x" / "README.md").write_text(_readme_prose_links(basename), encoding="utf-8")
    new_adr = docs_root / "adr" / "3.x" / basename
    new_adr.write_text(_adr("A Brand New Thing", "2026-06-30"), encoding="utf-8")

    result = freshen([new_adr], docs_root=docs_root, repo_root=repo_root, check=False)

    # The prose link must NOT suppress the table-row insert.
    assert basename in result.readme_rows_added
    rows = _table_rows(_read_readme(docs_root))
    assert any(f"]({basename})" in row for row in rows)


def test_check_reports_missing_when_only_prose_links_adr(tmp_path: Path) -> None:
    repo_root = tmp_path
    docs_root = _write_docs_tree(repo_root)
    basename = "2026-06-30-1-new-thing.md"
    (docs_root / "adr" / "3.x" / "README.md").write_text(_readme_prose_links(basename), encoding="utf-8")
    new_adr = docs_root / "adr" / "3.x" / basename
    new_adr.write_text(_adr("A Brand New Thing", "2026-06-30"), encoding="utf-8")
    _write_inventory(repo_root, docs_root)  # isolate: only the README row is at issue

    # Table-aware detection must still see it as missing (not prose-fooled) — and
    # --check must agree with write-mode.
    assert new_adr in detect_missing_adrs(docs_root)
    exit_code = main(
        [
            str(new_adr),
            "--check",
            "--repo-root",
            str(repo_root),
            "--docs-root",
            str(docs_root),
        ]
    )
    assert exit_code == 1
