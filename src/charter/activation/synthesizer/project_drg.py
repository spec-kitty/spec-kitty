"""Project-level DRG overlay writer.

Thin composer over ``src/charter/offering/drg`` primitives (KD-1 rule: no reusable
graph logic here — push any generic graph logic to ``src/charter/offering/drg/``
instead).

Public API:

- ``emit_project_layer(targets, adapter_outputs, spec_kitty_version,
                       built_in_drg) -> DRGGraph``
  Builds a ``DRGGraph`` for the project-local overlay.  Raises
  ``ProjectDRGValidationError`` on additive-only violations (FR-020 / EC-6).

- ``persist(graph, staging_dir, guard)``
  Serializes the graph under ``staging_dir/doctrine`` via the supplied
  ``PathGuard``. The promote step (WP03) will move this file to the live
  project doctrine directory.

See data-model.md §E-5 for the overlay discipline.
"""

from __future__ import annotations

import io
import logging
from collections.abc import Sequence
from pathlib import Path

from ruamel.yaml import YAML

from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.drg.migration.extractor import graph_document_to_dict, model_to_graph_dict
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation
from charter.offering.drg.project_scan import (walk_project_agent_profile_nodes, scan_project_artifacts, project_reference_edges, ProjectArtifact)

from charter.activation.synthesizer._constants import GRAPH_FILENAME as _GRAPH_FILENAME
from kernel.clock import now_utc_seconds
from kernel.charter_pack_paths import PROJECT_PACK_DIRNAME, project_pack_root

from .errors import ProjectDRGValidationError
from .path_guard import PathGuard
from .request import SynthesisTarget


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

#: The emittable project-tier kind allowlist: kinds that become project-overlay
#: DRG nodes, mapped to the ``NodeKind`` they carry. Its *keys* ARE the contract
#: — a kind's **absence** is deliberate, not an oversight: ``asset`` (#3037),
#: ``procedure``, ``paradigm``, ``toolguide``, ``glossary_pack``,
#: ``mission_step_contract``, ``template`` and ``anti_pattern`` are intentionally
#: not emitted at the project tier. ``AGENT_PROFILE`` was admitted in M6 (#3038)
#: so a hand-authored project profile becomes a cascade-reachable node.
#:
#: ``ArtifactKind``-keyed (not string-keyed) so the totality gate
#: (``tests/doctrine/drg/test_kind_mapping_totality.py``) is *guard-visible* to
#: it. The map is a deliberate partial listed in that gate's
#: ``_EXEMPT_GET_PARTIALS`` (the sole read site :func:`_node_kind_for` reads via
#: ``.get``, treating a miss as "not emitted at the project tier"), so this
#: entry itself never reddens the enum-keyed guard. The protection is indirect:
#: a future ``ArtifactKind`` reddens the *non-exempt* authority tables
#: (``PROJECT_KIND_DIRS`` et al.), forcing a developer through the kind surface
#: — at which point the decision to emit it at the project tier (extend this
#: map) or not (leave it out) is a conscious one, not a silent omission.
#:
#: NOTE: the ``AGENT_PROFILE`` entry drives the *answer-driven* synthesis-target
#: path (:func:`_node_kind_for`); the hand-authored filesystem-walk path
#: (:func:`charter.offering.drg.project_scan.walk_project_agent_profile_nodes`)
#: hardcodes ``NodeKind.AGENT_PROFILE`` directly. The answer-driven path does
#: not produce ``agent_profile`` targets today (interview sections map only to
#: directive/tactic/styleguide), so the entry primarily buys gate visibility and
#: forward-compatibility rather than an active answer-driven emission.
_KIND_TO_NODE_KIND: dict[ArtifactKind, NodeKind] = {
    ArtifactKind.DIRECTIVE: NodeKind.DIRECTIVE,
    ArtifactKind.TACTIC: NodeKind.TACTIC,
    ArtifactKind.STYLEGUIDE: NodeKind.STYLEGUIDE,
    ArtifactKind.AGENT_PROFILE: NodeKind.AGENT_PROFILE,
}


