"""CLI tests for ``spec-kitty charter pack regenerate-graph`` (WP09 / FR-009).

Covers the operator-facing regeneration surface:

1. ``--check --json`` reports the committed shipped graph as fresh (exit 0),
2. regenerate-twice produces byte-identical output (determinism),
3. ``--check`` against a deliberately corrupted graph reports stale (exit 1).

The committed ``src/charter/offering/graph.yaml`` is never mutated: write-mode tests
target a temporary doctrine root assembled from the shipped one.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from charter.offering.drg.loader import load_built_in_graph
from charter.offering.drg.models import NodeKind
from specify_cli.cli.commands.charter import charter_app

if TYPE_CHECKING:
    from charter.offering.drg.models import DRGGraph

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()

# The sharded ``*.graph.yaml`` DRG fragments relocated from ``src/doctrine`` to
# the top-level ``packs/built-in`` pack root (mission relocate-builtin-doctrine-packs);
# regenerate-graph resolves and rewrites them there.
DOCTRINE_ROOT = Path(__file__).resolve().parents[4] / "packs" / "built-in"

#: The LIVE, non-frozen current-state record of the shipped-graph orphan residual.
#:
#: The historical record,
#: ``kitty-specs/mission-lifecycle-dispatch-drg-closeout-01KV0S99/drg-orphan-residual.md``,
#: is parked under ``kitty-specs/`` — an immutable archive root
#: (``tests/architectural/test_archive_root_byte_identical.py``) — so it can be *cited*
#: but never *updated*; its last recorded state (ceiling 29 -> 30 over 17 step
#: contracts) is therefore as-of-date history, not current state. The live record is a
#: ``docs/architecture/`` page an operator can actually edit, and the guard below binds
#: it to the measurement so the two cannot drift silently (#6513).
LIVE_RESIDUAL_RECORD = (
    Path(__file__).resolve().parents[4]
    / "docs"
    / "architecture"
    / "charter-synthesis-drg.md"
)

#: Markers delimiting the record's machine-readable current-state block. Only the
#: backticked URNs between them take part in the guard: prose, historical sections and
#: tables in the same page cannot accidentally satisfy it.
RESIDUAL_BLOCK_BEGIN = "<!-- drg-orphan-residual:begin -->"
RESIDUAL_BLOCK_END = "<!-- drg-orphan-residual:end -->"

#: A whole backticked span that is a DRG node URN (``<kind>:<id>``). The kind set is
#: derived from :class:`~charter.offering.drg.models.NodeKind`, never hand-listed, so a
#: doctrine kind added later still parses here — a hand-written alternation would make a
#: *recorded* URN of a new kind drop out of the parsed set and report the confusing
#: "measured but not recorded" for a URN that is recorded. A stray inline code span such
#: as ``edges: []`` still cannot parse (the id pattern allows no whitespace).
_KIND_ALTERNATION = "|".join(
    re.escape(kind.value) for kind in sorted(NodeKind, key=lambda k: -len(k.value))
)
_URN_SPAN = re.compile(rf"`((?:{_KIND_ALTERNATION}):[A-Za-z0-9_./\-]+)`")


def _graph_files(doctrine_dir: Path) -> list[Path]:
    """Return the DRG graph source files under *doctrine_dir* (layout-agnostic).

    Mirrors :func:`charter.offering.drg.loader.load_graph_or_dir` / the shape of
    :func:`built_in_graph_source`: the ``graph.yaml`` monolith when present,
    otherwise the ``*.graph.yaml`` fragments. This lets per-file byte-identity
    assertions survive the WP05 monolith->fragment flip with no edit (DD-11).
    """
    single = doctrine_dir / "graph.yaml"
    if single.is_file():
        return [single]
    return sorted(doctrine_dir.glob("*.graph.yaml"))

#: The shipped-graph orphan residual has ONE source of truth: the delimited block in
#: ``LIVE_RESIDUAL_RECORD``. ``test_documented_residual_matches_measured_shipped_orphans``
#: requires its URN set to equal the measured shipped orphans exactly, so there is no
#: separate numeric ceiling to keep in step (a ceiling cannot see a shrink or a silent
#: raise). The pure-extractor membership pins (``_INTENTIONAL_ORPHANS`` /
#: ``_SHIPPED_ORPHANS`` in ``tests/charter_offering/drg/migration/test_extractor_projection.py``)
#: remain the extracted-frame authority; the two frames differ only by
#: ``_ORPHANS_RESOLVED_BY_OVERLAY``. The history of the retired ceiling is in the
#: "Ceiling history" section of the record.


def _orphan_urns(graph: DRGGraph) -> set[str]:
    """Return the URNs of nodes with no inbound and no outbound edge.

    Operates on a loaded :class:`~charter.offering.drg.models.DRGGraph` so the caller can
    read *whatever layout is on disk* through the seam (monolith today, fragments
    post-WP05) rather than re-parsing a hardcoded ``graph.yaml`` path.

    This membership is what binds the live record to the graph (#6513).
    """
    urns = {node.urn for node in graph.nodes}
    incident: set[str] = set()
    for edge in graph.edges:
        incident.add(edge.source)
        incident.add(edge.target)
    return urns - incident


def _documented_orphan_urns(record_path: Path = LIVE_RESIDUAL_RECORD) -> set[str] | None:
    """Return the URNs recorded in the live record's current-state block.

    Only the delimited block counts (see :data:`RESIDUAL_BLOCK_BEGIN`). ``None`` means the
    block itself is absent — a missing file or missing markers — which the guard reports as
    its own failure ("the record has no machine-readable block") instead of blaming 25
    individual URNs for being unrecorded. A present-but-empty block returns an empty set.
    """
    if not record_path.is_file():
        return None
    text = record_path.read_text(encoding="utf-8")
    try:
        start = text.index(RESIDUAL_BLOCK_BEGIN) + len(RESIDUAL_BLOCK_BEGIN)
        end = text.index(RESIDUAL_BLOCK_END, start)
    except ValueError:
        return None
    return set(_URN_SPAN.findall(text[start:end]))


def test_check_reports_committed_graph_fresh() -> None:
    """The shipped graph must be fresh — operator twin of the freshness gate.

    Freshness is asserted via the ``--check`` result (exit 0 + ``status ==
    'fresh'``), not the reported path shape: a ``payload['path'].endswith(
    'graph.yaml')`` assertion would break the instant WP05 replaces the monolith
    with ``*.graph.yaml`` fragments.
    """
    result = runner.invoke(
        charter_app, ["pack", "regenerate-graph", "--check", "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["status"] == "fresh"


def test_regenerate_twice_is_byte_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Write-mode regeneration is deterministic across two runs."""
    # Assemble a working-tree-shaped doctrine root and point the seam at it via
    # SPEC_KITTY_PACKS_ROOT (C1.5). Pre-WP03 this test relied on the CWD
    # ancestor-walk `_doctrine_root()` reimplemented (chdir into `fake_repo`
    # was enough to redirect discovery); WP03 retired that walk in favour of
    # `built_in_root()` (the seam), which resolves from the module's own
    # location and never reads CWD, so redirecting now requires the seam's own
    # override tier instead of chdir (mission
    # doctrine-built-in-seam-consolidation-01KYW3TX, NFR-001 delta).
    fake_repo = tmp_path / "repo"
    fake_doctrine = fake_repo / "packs" / "built-in"
    fake_doctrine.parent.mkdir(parents=True)
    shutil.copytree(DOCTRINE_ROOT, fake_doctrine)
    monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(fake_repo / "packs"))

    r1 = runner.invoke(charter_app, ["pack", "regenerate-graph"])
    assert r1.exit_code == 0, r1.output
    first = {p.name: p.read_bytes() for p in _graph_files(fake_doctrine)}
    assert first, "regenerate-graph produced no graph source files"

    r2 = runner.invoke(charter_app, ["pack", "regenerate-graph"])
    assert r2.exit_code == 0, r2.output
    second = {p.name: p.read_bytes() for p in _graph_files(fake_doctrine)}

    # DD-11: per-file byte-identity over the on-disk graph source (the
    # ``graph.yaml`` monolith today, ``*.graph.yaml`` fragments after WP05).
    assert first == second, "regenerate-graph is not idempotent (per-file byte drift)"


