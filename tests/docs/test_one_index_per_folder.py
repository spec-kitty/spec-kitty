"""Each docs folder holds one index file (#6928, ADR 2026-10-31-1 D-1, D-7).

doc-kitty refuses a build where a folder holds both ``index.md`` and
``README.md`` (both resolve to the same route). The four folders that had both
(``adr/1.x``, ``adr/2.x``, ``adr/3.x``, ``architecture``) kept ``index.md`` until
the README rename (#6939), which moved them back: ``README.md`` is their one index
again, and the ledger reads that later move as superseding the earlier one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.docs.moves_ledger import (
    DEFAULT_MOVES_LEDGER,
    DEFAULT_URL_BASELINE,
    collapse,
    load_baseline,
    load_moves,
)

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOCS = _REPO_ROOT / "docs"
_RESOLVED_FOLDERS = ("adr/1.x", "adr/2.x", "adr/3.x", "architecture")


@pytest.mark.parametrize("folder", _RESOLVED_FOLDERS)
def test_a_resolved_folder_is_back_on_its_readme(folder: str) -> None:
    """#6928 moved ``README -> index``; #6939 moved it back, so ``README.html`` is a live route again."""
    mapping = collapse(load_moves(DEFAULT_MOVES_LEDGER))
    assert f"/{folder}/README.html" not in mapping
    assert mapping.get(f"/{folder}/index.html") == f"/{folder}/README.html"
    assert f"/{folder}/README.html" in load_baseline(DEFAULT_URL_BASELINE)
    assert (_DOCS / folder / "README.md").is_file()
    assert not (_DOCS / folder / "index.md").exists()


def test_architecture_index_carries_the_landing_content() -> None:
    text = (_DOCS / "architecture" / "README.md").read_text(encoding="utf-8")
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
