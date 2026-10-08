"""Conflict detection for proposal batches (T032).

Implements every pairwise predicate from research.md R-006.

Source-of-truth:
    kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/research.md R-006
    kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/contracts/synthesizer_hook.md

Conflict matrix (row-for-row from R-006):
    1. add_edge(E) vs remove_edge(E):      same (from, to, kind) triple
    2. add_edge(E) vs rewire_edge(E_old→E): B's destination equals A
    3. remove_edge(E) vs rewire_edge(E→E_new): B's source equals A
    4. add_glossary_term(T) vs add_glossary_term(T):   same key, different definition_hash
    5. update_glossary_term(T) vs update_glossary_term(T): same key, different definition_hash
    6. synthesize_*(X) vs synthesize_*(X) (same kind): same id, different body_hash
    7. flag_not_helpful does NOT conflict with anything.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    pass

from specify_cli.retrospective.schema import (
    AddEdgePayload,
    AddGlossaryTermPayload,
    Proposal,
    RemoveEdgePayload,
    RewireEdgePayload,
    SynthesizeDirectivePayload,
    SynthesizeProcedurePayload,
    SynthesizeTacticPayload,
    UpdateGlossaryTermPayload,
)

# ---------------------------------------------------------------------------
# ConflictGroup (also exported from __init__)
# ---------------------------------------------------------------------------


class ConflictGroup(BaseModel):
    """A group of proposals that mutually conflict.

    Per synthesizer_hook.md: all proposals in a conflict group are rejected;
    the entire batch fails closed (FR-023).
    """

    model_config = ConfigDict(extra="forbid")

    proposal_ids: list[str]
    reason: str


# ---------------------------------------------------------------------------
# Edge-spec normalisation helpers
# ---------------------------------------------------------------------------


def _edge_key(from_node: str, to_node: str, kind: str) -> tuple[str, str, str]:
    return (from_node, to_node, kind)


# ---------------------------------------------------------------------------
# detect_conflicts
# ---------------------------------------------------------------------------


def detect_conflicts(proposals: list[Proposal]) -> list[ConflictGroup]:
    """Detect pairwise conflicts in *proposals* using the R-006 predicates.

    Args:
        proposals: The effective batch (approved + flag_not_helpful).

    Returns:
        A list of ConflictGroup instances.  Empty when no conflicts found.
    """
    groups: list[ConflictGroup] = []

    # Build typed sub-lists for cheap lookup
    add_edges: list[tuple[str, AddEdgePayload]] = []
    remove_edges: list[tuple[str, RemoveEdgePayload]] = []
    rewire_edges: list[tuple[str, RewireEdgePayload]] = []
    add_glossary: list[tuple[str, AddGlossaryTermPayload]] = []
    update_glossary: list[tuple[str, UpdateGlossaryTermPayload]] = []
    # synthesize: keyed by (kind, artifact_id) → [(proposal_id, body_hash)]
    synthesize_map: dict[tuple[str, str], list[tuple[str, str]]] = {}

    for p in proposals:
        payload = p.payload
        if isinstance(payload, AddEdgePayload):
            add_edges.append((p.id, payload))
        elif isinstance(payload, RemoveEdgePayload):
            remove_edges.append((p.id, payload))
        elif isinstance(payload, RewireEdgePayload):
            rewire_edges.append((p.id, payload))
        elif isinstance(payload, AddGlossaryTermPayload):
            add_glossary.append((p.id, payload))
        elif isinstance(payload, UpdateGlossaryTermPayload):
            update_glossary.append((p.id, payload))
        elif isinstance(
            payload,
            (SynthesizeDirectivePayload, SynthesizeTacticPayload, SynthesizeProcedurePayload),
        ):
            key = (payload.kind, payload.artifact_id)
            synthesize_map.setdefault(key, []).append((p.id, payload.body_hash))
        # FlagNotHelpfulPayload: skip — never conflicts (R-006)

    # ------------------------------------------------------------------
    # Predicate 1: add_edge(E) vs remove_edge(E) — same (from, to, kind)
    # ------------------------------------------------------------------
    add_edge_keys: dict[tuple[str, str, str], str] = {_edge_key(pay.edge.from_node, pay.edge.to_node, pay.edge.kind): pid for pid, pay in add_edges}
    for rem_pid, rem_pay in remove_edges:
        k = _edge_key(rem_pay.edge.from_node, rem_pay.edge.to_node, rem_pay.edge.kind)
        if k in add_edge_keys:
            add_pid = add_edge_keys[k]
            groups.append(
                ConflictGroup(
                    proposal_ids=[add_pid, rem_pid],
                    reason=(f"add_edge and remove_edge target the same edge ({k[0]!r} → {k[1]!r} [{k[2]!r}])"),
                )
            )

    # ------------------------------------------------------------------
    # Predicate 2: add_edge(E) vs rewire_edge(E_old → E)
    #   conflict when B's destination (edge_new) equals A
    # ------------------------------------------------------------------
    for rew_pid, rew_pay in rewire_edges:
        dest_key = _edge_key(
            rew_pay.edge_new.from_node,
            rew_pay.edge_new.to_node,
            rew_pay.edge_new.kind,
        )
        if dest_key in add_edge_keys:
            add_pid = add_edge_keys[dest_key]
            groups.append(
                ConflictGroup(
                    proposal_ids=[add_pid, rew_pid],
                    reason=(f"add_edge and rewire_edge both target the same destination edge ({dest_key[0]!r} → {dest_key[1]!r} [{dest_key[2]!r}])"),
                )
            )

    # ------------------------------------------------------------------
    # Predicate 3: remove_edge(E) vs rewire_edge(E → E_new)
    #   conflict when B's source (edge_old) equals A
    # ------------------------------------------------------------------
    remove_edge_keys: dict[tuple[str, str, str], str] = {_edge_key(pay.edge.from_node, pay.edge.to_node, pay.edge.kind): pid for pid, pay in remove_edges}
    for rew_pid, rew_pay in rewire_edges:
        src_key = _edge_key(
            rew_pay.edge_old.from_node,
            rew_pay.edge_old.to_node,
            rew_pay.edge_old.kind,
        )
        if src_key in remove_edge_keys:
            rem_pid = remove_edge_keys[src_key]
            groups.append(
                ConflictGroup(
                    proposal_ids=[rem_pid, rew_pid],
                    reason=(f"remove_edge and rewire_edge both target the same source edge ({src_key[0]!r} → {src_key[1]!r} [{src_key[2]!r}])"),
                )
            )

    # ------------------------------------------------------------------
    # Predicate 4: add_glossary_term(T) vs add_glossary_term(T)
    #   same key, different definition_hash
    # ------------------------------------------------------------------
    add_gloss_by_key: dict[str, list[tuple[str, str]]] = {}
    for pid, pay in add_glossary:
        add_gloss_by_key.setdefault(pay.term_key, []).append((pid, pay.definition_hash))

    for term_key, entries in add_gloss_by_key.items():
        if len(entries) > 1:
            # Check if all hashes are the same (convergent — no conflict)
            hashes = {h for _, h in entries}
            if len(hashes) > 1:
                groups.append(
                    ConflictGroup(
                        proposal_ids=[pid for pid, _ in entries],
                        reason=(f"Multiple add_glossary_term proposals for key {term_key!r} with diverging definition hashes: {sorted(hashes)}"),
                    )
                )

    # ------------------------------------------------------------------
    # Predicate 5: update_glossary_term(T) vs update_glossary_term(T)
    #   same key, different definition_hash
    # ------------------------------------------------------------------
    upd_gloss_by_key: dict[str, list[tuple[str, str]]] = {}
    for pid, update_payload in update_glossary:
        upd_gloss_by_key.setdefault(update_payload.term_key, []).append((pid, update_payload.definition_hash))

    for term_key, entries in upd_gloss_by_key.items():
        if len(entries) > 1:
            hashes = {h for _, h in entries}
            if len(hashes) > 1:
                groups.append(
                    ConflictGroup(
                        proposal_ids=[pid for pid, _ in entries],
                        reason=(f"Multiple update_glossary_term proposals for key {term_key!r} with diverging definition hashes: {sorted(hashes)}"),
                    )
                )

    # ------------------------------------------------------------------
    # Predicate 6: synthesize_*(X) vs synthesize_*(X)  — same kind + id,
    #              different body_hash
    # ------------------------------------------------------------------
    for (s_kind, artifact_id), entries in synthesize_map.items():
        if len(entries) > 1:
            hashes = {h for _, h in entries}
            if len(hashes) > 1:
                groups.append(
                    ConflictGroup(
                        proposal_ids=[pid for pid, _ in entries],
                        reason=(f"Multiple {s_kind!r} proposals for artifact {artifact_id!r} with diverging body hashes: {sorted(hashes)}"),
                    )
                )

    return groups
