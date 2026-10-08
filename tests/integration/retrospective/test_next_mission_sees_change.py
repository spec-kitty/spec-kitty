"""T060 — Next mission sees applied proposal from retrospective.

Scenario:
  1. Run mission A through terminus → captures a proposal (add_glossary_term).
  2. Apply the proposal via apply_proposals(..., dry_run=False) directly.
  3. Verify the glossary term was written under .kittify/glossary/<term>.yaml.
  4. Verify the provenance sidecar was written.
  5. Run mission B through its terminus (fresh fixture) — drive gate check.
  6. Load the glossary term file and assert provenance references mission A's
     mission_id and the proposal_id.

This tests the full retrospective → apply → next-mission-context chain
using public APIs only (run_terminus + apply_proposals).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]

from specify_cli.charter_pack_synthesizer.apply import apply_proposals
from runtime.next._internal_runtime.retrospective_terminus import run_terminus
from specify_cli.retrospective.schema import (
    ActorRef,
    AddGlossaryTermPayload,
    MissionIdentity,
    Mode,
    ModeSourceSignal,
    Proposal,
    ProposalProvenance,
    ProposalState,
    RecordProvenance,
    RetrospectiveRecord,
)

from tests.integration.retrospective.conftest import (
    HUMAN_ACTOR,
    event_names,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.integration]

def _setup_repo(
    tmp_path: Path,
    slug: str,
    mode: str = "autonomous",
) -> tuple[Path, str]:
    """Create a minimal repo for terminus tests.

    Returns (feature_dir, mission_id).
    """
    import ulid as _ulid

    mission_id = str(_ulid.ULID())
    feature_dir = tmp_path / "kitty-specs" / slug
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "mission_id": mission_id,
        "mission_slug": slug,
        "mission_type": "software-dev",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return feature_dir, mission_id


def _make_proposal(
    *,
    mission_id: str,
    event_id: str,
    term_key: str,
) -> Proposal:
    """Build a minimal add_glossary_term proposal with source provenance."""
    import ulid as _ulid

    return Proposal(
        id=str(_ulid.ULID()),
        kind="add_glossary_term",
        payload=AddGlossaryTermPayload(
            kind="add_glossary_term",
            term_key=term_key,
            definition=f"Definition of '{term_key}' added by retrospective.",
            definition_hash="sha256:feedc0de",
            related_terms=[],
        ),
        rationale="Introduced during WP11 integration test.",
        state=ProposalState(status="accepted", decided_at="2026-04-27T11:05:00+00:00"),
        provenance=ProposalProvenance(
            source_mission_id=mission_id,
            source_evidence_event_ids=[event_id],
            authored_by=ActorRef(kind="agent", id="facilitator", profile_id=None),
        ),
    )


def _make_record_with_proposal(
    *,
    mission_id: str,
    mission_slug: str,
    proposal: Proposal,
) -> RetrospectiveRecord:
    """Build a completed record carrying one proposal."""
    actor_ref = ActorRef(kind="agent", id="facilitator", profile_id=None)
    now = "2026-04-27T11:00:00+00:00"
    return RetrospectiveRecord(
        schema_version="1",
        mission=MissionIdentity(
            mission_id=mission_id,
            mid8=mission_id[:8],
            mission_slug=mission_slug,
            mission_type="software-dev",
            mission_started_at="2026-04-27T10:00:00+00:00",
            mission_completed_at=now,
        ),
        mode=Mode(
            value="autonomous",
            source_signal=ModeSourceSignal(kind="environment", evidence="SPEC_KITTY_MODE"),
        ),
        status="completed",
        started_at="2026-04-27T10:55:00+00:00",
        completed_at=now,
        actor=actor_ref,
        proposals=[proposal],
        provenance=RecordProvenance(
            authored_by=actor_ref,
            runtime_version="0.0.0-test",
            written_at=now,
            schema_version="1",
        ),
    )


# ---------------------------------------------------------------------------
# T060 — Next mission sees applied proposal
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_next_mission_sees_applied_glossary_term(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mission A retrospective → apply proposal → Mission B sees the glossary term.

    Steps:
    1. Run mission A through terminus with a proposal (add_glossary_term).
    2. Apply the proposal via apply_proposals(dry_run=False).
    3. Assert the glossary term file exists under .kittify/glossary/.
    4. Run mission B through its terminus (no facilitator — HiC skip path to avoid
       needing a real facilitator; gate allows HiC skip).
    5. Load the glossary term and assert provenance links back to mission A.
    """
    monkeypatch.setenv("SPEC_KITTY_MODE", "autonomous")

    # --------------------
    # Mission A setup
    # --------------------
    slug_a = "mission-a-retrospective"
    feature_dir_a, mission_id_a = _setup_repo(tmp_path, slug_a)

    # Seed a synthetic event id so the proposal's source_evidence_event_ids
    # resolves as non-stale during apply_proposals staleness check.
    import ulid as _ulid

    seeded_event_id = str(_ulid.ULID())
    seed_event = {
        "event_id": seeded_event_id,
        "event_name": "retrospective.started",
        "mission_id": mission_id_a,
        "at": "2026-04-27T10:00:00+00:00",
    }
    events_path = feature_dir_a / "status.events.jsonl"
    events_path.write_text(json.dumps(seed_event) + "\n", encoding="utf-8")

    term_key = "terminus-glossary-term"
    proposal = _make_proposal(
        mission_id=mission_id_a,
        event_id=seeded_event_id,
        term_key=term_key,
    )

    record = _make_record_with_proposal(
        mission_id=mission_id_a,
        mission_slug=slug_a,
        proposal=proposal,
    )

    def facilitator_a(**kwargs: Any) -> RetrospectiveRecord:
        return record

    # Run mission A's terminus.
    run_terminus(
        mission_id=mission_id_a,
            mission_type="software-dev",
        feature_dir=feature_dir_a,
        repo_root=tmp_path,
        operator_actor=HUMAN_ACTOR,
        facilitator_callback=facilitator_a,
    )

    names_a = event_names(feature_dir_a)
    assert "retrospective.completed" in names_a, (
        f"Mission A did not complete retrospective: {names_a}"
    )

    # --------------------
    # Apply the proposal (simulating the operator running the synthesizer CLI).
    # --------------------
    apply_actor = ActorRef(kind="human", id="operator", profile_id=None)
    result = apply_proposals(
        mission_id=mission_id_a,
        repo_root=tmp_path,
        proposals=[proposal],
        approved_proposal_ids={proposal.id},
        actor=apply_actor,
        dry_run=False,
    )

    assert len(result.applied) == 1, (
        f"Expected 1 applied change, got {len(result.applied)}. "
        f"Rejected: {result.rejected}"
    )
    assert len(result.rejected) == 0, f"Unexpected rejections: {result.rejected}"

    # --------------------
    # Verify glossary term was written.
    # --------------------
    glossary_file = tmp_path / ".kittify" / "glossary" / f"{term_key}.yaml"
    assert glossary_file.exists(), (
        f"Glossary term file not found: {glossary_file}"
    )

    term_data = yaml.safe_load(glossary_file.read_text(encoding="utf-8"))
    assert term_data["term_key"] == term_key
    assert "Definition of" in term_data["definition"]

    # --------------------
    # Verify provenance sidecar links to mission A and proposal_id.
    # --------------------
    applied_change = result.applied[0]
    assert applied_change.target_urn == f"glossary:term:{term_key}"
    prov_path = Path(applied_change.provenance_path)
    assert prov_path.exists(), f"Provenance sidecar not found: {prov_path}"

    prov_data = yaml.safe_load(prov_path.read_text(encoding="utf-8"))
    assert prov_data["source_mission_id"] == mission_id_a, (
        f"Provenance source_mission_id mismatch: {prov_data}"
    )
    assert prov_data["source_proposal_id"] == proposal.id, (
        f"Provenance source_proposal_id mismatch: {prov_data}"
    )

    # --------------------
    # Mission B: run through terminus (HiC skip path to keep test self-contained).
    # --------------------
    monkeypatch.setenv("SPEC_KITTY_MODE", "human_in_command")

    slug_b = "mission-b-next"
    feature_dir_b, mission_id_b = _setup_repo(tmp_path, slug_b)

    def hic_skip_b() -> tuple[bool, str | None]:
        return False, "Mission B skips retrospective in this integration test"

    # Mission B runs terminus; the glossary term applied from A is available
    # at repo_root/.kittify/glossary/ for B's context loading.
    run_terminus(
        mission_id=mission_id_b,
            mission_type="software-dev",
        feature_dir=feature_dir_b,
        repo_root=tmp_path,
        operator_actor=HUMAN_ACTOR,
        facilitator_callback=None,
        hic_prompt=hic_skip_b,
    )

    # Gate must allow mission B to complete (HiC skip is permitted).
    names_b = event_names(feature_dir_b)
    assert "retrospective.skipped" in names_b, (
        f"Mission B did not emit skipped event: {names_b}"
    )

    # --------------------
    # Assert the glossary term persists and is accessible after mission B's terminus.
    # This verifies the "next mission sees the change" contract.
    # --------------------
    assert glossary_file.exists(), (
        "Glossary term file should still exist after mission B's terminus"
    )
    final_term = yaml.safe_load(glossary_file.read_text(encoding="utf-8"))
    assert final_term["term_key"] == term_key, (
        f"Glossary term_key changed unexpectedly: {final_term}"
    )
