"""Org-pack chain-delivery verification, both classes (#3530 close).

Mission ``doctrine-drg-silent-drop-boundary-01M0PE7E`` WP05 / T022-T024,
requirements FR-011 (chain delivery) + FR-012 (misconfig fails loud),
contract C-IC5.

Two delivery classes and the enumerated fail-loud contrast:

* **Class-b (fragment-drop, this mission)** — ``test_class_b_*``. Built-in +
  the repo's own ``packs/internal`` (the canonical org shape: a
  ``drg/fragment.yaml`` and no root-level ``*.graph.yaml``). Every kind the
  internal pack declares (glossary pack, procedure, directive) and its
  ``refines`` edges must reach the consumer through the caller seam WP04 fixed
  (``executor.py`` threads ``org_fragments=load_org_drg(repo_root,
  strict=False)`` into ``load_validated_graph``). Before that fix a
  fragment-only pack was silently dropped on this dispatch path — the
  branch-named silent drop this mission closes.

* **Class-a (multi-org-pack fold)** — ``test_class_a_*``. Built-in + internal +
  a SECOND minimal org fixture (``tests/doctrine/fixtures/minimal_org_pack_2``).
  ``merge_three_layers`` iterates ALL fragments (``merge.py:1251``), so a single
  org pack proves only class-b; pinning that fragments PAST THE FIRST are folded
  (finding F10) requires >=2 org packs and an assertion that PACK #2's own
  distinctive node/edge reaches the merged graph. Provenance (``org:minimal-org-2``)
  is the load-bearing proof it came from pack #2 specifically, plus a negative
  control (absent when pack #2 is not registered).

* **Misconfig fails loud (enumerated, FR-012)** — ``test_misconfigured_*``.
  Three faults each RAISE (not warn) with a fault-naming message, contrasted
  with the honest "no graph" WARNING for a genuinely graphless root. The raises
  are asserted against the FAIL-LOUD load path (``load_org_drg`` /
  ``load_validated_graph`` -> ``merge_three_layers``), not the deliberately
  degrade-tolerant executor helper, which swallows a malformed optional org
  tier by design (see ``StepContractExecutor._load_org_fragments_degrading``).

G10 guard: both ``packs/internal`` and ``minimal_org_pack_2`` are
fragment/refines-only and carry NO governance-profile ``selected_*`` selection,
so WP03's org-tier governance guard has nothing to resolve. These tests assert
DELIVERY, not governance fail-loud (WP03's territory) — which is why WP05
depends only on WP04.
"""

from __future__ import annotations

import logging
from pathlib import Path
from textwrap import dedent

import pytest

from charter.activation._drg_helpers import load_validated_graph
from charter.activation.drg_activation import load_org_drg
from charter.offering.drg.merge import OrgDRGConflictError
from charter.offering.drg.models import DRGGraph
from charter.offering.drg.org_pack_loader import OrgPackSchemaError
from specify_cli.mission_step_contracts.executor import StepContractExecutor

pytestmark = [pytest.mark.integration, pytest.mark.doctrine]

_REPO_ROOT: Path = Path(__file__).resolve().parents[2]
_INTERNAL_PACK: Path = _REPO_ROOT / "packs" / "internal"
_MINIMAL_ORG_PACK_2: Path = _REPO_ROOT / "tests" / "doctrine" / "fixtures" / "minimal_org_pack_2"

#: URNs the internal pack contributes (minted ``<singular_kind>:<id>`` from its
#: plural-kinded fragment nodes). One per declared kind — the class-b coverage.
_INTERNAL_DECLARED_URNS: dict[str, str] = {
    "glossary_pack": "glossary_pack:spk-internal-glossary",
    "procedure": "procedure:landing-contributor-prs",
    "directive": "directive:OPERATOR_SIGNAL_CONTRACT",
}

#: The internal pack's ``refines`` edges (source is its own procedure node, both
#: targets are shipped built-in URNs). Each must reach the merged graph.
_INTERNAL_REFINES_EDGES: set[tuple[str, str]] = {
    ("procedure:landing-contributor-prs", "procedure:red-main-release-discipline"),
    ("procedure:landing-contributor-prs", "tactic:pr-agent-worktree-isolation"),
}

#: Pack #2's distinctive node/edge — the class-a fold proof.
_PACK2_MARKER_URN = "directive:MINIMAL_ORG_2_MARKER"
_PACK2_PROVENANCE = "org:minimal-org-2"


def _write_org_config(repo_root: Path, packs: list[tuple[str, Path]]) -> None:
    """Write ``.kittify/config.yaml`` declaring *packs* in the canonical
    ``doctrine.org.packs[]`` shape (``name`` + ``local_path``)."""
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    entries = "".join(f"      - name: {name}\n        local_path: {path}\n" for name, path in packs)
    (kittify / "config.yaml").write_text(f"charter_packs:\n  org:\n    packs:\n{entries}")


def _make_fragment_pack(root: Path, fragment_yaml: str) -> Path:
    """Materialise a one-off org pack shipping only ``drg/fragment.yaml``."""
    (root / "drg").mkdir(parents=True, exist_ok=True)
    (root / "drg" / "fragment.yaml").write_text(fragment_yaml)
    return root