def _node_kind_for(kind: str) -> NodeKind | None:
    """Return the ``NodeKind`` for a synthesis-target/project *kind*, or ``None``.

    Normalizes the *kind* string to an :class:`~charter.offering.artifact_kinds.ArtifactKind`
    (an unknown string → ``None``), then reads :data:`_KIND_TO_NODE_KIND` via
    ``.get`` (not a raising subscript). A kind outside the emittable
    project-tier allowlist — including the mission-tier ``template`` and
    loose-contract ``asset`` members — resolves to ``None``. Callers
    (:func:`emit_project_layer`) treat ``None`` as "skip this target's node and
    edges" so an unsupported kind never crashes project-DRG emission (WP06).
    """
    try:
        artifact_kind = ArtifactKind(kind)
    except ValueError:
        return None
    return _KIND_TO_NODE_KIND.get(artifact_kind)


def _node_to_dict(node: DRGNode) -> dict[str, object]:
    """Serialise one overlay ``DRGNode`` via the derived ``model_to_graph_dict``.

    T005: repointed from the T003 hand-restated shape at the canonical derived
    writer. The old shape restated ``{kind, urn, label}`` and silently dropped
    the declared ``DRGNode.tags`` field; deriving from ``model_fields`` closes
    that — and any field a later mission adds is emitted without editing here.
    Registered as a ``MappingWriter`` in ``specify_cli.drg_writers.registry``.
    """
    return dict(model_to_graph_dict(node))


def _edge_to_dict(edge: DRGEdge) -> dict[str, object]:
    """Serialise one overlay ``DRGEdge`` via the derived ``model_to_graph_dict``.

    T005 counterpart to :func:`_node_to_dict`.
    """
    return dict(model_to_graph_dict(edge))


def _document_dict(graph: DRGGraph) -> dict[str, object]:
    """Serialise a whole ``DRGGraph`` document via the canonical derived writer.

    Standalone/addressable for ``specify_cli.drg_writers.registry``'s
    ``DOCUMENT_WRITERS`` member -- T020/T021 counterpart to
    :func:`_node_to_dict`/:func:`_edge_to_dict` above. ``graph_document_to_dict``
    already recurses ``nodes``/``edges`` through :func:`model_to_graph_dict`
    internally, so this module's separate node/edge helpers are not called
    from here (they remain registered ``MappingWriter`` members used
    elsewhere).
    """
    return dict(graph_document_to_dict(graph))


