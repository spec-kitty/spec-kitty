"""Provenance sidecar tests (T034, T035, T036).

Verifies:
- Sidecar carries all FR-022 minimum fields:
    artifact_id, source, source_mission_id, source_proposal_id,
    source_evidence_event_ids, applied_by, applied_at, re_applied
- Re-run sets re_applied: True
- Canonical path scheme is deterministic
- is_already_applied() correctly identifies existing sidecars
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.charter_pack_synthesizer.provenance import (
    is_already_applied,
    load_provenance,
    provenance_path,
    write_provenance,
)
from specify_cli.retrospective.schema import (
    ActorRef,
    AddGlossaryTermPayload,
    Proposal,
    ProposalProvenance,
    ProposalState,
)

pytestmark = pytest.mark.fast

# ---------------------------------------------------------------------------
# Shared test identifiers (26-char Crockford base32 ULIDs)
# ---------------------------------------------------------------------------

MISSION_ID = "01KQ6YEGT4YBZ3GZF7X680KQ3V"
PROPOSAL_ID = "01KQ6YEGT4YBZ3GZF7X680KQ4A"
EVT_A = "01KQ6YEGT4YBZ3GZF7X680KQ3X"
EVT_B = "01KQ6YEGT4YBZ3GZF7X680KQ3Y"

HUMAN_ACTOR = ActorRef(kind="human", id="rob@robshouse.net", profile_id=None)
AGENT_ACTOR = ActorRef(kind="agent", id="claude-opus-4-7", profile_id="facilitator")


def _make_proposal(
    mission_id: str = MISSION_ID,
    proposal_id: str = PROPOSAL_ID,
    evidence: list[str] | None = None,
) -> Proposal:
    return Proposal(
        id=proposal_id,
        kind="add_glossary_term",
        payload=AddGlossaryTermPayload(
            kind="add_glossary_term",
            term_key="test-term",
            definition="A test term.",
            definition_hash="abc123",
        ),
        rationale="test rationale",
        state=ProposalState(status="accepted"),
        provenance=ProposalProvenance(
            source_mission_id=mission_id,
            source_evidence_event_ids=evidence or [EVT_A, EVT_B],
            authored_by=AGENT_ACTOR,
            approved_by=HUMAN_ACTOR,
        ),
    )


# ---------------------------------------------------------------------------
# provenance_path()
# ---------------------------------------------------------------------------


class TestProvenancePath:
    def test_deterministic_given_artifact_and_id(self, tmp_path: Path) -> None:
        artifact = tmp_path / "glossary" / "term.yaml"
        path1 = provenance_path(artifact, "my-term")
        path2 = provenance_path(artifact, "my-term")
        assert path1 == path2

    def test_sidecar_in_dot_provenance_subdir(self, tmp_path: Path) -> None:
        artifact = tmp_path / "glossary" / "term.yaml"
        p = provenance_path(artifact, "my-term")
        assert p.parent.name == ".provenance"
        assert p.parent.parent == artifact.parent

    def test_filename_is_artifact_id_dot_yaml(self, tmp_path: Path) -> None:
        artifact = tmp_path / "glossary" / "term.yaml"
        p = provenance_path(artifact, "my-term")
        assert p.name == "my-term.yaml"


# ---------------------------------------------------------------------------
# write_provenance() — FR-022 minimum field set
# ---------------------------------------------------------------------------


class TestWriteProvenance:
    def test_writes_all_minimum_fields(self, tmp_path: Path) -> None:
        artifact = tmp_path / "glossary" / "test-term.yaml"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("definition: test", encoding="utf-8")

        proposal = _make_proposal()
        sidecar = write_provenance(
            artifact_path=artifact,
            artifact_id="test-term",
            proposal=proposal,
            actor=HUMAN_ACTOR,
            re_applied=False,
        )

        assert sidecar.exists()
        data = load_provenance(sidecar)
        assert data is not None

        # FR-022 minimum fields
        assert data["artifact_id"] == "test-term"
        assert data["source"] == "retrospective"
        assert data["source_mission_id"] == MISSION_ID
        assert data["source_proposal_id"] == PROPOSAL_ID
        assert data["source_evidence_event_ids"] == [EVT_A, EVT_B]
        assert data["applied_by"]["kind"] == "human"
        assert data["applied_by"]["id"] == "rob@robshouse.net"
        assert "applied_at" in data
        assert data["re_applied"] is False

    def test_re_applied_flag_is_true_when_set(self, tmp_path: Path) -> None:
        artifact = tmp_path / "glossary" / "test-term.yaml"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("definition: test", encoding="utf-8")

        proposal = _make_proposal()
        sidecar = write_provenance(
            artifact_path=artifact,
            artifact_id="test-term",
            proposal=proposal,
            actor=HUMAN_ACTOR,
            re_applied=True,
        )

        data = load_provenance(sidecar)
        assert data is not None
        assert data["re_applied"] is True

    def test_creates_provenance_subdir(self, tmp_path: Path) -> None:
        artifact = tmp_path / "deep" / "nested" / "term.yaml"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("x: 1", encoding="utf-8")

        proposal = _make_proposal()
        sidecar = write_provenance(
            artifact_path=artifact,
            artifact_id="term",
            proposal=proposal,
            actor=HUMAN_ACTOR,
        )
        assert sidecar.parent.exists()
        assert sidecar.parent.name == ".provenance"

    def test_returns_absolute_path(self, tmp_path: Path) -> None:
        artifact = tmp_path / "glossary" / "t.yaml"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("x: 1", encoding="utf-8")

        proposal = _make_proposal()
        sidecar = write_provenance(
            artifact_path=artifact,
            artifact_id="t",
            proposal=proposal,
            actor=HUMAN_ACTOR,
        )
        assert sidecar.is_absolute()


# ---------------------------------------------------------------------------
# is_already_applied() — idempotency key check
# ---------------------------------------------------------------------------


class TestIsAlreadyApplied:
    def test_false_when_no_sidecar(self, tmp_path: Path) -> None:
        artifact = tmp_path / "glossary" / "term.yaml"
        artifact.parent.mkdir(parents=True)
        sidecar = provenance_path(artifact, "term")
        assert not is_already_applied(sidecar, MISSION_ID, PROPOSAL_ID)

    def test_true_after_writing_sidecar(self, tmp_path: Path) -> None:
        artifact = tmp_path / "glossary" / "term.yaml"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("x: 1", encoding="utf-8")

        proposal = _make_proposal()
        sidecar = write_provenance(
            artifact_path=artifact,
            artifact_id="term",
            proposal=proposal,
            actor=HUMAN_ACTOR,
        )
        assert is_already_applied(sidecar, MISSION_ID, PROPOSAL_ID)

    def test_false_different_mission_id(self, tmp_path: Path) -> None:
        artifact = tmp_path / "glossary" / "term.yaml"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("x: 1", encoding="utf-8")

        proposal = _make_proposal()
        sidecar = write_provenance(
            artifact_path=artifact,
            artifact_id="term",
            proposal=proposal,
            actor=HUMAN_ACTOR,
        )
        other_mission = "01KQ6YEGT4YBZ3GZF7X680KQ3W"
        assert not is_already_applied(sidecar, other_mission, PROPOSAL_ID)

    def test_false_different_proposal_id(self, tmp_path: Path) -> None:
        artifact = tmp_path / "glossary" / "term.yaml"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("x: 1", encoding="utf-8")

        proposal = _make_proposal()
        sidecar = write_provenance(
            artifact_path=artifact,
            artifact_id="term",
            proposal=proposal,
            actor=HUMAN_ACTOR,
        )
        other_proposal = "01KQ6YEGT4YBZ3GZF7X680KQ4B"
        assert not is_already_applied(sidecar, MISSION_ID, other_proposal)


# ---------------------------------------------------------------------------
# Re-run idempotency integration
# ---------------------------------------------------------------------------


class TestReRunIdempotency:
    """Demonstrate T035: re-running with the same proposal sets re_applied=True."""

    def test_first_run_re_applied_false(self, tmp_path: Path) -> None:
        artifact = tmp_path / "glossary" / "term.yaml"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("x: 1", encoding="utf-8")

        proposal = _make_proposal()
        sidecar = write_provenance(
            artifact_path=artifact,
            artifact_id="term",
            proposal=proposal,
            actor=HUMAN_ACTOR,
            re_applied=False,
        )
        data = load_provenance(sidecar)
        assert data is not None
        assert data["re_applied"] is False

    def test_second_run_re_applied_true(self, tmp_path: Path) -> None:
        artifact = tmp_path / "glossary" / "term.yaml"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("x: 1", encoding="utf-8")

        proposal = _make_proposal()
        # First write
        write_provenance(
            artifact_path=artifact,
            artifact_id="term",
            proposal=proposal,
            actor=HUMAN_ACTOR,
            re_applied=False,
        )
        # Second write (re-run)
        sidecar = write_provenance(
            artifact_path=artifact,
            artifact_id="term",
            proposal=proposal,
            actor=HUMAN_ACTOR,
            re_applied=True,
        )
        data = load_provenance(sidecar)
        assert data is not None
        assert data["re_applied"] is True
