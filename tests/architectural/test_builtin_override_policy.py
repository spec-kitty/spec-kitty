"""Governance-as-test: built-in DRG overrides must be sanctioned by the repo.

The three-layer merge (:mod:`charter.offering.drg.merge`) PERMITS a same-kind org node
to override a built-in node in place (recorded as a ``node_override`` conflict
with ``resolution_applied == "org_override"`` and a warning). The merge does
NOT decide whether *this* repo sanctions a given override — that is a per-repo
governance decision expressed in ``.kittify/doctrine/replaceable-builtins.yaml``
and in each configured org pack's own ``replaceable-builtins.yaml``.

This architectural test loads the repo's built-in graph plus any configured
org fragments, runs the live merge, and asserts that every built-in URN that
ends up overridden by an org node is sanctioned by the effective policy (the
same loader ``doctor doctrine`` uses). A built-in **directive** override
additionally requires a non-empty reason.

With no overrides authored in this repo, the test passes vacuously (this repo
authors none — its built-in graph is unchanged and no org pack overrides it).
The adjudication logic (:func:`adjudicate_overrides`) is pure and
reusable so a consumer repo can re-run the same governance gate.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.drg.loader import built_in_graph_source, load_graph_or_dir
from charter.offering.drg.merge import merge_three_layers
from charter.offering.drg.models import DRGGraph, DRGNode, NodeKind
from charter.offering.drg.org_pack_loader import OrgDRGFragment
from charter.offering.drg.override_policy import (
    EffectiveOverridePolicy,
    ReplaceableBuiltin,
    ReplaceableBuiltinsPolicy,
    adjudicate_overrides,
    configured_pack_names,
    find_overridden_builtins,
    load_effective_override_policy,
    pack_roots_from_fragments,
)

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
#: Built-in DRG *source directory* (WP03 seam). Pointing at the directory rather
#: than the ``graph.yaml`` file lets ``load_graph_or_dir`` resolve the monolith
#: today and ``*.graph.yaml`` fragments after WP05 — layout-agnostic, no edit.
_BUILT_IN_GRAPH = built_in_graph_source()


def _load_org_fragments(repo_root: Path) -> list[OrgDRGFragment]:
    """Load configured org fragments, tolerating a repo with none.

    The org-pack registry loader lives in the charter layer; the architectural
    suite is allowed to reach across layers. A repo with no ``organisation_packs``
    yields an empty list (the common case, including this repo).
    """
    from charter.activation.drg_activation import load_org_drg

    fragments: list[OrgDRGFragment] = load_org_drg(repo_root)
    return fragments


def test_builtin_overrides_are_sanctioned() -> None:
    """Every built-in override in the live merged graph is sanctioned.

    Vacuously green for this repo (no overrides authored). The assertion logic
    is the governance gate a consumer repo inherits, and it adjudicates through
    the same effective-policy loader as ``doctor doctrine`` (FR-013).
    """
    built_in = load_graph_or_dir(_BUILT_IN_GRAPH)
    org_fragments = _load_org_fragments(_REPO_ROOT)
    pack_roots = pack_roots_from_fragments(org_fragments, _REPO_ROOT)
    effective = load_effective_override_policy(_REPO_ROOT, pack_roots, configured_pack_names=configured_pack_names(_REPO_ROOT, pack_roots))

    try:
        # ``merge_three_layers`` raises only on hard-fail (kind-drift /
        # layer-rule); same-kind overrides are non-fatal and surfaced via the
        # merged graph's org-provenance nodes at built-in URNs. The project layer
        # is deliberately not merged (``project=None``): doctor merges without it
        # and project-tier overrides are ungoverned (C-006), so merging it here
        # could let a project node mask an org override only in the gate.
        merged = merge_three_layers(built_in=built_in, org_fragments=org_fragments, project=None)
    except Exception as exc:  # pragma: no cover - this repo never hard-fails
        pytest.fail(f"Built-in DRG merge hard-failed for this repo (no override expected): {exc}")

    assert effective.pack_errors == ()
    assert effective.consumer_error is None
    assert effective.revocation_errors == ()

    built_in_urns = frozenset(n.urn for n in built_in.nodes)
    overrides = find_overridden_builtins(merged, built_in_urns)
    findings = adjudicate_overrides(overrides, effective).unsanctioned
    assert findings == [], (
        "Unsanctioned built-in override(s) detected. Either add the target URN "
        "to .kittify/doctrine/replaceable-builtins.yaml or to the overriding pack's "
        "own replaceable-builtins.yaml (with a reason for directives) or remove the "
        "override from the org pack:\n" + "\n".join(f"  - {f.urn} ({f.kind}): {f.why}" for f in findings)
    )


def _org_fragment(pack_name: str, nodes: list[dict[str, object]]) -> OrgDRGFragment:
    return OrgDRGFragment.model_validate(
        {
            "pack_name": pack_name,
            "source_kind": "local_path",
            "source_ref": f"/nonexistent/{pack_name}",
            "layer_index": 1,
            "provenance_marker": "org",
            "nodes": nodes,
            "edges": [],
        }
    )


def test_real_merge_override_is_detected_and_governed() -> None:
    """Close the seam between the merge RECORDING an override and the gate
    DETECTING it.

    The live repo test (:func:`test_builtin_overrides_are_sanctioned`) is
    vacuous — this repo authors no overrides, so it would stay green even if
    :func:`find_overridden_builtins` returned ``[]``. This test plants a
    real same-kind org override, runs the *live* ``merge_three_layers``, and
    asserts the detector recovers it AND the governance predicate flags it
    when unlisted / clears it when allowlisted. A regression in the
    provenance-prefix detection (``org:`` / ``in built_in_urns``) fails here.
    """
    built_in = DRGGraph(
        schema_version="1.0",
        generated_at="2026-06-01T00:00:00Z",
        generated_by="unit-test",
        nodes=[DRGNode(urn="tactic:shared", kind=NodeKind.TACTIC, label="Built-in")],
        edges=[],
    )
    org = _org_fragment(
        "rogue",
        nodes=[{"id": "shared", "kind": "tactics", "title": "Override"}],
    )

    merged = merge_three_layers(built_in=built_in, org_fragments=[org], project=None)
    built_in_urns = frozenset(n.urn for n in built_in.nodes)

    # The detector recovers the planted override and its contributing pack (not vacuous).
    overrides = find_overridden_builtins(merged, built_in_urns)
    assert [(o.urn, o.kind, o.pack) for o in overrides] == [("tactic:shared", "tactic", "rogue")]

    # Unlisted -> flagged; allowlisted -> cleared. Both directions load-bearing.
    unlisted = adjudicate_overrides(overrides, _effective(_policy()))
    assert [f.urn for f in unlisted.unsanctioned] == ["tactic:shared"]
    sanctioned = adjudicate_overrides(overrides, _effective(_policy(("tactic:shared", "org tightened this tactic"))))
    assert sanctioned.unsanctioned == []
    assert [(s.urn, s.source) for s in sanctioned.sanctioned] == [("tactic:shared", "consumer")]


def _policy(*entries: tuple[str, str]) -> ReplaceableBuiltinsPolicy:
    return ReplaceableBuiltinsPolicy(entries=tuple(ReplaceableBuiltin(urn=u, reason=r) for u, r in entries))


def _effective(consumer: ReplaceableBuiltinsPolicy) -> EffectiveOverridePolicy:
    return EffectiveOverridePolicy(consumer=consumer, packs={}, pack_errors=())
