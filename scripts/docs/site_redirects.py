"""Generate the docsite's legacy redirect map (#6933; ADR 2026-10-31-1 D-5, amended 2026-11-10).

Every route the legacy site published before the cutover (``site/url-baseline.txt``) must keep resolving on the
doc-kitty site. All of them end in ``.html``. Astro refuses ``.html`` redirect keys on static
output (doc-kitty #253), so the map feeds doc-kitty's ``legacyHtmlRedirects`` option, which
writes one flat redirect stub per key. This module derives that map from three authorities
and writes it to ``site/legacy-redirects.json``. The map is generated and never hand-edited.

The inputs:

* the URL baseline (``scripts/docs/moves_ledger.py``, :func:`load_baseline`);
* the moves ledger ``site/moves.yaml``, with its chains collapsed (:func:`collapse`);
* the published set (``scripts/docs/_dockitty_contract.py``): every page's :func:`route_of`
  minus :func:`unpublished_routes`.

The rules, applied to each baseline route:

1. ``X.html`` redirects to ``X/``; ``dir/README.html`` and ``dir/index.html`` to ``dir/``.
2. A moved route first follows its collapsed chain to the final route.
3. A ``dir/index.html`` that is the built file of the live, unmoved page ``dir/`` gets no
   key: the page serves it.
4. A route whose page is unpublished (draft folder, draft status, excluded or archived
   folder) redirects to its nearest published ancestor, normally the section hub. It
   was put here, not in ``moves.yaml``, while the legacy site still published drafts
   (its map check refused a move away from a page it published); that site is retired
   (#6943), so a ``moves.yaml`` row may now carry the rule instead.
5. A route backed by a file under ``docs/`` that is not a page (a standalone HTML resource
   the legacy site copied, such as ``assets/spec-kitty-backlog.html``) redirects to its nearest
   published ancestor (operator ruling 2026-11-10). Any other route with no page and no
   move is refused.

Also refused: a moves-ledger cycle, a key whose file would overwrite a live page or a
``site/public`` file (doc-kitty fails the build on both), and a route with no published
ancestor at all.

Usage::

    python -m scripts.docs.site_redirects           # (re)write site/legacy-redirects.json
    python -m scripts.docs.site_redirects --check   # exit 1 when the committed map is stale

Standard library plus PyYAML (through ``moves_ledger``), so the runner's ``python3`` runs it
with ``PYTHONPATH=.:src``, like ``site_contract.py``.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Final

# Runnable bare (`python3 scripts/docs/site_redirects.py`): resolve `scripts.*` from the script, not the cwd.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.docs._dockitty_contract import INDEX_BASENAMES, route_of, unpublished_routes  # noqa: E402
from scripts.docs.moves_ledger import MovesLedgerError, collapse, load_baseline, load_moves  # noqa: E402

__all__ = ["MAP_PATH", "RedirectMapError", "build_map", "check", "main", "render", "write"]

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
MAP_PATH: Final[Path] = REPO_ROOT / "site" / "legacy-redirects.json"
_BASELINE: Final[Path] = REPO_ROOT / "site" / "url-baseline.txt"
_MOVES: Final[Path] = REPO_ROOT / "site" / "moves.yaml"
_DOCS: Final[Path] = REPO_ROOT / "docs"
_PUBLIC: Final[Path] = REPO_ROOT / "site" / "public"

_HTML_SUFFIX: Final[str] = ".html"
_MD_SUFFIX: Final[str] = ".md"
_INDEX_HTML: Final[str] = "index.html"
_INDEX_FOLDED: Final[frozenset[str]] = frozenset(name.lower() for name in INDEX_BASENAMES)
_FIX: Final[str] = "python -m scripts.docs.site_redirects"


class RedirectMapError(ValueError):
    """The inputs give no valid map; the message lists every problem, one per line."""


def _dir_route(legacy: str) -> str:
    """Rule 1: ``/a/b.html`` -> ``/a/b/``; ``/a/README.html`` and ``/a/index.html`` -> ``/a/``."""
    stem = legacy.strip("/").removesuffix(_HTML_SUFFIX)
    head, _, last = stem.rpartition("/")
    if last.lower() in _INDEX_FOLDED:
        stem = head
    return f"/{stem}/" if stem else "/"


def _ancestors(route: str) -> Iterator[str]:
    """``/a/b/c/`` -> ``/a/b/``, ``/a/``, ``/``."""
    parts = route.strip("/").split("/") if route != "/" else []
    for depth in range(len(parts) - 1, -1, -1):
        yield "/" + "".join(f"{part}/" for part in parts[:depth])


def _page_routes(docs: Path) -> frozenset[str]:
    return frozenset(route_of(path.relative_to(docs).as_posix()) for path in docs.rglob(f"*{_MD_SUFFIX}"))


def _is_resource(docs: Path, legacy: str) -> bool:
    path = docs / legacy.lstrip("/")
    return path.is_file() and path.suffix != _MD_SUFFIX


def _resolve(route: str, final: str, docs: Path, pages: frozenset[str], live: frozenset[str]) -> str:
    """The live target of the baseline *route*, whose collapsed chain ends at *final*."""
    target = _dir_route(final)
    if target in live:
        return target
    if target not in pages and not _is_resource(docs, final):
        raise RedirectMapError(f"{route}: no page, no move and no resource under docs/ (it would 404)")
    hub = next((ancestor for ancestor in _ancestors(target) if ancestor in live), None)
    if hub is None:
        raise RedirectMapError(f"{route}: no published ancestor of {target}")
    return hub


def _entry(route: str, moved: Mapping[str, str], docs: Path, public: Path, pages: frozenset[str], live: frozenset[str]) -> str | None:
    """The map value for *route*, or ``None`` when the route needs no key (rule 3)."""
    target = _resolve(route, moved.get(route, route), docs, pages, live)
    if route.endswith(f"/{_INDEX_HTML}") and route.removesuffix(_INDEX_HTML) in live:
        if route not in moved and target == route.removesuffix(_INDEX_HTML):
            return None
        raise RedirectMapError(f"{route}: the key would overwrite the live page {route.removesuffix(_INDEX_HTML)} (redirects to {target})")
    if (public / route.lstrip("/")).exists():
        raise RedirectMapError(f"{route}: the key would overwrite site/public/{route.lstrip('/')}")
    return target


def build_map(*, baseline: Path = _BASELINE, moves: Path = _MOVES, docs: Path = _DOCS, public: Path = _PUBLIC) -> dict[str, str]:
    """The legacy redirect map, sorted by key; :class:`RedirectMapError` lists every refusal."""
    try:
        moved = collapse(load_moves(moves))
    except MovesLedgerError as error:
        raise RedirectMapError(f"{moves}: {error}") from error
    try:
        routes = load_baseline(baseline)
    except MovesLedgerError as error:
        raise RedirectMapError(str(error)) from error
    if not routes:
        raise RedirectMapError(f"{baseline}: the URL baseline lists no route, so the map would cover nothing")
    pages = _page_routes(docs)
    live = pages - unpublished_routes(docs)
    mapping: dict[str, str] = {}
    problems: list[str] = []
    for route in routes:
        try:
            target = _entry(route, moved, docs, public, pages, live)
        except RedirectMapError as error:
            problems.append(str(error))
            continue
        if target is not None:
            mapping[route] = target
    if problems:
        raise RedirectMapError("\n".join(problems))
    return dict(sorted(mapping.items()))


def render(**inputs: Path) -> str:
    """The exact text of ``site/legacy-redirects.json``: a flat, sorted JSON object (no comment key)."""
    return json.dumps(build_map(**inputs), indent=2) + "\n"


def write(path: Path = MAP_PATH, **inputs: Path) -> None:
    """Write the map to *path*."""
    path.write_text(render(**inputs), encoding="utf-8")


def check(path: Path = MAP_PATH, **inputs: Path) -> list[str]:
    """The differences between the map at *path* and the generated one (empty when equal)."""
    try:
        expected = render(**inputs)
    except RedirectMapError as error:
        return str(error).splitlines()
    try:
        actual = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [f"{path} is missing"]
    if actual == expected:
        return []
    try:
        committed = json.loads(actual)
    except json.JSONDecodeError as error:
        return [f"{path} is not valid JSON: {error}"]
    generated = json.loads(expected)
    if not isinstance(committed, dict):
        return [f"{path} must hold a JSON object"]
    problems = [f"{key}: missing (expected -> {generated[key]})" for key in sorted(set(generated) - set(committed))]
    problems += [f"{key}: not generated (found -> {committed[key]})" for key in sorted(set(committed) - set(generated))]
    problems += [
        f"{key}: expected -> {generated[key]}, found -> {committed[key]}" for key in sorted(set(generated) & set(committed)) if generated[key] != committed[key]
    ]
    return problems or [f"{path} is not in the generated layout"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--check", action="store_true", help="verify the committed map instead of writing it")
    parser.add_argument("--path", type=Path, default=MAP_PATH, help="the map (default: site/legacy-redirects.json)")
    parser.add_argument("--baseline", type=Path, default=_BASELINE, help="the URL baseline (default: site/url-baseline.txt)")
    parser.add_argument("--moves", type=Path, default=_MOVES, help="the moves ledger (default: site/moves.yaml)")
    parser.add_argument("--docs", type=Path, default=_DOCS, help="the docs tree (default: docs)")
    parser.add_argument("--public", type=Path, default=_PUBLIC, help="the site's public folder (default: site/public)")
    args = parser.parse_args(argv)
    inputs = {"baseline": args.baseline, "moves": args.moves, "docs": args.docs, "public": args.public}
    if args.check:
        problems = check(args.path, **inputs)
        for problem in problems:
            print(f"legacy redirect map: {problem}", file=sys.stderr)
        if problems:
            print(f"Fix: {_FIX} (after fixing any refusal above)", file=sys.stderr)
        return 1 if problems else 0
    try:
        write(args.path, **inputs)
    except RedirectMapError as error:
        for problem in str(error).splitlines():
            print(f"legacy redirect map: {problem}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
