"""The published living pages and the text a page publishes: one door for the docs gates (#7520).

A *living page* is a page the doc-kitty site publishes (``_dockitty_contract.published_pages``)
outside the history folders (``_dockitty_contract.HISTORY_PREFIXES``). Both the retired-surface
gate (``scripts/docs/retired_surface_gate.py``) and the staleness inventory
(``scripts/docs/staleness_audit.py``) read pages through here, so neither depends on the other.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

# Runnable bare: resolve `scripts.*` from the script, not the cwd.
_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.docs._dockitty_contract import HISTORY_PREFIXES, published_pages  # noqa: E402  (sys.path bootstrap above)
from scripts.docs._inventory import parse_frontmatter  # noqa: E402  (sys.path bootstrap above)

__all__ = ["living_pages", "published_text"]

#: The frontmatter keys the site publishes on the page (doc-kitty renders both).
_PUBLISHED_KEYS: Final[tuple[str, ...]] = ("title", "description")
_FENCE_LINE: Final[str] = "---"


def published_text(text: str) -> str:
    """The text a page publishes, line for line: its ``title`` and ``description`` and its body.

    The frontmatter is read with the YAML loader, so a folded or continued value
    (``description: >-``) is whole; it is placed on its key's line. Every other frontmatter
    line is blanked, not removed, so line numbers stay file line numbers. The gate and the
    inventory both scan this text.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FENCE_LINE:
        return text
    closing = next((index for index in range(1, len(lines)) if lines[index].strip() == _FENCE_LINE), None)
    if closing is None:
        return text
    values = parse_frontmatter(text)
    kept = [""] * closing
    for index in range(1, closing):
        key = lines[index].split(":", 1)[0]
        if key in _PUBLISHED_KEYS and isinstance(values.get(key), str):
            kept[index] = " ".join(str(values[key]).split())
    return "\n".join([*kept, *lines[closing:]])


def living_pages(docs_root: Path) -> list[str]:
    """The published living pages under *docs_root*, relative to it and sorted."""
    return sorted(page for page in published_pages(docs_root) if not page.startswith(HISTORY_PREFIXES))
