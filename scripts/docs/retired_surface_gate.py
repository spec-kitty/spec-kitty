"""The retired-surface gate: a published living page must not newly name a retired surface (#7520).

The living pages are :func:`scripts.docs._living_pages.living_pages` (the published set
minus the history folders); the retired surfaces come from one authority,
:mod:`scripts.retired_surfaces`, which the code gate
``tests/architectural/test_no_retired_subsystems.py`` reads too.

Pages that already named a retired surface when the gate landed are listed in the tracked
burn-down ``scripts/docs/retired_surface_burndown.yaml``, each with the section sub-issue
(#7522-#7528) that drains it. The gate fails on:

* ``NEW``: a (page, surface) pair the burn-down does not list, or one the page names on more
  lines than the burn-down records (a burned-down page cannot add mentions of the same surface);
* ``STALE``: a burn-down pair the page no longer names, or names on fewer lines (remove it or
  lower its count, so the list shrinks);
* ``REFILL``: a burn-down pair the landing set ``scripts/docs/retired_surface_landing.yaml`` does
  not list, or a count above the landing one: the burn-down only shrinks, so a swap (drain one
  pair, add another, same count) fails here on its own;
* ``BASELINE``: the number of burned-down pairs, :data:`BURN_DOWN`, differs from
  ``test_retired_surface_gate.burn_down`` in ``tests/architectural/_baselines.yaml``. A pull
  request that drains a pair lowers that number with it, so a drained pair put back is above
  it. The shared ratchet there also fails on growth.

The body, the ``title`` and the ``description`` are scanned: they are what the site publishes.
It runs in the always-on ``docs-lint`` job::

    python -m scripts.docs.retired_surface_gate

Exit 0 when clean, 1 with one line per finding on stderr. No git history is read.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import yaml

# Runnable bare (`python3 scripts/docs/retired_surface_gate.py`): resolve `scripts.*` from the script, not the cwd.
_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.docs._living_pages import living_pages, published_text  # noqa: E402  (sys.path bootstrap above)
from scripts.retired_surfaces import docs_retired_surfaces, surfaces_named  # noqa: E402  (sys.path bootstrap above)

__all__ = [
    "BURN_DOWN",
    "BURNDOWN_KIND",
    "DEFAULT_BURNDOWN",
    "BurnDownEntry",
    "BurnDownError",
    "DEFAULT_BASELINES",
    "baseline_findings",
    "burn_down_counts",
    "check",
    "load_baseline",
    "DEFAULT_LANDING",
    "load_burndown",
    "load_landing",
    "main",
    "refill_findings",
    "refilled",
    "scan",
    "surfaces_named",
]

DEFAULT_BURNDOWN: Final[Path] = _REPO_ROOT / "scripts" / "docs" / "retired_surface_burndown.yaml"
#: The burn-down as it stood at landing, frozen: the burn-down may only shrink from it.
DEFAULT_LANDING: Final[Path] = _REPO_ROOT / "scripts" / "docs" / "retired_surface_landing.yaml"
#: The one authority for the burn-down's pair count (``test_retired_surface_gate.burn_down``).
DEFAULT_BASELINES: Final[Path] = _REPO_ROOT / "tests" / "architectural" / "_baselines.yaml"
_BASELINE_SECTION: Final[str] = "test_retired_surface_gate"
_BASELINE_LEAF: Final[str] = "burn_down"
_DEFAULT_DOCS: Final[Path] = _REPO_ROOT / "docs"
BURNDOWN_KIND: Final[str] = "retired-surface-burndown"
_LANDING_KIND: Final[str] = "retired-surface-landing"
_BURNDOWN_VERSION: Final[int] = 2


class BurnDownError(ValueError):
    """The burn-down file is malformed."""


@dataclass(frozen=True)
class BurnDownEntry:
    """A living page that still names retired surfaces, and the section sub-issue that drains it."""

    page: str
    surfaces: Mapping[str, int]  # surface id -> the number of lines on the page that name it
    issue: str


def _entry(raw: object, index: int) -> BurnDownEntry:
    if not isinstance(raw, Mapping):
        raise BurnDownError(f"entries[{index}] must be a mapping")
    page, issue, surfaces = raw.get("page"), raw.get("issue"), raw.get("surfaces")
    if not isinstance(page, str) or not isinstance(issue, str) or not isinstance(surfaces, Mapping) or not surfaces:
        raise BurnDownError(f"entries[{index}] needs a page, an issue and a non-empty surfaces mapping (surface -> line count)")
    counts = {str(surface): count for surface, count in surfaces.items()}
    if not all(type(count) is int and count > 0 for count in counts.values()):
        raise BurnDownError(f"entries[{index}] ({page}): every surface needs a positive integer line count")
    return BurnDownEntry(page=page, surfaces=counts, issue=issue)


def load_burndown(path: Path) -> list[BurnDownEntry]:
    """Read and check the burn-down file."""
    data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping) or data.get("kind") != BURNDOWN_KIND or data.get("version") != _BURNDOWN_VERSION:
        raise BurnDownError(f"{path} must declare kind: {BURNDOWN_KIND} and version: {_BURNDOWN_VERSION}")
    entries = data.get("entries", [])
    if not isinstance(entries, list):
        raise BurnDownError(f"{path}: entries must be a list")
    parsed = [_entry(raw, index) for index, raw in enumerate(entries)]
    seen: set[str] = set()
    for entry in parsed:
        if entry.page in seen:
            raise BurnDownError(f"{path}: duplicate page {entry.page}; list each page once with all its surfaces")
        seen.add(entry.page)
    return parsed


def scan(docs_root: Path) -> dict[str, dict[str, list[int]]]:
    """Every living page that names a retired surface: page -> surface -> file line numbers.

    The body, the ``title`` and the ``description`` are read; they are what the site publishes.
    """
    hits: dict[str, dict[str, list[int]]] = {}
    for page in living_pages(docs_root):
        found = surfaces_named(published_text((docs_root / page).read_text(encoding="utf-8")))
        if found:
            hits[page] = found
    return hits


def burn_down_counts(burndown: Iterable[BurnDownEntry]) -> dict[tuple[str, str], int]:
    """The burn-down as (page, surface) -> the number of lines that may name it."""
    return {(entry.page, surface): count for entry in burndown for surface, count in entry.surfaces.items()}


def check(docs_root: Path, burndown: Iterable[BurnDownEntry]) -> list[str]:
    """``NEW`` and ``STALE`` findings, sorted; empty when the tree matches the burn-down."""
    retired_by = {surface.id: surface.retired_by for surface in docs_retired_surfaces()}
    entries = list(burndown)
    allowed = burn_down_counts(entries)
    issues = {entry.page: entry.issue for entry in entries}
    hits = scan(docs_root)
    findings = []
    for page, surfaces in sorted(hits.items()):
        for surface, lines in sorted(surfaces.items()):
            listed = allowed.get((page, surface), 0)
            if len(lines) > listed:
                detail = "" if not listed else f" on {len(lines)} lines, the burn-down allows {listed}"
                findings.append(f"NEW {page}:{lines[listed]}: names retired surface '{surface}'{detail} (retired: {retired_by[surface]})")
    for (page, surface), listed in sorted(allowed.items()):
        live = len(hits.get(page, {}).get(surface, []))
        if live == 0:
            findings.append(f"STALE {page}: '{surface}' is no longer named; remove it from the burn-down ({issues[page]})")
        elif live < listed:
            findings.append(f"STALE {page}: '{surface}' is named on {live} lines, below the burn-down's {listed}; lower it to {live} ({issues[page]})")
    return findings


def load_landing(path: Path) -> dict[tuple[str, str], int]:
    """The frozen landing set: (page, surface) -> line count, as recorded when the gate landed."""
    data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    pages = data.get("pages") if isinstance(data, Mapping) else None
    if not isinstance(data, Mapping) or data.get("kind") != _LANDING_KIND or not isinstance(pages, Mapping):
        raise BurnDownError(f"{path} must declare kind: {_LANDING_KIND} and a pages mapping")
    landing = {(str(page), str(surface)): count for page, surfaces in pages.items() if isinstance(surfaces, Mapping) for surface, count in surfaces.items()}
    if not landing or not all(type(count) is int and count > 0 for count in landing.values()):
        raise BurnDownError(f"{path}: every landing surface needs a positive integer line count")
    return landing


def refilled(counts: Mapping[tuple[str, str], int], landing: Mapping[tuple[str, str], int]) -> list[tuple[str, str]]:
    """Burn-down pairs outside the *landing* set or above its count, sorted: a swap or a re-addition.

    The burn-down may only shrink from the landing set; :func:`main` fails on any pair this returns.
    """
    return sorted(pair for pair, count in counts.items() if count > landing.get(pair, 0))


def refill_findings(counts: Mapping[tuple[str, str], int], landing: Mapping[tuple[str, str], int]) -> list[str]:
    """``REFILL`` findings for :func:`refilled`, one line per pair."""
    return [
        f"REFILL {page}: '{surface}' is in the burn-down on {counts[(page, surface)]} lines but the landing set has {landing.get((page, surface), 0)}; "
        "the burn-down only shrinks, fix the page instead"
        for page, surface in refilled(counts, landing)
    ]


def load_baseline(path: Path) -> int:
    """The recorded burn-down pair count, ``test_retired_surface_gate.burn_down`` in *path*."""
    data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    section = data.get(_BASELINE_SECTION) if isinstance(data, Mapping) else None
    value = section.get(_BASELINE_LEAF) if isinstance(section, Mapping) else None
    if not isinstance(value, int):
        raise BurnDownError(f"{path} must record {_BASELINE_SECTION}.{_BASELINE_LEAF} as an integer")
    return value


def baseline_findings(pairs: frozenset[tuple[str, str]], baseline: int) -> list[str]:
    """``BASELINE`` findings: the burn-down's pair count must equal the recorded baseline.

    Equality, not only "at most", makes leaving one-way for this gate: a pull request that
    drains a pair lowers the baseline with it, and a drained pair put back is then above the
    baseline. (The shared ratchet in ``tests/architectural/test_ratchet_baselines.py`` only
    fails on growth; this check is the gate's own and changes no other key.)
    """
    count = len(pairs)
    if count > baseline:
        return [f"BASELINE the burn-down holds {count} pairs, above the recorded {baseline}: a pair was added back; fix the page instead"]
    if count < baseline:
        return [
            f"BASELINE the burn-down holds {count} pairs, below the recorded {baseline}: lower "
            f"{_BASELINE_SECTION}.{_BASELINE_LEAF} in tests/architectural/_baselines.yaml to {count} in the same pull request"
        ]
    return []


def main(argv: list[str] | None = None) -> int:
    """Run the gate; exit 1 on any finding."""
    parser = argparse.ArgumentParser(prog="retired_surface_gate", description="Fail when a published living page newly names a retired surface.")
    parser.add_argument("--docs-root", type=Path, default=_DEFAULT_DOCS)
    parser.add_argument("--burndown", type=Path, default=DEFAULT_BURNDOWN)
    parser.add_argument("--baselines", type=Path, default=DEFAULT_BASELINES)
    parser.add_argument("--landing", type=Path, default=DEFAULT_LANDING)
    args = parser.parse_args(argv)
    entries = load_burndown(args.burndown)
    counts = burn_down_counts(entries)
    findings = (
        check(args.docs_root, entries) + refill_findings(counts, load_landing(args.landing)) + baseline_findings(frozenset(counts), load_baseline(args.baselines))
    )
    for finding in findings:
        print(finding, file=sys.stderr)
    if findings:
        print(
            "retired_surface_gate: name the replacement the 'retired:' note gives, or drop the mention where it "
            "gives none. A STALE entry leaves scripts/docs/retired_surface_burndown.yaml, and "
            "test_retired_surface_gate.burn_down in tests/architectural/_baselines.yaml is lowered to match "
            "in the same pull request.",
            file=sys.stderr,
        )
        return 1
    print("retired_surface_gate: clean")
    return 0


#: The burned-down (page, surface) pairs; their count is ratcheted in ``tests/architectural/_baselines.yaml``.
BURN_DOWN: Final[frozenset[tuple[str, str]]] = frozenset(burn_down_counts(load_burndown(DEFAULT_BURNDOWN)))


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
