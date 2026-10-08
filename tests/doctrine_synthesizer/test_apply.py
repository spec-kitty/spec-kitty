"""Tests for apply_proposals() — T036.

Covers (at minimum):
- add_glossary_term: apply succeeds, provenance written, event emitted
- flag_not_helpful:  apply succeeds, provenance written, event emitted
- add_edge:          apply succeeds, provenance written, event emitted
- update_glossary_term, synthesize_directive, synthesize_tactic, synthesize_procedure
- Re-run idempotency: second call → re_applied=True, no new event
- dry_run=True default: no writes, no events, planned list populated
- Staleness check: unreachable evidence → RejectedProposal(stale_evidence)
- flag_not_helpful auto-include: included even if not in approved_ids
- Batch halts on first invalid apply (and records the failure)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.doctrine_synthesizer.apply import _repo_relative_posix, apply_proposals
from specify_cli.doctrine_synthesizer.provenance import load_provenance
from specify_cli.retrospective.schema import (
    ActorRef,
    AddEdgePayload,
    AddGlossaryTermPayload,
    EdgeSpec,
    FlagNotHelpfulPayload,
    Proposal,
    ProposalProvenance,
    ProposalState,
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
MISSION_SLUG = "test-mission"
EVT_A = "01KQ6YEGT4YBZ3GZF7X680KQ3X"
EVT_B = "01KQ6YEGT4YBZ3GZF7X680KQ3Y"
ACTOR = ActorRef(kind="human", id="rob@robshouse.net", profile_id=None)

PIDS = [
    "01KQ6YEGT4YBZ3GZF7X680KQ4A",
    "01KQ6YEGT4YBZ3GZF7X680KQ4B",
    "01KQ6YEGT4YBZ3GZF7X680KQ4C",
    "01KQ6YEGT4YBZ3GZF7X680KQ4D",
    "01KQ6YEGT4YBZ3GZF7X680KQ4E",
    "01KQ6YEGT4YBZ3GZF7X680KQ4F",
]


# ---------------------------------------------------------------------------
# Repo fixture helpers
# ---------------------------------------------------------------------------


def _make_repo(
    tmp_path: Path,
    event_ids: list[str] | None = None,
    mission_id: str = MISSION_ID,
    mission_slug: str = MISSION_SLUG,
) -> Path:
    """Create a minimal repo with kitty-specs/<mission_slug>/ and event log."""
    repo_root = tmp_path / "repo"
    feature_dir = repo_root / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)

    meta = {"mission_id": mission_id, "mission_slug": mission_slug}
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    if event_ids:
        events_path = feature_dir / "status.events.jsonl"
        with events_path.open("w", encoding="utf-8") as fh:
            for eid in event_ids:
                line = json.dumps({"event_id": eid, "event_name": "test"})
                fh.write(line + "\n")

    return repo_root


def _provenance(evidence: list[str] | None = None) -> ProposalProvenance:
    return ProposalProvenance(
        source_mission_id=MISSION_ID,
        source_evidence_event_ids=evidence or [EVT_A],
        authored_by=ActorRef(kind="agent", id="claude", profile_id=None),
        approved_by=None,
    )


def _proposal(pid: str, payload: object) -> Proposal:  # type: ignore[type-arg]
    return Proposal(
        id=pid,
        kind=payload.kind,  # type: ignore[attr-defined]
        payload=payload,  # type: ignore[arg-type]
        rationale="test",
        state=ProposalState(status="accepted"),
        provenance=_provenance(),
    )


# ---------------------------------------------------------------------------
# dry_run=True default
# ---------------------------------------------------------------------------


class TestDryRunDefault:
    def test_default_is_dry_run(self, tmp_path: Path) -> None:
        """apply_proposals must default to dry_run=True."""
        repo_root = _make_repo(tmp_path, [EVT_A])
        p = _proposal(
            PIDS[0],
            AddGlossaryTermPayload(
                kind="add_glossary_term",
                term_key="foo",
                definition="Foo definition.",
                definition_hash="hash-foo",
            ),
        )
        result = apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=[p],
            approved_proposal_ids={PIDS[0]},
            actor=ACTOR,
            # No dry_run kwarg — must default to True
        )
        assert result.dry_run is True
        assert result.applied == []
        assert result.events_emitted == []
        # Planned list populated
        assert len(result.planned) == 1
        assert result.planned[0].proposal_id == PIDS[0]

    def test_dry_run_no_files_written(self, tmp_path: Path) -> None:
        repo_root = _make_repo(tmp_path, [EVT_A])
        p = _proposal(
            PIDS[0],
            AddGlossaryTermPayload(
                kind="add_glossary_term",
                term_key="foo",
                definition="Foo definition.",
                definition_hash="hash-foo",
            ),
        )
        apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=[p],
            approved_proposal_ids={PIDS[0]},
            actor=ACTOR,
        )
        glossary_file = repo_root / ".kittify" / "glossary" / "foo.yaml"
        assert not glossary_file.exists()


# ---------------------------------------------------------------------------
# add_glossary_term
# ---------------------------------------------------------------------------


class TestAddGlossaryTerm:
    def test_apply_success(self, tmp_path: Path) -> None:
        repo_root = _make_repo(tmp_path, [EVT_A])
        p = _proposal(
            PIDS[0],
            AddGlossaryTermPayload(
                kind="add_glossary_term",
                term_key="doctrine",
                definition="Core principles.",
                definition_hash="hash-doc",
            ),
        )
        result = apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=[p],
            approved_proposal_ids={PIDS[0]},
            actor=ACTOR,
            dry_run=False,
        )
        assert len(result.applied) == 1
        assert result.applied[0].proposal_id == PIDS[0]
        assert "glossary:term:doctrine" in result.applied[0].target_urn

    def test_provenance_sidecar_written(self, tmp_path: Path) -> None:
        repo_root = _make_repo(tmp_path, [EVT_A])
        p = _proposal(
            PIDS[0],
            AddGlossaryTermPayload(
                kind="add_glossary_term",
                term_key="doctrine",
                definition="Core principles.",
                definition_hash="hash-doc",
            ),
        )
        result = apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=[p],
            approved_proposal_ids={PIDS[0]},
            actor=ACTOR,
            dry_run=False,
        )
        sidecar = Path(result.applied[0].provenance_path)
        assert sidecar.exists()
        data = load_provenance(sidecar)
        assert data is not None
        assert data["source"] == "retrospective"
        assert data["source_mission_id"] == MISSION_ID
        assert data["source_proposal_id"] == PIDS[0]
        assert data["applied_by"]["id"] == "rob@robshouse.net"

    def test_event_emitted(self, tmp_path: Path) -> None:
        repo_root = _make_repo(tmp_path, [EVT_A])
        p = _proposal(
            PIDS[0],
            AddGlossaryTermPayload(
                kind="add_glossary_term",
                term_key="doctrine",
                definition="Core principles.",
                definition_hash="hash-doc",
            ),
        )
        result = apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=[p],
            approved_proposal_ids={PIDS[0]},
            actor=ACTOR,
            dry_run=False,
        )
        assert len(result.events_emitted) == 1
        events_path = repo_root / "kitty-specs" / MISSION_SLUG / "status.events.jsonl"
        event = json.loads(events_path.read_text(encoding="utf-8").splitlines()[-1])
        provenance_ref = event["payload"]["provenance_ref"]
        assert provenance_ref == ".kittify/glossary/.provenance/doctrine.yaml"
        assert not Path(provenance_ref).is_absolute()

    def test_repo_relative_posix_falls_back_for_external_path(self, tmp_path: Path) -> None:
        repo_root = tmp_path / "repo"
        external_path = tmp_path / "external" / "artifact.yaml"

        assert _repo_relative_posix(external_path, repo_root) == external_path.as_posix()

    def test_idempotent_rerun_re_applied_true(self, tmp_path: Path) -> None:
        """Re-running with same approved set → applied with re_applied=True, no new event."""
        repo_root = _make_repo(tmp_path, [EVT_A])
        p = _proposal(
            PIDS[0],
            AddGlossaryTermPayload(
                kind="add_glossary_term",
                term_key="doctrine",
                definition="Core principles.",
                definition_hash="hash-doc",
            ),
        )

        # First run
        result1 = apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=[p],
            approved_proposal_ids={PIDS[0]},
            actor=ACTOR,
            dry_run=False,
        )
        assert result1.applied[0].re_applied is False
        assert len(result1.events_emitted) == 1

        # Second run
        result2 = apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=[p],
            approved_proposal_ids={PIDS[0]},
            actor=ACTOR,
            dry_run=False,
        )
        assert len(result2.applied) == 1
        assert result2.applied[0].re_applied is True
        # No new event emitted on re-apply
        assert len(result2.events_emitted) == 0


# ---------------------------------------------------------------------------
# flag_not_helpful
# ---------------------------------------------------------------------------


class TestFlagNotHelpful:
    def test_apply_success(self, tmp_path: Path) -> None:
        repo_root = _make_repo(tmp_path, [EVT_A])
        p = _proposal(
            PIDS[0],
            FlagNotHelpfulPayload(
                kind="flag_not_helpful",
                target=TargetReference(kind="drg_node", urn="drg:node:context-artifact"),
            ),
        )
        result = apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=[p],
            approved_proposal_ids={PIDS[0]},
            actor=ACTOR,
            dry_run=False,
        )
        assert len(result.applied) == 1
        assert result.applied[0].target_urn == "drg:node:context-artifact"

    def test_auto_include_without_approved_ids(self, tmp_path: Path) -> None:
        """flag_not_helpful is auto-included even if not in approved_proposal_ids (FR-020)."""
        repo_root = _make_repo(tmp_path, [EVT_A])
        p = _proposal(
            PIDS[0],
            FlagNotHelpfulPayload(
                kind="flag_not_helpful",
                target=TargetReference(kind="drg_node", urn="drg:node:foo"),
            ),
        )
        result = apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=[p],
            approved_proposal_ids=set(),  # empty — flag_not_helpful auto-included
            actor=ACTOR,
            dry_run=False,
        )
        assert len(result.applied) == 1

    def test_provenance_written(self, tmp_path: Path) -> None:
        repo_root = _make_repo(tmp_path, [EVT_A])
        p = _proposal(
            PIDS[0],
            FlagNotHelpfulPayload(
                kind="flag_not_helpful",
                target=TargetReference(kind="drg_node", urn="drg:node:foo"),
            ),
        )
        result = apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=[p],
            approved_proposal_ids={PIDS[0]},
            actor=ACTOR,
            dry_run=False,
        )
        sidecar = Path(result.applied[0].provenance_path)
        assert sidecar.exists()
        data = load_provenance(sidecar)
        assert data is not None
        assert data["source"] == "retrospective"

    def test_target_urn_cannot_escape_flags_or_provenance_dir(self, tmp_path: Path) -> None:
        repo_root = _make_repo(tmp_path, [EVT_A])
        p = _proposal(
            PIDS[0],
            FlagNotHelpfulPayload(
                kind="flag_not_helpful",
                target=TargetReference(kind="drg_node", urn="drg:node:../../outside\\escape"),
            ),
        )
        result = apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=[p],
            approved_proposal_ids=set(),
            actor=ACTOR,
            dry_run=False,
        )

        flag_path = Path(result.applied[0].artifact_path).resolve()
        sidecar = Path(result.applied[0].provenance_path).resolve()
        flags_dir = (repo_root / ".kittify" / "charter-packs" / ".flags").resolve()
        assert flag_path.is_relative_to(flags_dir)
        assert sidecar.is_relative_to(flags_dir / ".provenance")
        assert not (repo_root / "outside").exists()


# ---------------------------------------------------------------------------
# add_edge
# ---------------------------------------------------------------------------


class TestAddEdge:
    def test_apply_success(self, tmp_path: Path) -> None:
        repo_root = _make_repo(tmp_path, [EVT_A])
        p = _proposal(
            PIDS[0],
            AddEdgePayload(
                kind="add_edge",
                edge=EdgeSpec(from_node="NodeA", to_node="NodeB", kind="uses"),
            ),
        )
        result = apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=[p],
            approved_proposal_ids={PIDS[0]},
            actor=ACTOR,
            dry_run=False,
        )
        assert len(result.applied) == 1
        assert "drg:edge" in result.applied[0].target_urn

    def test_provenance_and_event(self, tmp_path: Path) -> None:
        repo_root = _make_repo(tmp_path, [EVT_A])
        p = _proposal(
            PIDS[0],
            AddEdgePayload(
                kind="add_edge",
                edge=EdgeSpec(from_node="NodeA", to_node="NodeB", kind="uses"),
            ),
        )
        result = apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=[p],
            approved_proposal_ids={PIDS[0]},
            actor=ACTOR,
            dry_run=False,
        )
        sidecar = Path(result.applied[0].provenance_path)
        assert sidecar.exists()
        assert len(result.events_emitted) == 1

    def test_edge_values_cannot_escape_provenance_dir(self, tmp_path: Path) -> None:
        repo_root = _make_repo(tmp_path, [EVT_A])
        p = _proposal(
            PIDS[0],
            AddEdgePayload(
                kind="add_edge",
                edge=EdgeSpec(from_node="../../outside", to_node="NodeB", kind="uses\\rel"),
            ),
        )
        result = apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=[p],
            approved_proposal_ids={PIDS[0]},
            actor=ACTOR,
            dry_run=False,
        )

        sidecar = Path(result.applied[0].provenance_path).resolve()
        provenance_dir = (repo_root / ".kittify" / "drg" / ".provenance").resolve()
        assert sidecar.is_relative_to(provenance_dir)
        assert not (repo_root / "outside-uses").exists()


# ---------------------------------------------------------------------------
# update_glossary_term
# ---------------------------------------------------------------------------


class TestUpdateGlossaryTerm:
    def test_apply_success(self, tmp_path: Path) -> None:
        repo_root = _make_repo(tmp_path, [EVT_A])
        p = _proposal(
            PIDS[0],
            UpdateGlossaryTermPayload(
                kind="update_glossary_term",
                term_key="existing-term",
                definition="Updated definition.",
                definition_hash="hash-upd",
            ),
        )
        result = apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=[p],
            approved_proposal_ids={PIDS[0]},
            actor=ACTOR,
            dry_run=False,
        )
        assert len(result.applied) == 1
        assert "glossary:term:existing-term" in result.applied[0].target_urn


# ---------------------------------------------------------------------------
# synthesize_directive / tactic / procedure
# ---------------------------------------------------------------------------


class TestSynthesizeKinds:
    def test_synthesize_directive(self, tmp_path: Path) -> None:
        repo_root = _make_repo(tmp_path, [EVT_A])
        p = _proposal(
            PIDS[0],
            SynthesizeDirectivePayload(
                kind="synthesize_directive",
                artifact_id="dir-001",
                body="Do the thing.",
                body_hash="hash-dir",
                scope=_EMPTY_SCOPE,
            ),
        )
        result = apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=[p],
            approved_proposal_ids={PIDS[0]},
            actor=ACTOR,
            dry_run=False,
        )
        assert len(result.applied) == 1
        assert "charter:directive:dir-001" in result.applied[0].target_urn
        artifact = Path(result.applied[0].artifact_path)
        assert artifact.exists()
        assert artifact.read_text(encoding="utf-8") == "Do the thing."

    def test_synthesize_tactic(self, tmp_path: Path) -> None:
        repo_root = _make_repo(tmp_path, [EVT_A])
        p = _proposal(
            PIDS[0],
            SynthesizeTacticPayload(
                kind="synthesize_tactic",
                artifact_id="tac-001",
                body="Use the tactic.",
                body_hash="hash-tac",
                scope=_EMPTY_SCOPE,
            ),
        )
        result = apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=[p],
            approved_proposal_ids={PIDS[0]},
            actor=ACTOR,
            dry_run=False,
        )
        assert len(result.applied) == 1
        assert "charter:tactic:tac-001" in result.applied[0].target_urn

    def test_synthesize_procedure(self, tmp_path: Path) -> None:
        repo_root = _make_repo(tmp_path, [EVT_A])
        p = _proposal(
            PIDS[0],
            SynthesizeProcedurePayload(
                kind="synthesize_procedure",
                artifact_id="proc-001",
                body="Follow the procedure.",
                body_hash="hash-proc",
                scope=_EMPTY_SCOPE,
            ),
        )
        result = apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=[p],
            approved_proposal_ids={PIDS[0]},
            actor=ACTOR,
            dry_run=False,
        )
        assert len(result.applied) == 1
        assert "charter:procedure:proc-001" in result.applied[0].target_urn


# ---------------------------------------------------------------------------
# Staleness check (T033)
# ---------------------------------------------------------------------------


class TestStalenessCheck:
    def test_stale_evidence_rejected(self, tmp_path: Path) -> None:
        """Proposal with unreachable evidence event ids → stale_evidence rejection."""
        repo_root = _make_repo(tmp_path, [EVT_A])  # EVT_B not present

        p = Proposal(
            id=PIDS[0],
            kind="add_glossary_term",
            payload=AddGlossaryTermPayload(
                kind="add_glossary_term",
                term_key="stale-term",
                definition="This is stale.",
                definition_hash="hash-stale",
            ),
            rationale="test",
            state=ProposalState(status="accepted"),
            provenance=ProposalProvenance(
                source_mission_id=MISSION_ID,
                source_evidence_event_ids=[EVT_A, EVT_B],  # EVT_B unreachable
                authored_by=ActorRef(kind="agent", id="claude", profile_id=None),
                approved_by=None,
            ),
        )
        result = apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=[p],
            approved_proposal_ids={PIDS[0]},
            actor=ACTOR,
            dry_run=False,
        )
        assert result.applied == []
        assert len(result.rejected) == 1
        assert result.rejected[0].reason == "stale_evidence"
        assert PIDS[0] == result.rejected[0].proposal_id

    def test_valid_evidence_passes(self, tmp_path: Path) -> None:
        """Proposal with all evidence present → not stale."""
        repo_root = _make_repo(tmp_path, [EVT_A, EVT_B])

        p = Proposal(
            id=PIDS[0],
            kind="add_glossary_term",
            payload=AddGlossaryTermPayload(
                kind="add_glossary_term",
                term_key="fresh-term",
                definition="This is fresh.",
                definition_hash="hash-fresh",
            ),
            rationale="test",
            state=ProposalState(status="accepted"),
            provenance=ProposalProvenance(
                source_mission_id=MISSION_ID,
                source_evidence_event_ids=[EVT_A, EVT_B],
                authored_by=ActorRef(kind="agent", id="claude", profile_id=None),
                approved_by=None,
            ),
        )
        result = apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=[p],
            approved_proposal_ids={PIDS[0]},
            actor=ACTOR,
            dry_run=False,
        )
        assert len(result.applied) == 1
        assert result.rejected == []

    def test_stale_dry_run_also_rejects(self, tmp_path: Path) -> None:
        """Staleness check runs even in dry_run mode."""
        repo_root = _make_repo(tmp_path, [EVT_A])

        p = Proposal(
            id=PIDS[0],
            kind="add_glossary_term",
            payload=AddGlossaryTermPayload(
                kind="add_glossary_term",
                term_key="stale-term",
                definition="Stale.",
                definition_hash="hash-stale",
            ),
            rationale="test",
            state=ProposalState(status="accepted"),
            provenance=ProposalProvenance(
                source_mission_id=MISSION_ID,
                source_evidence_event_ids=[EVT_B],  # EVT_B missing
                authored_by=ActorRef(kind="agent", id="claude", profile_id=None),
                approved_by=None,
            ),
        )
        result = apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=[p],
            approved_proposal_ids={PIDS[0]},
            actor=ACTOR,
            dry_run=True,
        )
        assert result.rejected[0].reason == "stale_evidence"
        assert result.applied == []


# ---------------------------------------------------------------------------
# Multiple proposals in one batch (deterministic order)
# ---------------------------------------------------------------------------


class TestBatchApply:
    def test_deterministic_order_by_proposal_id(self, tmp_path: Path) -> None:
        """Applied changes are in sorted proposal_id order."""
        repo_root = _make_repo(tmp_path, [EVT_A])

        # PID[1] < PID[0] lexicographically (they are the same length so compare char)
        # Use PIDS[0] (ends 4A) and PIDS[1] (ends 4B)
        p1 = _proposal(
            PIDS[1],
            AddGlossaryTermPayload(
                kind="add_glossary_term",
                term_key="alpha",
                definition="Alpha.",
                definition_hash="hash-alpha",
            ),
        )
        p0 = _proposal(
            PIDS[0],
            AddGlossaryTermPayload(
                kind="add_glossary_term",
                term_key="beta",
                definition="Beta.",
                definition_hash="hash-beta",
            ),
        )

        result = apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=[p1, p0],
            approved_proposal_ids={PIDS[0], PIDS[1]},
            actor=ACTOR,
            dry_run=False,
        )
        assert len(result.applied) == 2
        # First applied is PIDS[0] (lexicographically smaller)
        assert result.applied[0].proposal_id == PIDS[0]
        assert result.applied[1].proposal_id == PIDS[1]


# ---------------------------------------------------------------------------
# Proposals not in approved_ids and not flag_not_helpful are excluded
# ---------------------------------------------------------------------------


class TestEffectiveBatch:
    def test_unapproved_proposal_excluded(self, tmp_path: Path) -> None:
        repo_root = _make_repo(tmp_path, [EVT_A])
        approved = _proposal(
            PIDS[0],
            AddGlossaryTermPayload(
                kind="add_glossary_term",
                term_key="approved",
                definition="Approved.",
                definition_hash="hash-app",
            ),
        )
        unapproved = _proposal(
            PIDS[1],
            AddGlossaryTermPayload(
                kind="add_glossary_term",
                term_key="unapproved",
                definition="Not approved.",
                definition_hash="hash-unapp",
            ),
        )
        result = apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=[approved, unapproved],
            approved_proposal_ids={PIDS[0]},  # PIDS[1] not approved
            actor=ACTOR,
            dry_run=False,
        )
        assert len(result.applied) == 1
        assert result.applied[0].proposal_id == PIDS[0]


# ---------------------------------------------------------------------------
# rewire_edge apply
# ---------------------------------------------------------------------------


class TestRewireEdge:
    def test_apply_rewire_success(self, tmp_path: Path) -> None:
        from specify_cli.retrospective.schema import RewireEdgePayload

        repo_root = _make_repo(tmp_path, [EVT_A])
        p = _proposal(
            PIDS[0],
            RewireEdgePayload(
                kind="rewire_edge",
                edge_old=EdgeSpec(from_node="A", to_node="B", kind="uses"),
                edge_new=EdgeSpec(from_node="A", to_node="C", kind="uses"),
            ),
        )
        result = apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=[p],
            approved_proposal_ids={PIDS[0]},
            actor=ACTOR,
            dry_run=False,
        )
        assert len(result.applied) == 1
        assert "drg:edge" in result.applied[0].target_urn

    def test_rewire_replaces_existing_edge(self, tmp_path: Path) -> None:
        import yaml as _yaml
        from specify_cli.retrospective.schema import RewireEdgePayload

        repo_root = _make_repo(tmp_path, [EVT_A])

        drg_dir = repo_root / ".kittify" / "drg"
        drg_dir.mkdir(parents=True)
        edges_path = drg_dir / "edges.yaml"
        existing = [{"from_node": "A", "to_node": "B", "kind": "uses"}]
        with edges_path.open("w") as fh:
            _yaml.safe_dump(existing, fh)

        p = _proposal(
            PIDS[0],
            RewireEdgePayload(
                kind="rewire_edge",
                edge_old=EdgeSpec(from_node="A", to_node="B", kind="uses"),
                edge_new=EdgeSpec(from_node="A", to_node="C", kind="uses"),
            ),
        )
        apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=[p],
            approved_proposal_ids={PIDS[0]},
            actor=ACTOR,
            dry_run=False,
        )
        with edges_path.open("r") as fh:
            loaded = _yaml.safe_load(fh)
        assert isinstance(loaded, list)
        from_tos = [(e["from_node"], e["to_node"]) for e in loaded]
        assert ("A", "B") not in from_tos
        assert ("A", "C") in from_tos


# ---------------------------------------------------------------------------
# add_edge with existing edges.yaml (load path)
# ---------------------------------------------------------------------------


class TestAddEdgeExisting:
    def test_add_edge_appends_to_existing(self, tmp_path: Path) -> None:
        import yaml as _yaml

        repo_root = _make_repo(tmp_path, [EVT_A])

        drg_dir = repo_root / ".kittify" / "drg"
        drg_dir.mkdir(parents=True)
        edges_path = drg_dir / "edges.yaml"
        existing = [{"from_node": "X", "to_node": "Y", "kind": "provides"}]
        with edges_path.open("w") as fh:
            _yaml.safe_dump(existing, fh)

        p = _proposal(
            PIDS[0],
            AddEdgePayload(
                kind="add_edge",
                edge=EdgeSpec(from_node="A", to_node="B", kind="uses"),
            ),
        )
        apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=[p],
            approved_proposal_ids={PIDS[0]},
            actor=ACTOR,
            dry_run=False,
        )
        with edges_path.open("r") as fh:
            loaded = _yaml.safe_load(fh)
        assert isinstance(loaded, list)
        assert loaded == [
            {"from_node": "X", "to_node": "Y", "kind": "provides"},
            {"from_node": "A", "to_node": "B", "kind": "uses"},
        ]


# ---------------------------------------------------------------------------
# _load_event_ids edge cases
# ---------------------------------------------------------------------------


class TestLoadEventIdsEdgeCases:
    def test_empty_lines_skipped(self, tmp_path: Path) -> None:
        from specify_cli.doctrine_synthesizer.apply import _load_event_ids

        events_path = tmp_path / "status.events.jsonl"
        events_path.write_text(
            '\n\n{"event_id": "01KQ6YEGT4YBZ3GZF7X680KQ3X"}\n\n',
            encoding="utf-8",
        )
        ids = _load_event_ids(tmp_path)
        assert "01KQ6YEGT4YBZ3GZF7X680KQ3X" in ids

    def test_bad_json_lines_skipped(self, tmp_path: Path) -> None:
        from specify_cli.doctrine_synthesizer.apply import _load_event_ids

        events_path = tmp_path / "status.events.jsonl"
        events_path.write_text(
            'not-json\n{"event_id": "01KQ6YEGT4YBZ3GZF7X680KQ3X"}\n',
            encoding="utf-8",
        )
        ids = _load_event_ids(tmp_path)
        assert "01KQ6YEGT4YBZ3GZF7X680KQ3X" in ids

    def test_no_events_file_returns_empty(self, tmp_path: Path) -> None:
        from specify_cli.doctrine_synthesizer.apply import _load_event_ids

        ids = _load_event_ids(tmp_path)
        assert ids == set()


# ---------------------------------------------------------------------------
# _resolve_source_event_ids: missing kitty-specs dir
# ---------------------------------------------------------------------------


class TestResolveSourceEventIds:
    def test_missing_kitty_specs_returns_empty(self, tmp_path: Path) -> None:
        from specify_cli.doctrine_synthesizer.apply import _resolve_source_event_ids

        repo_root = tmp_path / "no-kitty-specs"
        repo_root.mkdir()
        result = _resolve_source_event_ids(MISSION_ID, repo_root)
        assert result == set()

    def test_non_matching_mission_returns_empty(self, tmp_path: Path) -> None:
        from specify_cli.doctrine_synthesizer.apply import _resolve_source_event_ids

        repo_root = tmp_path
        kitty_specs = repo_root / "kitty-specs" / "some-mission"
        kitty_specs.mkdir(parents=True)
        meta = {"mission_id": "01KQ6YEGT4YBZ3GZF7X680KQ3W", "mission_slug": "other"}
        (kitty_specs / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

        result = _resolve_source_event_ids(MISSION_ID, repo_root)
        assert result == set()

    def test_dir_without_meta_json_skipped(self, tmp_path: Path) -> None:
        from specify_cli.doctrine_synthesizer.apply import _resolve_source_event_ids

        repo_root = tmp_path
        kitty_specs = repo_root / "kitty-specs" / "no-meta-mission"
        kitty_specs.mkdir(parents=True)

        result = _resolve_source_event_ids(MISSION_ID, repo_root)
        assert result == set()


# ---------------------------------------------------------------------------
# dry_run planned list for rewire / synthesize kinds
# ---------------------------------------------------------------------------


class TestPlannedDryRun:
    def test_rewire_edge_in_planned(self, tmp_path: Path) -> None:
        from specify_cli.retrospective.schema import RewireEdgePayload

        repo_root = _make_repo(tmp_path, [EVT_A])
        p = _proposal(
            PIDS[0],
            RewireEdgePayload(
                kind="rewire_edge",
                edge_old=EdgeSpec(from_node="A", to_node="B", kind="uses"),
                edge_new=EdgeSpec(from_node="A", to_node="C", kind="uses"),
            ),
        )
        result = apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=[p],
            approved_proposal_ids={PIDS[0]},
            actor=ACTOR,
            dry_run=True,
        )
        assert len(result.planned) == 1
        assert "rewire" in result.planned[0].diff_preview

    def test_synthesize_directive_in_planned(self, tmp_path: Path) -> None:
        repo_root = _make_repo(tmp_path, [EVT_A])
        p = _proposal(
            PIDS[0],
            SynthesizeDirectivePayload(
                kind="synthesize_directive",
                artifact_id="dir-plan-001",
                body="Body.",
                body_hash="h",
                scope=_EMPTY_SCOPE,
            ),
        )
        result = apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=[p],
            approved_proposal_ids={PIDS[0]},
            actor=ACTOR,
            dry_run=True,
        )
        assert len(result.planned) == 1
        assert "directive" in result.planned[0].diff_preview

    def test_flag_not_helpful_in_planned(self, tmp_path: Path) -> None:
        repo_root = _make_repo(tmp_path, [EVT_A])
        p = _proposal(
            PIDS[0],
            FlagNotHelpfulPayload(
                kind="flag_not_helpful",
                target=TargetReference(kind="drg_node", urn="drg:node:foo"),
            ),
        )
        result = apply_proposals(
            mission_id=MISSION_ID,
            repo_root=repo_root,
            proposals=[p],
            approved_proposal_ids={PIDS[0]},
            actor=ACTOR,
            dry_run=True,
        )
        assert len(result.planned) == 1
        assert "not_helpful" in result.planned[0].diff_preview
