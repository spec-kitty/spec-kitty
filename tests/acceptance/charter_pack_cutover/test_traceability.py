"""Traceability of the cutover acceptance suite (#3732, T010, C-006).

* the closed id list equals what spec.md declares;
* every id is covered by at least one ``covers(...)`` decorator;
* ``covers(...)`` rejects ids outside the requirement id grammar.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable
from pathlib import Path

import pytest

from ._requirements import (
    DM_IDS,
    EDGE_CASES,
    FR_IDS,
    INVENTORY_ITEMS,
    NFR_IDS,
    OD_IDS,
    REQUIRED_IDS,
    SC_IDS,
    SPEC_PATH,
    US_IDS,
)
from ._support import covers

pytestmark = [pytest.mark.corpus]

SUITE_DIR = Path(__file__).resolve().parent
Source = tuple[str, str]  # (file name, source text)


# --------------------------------------------------------------------------------------
# Spec parsing
# --------------------------------------------------------------------------------------


def _section(text: str, heading: str) -> str:
    start = text.index(heading)
    level = heading.split(" ", 1)[0]
    rest = text[start + len(heading) :]
    match = re.search(rf"^#{{1,{len(level)}}} ", rest, flags=re.MULTILINE)
    return rest[: match.start()] if match else rest


def _story_ids(text: str) -> list[str]:
    ids: list[str] = []
    for match in re.finditer(r"^### User Story (\d) ", text, flags=re.MULTILINE):
        story = _section(text, match.group(0).rstrip())
        scenarios = re.findall(r"^(\d+)\. \*\*Given\*\*", story, flags=re.MULTILINE)
        ids += [f"US{match.group(1)}-{n}" for n in scenarios]
    return ids


def spec_ids(text: str) -> set[str]:
    ids: set[str] = set()
    ids |= set(re.findall(r"^\| (FR-\d{3}) \|", text, flags=re.MULTILINE))
    ids |= set(re.findall(r"^\| (NFR-\d{3}) \|", text, flags=re.MULTILINE))
    ids |= set(re.findall(r"^- \*\*(SC-\d{3})\*\*", text, flags=re.MULTILINE))
    ids |= set(re.findall(r"^\| (OD-\d+) \|", text, flags=re.MULTILINE))
    ids |= set(re.findall(r"\b(DM-[0-9A-Z]{26})\b", text))
    ids |= set(_story_ids(text))
    inventory = _section(text, "#### FR-012 migration inventory")
    ids |= {f"INV:{cell.strip()}" for cell in re.findall(r"^\| ([^|]+?) \|", inventory, flags=re.MULTILINE) if cell.strip() not in {"Item", "---"}}
    edges = _section(text, "### Edge Cases")
    ids |= {f"EC:{title}" for title in re.findall(r"^- \*\*(.+?)\*\*", edges, flags=re.MULTILINE)}
    return ids


@covers("C-006", "OD-10")
def test_required_ids_match_spec() -> None:
    parsed = spec_ids(SPEC_PATH.read_text(encoding="utf-8"))
    assert len(FR_IDS) == 19 and len(NFR_IDS) == 4 and len(SC_IDS) == 5 and len(US_IDS) == 20
    assert len(INVENTORY_ITEMS) == 18 and len(EDGE_CASES) == 13 and len(OD_IDS) == 10 and len(DM_IDS) == 2
    assert parsed == set(REQUIRED_IDS), {"only in spec": sorted(parsed - set(REQUIRED_IDS)), "only in list": sorted(set(REQUIRED_IDS) - parsed)}


# --------------------------------------------------------------------------------------
# AST readers (take sources, so the planted checks need no file in the tree)
# --------------------------------------------------------------------------------------


def suite_sources() -> list[Source]:
    return [(p.name, p.read_text(encoding="utf-8")) for p in sorted(SUITE_DIR.glob("test_*.py"))]


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _calls(sources: Iterable[Source], name: str) -> list[tuple[str, ast.Call]]:
    found: list[tuple[str, ast.Call]] = []
    for file_name, source in sources:
        found += [(file_name, n) for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Call) and _call_name(n) == name]
    return found


def covered_ids(sources: Iterable[Source]) -> set[str]:
    ids: set[str] = set()
    for _, call in _calls(sources, "covers"):
        ids |= {a.value for a in call.args if isinstance(a, ast.Constant) and isinstance(a.value, str)}
    return ids


# --------------------------------------------------------------------------------------
# Coverage
# --------------------------------------------------------------------------------------


@covers("C-006")
def test_every_required_id_is_covered() -> None:
    missing = sorted(set(REQUIRED_IDS) - covered_ids(suite_sources()))
    assert missing == [], missing


# --------------------------------------------------------------------------------------
# Self-tests of the checkers and helpers
# --------------------------------------------------------------------------------------


@covers("C-006")
def test_dropped_cover_is_named() -> None:
    sources = suite_sources()
    stripped = [(n, s.replace('"FR-019"', '"FR-001"')) for n, s in sources]
    assert "FR-019" in covered_ids(sources)
    assert "FR-019" in set(REQUIRED_IDS) - covered_ids(stripped)


@covers("C-006")
def test_covers_rejects_unknown_ids() -> None:
    with pytest.raises(ValueError, match="grammar"):
        covers("FR-1")

    @covers("FR-001", "INV:Org packs list")
    def sample() -> None:
        return None

    assert vars(sample)["__covers__"] == ("FR-001", "INV:Org packs list")
