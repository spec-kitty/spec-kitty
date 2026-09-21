"""Validate and register direct-written project doctrine without rewriting its source.

Planning performs all schema, graph and provenance work before activation may
mutate its store. Committing writes only derived state, with the manifest last.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path

from ulid import ULID

from charter.activation._drg_helpers import load_validated_graph
from charter.activation.drg_activation import load_org_drg
from charter.activation.synthesizer.manifest import (
    MANIFEST_PATH,
    ManifestArtifactEntry,
    SynthesisManifest,
    finalize_manifest,
    hash_content_bytes,
    load_yaml as load_manifest,
    verify_manifest_hash,
)
from charter.activation.synthesizer.path_guard import PathGuard
from charter.activation.synthesizer.provenance import ProvenanceEntry, provenance_path_for
from charter.activation.synthesizer.synthesize_pipeline import canonical_yaml
from charter.offering.artifact_kinds import slug_for
from charter.offering.drg.loader import has_graph_files, load_graph_or_dir, merge_layers
from charter.offering.drg.migration.extractor import graph_document_to_dict
from charter.offering.drg.models import DRGGraph
from charter.offering.drg.org_pack_config import resolve_existing_org_roots
from charter.offering.drg.project_scan import ProjectArtifact, project_reference_edges, scan_project_artifacts
from charter.offering.drg.validator import assert_valid
from kernel.clock import now_utc_seconds

__all__ = ["plan_project_registration", "commit_project_registration"]


@dataclass(frozen=True)
class ProjectRegistrationPlan:
    """Validated merged graph for cascade and prepared derived-state writes."""

    repo_root: Path
    graph: DRGGraph
    artifacts: tuple[ProjectArtifact, ...]
    warnings: tuple[str, ...]
    writes: tuple[tuple[Path, str], ...]
    deletes: tuple[Path, ...] = ()
    """Provenance sidecars whose registration is pruned (#4121): committed
    direct-write registrations whose artifact URN the current project scan no
    longer produces (a deleted source, or an in-place identity edit)."""


def _sidecar_recorded_urn(root: Path, entry: ManifestArtifactEntry) -> str | None:
    """The artifact URN a committed entry's sidecar records, or ``None``.

    ``None`` when the sidecar is missing (the registration's URN cannot be
    recovered, so the entry is not this lane's to touch), when the sidecar
    belongs to another adapter (a synthesized artifact is the synthesis
    lane's orphan, not registration's), or when the sidecar cannot be read —
    a malformed sidecar degrades to "not this lane's to touch" instead of
    crashing planning, mirroring the best-effort probe in
    ``reconcile._provenance_urn``.
    """
    from .synthesizer.provenance import load_yaml as load_provenance

    sidecar = root / entry.provenance_path
    if not sidecar.is_file():
        return None
    try:
        record = load_provenance(sidecar)
    except Exception:  # noqa: BLE001 -- identity probe, not a load-bearing
        # read: a corrupt sidecar must not take planning down with it.
        return None
    if record.adapter_id != "project-direct-write":
        return None
    return str(record.artifact_urn)


def _direct_write_registrations(
    root: Path,
    live_urns: frozenset[str],
) -> tuple[tuple[str, ManifestArtifactEntry], ...]:
    """Committed direct-write registrations the current scan no longer produces.

    A registration is prunable only when it can be identified as this lane's
    own — its provenance sidecar still records ``adapter_id ==
    "project-direct-write"`` — AND the ``artifact_urn`` that sidecar records
    is not produced by the current project scan (#4121 pass 2). URN
    reachability, not path existence, is the staleness key: an in-place
    identity edit (``id:`` rewritten in the same file) leaves the path very
    much alive while the registered identity is gone, and a path-existence
    key is blind to it. Synthesis-owned entries are skipped — their prune
    policy belongs to ``charter synthesize --prune`` and the FR-014 orphan
    refusal, not to registration. A missing sidecar is skipped too: without
    it the registration's URN cannot be recovered, so pruning its graph node
    is not safe.
    """
    manifest_path = root / MANIFEST_PATH
    if not manifest_path.exists():
        return ()
    stale: list[tuple[str, ManifestArtifactEntry]] = []
    for entry in load_manifest(manifest_path).artifacts:
        urn = _sidecar_recorded_urn(root, entry)
        if urn is None or urn in live_urns:
            continue
        stale.append((urn, entry))
    return tuple(stale)


def _project_graph(
    root: Path,
    artifacts: tuple[ProjectArtifact, ...],
    base: DRGGraph,
    stale_urns: frozenset[str] = frozenset(),
) -> tuple[DRGGraph, tuple[str, ...]]:
    directory = root / ".kittify/doctrine"
    existing = load_graph_or_dir(directory) if has_graph_files(directory) else None
    nodes = {node.urn: node for node in existing.nodes} if existing else {}
    # Prune phantom nodes (#4121): a committed registration whose URN the
    # current scan no longer produces must not keep satisfying profile
    # references — whether its source file was deleted or its identity was
    # edited in place.
    for urn in stale_urns:
        nodes.pop(urn, None)
    nodes.update({artifact.node.urn: artifact.node for artifact in artifacts})
    # The universe excludes pruned urns on BOTH fronts: the committed overlay
    # above and base's copy of it below (base folds the project layer too, so
    # an unfiltered base would keep satisfying the deleted reference).
    universe = [node for node in base.nodes if node.urn not in stale_urns]
    projected, warnings = project_reference_edges(artifacts, [*universe, *nodes.values()])
    profile_urns = {a.node.urn for a in artifacts if a.node.kind.value == "agent_profile"}
    # Only previously projected reference edges are replaced. Explicit lineage,
    # tension and synthesis provenance edges remain owned by their authors.
    reference_relations = {"requires", "suggests"}
    edges = [e for e in existing.edges if not (e.source in profile_urns and e.relation.value in reference_relations)] if existing else []
    if stale_urns:
        # Drop every edge the pruned nodes participated in on either endpoint,
        # or the pruned graph would carry dangling edges into assert_valid.
        edges = [e for e in edges if e.source not in stale_urns and e.target not in stale_urns]
    triples = {(e.source, e.target, e.relation): e for e in edges}
    triples.update({(e.source, e.target, e.relation): e for e in projected})
    graph = DRGGraph(
        schema_version="1.0",
        generated_at=existing.generated_at if existing else now_utc_seconds(),
        generated_by="spec-kitty project registration",
        nodes=list(nodes.values()),
        edges=list(triples.values()),
    )
    return graph, warnings


def _registration_records(
    root: Path,
    artifacts: tuple[ProjectArtifact, ...],
    stale: tuple[tuple[str, ManifestArtifactEntry], ...] = (),
) -> tuple[list[tuple[Path, str]], list[Path]]:
    manifest_path = root / MANIFEST_PATH
    existing = load_manifest(manifest_path) if manifest_path.exists() else None
    if existing:
        verify_manifest_hash(existing)
    entries = {(entry.kind, entry.slug): entry for entry in existing.artifacts} if existing else {}
    # Prune dead entries (#4121): a manifest entry naming a nonexistent path
    # makes verify() raise on every subsequent read with no in-tool recovery.
    for _, entry in stale:
        entries.pop((entry.kind, entry.slug), None)
    # Reconcile by URN (#4121 pass 2): a registration's identity is the URN
    # its sidecar records, never its source path or (kind, slug) key — an
    # in-place identity edit must not silently re-point the predecessor's
    # entry (and thereby orphan the old URN's graph node) but register fresh
    # while the predecessor is pruned as stale above.
    urn_entries: dict[str, ManifestArtifactEntry] = {}
    for entry in entries.values():
        urn = _sidecar_recorded_urn(root, entry)
        if urn is not None:
            urn_entries.setdefault(urn, entry)
    writes: list[tuple[Path, str]] = []
    stale_sidecars: list[Path] = []
    timestamp = now_utc_seconds()
    run_id = str(ULID())
    package_version = version("spec-kitty-cli")
    for artifact in artifacts:
        kind, identifier = artifact.node.urn.split(":", 1)
        # URNs admit slash-separated identities; slug_for (WP01) is the single
        # producer-side authority that encodes them as one filesystem-safe
        # component and normalizes canonical uppercase directive IDs.
        slug = slug_for(kind, identifier)
        content_hash = hash_content_bytes(artifact.path.read_bytes())
        resolved_path = artifact.path.relative_to(root).as_posix()
        previous = urn_entries.get(artifact.node.urn) or entries.get((kind, slug))
        if previous is not None and previous.slug != slug:
            # #4834 follow-on (T012): never perpetuate a legacy, non-canonical
            # slug reused from an existing manifest entry -- drop its stale
            # (kind, legacy-slug) key and queue its now-orphaned provenance
            # sidecar for deletion. Both are derived state; the authored
            # artifact source file is never touched (no rename).
            entries.pop((kind, previous.slug), None)
            legacy_sidecar = root / previous.provenance_path
            if legacy_sidecar.is_file():
                stale_sidecars.append(legacy_sidecar)
        resolved_provenance_path = provenance_path_for(kind, slug)
        key = (kind, slug)
        # #4834: even when content is unchanged, the manifest entry is
        # re-written when the resolved source path or provenance path has
        # drifted from what is recorded -- an unconditional early skip here
        # left a permanently-stale manifest entry. No sidecar is deleted by
        # this branch; a slug-driven sidecar move is handled above (T012).
        if (
            previous is not None
            and previous.slug == slug
            and previous.content_hash == content_hash
            and previous.path == resolved_path
            and previous.provenance_path == resolved_provenance_path
            and (root / previous.provenance_path).is_file()
        ):
            continue
        record = ProvenanceEntry(
            artifact_urn=artifact.node.urn,
            artifact_kind=kind,
            artifact_slug=slug,
            artifact_content_hash=content_hash,
            inputs_hash=content_hash,
            adapter_id="project-direct-write",
            adapter_version="1",
            synthesizer_version=package_version,
            source_section=resolved_path,
            source_urns=[],
            source_input_ids=[resolved_path],
            generated_at=timestamp,
            produced_at=timestamp,
            corpus_snapshot_id="(none)",
            synthesis_run_id=run_id,
            adapter_notes="Registered authored project content; no generation or source rewrite performed.",
        )
        writes.append((root / resolved_provenance_path, canonical_yaml(record.model_dump(mode="python")).decode()))
        entries[key] = ManifestArtifactEntry(kind=kind, slug=slug, path=resolved_path, provenance_path=resolved_provenance_path, content_hash=content_hash)
    if existing:
        manifest = existing.model_copy(update={"artifacts": list(entries.values()), "built_in_only": False})
    else:
        manifest = SynthesisManifest(
            created_at=timestamp,
            run_id=run_id,
            adapter_id="project-direct-write",
            adapter_version="1",
            synthesizer_version=package_version,
            manifest_hash="0" * 64,
            artifacts=list(entries.values()),
            built_in_only=False,
        )
    manifest = finalize_manifest(manifest)
    writes.append((manifest_path, canonical_yaml(manifest.model_dump(mode="python")).decode()))
    return writes, stale_sidecars


def plan_project_registration(repo_root: Path, *, base_graph: DRGGraph | None = None) -> ProjectRegistrationPlan:
    """Return validated project registration and its merged graph without writes."""
    root = repo_root.resolve()
    artifacts = scan_project_artifacts(root)
    base = (
        base_graph
        if base_graph is not None
        else load_validated_graph(
            root,
            org_roots=resolve_existing_org_roots(root),
            org_fragments=load_org_drg(root, strict=False),
        )
    )
    stale = _direct_write_registrations(root, frozenset(artifact.node.urn for artifact in artifacts))
    stale_urns = frozenset(urn for urn, _ in stale)
    if not artifacts and not stale:
        return ProjectRegistrationPlan(root, base, (), (), ())
    project, warnings = _project_graph(root, artifacts, base, stale_urns)
    stale_warnings = tuple(
        f"Pruned project registration for {urn}: the current project scan no longer produces it "
        f"(registered source {entry.path}); removed its graph node and edges, manifest entry, and provenance sidecar."
        for urn, entry in stale
    )
    project_triples = {(e.source, e.target, e.relation) for e in project.edges}
    profile_urns = {a.node.urn for a in artifacts if a.node.kind.value == "agent_profile"}
    retained_edges = [
        e
        for e in base.edges
        if (e.source, e.target, e.relation) not in project_triples
        and not (e.source in profile_urns and e.relation.value in {"requires", "suggests"})
        and e.source not in stale_urns
        and e.target not in stale_urns
    ]
    # The merged cascade graph must not resurrect a pruned registration through
    # base's copy of the committed project layer (#4121).
    merged = merge_layers(
        base.model_copy(update={"nodes": [node for node in base.nodes if node.urn not in stale_urns], "edges": retained_edges}),
        project,
    )
    assert_valid(merged)
    writes = [(root / ".kittify/doctrine/graph.yaml", canonical_yaml(graph_document_to_dict(project)).decode())]
    registration_writes, slug_reconcile_deletes = _registration_records(root, artifacts, stale)
    writes.extend(registration_writes)
    # A re-created artifact with the same identity reuses its predecessor's
    # sidecar path, so a pruned sidecar is only deleted when this same plan
    # does not re-write it. The same rule covers a slug-reconciliation move
    # (T012): the legacy sidecar is only deleted once the canonical sidecar
    # has actually been queued for write.
    written = {path for path, _ in writes}
    stale_candidates = {root / entry.provenance_path for _, entry in stale if (root / entry.provenance_path).is_file()}
    stale_candidates.update(slug_reconcile_deletes)
    deletes = tuple(path for path in stale_candidates if path not in written)
    changed = tuple((path, text) for path, text in writes if not path.exists() or path.read_text() != text)
    return ProjectRegistrationPlan(root, merged, artifacts, (*stale_warnings, *warnings), changed, deletes)


def commit_project_registration(plan: ProjectRegistrationPlan) -> None:
    """Write a validated registration plan, preserving every authored source file."""
    guard = PathGuard(plan.repo_root)
    for path, text in plan.writes:
        guard.mkdir(path.parent, caller="project_registration.commit")
        guard.write_text(path, text, caller="project_registration.commit")
    for path in plan.deletes:
        guard.unlink(path, caller="project_registration.commit")
