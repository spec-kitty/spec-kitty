"""A generator-shape proposal can carry a structured ``payload`` (#6385).

`retrospect create` writes the generator-shape record (``GenRetrospectiveRecord``); the nested
Pydantic ``Proposal`` that ``agent retrospect synthesize`` applies carries a discriminated
``payload``. Without a payload field on the generator shape there is nothing for synthesize to
translate, which is the application half of #6385.

This module pins the record-shape half only:

* a payload written into ``retrospective.yaml`` survives ``read_gen_record()`` / ``write_gen_record()``;
* a payload-free record round-trips byte-identically (no existing record is rewritten);
* a malformed payload fails at the read boundary with a ``SchemaError`` naming the problem, and it
  is validated by the *existing* ``ProposalPayload`` union rather than a second schema.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from specify_cli.retrospective.reader import SchemaError, read_gen_record
from specify_cli.retrospective.schema import (
    GenActor,
    GenEvidenceRef,
    GenFinding,
    GenProposal,
    GenProvenance,
    GenRetrospectiveRecord,
)
from specify_cli.retrospective.writer import _dict_to_gen_record, _gen_record_to_dict, write_gen_record

pytestmark = [pytest.mark.unit, pytest.mark.fast]

MISSION_ID = "01M68ZKX1DCY9S7NM80G0YQFKY"
MISSION_SLUG = "retrospect-synthesize-generator-proposals-01M68ZKX"

_GOOD_PAYLOAD = {
    "kind": "add_glossary_term",
    "term_key": "generator-shape-record",
    "definition": "The dataclass record shape `retrospect create` writes.",
    "definition_hash": "sha256:9f2c",
    "related_terms": ["nested-record"],
}

_YAML_WITH_SCALAR_PAYLOAD = f"""\
schema_version: 1
mission_id: {MISSION_ID}
mission_slug: {MISSION_SLUG}
mission_number: null
friendly_name: synthesize generator proposals
mission_type: software-dev
target_branch: issue-6385
created_at: "2026-10-31T12:00:00+00:00"
created_by:
  kind: human
  id: cli
provenance:
  kind: explicit_create
  invoked_at: "2026-10-31T12:00:00+00:00"
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
proposals:
  - id: p-001
    category: glossary
    risk_class: structural
    summary: add a glossary term
    evidence_refs: [e-001]
    suggested_action: "add_glossary_term: generator-shape-record"
    auto_applicable: false
    payload: not-a-mapping
evidence_refs:
  - id: e-001
    kind: event_range
    path: kitty-specs/x/status.events.jsonl
    range: "{MISSION_ID}"
generator_version: "1.0"
provenance_history: []
"""


def _record(*, proposals: list[GenProposal] | None = None) -> GenRetrospectiveRecord:
    """A minimal persisted generator record with one finding."""
    return GenRetrospectiveRecord(
        schema_version=1,
        mission_id=MISSION_ID,
        mission_slug=MISSION_SLUG,
        mission_number=None,
        friendly_name="synthesize generator proposals",
        mission_type="software-dev",
        target_branch="issue-6385",
        created_at="2026-10-31T12:00:00+00:00",
        created_by=GenActor(kind="human", id="cli"),
        provenance=GenProvenance(
            kind="explicit_create",
            invoked_at="2026-10-31T12:00:00+00:00",
            policy_resolved_from={},
            command="spec-kitty retrospect create",
        ),
        policy_source={},
        findings_status="has_findings",
        helped=[],
        not_helpful=[
            GenFinding(
                id="n-001",
                category="process",
                summary="lane bounce before approval",
                evidence_refs=["e-001"],
            )
        ],
        gaps=[],
        proposals=proposals or [],
        evidence_refs=[
            GenEvidenceRef(
                id="e-001",
                kind="event_range",
                path="kitty-specs/x/status.events.jsonl",
                range="01M68ZKX1DCY9S7NM80G0YQFKY",
            )
        ],
        generator_version="1.0",
    )


def _proposal(payload: dict[str, object] | None = _GOOD_PAYLOAD) -> GenProposal:
    return GenProposal(
        id="p-001",
        category="glossary",
        risk_class="structural",
        summary="add a glossary term for the generator record shape",
        evidence_refs=["e-001"],
        suggested_action="add_glossary_term: generator-shape-record",
        auto_applicable=False,
        payload=payload,
    )


def _write(tmp_path: Path, record: GenRetrospectiveRecord) -> Path:
    return write_gen_record(record, mode="overwrite", repo_root=tmp_path)


# ---------------------------------------------------------------------------
# T001 — the payload survives a read/write round trip
# ---------------------------------------------------------------------------


def test_payload_survives_round_trip(tmp_path: Path) -> None:
    """A proposal payload written to disk is readable again, unchanged."""
    path = _write(tmp_path, _record(proposals=[_proposal()]))

    loaded = read_gen_record(path)

    assert loaded.proposals[0].payload == _GOOD_PAYLOAD


def test_payload_absent_round_trips_byte_identically(tmp_path: Path) -> None:
    """A payload-free record is not rewritten: byte identity is the contract (NFR-001)."""
    path = _write(tmp_path, _record(proposals=[_proposal(payload=None)]))
    first = path.read_bytes()

    again = _write(tmp_path, read_gen_record(path))

    assert again.read_bytes() == first


def test_payload_only_emitted_when_present() -> None:
    """The serialized mapping carries `payload` only for a proposal that has one."""
    with_payload = _gen_record_to_dict(_record(proposals=[_proposal()]))
    without_payload = _gen_record_to_dict(_record(proposals=[_proposal(payload=None)]))

    assert with_payload["proposals"][0]["payload"] == _GOOD_PAYLOAD
    assert "payload" not in without_payload["proposals"][0]


def test_dict_to_gen_record_carries_payload() -> None:
    """The writer's own hydration path (update merge) keeps the payload."""
    data = _gen_record_to_dict(_record(proposals=[_proposal()]))

    assert _dict_to_gen_record(data).proposals[0].payload == _GOOD_PAYLOAD


