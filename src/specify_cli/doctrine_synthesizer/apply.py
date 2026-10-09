"""Synthesizer core — apply_proposals() public API (T031, T033, T035).

This module is the **only** path that mutates project-local doctrine, DRG, or
glossary state from a retrospective finding.  It does not auto-run; WP08's CLI
surface is the trigger.

Behavior contract (synthesizer_hook.md):
    1. Compute effective batch: approved_ids ∪ all flag_not_helpful proposals.
    2. Run conflict detection (conflict.py).  If conflicts → fail closed;
       emit rejection events (dry_run=False); return with empty applied list.
    3. Run staleness check: every provenance.source_evidence_event_ids must
       exist in the source-mission event log.  Unreachable → RejectedProposal
       with reason "stale_evidence"; proposal stays status="accepted".
    4. dry_run=True → return planned applications + rejections; no events/writes.
    5. dry_run=False → apply in deterministic order (sorted by proposal_id),
       write provenance sidecar, emit proposal.applied event per success.
       Idempotency: if sidecar already exists for (source_mission_id, proposal_id),
       treat as re_applied=True and emit no new event.

Source-of-truth:
    kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/contracts/synthesizer_hook.md
    kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/data-model.md
"""

from __future__ import annotations

from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.lanes.branch_naming import resolve_mid8
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from kernel.charter_pack_paths import LEGACY_PROJECT_PACK_DIRNAME

if TYPE_CHECKING:
    from specify_cli.context.mission_resolver import ResolvedMission

import yaml as _yaml

from pydantic import BaseModel, ConfigDict

from specify_cli.retrospective.schema import (
    ActorRef,
    AddEdgePayload,
    AddGlossaryTermPayload,
    FlagNotHelpfulPayload,
    Proposal,
    ProposalId,
    RewireEdgePayload,
    SynthesizeDirectivePayload,
    SynthesizeProcedurePayload,
    SynthesizeTacticPayload,
    UpdateGlossaryTermPayload,
)

from .conflict import ConflictGroup, detect_conflicts
from .provenance import _safe_path_component, is_already_applied, provenance_path, write_provenance

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

MissionId = str
EventId = str

# ---------------------------------------------------------------------------
# Result models (defined here; re-exported from __init__)
# ---------------------------------------------------------------------------


class PlannedApplication(BaseModel):
    """Describes what would be applied in a dry-run."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: ProposalId
    kind: str
    targets: list[str]
    diff_preview: str


class AppliedChange(BaseModel):
    """Records a successful apply action."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: ProposalId
    target_urn: str
    artifact_path: str
    provenance_path: str
    re_applied: bool = False


