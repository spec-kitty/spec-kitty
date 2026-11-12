"""Search metadata for the published docsite pages (#6943; ADR 2026-10-31-1 D-7, D-8).

The published set is the doc-kitty site's: :func:`published_pages` in
``scripts/docs/_dockitty_contract.py``, the one authority the built-site check and
the redirect generator read too. It replaced a second answer, the legacy site
configuration, which was retired with that site (#6943). Every published page
carries a ``title`` and a ``description`` within the contract's band: at most
:data:`DESCRIPTION_MAX` characters (an error in doc-kitty's frontmatter gate) and,
held stricter here, at least :data:`DESCRIPTION_SOFT_MIN` (a warning there).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.docs._dockitty_contract import DESCRIPTION_MAX, DESCRIPTION_SOFT_MIN, published_pages
from scripts.docs._inventory import parse_frontmatter

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs"
SITE_PUBLIC = REPO_ROOT / "site" / "public"

#: Non-vacuity floor: 631 pages were published when the set moved to the contract (#6943).
MINIMUM_PUBLISHED_PAGES = 500

pytestmark = [pytest.mark.unit, pytest.mark.fast]


FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


def _published_markdown_files() -> list[Path]:
    """Every published source page, per the doc-kitty contract."""
    return sorted(DOCS_DIR / rel for rel in published_pages(DOCS_DIR))


def _frontmatter(path: Path) -> dict[str, str]:
    """Parse ``path``'s front matter with the repository's canonical YAML reader.

    A hand-rolled ``split(":", 1)`` loop once kept the quotes on ``description: '…'``
    (two phantom characters) and read past a ``#`` comment in an unquoted scalar. The
    site parses real YAML, so the check must too.
    """
    text = path.read_text(encoding="utf-8")
    assert FRONTMATTER_RE.match(text), f"{path.relative_to(REPO_ROOT)} must start with YAML front matter"
    return {key: value for key, value in parse_frontmatter(text).items() if isinstance(key, str) and isinstance(value, str)}


def metadata_problem(metadata: dict[str, str]) -> str | None:
    """Why *metadata* fails the published-page rule, or ``None`` when it passes."""
    if not metadata.get("title"):
        return "missing title"
    description = metadata.get("description")
    if not description:
        return "missing description"
    if not DESCRIPTION_SOFT_MIN <= len(description) <= DESCRIPTION_MAX:
        return f"description length is off: {len(description)} (band {DESCRIPTION_SOFT_MIN}-{DESCRIPTION_MAX})"
    return None


def test_the_published_set_is_not_vacuous() -> None:
    assert len(_published_markdown_files()) >= MINIMUM_PUBLISHED_PAGES


@pytest.mark.parametrize("path", _published_markdown_files(), ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_published_pages_have_title_and_description(path: Path) -> None:
    problem = metadata_problem(_frontmatter(path))
    assert problem is None, f"{path.relative_to(REPO_ROOT)}: {problem}"


@pytest.mark.parametrize(
    ("metadata", "problem"),
    [
        ({"description": "d" * 100}, "missing title"),
        ({"title": "T"}, "missing description"),
        ({"title": "T", "description": "d" * (DESCRIPTION_SOFT_MIN - 1)}, "description length is off"),
        ({"title": "T", "description": "d" * (DESCRIPTION_MAX + 1)}, "description length is off"),
    ],
)
def test_the_rule_rejects_each_defect(metadata: dict[str, str], problem: str) -> None:
    found = metadata_problem(metadata)
    assert found is not None and found.startswith(problem)


def test_the_rule_accepts_a_described_page() -> None:
    """Positive control on the same rule: in-band at both ends."""
    assert metadata_problem({"title": "T", "description": "d" * DESCRIPTION_SOFT_MIN}) is None
    assert metadata_problem({"title": "T", "description": "d" * DESCRIPTION_MAX}) is None


def test_a_draft_page_without_a_description_is_not_in_the_published_set(tmp_path: Path) -> None:
    """The set is the contract's: a draft is not published, an active page is."""
    (tmp_path / "guides").mkdir()
    (tmp_path / "guides" / "wip.md").write_text("---\ntitle: WIP\ndoc_status: draft\n---\n", encoding="utf-8")
    (tmp_path / "guides" / "live.md").write_text("---\ntitle: Live\ndoc_status: active\n---\n", encoding="utf-8")
    assert published_pages(tmp_path) == frozenset({"guides/live.md"})


def test_static_site_files_exist() -> None:
    """The custom domain and robots file ship from the site's ``public/`` folder."""
    for name in ("robots.txt", "CNAME"):
        assert (SITE_PUBLIC / name).is_file(), f"Missing site/public/{name}"
    assert (SITE_PUBLIC / "CNAME").read_text(encoding="utf-8").strip() == "docs.spec-kitty.ai"
