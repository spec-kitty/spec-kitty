"""Each docs folder holds one index file (#6928, ADR 2026-10-31-1 D-1, D-7).

doc-kitty refuses a build where a folder holds both ``index.md`` and
``README.md`` (both resolve to the same route). The four folders that had both
(``adr/1.x``, ``adr/2.x``, ``adr/3.x``, ``architecture``) keep ``index.md`` while
DocFX deploys, and their old ``README.html`` URLs redirect to that index through
the standing moves ledger ``site/moves.yaml``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.docs.moves_ledger import (
    DEFAULT_MOVES_LEDGER,
    DEFAULT_URL_BASELINE,
    derive_redirect_map,
    load_baseline,
    load_moves,
)

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOCS = _REPO_ROOT / "docs"
_RESOLVED_FOLDERS = ("adr/1.x", "adr/2.x", "adr/3.x", "architecture")


def folders_with_two_index_files(root: Path) -> list[str]:
    """Folders under *root* that hold both ``index.md`` and ``README.md``."""
    return sorted(index.parent.relative_to(root).as_posix() for index in root.rglob("index.md") if (index.parent / "README.md").is_file())


def test_no_docs_folder_holds_two_index_files() -> None:
    assert len(list(_DOCS.rglob("index.md"))) >= 50  # non-vacuous: 60 today
    assert folders_with_two_index_files(_DOCS) == []


def test_helper_reports_a_folder_with_both_files(tmp_path: Path) -> None:
    """Positive control: the helper sees a collision when there is one."""
    (tmp_path / "both").mkdir()
    (tmp_path / "both" / "index.md").write_text("x", encoding="utf-8")
    (tmp_path / "both" / "README.md").write_text("x", encoding="utf-8")
    (tmp_path / "one").mkdir()
    (tmp_path / "one" / "index.md").write_text("x", encoding="utf-8")
    assert folders_with_two_index_files(tmp_path) == ["both"]


@pytest.mark.parametrize("folder", _RESOLVED_FOLDERS)
def test_readme_route_redirects_to_its_index(folder: str) -> None:
    mapping = derive_redirect_map(load_moves(DEFAULT_MOVES_LEDGER))
    assert mapping.get(f"{folder}/README.html") == f"{folder}/index.html"
    assert f"/{folder}/README.html" in load_baseline(DEFAULT_URL_BASELINE)
    assert not (_DOCS / folder / "README.md").exists()


def test_architecture_index_carries_the_landing_content() -> None:
    text = (_DOCS / "architecture" / "index.md").read_text(encoding="utf-8")
    for heading in (
        "## Boundary rule (single source of truth)",
        "## Living pages and frozen history",
        "### Decay rule (so the layout can't re-drift)",
        "## ADR locations",
        "## C4 model",
        "## Creating a new ADR",
        "## Page index",
    ):
        assert heading in text, heading
