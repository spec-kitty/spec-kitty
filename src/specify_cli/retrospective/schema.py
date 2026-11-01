"""Pydantic v2 schema for retrospective.yaml (schema_version=1) and
dataclass-based generator record schema (WP02).

Source-of-truth (Pydantic models): kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/data-model.md
Contract (Pydantic):               kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/contracts/retrospective_yaml_v1.md

Source-of-truth (generator records): kitty-specs/retrospective-default-policy-01KS049J/data-model.md
Contract (generator records):        kitty-specs/retrospective-default-policy-01KS049J/contracts/retrospective-record.schema.json
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal, Union

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

# ---------------------------------------------------------------------------
# Identity primitives
# ---------------------------------------------------------------------------

#: 26-char Crockford base32 ULID (no I, L, O, U)
_ULID_PATTERN = r"^[0-9A-HJ-KM-NP-TV-Z]{26}$"

MissionId = Annotated[str, StringConstraints(pattern=_ULID_PATTERN)]
Mid8 = Annotated[str, StringConstraints(min_length=8, max_length=8)]
EventId = Annotated[str, StringConstraints(pattern=_ULID_PATTERN)]
ProposalId = Annotated[str, StringConstraints(pattern=_ULID_PATTERN)]
Timestamp = Annotated[str, StringConstraints(min_length=1)]


# ---------------------------------------------------------------------------
# ActorRef
# ---------------------------------------------------------------------------


class ActorRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["human", "agent", "runtime"]
    id: str
    profile_id: str | None = None


# ---------------------------------------------------------------------------
# MissionIdentity, ModeSourceSignal, Mode
# ---------------------------------------------------------------------------


class MissionIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mission_id: MissionId
    mid8: Mid8
    mission_slug: str
    mission_type: str
    mission_started_at: Timestamp
    mission_completed_at: Timestamp | None = None


class ModeSourceSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["charter_override", "explicit_flag", "environment", "parent_process"]
    evidence: str


class Mode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: Literal["autonomous", "human_in_command"]
    source_signal: ModeSourceSignal


# ---------------------------------------------------------------------------
# TargetReference
# ---------------------------------------------------------------------------


class TargetReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal[
        "doctrine_directive",
        "doctrine_tactic",
        "doctrine_procedure",
        "drg_edge",
        "drg_node",
        "glossary_term",
        "prompt_template",
        "test",
        "context_artifact",
    ]
    urn: str


# ---------------------------------------------------------------------------
# Provenance models
# ---------------------------------------------------------------------------


class FindingProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_mission_id: MissionId
    evidence_event_ids: list[EventId] = Field(min_length=1)
    actor: ActorRef
    captured_at: Timestamp


class ProposalProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_mission_id: MissionId
    source_evidence_event_ids: list[EventId]
    authored_by: ActorRef
    approved_by: ActorRef | None = None


class RecordProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authored_by: ActorRef
    runtime_version: str
    written_at: Timestamp
    schema_version: Literal["1"]


# ---------------------------------------------------------------------------
# Finding
# ---------------------------------------------------------------------------


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    target: TargetReference
    note: str = Field(max_length=2000)
    provenance: FindingProvenance


# ---------------------------------------------------------------------------
# ProposalState, ProposalApplyAttempt
# ---------------------------------------------------------------------------


class ProposalApplyAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt_id: EventId
    at: Timestamp
    outcome: Literal["applied", "rejected_conflict", "rejected_stale", "rejected_invalid"]
    error: str | None = None


class ProposalState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["pending", "accepted", "rejected", "applied", "superseded"]
    decided_at: Timestamp | None = None
    decided_by: ActorRef | None = None
    apply_attempts: list[ProposalApplyAttempt] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Proposal payload models (discriminated union)
# ---------------------------------------------------------------------------


class SynthesizeScope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actions: list[str] = Field(default_factory=list)
    profiles: list[str] = Field(default_factory=list)


# Validator applied to filesystem-bound identifiers (term_key, artifact_id).
# The contract uses both lowercase glossary terms (e.g. ``mission-id``) and
# mixed-case doctrine artifact ids (e.g. ``DIRECTIVE_001``,
# ``TACTIC_phase_2``, ``PROCEDURE-v2``), so the alphabet must accept both.
# The security shape is what matters:
#   * length 1-128 (rules out empty)
#   * alphabet limited to [A-Za-z0-9._-] (no path separators, no spaces, no
#     control characters or shell meta)
#   * no leading dot (no hidden file)
#   * no ``..`` substring anywhere (no traversal)
# Pydantic v2 uses the Rust regex engine, which has no look-around, so the
# composite check is split into a regex (alphabet + length) plus an
# AfterValidator for the structural ``..``/leading-dot rules.
# ``_assert_within`` in apply.py adds defense in depth at write time.
_SLUG_REGEX = r"^[A-Za-z0-9._-]{1,128}$"


def _validate_safe_slug(value: str) -> str:
    if value.startswith("."):
        raise ValueError(
            "identifier must not start with '.': leading-dot names are reserved"
        )
    if ".." in value:
        raise ValueError(
            "identifier must not contain '..': path-traversal sequences are forbidden"
        )
    return value


# A reusable Annotated type so all filesystem-bound identifier fields share
# one definition. AfterValidator runs after the regex pattern validates the
# alphabet + length.
SafeSlug = Annotated[
    str,
    Field(pattern=_SLUG_REGEX),
    AfterValidator(_validate_safe_slug),
]


class SynthesizeDirectivePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["synthesize_directive"]
    artifact_id: SafeSlug
    body: str
    body_hash: str
    scope: SynthesizeScope


class SynthesizeTacticPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["synthesize_tactic"]
    artifact_id: SafeSlug
    body: str
    body_hash: str
    scope: SynthesizeScope


class SynthesizeProcedurePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["synthesize_procedure"]
    artifact_id: SafeSlug
    body: str
    body_hash: str
    scope: SynthesizeScope


class EdgeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_node: str
    to_node: str
    kind: str


class RewireEdgePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["rewire_edge"]
    edge_old: EdgeSpec
    edge_new: EdgeSpec


class AddEdgePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["add_edge"]
    edge: EdgeSpec


class RemoveEdgePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["remove_edge"]
    edge: EdgeSpec


class AddGlossaryTermPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["add_glossary_term"]
    term_key: SafeSlug
    definition: str
    definition_hash: str
    related_terms: list[str] = Field(default_factory=list)


class UpdateGlossaryTermPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["update_glossary_term"]
    term_key: SafeSlug
    definition: str
    definition_hash: str
    related_terms: list[str] = Field(default_factory=list)


class FlagNotHelpfulPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["flag_not_helpful"]
    target: TargetReference


# Discriminated union for all proposal payloads
ProposalPayload = Annotated[
    Union[
        SynthesizeDirectivePayload,
        SynthesizeTacticPayload,
        SynthesizeProcedurePayload,
        RewireEdgePayload,
        AddEdgePayload,
        RemoveEdgePayload,
        AddGlossaryTermPayload,
        UpdateGlossaryTermPayload,
        FlagNotHelpfulPayload,
    ],
    Field(discriminator="kind"),
]


# ---------------------------------------------------------------------------
# Proposal
# ---------------------------------------------------------------------------


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: ProposalId
    kind: Literal[
        "synthesize_directive",
        "synthesize_tactic",
        "synthesize_procedure",
        "rewire_edge",
        "add_edge",
        "remove_edge",
        "add_glossary_term",
        "update_glossary_term",
        "flag_not_helpful",
    ]
    payload: ProposalPayload
    rationale: str = Field(max_length=2000)
    state: ProposalState
    provenance: ProposalProvenance


# ---------------------------------------------------------------------------
# RetrospectiveFailure
# ---------------------------------------------------------------------------


class RetrospectiveFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal[
        "writer_io_error",
        "schema_invalid",
        "facilitator_error",
        "evidence_unreachable",
        "mode_resolution_error",
        "internal_error",
    ]
    message: str
    error_chain: list[str] = Field(max_length=16)


# ---------------------------------------------------------------------------
# RetrospectiveRecord (top-level)
# ---------------------------------------------------------------------------


class RetrospectiveRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"]
    mission: MissionIdentity
    mode: Mode
    status: Literal["completed", "skipped", "failed", "pending"]
    started_at: Timestamp
    completed_at: Timestamp | None = None
    actor: ActorRef
    helped: list[Finding] = Field(default_factory=list)
    not_helpful: list[Finding] = Field(default_factory=list)
    gaps: list[Finding] = Field(default_factory=list)
    proposals: list[Proposal] = Field(default_factory=list)
    provenance: RecordProvenance
    skip_reason: str | None = None
    failure: RetrospectiveFailure | None = None
    successor_mission_id: MissionId | None = None

    @model_validator(mode="after")
    def validate_status_conditionals(self) -> "RetrospectiveRecord":
        """Enforce status-conditional field requirements."""
        status = self.status

        if status == "completed" and self.completed_at is None:
            raise ValueError("status='completed' requires completed_at to be set")

        if status == "skipped":
            if self.skip_reason is None or len(self.skip_reason) == 0:
                raise ValueError("status='skipped' requires a non-empty skip_reason")

        if status == "failed" and self.failure is None:
            raise ValueError("status='failed' requires failure to be set")

        if status == "pending":
            raise ValueError(
                "status='pending' is not persistable; the writer refuses to materialize a pending record"
            )

        return self

    @model_validator(mode="after")
    def validate_unique_finding_ids(self) -> "RetrospectiveRecord":
        """Ensure all Finding.id values are unique within the record."""
        all_findings = list(self.helped) + list(self.not_helpful) + list(self.gaps)
        ids = [f.id for f in all_findings]
        seen: set[str] = set()
        for fid in ids:
            if fid in seen:
                raise ValueError(f"Duplicate Finding.id '{fid}' found in record")
            seen.add(fid)
        return self

    @model_validator(mode="after")
    def validate_unique_proposal_ids(self) -> "RetrospectiveRecord":
        """Ensure all Proposal.id values are unique within the record."""
        ids = [p.id for p in self.proposals]
        seen: set[str] = set()
        for pid in ids:
            if pid in seen:
                raise ValueError(f"Duplicate Proposal.id '{pid}' found in record")
            seen.add(pid)
        return self


# =============================================================================
# WP02 Generator Record Schema (dataclasses)
# Source-of-truth: kitty-specs/retrospective-default-policy-01KS049J/data-model.md
# Contract:        kitty-specs/retrospective-default-policy-01KS049J/contracts/retrospective-record.schema.json
#
# These types are prefixed "Gen" to coexist with the Pydantic types above.
# Public exports via __init__.py alias them without the "Gen" prefix.
# =============================================================================

# ---------------------------------------------------------------------------
# Validation patterns (matching JSON Schema patterns)
# ---------------------------------------------------------------------------

_FINDING_ID_RE = re.compile(r"^[a-z]-\d{3,}$")
_PROPOSAL_ID_RE = re.compile(r"^p-\d{3,}$")
_EVIDENCE_ID_RE = re.compile(r"^e-\d{3,}$")


# ---------------------------------------------------------------------------
# Type aliases for WP02 generator schema
# ---------------------------------------------------------------------------

ProvenanceKind = Literal[
    "runtime_post_completion",
    "runtime_strict_gate",
    "runtime_abandoned",
    "explicit_create",
    "backfill",
    "synthesize_fabricate",
]

FindingCategory = Literal[
    "process",
    "tooling",
    "spec_quality",
    "review_loop",
    "design",
    "implementation",
    "doc",
    "other",
]

ProposalCategory = Literal[
    "glossary",
    "drg",
    "doctrine",
    "tooling",
    "process",
    "other",
]

# Persisted records may ONLY be "has_findings" or "ran_no_findings".
# "missing" and "failed" are event-payload-only states — never persisted in a record.
FindingsStatus = Literal["has_findings", "ran_no_findings"]


# ---------------------------------------------------------------------------
# Generator sub-types (dataclasses)
# ---------------------------------------------------------------------------


@dataclass
class GenActor:
    """Identity attribution for who authored the retrospective record.

    Matches Actor in contracts/retrospective-record.schema.json.
    """

    kind: Literal["human", "agent", "runtime"]
    id: str
    display: str | None = None


@dataclass
class GenProvenance:
    """How and when the record was authored.

    Matches Provenance in contracts/retrospective-record.schema.json.
    """

    kind: ProvenanceKind
    invoked_at: str  # RFC 3339
    policy_resolved_from: dict[str, str] = field(default_factory=dict)
    command: str | None = None


@dataclass
class GenEvidenceRef:
    """Pointer to a source artifact supporting a finding or proposal.

    Matches EvidenceRef in contracts/retrospective-record.schema.json.
    id MUST match pattern ^e-[0-9]{3,}$.
    """

    id: str
    kind: Literal["file", "event_range", "external"]
    path: str | None = None
    range: str | None = None  # noqa: A003 (shadows builtin but matches JSON schema field name)
    url: str | None = None


@dataclass
class GenFinding:
    """A single finding (helped / not_helpful / gap).

    Matches Finding in contracts/retrospective-record.schema.json.
    id MUST match pattern ^[a-z]-[0-9]{3,}$.
    evidence_refs entries MUST resolve to ids in the parent record's evidence_refs list.
    """

    id: str
    category: FindingCategory
    summary: str
    evidence_refs: list[str] = field(default_factory=list)
    details: str | None = None


@dataclass
class GenProposal:
    """A concrete improvement proposal derived from findings.

    Matches Proposal in contracts/retrospective-record.schema.json.
    id MUST match pattern ^p-[0-9]{3,}$.
    auto_applicable MUST be False when risk_class == "structural".

    ``payload`` (#6385) is the optional structured half of the proposal: a mapping
    validated against the nested record's discriminated :data:`ProposalPayload`
    union, so a generator-shape proposal can say *what* it would apply instead of
    leaving that to free-text ``suggested_action``. It is ``None`` for every
    record written before #6385 and for generation that has not yet graded a
    finding into a payload (#3947); the writer emits the key only when present so
    those records stay byte-identical. Validation lives at the read boundary
    (:func:`specify_cli.retrospective.reader.read_gen_record`), not here, so this
    dataclass keeps its plain-data contract.
    """

    id: str
    category: ProposalCategory
    risk_class: Literal["low", "structural"]
    summary: str
    evidence_refs: list[str]
    suggested_action: str
    auto_applicable: bool
    details: str | None = None
    payload: dict[str, Any] | None = None


@dataclass
class GenRetrospectiveRecord:
    """Top-level generator output record for a mission retrospective.

    Matches the shape in contracts/retrospective-record.schema.json.
    Use validate_record() to enforce all invariants before persisting.

    findings_status values:
      "has_findings"     — at least one of helped/not_helpful/gaps/proposals is non-empty
      "ran_no_findings"  — all four lists are empty; run was successful but found nothing
      "missing" and "failed" are NEVER valid for a persisted record (event-payload only).
    """

    schema_version: Literal[1] = 1
    mission_id: str = ""
    mission_slug: str = ""
    mission_number: int | None = None
    friendly_name: str = ""
    mission_type: str = ""
    target_branch: str = ""
    created_at: str = ""  # RFC 3339
    created_by: GenActor = field(default_factory=lambda: GenActor(kind="runtime", id="unknown"))
    provenance: GenProvenance = field(
        default_factory=lambda: GenProvenance(kind="runtime_post_completion", invoked_at="")
    )
    policy_source: dict[str, str] = field(default_factory=dict)
    findings_status: FindingsStatus = "ran_no_findings"
    helped: list[GenFinding] = field(default_factory=list)
    not_helpful: list[GenFinding] = field(default_factory=list)
    gaps: list[GenFinding] = field(default_factory=list)
    proposals: list[GenProposal] = field(default_factory=list)
    evidence_refs: list[GenEvidenceRef] = field(default_factory=list)
    generator_version: str = ""
    provenance_history: list[GenProvenance] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Validation error + validate_record()
# ---------------------------------------------------------------------------


class RecordValidationError(Exception):
    """Raised by validate_record() when a GenRetrospectiveRecord violates invariants.

    Attributes:
        violation: Short machine-readable code for the violated invariant.
        detail:    Human-readable description.
    """

    def __init__(self, violation: str, detail: str) -> None:
        self.violation = violation
        self.detail = detail
        super().__init__(f"[{violation}] {detail}")


def validate_record(record: "GenRetrospectiveRecord") -> None:
    """Validate all data-model invariants for a generator record.

    Raises RecordValidationError for any violation:
    1. findings_status not in the two allowed persisted values.
    2. findings_status == "has_findings" AND all four lists empty.
    3. findings_status == "ran_no_findings" AND any list non-empty.
    4. provenance.kind == "synthesize_fabricate" AND findings_status != "ran_no_findings".
    5. Any Finding/Proposal evidence_ref id not present in top-level evidence_refs.

    Args:
        record: The generator record to validate.

    Raises:
        RecordValidationError: On the FIRST invariant violation found.
    """
    # Invariant 1: findings_status must be one of the two allowed persisted values.
    # "missing" and "failed" are event-payload-only states and MUST NOT appear in a persisted record.
    allowed_status: frozenset[str] = frozenset({"has_findings", "ran_no_findings"})
    if record.findings_status not in allowed_status:
        raise RecordValidationError(
            violation="invalid_findings_status",
            detail=(
                f"findings_status {record.findings_status!r} is not a valid persisted value. "
                "Allowed: 'has_findings', 'ran_no_findings'. "
                "'missing' and 'failed' are event-payload-only states."
            ),
        )

    has_any = bool(record.helped or record.not_helpful or record.gaps or record.proposals)

    # Invariant 2: has_findings requires at least one non-empty list.
    if record.findings_status == "has_findings" and not has_any:
        raise RecordValidationError(
            violation="has_findings_but_all_lists_empty",
            detail=(
                "findings_status='has_findings' but all four lists (helped, not_helpful, "
                "gaps, proposals) are empty. Either populate at least one list or set "
                "findings_status='ran_no_findings'."
            ),
        )

    # Invariant 3: ran_no_findings requires all lists to be empty.
    if record.findings_status == "ran_no_findings" and has_any:
        nonempty = [
            name
            for name, lst in (
                ("helped", record.helped),
                ("not_helpful", record.not_helpful),
                ("gaps", record.gaps),
                ("proposals", record.proposals),
            )
            if lst
        ]
        raise RecordValidationError(
            violation="ran_no_findings_but_lists_non_empty",
            detail=(
                f"findings_status='ran_no_findings' but lists are non-empty: {nonempty}. "
                "Set findings_status='has_findings' or clear all four lists."
            ),
        )

    # Invariant 4: synthesize_fabricate provenance must produce ran_no_findings.
    if (
        record.provenance.kind == "synthesize_fabricate"
        and record.findings_status != "ran_no_findings"
    ):
        raise RecordValidationError(
            violation="synthesize_fabricate_must_have_no_findings",
            detail=(
                "provenance.kind='synthesize_fabricate' implies findings_status must be "
                "'ran_no_findings'. The fabrication compatibility path may never author a "
                "has_findings record (FR-014 invariant)."
            ),
        )

    # Invariant 5: every evidence_ref id in findings/proposals must resolve to
    # an id in the top-level evidence_refs list.
    known_evidence_ids: set[str] = {e.id for e in record.evidence_refs}

    for finding in (*record.helped, *record.not_helpful, *record.gaps):
        for ref_id in finding.evidence_refs:
            if ref_id not in known_evidence_ids:
                raise RecordValidationError(
                    violation="unresolved_evidence_ref",
                    detail=(
                        f"Finding id={finding.id!r} references evidence_ref id={ref_id!r} "
                        "which is not present in the top-level evidence_refs list."
                    ),
                )

    for proposal in record.proposals:
        for ref_id in proposal.evidence_refs:
            if ref_id not in known_evidence_ids:
                raise RecordValidationError(
                    violation="unresolved_evidence_ref",
                    detail=(
                        f"Proposal id={proposal.id!r} references evidence_ref id={ref_id!r} "
                        "which is not present in the top-level evidence_refs list."
                    ),
                )
