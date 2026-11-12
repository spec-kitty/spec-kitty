"""The standing docsite ledgers: the URL baseline and the moves ledger (#6927).

Two committed, repository-level files under ``site/`` (ADR ``2026-10-31-1`` D-5):

``site/url-baseline.txt``
    Every route the docsite has published: one route per line, with a leading
    ``/`` (doc-kitty's baseline format), ``#`` comments allowed. It grows when a
    page is published. A route leaves only through an amendment recorded in the
    file's header.

``site/moves.yaml``
    An append-only list of ``from -> to`` route moves. It replaces the binding to
    a closed Mission's ``occurrence_map.yaml`` that #2358 reported. When a page
    moves again, a new entry is appended from its previous route, and
    :func:`collapse` follows the chain to the final route.

A **route** is a site-relative published path in its legacy ``.html`` form, such
as ``/guides/x.html`` or ``/adr/1.x/index.html``: the form the legacy site
published before the doc-kitty cutover (#6938). The doc-kitty redirect generator
(``scripts/docs/site_redirects.py``) maps ``X.html`` to the directory URL ``X/``
(ADR D-5 rule 1).

This module is the single reader and validator of both files. It has no CLI.
``scripts/docs/site_redirects.py`` and the live-site probe read the collapsed
ledger (:func:`collapse`), and the rename gate and link rewriters read the moves
through :func:`source_pairs`. Standard library plus PyYAML only, because the
docsite jobs run it with the system ``python3``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import yaml

__all__ = [
    "DEFAULT_MOVES_LEDGER",
    "DEFAULT_URL_BASELINE",
    "LEDGER_KIND",
    "LEDGER_VERSION",
    "Move",
    "MovesLedgerError",
    "collapse",
    "load_baseline",
    "load_moves",
    "route_to_source",
    "source_pairs",
    "source_to_route",
]

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
DEFAULT_MOVES_LEDGER: Final[Path] = REPO_ROOT / "site" / "moves.yaml"
DEFAULT_URL_BASELINE: Final[Path] = REPO_ROOT / "site" / "url-baseline.txt"

LEDGER_KIND: Final[str] = "docs-moves-ledger"
LEDGER_VERSION: Final[int] = 1

_DOCS_PREFIX: Final[str] = "docs/"
_MD_SUFFIX: Final[str] = ".md"
_HTML_SUFFIX: Final[str] = ".html"
_SLASH: Final[str] = "/"


class MovesLedgerError(ValueError):
    """A ledger file is malformed or breaks one of its invariants."""


@dataclass(frozen=True)
class Move:
    """One ``site/moves.yaml`` entry: ``from_route`` was replaced by ``to_route``."""

    from_route: str
    to_route: str
    ref: str
    note: str = ""


# --- Moves ledger --------------------------------------------------------------


def _require_route(value: object, field: str, index: int) -> str:
    if not isinstance(value, str) or not value.startswith(_SLASH) or len(value) < 2:
        raise MovesLedgerError(f"moves[{index}].{field} must be a route starting with '/', got {value!r}")
    return value


def _parse_move(raw: object, index: int) -> Move:
    if not isinstance(raw, Mapping):
        raise MovesLedgerError(f"moves[{index}] must be a mapping, got {raw!r}")
    ref = raw.get("ref")
    if not isinstance(ref, str) or not ref.strip():
        raise MovesLedgerError(f"moves[{index}].ref must name a PR, issue or Mission")
    note = raw.get("note", "")
    return Move(
        from_route=_require_route(raw.get("from"), "from", index),
        to_route=_require_route(raw.get("to"), "to", index),
        ref=ref,
        note=str(note) if note else "",
    )


def load_moves(path: Path) -> list[Move]:
    """Load and check ``site/moves.yaml``, in file order.

    Refuses an unknown ``kind`` or ``version``, a malformed entry, and a ``from``
    route that appears twice: append-only means a later move is a new entry from
    the previous destination, never a second entry for the same source.
    """
    data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise MovesLedgerError(f"{path} is not a mapping")
    if data.get("kind") != LEDGER_KIND or data.get("version") != LEDGER_VERSION:
        raise MovesLedgerError(f"{path} must declare kind: {LEDGER_KIND} and version: {LEDGER_VERSION}")
    raw_moves = data.get("moves") or []
    if not isinstance(raw_moves, list):
        raise MovesLedgerError(f"{path}: moves must be a list")
    moves = [_parse_move(raw, index) for index, raw in enumerate(raw_moves)]
    seen: set[str] = set()
    for move in moves:
        if move.from_route in seen:
            raise MovesLedgerError(f"{path}: duplicate from route {move.from_route}")
        seen.add(move.from_route)
    return moves


def _final_route(start: str, direct: Mapping[str, str]) -> str:
    visited = [start]
    current = direct[start]
    while current in direct:
        if current in visited:
            chain = " -> ".join([*visited, current])
            raise MovesLedgerError(f"cycle in the moves ledger: {chain}")
        visited.append(current)
        current = direct[current]
    return current


def collapse(moves: Iterable[Move]) -> dict[str, str]:
    """Map every ``from`` route to the end of its chain (ADR D-5 rule 2)."""
    direct = {move.from_route: move.to_route for move in moves}
    return {source: _final_route(source, direct) for source in direct}


# --- URL baseline --------------------------------------------------------------


def load_baseline(path: Path) -> list[str]:
    """Routes of ``site/url-baseline.txt``: sorted, de-duplicated, comments skipped."""
    routes: set[str] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        if not entry.startswith(_SLASH):
            raise MovesLedgerError(f"{path}:{number}: route must start with '/': {entry}")
        routes.add(entry)
    return sorted(routes)


# --- Route <-> docs source --------------------------------------------------------


def route_to_source(route: str) -> str | None:
    """``/a/b.html`` -> ``docs/a/b.md``; ``None`` for a route that is not a page."""
    if not route.startswith(_SLASH) or not route.endswith(_HTML_SUFFIX):
        return None
    return f"{_DOCS_PREFIX}{route[1 : -len(_HTML_SUFFIX)]}{_MD_SUFFIX}"


def source_to_route(path: str) -> str | None:
    """``docs/a/b.md`` -> ``/a/b.html``; ``None`` for a file that is not a page."""
    if not path.startswith(_DOCS_PREFIX) or not path.endswith(_MD_SUFFIX):
        return None
    return f"{_SLASH}{path[len(_DOCS_PREFIX) : -len(_MD_SUFFIX)]}{_HTML_SUFFIX}"


def source_pairs(moves: Iterable[Move]) -> list[tuple[str, str]]:
    """``(old docs source, new docs source)`` for every move between two pages.

    The link rewriters (``bulk_ref_rewrite.py``, ``relative_link_fixer.py``) work
    on source paths. A move whose ``from`` or ``to`` is not a page route is
    skipped.
    """
    pairs: list[tuple[str, str]] = []
    for move in moves:
        old = route_to_source(move.from_route)
        new = route_to_source(move.to_route)
        if old is not None and new is not None:
            pairs.append((old, new))
    return pairs
