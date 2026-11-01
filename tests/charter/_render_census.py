"""Test-only census: which shipped doctrine documents one call actually parses.

Why this exists (#6462): "the CLI parses the whole charter catalog for every call"
cannot be guarded by a wall clock on a shared, loaded host. It *can* be guarded by
the work itself: the number and kind of shipped documents a call actually parses.

Two production seams are censused, both cold for the duration of the census so the
count reflects what a fresh CLI process pays:

- :func:`charter.offering.yaml_utils.parse_shipped_yaml` — every catalog, profile and
  other doctrine document parsed through the per-change memo (the memo is emptied for
  the census, so each call is a real parse).
- :func:`charter.offering.drg.loader.load_graph` — every ``*.graph.yaml`` fragment
  parsed for the built-in DRG (its own memo is emptied too).

Everything is restored on exit, including the two memos, so a census never changes
what a later test sees.
"""

from __future__ import annotations

import contextlib
import sys
import traceback
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from collections.abc import Iterator

from charter.offering import yaml_utils
from charter.offering.drg import loader as drg_loader

__all__ = ["CENSUS_KINDS", "RenderCensus", "census", "kind_of"]

#: Kinds the census distinguishes, keyed by the filename suffix the pack uses.
CENSUS_KINDS: tuple[str, ...] = (
    "paradigm",
    "directive",
    "tactic",
    "styleguide",
    "toolguide",
    "procedure",
    "agent_profile",
    "mission_step",
    "mission_type",
    "glossary_pack",
    "asset",
    "skill",
    "graph",
)

#: Kinds a persona render must never enumerate (the domains its governance
#: resolution does not read). ``graph`` is censused separately by the board guard.
UNUSED_BY_PERSONA_RENDER: tuple[str, ...] = (
    "tactic",
    "styleguide",
    "toolguide",
    "procedure",
    "agent_profile",
)


def kind_of(path: str | Path) -> str:
    """Return the census kind for one shipped doctrine file path."""
    name = Path(str(path)).name
    for kind in CENSUS_KINDS:
        if name.endswith(f".{kind}.yaml"):
            return kind
    # Agent profiles ship as ``*.agent.yaml`` (declared kind ``agent_profile``).
    if name.endswith(".agent.yaml"):
        return "agent_profile"
    return "other"


@dataclass
class RenderCensus:
    """Counts of shipped documents actually parsed inside one :func:`census` block."""

    counts: Counter[str] = field(default_factory=Counter)
    paths: dict[str, list[str]] = field(default_factory=dict)
    callers: Counter[str] = field(default_factory=Counter)

    def record(self, kind: str, path: str | Path) -> None:
        self.counts[kind] += 1
        self.paths.setdefault(kind, []).append(str(path))
        caller = traceback.extract_stack(limit=4)[-2]
        self.callers[f"{caller.name}:{caller.lineno}"] += 1

    def total(self) -> int:
        """Every shipped document parsed, any kind."""
        return sum(self.counts.values())

    def for_kinds(self, kinds: tuple[str, ...]) -> int:
        """Parsed documents of the named kinds."""
        return sum(self.counts.get(kind, 0) for kind in kinds)

    def describe(self) -> str:
        """One-line, diff-friendly rendering used in assertion messages."""
        return ", ".join(f"{kind}={count}" for kind, count in sorted(self.counts.items())) or "(nothing parsed)"


@contextlib.contextmanager
def census() -> Iterator[RenderCensus]:
    """Count every shipped-doctrine parse performed inside the block.

    The two per-change memos are emptied on entry and restored on exit, so the
    census measures first-parse cost (what a fresh CLI invocation pays) rather
    than whatever an earlier test in the same process already warmed.
    """
    state = RenderCensus()

    shipped_memo = yaml_utils._SHIPPED_DOCUMENT_MEMO
    graph_memo = drg_loader._BUILT_IN_GRAPH_MEMO
    yaml_utils._SHIPPED_DOCUMENT_MEMO = {}
    drg_loader._BUILT_IN_GRAPH_MEMO = {}

    original_parse = yaml_utils.parse_shipped_yaml
    original_load_graph = drg_loader.load_graph

    def counting_parse(path: Path, parse, *, variant):  # type: ignore[no-untyped-def]
        state.record(kind_of(path), path)
        return original_parse(path, parse, variant=variant)

    def counting_load_graph(path: Path):  # type: ignore[no-untyped-def]
        state.record("graph", path)
        return original_load_graph(path)

    rebound: list[tuple[object, str, object]] = []
    for module in list(sys.modules.values()):
        if getattr(module, "parse_shipped_yaml", None) is original_parse:
            rebound.append((module, "parse_shipped_yaml", original_parse))
            module.parse_shipped_yaml = counting_parse  # type: ignore[attr-defined]
        if getattr(module, "load_graph", None) is original_load_graph:
            rebound.append((module, "load_graph", original_load_graph))
            module.load_graph = counting_load_graph  # type: ignore[attr-defined]

    try:
        yield state
    finally:
        for module, attribute, original in rebound:
            setattr(module, attribute, original)
        yaml_utils._SHIPPED_DOCUMENT_MEMO = shipped_memo
        drg_loader._BUILT_IN_GRAPH_MEMO = graph_memo