def _serialize_graph(graph: DRGGraph) -> str:
    """Return a canonical YAML string for *graph* with sorted keys."""
    payload = _document_dict(graph)

    yaml = YAML()
    yaml.default_flow_style = False
    buf = io.StringIO()
    yaml.dump(payload, buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _append_project_profile_nodes(
    *,
    project_root: Path,
    nodes: list[DRGNode],
    seen_urns: set[str],
    built_in_node_urns: frozenset[str],
    built_in_node_count: int,
) -> None:
    """Append hand-authored project agent_profile nodes through the overlay guards.

    Walks ``<project_root>/.kittify/charter-packs/agent_profiles/`` (M6 / #3038) and
    merges the discovered ``agent_profile:<id>`` nodes into *nodes* in place,
    applying the same additive-only and overlay-dedupe invariants the
    answer-driven loop enforces:

    * **Additive-only (INV-1)** — a URN already present in the built-in layer
      raises :class:`ProjectDRGValidationError` (a project profile must not
      shadow a built-in node).
    * **Dedupe (INV-2)** — a URN already emitted in this overlay (by an
      answer-driven target or an earlier walked file with the same
      ``profile-id``) is skipped, so each ``agent_profile:<id>`` appears once.

    The walk itself fails loud on a malformed profile file (INV-6 / NFR-002).
    """
    for node in walk_project_agent_profile_nodes(project_root):
        urn = node.urn
        if urn in built_in_node_urns:
            raise ProjectDRGValidationError(
                errors=(
                    f"Additive-only violation (INV-1): project agent_profile URN "
                    f"'{urn}' already exists in the built-in DRG layer.  A "
                    f"hand-authored project profile must carry a new URN disjoint "
                    f"from built-in nodes.",
                ),
                merged_graph_summary=(
                    f"built_in_nodes={built_in_node_count}, colliding_urn={urn!r}"
                ),
            )
        if urn in seen_urns:
            continue  # INV-2 overlay dedupe: emit each agent_profile:<id> once.
        seen_urns.add(urn)
        nodes.append(node)



def _registered_project_artifacts(project_root: Path) -> tuple[ProjectArtifact, ...]:
    """Re-emit direct-write registrations; synthesis-owned artifacts follow targets."""
    from .manifest import MANIFEST_PATH, load_yaml as load_manifest
    from .provenance import load_yaml as load_provenance

    manifest_path = project_root / MANIFEST_PATH
    if not manifest_path.exists():
        return ()
    manifest = load_manifest(manifest_path)
    paths = frozenset(
        project_root / entry.path for entry in manifest.artifacts
        if (project_root / entry.provenance_path).exists()
        and load_provenance(project_root / entry.provenance_path).adapter_id == "project-direct-write"
    )
    return scan_project_artifacts(project_root, paths=paths)


def emit_project_layer(
    targets: Sequence[SynthesisTarget],
    spec_kitty_version: str,
    built_in_drg: DRGGraph,
    project_root: Path | None = None,
    *,
    org_drg: DRGGraph | None = None,
    warnings_out: list[str] | None = None,
) -> DRGGraph:
    """Build an additive project-layer ``DRGGraph`` from *targets*.

    One node is emitted per target; edges are derived from each target's
    ``source_urns`` (direction: project node ``derived_from``/``requires``
    the source URN per existing DRG conventions).

    When *project_root* is supplied, hand-authored project-tier ``agent_profile``
    artefacts under ``<project_root>/.kittify/charter-packs/agent_profiles/`` are also
    walked and appended as ``agent_profile:<id>`` nodes (M6 / #3038), through the
    same additive-only / overlay-dedupe guards. When *project_root* is ``None``
    the emit is answer-driven-only (pre-M6 behaviour, unchanged).

    FR-020 / EC-6 additive-only enforcement:

    * A target whose URN is already present in ``built_in_drg.nodes`` raises
      ``ProjectDRGValidationError`` — synthesized artifacts carry *new* URNs;
      they do not shadow built-in URNs.
    * Any ``(source, target, relation)`` triple that already exists in
      ``built_in_drg.edges`` raises ``ProjectDRGValidationError`` — no
      duplicate edges allowed.

    A target whose ``kind`` is not a synthesizable node kind (see
    :func:`_node_kind_for` — only ``directive``/``tactic``/``styleguide`` are
    synthesis targets today) is skipped: neither its node nor its edges are
    emitted (WP06 charter-cascade exhaustiveness — an unsupported kind must
    not crash emission).

    Org-aware reference resolution (#4121, MAJOR 2): profile references are
    projected against the SAME universe activation resolves against —
    built-in + the org chain + the overlay's own nodes — instead of a
    built-in-only one, so a project profile referencing an org-pack artifact
    keeps its edge through re-emission rather than having it silently
    replaced away by :func:`charter.activation.synthesizer.reconcile.merge_project_overlay`.
    *org_drg* is that org-chain base (the built-in + org graph returned by
    :func:`charter.activation._drg_helpers.org_chain_graph`); ``None`` means
    no org layer is configured and the universe is built-in + overlay only,
    byte-identical to the pre-#4121 behaviour.

    Args:
        targets: Ordered sequence of ``SynthesisTarget`` objects to emit.
        spec_kitty_version: Version string embedded in ``generated_by``.
        built_in_drg: The built-in-layer ``DRGGraph`` used for additive-only
            checks.  **Not mutated.**
        project_root: Project root for hand-authored profile/registered-
            artifact composition (see above).
        org_drg: The org-chain base graph (built-in + org merged, as returned
            by :func:`charter.activation._drg_helpers.org_chain_graph`), or ``None``
            when no org packs are configured. Used ONLY for the
            reference-resolution universe — the additive-only checks stay
            built-in-only, because an org node may legitimately be overridden
            by the project layer (``merge_three_layers`` precedence) while a
            built-in node may not. **Not mutated.**
        warnings_out: Optional sink that receives the unresolved-reference
            warnings (the same strings logged below) so CLI callers can
            surface them instead of them living only in ``logging`` output.

    Returns:
        A new ``DRGGraph`` representing the project overlay.  The caller
        (typically ``validation_gate.validate``) is responsible for running
        ``merge_layers`` + ``validate_graph`` before persisting.

    Raises:
        ProjectDRGValidationError: If any additive-only invariant is violated.
    """
    now_iso = now_utc_seconds()
    generated_by = f"spec-kitty charter synthesize {spec_kitty_version}"

    # Build indexes for additive-only checks.
    built_in_node_urns: frozenset[str] = frozenset(n.urn for n in built_in_drg.nodes)
    built_in_edge_triples: frozenset[tuple[str, str, str]] = frozenset(
        (e.source, e.target, e.relation.value) for e in built_in_drg.edges
    )

    nodes: list[DRGNode] = []
    edges: list[DRGEdge] = []
    seen_urns: set[str] = set()  # tracks overlay-internal duplicates

    for target in targets:
        urn = target.urn

        # WP06: unsupported target kinds (not directive/tactic/styleguide —
        # including the mission-tier ``template`` and loose-contract ``asset``
        # ArtifactKind members) are skipped rather than crashing emission.
        node_kind = _node_kind_for(target.kind)
        if node_kind is None:
            continue

        # FR-020 / EC-6: reject URNs that collide with built-in nodes.
        if urn in built_in_node_urns:
            raise ProjectDRGValidationError(
                errors=(
                    f"Additive-only violation (FR-020 / EC-6): URN '{urn}' "
                    f"already exists in the built-in DRG layer.  Synthesized "
                    f"artifacts must carry new URNs disjoint from built-in nodes.",
                ),
                merged_graph_summary=(
                    f"built_in_nodes={len(built_in_drg.nodes)}, "
                    f"colliding_urn={urn!r}"
                ),
            )

        # Overlay-internal duplicate guard.
        if urn in seen_urns:
            raise ProjectDRGValidationError(
                errors=(
                    f"Duplicate project-layer URN '{urn}': each target must "
                    f"produce a distinct URN within one synthesis run.",
                ),
                merged_graph_summary=(
                    f"colliding_urn={urn!r}"
                ),
            )
        seen_urns.add(urn)

        node = DRGNode(
            urn=urn,
            kind=node_kind,
            label=target.title,
        )
        nodes.append(node)

        # Derive edges from source_urns: project node *derived_from* (or
        # *requires* for directives) the upstream built-in/project URN.
        for source_urn in target.source_urns:
            relation = (
                Relation.REQUIRES if target.kind == "directive"
                else Relation.APPLIES
            )
            triple = (urn, source_urn, relation.value)

            # FR-020: reject edges whose triple already exists in built-in.
            if triple in built_in_edge_triples:
                raise ProjectDRGValidationError(
                    errors=(
                        f"Duplicate edge (FR-020 / EC-6): triple "
                        f"({urn!r} --{relation.value}--> {source_urn!r}) "
                        f"already exists in the built-in DRG layer.",
                    ),
                    merged_graph_summary=(
                        f"colliding_edge=({urn} --{relation.value}--> {source_urn})"
                    ),
                )

            edge = DRGEdge(
                source=urn,
                target=source_urn,
                relation=relation,
                reason=f"Derived from synthesis target {target.slug!r}",
            )
            edges.append(edge)

    # M6 (#3038): compose hand-authored project agent_profile nodes. These are
    # artefact-driven (no synthesis answer), so they only appear when a
    # project_root is threaded from the caller's write/preview seam.
    if project_root is not None:
        _append_project_profile_nodes(
            project_root=project_root,
            nodes=nodes,
            seen_urns=seen_urns,
            built_in_node_urns=built_in_node_urns,
            built_in_node_count=len(built_in_drg.nodes),
        )
        artifacts = _registered_project_artifacts(project_root)
        for artifact in artifacts:
            if artifact.node.urn not in seen_urns:
                nodes.append(artifact.node)
                seen_urns.add(artifact.node.urn)
        # Org-aware universe (#4121, MAJOR 2): org_drg already folds the
        # built-in layer, so the ordering built-in -> org -> overlay mirrors
        # the merge precedence and `nodes` (overlay) wins on URN collision.
        universe = [*built_in_drg.nodes, *(org_drg.nodes if org_drg is not None else ()), *nodes]
        projected, warnings = project_reference_edges(artifacts, universe)
        triples = {(edge.source, edge.target, edge.relation) for edge in edges}
        edges.extend(edge for edge in projected if (edge.source, edge.target, edge.relation) not in triples)
        for warning in warnings:
            logging.getLogger(__name__).warning("%s", warning)
        if warnings_out is not None:
            warnings_out.extend(warnings)


    return DRGGraph(
        schema_version="1.0",
        generated_at=now_iso,
        generated_by=generated_by,
        nodes=nodes,
        edges=edges,
    )


def apply_post_condition(
    repo_root: Path,
    *,
    has_project_graph: bool,
) -> None:
    """Enforce the FR-009 post-condition on the live ``.kittify/`` tree.

    After ``write_pipeline.promote`` returns, exactly one of two states must
    hold:

    1. ``has_project_graph=True``  -> ``.kittify/charter-packs/graph.yaml`` exists
       and the synthesis manifest records ``built_in_only=False`` (default).
       No-op: ``promote`` already wrote both files in that case.
    2. ``has_project_graph=False`` -> no live ``graph.yaml`` is present and
       the synthesis manifest records ``built_in_only=True``.  This function
       performs the two mutations atomically from the caller's perspective:
       it unlinks any pre-existing ``.kittify/charter-packs/graph.yaml`` and
       rewrites the manifest with ``built_in_only=True`` via temp-file +
       atomic ``os.replace``.

    Atomicity guarantee
    -------------------
    The manifest rewrite is staged to a sibling temp file and renamed via
    ``os.replace`` (POSIX atomic rename) inside the same ``try`` block as
    the ``graph.yaml`` unlink.  An exception between the unlink and the
    replace leaves the manifest unchanged on disk; the in-memory mutation
    is not visible.  An exception inside the manifest write surfaces with
    both the previous manifest (untouched on disk) and the unlink already
    applied — operators MAY observe a missing ``graph.yaml`` plus an
    out-of-date manifest, but never a half-written manifest, never the
    forbidden ``built_in_only=True + graph.yaml present`` conflict state.

    Args:
        repo_root: Repository root containing ``.kittify/``.
        has_project_graph: True when synthesis emitted a project DRG; False
            when synthesis produced no project artifacts and the result is
            built-in-only.
    """
    import io  # noqa: PLC0415 — local import keeps module-level surface small
    import os  # noqa: PLC0415
    import tempfile  # noqa: PLC0415

    from .manifest import (  # noqa: PLC0415
        MANIFEST_PATH,
        finalize_manifest,
        load_yaml,
    )
    from .path_guard import PathGuard  # noqa: PLC0415

    manifest_path = repo_root / MANIFEST_PATH
    graph_path = project_pack_root(repo_root) / _GRAPH_FILENAME

    if not manifest_path.exists():
        # Synthesizer must have already written the manifest. Defensive: if
        # the caller invokes this before promote completes, do nothing.
        return

    manifest = load_yaml(manifest_path)
    desired_built_in_only = not has_project_graph

    # Fast path: nothing to mutate.
    if manifest.built_in_only == desired_built_in_only and not (
        desired_built_in_only and graph_path.exists()
    ):
        return

    # Build the post-condition manifest (immutable Pydantic model -> copy).
    # model_copy PRESERVES every unlisted field (incl. bundle_content_hash,
    # schema_version) -- the explicit-kwarg reconstruction this replaces
    # silently dropped bundle_content_hash back to None (BLOCKER-1). Does
    # NOT recompute bundle_content_hash here (data-model.md -- this site
    # "preserves unchanged via model_copy"; the reader short-circuits on
    # built_in_only before the hash comparison, so recomputing would be dead
    # work).
    new_manifest = finalize_manifest(
        manifest.model_copy(update={"built_in_only": desired_built_in_only})
    )

    # All writes go through PathGuard (R-10). The tmp file is a sibling of
    # ``manifest_path`` (same ``.kittify/charter/`` directory, which is in
    # the default allowlist), so both the staging write and the atomic
    # ``replace`` are sanctioned.
    guard = PathGuard(repo_root=repo_root)
    fd, tmp_path_str = tempfile.mkstemp(
        prefix=manifest_path.name + ".",
        suffix=".tmp",
        dir=str(manifest_path.parent),
    )
    os.close(fd)
    tmp_path = Path(tmp_path_str)

    try:
        from ruamel.yaml import YAML  # noqa: PLC0415

        yaml = YAML()
        yaml.default_flow_style = False
        data = new_manifest.model_dump(mode="python")
        # Serialise via an in-memory buffer so the on-disk write flows
        # through ``guard.write_text`` instead of a raw ``open(..., "w")``.
        buffer = io.StringIO()
        yaml.dump(data, buffer)
        guard.write_text(tmp_path, buffer.getvalue(), caller="project_drg.apply_post_condition")

        # Atomic mutations: delete stale graph and atomically replace the
        # manifest. POSIX guarantees the ``replace`` is atomic; if the
        # unlink succeeds but the replace fails the manifest is unchanged
        # on disk -- never half-written. The unlink stays IN PLACE within this
        # guarded sequence (FR-007); only the bare expression is consolidated
        # into the shared helper.
        if desired_built_in_only:
            from .graph_residue import unlink_stale_project_graph  # noqa: PLC0415

            unlink_stale_project_graph(graph_path.parent)
        guard.replace(tmp_path, manifest_path, caller="project_drg.apply_post_condition")
    except Exception:
        # Clean up the staged temp file on failure.
        import contextlib  # noqa: PLC0415

        with contextlib.suppress(OSError):
            tmp_path.unlink(missing_ok=True)
        raise


def persist(
    graph: DRGGraph,
    staging_dir: Path,
    guard: PathGuard,
) -> None:
    """Serialize *graph* under the staged doctrine directory via *guard*.

    The promote step (WP03) will atomically move this file to the live project
    doctrine directory.

    Args:
        graph: The project overlay ``DRGGraph`` to write.
        staging_dir: Root of the staging area (must be within the PathGuard
            allowlist).
        guard: ``PathGuard`` instance that governs all writes.
    """
    pack_dir = staging_dir / PROJECT_PACK_DIRNAME
    guard.mkdir(pack_dir, caller="project_drg.persist")
    graph_path = pack_dir / _GRAPH_FILENAME
    guard.write_text(graph_path, _serialize_graph(graph), caller="project_drg.persist")


__all__ = ["apply_post_condition", "emit_project_layer", "persist"]
