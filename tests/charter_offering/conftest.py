"""Shared constants for doctrine test suite.

OFFERING_SOURCE_ROOT is the canonical path to the in-repo doctrine source tree
(``src/charter/offering/`` since mission ``charter-code-topology-01M152G1``
relocated the former top-level ``src/charter/offering/`` package there).
Compliance-guard and consistency tests import this constant instead of
hardcoding ``REPO_ROOT / "src" / "charter" / "offering"`` independently.  The
path is intentionally *not* routed through ``MissionTemplateRepository`` —
these tests act as layout canaries and should break if the directory
structure changes.

BUILT_IN_MISSIONS_ROOT is the analogous canonical constant for the missions
DATA subdirectories, relocated by mission
``doctrine-consumer-surface-missions-extraction-01KZ6G6H`` (FR-005) from
``src/charter/offering/missions`` (nested under ``OFFERING_SOURCE_ROOT``) to
``packs/built-in/missions`` (a sibling of ``OFFERING_SOURCE_ROOT``, not nested
under it). Compliance-guard/layout-canary tests that need the shipped mission
data on disk should import this constant rather than composing
``OFFERING_SOURCE_ROOT / "missions"`` themselves -- that composition still
type-checks and still resolves to an *existing* directory post-relocation
(the 11 ``.py`` logic modules stay there), it is just the wrong, now
data-less one.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from charter.offering.drg.models import DRGGraph

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
"""Repository root, resolved from ``tests/charter_offering/conftest.py``."""

OFFERING_SOURCE_ROOT: Path = REPO_ROOT / "src" / "charter" / "offering"
"""Canonical on-disk path to the doctrine source tree (``src/charter/offering/``)."""

BUILT_IN_MISSIONS_ROOT: Path = REPO_ROOT / "packs" / "built-in" / "missions"
"""Canonical on-disk path to the relocated missions data tree
(``packs/built-in/missions/``) -- see module docstring."""


# ---------------------------------------------------------------------------
# Built-in DRG graph seam fixtures (WP03/T012 seam, WP04/T018, FR-009, NFR-007)
# ---------------------------------------------------------------------------
#
# The shipped DRG lives under ``src/charter/offering/`` as a ``graph.yaml`` monolith
# today and, after mission #2680 WP05, as ``*.graph.yaml`` fragments. Tests
# MUST NOT reconstruct ``.../src/charter/offering/graph.yaml`` themselves: that path
# breaks the instant WP05 deletes the monolith. Instead they route through the
# canonical WP03 seam — ``built_in_graph_source()`` (the *directory*) and
# ``load_built_in_graph()`` (``load_graph_or_dir`` over that directory) — which
# follows the monolith->fragment migration transparently.
#
# ``built_in_graph`` caches the parsed graph so the doctrine suite pays the
# ~0.18s load once per session rather than once per test.
#
# READ-ONLY contract: consumers may only *read* the returned graph (node/edge
# lookups, traversal). They must NOT mutate it — a ``DRGGraph`` mutated in one
# test would bleed into every other test sharing the session fixture. Tests
# that need to construct/modify their own graph keep building synthetic
# in-memory graphs (e.g. ``test_drg_relations.py`` / ``test_drg_merge.py``).
#
# CARVE-OUTS (must NOT use this cache):
#   * ``test_graph_file_exists`` / ``test_shipped_graph_yaml_is_fresh`` and any
#     freshness/existence canary — they assert the *on-disk* file, not a parsed
#     in-memory cache, and must read from disk every run.
#   * idempotency / "loads twice" tests — they assert independent load behaviour.


@pytest.fixture(scope="session")
def built_in_graph_dir() -> Path:
    """Directory that ships the built-in DRG (monolith today, fragments post-WP05).

    Backed by the WP03 seam ``built_in_graph_source()`` so callers never encode
    the ``graph.yaml`` filename and survive the WP05 monolith->fragment flip.
    """
    from charter.offering.drg.loader import built_in_graph_source

    return built_in_graph_source()


@pytest.fixture(scope="session")
def built_in_graph() -> DRGGraph:
    """Load the built-in DRG once per session via the WP03 seam (read-only).

    Backed by ``load_built_in_graph()`` (``load_graph_or_dir`` over
    ``built_in_graph_source()``), which prefers the ``graph.yaml`` monolith when
    present and otherwise merges ``*.graph.yaml`` fragments. Imported lazily so
    that merely collecting the doctrine suite does not pay the doctrine import
    cost. Consumers MUST treat the returned graph as read-only (see module note).
    """
    from charter.offering.drg.loader import load_built_in_graph

    return load_built_in_graph()


@pytest.fixture(scope="session")
def shipped_drg_graph(built_in_graph: DRGGraph) -> DRGGraph:
    """Validated built-in DRG once per session (read-only).

    Delegates loading to the seam-backed ``built_in_graph`` fixture and runs
    ``assert_valid`` once so validated-graph consumers share a single cached,
    read-only graph. ``load_built_in_graph()`` already merges any project layer
    absence (``merge_layers(built_in, None)`` is an identity), so no extra merge
    step is needed here.
    """
    from charter.offering.drg.validator import assert_valid

    assert_valid(built_in_graph)
    return built_in_graph
