"""Tests for ``spec-kitty agent retrospect synthesize`` (WP08 / T041).

Exercises all exit codes (0–5), JSON envelope schema, Rich/JSON informational
equivalence (CHK034), and the --apply flag semantics.

Uses :class:`typer.testing.CliRunner` against the agent typer app.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent import app
from specify_cli.context.mission_resolver import AmbiguousHandleError, ResolvedMission
from specify_cli.doctrine_synthesizer import (
    AppliedChange,
    ConflictGroup,
    PlannedApplication,
    RejectedProposal,
    SynthesisResult,
)

# ---------------------------------------------------------------------------
# Runner + fixtures
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.integration]

runner = CliRunner()

# Valid 26-char ULIDs for test fixtures (Crockford base32: 0-9 A-H J-N P-T V-Z)
# No I, L, O, or U characters allowed.
FAKE_MISSION_ID = "01KQ6YEG000000000000000000"
FAKE_MID8 = FAKE_MISSION_ID[:8]
FAKE_SLUG = "mission-retrospective-learning-loop-01KQ6YEG"
FAKE_PROPOSAL_ID_A = "01KQ6YEG00000000000000001A"
FAKE_PROPOSAL_ID_B = "01KQ6YEG00000000000000001B"
FAKE_EVENT_ID = "01KQ6YEG00000000000000001C"

PLANNED_APP = PlannedApplication(
    proposal_id=FAKE_PROPOSAL_ID_A,
    kind="add_glossary_term",
    targets=["glossary:term:foo"],
    diff_preview="add glossary term 'foo'",
)

APPLIED_CHANGE = AppliedChange(
    proposal_id=FAKE_PROPOSAL_ID_A,
    target_urn="glossary:term:foo",
    artifact_path=".kittify/glossary/foo.yaml",
    provenance_path=".kittify/glossary/.provenance/foo.yaml",
    re_applied=False,
)

CONFLICT_GROUP = ConflictGroup(
    proposal_ids=[FAKE_PROPOSAL_ID_A, FAKE_PROPOSAL_ID_B],
    reason="Conflicting add_glossary_term proposals",
)

STALE_REJECTION = RejectedProposal(
    proposal_id=FAKE_PROPOSAL_ID_A,
    reason="stale_evidence",
    detail="Evidence event ids not reachable in source mission event log: ['01EV']",
)

INVALID_REJECTION = RejectedProposal(
    proposal_id=FAKE_PROPOSAL_ID_A,
    reason="invalid_payload",
    detail="No apply handler found",
)


def _make_resolved_mission(mission_id: str = FAKE_MISSION_ID, tmp_path: Path | None = None) -> ResolvedMission:
    """Build a fake ResolvedMission."""
    feature_dir = (tmp_path or Path("/tmp")) / "kitty-specs" / FAKE_SLUG
    return ResolvedMission(
        mission_id=mission_id,
        mission_slug=FAKE_SLUG,
        mid8=mission_id[:8],
        feature_dir=feature_dir,
    )


def _good_result(dry_run: bool = True) -> SynthesisResult:
    """A clean SynthesisResult (no conflicts/rejections)."""
    return SynthesisResult(
        dry_run=dry_run,
        planned=[PLANNED_APP],
        applied=[] if dry_run else [APPLIED_CHANGE],
        conflicts=[],
        rejected=[],
        events_emitted=[] if dry_run else [FAKE_EVENT_ID],
    )


def _conflict_result() -> SynthesisResult:
    return SynthesisResult(
        dry_run=False,
        planned=[],
        applied=[],
        conflicts=[CONFLICT_GROUP],
        rejected=[
            RejectedProposal(
                proposal_id=FAKE_PROPOSAL_ID_A,
                reason="conflict",
                detail="Conflicting proposals",
            )
        ],
        events_emitted=[],
    )


def _stale_result() -> SynthesisResult:
    return SynthesisResult(
        dry_run=False,
        planned=[PLANNED_APP],
        applied=[],
        conflicts=[],
        rejected=[STALE_REJECTION],
        events_emitted=[],
    )


# ---------------------------------------------------------------------------
# Helpers for patching the command's dependencies
# ---------------------------------------------------------------------------


def _patched_invoke(
    args: list[str],
    *,
    resolved_mission: ResolvedMission | None = None,
    result: SynthesisResult | None = None,
    read_record_side_effect: Exception | None = None,
    repo_root: Path | None = None,
) -> Any:
    """
    Invoke ``agent retrospect synthesize`` with key dependencies mocked.

    - locate_project_root → returns ``repo_root`` (default: Path("/fake/root"))
    - resolve_mission_handle → returns ``resolved_mission``
    - read_record → returns a stub RetrospectiveRecord (or raises side_effect)
    - apply_proposals → returns ``result``
    """
    root = repo_root or Path("/fake/root")
    resolved = resolved_mission or _make_resolved_mission()

    # Build a minimal stub retrospective record whose proposals list is empty
    stub_record = MagicMock()
    stub_record.proposals = []
    stub_record.mission.mission_id = FAKE_MISSION_ID

    with (
        patch(
            "specify_cli.cli.commands.agent_retrospect.locate_project_root",
            return_value=root,
        ),
        patch(
            "specify_cli.cli.commands.agent_retrospect.resolve_mission_handle",
            return_value=resolved,
        ),
        patch(
            "specify_cli.cli.commands.agent_retrospect.read_record",
            side_effect=read_record_side_effect,
            return_value=None if read_record_side_effect else stub_record,
        ),
        patch(
            "specify_cli.cli.commands.agent_retrospect.apply_proposals",
            return_value=result or _good_result(),
        ),
    ):
        return runner.invoke(app, args, catch_exceptions=False)


# ---------------------------------------------------------------------------
# Exit code 0 — valid handle, dry-run, fixture record
# ---------------------------------------------------------------------------


def test_valid_handle_dryrun_exit0() -> None:
    """Valid handle + dry-run completes cleanly (exit 0)."""
    result = _patched_invoke(
        ["retrospect", "synthesize", "--mission", "01KQ6YEG"],
        result=_good_result(dry_run=True),
    )
    assert result.exit_code == 0, result.output


def _write_generator_retrospective(root: Path) -> Path:
    """Write the generator-shape record emitted by ``retrospect create``."""
    retro_dir = root / ".kittify" / "missions" / FAKE_MISSION_ID
    retro_dir.mkdir(parents=True)
    retro_path = retro_dir / "retrospective.yaml"
    retro_path.write_text(
        f"""\
