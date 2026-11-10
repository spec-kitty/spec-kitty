"""The ``llms-content`` surface of the built-site check (#6934; ADR 2026-10-31-1 D-8, D-9).

doc-kitty generates ``llms.txt`` (``site/src/pages/llms.txt.ts``, a wrapper that adds the
version stance) and the agent index (``site/src/pages/api/index.json.ts``). This surface
checks what the built files must hold, beyond the unpublished routes the ``llms`` and
``agent-index`` surfaces of ``site_built_check.py`` already report:

* ``llms.txt`` exists and carries :data:`~scripts.docs._dockitty_contract.LLMS_STANCE`
  exactly (``stance``);
* it lists no route of a section whose ``feeds`` in ``docs/_meta/sections.yaml`` leave
  out ``llms`` (``plans``: sitemap only); an absent ``feeds`` feeds every surface, as
  doc-kitty's ``feedsSurface`` reads it;
* the agent index ``api/index.json`` exists, so the machine-index line doc-kitty always
  prints in ``llms.txt`` resolves (spec-kitty/doc-kitty#312).

Standard library only, like ``site_built_check.py``: a narrow reader of the section
registry, not a YAML parser.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Final

from scripts.docs._dockitty_contract import LLMS_STANCE

if TYPE_CHECKING:
    from scripts.docs.site_built_check import Finding

__all__ = ["SECTIONS_YAML", "SURFACE", "findings", "restricted_sections", "surface"]

#: The surface name the findings carry (the key in ``site_built_check.SURFACES``).
SURFACE: Final[str] = "llms-content"

#: The section registry the site is built with.
SECTIONS_YAML: Final[Path] = Path(__file__).resolve().parents[2] / "docs" / "_meta" / "sections.yaml"

_LLMS_TXT: Final[str] = "llms.txt"
_AGENT_INDEX: Final[str] = "api/index.json"
_FEED: Final[str] = "llms"
_URL: Final[re.Pattern[str]] = re.compile(r"https?://[^\s)\]>\"'`]+")
_ENTRY: Final[re.Pattern[str]] = re.compile(r"^\s*-\s+id:\s*(?P<id>[^\s#]+)")
_KEY: Final[re.Pattern[str]] = re.compile(r"^\s+(?P<key>[a-z_]+):\s*(?P<value>[^#]*?)\s*(?:#.*)?$")
_ITEM: Final[re.Pattern[str]] = re.compile(r"^\s+-\s+(?P<value>[^\s#]+)")


def _inline_list(value: str) -> list[str]:
    return [item.strip().strip("'\"") for item in value.strip("[]").split(",") if item.strip()]


def restricted_sections(sections_yaml: Path, feed: str = _FEED) -> frozenset[str]:
    """The ids of the sections whose ``feeds`` are given and leave out *feed*.

    Reads ``feeds`` in flow form (``feeds: [sitemap]``) or block form (one ``- item``
    per line). A section without ``feeds`` feeds every surface, so it is never restricted.
    """
    feeds: dict[str, list[str]] = {}
    section: str | None = None
    in_block = False
    for line in sections_yaml.read_text(encoding="utf-8").splitlines():
        entry = _ENTRY.match(line)
        if entry:
            section, in_block = entry["id"].strip("'\""), False
            continue
        item = _ITEM.match(line) if in_block else None
        if item and section is not None:
            feeds[section].append(item["value"].strip("'\""))
            continue
        key = _KEY.match(line)
        in_block = False
        if key and key["key"] == "feeds" and section is not None:
            feeds[section] = _inline_list(key["value"])
            in_block = not key["value"]
    return frozenset(name for name, items in feeds.items() if feed not in items)


def _section_of(route: str) -> str:
    return route.strip("/").split("/", 1)[0]


def findings(dist: Path, *, sections: Path, stance: str) -> Iterator[Finding]:
    """Every ``llms-content`` finding of the built site at *dist*.

    *sections* is the section registry the site was built with; *stance* is the block
    ``llms.txt`` must carry verbatim.
    """
    from scripts.docs.site_built_check import Finding, normalise_url  # noqa: PLC0415  (site_built_check registers this surface; a top-level import is a cycle)

    if not (dist / _AGENT_INDEX).is_file():
        yield Finding(SURFACE, "missing", f"{_AGENT_INDEX}: the agent index llms.txt names is not built")
    path = dist / _LLMS_TXT
    if not path.is_file():
        yield Finding(SURFACE, "missing", f"{_LLMS_TXT}: not built")
        return
    text = path.read_text(encoding="utf-8")
    if stance not in text:
        yield Finding(SURFACE, "stance", f"{_LLMS_TXT}: the version stance block is missing or altered")
    restricted = restricted_sections(sections)
    reported: set[str] = set()
    for match in _URL.finditer(text):
        route = normalise_url(match.group(0))
        if route is None or route in reported or _section_of(route) not in restricted:
            continue
        reported.add(route)
        yield Finding(SURFACE, route, f"{_LLMS_TXT}: section {_section_of(route)} does not feed {_FEED}")


def surface(dist: Path, routes: frozenset[str]) -> Iterator[Finding]:
    """The registered surface: the repository's section registry and the contract's stance.

    *routes* (the unpublished routes) are the ``llms`` surface's concern, not this one's.
    """
    del routes
    yield from findings(dist, sections=SECTIONS_YAML, stance=LLMS_STANCE)
