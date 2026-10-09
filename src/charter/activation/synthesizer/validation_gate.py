"""Pre-synthesis validation gate (FR-008 / NFR-004 / US-5).

Public API: ``validate(staging_dir, built_in_drg, conflicts=()) -> None``

Flow:
1. Load the staged project overlay from ``staging_dir/doctrine``.
   ``orchestrator.synthesize._validation_callback`` (WP01) persists the
   MERGED (preserved + emitted) overlay into staging before calling this
   gate, so the overlay loaded here is already the merged graph, not only
   the current run's fresh emit (T007) -- no separate merge step is needed
   for that purpose.
2. Merge with *built_in_drg* via ``merge_layers()`` (additive semantics).
3. Suppress-vs-raise (T008/T009, FR-006 split -- this is WP02's half of the
   split; WP01 owns detection + classification onto
   ``ReconciliationDelta.conflicts``): an edge matching a *preserved*-
   provenance ``ReconciliationConflict`` is excluded from THIS validation
   pass -- its conflict is already surfaced via ``delta.conflicts`` for the
   CLI/boundary to render, so re-raising here would turn WP01's
   "preserve, don't drop" contract into a crash (NFR-003). A conflict whose
   provenance is ``"new_emit"`` (or that is not classified ``"preserved"``
   at all) is left untouched and still hard-fails below, unchanged from
   pre-WP02 behavior.
4. Call ``validate_graph(merged)`` — dangling refs, duplicate edges, cycles —
   on the (possibly conflict-filtered) merged graph.
5. If any errors remain: raise ``ProjectDRGValidationError`` with structured
   fields that carry enough information for a ``rich``-rendered CLI panel
   (US-5).

NFR-004: fail-closed within 5s.  The validator runs entirely in-process on
in-memory data structures — 5s is orders of magnitude above actual latency.
``test_validation_gate.py`` includes a timing assertion to lock this in.

WP03 integration: ``write_pipeline.promote(validation_callback=validate)``
calls this gate before any ``os.replace`` writes land in ``.kittify/``.  On
``ProjectDRGValidationError`` the orchestrator routes the staging dir to
``.failed/`` and surfaces the structured error.

Conflict matching (T009): a preserved conflict is matched to its offending
edge in the merged graph by ``target_id`` — never by parsing
``validate_graph``'s human-readable error strings (those are formatting, not
identity). See ``_edge_conflict_key`` for the label format.

See data-model.md §E-5 for overlay discipline.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from charter.offering.drg.loader import DRGLoadError, load_graph_or_dir, merge_layers
from charter.offering.drg.models import DRGEdge, DRGGraph
from charter.offering.drg.validator import validate_graph

from kernel.charter_pack_paths import PROJECT_PACK_DIRNAME

from .errors import ProjectDRGValidationError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .reconcile import ReconciliationConflict


# ---------------------------------------------------------------------------
# Conflict-suppression helpers (T009)
# ---------------------------------------------------------------------------


def _edge_conflict_key(edge: DRGEdge) -> str:
    """Build the same ``target_id`` label ``reconcile._edge_label`` builds.

    ``ReconciliationConflict.target_id`` (every reconciliation conflict is
    edge-shaped: ``duplicate_triple`` and ``preserved_dangling_endpoint``
    both come from ``charter.activation.synthesizer.reconcile._edge_conflict``, which
    stamps ``target_id`` via that module's private ``_edge_label``) is the
    join key this module uses to match a conflict to "the edge it is
    about", instead of parsing ``validate_graph``'s human-readable strings.
    Reconstructing the identical format here — rather than reaching across
    the ownership boundary to import a private helper from ``reconcile.py``
    — keeps this module's only dependency on the reconciliation seam at the
    public ``ReconciliationConflict`` shape. Keep this format in lockstep
    with ``reconcile._edge_label`` if it ever changes.
    """
    return f"{edge.source}--{edge.relation.value}-->{edge.target}"


def _graph_excluding_preserved_conflicts(
    graph: DRGGraph,
    conflicts: Sequence[ReconciliationConflict],
) -> DRGGraph:
    """Return *graph* with preserved-provenance conflict edges suppressed.

    - ``preserved_dangling_endpoint``: the offending edge is dropped
      entirely — it references a URN the current run does not emit, and a
      dangling reference cannot legitimately participate in cycle
      detection, so removing it changes no other check's verdict.
    - ``duplicate_triple``: only occurrences AFTER the first are dropped
      (mirrors ``charter.offering.drg.validator.duplicate_edge_triples``'s "the
      first occurrence is not itself a duplicate" rule), so the edge still
      participates once in every other structural check (cycles, dangling)
      — only the redundant repeat is suppressed.

    ``new_emit`` conflicts, and anything not classified ``"preserved"``, are
    left untouched here and still fail ``validate_graph`` below (unchanged
    behavior — the hard error for a current run's own collision).
    """
    preserved_dangling = {
        c.target_id
        for c in conflicts
        if c.provenance == "preserved" and c.kind == "preserved_dangling_endpoint"
    }
    preserved_duplicate = {
        c.target_id
        for c in conflicts
        if c.provenance == "preserved" and c.kind == "duplicate_triple"
    }
    if not preserved_dangling and not preserved_duplicate:
        return graph

    filtered_edges: list[DRGEdge] = []
    seen_duplicate_keys: set[str] = set()
    for edge in graph.edges:
        key = _edge_conflict_key(edge)
        if key in preserved_dangling:
            continue
        if key in preserved_duplicate:
            if key in seen_duplicate_keys:
                continue
            seen_duplicate_keys.add(key)
        filtered_edges.append(edge)

    return graph.model_copy(update={"edges": filtered_edges})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate(
    staging_dir: Path,
    built_in_drg: DRGGraph,
    conflicts: Sequence[ReconciliationConflict] = (),
    *,
    org_drg: DRGGraph | None = None,
) -> None:
    """Validate the staged (merged) project DRG overlay against *built_in_drg*.

    Args:
        staging_dir: Root of the staging area produced by the current run.
            The overlay is expected under ``staging_dir/doctrine``. The
            orchestrator's callback persists the MERGED overlay here before
            calling this gate, so this is already the merged (preserved +
            emitted) graph, not only the current run's fresh emit (T007).
        built_in_drg: The built-in-layer ``DRGGraph``.  Used as the lower layer
            in the ``merge_layers`` call.
        conflicts: The classified ``ReconciliationConflict`` sequence WP01's
            reconciliation seam populates on ``ReconciliationDelta.conflicts``
            (FR-006 split — WP01 detects/classifies, WP02 routes). Every
            conflict whose ``provenance`` is ``"preserved"`` is suppressed
            here (it is already reported via ``delta.conflicts``); every
            other conflict — ``"new_emit"``, or absent entirely — still
            hard-fails below, unchanged from pre-WP02 behavior. Defaults to
            ``()`` so every pre-existing positional caller (``validate(
            staging_dir, built_in_drg)``) keeps working unchanged.
        org_drg: The org-chain base graph (built-in + org merged, as returned
            by :func:`charter.activation._drg_helpers.org_chain_graph`), or ``None``
            when no org packs are configured (#4121, MAJOR 2). When supplied
            it REPLACES ``built_in_drg`` as the merge's lower layer — it
            already folds the built-in nodes — so an overlay edge referencing
            an org-pack artifact is not mis-read as dangling. The additive
            universe below the project overlay is exactly what
            ``emit_project_layer`` projected references against, keeping this
            gate and the emitter in agreement.

    Raises:
        ProjectDRGValidationError: When validation fails for any reason:
            * The staged overlay file is missing or malformed.
            * ``validate_graph`` returns ≥ 1 errors (dangling refs, duplicate
              edges, cycles) that survive preserved-conflict suppression.
        The error carries ``errors`` and ``merged_graph_summary`` fields rich
        enough for a CLI panel that names the dangling URN, the offending
        artifact, and the source reference that triggered it (US-5).
    """
    overlay_doctrine_dir = staging_dir / PROJECT_PACK_DIRNAME

    # --- Step 1: Load the staged overlay -----------------------------------
    try:
        project_overlay = load_graph_or_dir(overlay_doctrine_dir)
    except DRGLoadError as exc:
        raise ProjectDRGValidationError(
            errors=(
                f"Could not load staged project overlay from "
                f"{overlay_doctrine_dir}: {exc}",
            ),
            merged_graph_summary=(
                f"staging_dir={staging_dir}, "
                f"built_in_nodes={len(built_in_drg.nodes)}"
            ),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise ProjectDRGValidationError(
            errors=(f"Unexpected error loading overlay {overlay_doctrine_dir}: {exc}",),
            merged_graph_summary=(
                f"staging_dir={staging_dir}"
            ),
        ) from exc

    # --- Step 2: Merge layers (additive) -----------------------------------
    # org_drg already folds the built-in layer, so it substitutes for (not
    # unions with) built_in_drg as the lower layer (#4121, MAJOR 2).
    base_layer = org_drg if org_drg is not None else built_in_drg
    merged = merge_layers(base_layer, project_overlay)

    # --- Step 3: Suppress preserved-content conflicts (T009) ---------------
    graph_for_validation = _graph_excluding_preserved_conflicts(merged, conflicts)

    # --- Step 4: Validate merged graph -------------------------------------
    errors = validate_graph(graph_for_validation)
    if not errors:
        return  # all good — no raise

    # --- Step 5: Surface structured error ----------------------------------
    # Build a human-readable summary that names specific problem artifacts.
    project_urns = frozenset(n.urn for n in project_overlay.nodes)
    summary = (
        f"built_in_nodes={len(built_in_drg.nodes)}, "
        f"project_nodes={len(project_overlay.nodes)}, "
        f"merged_nodes={len(merged.nodes)}, "
        f"merged_edges={len(merged.edges)}, "
        f"project_urns=[{', '.join(sorted(project_urns))}]"
    )

    raise ProjectDRGValidationError(
        errors=tuple(errors),
        merged_graph_summary=summary,
    )


__all__ = ["validate"]