def test_check_detects_stale_graph(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A corrupted committed graph is reported stale with exit code 1."""
    # See test_regenerate_twice_is_byte_identical: SPEC_KITTY_PACKS_ROOT (C1.5)
    # replaces the retired CWD ancestor-walk as the discovery override.
    fake_repo = tmp_path / "repo"
    fake_doctrine = fake_repo / "packs" / "built-in"
    fake_doctrine.parent.mkdir(parents=True)
    shutil.copytree(DOCTRINE_ROOT, fake_doctrine)
    monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(fake_repo / "packs"))

    # Corrupt whichever graph source file is on disk (monolith today, a fragment
    # after WP05) so the committed graph drifts from a fresh regeneration.
    stale_target = _graph_files(fake_doctrine)[0]
    stale_target.write_text(
        stale_target.read_text(encoding="utf-8") + "\n# stale drift marker\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        charter_app, ["pack", "regenerate-graph", "--check", "--json"]
    )
    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    assert payload["status"] == "stale"


def test_documented_residual_matches_measured_shipped_orphans() -> None:
    """The live record's membership must equal the measured shipped orphan set (#6513).

    A numeric ceiling could not see a *raise* or a shrink, so the record's membership is
    the only guard. It fails in both directions — an orphan measured but not recorded fails, and a recorded URN that is
    no longer an orphan fails, so a shrink has to be recorded too.

    The record is the *shipped* frame (``load_built_in_graph()``), matching what the
    guard measures. ``_SHIPPED_ORPHANS`` in
    ``tests/charter_offering/drg/migration/test_extractor_projection.py`` is the
    *pure-extractor* frame; the two differ only by ``_ORPHANS_RESOLVED_BY_OVERLAY``,
    so neither may be "corrected" against the other.
    """
    measured = _orphan_urns(load_built_in_graph())
    documented = _documented_orphan_urns()
    assert documented is not None, (
        f"The live DRG orphan residual record has no machine-readable current-state "
        f"block: {RESIDUAL_BLOCK_BEGIN} … {RESIDUAL_BLOCK_END} not found in "
        f"{LIVE_RESIDUAL_RECORD}. Restore the delimited block (one backticked URN per "
        f"line) rather than removing it — it is what binds this record to the graph."
    )
    undocumented = sorted(measured - documented)
    stale = sorted(documented - measured)
    assert not undocumented and not stale, (
        "The live DRG orphan residual record and the measured shipped graph disagree "
        f"({LIVE_RESIDUAL_RECORD}).\n"
        f"  Measured but not recorded ({len(undocumented)}): {undocumented}\n"
        f"  Recorded but no longer an orphan ({len(stale)}): {stale}\n"
        "Update the record's current-state block in the same change — wire a real inbound edge "
        "first if a genuine referent exists (D-C2 / C-003 forbid deleting or "
        "manufacturing an edge to zero the metric)."
    )


def test_phantom_java_implementer_node_is_absent() -> None:
    """The repaired java-implementer reference must not mint a phantom node."""
    graph = load_built_in_graph()
    urns = {node.urn for node in graph.nodes}
    assert "agent_profile:java-implementer" not in urns
    assert "agent_profile:java-jenny" in urns