schema_version: 1
mission_id: {FAKE_MISSION_ID}
mission_slug: {FAKE_SLUG}
mission_number: 1
friendly_name: Test Mission
mission_type: software-dev
target_branch: main
created_at: "2026-05-21T08:09:55+00:00"
created_by:
  kind: human
  id: cli
  display: spec-kitty retrospect
provenance:
  kind: explicit_create
  invoked_at: "2026-05-21T08:09:55+00:00"
  policy_resolved_from: {{}}
  command: spec-kitty retrospect create
policy_source: {{}}
findings_status: has_findings
helped: []
not_helpful:
  - id: n-001
    category: process
    summary: lane bounce before approval
    evidence_refs: [e-001]
gaps: []
proposals: []
evidence_refs:
  - id: e-001
    kind: event_range
    path: kitty-specs/{FAKE_SLUG}/status.events.jsonl
    range: "event-1"
generator_version: "1.0"
provenance_history: []
""",
        encoding="utf-8",
    )
    return retro_path


def test_generator_record_dryrun_exit0(tmp_path: Path) -> None:
    """A record authored by retrospect create is accepted by synthesize."""
    root = tmp_path
    _write_generator_retrospective(root)

    with (
        patch(
            "specify_cli.cli.commands.agent_retrospect.locate_project_root",
            return_value=root,
        ),
        patch(
            "specify_cli.cli.commands.agent_retrospect.resolve_mission_handle",
            return_value=_make_resolved_mission(tmp_path=root),
        ),
        patch(
            "specify_cli.cli.commands.agent_retrospect.apply_proposals",
            return_value=_good_result(),
        ) as apply_mock,
    ):
        result = runner.invoke(
            app,
            ["retrospect", "synthesize", "--mission", FAKE_SLUG],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, result.output
    assert apply_mock.call_args.kwargs["proposals"] == []
    assert apply_mock.call_args.kwargs["dry_run"] is True


def test_generator_record_apply_exit0(tmp_path: Path) -> None:
    """A create-authored record is also accepted by the --apply path."""
    root = tmp_path
    _write_generator_retrospective(root)

    with (
        patch(
            "specify_cli.cli.commands.agent_retrospect.locate_project_root",
            return_value=root,
        ),
        patch(
            "specify_cli.cli.commands.agent_retrospect.resolve_mission_handle",
            return_value=_make_resolved_mission(tmp_path=root),
        ),
        patch(
            "specify_cli.cli.commands.agent_retrospect.apply_proposals",
            return_value=_good_result(dry_run=False),
        ) as apply_mock,
    ):
        result = runner.invoke(
            app,
            ["retrospect", "synthesize", "--mission", FAKE_SLUG, "--apply"],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, result.output
    assert apply_mock.call_args.kwargs["proposals"] == []
    assert apply_mock.call_args.kwargs["dry_run"] is False


def test_dryrun_is_default() -> None:
    """Default (no --apply flag) is dry-run."""
    result = _patched_invoke(
        ["retrospect", "synthesize", "--mission", "01KQ6YEG"],
        result=_good_result(dry_run=True),
    )
    assert result.exit_code == 0
    # Rich output should say DRY-RUN
    assert "DRY-RUN" in result.output


# ---------------------------------------------------------------------------
# Exit code 1 — ambiguous / unresolvable handle
# ---------------------------------------------------------------------------


def test_ambiguous_handle_exit1() -> None:
    """Ambiguous mission handle → exit 1."""
    mock_ambig = AmbiguousHandleError(
        handle="dup",
        candidates=[
            ResolvedMission(
                mission_id=FAKE_MISSION_ID,
                mission_slug=FAKE_SLUG,
                mid8=FAKE_MID8,
                feature_dir=Path("/fake/kitty-specs") / FAKE_SLUG,
            )
        ],
    )

    with (
        patch(
            "specify_cli.cli.commands.agent_retrospect.locate_project_root",
            return_value=Path("/fake/root"),
        ),
        patch(
            "specify_cli.cli.commands.agent_retrospect.resolve_mission_handle",
            side_effect=SystemExit(2),
        ),
    ):
        result = runner.invoke(app, ["retrospect", "synthesize", "--mission", "dup"])

    # Contract: exit 1 for unresolvable (resolve_mission_handle calls sys.exit(2),
    # the command catches SystemExit and re-raises typer.Exit(1))
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Missing retrospective record default behavior
# ---------------------------------------------------------------------------


def test_missing_record_default_exit1() -> None:
    """Missing retrospective.yaml → exit 1 with create-record guidance."""
    result = _patched_invoke(
        ["retrospect", "synthesize", "--mission", "01KQ6YEG"],
        read_record_side_effect=FileNotFoundError("not found"),
    )
    assert result.exit_code == 1


def test_malformed_record_exit3() -> None:
    """Malformed retrospective.yaml (SchemaError) → exit 3."""
    from specify_cli.retrospective.reader import SchemaError

    result = _patched_invoke(
        ["retrospect", "synthesize", "--mission", "01KQ6YEG"],
        read_record_side_effect=SchemaError("bad schema"),
    )
    assert result.exit_code == 3


def test_yaml_parse_error_exit3() -> None:
    """Invalid YAML (YAMLParseError) → exit 3."""
    from specify_cli.retrospective.reader import YAMLParseError

    result = _patched_invoke(
        ["retrospect", "synthesize", "--mission", "01KQ6YEG"],
        read_record_side_effect=YAMLParseError("bad yaml"),
    )
    assert result.exit_code == 3


def test_io_error_exit2() -> None:
    """OS-level I/O error reading retrospective → exit 2."""
    result = _patched_invoke(
        ["retrospect", "synthesize", "--mission", "01KQ6YEG"],
        read_record_side_effect=OSError("permission denied"),
    )
    assert result.exit_code == 2


# ---------------------------------------------------------------------------
# Exit code 4 — conflict batch with --apply
# ---------------------------------------------------------------------------


def test_conflict_batch_apply_exit4() -> None:
    """Conflict batch with --apply → exit 4; nothing applied."""
    result = _patched_invoke(
        ["retrospect", "synthesize", "--mission", "01KQ6YEG", "--apply"],
        result=_conflict_result(),
    )
    assert result.exit_code == 4


# ---------------------------------------------------------------------------
# Exit code 5 — stale evidence / invalid_payload rejections with --apply
# ---------------------------------------------------------------------------


def test_stale_evidence_apply_exit5() -> None:
    """Stale evidence with --apply → exit 5."""
    result = _patched_invoke(
        ["retrospect", "synthesize", "--mission", "01KQ6YEG", "--apply"],
        result=_stale_result(),
    )
    assert result.exit_code == 5


def test_invalid_payload_apply_exit5() -> None:
    """invalid_payload rejection with --apply → exit 5."""
    inv_result = SynthesisResult(
        dry_run=False,
        planned=[PLANNED_APP],
        applied=[],
        conflicts=[],
        rejected=[INVALID_REJECTION],
        events_emitted=[],
    )
    result = _patched_invoke(
        ["retrospect", "synthesize", "--mission", "01KQ6YEG", "--apply"],
        result=inv_result,
    )
    assert result.exit_code == 5


def test_apply_success_exit0() -> None:
    """Successful --apply (no conflicts/rejections) → exit 0."""
    result = _patched_invoke(
        ["retrospect", "synthesize", "--mission", "01KQ6YEG", "--apply"],
        result=_good_result(dry_run=False),
    )
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# JSON output schema
# ---------------------------------------------------------------------------


def test_json_output_schema() -> None:
    """--json output matches expected envelope schema."""
    result = _patched_invoke(
        ["retrospect", "synthesize", "--mission", "01KQ6YEG", "--json"],
        result=_good_result(dry_run=True),
    )
    assert result.exit_code == 0

    envelope = json.loads(result.output)
    assert envelope["schema_version"] == "1"
    assert envelope["command"] == "agent.retrospect.synthesize"
    assert "generated_at" in envelope
    assert envelope["dry_run"] is True
    assert "result" in envelope

    r = envelope["result"]
    assert "dry_run" in r
    assert "planned" in r
    assert "applied" in r
    assert "conflicts" in r
    assert "rejected" in r
    assert "events_emitted" in r


def test_json_envelope_apply_field() -> None:
    """dry_run field in JSON envelope is False when --apply is passed."""
    result = _patched_invoke(
        ["retrospect", "synthesize", "--mission", "01KQ6YEG", "--apply", "--json"],
        result=_good_result(dry_run=False),
    )
    assert result.exit_code == 0
    envelope = json.loads(result.output)
    assert envelope["dry_run"] is False


# ---------------------------------------------------------------------------
# Rich / JSON informational equivalence (CHK034)
# ---------------------------------------------------------------------------


def test_rich_json_informational_equivalence() -> None:
    """Rich rendering and JSON result carry the same counts and key fields.

    Asserts:
    - planned count matches between Rich summary line and JSON result
    - applied count matches
    - conflicts count matches
    - rejected count matches
    """
    synth_result = _good_result(dry_run=True)

    # Capture Rich output
    rich_result = _patched_invoke(
        ["retrospect", "synthesize", "--mission", "01KQ6YEG"],
        result=synth_result,
    )
    assert rich_result.exit_code == 0

    # Capture JSON output
    json_result = _patched_invoke(
        ["retrospect", "synthesize", "--mission", "01KQ6YEG", "--json"],
        result=synth_result,
    )
    assert json_result.exit_code == 0

    envelope = json.loads(json_result.output)
    r = envelope["result"]

    # Counts from JSON
    json_planned = len(r["planned"])
    json_applied = len(r["applied"])
    json_conflicts = len(r["conflicts"])
    json_rejected = len(r["rejected"])

    # Verify JSON counts match what was in the result
    assert json_planned == len(synth_result.planned)
    assert json_applied == len(synth_result.applied)
    assert json_conflicts == len(synth_result.conflicts)
    assert json_rejected == len(synth_result.rejected)

    # Verify Rich output summary line contains the same counts
    rich_output = rich_result.output
    assert f"planned={json_planned}" in rich_output
    assert f"applied={json_applied}" in rich_output
    assert f"conflicts={json_conflicts}" in rich_output
    assert f"rejected={json_rejected}" in rich_output


def test_rich_json_equivalence_with_conflicts() -> None:
    """Conflict case: Rich and JSON both surface the same conflict count."""
    conflict_res = _conflict_result()

    rich_result = _patched_invoke(
        ["retrospect", "synthesize", "--mission", "01KQ6YEG", "--apply"],
        result=conflict_res,
    )
    json_result = _patched_invoke(
        ["retrospect", "synthesize", "--mission", "01KQ6YEG", "--apply", "--json"],
        result=conflict_res,
    )

    envelope = json.loads(json_result.output)
    json_conflicts = len(envelope["result"]["conflicts"])
    assert json_conflicts == 1
    assert f"conflicts={json_conflicts}" in rich_result.output


# ---------------------------------------------------------------------------
# Accepted-only default and dry-run default, on a real record
# ---------------------------------------------------------------------------

REAL_MISSION_ID = "01KQ6YEGA0B1C2D3E4F5G6H7J8"
REAL_SLUG = "synth-accepted-only-01KQ6YEG"
REAL_EVIDENCE_EVENT_ID = "01KQ6YEGA0B1C2D3E4F5G6H7K9"
ACCEPTED_PROPOSAL_ID = "01KQ6YEGA0B1C2D3E4F5G6H7M1"
PENDING_PROPOSAL_ID = "01KQ6YEGA0B1C2D3E4F5G6H7M2"
REJECTED_PROPOSAL_ID = "01KQ6YEGA0B1C2D3E4F5G6H7M3"


def _glossary_proposal(proposal_id: str, term_key: str, status: str) -> Any:
    from specify_cli.retrospective.schema import (
        ActorRef,
        AddGlossaryTermPayload,
        Proposal,
        ProposalProvenance,
        ProposalState,
    )

    return Proposal(
        id=proposal_id,
        kind="add_glossary_term",
        payload=AddGlossaryTermPayload(
            kind="add_glossary_term",
            term_key=term_key,
            definition=f"Definition of {term_key}.",
            definition_hash="sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
            related_terms=[],
        ),
        rationale=f"{status} proposal",
        state=ProposalState(status=status, decided_at=None if status == "pending" else "2026-04-27T11:05:00+00:00"),
        provenance=ProposalProvenance(
            source_mission_id=REAL_MISSION_ID,
            source_evidence_event_ids=[REAL_EVIDENCE_EVENT_ID],
            authored_by=ActorRef(kind="agent", id="facilitator", profile_id=None),
        ),
    )


def _seed_project_with_mixed_proposals(root: Path) -> None:
    """A real project: mission meta, an event log holding the evidence, and a
    retrospective record (written by the production writer) carrying one
    accepted, one pending and one rejected ``add_glossary_term`` proposal."""
    from specify_cli.retrospective.schema import (
        ActorRef,
        MissionIdentity,
        Mode,
        ModeSourceSignal,
        RecordProvenance,
        RetrospectiveRecord,
    )
    from specify_cli.retrospective.writer import write_record

    (root / ".kittify").mkdir()
    feature_dir = root / "kitty-specs" / REAL_SLUG
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_id": REAL_MISSION_ID, "mission_slug": REAL_SLUG, "slug": REAL_SLUG, "mission_type": "software-dev"}),
        encoding="utf-8",
    )
    evidence = {"event_id": REAL_EVIDENCE_EVENT_ID, "event_name": "retrospective.started", "mission_id": REAL_MISSION_ID, "at": "2026-04-27T10:00:00+00:00"}
    (feature_dir / "status.events.jsonl").write_text(json.dumps(evidence) + "\n", encoding="utf-8")

    actor = ActorRef(kind="agent", id="facilitator", profile_id=None)
    completed_at = "2026-04-27T11:00:00+00:00"
    write_record(
        RetrospectiveRecord(
            schema_version="1",
            mission=MissionIdentity(
                mission_id=REAL_MISSION_ID,
                mid8=REAL_MISSION_ID[:8],
                mission_slug=REAL_SLUG,
                mission_type="software-dev",
                mission_started_at="2026-04-27T10:00:00+00:00",
                mission_completed_at=completed_at,
            ),
            mode=Mode(value="autonomous", source_signal=ModeSourceSignal(kind="environment", evidence="SPEC_KITTY_MODE")),
            status="completed",
            started_at="2026-04-27T10:55:00+00:00",
            completed_at=completed_at,
            actor=actor,
            proposals=[
                _glossary_proposal(ACCEPTED_PROPOSAL_ID, "accepted-term", "accepted"),
                _glossary_proposal(PENDING_PROPOSAL_ID, "pending-term", "pending"),
                _glossary_proposal(REJECTED_PROPOSAL_ID, "rejected-term", "rejected"),
            ],
            provenance=RecordProvenance(authored_by=actor, runtime_version="0.0.0-test", written_at=completed_at, schema_version="1"),
        ),
        repo_root=root,
    )


def _tree_digest(root: Path) -> dict[str, bytes]:
    return {str(path.relative_to(root)): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def test_synthesize_default_is_a_dry_run_of_accepted_proposals_that_touches_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without ``--apply``: only the accepted proposal is planned, and the project is byte-identical."""
    _seed_project_with_mixed_proposals(tmp_path)
    monkeypatch.chdir(tmp_path)
    before = _tree_digest(tmp_path)

    result = runner.invoke(app, ["retrospect", "synthesize", "--mission", REAL_SLUG, "--json"])

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.stdout)
    assert envelope["dry_run"] is True
    assert [planned["proposal_id"] for planned in envelope["result"]["planned"]] == [ACCEPTED_PROPOSAL_ID]
    assert envelope["result"]["applied"] == []
    assert _tree_digest(tmp_path) == before


