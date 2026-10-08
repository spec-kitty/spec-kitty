"""Bounded resynthesis pipeline — WP05 (T029).

Public entry point: ``run(request, adapter, topic) -> SynthesisManifest``

This module wraps the WP02 synthesis pipeline but scopes it to a single
structured topic selector (FR-011, FR-012).  It re-uses:
  - ``topic_resolver.resolve()``       — tier-1/2/3 selector resolution
  - ``synthesize_pipeline.run_all()``  — in-memory pipeline (WP02)
  - ``write_pipeline.promote()``       — staging/promote machinery (WP03)
  - ``manifest.load_yaml()``           — reads existing manifest (WP03)

Manifest rewrite semantics (FR-017):
  - Regenerated artifacts get fresh ``content_hash``, ``provenance_path``.
  - **Untouched artifacts** retain their prior ``content_hash`` and
    ``provenance_path`` unchanged.
  - A new ``run_id`` (ULID) is minted for the resynthesis run.
  - ``created_at`` is refreshed to the current UTC timestamp.

Zero-match (EC-4):
  If ``topic_resolver.resolve()`` returns a ``ResolvedTopic`` with an empty
  ``targets`` list (DRG-URN hit but no project artifact references it), this
  function returns the **current manifest unchanged** and emits a diagnostic
  result.  No writes occur; no model calls occur.

No-prior-manifest:
  If ``.kittify/charter/synthesis-manifest.yaml`` does not exist, a
  ``FileNotFoundError`` is raised immediately (before any model calls).

All filesystem writes go through ``PathGuard`` (FR-016).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from charter.offering.drg.loader import load_graph_or_dir
from charter.offering.drg.models import DRGGraph
from kernel.charter_pack_paths import project_pack_root

from .manifest import (
    MANIFEST_PATH,
    SynthesisManifest,
    load_yaml as load_manifest,
)
from .reconcile import merge_project_overlay as _merge_project_overlay
from .reconcile import rewrite_manifest as _rewrite_manifest
from .request import SynthesisRequest, SynthesisTarget
from .synthesize_pipeline import ProvenanceEntry, _get_synthesizer_version
from .topic_resolver import ResolvedTopic, resolve as resolve_topic

_KITTIFY_DIRNAME = ".kittify"


# ---------------------------------------------------------------------------
# Manifest-rewrite helper: ``_rewrite_manifest`` / ``_merge_project_overlay``
# now live in ``reconcile.py`` (charter-synthesize-reconciliation WP01, T002)
# and are imported above under their historical private names so every call
# site below (and this module's behavior) is unchanged. The full-synthesize
# path (``orchestrator.synthesize``) shares the SAME implementation via
# ``reconcile.reconcile_synthesis`` — one merge, not two.
# ---------------------------------------------------------------------------


def _new_ulid() -> str:
    """Generate a new ULID string (stdlib-only).

    Uses ``time.time_ns()`` for the 48-bit timestamp component and
    ``secrets.token_bytes(10)`` for the 80-bit randomness component.
    Encodes to the standard Crockford base-32 ULID alphabet.
    """
    import secrets
    import time

    # Crockford base-32 encoding alphabet
    _ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

    ts_ms = time.time_ns() // 1_000_000  # 48-bit ms timestamp
    rand_bytes = secrets.token_bytes(10)  # 80-bit randomness

    # Encode 48-bit timestamp into 10 base-32 chars
    ts_part = ""
    v = ts_ms
    for _ in range(10):
        ts_part = _ALPHABET[v & 0x1F] + ts_part
        v >>= 5

    # Encode 80-bit random into 16 base-32 chars
    rand_int = int.from_bytes(rand_bytes, "big")
    rand_part = ""
    for _ in range(16):
        rand_part = _ALPHABET[rand_int & 0x1F] + rand_part
        rand_int >>= 5

    return ts_part + rand_part


# ---------------------------------------------------------------------------
# Zero-match diagnostic result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResynthesisResult:
    """Result of a resynthesis run.

    Attributes
    ----------
    manifest:
        The (potentially updated) synthesis manifest.
    resolved_topic:
        The ``ResolvedTopic`` from the selector resolver.
    is_noop:
        ``True`` when EC-4 zero-match: DRG-URN resolved but no project-local
        artifact references it.  No writes occurred; no model calls occurred.
    diagnostic:
        Human-readable diagnostic message for no-op runs.
    """

    manifest: SynthesisManifest
    resolved_topic: ResolvedTopic
    is_noop: bool = False
    diagnostic: str = ""
    reference_warnings: tuple[str, ...] = ()
    """Unresolved project-profile reference warnings from this run's overlay
    re-emission (#4121, MAJOR 2) — the same strings ``emit_project_layer``
    logs, carried so the CLI can surface them."""


# ---------------------------------------------------------------------------
# Bounded pipeline via full run_all + filter
# ---------------------------------------------------------------------------


def _run_bounded(
    request: SynthesisRequest,
    adapter: Any,
    target_slugs: frozenset[str],
) -> list[tuple[Mapping[str, Any], ProvenanceEntry]]:
    """Run the full synthesis pipeline and filter to only the bounded targets.

    Why this approach instead of calling adapter.generate() per target:
      The fixture adapter (and any deterministic adapter) computes a hash from
      the full ``SynthesisRequest`` envelope, including ``target.title``.  The
      title is not stored in provenance sidecars, so a target reconstructed
      from provenance would produce a different hash.  By running the full
      pipeline (which uses the original interview mapping to produce targets
      with their original titles) and filtering, we guarantee hash stability
      across synthesis and resynthesis runs.

    Parameters
    ----------
    request:
        The full SynthesisRequest with the original interview/doctrine/DRG
        snapshots.  ``request.target`` is a placeholder; actual targets come
        from the interview mapping inside ``run_all``.
    adapter:
        Adapter instance supporting ``generate()`` / ``generate_batch()``.
    target_slugs:
        Set of ``artifact_slug`` values to keep from the full pipeline output.
        All other targets are discarded (bounded contract).

    Returns
    -------
    list[tuple[Mapping, ProvenanceEntry]]
        One tuple per filtered target, in the order produced by ``run_all``.
    """
    from .synthesize_pipeline import run_all

    all_results = run_all(request, adapter=adapter)

    # Filter to only the slugs in the resolved target set
    return [
        (body, prov)
        for body, prov in all_results
        if prov.artifact_slug in target_slugs
    ]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run(
    request: SynthesisRequest,
    adapter: Any,
    topic: str,
    repo_root: Path | None = None,
    project_artifacts: Sequence[SynthesisTarget] | None = None,
    merged_drg: Mapping[str, Any] | None = None,
    interview_sections: Sequence[str] | None = None,
) -> ResynthesisResult:
    """Run the bounded resynthesis pipeline for a single topic selector.

    This function is the implementation of ``orchestrator.resynthesize()``.

    Flow:
        1. Load current manifest from ``.kittify/charter/synthesis-manifest.yaml``.
           If absent → raise ``FileNotFoundError``.
        2. Load all provenance sidecars → build lookup maps.
        3. Call ``topic_resolver.resolve(topic, ...)`` → ``ResolvedTopic``.
           Empty targets (EC-4) → return current manifest unchanged + diagnostic.
        4. Construct bounded ``SynthesisRequest`` objects for each target.
        5. Call ``synthesize_pipeline.run_all()`` → ``[(body, prov), ...]``.
        6. Build the authoritative merged manifest: regenerated entries get
           fresh hashes; untouched entries retain prior ``content_hash``
           (FR-017).
        7. Stage + promote bounded artifacts via WP03's
           ``write_pipeline.promote()``, passing the merged manifest so the
           manifest-last write is still the final commit marker.
        8. Return ``ResynthesisResult``.

    Parameters
    ----------
    request:
        The base ``SynthesisRequest`` providing interview/doctrine/DRG snapshots
        and the run context.  ``request.target`` is used as a sentinel; the
        actual target(s) are resolved from ``topic``.
    adapter:
        Adapter instance to use for generation.  Must support
        ``generate(SynthesisRequest)`` (and optionally ``generate_batch``).
    topic:
        Structured selector string (kind:slug | DRG URN | interview section).
    repo_root:
        Repository root path.  Defaults to ``Path.cwd()``.
    project_artifacts:
        Project-local SynthesisTarget objects for topic resolution.
        If None, loaded from provenance sidecars under
        ``.kittify/charter/provenance/``.
    merged_drg:
        The merged built-in+project DRG graph dict.  If None, loaded from
        the project charter pack root (``.kittify/charter-packs``) and the
        built-in DRG.
    interview_sections:
        Known interview section labels.  If None, inferred from
        ``request.interview_snapshot`` keys.

    Returns
    -------
    ResynthesisResult
        Contains the updated manifest, resolved topic, and no-op flag.

    Raises
    ------
    FileNotFoundError
        If no prior synthesis manifest exists.
    TopicSelectorUnresolvedError
        If ``topic`` cannot be resolved via any of the three tiers.
    """
    from . import write_pipeline as _write_pipeline  # noqa: PLC0415
    from .project_drg import emit_project_layer as _emit_project_layer  # noqa: PLC0415
    from .project_drg import persist as _persist_project_graph  # noqa: PLC0415
    from .staging import StagingDir as _StagingDir  # noqa: PLC0415
    from .validation_gate import validate as _validate_project_graph  # noqa: PLC0415

    # _get_synthesizer_version() (module-level import, above) never raises —
    # it catches importlib.metadata.PackageNotFoundError (and any other
    # metadata-resolution failure) internally and falls back to a dev
    # sentinel. A bare importlib.metadata.version() call here previously let
    # PackageNotFoundError (a subclass of ImportError) escape and be
    # mislabeled by orchestrator.resynthesize()'s except ImportError as
    # "resynthesize_pipeline.py is missing".
    _SPEC_KITTY_VERSION = _get_synthesizer_version()

    _repo_root = repo_root if repo_root is not None else Path.cwd()

    # ------------------------------------------------------------------
    # Step 1: Load existing manifest (fail-closed if absent)
    # ------------------------------------------------------------------
    manifest_path = _repo_root / MANIFEST_PATH
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"No prior synthesis manifest found at '{manifest_path}'. "
            "Run 'spec-kitty charter synthesize' first to create a baseline, "
            "then use 'spec-kitty charter resynthesize --topic' for bounded updates."
        )
    existing_manifest = load_manifest(manifest_path)

    # ------------------------------------------------------------------
    # Step 2: Build provenance lookup maps
    # ------------------------------------------------------------------
    if project_artifacts is None:
        project_artifacts = _load_project_artifacts_from_provenance(_repo_root)

    if merged_drg is None:
        merged_drg = _load_merged_drg(_repo_root, request)

    if interview_sections is None:
        # Default: all top-level keys from the interview snapshot
        interview_sections = list(request.interview_snapshot.keys())

    # ------------------------------------------------------------------
    # Step 3: Resolve topic → ResolvedTopic
    # ------------------------------------------------------------------
    resolved = resolve_topic(
        raw=topic,
        project_artifacts=project_artifacts,
        merged_drg=merged_drg,
        interview_sections=interview_sections,
    )

    # EC-4 zero-match: no artifacts to regenerate — return unchanged manifest
    if not resolved.targets:
        return ResynthesisResult(
            manifest=existing_manifest,
            resolved_topic=resolved,
            is_noop=True,
            diagnostic=(
                f"Topic '{topic}' resolved to a DRG URN but no project-local "
                "artifacts reference it. No writes performed (EC-4)."
            ),
        )

    # ------------------------------------------------------------------
    # Step 4: Compute bounded target slugs + new run_id
    # ------------------------------------------------------------------
    run_id = _new_ulid()
    target_slugs = frozenset(t.slug for t in resolved.targets)

    # Construct a single full SynthesisRequest for the bounded pipeline.
    # We use request.target as a placeholder (run_all ignores it in favour
    # of the interview-mapping output); what matters is that the interview
    # snapshot, doctrine snapshot, and DRG snapshot match the original run.
    bounded_request = SynthesisRequest(
        target=request.target,  # placeholder — actual targets from interview mapping
        interview_snapshot=request.interview_snapshot,
        doctrine_snapshot=request.doctrine_snapshot,
        drg_snapshot=request.drg_snapshot,
        run_id=run_id,
        adapter_hints=request.adapter_hints,
        evidence=request.evidence,
    )

    # ------------------------------------------------------------------
    # Step 5: Run the full pipeline and filter to bounded targets
    # ------------------------------------------------------------------
    all_new_results = _run_bounded(bounded_request, adapter, target_slugs)

    # ------------------------------------------------------------------
    # Step 6: Build final merged manifest (FR-017: untouched entries retain
    # prior hash). It is passed into promote() so bounded resynthesis does not
    # write a temporary bounded-only manifest before the authoritative full
    # manifest.
    # ------------------------------------------------------------------
    new_manifest = _rewrite_manifest(existing_manifest, all_new_results, run_id, _repo_root)

    # ------------------------------------------------------------------
    # Step 7: Stage + promote bounded artifacts
    # ------------------------------------------------------------------
    built_in_drg = _built_in_drg_from_request(request)

    # Org-aware re-emission base (#4121, MAJOR 2), shared by the emit and the
    # validation gate below so both see the universe below the project
    # overlay that activation resolves against. ``None`` for org-less repos.
    from charter.activation._drg_helpers import org_chain_graph  # noqa: PLC0415

    org_drg = org_chain_graph(_repo_root)
    reference_warnings: list[str] = []

    def _validation_callback(staged_dir: _StagingDir) -> None:
        updated_overlay = _emit_project_layer(
            targets=resolved.targets,
            spec_kitty_version=_SPEC_KITTY_VERSION,
            built_in_drg=built_in_drg,
            project_root=_repo_root,
            org_drg=org_drg,
            warnings_out=reference_warnings,
        )
        existing_graph_dir = project_pack_root(_repo_root)
        project_graph = updated_overlay
        if existing_graph_dir.exists():
            project_graph = _merge_project_overlay(
                existing_overlay=load_graph_or_dir(existing_graph_dir),
                updated_overlay=updated_overlay,
            )
        _persist_project_graph(project_graph, staged_dir.root, staged_dir.guard)
        _validate_project_graph(staged_dir.root, built_in_drg, org_drg=org_drg)

    with _StagingDir.create(_repo_root, run_id) as staging_dir:
        written_manifest = _write_pipeline.promote(
            bounded_request,
            staging_dir,
            all_new_results,
            _validation_callback,
            repo_root=_repo_root,
            manifest_override=new_manifest,
        )

    # ------------------------------------------------------------------
    # Step 8: Return result
    # ------------------------------------------------------------------
    return ResynthesisResult(
        manifest=written_manifest,
        resolved_topic=resolved,
        is_noop=False,
        diagnostic="",
        reference_warnings=tuple(reference_warnings),
    )


# ---------------------------------------------------------------------------
# Internal helpers for loading project state
# ---------------------------------------------------------------------------


def _load_project_artifacts_from_provenance(
    repo_root: Path,
) -> list[SynthesisTarget]:
    """Load all project-local SynthesisTarget objects from provenance sidecars.

    Reads every ``.kittify/charter/provenance/*.yaml`` file and reconstructs
    a ``SynthesisTarget`` for each provenance entry.

    Returns an empty list if the provenance directory does not exist.
    """
    from .provenance import load_yaml as load_provenance  # noqa: PLC0415

    prov_dir = repo_root / _KITTIFY_DIRNAME / "charter" / "provenance"
    if not prov_dir.exists():
        return []

    graph_labels = _load_project_graph_labels(repo_root)
    targets: list[SynthesisTarget] = []
    for prov_file in sorted(prov_dir.glob("*.yaml")):
        try:
            prov = load_provenance(prov_file)
            artifact_id = prov.artifact_urn.split(":", 1)[1]
            artifact_urn = f"{prov.artifact_kind}:{artifact_id}"
            # Reconstruct a minimal SynthesisTarget from provenance data
            # (title is not stored in provenance; prefer the existing graph
            # label so bounded no-op resynthesis does not churn graph.yaml)
            target = SynthesisTarget(
                kind=prov.artifact_kind,
                slug=prov.artifact_slug,
                title=graph_labels.get(
                    artifact_urn,
                    prov.artifact_slug.replace("-", " ").title(),
                ),
                artifact_id=artifact_id,
                source_section=prov.source_section,
                source_urns=tuple(prov.source_urns),
            )
            targets.append(target)
        except Exception:  # noqa: BLE001, S112
            continue  # Skip malformed provenance files

    return targets


def _load_project_graph_labels(repo_root: Path) -> dict[str, str]:
    """Return existing project graph labels keyed by URN, best-effort."""
    project_graph_dir = project_pack_root(repo_root)
    if not project_graph_dir.exists():
        return {}
    try:
        graph = load_graph_or_dir(project_graph_dir)
    except Exception:  # noqa: BLE001
        return {}
    return {
        node.urn: node.label
        for node in graph.nodes
        if node.label is not None
    }


def _load_merged_drg(
    repo_root: Path,
    request: SynthesisRequest,
) -> Mapping[str, Any]:
    """Load the merged DRG graph: project overlay + built-in DRG snapshot.

    Falls back to ``request.drg_snapshot`` if no project graph file exists.
    """
    # Bind the snapshot to an explicitly-typed local. The ``charter.*`` mypy
    # override sets ``follow_imports = "skip"``, so when this module is checked
    # in isolation ``SynthesisRequest`` resolves to ``Any`` and a bare
    # ``return request.drg_snapshot`` reads as a ``no-any-return``. The
    # annotation keeps the two fallbacks strictly typed under both whole-package
    # and per-file checking, and de-duplicates the three snapshot reads below.
    snapshot: Mapping[str, Any] = request.drg_snapshot
    project_graph_dir = project_pack_root(repo_root)
    if not project_graph_dir.exists():
        return snapshot

    try:
        project_graph_model = load_graph_or_dir(project_graph_dir)
    except Exception:  # noqa: BLE001
        return snapshot
    project_graph = project_graph_model.model_dump(mode="json")

    # Merge: combine nodes from both graphs (project overlay + built-in snapshot)
    built_in_nodes = list(snapshot.get("nodes", []))
    project_nodes = list(project_graph.get("nodes", []))
    built_in_edges = list(snapshot.get("edges", []))
    project_edges = list(project_graph.get("edges", []))

    return {
        "nodes": built_in_nodes + project_nodes,
        "edges": built_in_edges + project_edges,
        "schema_version": project_graph.get("schema_version", "1"),
    }


def _built_in_drg_from_request(request: SynthesisRequest) -> DRGGraph:
    """Build the built-in-layer DRGGraph from the request snapshot."""
    snapshot = dict(request.drg_snapshot)
    snapshot.setdefault("nodes", [])
    snapshot.setdefault("edges", [])
    snapshot["schema_version"] = "1.0"
    snapshot.setdefault("generated_at", "1970-01-01T00:00:00+00:00")
    snapshot.setdefault("generated_by", "request.drg_snapshot")
    return DRGGraph.model_validate(snapshot)


__all__ = [
    "ResynthesisResult",
    "run",
]
