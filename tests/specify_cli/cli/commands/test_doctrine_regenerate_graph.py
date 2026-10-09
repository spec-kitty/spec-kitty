"""CLI tests for ``spec-kitty doctrine regenerate-graph`` (WP09 / FR-009).

Covers the operator-facing regeneration surface:

1. ``--check --json`` reports the committed shipped graph as fresh (exit 0),
2. regenerate-twice produces byte-identical output (determinism),
3. ``--check`` against a deliberately corrupted graph reports stale (exit 1).

The committed ``src/charter/offering/graph.yaml`` is never mutated: write-mode tests
target a temporary doctrine root assembled from the shipped one.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from charter.offering.drg.loader import load_built_in_graph
from specify_cli.cli.commands.doctrine import app as doctrine_app

if TYPE_CHECKING:
    from charter.offering.drg.models import DRGGraph

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()

# The sharded ``*.graph.yaml`` DRG fragments relocated from ``src/doctrine`` to
# the top-level ``packs/built-in`` pack root (mission relocate-builtin-doctrine-packs);
# regenerate-graph resolves and rewrites them there.
DOCTRINE_ROOT = Path(__file__).resolve().parents[4] / "packs" / "built-in"


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

#: WP05 / FR-009 / C-003 — orphan-count regression ceiling.
#:
#: After repairing the phantom ``java-implementer`` reference and wiring the
#: refactoring-procedure → Fowler-catalog and mutation-workflow → mutation-tools
#: inbound edges, the shipped DRG carried 14 orphaned-but-valid doctrine
#: artifacts. Each is a deliberately-authored artifact with no single natural
#: referent and is documented (with per-orphan rationale) in
#: ``kitty-specs/mission-lifecycle-dispatch-drg-closeout-01KV0S99/drg-orphan-residual.md``.
#:
#: 2026-07-16 (ceiling stays 14; empirical residual 10): an interim curation pass
#: had briefly raised this to 18 to *accept* 8 structural mission-type nodes
#: (``mission_type:{documentation,plan,research,software-dev}`` +
#: ``action:plan/{plan,research,review,specify}``) as edgeless residuals, because
#: the generator emitted mission-type nodes nodes-only pending a deferred
#: S0-continuation edge feature. **Mission ``mission-type-drg-edges-01KXKY2N``
#: (#2677) implemented that feature**: the generator now emits
#: ``mission_type:X → action:X/<step>`` ``requires`` edges from each type's
#: ``action_sequence`` (21 edges), so all 8 structural nodes are wired and leave
#: the orphan set — the 18 raise is reverted to 14. In the same pass 4 of the
#: original residuals were found already-wired (stale rows), taking the empirical
#: residual from 14 to **10**. Full narrative + the 10 surviving rows are in
#: ``drg-orphan-residual.md``.
#:
#: D-C2 / C-003 forbid deleting valid orphans to shrink this metric. This ceiling
#: is a regression guard against the count silently *growing* — a new orphan must
#: either be wired or added to the documented residual (and this ceiling raised
#: with a rationale). It is NOT a mandate to prune to reach a lower number.
#:
#: Mission ``doctrine-controlled-transition-gates`` (epic #2535 half A) shipped the
#: 17 built-in ``mission_step_contract:<mission>/<action>`` nodes as intentionally
#: edge-less residuals: the MSC fragment ships ``edges: []`` because the activation
#: join gates on the node's *presence*, not on edges. That raises the ceiling from
#: the historical 14 baseline to 29 (empirical 29, no slack). Full narrative in
#: ``drg-orphan-residual.md``.
#:
#: 2026-07-26 (PR #2936 fold): #2936 promoted ``toolguide:powershell-syntax`` from a
#: dead, unreachable file into a live graph node with no inbound/outbound edge (real
#: PowerShell-authoring content, consumed at runtime, no doctrinal static referent —
#: same class as the then-existing ``toolguide:rtk-search-tooling`` /
#: ``toolguide:python-review-checks`` residuals). Accepted as an edge-less residual per
#: D-C2 / C-003 rather than a manufactured edge. Raised the ceiling 29 -> 30. Full
#: narrative in ``drg-orphan-residual.md``.
#:
#: 2026-07-28 (PR #3007 landing folds, operator ruling on #3009): ratcheted
#: 30 -> 21, measured. BOTH residuals the 2026-07-26 note cites are gone --
#: ``rtk-search-tooling`` was DELETED outright and ``python-review-checks`` was
#: WIRED (``styleguide:python-conventions --suggests-->``), along with six other
#: activated-but-unreachable artefacts. The ceiling stayed green at 30 through
#: all of that because a ceiling cannot see a shrink, which is exactly why it is
#: being ratcheted rather than left with nine points of silent slack. The
#: authoritative membership record is ``_INTENTIONAL_ORPHANS`` in
#: ``tests/doctrine/drg/migration/test_extractor_projection.py`` (pure-extractor
#: view, 23); this ceiling is the shipped-graph view (21) and the two differ by
#: the hand-authored overlay, per that module's own stated cause.
#:
#: 2026-07-31 (mission charter-delivery-finish-context-degod, #3064, post-merge
#: follow-up): WP03's ``asset:common-charter-scaffold-minimal`` doctrine asset was
#: relocated to first-class charter-pack status (today the built-in ``minimal`` preset,
#: applied via ``spec-kitty charter activate --preset minimal``) — it is structurally a
#: charter pack, not a generic doctrine asset. The asset node is gone from the DRG,
#: reverting the ceiling **22 -> 21**. Full narrative in ``drg-orphan-residual.md``.
#:
#: Mission drg-reachability-metric-wiring-01KZS5VR (WP01, #3009 point 3): the six
#: curated edges de-orphan three pure-extractor nodes (``directive:RECONCILE_
#: CHANGE_SCOPE_TENSIONS``, ``directive:DISCIPLINED_REFACTORING``,
#: ``directive:USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY`` — see
#: ``tests/doctrine/drg/migration/test_extractor_projection.py`` ledger entry
#: 19), but all three were ALREADY resolved by the hand-authored overlay in the
#: *shipped* graph, so ``_orphan_urns(load_built_in_graph())`` measures
#: UNCHANGED at 21 — verified empirically, not assumed. The ceiling is already
#: tight (no leftover slack) both before and after this wiring; it is NOT
#: ratcheted, because there is nothing to ratchet down to.
DOCUMENTED_ORPHAN_RESIDUAL = 21


def _count_orphans(graph: DRGGraph) -> int:
    """Return the number of nodes with no inbound or outbound edge.

    Operates on a loaded :class:`~charter.offering.drg.models.DRGGraph` so the caller can
    read *whatever layout is on disk* through the seam (monolith today, fragments
    post-WP05) rather than re-parsing a hardcoded ``graph.yaml`` path.
    """
    urns = {node.urn for node in graph.nodes}
    incident: set[str] = set()
    for edge in graph.edges:
        incident.add(edge.source)
        incident.add(edge.target)
    return len(urns - incident)


def test_check_reports_committed_graph_fresh() -> None:
    """The shipped graph must be fresh — operator twin of the freshness gate.

    Freshness is asserted via the ``--check`` result (exit 0 + ``status ==
    'fresh'``), not the reported path shape: a ``payload['path'].endswith(
    'graph.yaml')`` assertion would break the instant WP05 replaces the monolith
    with ``*.graph.yaml`` fragments.
    """
    result = runner.invoke(
        doctrine_app, ["regenerate-graph", "--check", "--json"]
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

    r1 = runner.invoke(doctrine_app, ["regenerate-graph"])
    assert r1.exit_code == 0, r1.output
    first = {p.name: p.read_bytes() for p in _graph_files(fake_doctrine)}
    assert first, "regenerate-graph produced no graph source files"

    r2 = runner.invoke(doctrine_app, ["regenerate-graph"])
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
        doctrine_app, ["regenerate-graph", "--check", "--json"]
    )
    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    assert payload["status"] == "stale"


def test_shipped_graph_orphan_count_within_documented_residual() -> None:
    """Orphan count must not exceed the documented residual (WP05 / C-003).

    Guards against orphan growth without forcing valid-artifact deletion: a new
    orphan must be wired or added to the documented residual (raising the
    ceiling with rationale), per the no-bulk-delete correction (D-C2).
    """
    orphans = _count_orphans(load_built_in_graph())
    assert orphans <= DOCUMENTED_ORPHAN_RESIDUAL, (
        f"DRG orphan count {orphans} exceeds documented residual "
        f"{DOCUMENTED_ORPHAN_RESIDUAL}; wire a real inbound edge or update "
        f"drg-orphan-residual.md and raise the ceiling with rationale."
    )


def test_phantom_java_implementer_node_is_absent() -> None:
    """The repaired java-implementer reference must not mint a phantom node."""
    graph = load_built_in_graph()
    urns = {node.urn for node in graph.nodes}
    assert "agent_profile:java-implementer" not in urns
    assert "agent_profile:java-jenny" in urns