def _merge_via_executor_seam(repo_root: Path) -> DRGGraph:
    """Drive the exact seam WP04 fixed (``executor.py:362``).

    ``StepContractExecutor._load_graph_degrading_malformed_org_pack`` loads the
    org ``drg/fragment.yaml`` layer via ``load_org_drg(repo_root, strict=False)``
    and threads it into ``load_validated_graph`` — the caller path a
    fragment-only pack was previously dropped on. Passing ``org_roots=[]`` (no
    root-graph packs) isolates the fragment-fold behaviour this mission fixes.
    """
    # Typed local absorbs the ``Any`` mypy sees on the executor's static-method
    # return (facade re-export chain), restoring the concrete type without a
    # suppression (Wave4 strict-quarantine boundary pattern).
    merged: DRGGraph = StepContractExecutor._load_graph_degrading_malformed_org_pack(repo_root, org_roots=[])
    return merged


def _merge_via_failloud_apis(repo_root: Path) -> DRGGraph:
    """Load the chain through the FAIL-LOUD APIs (not the degrade-tolerant
    executor): ``load_org_drg`` then ``load_validated_graph`` ->
    ``merge_three_layers``. This is the path on which a misconfigured pack must
    surface as an error rather than being silently degraded away."""
    fragments = load_org_drg(repo_root, strict=False)
    # Typed local absorbs the facade ``Any`` (see :func:`_merge_via_executor_seam`).
    merged: DRGGraph = load_validated_graph(repo_root, org_roots=[], org_fragments=fragments)
    return merged


# ---------------------------------------------------------------------------
# T022 — Class-b: built-in + internal delivers every declared kind
# ---------------------------------------------------------------------------


def test_class_b_internal_pack_delivers_every_declared_kind(tmp_path: Path) -> None:
    """FR-011 / C-IC5 class-b: the repo's own fragment-only ``packs/internal``
    delivers 100% of its declared kinds (glossary pack, procedure, directive)
    AND both ``refines`` edges through the WP04-fixed executor seam."""
    _write_org_config(tmp_path, [("spec-kitty-internal", _INTERNAL_PACK)])

    merged = _merge_via_executor_seam(tmp_path)
    node_urns = merged.node_urns()

    missing = [urn for urn in _INTERNAL_DECLARED_URNS.values() if urn not in node_urns]
    assert not missing, (
        "class-b silent drop: the internal pack's declared kinds did not reach "
        f"the consumer via the executor seam: {missing}. If ALL are missing, "
        "WP04's org_fragments threading is not in the base."
    )

    # Every node from the internal pack is provenance-tagged to that pack.
    for urn in _INTERNAL_DECLARED_URNS.values():
        node = next(n for n in merged.nodes if n.urn == urn)
        assert node.provenance == "org:spec-kitty-internal", (
            f"{urn} reached the graph but is mis-tiered as {node.provenance!r} (F1: an org_roots-seam fix mis-tiers org content as built-in)"
        )

    edge_pairs = {(e.source, e.target) for e in merged.edges}
    missing_edges = _INTERNAL_REFINES_EDGES - edge_pairs
    assert not missing_edges, f"internal pack refines edges did not reach the consumer: {missing_edges}"


def test_class_b_delivery_matches_failloud_api_path(tmp_path: Path) -> None:
    """The executor seam and the direct fail-loud API path deliver the SAME
    internal-pack nodes — proof the executor seam is not quietly narrowing the
    fold relative to the canonical loader."""
    _write_org_config(tmp_path, [("spec-kitty-internal", _INTERNAL_PACK)])

    via_seam = _merge_via_executor_seam(tmp_path).node_urns()
    via_api = _merge_via_failloud_apis(tmp_path).node_urns()

    for urn in _INTERNAL_DECLARED_URNS.values():
        assert urn in via_seam and urn in via_api


# ---------------------------------------------------------------------------
# T023 — Class-a: a SECOND org pack's fragment folds (multi-org-pack path, F10)
# ---------------------------------------------------------------------------


def test_class_a_second_org_pack_fragment_folds(tmp_path: Path) -> None:
    """FR-011 / C-IC5 class-a: in a 2-org-pack chain (internal, then
    minimal-org-2) PACK #2's distinctive fragment node AND its edge reach the
    merged graph — proving fragments past the first are folded (F10). A single
    org pack cannot prove this."""
    _write_org_config(
        tmp_path,
        [
            ("spec-kitty-internal", _INTERNAL_PACK),
            ("minimal-org-2", _MINIMAL_ORG_PACK_2),
        ],
    )

    fragments = load_org_drg(tmp_path, strict=False)
    # Pack #2 is genuinely the SECOND fragment in declaration order.
    assert [f.pack_name for f in fragments] == ["spec-kitty-internal", "minimal-org-2"]

    merged = _merge_via_executor_seam(tmp_path)

    marker = next((n for n in merged.nodes if n.urn == _PACK2_MARKER_URN), None)
    assert marker is not None, (
        "class-a fold failure: pack #2's distinctive node "
        f"{_PACK2_MARKER_URN!r} is absent — fragments past the first were "
        "dropped (contradicts merge_three_layers iterating all fragments)."
    )
    # Provenance pins it to pack #2 specifically, not "some org node".
    assert marker.provenance == _PACK2_PROVENANCE

    marker_edges = {(e.source, e.target) for e in merged.edges if e.source == _PACK2_MARKER_URN}
    assert (_PACK2_MARKER_URN, "procedure:red-main-release-discipline") in marker_edges


