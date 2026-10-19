"""Library reconciliation seam — WP01 (preserve-and-succeed).

This module owns the reconciliation vocabulary and logic that lets
``orchestrator.synthesize`` merge a freshly-emitted project DRG overlay and
synthesis manifest against what is already on disk, instead of rebuilding
both from the current target set and whole-file-swapping them in
(the #3270 defect class).

Public API
----------
- ``SynthesizeMode`` — ``preserve`` (default) / ``prune`` / ``dry_run``.
- ``ReconciliationConflict`` / ``ReconciliationDelta`` — the typed delta
  vocabulary (data-model.md "In-memory value objects").
- ``merge_project_overlay`` / ``rewrite_manifest`` — the canonical merge
  primitives (C-002: reused here AND from ``resynthesize_pipeline.py``; not
  hand-rolled twice).
- ``reconcile_synthesis`` — the seam's main entry point: loads on-disk state,
  merges, classifies preserved-content conflicts, and returns a
  ``ReconciliationOutcome``.
- ``apply_prune`` — minimal ``--prune`` support (excises ``delta.removable``
  from the merged overlay/manifest); WP03 owns the CLI-facing UX.

Import-cycle note
------------------
``charter.activation.synthesizer.synthesize_pipeline`` imports ``SynthesisResult`` from
``.orchestrator``, and ``.manifest`` / ``.provenance`` both import
``synthesize_pipeline``. ``orchestrator.py`` needs ``SynthesizeMode`` as a
*real* (non-lazy) top-level import because it is used as a function-default
value. To keep that safe, this module's OWN top-level imports are limited to
dependency-light, cycle-free surfaces (``charter.offering.drg.*``, stdlib,
``.artifact_naming``, ``charter.bundle``); anything that reaches back into
``.manifest`` / ``.synthesize_pipeline`` / ``.provenance`` is imported lazily
inside the function that needs it — the same lazy-import convention already
used throughout ``orchestrator.py`` and ``project_drg.py``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from charter.offering.drg.loader import DRGLoadError as DRGLoadError  # re-export (FR-007)
from charter.offering.drg.loader import has_graph_files, load_graph_or_dir, merge_layers
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, Relation
from charter.offering.drg.validator import dangling_endpoints, duplicate_edge_triples
from kernel.charter_pack_paths import PROJECT_PACK_ROOT, project_pack_root

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping
    from pathlib import Path

    from .manifest import ManifestArtifactEntry, SynthesisManifest
    from .synthesize_pipeline import ProvenanceEntry

__all__ = [
    "DRGLoadError",
    "NodeOrEdgeRef",
    "ReconciliationConflict",
    "ReconciliationDelta",
    "SynthesizeMode",
    "REACH_ONLY_KINDS",
    "apply_prune",
    "is_synthesized_source_edge",
    "legacy_strip_notice",
    "merge_project_overlay",
    "reconcile_synthesis",
    "rewrite_manifest",
]


class SynthesizeMode(enum.Enum):
    """Selector controlling how ``synthesize()`` treats on-disk divergence.

    ``preserve`` is the library default (decision ``01KZJV6H7TW63M6ZGNM05XKM2S``,
    superseding the earlier refuse-with-prune answer): a plain run never
    silently drops backed content and always exits 0. ``prune``/``dry_run``
    require an explicit opt-in from the caller (WP03's CLI flags).
    """

    preserve = "preserve"
    prune = "prune"
    dry_run = "dry_run"


# ---------------------------------------------------------------------------
# Conflict vocabulary (modeled after -- NOT reusing -- charter.offering.drg.merge's
# OrgDRGConflict / _CONFLICT_REMEDIATIONS shape; different subsystem, distinct
# `kind` names so the two never fork the same Literal string).
# ---------------------------------------------------------------------------

_ReconciliationConflictKind = Literal["duplicate_triple", "preserved_dangling_endpoint"]

#: Per-conflict-class operator remediation. Every ``ReconciliationConflict.kind``
#: needs an entry here -- a class with no remediation hands the operator a
#: label and no way to act on it. Enforced by
#: ``test_every_conflict_class_carries_a_remediation_line`` in
#: ``tests/charter/synthesizer/test_synthesize_reconcile.py`` (mirrors
#: ``charter.offering.drg.merge``'s gate of the same name).
_RECONCILE_REMEDIATIONS: dict[str, str] = {
    "duplicate_triple": (
        "Remediation (duplicate triple): a preserved edge repeats a "
        "(source, target, relation) triple already present in the merged "
        "graph. Remove the duplicate from its backing doctrine artifact, or "
        "drop the stale copy with `spec-kitty charter synthesize --prune`."
    ),
    "preserved_dangling_endpoint": (
        "Remediation (dangling endpoint): a preserved edge references an "
        "endpoint the current run no longer emits. Restore the backing "
        "artifact that defines the endpoint, or remove the edge with "
        "`spec-kitty charter synthesize --prune`."
    ),
}


@dataclass(frozen=True)
class ReconciliationConflict:
    """A single preserved-content conflict surfaced by the reconciliation seam.

    Modeled after (not reusing) ``charter.offering.drg.merge.OrgDRGConflict`` -- that
    type is the org-pack fragment-merge subsystem's closed-``Literal`` shape
    and carries no ``backing_artifact``/``remediation`` fields. This is a new,
    distinct object (data-model.md "ReconciliationConflict").

    ``provenance`` partitions the routing decision WP02 will own:
    ``"preserved"`` conflicts are non-fatal / report-only (the offending
    content came from on-disk, not this run); ``"new_emit"`` conflicts are
    the current run's own output colliding with itself or the built-in layer
    and remain a hard error (unchanged behavior).
    """

    kind: _ReconciliationConflictKind
    target_id: str
    backing_artifact: str | None
    remediation: str
    provenance: Literal["preserved", "new_emit"]

    def __post_init__(self) -> None:
        if not self.remediation:
            raise ValueError(
                f"ReconciliationConflict.kind={self.kind!r} carries no remediation "
                "(every conflict class must be operator-actionable)"
            )


@dataclass(frozen=True)
class NodeOrEdgeRef:
    """A single node or edge reference inside a ``ReconciliationDelta``.

    ``urn`` is the node URN for ``ref_kind="node"``, or a stable
    ``"<source>--<relation>-->target"`` label for ``ref_kind="edge"``.
    ``backing_artifact`` is the repo-relative doctrine artifact path when the
    referenced content is still backed on disk, else ``None`` (orphaned) --
    populated by probing the filesystem, never assumed (amendment #4).
    ``reason`` is set only on a removal the run performs on its own (a legacy
    ``applies`` edge replaced by its ``suggests`` successor, #6404), so the
    operator-facing report names it instead of dropping it silently.
    """

    ref_kind: Literal["node", "edge"]
    urn: str
    backing_artifact: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class ManifestEntryRef:
    """A single manifest artifact reference inside a ``ManifestDelta``."""

    kind: str
    slug: str
    backing_artifact: str | None = None


@dataclass(frozen=True)
class ManifestDelta:
    """Manifest-side counterpart to ``ReconciliationDelta``'s graph fields."""

    retained: tuple[ManifestEntryRef, ...] = ()
    added: tuple[ManifestEntryRef, ...] = ()
    removable: tuple[ManifestEntryRef, ...] = ()


@dataclass(frozen=True)
class ReconciliationDelta:
    """The reconciliation outcome returned to CLI (WP03) and boundary (WP04) callers.

    See data-model.md "ReconciliationDelta (new -- FR-009)".
    """

    retained: tuple[NodeOrEdgeRef, ...] = ()
    added: tuple[NodeOrEdgeRef, ...] = ()
    removable: tuple[NodeOrEdgeRef, ...] = ()
    manifest_delta: ManifestDelta = field(default_factory=ManifestDelta)
    conflicts: tuple[ReconciliationConflict, ...] = ()

    @property
    def is_empty(self) -> bool:
        """True when this run reconciled against a clean/no-op baseline."""
        return not (self.retained or self.added or self.removable or self.conflicts)


@dataclass(frozen=True)
class ReconciliationOutcome:
    """The full result of ``reconcile_synthesis``: what to persist + the delta."""

    merged_overlay: DRGGraph
    merged_manifest: SynthesisManifest
    delta: ReconciliationDelta


# ---------------------------------------------------------------------------
# Shared merge primitives (T002, C-002) -- moved here from
# resynthesize_pipeline.py (behavior-preserving) so both the resynthesize
# path AND the full-synthesize path share ONE implementation.
# resynthesize_pipeline.py re-imports these under its historical private
# names (`_merge_project_overlay`, `_rewrite_manifest`); its call sites and
# behavior are unchanged.
# ---------------------------------------------------------------------------


LEGACY_APPLIES_REASON = "legacy applies edge replaced by suggests"

_DIRECTIVE_URN_PREFIX = "directive:"

#: Kinds a synthesis run links FROM their source directive (``directive --suggests--> <kind>``)
#: so they reach action context only through that edge (#6404 tactics, #6442 styleguides).
REACH_ONLY_KINDS: tuple[str, ...] = ("tactic", "styleguide")
_REACH_ONLY_URN_PREFIXES: tuple[str, ...] = tuple(f"{kind}:" for kind in REACH_ONLY_KINDS)


def synthesized_edge_reason(kind: str, slug: str) -> str:
    """The ``reason`` text synthesis stamps on a reach-only artifact's derived ``suggests`` edge.

    The tactic text is byte-identical to the one #6404 shipped: existing overlays carry it.
    """
    return f"Synthesized {kind} {slug!r} is how this project applies the directive"


def is_synthesized_source_edge(edge: DRGEdge) -> bool:
    """True for the exact shape synthesis derives for a reach-only artifact (#6404, #6442).

    The single "synthesis shape" predicate shared by reconcile ownership and the
    reach-only reader: ``directive:<id> --suggests--> <kind>:<slug>`` for a kind in
    :data:`REACH_ONLY_KINDS`, carrying the reason :func:`synthesized_edge_reason`
    stamps (see ``project_drg._derived_edge``). A hand-authored edge of the same
    relation and endpoints has a different reason and is therefore NOT a synthesized one.
    """
    if edge.relation is not Relation.SUGGESTS or not edge.source.startswith(_DIRECTIVE_URN_PREFIX):
        return False
    kind, _, slug = edge.target.partition(":")
    return kind in REACH_ONLY_KINDS and edge.reason == synthesized_edge_reason(kind, slug)


def edge_owner(edge: DRGEdge, overlay_urns: Collection[str]) -> str | None:
    """Return the overlay node that owns *edge*, or ``None`` when it has none (#6404).

    The single ownership authority for every reconcile call site: an edge
    follows its owner through merge, delta, conflict classification and prune.

    * A synthesized source edge (:func:`is_synthesized_source_edge`) is owned by
      its reach-only *target* (the node synthesis derived it for); its source is a
      built-in or org directive the overlay does not own.
    * Every other edge, including a hand-authored ``directive:* --suggests--> tactic:*``,
      is owned by its source when that is an overlay node (so regenerating the
      *directive* replaces it, and a hand-authored
      ``agent_profile --requires--> tactic:...`` stays with the profile). When its
      source is not an overlay node it has no owner and is preserved untouched, so a
      hand-authored ``procedure --requires--> tactic:...`` survives regeneration of
      that tactic. Prune drops an edge touching a removed node at either end through
      its own explicit check.
    """
    if is_synthesized_source_edge(edge) and edge.target in overlay_urns:
        return str(edge.target)
    if edge.source in overlay_urns:
        return str(edge.source)
    return None


def synthesized_node_urns(manifest: SynthesisManifest) -> frozenset[str]:
    """Node URNs of the non-directive artifacts the synthesis manifest registers.

    Directive nodes are keyed by artifact id, not slug, and never carried the
    legacy ``applies`` edge, so only ``<kind>:<slug>`` URNs are derived.
    """
    return frozenset(f"{e.kind}:{e.slug}" for e in manifest.artifacts if e.kind != "directive")


def _is_legacy_applies(
    edge: DRGEdge,
    synthesized_urns: Collection[str],
    regenerated_urns: Collection[str] | None = None,
) -> bool:
    """A legacy ``<kind> --applies--> ...`` edge on a synthesized reach-only artifact (#6404, #6442).

    Only sources of a kind in :data:`REACH_ONLY_KINDS` qualify: the current shape
    links FROM the directive, so a source-side ``applies`` edge is legacy. With
    *regenerated_urns* given (a topic-scoped run) only an
    owner regenerated in this run qualifies; an untargeted node is left untouched.
    """
    return (
        edge.relation is Relation.APPLIES
        and edge.source.startswith(_REACH_ONLY_URN_PREFIXES)
        and edge.source in synthesized_urns
        and (regenerated_urns is None or edge.source in regenerated_urns)
    )


def legacy_strip_notice(edge: DRGEdge) -> str:
    """Operator-facing line naming one stripped legacy ``applies`` edge (#6404)."""
    return f"{LEGACY_APPLIES_REASON}: {edge.source} --applies--> {edge.target}"


def legacy_applies_edges(
    existing_overlay: DRGGraph,
    synthesized_urns: Collection[str],
    regenerated_urns: Collection[str] | None = None,
) -> tuple[DRGEdge, ...]:
    """Existing legacy ``applies`` edges a run strips (see :func:`_is_legacy_applies`) (#6404)."""
    return tuple(e for e in existing_overlay.edges if _is_legacy_applies(e, synthesized_urns, regenerated_urns))


def merge_project_overlay(
    *,
    existing_overlay: DRGGraph,
    updated_overlay: DRGGraph,
    synthesized_urns: Collection[str] = (),
    topic_scoped: bool = False,
) -> DRGGraph:
    """Replace only the resynthesized nodes/edges inside an existing overlay.

    A node whose URN is present in ``updated_overlay`` is replaced wholesale
    by the updated version; every other on-disk node is preserved untouched.
    Edges follow their owner (:func:`edge_owner`) atomically (FR-002): all of
    a regenerated owner's prior edges are dropped in favor of its fresh set;
    every other owner's edges are preserved untouched.

    Legacy ``applies`` edges sourced at a reach-only-kind node in
    *synthesized_urns* are dropped (#6404); a *topic_scoped* run drops only
    those of owners it regenerated. Callers report them via
    :func:`legacy_applies_edges`.
    """
    updated_urns = {node.urn for node in updated_overlay.nodes}
    updated_nodes_by_urn = {node.urn: node for node in updated_overlay.nodes}
    merged_nodes: list[DRGNode] = []
    for node in existing_overlay.nodes:
        replacement = updated_nodes_by_urn.pop(node.urn, None)
        merged_nodes.append(replacement if replacement is not None else node)
    merged_nodes.extend(updated_nodes_by_urn.values())

    all_urns = {n.urn for n in existing_overlay.nodes} | updated_urns

    def _owner(edge: DRGEdge) -> str:
        return edge_owner(edge, all_urns) or edge.source

    updated_edges_by_owner: dict[str, list[DRGEdge]] = {}
    for edge in updated_overlay.edges:
        updated_edges_by_owner.setdefault(_owner(edge), []).append(edge)

    merged_edges: list[DRGEdge] = []
    inserted_owners: set[str] = set()
    for edge in existing_overlay.edges:
        if _is_legacy_applies(edge, synthesized_urns, updated_urns if topic_scoped else None):
            continue
        owner = _owner(edge)
        if owner not in updated_urns:
            merged_edges.append(edge)
            continue
        if owner in inserted_owners:
            continue
        merged_edges.extend(updated_edges_by_owner.get(owner, []))
        inserted_owners.add(owner)

    for owner, edges in updated_edges_by_owner.items():
        if owner not in inserted_owners:
            merged_edges.extend(edges)

    return DRGGraph(
        schema_version=updated_overlay.schema_version,
        generated_at=updated_overlay.generated_at,
        generated_by=updated_overlay.generated_by,
        nodes=merged_nodes,
        edges=merged_edges,
    )


def rewrite_manifest(
    existing: SynthesisManifest,
    new_results: list[tuple[Mapping[str, Any], ProvenanceEntry]],
    run_id: str,
    repo_root: Path,
) -> SynthesisManifest:
    """Produce a new ``SynthesisManifest`` merging old entries with fresh ones.

    For each artifact in ``new_results``: compute a fresh ``content_hash`` and
    ``provenance_path`` and replace (or insert) the corresponding manifest
    entry. For artifacts NOT in ``new_results``: retain the prior entry
    unchanged (FR-004/FR-017 -- avoids manifest/graph version-skew on a
    partial re-synthesis).
    """
    import hashlib  # noqa: PLC0415 -- lazy: see module docstring's import-cycle note
    from kernel.clock import now_utc_iso  # noqa: PLC0415

    from charter.bundle import compute_bundle_content_hash  # noqa: PLC0415

    from .artifact_naming import artifact_filename, pack_kind_subdir  # noqa: PLC0415
    from .manifest import ManifestArtifactEntry, SynthesisManifest, finalize_manifest  # noqa: PLC0415
    from .provenance import provenance_path_for  # noqa: PLC0415
    from .synthesize_pipeline import _get_synthesizer_version, canonical_yaml  # noqa: PLC0415

    new_entries_by_key: dict[tuple[str, str], ManifestArtifactEntry] = {}
    new_adapter_ids: set[str] = set()
    new_adapter_versions: set[str] = set()

    for body, prov in new_results:
        kind = prov.artifact_kind
        slug = prov.artifact_slug
        artifact_id: str | None = None
        if kind == "directive":
            artifact_id = prov.artifact_urn.split(":", 1)[1]

        filename = artifact_filename(kind, slug, artifact_id)
        yaml_bytes = canonical_yaml(body)
        content_hash = hashlib.sha256(yaml_bytes).hexdigest()  # noqa: TID251 - production raw SHA-256 owner

        rel_content = (PROJECT_PACK_ROOT / pack_kind_subdir(kind) / filename).as_posix()
        rel_prov = provenance_path_for(kind, slug)

        new_entries_by_key[(kind, slug)] = ManifestArtifactEntry(
            kind=kind,
            slug=slug,
            path=rel_content,
            provenance_path=rel_prov,
            content_hash=content_hash,
        )
        new_adapter_ids.add(prov.adapter_id)
        new_adapter_versions.add(prov.adapter_version)

    merged: list[ManifestArtifactEntry] = []
    existing_keys: set[tuple[str, str]] = set()
    for entry in existing.artifacts:
        key = (entry.kind, entry.slug)
        existing_keys.add(key)
        merged.append(new_entries_by_key.get(key, entry))

    for raw_key, new_entry in new_entries_by_key.items():
        if raw_key not in existing_keys:
            merged.append(new_entry)

    if len(new_adapter_ids) == 1:
        primary_adapter_id = new_adapter_ids.pop()
        primary_adapter_version = (
            new_adapter_versions.pop() if len(new_adapter_versions) == 1 else existing.adapter_version
        )
    else:
        primary_adapter_id = existing.adapter_id
        primary_adapter_version = existing.adapter_version

    synthesizer_ver = _get_synthesizer_version()
    sorted_merged = sorted(merged, key=lambda e: (e.kind, e.slug))
    created_at = now_utc_iso()

    manifest = SynthesisManifest(
        mission_id=existing.mission_id,
        created_at=created_at,
        run_id=run_id,
        adapter_id=primary_adapter_id,
        adapter_version=primary_adapter_version,
        synthesizer_version=synthesizer_ver,
        manifest_hash="0" * 64,
        artifacts=sorted_merged,
        bundle_content_hash=compute_bundle_content_hash(repo_root),
    )
    return finalize_manifest(manifest)


def _empty_manifest_seed(run_id: str) -> SynthesisManifest:
    """Seed an empty manifest for ``rewrite_manifest`` on a first-ever synthesize.

    Mirrors the graph reconciliation's "if present" guard (amendment #7):
    there is nothing on disk yet, so the seed carries no artifacts and
    ``rewrite_manifest`` reduces to exactly what the default (non-reconciled)
    manifest builder in ``write_pipeline.promote`` would have produced.
    """
    from kernel.clock import now_utc_iso  # noqa: PLC0415

    from .manifest import SynthesisManifest  # noqa: PLC0415
    from .synthesize_pipeline import _get_synthesizer_version  # noqa: PLC0415

    return SynthesisManifest(
        mission_id=None,
        created_at=now_utc_iso(),
        run_id=run_id,
        adapter_id="",
        adapter_version="",
        synthesizer_version=_get_synthesizer_version(),
        manifest_hash="0" * 64,
        artifacts=[],
        bundle_content_hash=None,
    )


# ---------------------------------------------------------------------------
# Backing-artifact probing (amendment #4: classify backed vs orphaned by
# probing the filesystem, never assuming).
# ---------------------------------------------------------------------------


def _provenance_urn(repo_root: Path, entry: ManifestArtifactEntry) -> str | None:
    """Best-effort read of an artifact's URN from its provenance sidecar."""
    from .provenance import load_yaml as load_provenance  # noqa: PLC0415

    prov_path = repo_root / entry.provenance_path
    if not prov_path.exists():
        return None
    try:
        return str(load_provenance(prov_path).artifact_urn)
    except Exception:  # noqa: BLE001 -- a malformed sidecar must degrade to
        # "unresolvable backing", never crash reconciliation (this is a
        # best-effort probe, not a load-bearing read).
        return None


def _backing_path_by_urn(repo_root: Path, manifest: SynthesisManifest) -> dict[str, str]:
    """Map node URN -> repo-relative backing artifact path, filesystem-verified."""
    mapping: dict[str, str] = {}
    for entry in manifest.artifacts:
        urn = _provenance_urn(repo_root, entry)
        if urn is not None and (repo_root / entry.path).exists():
            mapping[urn] = entry.path
    return mapping


def _node_ref(node: DRGNode, urn_to_path: dict[str, str]) -> NodeOrEdgeRef:
    return NodeOrEdgeRef(ref_kind="node", urn=node.urn, backing_artifact=urn_to_path.get(node.urn))


def _edge_label(edge: DRGEdge) -> str:
    return f"{edge.source}--{edge.relation.value}-->{edge.target}"


def _edge_ref(
    edge: DRGEdge,
    urn_to_path: dict[str, str],
    overlay_urns: Collection[str],
    *,
    reason: str | None = None,
) -> NodeOrEdgeRef:
    owner = edge_owner(edge, overlay_urns)
    return NodeOrEdgeRef(
        ref_kind="edge",
        urn=_edge_label(edge),
        backing_artifact=urn_to_path.get(owner) if owner is not None else None,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# Delta computation
# ---------------------------------------------------------------------------


def _graph_delta(
    *,
    existing_overlay: DRGGraph | None,
    fresh_overlay: DRGGraph,
    urn_to_path: dict[str, str],
    synthesized_urns: Collection[str] = (),
) -> tuple[tuple[NodeOrEdgeRef, ...], tuple[NodeOrEdgeRef, ...], tuple[NodeOrEdgeRef, ...]]:
    """Return (retained, added, removable) graph-level refs."""
    fresh_node_urns = {n.urn for n in fresh_overlay.nodes}
    if existing_overlay is None:
        added = tuple(_node_ref(n, urn_to_path) for n in fresh_overlay.nodes) + tuple(
            _edge_ref(e, urn_to_path, fresh_node_urns) for e in fresh_overlay.edges
        )
        return (), added, ()

    existing_node_urns = {n.urn for n in existing_overlay.nodes}
    overlay_urns = fresh_node_urns | existing_node_urns
    legacy = legacy_applies_edges(existing_overlay, synthesized_urns)

    def _owner_in(edge: DRGEdge, urns: set[str]) -> bool:
        return edge_owner(edge, overlay_urns) in urns

    preserved_refs = tuple(
        _node_ref(n, urn_to_path) for n in existing_overlay.nodes if n.urn not in fresh_node_urns
    ) + tuple(
        _edge_ref(e, urn_to_path, overlay_urns)
        for e in existing_overlay.edges
        if not _owner_in(e, fresh_node_urns) and not _is_legacy_applies(e, synthesized_urns)
    )
    added_refs = tuple(
        _node_ref(n, urn_to_path) for n in fresh_overlay.nodes if n.urn not in existing_node_urns
    ) + tuple(_edge_ref(e, urn_to_path, overlay_urns) for e in fresh_overlay.edges if not _owner_in(e, existing_node_urns))
    stripped_refs = tuple(_edge_ref(e, urn_to_path, overlay_urns, reason=LEGACY_APPLIES_REASON) for e in legacy)
    return preserved_refs, added_refs, preserved_refs + stripped_refs


def _manifest_ref(entry: ManifestArtifactEntry, repo_root: Path) -> ManifestEntryRef:
    backing = entry.path if (repo_root / entry.path).exists() else None
    return ManifestEntryRef(kind=entry.kind, slug=entry.slug, backing_artifact=backing)


def _manifest_delta(
    *,
    existing_manifest: SynthesisManifest,
    merged_manifest: SynthesisManifest,
    new_results: list[tuple[Mapping[str, Any], ProvenanceEntry]],
    repo_root: Path,
) -> ManifestDelta:
    new_keys = {(p.artifact_kind, p.artifact_slug) for _, p in new_results}
    existing_keys = {(e.kind, e.slug) for e in existing_manifest.artifacts}
    merged_by_key = {(e.kind, e.slug): e for e in merged_manifest.artifacts}

    preserved_keys = sorted(existing_keys - new_keys)
    added_keys = sorted(set(merged_by_key) - existing_keys)

    preserved = tuple(_manifest_ref(merged_by_key[key], repo_root) for key in preserved_keys if key in merged_by_key)
    added = tuple(_manifest_ref(merged_by_key[key], repo_root) for key in added_keys)
    return ManifestDelta(retained=preserved, added=added, removable=preserved)


def _edge_conflict(
    kind: _ReconciliationConflictKind,
    edge: DRGEdge,
    target_urns: set[str],
    urn_to_path: dict[str, str],
    overlay_urns: Collection[str],
) -> ReconciliationConflict:
    owner = edge_owner(edge, overlay_urns)
    provenance: Literal["preserved", "new_emit"] = "new_emit" if owner in target_urns else "preserved"
    return ReconciliationConflict(
        kind=kind,
        target_id=_edge_label(edge),
        backing_artifact=urn_to_path.get(owner) if owner is not None else None,
        remediation=_RECONCILE_REMEDIATIONS[kind],
        provenance=provenance,
    )


def _classify_conflicts(
    *,
    merged_overlay: DRGGraph,
    built_in_drg: DRGGraph,
    fresh_overlay: DRGGraph,
    urn_to_path: dict[str, str],
    org_drg: DRGGraph | None = None,
) -> tuple[ReconciliationConflict, ...]:
    """Detect + classify preserved-content conflicts (amendment #3).

    Runs the SAME structured detection ``validation_gate.validate`` will
    subsequently run (via ``validate_graph`` -> these same helpers) against
    the identical merged-with-below-project graph, so a conflict found here
    is exactly what validation would also see -- single source of truth, not
    a second re-implementation.

    *org_drg* (#4121, MAJOR 2) is the org-chain base (built-in + org merged,
    as returned by ``charter.activation._drg_helpers.org_chain_graph``); when supplied
    it substitutes for ``built_in_drg`` as the merge's lower layer, exactly
    as ``validation_gate.validate`` does, so an overlay edge referencing an
    org-pack artifact is not classified as a dangling endpoint here either.
    """
    base_layer = org_drg if org_drg is not None else built_in_drg
    full_graph = merge_layers(base_layer, merged_overlay)
    target_urns = {n.urn for n in fresh_overlay.nodes}
    overlay_urns = {n.urn for n in merged_overlay.nodes}

    conflicts = [
        _edge_conflict("duplicate_triple", edge, target_urns, urn_to_path, overlay_urns)
        for edge in duplicate_edge_triples(full_graph)
    ]
    conflicts.extend(
        _edge_conflict("preserved_dangling_endpoint", edge, target_urns, urn_to_path, overlay_urns)
        for edge in dangling_endpoints(full_graph)
    )
    return tuple(conflicts)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def _load_existing_overlay(pack_dir: Path) -> DRGGraph | None:
    """Load the on-disk project overlay, or ``None`` when there is none yet.

    Fail-closed (FR-007, amendment #2): a *present but unparseable* overlay
    propagates ``DRGLoadError`` uncaught -- the caller must never fall back to
    a wholesale rebuild. A doctrine dir that exists but carries no graph file
    at all (e.g. only artifact-body subdirectories from a prior built-in-only
    run) is legitimately "nothing to reconcile against", not corruption.
    """
    if not pack_dir.exists() or not has_graph_files(pack_dir):
        return None
    graph: DRGGraph = load_graph_or_dir(pack_dir)
    return graph


def reconcile_synthesis(
    *,
    repo_root: Path,
    fresh_overlay: DRGGraph,
    new_results: list[tuple[Mapping[str, Any], ProvenanceEntry]],
    run_id: str,
    built_in_drg: DRGGraph,
    org_drg: DRGGraph | None = None,
) -> ReconciliationOutcome:
    """Reconcile a freshly-emitted overlay + manifest against on-disk state.

    Preserve-mode reconciliation (FR-001/FR-002/FR-004/FR-005/FR-006/FR-009):
    loads the on-disk project overlay and synthesis manifest (if any), merges
    them with the fresh emit via the shared merge primitives, classifies
    preserved-content conflicts against the merged+built-in graph, and
    returns the merged overlay, merged manifest, and the
    ``ReconciliationDelta`` -- including conflicts, populated in-memory (no
    filesystem sidecar; amendment #3).

    Callers persist ``outcome.merged_overlay``/``outcome.merged_manifest``
    unconditionally when they carry content -- this function performs no
    I/O writes itself, only reads.

    *org_drg* (#4121, MAJOR 2) is the org-chain base (built-in + org merged,
    as returned by ``charter.activation._drg_helpers.org_chain_graph``) the fresh
    overlay was emitted against; pass the SAME graph
    ``emit_project_layer`` received so conflict classification and the
    emitter agree on the universe below the project overlay. ``None`` (the
    default, and every pre-#4121 caller) means no org layer is configured.

    Raises
    ------
    charter.offering.drg.loader.DRGLoadError
        When an on-disk project overlay exists but cannot be parsed (FR-007
        fail-closed at the library seam).
    """
    from .manifest import MANIFEST_PATH  # noqa: PLC0415
    from .manifest import load_yaml as load_manifest  # noqa: PLC0415

    # A pure read (see the "performs no I/O writes itself, only reads"
    # docstring note above): the one call site in this module that routes
    # through the temporary dual-root reader (FR-011, removed by WP14). It
    # prefers the project charter pack root and falls back to the retired
    # root (warn-once) only while a project has not been migrated. The
    # manifest bookkeeping paths (`rel_content`) always name the project
    # charter pack root (FR-016).
    pack_dir = project_pack_root(repo_root)
    existing_overlay = _load_existing_overlay(pack_dir)

    manifest_path = repo_root / MANIFEST_PATH
    existing_manifest = load_manifest(manifest_path) if manifest_path.exists() else _empty_manifest_seed(run_id)
    merged_manifest = rewrite_manifest(existing_manifest, new_results, run_id, repo_root)
    synthesized_urns = synthesized_node_urns(merged_manifest)

    merged_overlay = (
        fresh_overlay
        if existing_overlay is None
        else merge_project_overlay(
            existing_overlay=existing_overlay,
            updated_overlay=fresh_overlay,
            synthesized_urns=synthesized_urns,
        )
    )

    urn_to_path = _backing_path_by_urn(repo_root, merged_manifest)
    retained, added, removable = _graph_delta(
        existing_overlay=existing_overlay,
        fresh_overlay=fresh_overlay,
        urn_to_path=urn_to_path,
        synthesized_urns=synthesized_urns,
    )
    manifest_delta = _manifest_delta(
        existing_manifest=existing_manifest,
        merged_manifest=merged_manifest,
        new_results=new_results,
        repo_root=repo_root,
    )
    conflicts = _classify_conflicts(
        merged_overlay=merged_overlay,
        built_in_drg=built_in_drg,
        fresh_overlay=fresh_overlay,
        urn_to_path=urn_to_path,
        org_drg=org_drg,
    )

    delta = ReconciliationDelta(
        retained=retained,
        added=added,
        removable=removable,
        manifest_delta=manifest_delta,
        conflicts=conflicts,
    )
    return ReconciliationOutcome(merged_overlay=merged_overlay, merged_manifest=merged_manifest, delta=delta)


def apply_prune(outcome: ReconciliationOutcome) -> ReconciliationOutcome:
    """Excise ``outcome.delta.removable`` from the merged overlay + manifest.

    Minimal ``--prune`` support (T005): the mode seam exists and performs the
    underlying excision; WP03 owns the CLI-facing UX (listing each deletion,
    confirmation prompts, etc.).
    """
    from .manifest import finalize_manifest  # noqa: PLC0415

    removable_node_urns = {ref.urn for ref in outcome.delta.removable if ref.ref_kind == "node"}
    pruned_nodes = [n for n in outcome.merged_overlay.nodes if n.urn not in removable_node_urns]
    # An edge touching a removed node on either end goes with it (#6404).
    pruned_edges = [
        e
        for e in outcome.merged_overlay.edges
        if e.source not in removable_node_urns and e.target not in removable_node_urns
    ]
    pruned_overlay = outcome.merged_overlay.model_copy(update={"nodes": pruned_nodes, "edges": pruned_edges})

    removable_manifest_keys = {(ref.kind, ref.slug) for ref in outcome.delta.manifest_delta.removable}
    pruned_artifacts = [
        a for a in outcome.merged_manifest.artifacts if (a.kind, a.slug) not in removable_manifest_keys
    ]
    pruned_manifest = finalize_manifest(outcome.merged_manifest.model_copy(update={"artifacts": pruned_artifacts}))

    return ReconciliationOutcome(
        merged_overlay=pruned_overlay,
        merged_manifest=pruned_manifest,
        delta=outcome.delta,
    )
