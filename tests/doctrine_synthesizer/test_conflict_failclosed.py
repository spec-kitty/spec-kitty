"""Conflict detection tests — covers every R-006 predicate (T036).

Source-of-truth:
    kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/research.md R-006
    kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/contracts/synthesizer_hook.md

R-006 conflict matrix (row-for-row):
    1. add_edge(E)  vs remove_edge(E):             same (from, to, kind) triple
    2. add_edge(E)  vs rewire_edge(E_old → E):     destination equals A
    3. remove_edge(E) vs rewire_edge(E → E_new):   source equals A
    4. add_glossary_term(T) vs add_glossary_term(T):   same key, different definition_hash
    5. update_glossary_term(T) vs update_glossary_term(T): same key, different definition_hash
    6a. synthesize_directive(D)  vs synthesize_directive(D):  same id, different body_hash
    6b. synthesize_tactic(T)     vs synthesize_tactic(T):     same id, different body_hash
    6c. synthesize_procedure(P)  vs synthesize_procedure(P):  same id, different body_hash
    7. flag_not_helpful does NOT conflict with anything

Contract: on conflict the entire batch fails closed (FR-023).
    - apply_proposals returns no applied rows
    - SynthesisResult.conflicts is non-empty
    - With dry_run=False, rejection events are emitted (events_emitted non-empty)
    - No files are written
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.doctrine_synthesizer.apply import apply_proposals
from specify_cli.doctrine_synthesizer.conflict import detect_conflicts
from specify_cli.retrospective.schema import (
    ActorRef,
    AddEdgePayload,
    AddGlossaryTermPayload,
    EdgeSpec,
    FlagNotHelpfulPayload,
    Proposal,
    ProposalProvenance,
    ProposalState,
    RemoveEdgePayload,
    RewireEdgePayload,
    SynthesizeDirectivePayload,
    SynthesizeProcedurePayload,
    SynthesizeScope,
    SynthesizeTacticPayload,
    TargetReference,
    UpdateGlossaryTermPayload,
)

_EMPTY_SCOPE = SynthesizeScope()

pytestmark = pytest.mark.fast

# ---------------------------------------------------------------------------
# Shared test identifiers
# ---------------------------------------------------------------------------

MISSION_ID = "01KQ6YEGT4YBZ3GZF7X680KQ3V"
EVT_A = "01KQ6YEGT4YBZ3GZF7X680KQ3X"
EVT_B = "01KQ6YEGT4YBZ3GZF7X680KQ3Y"
ACTOR = ActorRef(kind="human", id="rob@robshouse.net", profile_id=None)


def _make_provenance(evidence: list[str] | None = None) -> ProposalProvenance:
    return ProposalProvenance(
        source_mission_id=MISSION_ID,
        source_evidence_event_ids=evidence or [EVT_A],
        authored_by=ACTOR,
        approved_by=None,
    )


def _accepted_state() -> ProposalState:
    return ProposalState(status="accepted")


def _proposal(pid: str, payload: object) -> Proposal:  # type: ignore[type-arg]
    from specify_cli.retrospective.schema import ProposalPayload
    return Proposal(
        id=pid,
        kind=payload.kind,  # type: ignore[attr-defined]
        payload=payload,  # type: ignore[arg-type]
        rationale="test",
        state=_accepted_state(),
        provenance=_make_provenance(),
    )


# Valid ULID-like proposal IDs (26 chars Crockford base32)
PID = [
    "01KQ6YEGT4YBZ3GZF7X680KQ4A",
    "01KQ6YEGT4YBZ3GZF7X680KQ4B",
    "01KQ6YEGT4YBZ3GZF7X680KQ4C",
    "01KQ6YEGT4YBZ3GZF7X680KQ4D",
]


# ---------------------------------------------------------------------------
# Helpers for building fixture edges / terms
# ---------------------------------------------------------------------------

def _edge(from_node: str, to_node: str, kind: str = "uses") -> EdgeSpec:
    return EdgeSpec(from_node=from_node, to_node=to_node, kind=kind)


def _add_edge(pid: str, from_node: str, to_node: str, kind: str = "uses") -> Proposal:
    return _proposal(pid, AddEdgePayload(kind="add_edge", edge=_edge(from_node, to_node, kind)))


def _remove_edge(pid: str, from_node: str, to_node: str, kind: str = "uses") -> Proposal:
    return _proposal(pid, RemoveEdgePayload(kind="remove_edge", edge=_edge(from_node, to_node, kind)))


def _rewire_edge(
    pid: str,
    old_from: str, old_to: str,
    new_from: str, new_to: str,
    kind: str = "uses",
) -> Proposal:
    return _proposal(pid, RewireEdgePayload(
        kind="rewire_edge",
        edge_old=_edge(old_from, old_to, kind),
        edge_new=_edge(new_from, new_to, kind),
    ))


def _add_gloss(pid: str, key: str, defhash: str = "hash-a") -> Proposal:
    return _proposal(pid, AddGlossaryTermPayload(
        kind="add_glossary_term",
        term_key=key,
        definition=f"definition for {key}",
        definition_hash=defhash,
    ))


def _upd_gloss(pid: str, key: str, defhash: str = "hash-a") -> Proposal:
    return _proposal(pid, UpdateGlossaryTermPayload(
        kind="update_glossary_term",
        term_key=key,
        definition=f"updated definition for {key}",
        definition_hash=defhash,
    ))


def _synth_directive(pid: str, artifact_id: str, body_hash: str = "hash-a") -> Proposal:
    return _proposal(pid, SynthesizeDirectivePayload(
        kind="synthesize_directive",
        artifact_id=artifact_id,
        body="directive body",
        body_hash=body_hash,
        scope=_EMPTY_SCOPE,
    ))


def _synth_tactic(pid: str, artifact_id: str, body_hash: str = "hash-a") -> Proposal:
    return _proposal(pid, SynthesizeTacticPayload(
        kind="synthesize_tactic",
        artifact_id=artifact_id,
        body="tactic body",
        body_hash=body_hash,
        scope=_EMPTY_SCOPE,
    ))


def _synth_procedure(pid: str, artifact_id: str, body_hash: str = "hash-a") -> Proposal:
    return _proposal(pid, SynthesizeProcedurePayload(
        kind="synthesize_procedure",
        artifact_id=artifact_id,
        body="procedure body",
        body_hash=body_hash,
        scope=_EMPTY_SCOPE,
    ))


def _flag(pid: str, urn: str = "drg:node:foo") -> Proposal:
    return _proposal(pid, FlagNotHelpfulPayload(
        kind="flag_not_helpful",
        target=TargetReference(kind="drg_node", urn=urn),
    ))


# ---------------------------------------------------------------------------
# Test: detect_conflicts function directly
# ---------------------------------------------------------------------------

class TestDetectConflictsDirect:
    """Unit tests for detect_conflicts() against each R-006 predicate."""

    # Predicate 1: add_edge vs remove_edge (same triple)
    def test_p1_add_vs_remove_same_edge(self) -> None:
        proposals = [
            _add_edge(PID[0], "A", "B", "uses"),
            _remove_edge(PID[1], "A", "B", "uses"),
        ]
        groups = detect_conflicts(proposals)
        # cardinality-is-contract: collapse to exactly ONE group; set-of-frozensets hides a spurious duplicate group
        assert len(groups) == 1
        assert {frozenset(g.proposal_ids) for g in groups} == {frozenset({PID[0], PID[1]})}
        assert set(groups[0].proposal_ids) == {PID[0], PID[1]}
        assert "add_edge" in groups[0].reason
        assert "remove_edge" in groups[0].reason

    def test_p1_no_conflict_different_triple(self) -> None:
        proposals = [
            _add_edge(PID[0], "A", "B", "uses"),
            _remove_edge(PID[1], "A", "C", "uses"),
        ]
        groups = detect_conflicts(proposals)
        assert groups == []

    def test_p1_no_conflict_different_kind(self) -> None:
        proposals = [
            _add_edge(PID[0], "A", "B", "uses"),
            _remove_edge(PID[1], "A", "B", "provides"),
        ]
        groups = detect_conflicts(proposals)
        assert groups == []

    # Predicate 2: add_edge vs rewire_edge (destination equals A)
    def test_p2_add_vs_rewire_destination_conflict(self) -> None:
        # rewire_edge's new destination matches the add_edge
        proposals = [
            _add_edge(PID[0], "A", "B", "uses"),
            _rewire_edge(PID[1], "X", "Y", "A", "B", "uses"),  # edge_new = (A, B, uses)
        ]
        groups = detect_conflicts(proposals)
        # cardinality-is-contract: collapse to exactly ONE group; set-of-frozensets hides a spurious duplicate group
        assert len(groups) == 1
        assert {frozenset(g.proposal_ids) for g in groups} == {frozenset({PID[0], PID[1]})}
        assert set(groups[0].proposal_ids) == {PID[0], PID[1]}

    def test_p2_no_conflict_different_destination(self) -> None:
        proposals = [
            _add_edge(PID[0], "A", "B", "uses"),
            _rewire_edge(PID[1], "X", "Y", "A", "C", "uses"),
        ]
        groups = detect_conflicts(proposals)
        assert groups == []

    # Predicate 3: remove_edge vs rewire_edge (source equals A)
    def test_p3_remove_vs_rewire_source_conflict(self) -> None:
        # rewire_edge's old source matches the remove_edge
        proposals = [
            _remove_edge(PID[0], "A", "B", "uses"),
            _rewire_edge(PID[1], "A", "B", "C", "D", "uses"),  # edge_old = (A, B, uses)
        ]
        groups = detect_conflicts(proposals)
        # cardinality-is-contract: collapse to exactly ONE group; set-of-frozensets hides a spurious duplicate group
        assert len(groups) == 1
        assert {frozenset(g.proposal_ids) for g in groups} == {frozenset({PID[0], PID[1]})}
        assert set(groups[0].proposal_ids) == {PID[0], PID[1]}

    def test_p3_no_conflict_different_source(self) -> None:
        proposals = [
            _remove_edge(PID[0], "A", "B", "uses"),
            _rewire_edge(PID[1], "X", "Y", "C", "D", "uses"),
        ]
        groups = detect_conflicts(proposals)
        assert groups == []

    # Predicate 4: add_glossary_term vs add_glossary_term (same key, different hash)
    def test_p4_add_gloss_same_key_different_hash(self) -> None:
        proposals = [
            _add_gloss(PID[0], "doctrine", "hash-a"),
            _add_gloss(PID[1], "doctrine", "hash-b"),
        ]
        groups = detect_conflicts(proposals)
        # cardinality-is-contract: collapse to exactly ONE group; set-of-frozensets hides a spurious duplicate group
        assert len(groups) == 1
        assert {frozenset(g.proposal_ids) for g in groups} == {frozenset({PID[0], PID[1]})}
        assert set(groups[0].proposal_ids) == {PID[0], PID[1]}

    def test_p4_no_conflict_same_hash(self) -> None:
        # Convergent: same key, same hash → no conflict
        proposals = [
            _add_gloss(PID[0], "doctrine", "hash-a"),
            _add_gloss(PID[1], "doctrine", "hash-a"),
        ]
        groups = detect_conflicts(proposals)
        assert groups == []

    def test_p4_no_conflict_different_key(self) -> None:
        proposals = [
            _add_gloss(PID[0], "doctrine", "hash-a"),
            _add_gloss(PID[1], "mission", "hash-b"),
        ]
        groups = detect_conflicts(proposals)
        assert groups == []

    # Predicate 5: update_glossary_term vs update_glossary_term (same key, different hash)
    def test_p5_update_gloss_same_key_different_hash(self) -> None:
        proposals = [
            _upd_gloss(PID[0], "doctrine", "hash-a"),
            _upd_gloss(PID[1], "doctrine", "hash-b"),
        ]
        groups = detect_conflicts(proposals)
        # cardinality-is-contract: collapse to exactly ONE group; set-of-frozensets hides a spurious duplicate group
        assert len(groups) == 1
        assert {frozenset(g.proposal_ids) for g in groups} == {frozenset({PID[0], PID[1]})}
        assert set(groups[0].proposal_ids) == {PID[0], PID[1]}

    def test_p5_no_conflict_same_hash(self) -> None:
        proposals = [
            _upd_gloss(PID[0], "doctrine", "hash-a"),
            _upd_gloss(PID[1], "doctrine", "hash-a"),
        ]
        groups = detect_conflicts(proposals)
        assert groups == []

    # Predicate 6a: synthesize_directive (same id, different body_hash)
    def test_p6a_synthesize_directive_conflict(self) -> None:
        proposals = [
            _synth_directive(PID[0], "dir-001", "hash-a"),
            _synth_directive(PID[1], "dir-001", "hash-b"),
        ]
        groups = detect_conflicts(proposals)
        # cardinality-is-contract: collapse to exactly ONE group; set-of-frozensets hides a spurious duplicate group
        assert len(groups) == 1
        assert {frozenset(g.proposal_ids) for g in groups} == {frozenset({PID[0], PID[1]})}
        assert set(groups[0].proposal_ids) == {PID[0], PID[1]}

    def test_p6a_synthesize_directive_no_conflict_same_hash(self) -> None:
        proposals = [
            _synth_directive(PID[0], "dir-001", "hash-a"),
            _synth_directive(PID[1], "dir-001", "hash-a"),
        ]
        groups = detect_conflicts(proposals)
        assert groups == []

    def test_p6a_synthesize_directive_no_conflict_different_id(self) -> None:
        proposals = [
            _synth_directive(PID[0], "dir-001", "hash-a"),
            _synth_directive(PID[1], "dir-002", "hash-b"),
        ]
        groups = detect_conflicts(proposals)
        assert groups == []

    # Predicate 6b: synthesize_tactic
    def test_p6b_synthesize_tactic_conflict(self) -> None:
        proposals = [
            _synth_tactic(PID[0], "tac-001", "hash-a"),
            _synth_tactic(PID[1], "tac-001", "hash-b"),
        ]
        groups = detect_conflicts(proposals)
        # cardinality-is-contract: collapse to exactly ONE group; set-of-frozensets hides a spurious duplicate group
        assert len(groups) == 1
        assert {frozenset(g.proposal_ids) for g in groups} == {frozenset({PID[0], PID[1]})}
        assert set(groups[0].proposal_ids) == {PID[0], PID[1]}

    # Predicate 6c: synthesize_procedure
    def test_p6c_synthesize_procedure_conflict(self) -> None:
        proposals = [
            _synth_procedure(PID[0], "proc-001", "hash-a"),
            _synth_procedure(PID[1], "proc-001", "hash-b"),
        ]
        groups = detect_conflicts(proposals)
        # cardinality-is-contract: collapse to exactly ONE group; set-of-frozensets hides a spurious duplicate group
        assert len(groups) == 1
        assert {frozenset(g.proposal_ids) for g in groups} == {frozenset({PID[0], PID[1]})}
        assert set(groups[0].proposal_ids) == {PID[0], PID[1]}

    # Predicate 7: flag_not_helpful never conflicts
    def test_p7_flag_not_helpful_no_conflict_with_anything(self) -> None:
        proposals = [
            _flag(PID[0], "drg:node:foo"),
            _add_edge(PID[1], "A", "B"),
            _remove_edge(PID[2], "A", "B"),
        ]
        # add_edge vs remove_edge does conflict (P1), but flag_not_helpful is not in it
        groups = detect_conflicts(proposals)
        conflict_ids: set[str] = set()
        for g in groups:
            conflict_ids.update(g.proposal_ids)
        assert PID[0] not in conflict_ids

    def test_p7_flag_only_batch_no_conflict(self) -> None:
        proposals = [
            _flag(PID[0], "drg:node:foo"),
            _flag(PID[1], "drg:node:bar"),
        ]
        groups = detect_conflicts(proposals)
        assert groups == []

    # Multi-conflict batch
    def test_multiple_conflicts_in_one_batch(self) -> None:
        proposals = [
            _add_edge(PID[0], "A", "B"),
            _remove_edge(PID[1], "A", "B"),  # conflict with PID[0]
            _add_gloss(PID[2], "term", "hash-a"),
            _add_gloss(PID[3], "term", "hash-b"),  # conflict with PID[2]
        ]
        groups = detect_conflicts(proposals)
        # cardinality-is-contract: two independent conflicts must form exactly TWO groups; the set-of-frozensets hides a spurious duplicate group
        assert len(groups) == 2
        assert {frozenset(g.proposal_ids) for g in groups} == {
            frozenset({PID[0], PID[1]}),
            frozenset({PID[2], PID[3]}),
        }


# ---------------------------------------------------------------------------
# Test: apply_proposals fails closed on conflict
# ---------------------------------------------------------------------------

class TestApplyFailsClosedOnConflict:
    """Verify FR-023: conflict → nothing applied, conflicts non-empty."""

    def _make_repo(self, tmp_path: Path, event_ids: list[str]) -> Path:
        """Create minimal repo structure with event log."""
        repo_root = tmp_path / "repo"
        feature_dir = repo_root / "kitty-specs" / "test-slug"
        feature_dir.mkdir(parents=True)

        meta = {"mission_id": MISSION_ID, "mission_slug": "test-slug"}
        (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

        events_path = feature_dir / "status.events.jsonl"
        for eid in event_ids:
            line = json.dumps({"event_id": eid, "event_name": "retrospective.started"})
            events_path.open("a").write(line + "\n")

        return repo_root

    def test_conflict_dry_run_returns_empty_applied(self, tmp_path: Path) -> None:
        repo_root = self._make_repo(tmp_path, [EVT_A])
        proposals = [
            _add_edge(PID[0], "A", "B"),
            _remove_edge(PID[1], "A", "B"),
        ]
        result = apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=proposals,
            approved_proposal_ids={PID[0], PID[1]},
            actor=ACTOR,
            dry_run=True,
        )
        assert result.dry_run is True
        assert result.applied == []
        assert len(result.conflicts) == 1
        assert set(result.conflicts[0].proposal_ids) == {PID[0], PID[1]}
        assert len(result.events_emitted) == 0  # dry_run: no events

    def test_conflict_apply_mode_returns_empty_applied(self, tmp_path: Path) -> None:
        repo_root = self._make_repo(tmp_path, [EVT_A])
        proposals = [
            _add_edge(PID[0], "A", "B"),
            _remove_edge(PID[1], "A", "B"),
        ]
        result = apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=proposals,
            approved_proposal_ids={PID[0], PID[1]},
            actor=ACTOR,
            dry_run=False,
        )
        assert result.dry_run is False
        assert result.applied == []
        assert len(result.conflicts) == 1
        # Rejection events emitted for conflicted proposals
        assert len(result.events_emitted) > 0

    def test_conflict_no_files_written(self, tmp_path: Path) -> None:
        repo_root = self._make_repo(tmp_path, [EVT_A])
        proposals = [
            _add_gloss(PID[0], "term", "hash-a"),
            _add_gloss(PID[1], "term", "hash-b"),
        ]
        apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=proposals,
            approved_proposal_ids={PID[0], PID[1]},
            actor=ACTOR,
            dry_run=False,
        )
        # No glossary file should be written
        glossary_file = repo_root / ".kittify" / "glossary" / "term.yaml"
        assert not glossary_file.exists()

    def test_all_r006_predicates_fail_closed(self, tmp_path: Path) -> None:
        """All R-006 conflict pairs must block apply (no exceptions)."""
        conflict_pairs: list[tuple[Proposal, Proposal]] = [
            # P1
            (_add_edge(PID[0], "A", "B"), _remove_edge(PID[1], "A", "B")),
            # P2
            (_add_edge(PID[0], "A", "B"), _rewire_edge(PID[1], "X", "Y", "A", "B")),
            # P3
            (_remove_edge(PID[0], "A", "B"), _rewire_edge(PID[1], "A", "B", "C", "D")),
            # P4
            (_add_gloss(PID[0], "term", "h-a"), _add_gloss(PID[1], "term", "h-b")),
            # P5
            (_upd_gloss(PID[0], "term", "h-a"), _upd_gloss(PID[1], "term", "h-b")),
            # P6a
            (_synth_directive(PID[0], "d001", "h-a"), _synth_directive(PID[1], "d001", "h-b")),
            # P6b
            (_synth_tactic(PID[0], "t001", "h-a"), _synth_tactic(PID[1], "t001", "h-b")),
            # P6c
            (_synth_procedure(PID[0], "p001", "h-a"), _synth_procedure(PID[1], "p001", "h-b")),
        ]
        for i, (p_a, p_b) in enumerate(conflict_pairs):
            repo_root = self._make_repo(tmp_path / f"repo_{i}", [EVT_A])
            result = apply_proposals(
                mission_id=MISSION_ID,
                repo_root=repo_root,
                proposals=[p_a, p_b],
                approved_proposal_ids={p_a.id, p_b.id},
                actor=ACTOR,
                dry_run=True,
            )
            assert result.applied == [], f"Predicate {i+1}: expected no applied on conflict"
            assert len(result.conflicts) >= 1, f"Predicate {i+1}: expected at least one conflict group"
