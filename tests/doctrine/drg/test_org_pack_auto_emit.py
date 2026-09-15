"""Tests for FR-014 DRG auto-emit on org pack load (WP06 T036).

When a pack artifact declares ``enhances: <id>`` or ``overrides: <id>``,
:func:`charter.offering.drg.org_pack_loader.load_org_pack` MUST auto-emit a matching
edge into the pack's DRG fragment. A hand-authored duplicate of the same edge
contributes once to the merged graph, deduplicated by
``(source, target, relation)`` — see
:class:`charter.offering.drg.merge._OrgEdgeCollector` for why that reconciliation is
owned by the merge rather than by this loader.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.drg.merge import merge_three_layers
from charter.offering.drg.models import DRGGraph, Relation
from charter.offering.drg.org_pack_loader import OrgPackSchemaError, load_org_pack

pytestmark = [pytest.mark.unit, pytest.mark.fast]

#: Re-pinned by the WP08 rejection fold. The FR-014 provenance string is
#: unchanged; what moved is the field it lives on. It used to share ``reason``
#: with a governance author's own rationale, and
#: ``merge._warn_discarded_edge_rationale`` read that shared field as proof an
#: author had written something — so a pack in the sanctioned migration-window
#: shape (a legacy ``enhances:`` field plus the explicit fragment edge that
#: documents it) was warned at for discarding boilerplate the machine wrote.
#: Splitting the field is the fix, so asserting the split is the contract:
#: machine provenance on ``generated_reason``, ``reason`` empty unless a human
#: filled it.
_REASON_IS_AUTHORED_ONLY = (
    "`reason` is reserved for the author's own words — a projection edge must "
    "leave it empty or the merge cannot tell machine provenance from a "
    "governance rationale"
)


def _write_tactic_yaml(
    pack_root: Path,
    *,
    artifact_id: str,
    overrides: str | None = None,
    enhances: str | None = None,
) -> Path:
    """Write a minimal, schema-valid pack tactic with optional augmentation fields."""
    tactics_dir = pack_root / "tactics"
    tactics_dir.mkdir(parents=True, exist_ok=True)
    body_lines = [
        'schema_version: "1.0"',
        f"id: {artifact_id}",
        f"name: {artifact_id.title()}",
    ]
    if overrides is not None:
        body_lines.append(f"overrides: {overrides}")
    if enhances is not None:
        body_lines.append(f"enhances: {enhances}")
    body_lines.extend(
        [
            "steps:",
            "  - title: Single step",
        ]
    )
    yaml_path = tactics_dir / f"{artifact_id}.tactic.yaml"
    yaml_path.write_text("\n".join(body_lines) + "\n", encoding="utf-8")
    return yaml_path


def _write_fragment_yaml(pack_root: Path, body: str) -> Path:
    drg_dir = pack_root / "drg"
    drg_dir.mkdir(parents=True, exist_ok=True)
    fragment_path = drg_dir / "fragment.yaml"
    fragment_path.write_text(body, encoding="utf-8")
    return fragment_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_enhances_auto_emits_drg_edge(tmp_path: Path) -> None:
    """FR-014: `enhances` field surfaces as an ENHANCES edge in the fragment."""
    pack_root = tmp_path / "pack"
    _write_tactic_yaml(
        pack_root,
        artifact_id="pack-tactic",
        enhances="builtin-tactic-id",
    )
    _write_fragment_yaml(
        pack_root,
        body=(
            'pack_name: testpack\n'
            'source_kind: local_path\n'
            'source_ref: "/nonexistent/pack"\n'
            "layer_index: 1\n"
            "nodes: []\n"
            "edges: []\n"
        ),
    )

    fragment = load_org_pack("testpack", pack_root, layer_index=1)

    matching = [
        e
        for e in fragment.edges
        if e.source == "tactic:pack-tactic"
        and e.target == "tactic:builtin-tactic-id"
        and e.relation == Relation.ENHANCES.value
    ]
    assert matching, f"Auto-emitted ENHANCES edge missing. edges={fragment.edges}"
    assert matching[0].generated_reason == "declared via tactic.enhances field"
    assert matching[0].reason is None, _REASON_IS_AUTHORED_ONLY


def test_overrides_auto_emits_drg_edge(tmp_path: Path) -> None:
    """FR-014: `overrides` field surfaces as an OVERRIDES edge in the fragment."""
    pack_root = tmp_path / "pack"
    _write_tactic_yaml(
        pack_root,
        artifact_id="pack-tactic",
        overrides="builtin-tactic-id",
    )
    _write_fragment_yaml(
        pack_root,
        body=(
            'pack_name: testpack\n'
            'source_kind: local_path\n'
            'source_ref: "/nonexistent/pack"\n'
            "layer_index: 1\n"
            "nodes: []\n"
            "edges: []\n"
        ),
    )

    fragment = load_org_pack("testpack", pack_root, layer_index=1)

    matching = [
        e
        for e in fragment.edges
        if e.source == "tactic:pack-tactic"
        and e.target == "tactic:builtin-tactic-id"
        and e.relation == Relation.OVERRIDES.value
    ]
    assert matching, f"Auto-emitted OVERRIDES edge missing. edges={fragment.edges}"
    assert matching[0].generated_reason == "declared via tactic.overrides field"
    assert matching[0].reason is None, _REASON_IS_AUTHORED_ONLY


def _empty_built_in() -> DRGGraph:
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-07-27T00:00:00Z",
        generated_by="test_org_pack_auto_emit",
        nodes=[],
        edges=[],
    )


def test_auto_emit_deduplicates_hand_authored_edge(tmp_path: Path) -> None:
    """FR-014 dedupe: hand-authored copy of the auto-emitted edge lands once.

    Re-pinned by the WP08 fold. The FR-014 intent — one relationship declared
    twice contributes one edge — is unchanged and is what this asserts. What
    moved is *where* it is enforced.

    This used to assert on ``fragment.edges``, i.e. on a dedup the loader
    performed over the RAW endpoint strings. That could only ever collapse the
    byte-identical case exercised below: the projection path emits qualified
    ``<kind>:<id>`` endpoints while an author naturally writes bare ids, and
    the loader cannot resolve a bare id it does not declare (that needs the
    built-in layer). Keeping a partial reconciliation upstream is what made a
    duplicate-emitting merge look reconciled.

    So the assertion follows the guarantee to the merge. The loader now
    reports what the pack literally declares — during the migration window
    that doubled entry is the signal that a leftover ``enhances:`` field is
    still there — and the merge collapses by resolved triple. The bare-vs-
    qualified case the loader never could catch is covered in
    ``tests/doctrine/drg/test_org_drg_bridge.py::TestOneRelationshipYieldsOneEdge``.
    """
    pack_root = tmp_path / "pack"
    _write_tactic_yaml(
        pack_root,
        artifact_id="pack-tactic",
        enhances="builtin-tactic-id",
    )
    _write_fragment_yaml(
        pack_root,
        body=(
            'pack_name: testpack\n'
            'source_kind: local_path\n'
            'source_ref: "/nonexistent/pack"\n'
            "layer_index: 1\n"
            "nodes: []\n"
            "edges:\n"
            "  - source: tactic:pack-tactic\n"
            "    target: tactic:builtin-tactic-id\n"
            "    relation: enhances\n"
        ),
    )

    fragment = load_org_pack("testpack", pack_root, layer_index=1)
    merged = merge_three_layers(_empty_built_in(), [fragment], None)

    matching = [
        e
        for e in merged.edges
        if e.source == "tactic:pack-tactic"
        and e.target == "tactic:builtin-tactic-id"
        and e.relation == Relation.ENHANCES
    ]
    assert len(matching) == 1, (
        f"Hand-authored + auto-emitted edge should collapse to one. "
        f"Found {len(matching)}: {matching}"
    )


def test_no_augmentation_fields_emits_no_extra_edges(tmp_path: Path) -> None:
    """Baseline: pack without `enhances`/`overrides` does not gain auto edges."""
    pack_root = tmp_path / "pack"
    _write_tactic_yaml(pack_root, artifact_id="pack-tactic")
    _write_fragment_yaml(
        pack_root,
        body=(
            'pack_name: testpack\n'
            'source_kind: local_path\n'
            'source_ref: "/nonexistent/pack"\n'
            "layer_index: 1\n"
            "nodes: []\n"
            "edges: []\n"
        ),
    )

    fragment = load_org_pack("testpack", pack_root, layer_index=1)

    assert fragment.edges == []


def test_a_fragment_cannot_forge_machine_provenance(tmp_path: Path) -> None:
    """``generated_reason`` is unwritable from YAML, which is what makes it proof.

    The merge treats "no ``generated_reason``, some ``reason``" as "a human
    wrote this". A flag a fragment author could set would make that inference
    advisory; ``extra="forbid"`` on the author-facing edge schema makes it
    structural — the only way to produce a
    ``_ProjectedOrgDRGEdge`` is the loader's own projection path.
    """
    pack_root = tmp_path / "pack"
    _write_tactic_yaml(pack_root, artifact_id="pack-tactic")
    _write_fragment_yaml(
        pack_root,
        body=(
            'pack_name: testpack\n'
            'source_kind: local_path\n'
            'source_ref: "/nonexistent/pack"\n'
            "layer_index: 1\n"
            "nodes: []\n"
            "edges:\n"
            "  - source: tactic:pack-tactic\n"
            "    target: tactic:builtin-tactic-id\n"
            "    relation: enhances\n"
            "    generated_reason: I am not the machine\n"
        ),
    )

    with pytest.raises(OrgPackSchemaError) as excinfo:
        load_org_pack("testpack", pack_root, layer_index=1)

    assert "generated_reason" in str(excinfo.value), (
        f"the refusal must name the offending key; got {excinfo.value}"
    )


def test_relation_enum_includes_enhances_and_overrides() -> None:
    """T035: `Relation` enum exposes the new augmentation values; REPLACES remains."""
    assert Relation.ENHANCES.value == "enhances"
    assert Relation.OVERRIDES.value == "overrides"
    # Backward compatibility: REPLACES must NOT be removed.
    assert Relation.REPLACES.value == "replaces"