def test_class_a_marker_absent_without_second_pack(tmp_path: Path) -> None:
    """Negative control for the class-a proof: with ONLY pack #1 registered,
    pack #2's marker must NOT appear — so its presence in the sibling test is
    genuinely pack #2's contribution, not a fixture leak."""
    _write_org_config(tmp_path, [("spec-kitty-internal", _INTERNAL_PACK)])

    merged = _merge_via_executor_seam(tmp_path)
    assert _PACK2_MARKER_URN not in merged.node_urns()


# ---------------------------------------------------------------------------
# T024 — Enumerated misconfig fail-loud (raise), contrasted with a warn
# ---------------------------------------------------------------------------

_MISCONFIG_CASES: list[tuple[str, str, type[Exception], tuple[str, ...]]] = [
    (
        # (i) refines edge -> nonexistent built-in target. Authored as a bare
        # id that resolves to nothing (not fragment-local, not a valid URN, no
        # built-in match) -> merge hard-fails naming the token, rather than
        # minting a phantom node. Raises at load_validated_graph -> merge.
        "nonexistent_refine_target",
        dedent(
            """\
            pack_name: bad-endpoint
            source_kind: local_path
            source_ref: x
            layer_index: 1
            provenance_marker: org
            nodes:
              - id: my-node
                kind: directives
                title: t
            edges:
              - source: my-node
                target: nonexistent-refine-target-xyz
                relation: refines
            """
        ),
        OrgDRGConflictError,
        ("nonexistent-refine-target-xyz", "unresolved_edge_endpoint"),
    ),
    (
        # (ii) missing required key: a node without its required ``kind`` field.
        # The fragment schema (``_OrgDRGNode``) rejects it at load time.
        "missing_required_key",
        dedent(
            """\
            pack_name: missing-key
            source_kind: local_path
            source_ref: x
            layer_index: 1
            provenance_marker: org
            nodes:
              - id: my-node
                title: t
            """
        ),
        OrgPackSchemaError,
        ("kind",),
    ),
    (
        # (iii) declared kind with no node: a node whose declared ``kind`` is
        # not in the canonical org-pack kind universe, so no real node can be
        # minted for it. Rejected at load time naming the offending kind.
        "declared_kind_with_no_node",
        dedent(
            """\
            pack_name: bad-kind
            source_kind: local_path
            source_ref: x
            layer_index: 1
            provenance_marker: org
            nodes:
              - id: my-node
                kind: notarealkind
                title: t
            """
        ),
        OrgPackSchemaError,
        ("unknown kind", "notarealkind"),
    ),
]


@pytest.mark.parametrize(
    ("case_id", "fragment_yaml", "exc_type", "message_fragments"),
    _MISCONFIG_CASES,
    ids=[c[0] for c in _MISCONFIG_CASES],
)
def test_misconfigured_pack_in_chain_fails_loud(
    tmp_path: Path,
    case_id: str,
    fragment_yaml: str,
    exc_type: type[Exception],
    message_fragments: tuple[str, ...],
) -> None:
    """FR-012 / C-IC5: each enumerated misconfig RAISES (not warns) through the
    fail-loud load path, with a message naming the fault — so a chain never
    reports success over an inert pack."""
    pack_root = _make_fragment_pack(tmp_path / case_id, fragment_yaml)
    _write_org_config(tmp_path, [(case_id, pack_root)])

    with pytest.raises(exc_type) as excinfo:
        _merge_via_failloud_apis(tmp_path)

    message = str(excinfo.value)
    for fragment in message_fragments:
        assert fragment in message, f"{case_id}: {exc_type.__name__} did not name {fragment!r}: {message}"


def test_misconfig_raise_is_not_the_graphless_warn(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """C-IC5 contrast: a genuinely graphless root (no root ``*.graph.yaml`` and
    no ``drg/fragment.yaml``) is an honest "no graph" case — it WARNS and the
    merged graph still loads. This is the deliberate non-raise the enumerated
    misconfigs above must be distinguished from."""
    graphless = tmp_path / "graphless"
    graphless.mkdir()

    with caplog.at_level(logging.WARNING, logger="charter._drg_helpers"):
        merged = load_validated_graph(tmp_path, org_roots=[graphless], org_fragments=[])

    # No raise; the built-in layer is still delivered.
    assert merged.nodes
    assert any("ships no root-level DRG graph" in record.getMessage() for record in caplog.records), "graphless root must emit the honest 'no graph' WARNING"