def test_synthesize_apply_applies_only_accepted_proposals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``--apply`` with no ``--proposal-id``: the accepted term is written; pending and rejected are not."""
    _seed_project_with_mixed_proposals(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["retrospect", "synthesize", "--mission", REAL_SLUG, "--apply", "--json"])

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.stdout)
    assert envelope["dry_run"] is False
    assert [applied["proposal_id"] for applied in envelope["result"]["applied"]] == [ACCEPTED_PROPOSAL_ID]
    glossary = tmp_path / ".kittify" / "glossary"
    assert sorted(path.name for path in glossary.glob("*.yaml")) == ["accepted-term.yaml"]
    assert sorted(path.name for path in (glossary / ".provenance").glob("*.yaml")) == ["accepted-term.yaml"]


# ---------------------------------------------------------------------------
# actor-id flag
# ---------------------------------------------------------------------------


def test_actor_id_forwarded() -> None:
    """--actor-id overrides the actor passed to apply_proposals."""
    root = Path("/fake/root")
    resolved = _make_resolved_mission()

    stub_record = MagicMock()
    stub_record.proposals = []

    with (
        patch(
            "specify_cli.cli.commands.agent_retrospect.locate_project_root",
            return_value=root,
        ),
        patch(
            "specify_cli.cli.commands.agent_retrospect.resolve_mission_handle",
            return_value=resolved,
        ),
        patch(
            "specify_cli.cli.commands.agent_retrospect.read_record",
            return_value=stub_record,
        ),
        patch(
            "specify_cli.cli.commands.agent_retrospect.apply_proposals",
            return_value=_good_result(),
        ) as mock_apply,
    ):
        runner.invoke(
            app,
            ["retrospect", "synthesize", "--mission", "01KQ6YEG", "--actor-id", "my-agent"],
            catch_exceptions=False,
        )

    actor = mock_apply.call_args.kwargs["actor"]
    assert actor.id == "my-agent"
    assert actor.kind == "agent"


# ---------------------------------------------------------------------------
# json-out flag
# ---------------------------------------------------------------------------


def test_json_out_writes_file(tmp_path: Path) -> None:
    """--json-out writes the JSON envelope to the specified path."""
    out_file = tmp_path / "out" / "plan.json"

    result = _patched_invoke(
        ["retrospect", "synthesize", "--mission", "01KQ6YEG", "--json-out", str(out_file)],
        result=_good_result(dry_run=True),
    )
    assert result.exit_code == 0
    assert out_file.exists()
    envelope = json.loads(out_file.read_text())
    assert envelope["schema_version"] == "1"
    assert envelope["command"] == "agent.retrospect.synthesize"


def test_invalid_category_reports_generator_diagnosis_not_pydantic_wall(tmp_path: Path) -> None:
    """#3533: one bad enum value must not surface ~100 errors for the other schema.

    A record written by ``retrospect create`` is generator-shaped, so the nested
    Pydantic reader always rejects it. When the generator reader ALSO rejects it,
    the actionable message is the generator's one-liner naming the field -- not
    the Pydantic error list, which describes a schema the file never targeted.
    Reporting the wrong one twice led readers to conclude the tool contradicts
    itself when a single category value was wrong.
    """
    root = tmp_path
    retro_path = _write_generator_retrospective(root)
    retro_path.write_text(
        retro_path.read_text(encoding="utf-8").replace(
            "category: process", "category: terminus"
        ),
        encoding="utf-8",
    )

    with (
        patch(
            "specify_cli.cli.commands.agent_retrospect.locate_project_root",
            return_value=root,
        ),
        patch(
            "specify_cli.cli.commands.agent_retrospect.resolve_mission_handle",
            return_value=_make_resolved_mission(tmp_path=root),
        ),
    ):
        result = runner.invoke(
            app,
            ["retrospect", "synthesize", "--mission", FAKE_SLUG],
            catch_exceptions=False,
        )

    assert result.exit_code == 3, result.output
    # The generator reader's precise diagnosis is what reaches the operator.
    assert "not_helpful[0].category is invalid" in result.output, result.output
    # And the allow-list, because it is otherwise only a frozenset in reader.py.
    assert "Allowed finding categories:" in result.output, result.output
    assert "review_loop" in result.output, result.output
    # The Pydantic wall for the schema this file never targeted must NOT appear.
    assert "extra_forbidden" not in result.output, result.output
    assert "Field required" not in result.output, result.output


def test_invalid_proposal_category_reports_proposal_allow_list(tmp_path: Path) -> None:
    """#3537 landing: findings and proposals both raise "<label>.category is invalid"
    but draw from DIFFERENT allow-lists. A bad *proposal* category must be handed the
    proposal vocabulary, not the finding one — otherwise the "accurate diagnosis" the
    fix promises steers the author toward values that are invalid for a proposal.
    """
    root = tmp_path
    retro_path = _write_generator_retrospective(root)
    # Findings stay valid; add a proposal whose category is out of the proposal set.
    retro_path.write_text(
        retro_path.read_text(encoding="utf-8").replace(
            "proposals: []",
            "proposals:\n  - id: p-001\n    category: implementation\n",
        ),
        encoding="utf-8",
    )

    with (
        patch(
            "specify_cli.cli.commands.agent_retrospect.locate_project_root",
            return_value=root,
        ),
        patch(
            "specify_cli.cli.commands.agent_retrospect.resolve_mission_handle",
            return_value=_make_resolved_mission(tmp_path=root),
        ),
    ):
        result = runner.invoke(
            app,
            ["retrospect", "synthesize", "--mission", FAKE_SLUG],
            catch_exceptions=False,
        )

    assert result.exit_code == 3, result.output
    # `implementation` is a valid FINDING category but NOT a proposal one, so the
    # generator reader flags the proposal and we must show the proposal allow-list.
    assert "proposals[0].category is invalid" in result.output, result.output
    assert "Allowed proposal categories:" in result.output, result.output
    assert "glossary" in result.output, result.output  # proposal-only value
    # The finding allow-list (and its finding-only values) must NOT be offered here.
    assert "Allowed finding categories:" not in result.output, result.output
    assert "review_loop" not in result.output, result.output
    assert "spec_quality" not in result.output, result.output


def test_invalid_category_json_surface_carries_diagnosis_and_allow_list(tmp_path: Path) -> None:
    """#3537: the ``--json`` envelope's ``detail`` carries the same corrected
    generator diagnosis and allow-list as the Rich surface, not the Pydantic wall.
    """
    root = tmp_path
    retro_path = _write_generator_retrospective(root)
    retro_path.write_text(
        retro_path.read_text(encoding="utf-8").replace(
            "category: process", "category: terminus"
        ),
        encoding="utf-8",
    )

    with (
        patch(
            "specify_cli.cli.commands.agent_retrospect.locate_project_root",
            return_value=root,
        ),
        patch(
            "specify_cli.cli.commands.agent_retrospect.resolve_mission_handle",
            return_value=_make_resolved_mission(tmp_path=root),
        ),
    ):
        result = runner.invoke(
            app,
            ["retrospect", "synthesize", "--mission", FAKE_SLUG, "--json"],
            catch_exceptions=False,
        )

    assert result.exit_code == 3, result.output
    envelope = json.loads(result.output)
    assert envelope["error"] == "record_malformed", envelope
    detail = envelope["detail"]
    assert "not_helpful[0].category is invalid" in detail, detail
    assert "Allowed finding categories:" in detail, detail
    assert "extra_forbidden" not in detail, detail