def test_update_merge_preserves_existing_payload() -> None:
    """`--update` keeps an existing proposal's payload instead of dropping it."""
    from specify_cli.retrospective.writer import _merge_gen_records

    existing = _record(proposals=[_proposal()])
    merged = _merge_gen_records(existing, _record(proposals=[]))

    assert merged.proposals[0].payload == _GOOD_PAYLOAD


# ---------------------------------------------------------------------------
# T004 — malformed payloads fail at the read boundary, named
# ---------------------------------------------------------------------------


def test_unknown_payload_kind_is_named(tmp_path: Path) -> None:
    bad = {"kind": "publish_everything", "artifact_id": "x"}
    path = _write(tmp_path, _record(proposals=[_proposal(payload=bad)]))

    with pytest.raises(SchemaError) as excinfo:
        read_gen_record(path)

    message = str(excinfo.value)
    assert "proposals[0].payload" in message
    assert "add_glossary_term" in message  # the accepted set is named, not just "invalid"


def test_missing_required_payload_field_is_named(tmp_path: Path) -> None:
    """A synthesize_directive without `body_hash` is rejected, not accepted silently."""
    bad = {
        "kind": "synthesize_directive",
        "artifact_id": "DIRECTIVE_099",
        "body": "text",
        "scope": {"actions": [], "profiles": []},
    }
    path = _write(tmp_path, _record(proposals=[_proposal(payload=bad)]))

    with pytest.raises(SchemaError) as excinfo:
        read_gen_record(path)

    assert "body_hash" in str(excinfo.value)


def test_unsafe_artifact_id_is_rejected(tmp_path: Path) -> None:
    """The existing SafeSlug guard applies: path traversal never reaches apply time."""
    bad = dict(_GOOD_PAYLOAD)
    bad["term_key"] = "../escape"
    path = _write(tmp_path, _record(proposals=[_proposal(payload=bad)]))

    with pytest.raises(SchemaError):
        read_gen_record(path)


def test_non_mapping_payload_is_rejected(tmp_path: Path) -> None:
    """A scalar payload is a schema error naming the proposal, not a traceback."""
    path = tmp_path / "retrospective.yaml"
    path.write_text(_YAML_WITH_SCALAR_PAYLOAD, encoding="utf-8")

    with pytest.raises(SchemaError) as excinfo:
        read_gen_record(path)

    assert "proposals[0].payload must be a mapping" in str(excinfo.value)


def test_payload_is_optional_and_defaults_to_none() -> None:
    """The dataclass default keeps every existing construction site working."""
    proposal = GenProposal(
        id="p-002",
        category="process",
        risk_class="structural",
        summary="s",
        evidence_refs=[],
        suggested_action="synthesize_directive: x",
        auto_applicable=False,
    )

    assert proposal.payload is None
    assert dataclasses.replace(proposal, payload=_GOOD_PAYLOAD).payload == _GOOD_PAYLOAD
