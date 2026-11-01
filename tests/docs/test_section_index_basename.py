"""Ratchet: every docs section landing page is ``README.md``, never ``index.md``.

ADR ``2026-10-31-1`` D-1 makes ``README.md`` the section landing basename for the
doc-kitty site (``indexBasename: 'README'``), which keeps DocFX's ``dir/index.html``
output URL. Issue #6939 renamed the 60 legacy ``docs/**/index.md`` pages; this module is
the guard that stops the old basename from creeping back one section at a time.

The live assertion walks the real ``docs/`` tree. The positive control runs the same
walk over a synthetic tree that DOES contain an ``index.md``, so a walk that stops
reporting cannot make the live assertion pass vacuously.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

#: Repo root: tests/docs/<this file> -> parents[2].
_REPO_ROOT = Path(__file__).resolve().parents[2]

#: The docs root the guard walks.
_DOCS_ROOT = _REPO_ROOT / "docs"

#: The retired section landing basename.
_RETIRED_BASENAME = "index.md"


def stray_section_indexes(docs_root: Path) -> list[str]:
    """The ``index.md`` pages under *docs_root*, repo-relative and sorted.

    A section landing page is ``README.md`` (issue #6939); any ``index.md`` under
    ``docs/`` is a page that escaped the rename. Returns an empty list for a clean
    tree.
    """
    if not docs_root.is_dir():
        return []
    return sorted(path.relative_to(docs_root.parent).as_posix() for path in docs_root.rglob(_RETIRED_BASENAME) if path.is_file())


def test_no_index_md_remains_under_docs() -> None:
    """The real tree carries no section ``index.md`` (issue #6939)."""
    assert _DOCS_ROOT.is_dir(), f"docs root not found at {_DOCS_ROOT}"

    stray = stray_section_indexes(_DOCS_ROOT)

    assert stray == [], (
        "section landing pages must be README.md (issue #6939, ADR 2026-10-31-1 D-1); "
        f"these pages still use the retired {_RETIRED_BASENAME} basename:\n  " + "\n  ".join(stray)
    )


def test_the_guard_catches_a_reintroduced_index_md(tmp_path: Path) -> None:
    """Positive control: the same walk reports a reintroduced ``index.md``."""
    docs = tmp_path / "docs"
    (docs / "guides").mkdir(parents=True)
    (docs / "guides" / "README.md").write_text("# Guides\n", encoding="utf-8")
    (docs / "guides" / "how-to").mkdir()
    (docs / "guides" / "how-to" / "README.md").write_text("# How-to\n", encoding="utf-8")
    (docs / "guides" / "how-to" / _RETIRED_BASENAME).write_text("# How-to (retired basename)\n", encoding="utf-8")

    assert stray_section_indexes(docs) == ["docs/guides/how-to/index.md"]


def test_a_clean_tree_reports_nothing(tmp_path: Path) -> None:
    """The negative half: a README-only tree is clean, so the guard has two sides."""
    docs = tmp_path / "docs"
    (docs / "guides").mkdir(parents=True)
    (docs / "guides" / "README.md").write_text("# Guides\n", encoding="utf-8")

    assert stray_section_indexes(docs) == []