class RejectedProposal(BaseModel):
    """Records a proposal that could not be applied."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: ProposalId
    reason: Literal["conflict", "stale_evidence", "invalid_payload"]
    detail: str


class SynthesisResult(BaseModel):
    """Complete result returned by apply_proposals()."""

    model_config = ConfigDict(extra="forbid")

    dry_run: bool
    planned: list[PlannedApplication]
    applied: list[AppliedChange]
    conflicts: list[ConflictGroup]
    rejected: list[RejectedProposal]
    events_emitted: list[EventId]


# ---------------------------------------------------------------------------
# Staleness check helper
# ---------------------------------------------------------------------------


def _load_event_ids(feature_dir: Path) -> set[str]:
    """Read status.events.jsonl and return all event_ids as a set.

    Returns an empty set if the file does not exist or cannot be parsed.
    """
    events_path = feature_dir / "status.events.jsonl"
    if not events_path.exists():
        return set()
    ids: set[str] = set()
    with events_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                eid = obj.get("event_id")
                if isinstance(eid, str):
                    ids.add(eid)
            except json.JSONDecodeError:
                continue
    return ids


# ---------------------------------------------------------------------------
# Feature-dir resolver
# ---------------------------------------------------------------------------


def _feature_dir(repo_root: Path, mission_slug: str) -> Path:
    """Return the kitty-specs feature directory for *mission_slug*.

    Routed onto the kind-aware read seam (FR-001): this helper backs
    event-log-facing callers (see :func:`_apply_one` /
    :func:`_emit_conflict_rejections`), so it resolves the STATUS-partition
    (``status.events.jsonl``) surface -- topology-aware / coord-consulting
    for a coord-topology mission (C-001).

    read-side-placement-seam-migration WP07: routed through
    :meth:`~mission_runtime.PlacementSeam.read_dir` (fail-loud on a
    deleted-coord mismatch, NFR-002) instead of the kind-blind
    ``resolve_planning_read_dir`` -- this is a genuine functional (not
    diagnostic) STATUS read, so fail-loud is appropriate here.
    """
    # ``PlacementSeam.read_dir`` is typed -> Path; mypy widens it to
    # ``Any`` through the late-import chain (``follow_imports=skip`` on
    # ``specify_cli.*`` -- the same pre-existing systemic pattern documented
    # via the ``_compose_mission_dir`` cast note in ``_read_path_resolver.py``);
    # bind explicitly so the return narrows back to ``Path``.
    resolved: Path = placement_seam(repo_root, mission_slug).read_dir(
        MissionArtifactKind.STATUS_STATE
    )
    return resolved


# ---------------------------------------------------------------------------
# Per-kind apply logic
# ---------------------------------------------------------------------------

#: Base path under repo_root for project-local glossary state.
_GLOSSARY_BASE = Path(".kittify") / "glossary"
#: Base path for project-local DRG overlay.
_DRG_BASE = Path(".kittify") / "drg"
#: Base path for project-local doctrine artifacts. CR-07 (mission
#: ``charter-code-topology-01M152G1`` S4): this producer only ever WRITES
#: (``mkdir`` + create) into this base -- an M3 concern (the actual data
#: move + write-side cutover to ``.kittify/charter-packs``), not M2's
#: read-side dual-root reader (``kernel.charter_pack_paths``). Composed from the
#: single shared ``LEGACY_PROJECT_PACK_DIRNAME`` source rather than a re-spelled
#: ``"doctrine"`` literal so a census over that constant finds this site too.
_DOCTRINE_BASE = Path(".kittify") / LEGACY_PROJECT_PACK_DIRNAME

#: CR-05 (mission ``charter-code-topology-01M152G1`` S4): the canonical
#: ``target_urn`` scheme prefix this producer emits for newly-synthesized
#: artifacts, replacing the retired ``doctrine:`` prefix. ``target_urn`` is
#: an intentionally opaque, unconstrained identifier string everywhere it is
#: consumed (``ProposalAppliedPayload.target_urn: str`` -- no format/prefix
#: validation; see ``specify_cli.retrospective.events``) -- the durable
#: event-log contract this CR must honor is therefore satisfied by
#: construction: events already written with the legacy ``doctrine:`` prefix
#: keep parsing exactly as before, and this producer only changes what NEW
#: events look like going forward. Do not confuse with the 2-part DRG node
#: URN space (``charter/offering/drg/merge.py``/``models.py``), which is a
#: separate, unrelated URN scheme this CR explicitly does not touch.
_TARGET_URN_SCHEME = "charter"


def _assert_within(base: Path, target: Path) -> Path:
    """Resolve ``target`` and confirm it stays inside ``base``.

    Defense-in-depth against path traversal even after schema validation:
    schema rejects unsafe identifiers via ``_SLUG_PATTERN``, and this check
    catches any future regression that could let a slug escape its bucket
    (symlinks, drive letters, etc.).

    Returns the resolved target path.

    Raises:
        ValueError: if the resolved target is not contained in ``base``.
    """
    resolved_base = base.resolve()
    resolved_target = target.resolve()
    try:
        resolved_target.relative_to(resolved_base)
    except ValueError as exc:
        raise ValueError(f"refusing to write outside artifact base: target={resolved_target} base={resolved_base}") from exc
    return resolved_target


def _repo_relative_posix(path: Path, repo_root: Path) -> str:
    """Return a stable repo-relative path for persisted event payloads."""
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _apply_add_glossary_term(
    payload: AddGlossaryTermPayload,
    repo_root: Path,
    _proposal: Proposal,
    _actor: ActorRef,
) -> tuple[str, str]:
    """Apply an add_glossary_term proposal.

    Writes a YAML file at .kittify/glossary/<term_key>.yaml and a provenance
    sidecar.

    Returns:
        (target_urn, artifact_path_str)
    """
    term_key = payload.term_key
    glossary_dir = repo_root / _GLOSSARY_BASE
    glossary_dir.mkdir(parents=True, exist_ok=True)

    artifact_path = _assert_within(glossary_dir, glossary_dir / f"{term_key}.yaml")
    target_urn = f"glossary:term:{term_key}"

    term_data: dict[str, object] = {
        "term_key": term_key,
        "definition": payload.definition,
        "definition_hash": payload.definition_hash,
        "related_terms": payload.related_terms,
    }
    with artifact_path.open("w", encoding="utf-8") as fh:
        _yaml.safe_dump(term_data, fh, allow_unicode=True)

    return target_urn, str(artifact_path)


def _apply_update_glossary_term(
    payload: UpdateGlossaryTermPayload,
    repo_root: Path,
    _proposal: Proposal,
    _actor: ActorRef,
) -> tuple[str, str]:
    """Apply an update_glossary_term proposal (same storage as add)."""
    term_key = payload.term_key
    glossary_dir = repo_root / _GLOSSARY_BASE
    glossary_dir.mkdir(parents=True, exist_ok=True)

    artifact_path = _assert_within(glossary_dir, glossary_dir / f"{term_key}.yaml")
    target_urn = f"glossary:term:{term_key}"

    term_data: dict[str, object] = {
        "term_key": term_key,
        "definition": payload.definition,
        "definition_hash": payload.definition_hash,
        "related_terms": payload.related_terms,
    }
    with artifact_path.open("w", encoding="utf-8") as fh:
        _yaml.safe_dump(term_data, fh, allow_unicode=True)

    return target_urn, str(artifact_path)


def _apply_flag_not_helpful(
    payload: FlagNotHelpfulPayload,
    repo_root: Path,
    proposal: Proposal,
    _actor: ActorRef,
) -> tuple[str, str]:
    """Apply a flag_not_helpful proposal.

    Annotates the doctrine artifact with a "flagged" provenance entry.
    This does NOT remove the artifact (per synthesizer_hook.md §6).

    The annotation is written to .kittify/doctrine/.flags/<urn-slug>.yaml.
    """
    urn = payload.target.urn
    urn_slug = _safe_path_component(urn)
    flags_dir = repo_root / _DOCTRINE_BASE / ".flags"
    flags_dir.mkdir(parents=True, exist_ok=True)

    artifact_path = _assert_within(flags_dir, flags_dir / f"{urn_slug}.yaml")
    target_urn = urn

    flag_data: dict[str, object] = {
        "target_urn": urn,
        "flag": "not_helpful",
        "proposal_id": proposal.id,
    }
    with artifact_path.open("w", encoding="utf-8") as fh:
        _yaml.safe_dump(flag_data, fh, allow_unicode=True)

    return target_urn, str(artifact_path)


def _apply_add_edge(
    payload: AddEdgePayload,
    repo_root: Path,
    _proposal: Proposal,
    _actor: ActorRef,
) -> tuple[str, str]:
    """Apply an add_edge proposal.

    Appends an edge record to .kittify/drg/edges.yaml.
    """
    drg_dir = repo_root / _DRG_BASE
    drg_dir.mkdir(parents=True, exist_ok=True)

    artifact_path = drg_dir / "edges.yaml"
    edge = payload.edge

    # Load existing edges
    edges: list[dict[str, str]] = []
    if artifact_path.exists():
        with artifact_path.open("r", encoding="utf-8") as fh:
            loaded = _yaml.safe_load(fh)
            if isinstance(loaded, list):
                edges = loaded

    edge_dict: dict[str, str] = {
        "from_node": edge.from_node,
        "to_node": edge.to_node,
        "kind": edge.kind,
    }
    edges.append(edge_dict)

    with artifact_path.open("w", encoding="utf-8") as fh:
        _yaml.safe_dump(edges, fh, allow_unicode=True)

    target_urn = f"drg:edge:{edge.from_node}-{edge.kind}-{edge.to_node}"
    return target_urn, str(artifact_path)


def _apply_rewire_edge(
    payload: RewireEdgePayload,
    repo_root: Path,
    _proposal: Proposal,
    _actor: ActorRef,
) -> tuple[str, str]:
    """Apply a rewire_edge proposal.

    Removes the old edge and adds the new edge in .kittify/drg/edges.yaml.
    """
    drg_dir = repo_root / _DRG_BASE
    drg_dir.mkdir(parents=True, exist_ok=True)

    artifact_path = drg_dir / "edges.yaml"
    old_edge = payload.edge_old
    new_edge = payload.edge_new

    edges: list[dict[str, str]] = []
    if artifact_path.exists():
        with artifact_path.open("r", encoding="utf-8") as fh:
            loaded = _yaml.safe_load(fh)
            if isinstance(loaded, list):
                edges = loaded

    # Remove old edge
    edges = [e for e in edges if not (e.get("from_node") == old_edge.from_node and e.get("to_node") == old_edge.to_node and e.get("kind") == old_edge.kind)]
    # Add new edge
    edges.append(
        {
            "from_node": new_edge.from_node,
            "to_node": new_edge.to_node,
            "kind": new_edge.kind,
        }
    )

    with artifact_path.open("w", encoding="utf-8") as fh:
        _yaml.safe_dump(edges, fh, allow_unicode=True)

    target_urn = f"drg:edge:{new_edge.from_node}-{new_edge.kind}-{new_edge.to_node}"
    return target_urn, str(artifact_path)


def _apply_synthesize(
    payload: SynthesizeDirectivePayload | SynthesizeTacticPayload | SynthesizeProcedurePayload,
    repo_root: Path,
    _proposal: Proposal,
    _actor: ActorRef,
) -> tuple[str, str]:
    """Apply a synthesize_* proposal.

    Writes the artifact body to .kittify/doctrine/<kind>/<artifact_id>.md.
    """
    kind_slug = payload.kind.replace("synthesize_", "")  # "directive", "tactic", "procedure"
    doctrine_dir = repo_root / _DOCTRINE_BASE / kind_slug
    doctrine_dir.mkdir(parents=True, exist_ok=True)

    artifact_path = _assert_within(doctrine_dir, doctrine_dir / f"{payload.artifact_id}.md")
    with artifact_path.open("w", encoding="utf-8") as fh:
        fh.write(payload.body)

    target_urn = f"{_TARGET_URN_SCHEME}:{kind_slug}:{payload.artifact_id}"
    return target_urn, str(artifact_path)


# ---------------------------------------------------------------------------
# apply_proposals
# ---------------------------------------------------------------------------


def apply_proposals(
    *,
    mission_id: MissionId,
    repo_root: Path,
    proposals: list[Proposal],
    approved_proposal_ids: set[ProposalId],
    actor: ActorRef,
    dry_run: bool = True,
) -> SynthesisResult:
    """Apply a batch of retrospective proposals to project-local state.

    This is the **only** entry-point for mutating doctrine/DRG/glossary from
    a retrospective.  The default ``dry_run=True`` means callers must
    explicitly opt in to mutation.

    Args:
        mission_id: Canonical ULID of the **source** retrospective mission.
            Used for provenance and event emission.
        repo_root: Project root; all writes are scoped under this path.
        proposals: The full proposal list from the retrospective record.
        approved_proposal_ids: Subset of proposal ids the operator approved.
            ``flag_not_helpful`` proposals are auto-included regardless.
        actor: Who authorised the synthesis run.
        dry_run: When ``True`` (default) plan and check but do not write or
            emit events.  Pass ``dry_run=False`` to actually apply.

    Returns:
        :class:`SynthesisResult` with dry_run, planned, applied, conflicts,
        rejected, and events_emitted fields.
    """
    # ------------------------------------------------------------------
    # Step 1: Build the effective batch
    #   approved_ids ∪ all flag_not_helpful proposals
    # ------------------------------------------------------------------
    effective: list[Proposal] = []
    for p in proposals:
        if p.id in approved_proposal_ids or p.kind == "flag_not_helpful":
            effective.append(p)

    # ------------------------------------------------------------------
    # Step 2: Conflict detection (always runs, even dry_run)
    # ------------------------------------------------------------------
    conflicts = detect_conflicts(effective)

    if conflicts:
        # Fail closed — emit rejection events (if not dry_run), return empty applied.
        rejected: list[RejectedProposal] = []
        events_emitted: list[EventId] = []
        conflicted_ids: set[str] = set()
        for cg in conflicts:
            conflicted_ids.update(cg.proposal_ids)

        for p in effective:
            if p.id in conflicted_ids:
                rejected.append(
                    RejectedProposal(
                        proposal_id=p.id,
                        reason="conflict",
                        detail=next(cg.reason for cg in conflicts if p.id in cg.proposal_ids),
                    )
                )

        if not dry_run:
            events_emitted = _emit_conflict_rejections(
                mission_id=mission_id,
                repo_root=repo_root,
                proposals={p.id: p for p in effective},
                conflict_groups=conflicts,
                actor=actor,
            )

        return SynthesisResult(
            dry_run=dry_run,
            planned=[],
            applied=[],
            conflicts=conflicts,
            rejected=rejected,
            events_emitted=events_emitted,
        )

    # ------------------------------------------------------------------
    # Step 3: Staleness check
    # ------------------------------------------------------------------
    # Derive the source mission's event log location.
    # The mission_id is the source retrospective's mission — we need its
    # feature_dir.  We look up the slug from kitty-specs by searching for
    # a meta.json with matching mission_id.
    source_event_ids = _resolve_source_event_ids(mission_id, repo_root)

    stale_rejected: list[RejectedProposal] = []
    surviving: list[Proposal] = []

    for p in effective:
        unreachable = [eid for eid in p.provenance.source_evidence_event_ids if eid not in source_event_ids]
        if unreachable:
            stale_rejected.append(
                RejectedProposal(
                    proposal_id=p.id,
                    reason="stale_evidence",
                    detail=(f"Evidence event ids not reachable in source mission event log: {unreachable}"),
                )
            )
        else:
            surviving.append(p)

    # ------------------------------------------------------------------
    # Step 4: Build planned applications
    # ------------------------------------------------------------------
    planned = [_plan_application(p) for p in surviving]

    # ------------------------------------------------------------------
    # Step 5: dry_run=True → return plan; no writes, no events
    # ------------------------------------------------------------------
    if dry_run:
        return SynthesisResult(
            dry_run=True,
            planned=planned,
            applied=[],
            conflicts=[],
            rejected=stale_rejected,
            events_emitted=[],
        )

    # ------------------------------------------------------------------
    # Step 6: dry_run=False → apply in deterministic order
    # ------------------------------------------------------------------
    surviving.sort(key=lambda p: p.id)  # deterministic: sorted by proposal_id

    applied: list[AppliedChange] = []
    apply_rejected: list[RejectedProposal] = []
    events_emitted_live: list[EventId] = []

    for p in surviving:
        try:
            applied_change, event_id = _apply_one(
                proposal=p,
                mission_id=mission_id,
                repo_root=repo_root,
                actor=actor,
            )
            applied.append(applied_change)
            if event_id is not None:
                events_emitted_live.append(event_id)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Failed to apply proposal %s (%s): %s",
                p.id,
                p.kind,
                exc,
                exc_info=True,
            )
            apply_rejected.append(
                RejectedProposal(
                    proposal_id=p.id,
                    reason="invalid_payload",
                    detail=str(exc),
                )
            )
            # Halt remaining batch on failure (synthesizer_hook.md §3.5)
            break

    all_rejected = stale_rejected + apply_rejected

    return SynthesisResult(
        dry_run=False,
        planned=planned,
        applied=applied,
        conflicts=[],
        rejected=all_rejected,
        events_emitted=events_emitted_live,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_mission_by_id(mission_id: MissionId, repo_root: Path) -> ResolvedMission | None:
    """Find the mission whose ``mission_id`` matches, via the canonical resolver.

    Adopts :class:`~specify_cli.context.mission_resolver.FsMissionResolver`
    (mission-resolver-port-01KX1C05 WP03, FR-003/T015) in place of the two
    duplicated hand-rolled ``kitty-specs/`` ``iterdir()`` + meta.json scans this
    module used to run (:func:`_resolve_source_event_ids`,
    :func:`_slug_for_mission` — now both single-line callers of this helper).
    Uses :meth:`~mission_runtime.MissionResolver.all_missions` rather than
    :meth:`~mission_runtime.MissionResolver.resolve`: both call sites already
    tolerate "no match" by returning ``None`` / an empty set (a best-effort
    provenance lookup), not the resolver's fail-closed-loud ``resolve()``
    contract, which would raise on the very "not found" case these callers
    treat as a normal, safe outcome.
    """
    from specify_cli.context.mission_resolver import FsMissionResolver

    for mission in FsMissionResolver(repo_root).all_missions():
        if mission.mission_id == mission_id:
            return mission
    return None


def _resolve_source_event_ids(mission_id: MissionId, repo_root: Path) -> set[str]:
    """Return event ids from the source mission's event log.

    Resolves the source mission's feature directory via
    :func:`_resolve_mission_by_id` (WP03 adoption) and falls back to an empty
    set when no mission matches (the staleness check then rejects all
    proposals with unresolvable evidence — safe / fail-closed).
    """
    mission = _resolve_mission_by_id(mission_id, repo_root)
    if mission is None:
        # Fallback: if the mission slug is embedded in the mission_id derivation
        # path we can't find it; return empty (fail-closed on staleness).
        return set()
    return _load_event_ids(mission.feature_dir)


def _plan_application(proposal: Proposal) -> PlannedApplication:
    """Build a :class:`PlannedApplication` for a surviving proposal."""
    payload = proposal.payload
    targets: list[str] = []
    diff_preview: str = ""

    if isinstance(payload, AddGlossaryTermPayload):
        targets = [f"glossary:term:{payload.term_key}"]
        diff_preview = f"add glossary term {payload.term_key!r}"
    elif isinstance(payload, UpdateGlossaryTermPayload):
        targets = [f"glossary:term:{payload.term_key}"]
        diff_preview = f"update glossary term {payload.term_key!r}"
    elif isinstance(payload, FlagNotHelpfulPayload):
        targets = [payload.target.urn]
        diff_preview = f"flag {payload.target.urn!r} as not_helpful"
    elif isinstance(payload, AddEdgePayload):
        e = payload.edge
        targets = [f"drg:edge:{e.from_node}-{e.kind}-{e.to_node}"]
        diff_preview = f"add DRG edge {e.from_node!r} --[{e.kind}]--> {e.to_node!r}"
    elif isinstance(payload, RewireEdgePayload):
        e = payload.edge_new
        targets = [f"drg:edge:{e.from_node}-{e.kind}-{e.to_node}"]
        diff_preview = f"rewire DRG edge to {e.from_node!r} --[{e.kind}]--> {e.to_node!r}"
    elif isinstance(
        payload,
        (SynthesizeDirectivePayload, SynthesizeTacticPayload, SynthesizeProcedurePayload),
    ):
        kind_slug = payload.kind.replace("synthesize_", "")
        targets = [f"{_TARGET_URN_SCHEME}:{kind_slug}:{payload.artifact_id}"]
        diff_preview = f"synthesize {kind_slug} {payload.artifact_id!r}"
    else:
        targets = ["unknown"]
        diff_preview = f"apply {proposal.kind}"

    return PlannedApplication(
        proposal_id=proposal.id,
        kind=proposal.kind,
        targets=targets,
        diff_preview=diff_preview,
    )


def _apply_one(
    *,
    proposal: Proposal,
    mission_id: MissionId,
    repo_root: Path,
    actor: ActorRef,
) -> tuple[AppliedChange, EventId | None]:
    """Apply a single proposal.

    Checks idempotency (T035), delegates to per-kind handler, writes
    provenance sidecar, emits event.

    Returns:
        (AppliedChange, event_id_or_None)
    """
    from specify_cli.retrospective.events import (
        ProposalAppliedPayload,
        emit_retrospective_event,
    )

    payload = proposal.payload

    # Dispatch to per-kind handler
    if isinstance(payload, AddGlossaryTermPayload):
        target_urn, artifact_path_str = _apply_add_glossary_term(payload, repo_root, proposal, actor)
        artifact_id = payload.term_key
    elif isinstance(payload, UpdateGlossaryTermPayload):
        target_urn, artifact_path_str = _apply_update_glossary_term(payload, repo_root, proposal, actor)
        artifact_id = payload.term_key
    elif isinstance(payload, FlagNotHelpfulPayload):
        target_urn, artifact_path_str = _apply_flag_not_helpful(payload, repo_root, proposal, actor)
        artifact_id = payload.target.urn
    elif isinstance(payload, AddEdgePayload):
        target_urn, artifact_path_str = _apply_add_edge(payload, repo_root, proposal, actor)
        e = payload.edge
        artifact_id = f"{e.from_node}-{e.kind}-{e.to_node}"
    elif isinstance(payload, RewireEdgePayload):
        target_urn, artifact_path_str = _apply_rewire_edge(payload, repo_root, proposal, actor)
        e = payload.edge_new
        artifact_id = f"{e.from_node}-{e.kind}-{e.to_node}"
    elif isinstance(
        payload,
        (SynthesizeDirectivePayload, SynthesizeTacticPayload, SynthesizeProcedurePayload),
    ):
        target_urn, artifact_path_str = _apply_synthesize(payload, repo_root, proposal, actor)
        artifact_id = payload.artifact_id
    else:
        raise NotImplementedError(f"No apply handler for proposal kind {proposal.kind!r}")

    artifact_path = Path(artifact_path_str)

    # ------------------------------------------------------------------
    # Idempotency check (T035)
    # ------------------------------------------------------------------
    sidecar = provenance_path(artifact_path, artifact_id)
    already = is_already_applied(sidecar, proposal.provenance.source_mission_id, proposal.id)

    if already:
        # Re-run: update sidecar with re_applied=True; emit no event
        prov_path = write_provenance(
            artifact_path=artifact_path,
            artifact_id=artifact_id,
            proposal=proposal,
            actor=actor,
            re_applied=True,
        )
        return (
            AppliedChange(
                proposal_id=proposal.id,
                target_urn=target_urn,
                artifact_path=artifact_path_str,
                provenance_path=str(prov_path),
                re_applied=True,
            ),
            None,  # no event for re-applied
        )

    # Fresh apply: write provenance sidecar
    prov_path = write_provenance(
        artifact_path=artifact_path,
        artifact_id=artifact_id,
        proposal=proposal,
        actor=actor,
        re_applied=False,
    )

    # Emit proposal.applied event
    # Derive mission_slug from kitty-specs/<slug> by probing meta.json
    mission_slug = _slug_for_mission(mission_id, repo_root)
    feature_dir = _feature_dir(repo_root, mission_slug) if mission_slug else None

    event_id: str | None = None
    if feature_dir is not None:
        assert mission_slug is not None  # invariant: feature_dir is only set when mission_slug is set
        event_id = emit_retrospective_event(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            mission_id=mission_id,
            mid8=resolve_mid8(mission_slug, mission_id=mission_id),
            actor=actor,
            event_name="retrospective.proposal.applied",
            payload=ProposalAppliedPayload(
                proposal_id=proposal.id,
                kind=proposal.kind,
                target_urn=target_urn,
                provenance_ref=_repo_relative_posix(prov_path, repo_root),
                applied_by=actor,
            ),
        )

    return (
        AppliedChange(
            proposal_id=proposal.id,
            target_urn=target_urn,
            artifact_path=artifact_path_str,
            provenance_path=str(prov_path),
            re_applied=False,
        ),
        event_id,
    )


def _slug_for_mission(mission_id: MissionId, repo_root: Path) -> str | None:
    """Find the mission_slug for a given mission_id via the canonical resolver.

    See :func:`_resolve_mission_by_id` (WP03 adoption note) — this is the
    second of the two duplicated scans it consolidates.
    """
    mission = _resolve_mission_by_id(mission_id, repo_root)
    return mission.mission_slug if mission is not None else None


def _emit_conflict_rejections(
    *,
    mission_id: MissionId,
    repo_root: Path,
    proposals: dict[str, Proposal],
    conflict_groups: list[ConflictGroup],
    actor: ActorRef,
) -> list[EventId]:
    """Emit proposal.rejected events for conflicted proposals."""
    from specify_cli.retrospective.events import (
        ProposalRejectedPayload,
        emit_retrospective_event,
    )

    mission_slug = _slug_for_mission(mission_id, repo_root)
    if mission_slug is None:
        return []

    feature_dir = _feature_dir(repo_root, mission_slug)
    emitted: list[EventId] = []

    # Emit one rejection event per proposal in any conflict group
    conflicted_ids: set[str] = set()
    for cg in conflict_groups:
        for pid in cg.proposal_ids:
            conflicted_ids.add(pid)

    for pid in conflicted_ids:
        p = proposals.get(pid)
        if p is None:
            continue
        # Find the reason from the group
        reason = next(
            (cg.reason for cg in conflict_groups if pid in cg.proposal_ids),
            "conflict",
        )
        event_id = emit_retrospective_event(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            mission_id=mission_id,
            mid8=resolve_mid8(mission_slug, mission_id=mission_id),
            actor=actor,
            event_name="retrospective.proposal.rejected",
            payload=ProposalRejectedPayload(
                proposal_id=pid,
                kind=p.kind,
                reason="conflict",
                detail=reason,
                rejected_by=actor,
            ),
        )
        emitted.append(event_id)

    return emitted
