"""Versioned docs integrity checks for archived 1.x and 2.x tracks.

Note: bare-relative link resolution is now owned by the unified gate in
:mod:`tests.docs.test_relative_link_fixer` (WP02/T027, FR-005).  The
hand-rolled ``test_versioned_docs_relative_links_resolve`` that previously
lived here has been retired — it is superseded by ``check_dead_body_links``
operating across the full ``docs/`` tree, including ``docs/archive/``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs"
# The archived 1.x/2.x tracks were rehomed docs/archive/ -> docs/changelog/ by the
# common-docs-convergence mission (WP12); the versioned-docs integrity checks follow.
ARCHIVE_DIR = DOCS_DIR / "changelog"
TRACKS = ("1x", "2x")

FORBIDDEN_TERMS = (
    "saas",
    "auth0",
    "nango",
    "authentication",
    "login",
    "dashboard",
    "websocket",
)


def test_versioned_docs_required_files_exist() -> None:
    expected = [
        DOCS_DIR / "README.md",
        DOCS_DIR / "toc.yml",
        ARCHIVE_DIR / "README.md",
        ARCHIVE_DIR / "toc.yml",
        ARCHIVE_DIR / "1x" / "README.md",
        ARCHIVE_DIR / "1x" / "toc.yml",
        ARCHIVE_DIR / "2x" / "README.md",
        ARCHIVE_DIR / "2x" / "toc.yml",
    ]
    missing = [str(path.relative_to(REPO_ROOT)) for path in expected if not path.is_file()]
    assert not missing, f"Missing required versioned docs files: {missing}"


def test_versioned_docs_exclude_out_of_scope_terms() -> None:
    failures: list[str] = []
    for track in TRACKS:
        for doc_path in sorted((ARCHIVE_DIR / track).glob("*.md")):
            text = doc_path.read_text(encoding="utf-8").lower()
            for term in FORBIDDEN_TERMS:
                if term in text:
                    failures.append(f"{doc_path.relative_to(REPO_ROOT)} contains forbidden term: '{term}'")
    assert not failures, "\n".join(failures)
